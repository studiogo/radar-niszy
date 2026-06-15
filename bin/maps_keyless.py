#!/usr/bin/env python3
"""
maps_keyless.py — recenzje wizytówek Google BEZ klucza (headless, seleniumbase UC).

KANAŁ OPCJONALNY. Headless + bezobsługowe. Wyciąga recenzje ≤3★ (skargi/bóle klientów firm
lokalnych) z wielu wizytówek. Tylko narzekające (≤3★), „jak najwięcej" = scroll-harvest po
`data-review-id` (przebija wirtualizację) + sort „najniższe oceny".

DLACZEGO seleniumbase uc=True (a nie goły Playwright): goły headless Google WYKRYWA i okraja
recenzje do ~10 + wyłącza doładowanie. Tryb UC (undetected) sprawia, że Google traktuje go jak
prawdziwą przeglądarkę → pełne recenzje + scroll działa. Wzorzec: repo georgekhananaev/
google-reviews-scraper-pro (MIT, ⭐251) — odwzorowany rdzeń, bez ich Mongo/S3/FastAPI.

Selektory (sprawdzone: Tampermonkey Łukasza + repo): karta div[data-review-id], autor .d4r55,
ocena span.kvMYJc[aria-label], treść span.wiI7pd, data .rsqaWe, „Więcej" button.w8nwRe.kyuRq.

Kontrakt sygnału (zgodny z dossier-niszy.py): {text, src, autor, score, match}.

Użycie:
  maps_keyless.py --nisza "fizjoterapia" --location "Warszawa" [--max-firm 8] [--max-rec 200] [--widoczna]
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, json, sys, time
from pathlib import Path

SOCS = "CAISNQgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"  # cookie zgody → pomija consent wall
LOWEST = ["Najniższa ocena", "Lowest rating", "Lowest"]  # nazwa pozycji menu sortu (PL/EN)

# JS: zbierz widoczne karty do window.__acc po data-review-id (akumulacja mimo wirtualizacji)
HARVEST_JS = r"""
window.__acc = window.__acc || {};
const cl = s => (s||'').replace(/\s+/g,' ').trim();
for (const c of document.querySelectorAll('div[data-review-id]')) {
  const id = c.getAttribute('data-review-id'); if (!id || window.__acc[id]) continue;
  const m = c.querySelector('button.w8nwRe.kyuRq'); if (m) { try { m.click(); } catch(e){} }
  const au = cl(c.querySelector('.d4r55') && c.querySelector('.d4r55').innerText);
  const rt = c.querySelector('span.kvMYJc[aria-label], span[role=img][aria-label]');
  let sc = null; if (rt) { const mm=(rt.getAttribute('aria-label')||'').match(/(\d)/); if(mm) sc=parseInt(mm[1]); }
  const tx = cl((c.querySelector('span.wiI7pd, .MyEned')||{}).innerText);
  let dt = cl((c.querySelector('.rsqaWe')||{}).innerText);
  window.__acc[id] = {autor: au||null, score: sc, text: tx, date: dt};
}
return Object.keys(window.__acc).length;
"""
SETPANE_JS = r"""
const PANE='div[role="main"] div.m6QErb.DxyBCb.kA9KIf.dS8AEf';
let pane = document.querySelector(PANE);
if (!pane) { const rv = document.querySelector('div[data-review-id]');
  if (rv) { let p = rv.parentElement; while (p) { const s = getComputedStyle(p);
    if ((s.overflowY==='auto'||s.overflowY==='scroll') && p.scrollHeight>p.clientHeight+10){pane=p;break;} p=p.parentElement; } } }
window.__pane = pane; return !!pane;
"""


def _reviews_url(href):
    """Buduje dedykowany URL pełnego feedu recenzji (metoda repo): .../place/<nazwa>/reviews?hl=pl."""
    if "/place/" not in href:
        return None
    parts = href.split("/place/")
    name = parts[1].split("/")[0]
    if not name:
        return None
    return parts[0] + "/place/" + name + "/reviews?hl=pl"


def _click_reviews_tab(d):
    for sel in ['button[role="tab"][aria-label*="Opinie" i]', 'button[role="tab"][aria-label*="review" i]',
                'button[role="tab"][aria-label*="recenzj" i]']:
        try:
            d.find_element("css selector", sel)
            d.execute_script("arguments[0].click();", d.find_element("css selector", sel))
            time.sleep(2.5)
            return True
        except Exception:
            pass
    return False


def _sort_lowest(d, log, name):
    for sel in ['button[aria-label*="Sortuj" i]', 'button[aria-label*="Sort" i]']:
        try:
            d.execute_script("arguments[0].click();", d.find_element("css selector", sel))
            time.sleep(1.0)
            for item in d.find_elements("css selector", '[role="menuitemradio"], [role="menuitem"]'):
                t = (item.text or "").strip()
                if any(t.startswith(x) or x in t for x in LOWEST):
                    d.execute_script("arguments[0].click();", item)
                    time.sleep(2.5)
                    return True
        except Exception:
            pass
    log.append(f"{name[:24]}: sortu 'najniższe' nie ustawiono (zbieram domyślne i filtruję)")
    return False


def scrape_place(d, href, name, max_rec, max_idle=12, max_attempts=80):
    """Otwiera wizytówkę, sort najniższe, scroll-harvest po data-review-id. Zwraca dict acc."""
    # PRIMARY: dedykowany URL pełnego feedu recenzji (głęboki scroll); fallback: klik zakładki
    rev = _reviews_url(href)
    opened = False
    if rev:
        d.get(rev); time.sleep(3.5)
        try:
            opened = d.execute_script("return document.querySelectorAll('div[data-review-id]').length") > 0
        except Exception:
            opened = False
    if not opened:
        d.get(href); time.sleep(3)
        if not _click_reviews_tab(d):
            d.refresh(); time.sleep(3); _click_reviews_tab(d)
    time.sleep(2)
    _sort_lowest(d, [], name)
    d.execute_script("window.__acc = {};")
    has_pane = d.execute_script(SETPANE_JS)
    idle, attempts, prev = 0, 0, 0
    while attempts < max_attempts and idle < max_idle:
        n = d.execute_script(HARVEST_JS)
        if n == prev:
            idle += 1
        else:
            idle = 0
        prev = n
        attempts += 1
        if max_rec and n >= max_rec:
            break
        try:
            if has_pane:
                d.execute_script("if(window.__pane) window.__pane.scrollBy(0, window.__pane.scrollHeight);")
            else:
                d.execute_script("window.scrollBy(0, 2500);")
        except Exception:
            pass
        time.sleep(1.3)
    return d.execute_script("return window.__acc || {};")


def run(nisza, city, max_firm, max_rec, headless=True):
    from seleniumbase import Driver
    out, log = [], []
    d = Driver(uc=True, headless=headless, incognito=True)
    try:
        d.get("https://www.google.com/")
        try:
            d.add_cookie({"name": "SOCS", "value": SOCS, "domain": ".google.com"})
        except Exception:
            pass
        d.get(f"https://www.google.com/maps/search/{nisza}+{city}/?hl=pl&gl=pl")
        time.sleep(5)
        for xp in ['//button[.//span[contains(.,"Zaakceptuj")]]', '//button[contains(.,"Accept all")]']:
            try:
                d.execute_script("arguments[0].click();", d.find_element("xpath", xp)); time.sleep(2); break
            except Exception:
                pass
        # zbierz linki wizytówek
        hrefs = []
        try:
            for a in d.find_elements("css selector", "a.hfpxzc")[:max_firm]:
                h = a.get_attribute("href")
                if h:
                    hrefs.append((h, a.get_attribute("aria-label") or nisza))
        except Exception:
            pass
        if not hrefs:  # wpadliśmy prosto w jedną wizytówkę
            hrefs = [(d.current_url, nisza)]
        log.append(f"wizytówek do przejścia: {len(hrefs)}")
        for h, nm in hrefs:
            try:
                acc = scrape_place(d, h, nm, max_rec)
            except Exception as e:
                log.append(f"{nm[:24]}: błąd {str(e)[:50]}"); continue
            firm_n = 0
            for r in acc.values():
                if r.get("text") and len(r["text"]) >= 12 and (r.get("score") is None or r["score"] <= 3):
                    out.append({"text": r["text"], "src": f"Google: {nm[:24]} (bez klucza)",
                                "autor": r.get("autor"), "score": r.get("score"), "match": nm})
                    firm_n += 1
            log.append(f"{nm[:30]}: {len(acc)} recenzji, {firm_n} skarg ≤3★")
    finally:
        try:
            d.quit()
        except Exception:
            pass
    return out, log


def main():
    ap = argparse.ArgumentParser(description="Maps keyless — recenzje wizytówek Google (seleniumbase UC, headless)")
    ap.add_argument("--nisza", "-q", required=True)
    ap.add_argument("--location", "-l", required=True)
    ap.add_argument("--max-firm", type=int, default=8)
    ap.add_argument("--max-rec", type=int, default=200)
    ap.add_argument("--widoczna", action="store_true", help="okno widoczne (debug)")
    ap.add_argument("--out-file")
    a = ap.parse_args()
    try:
        out, log = run(a.nisza, a.location, a.max_firm, a.max_rec, headless=not a.widoczna)
    except Exception as e:
        print(json.dumps({"error": str(e), "hint": "pip install seleniumbase + Chrome"}, ensure_ascii=False)); sys.exit(1)
    res = {"n": len(out), "log": log, "sygnaly": out}
    if a.out_file:
        Path(a.out_file).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
