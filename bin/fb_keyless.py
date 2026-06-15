#!/usr/bin/env python3
"""
fb_keyless.py — posty publicznych grup Facebooka BEZ klucza/Apify (seleniumbase UC headless).

Dwie ścieżki uwierzytelnienia (cross-platform):
  ŚCIEŻKA 1 — browser_cookie3: czyta zalogowaną sesję FB z Twojego Chrome (Mac/Linux — zero logowania).
  ŚCIEŻKA 2 — DEDYKOWANY profil: gdy ścieżka 1 padnie (nowy Chrome ≥127 na Windows szyfruje
              ciasteczka App-Bound Encryption → browser_cookie3 ich nie odczyta). Wtedy narzędzie
              używa własnego, oddzielnego profilu Chrome — logujesz się do FB RAZ (`--login`),
              potem działa headless. Nie rusza Twojego codziennego Chrome (brak locka), a Chrome
              sam odszyfrowuje swój profil (ABE nieistotne).

⚠️ OSTRZEŻENIE: automat na ZALOGOWANYM koncie FB łamie regulamin FB → ryzyko blokady konta. Opcjonalny.
Discovery grup: DuckDuckGo (keyless). Kontrakt sygnału: {text, src, autor, score, match}.

Użycie:
  fb_keyless.py --login                          # JEDNORAZOWO: otwiera okno, zaloguj się do FB
  fb_keyless.py --nisza "fizjoterapia" [--max-grup 3] [--max-postow 40]
  fb_keyless.py --grupa "https://www.facebook.com/groups/<id>"
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

POST_SEL = "div[data-ad-rendering-role='story_message']"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
# Dedykowany profil Chrome TYLKO dla tego narzędzia (oddzielny od codziennego Chrome usera).
PROFILE_DIR = Path.home() / ".config" / "dossier-niszy-keyless" / "fb-profile"


def _fb_cookies():
    """ŚCIEŻKA 1: zalogowana sesja FB z Chrome przez browser_cookie3. (lista_cookies, zalogowany?).
    Każdy błąd (brak Chrome, App-Bound Encryption na Windows, brak browser_cookie3) → ([], False)."""
    try:
        import browser_cookie3 as bc3
        cj = bc3.chrome(domain_name="facebook.com")
        out = [{"name": c.name, "value": c.value, "domain": c.domain or ".facebook.com",
                "path": c.path or "/"} for c in cj]
        have = {c["name"] for c in out}
        return out, ("c_user" in have and "xs" in have)
    except Exception:
        return [], False


def _logged_in(d):
    """Czy w aktywnym profilu jest zalogowana sesja FB (cookie c_user)."""
    try:
        return any(c.get("name") == "c_user" for c in d.get_cookies())
    except Exception:
        return False


def discover_groups(nisza, n=3):
    """Znajdź URL-e grup FB przez DuckDuckGo (keyless) — bez palenia requestów FB."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": f"site:facebook.com/groups {nisza}", "kl": "pl-pl"})
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20).read().decode("utf-8", "replace")
    except Exception:
        return []
    slugs = re.findall(r'facebook\.com%2Fgroups%2F([0-9A-Za-z._-]+)', raw) + \
            re.findall(r'facebook\.com/groups/([0-9A-Za-z._-]+)', raw)
    seen, out = set(), []
    for s in slugs:
        if s.lower() in ("create", "feed", "discover", "search") or s in seen:
            continue
        seen.add(s); out.append(f"https://www.facebook.com/groups/{s}")
        if len(out) >= n:
            break
    return out


# Ekstrakcja postów metodą 2026 (wzorzec belia-it/facebook-scraper): kontener [role="feed"] →
# per element: tekst z [data-ad-rendering-role="story_message"], a w razie braku sklejone [dir="auto"].
_FEED_JS = r"""
const out = [];
const feed = document.querySelector('[role="feed"]');
const items = feed ? Array.from(feed.children)
                   : Array.from(document.querySelectorAll('div[data-ad-rendering-role="story_message"]'));
for (const it of items) {
  let txt = "";
  const sm = it.querySelector ? it.querySelector('[data-ad-rendering-role="story_message"]') : null;
  const self = (it.matches && it.matches('[data-ad-rendering-role="story_message"]')) ? it : null;
  const body = sm || self;
  if (body) {
    txt = (body.innerText || "").trim();
  } else if (it.querySelectorAll) {
    const s = new Set();
    for (const b of it.querySelectorAll('[dir="auto"]')) {
      const t = (b.innerText || "").trim();
      if (t && t.length > 3 && !s.has(t)) { s.add(t); txt += t + "\n"; }
    }
    txt = txt.trim();
  }
  if (txt.length > 25) out.push(txt.slice(0, 1500));
}
return out;
"""


def scrape_group(d, group_url, max_posts=40, max_scroll=40):
    """Scroll + harvest postów grupy metodą 2026: czeka na [role="feed"], wyciąga teksty z
    story_message / [dir="auto"]. d = już uwierzytelniony Driver."""
    d.get(group_url + ("?hl=pl" if "?" not in group_url else ""))
    time.sleep(4)
    try:  # FB doładowuje feed Reactem — poczekaj na kontener przed ekstrakcją
        d.wait_for_element('[role="feed"]', timeout=25)
    except Exception:
        pass
    posts, seen, idle = [], set(), 0
    for _ in range(max_scroll):
        n0 = len(seen)
        try:
            found = d.execute_script(_FEED_JS) or []
        except Exception:
            found = []
        for t in found:
            if t and t not in seen:
                seen.add(t); posts.append(t)
        if len(posts) >= max_posts:
            break
        idle = idle + 1 if len(seen) == n0 else 0
        if idle >= 5:
            break
        d.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2.2)
    return posts[:max_posts]


def _harvest(d, group_urls, nisza_label, max_posts):
    out, log = [], []
    for url in group_urls:
        try:
            posts = scrape_group(d, url, max_posts)
        except Exception as e:
            log.append(f"{url[-30:]}: błąd {str(e)[:40]}"); continue
        for p in posts:
            out.append({"text": p[:1200], "src": f"FB grupa {url.rstrip('/').split('/')[-1][:20]}",
                        "autor": None, "score": None, "match": nisza_label})
        log.append(f"{url[-30:]}: {len(posts)} postów")
    return out, ("; ".join(log) if log else None)


def login(timeout=200):
    """JEDNORAZOWO: otwiera WIDOCZNE okno Chrome na dedykowanym profilu, czeka aż user zaloguje się
    do FB (wykryje cookie c_user), zapisuje profil, zamyka. Potem `run()` działa headless."""
    from seleniumbase import Driver
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    d = Driver(uc=True, headless=False, user_data_dir=str(PROFILE_DIR))
    try:
        d.get("https://www.facebook.com/")
        print("Otworzyłem okno Facebooka — zaloguj się. Czekam do ~3 minut…", file=sys.stderr)
        for _ in range(int(timeout / 2)):
            if _logged_in(d):
                return True
            time.sleep(2)
        return False
    finally:
        try:
            d.quit()
        except Exception:
            pass


LOGIN_HINT = ("FB: zaloguj się RAZ w dedykowanym profilu — uruchom: python bin/fb_keyless.py --login "
              "(otworzy okno, zaloguj się do Facebooka; potem zbieranie działa samo).")


def run(group_urls, nisza_label, max_posts, headless=True):
    """ŚCIEŻKA 1 (browser_cookie3) → fallback ŚCIEŻKA 2 (dedykowany profil)."""
    from seleniumbase import Driver
    cookies, logged = _fb_cookies()
    if logged:  # Mac/Linux: wstrzyknij ciasteczka do świeżego profilu
        d = Driver(uc=True, headless=headless, incognito=False)
        try:
            d.get("https://www.facebook.com/")
            for c in cookies:
                try:
                    d.add_cookie(c)
                except Exception:
                    pass
            return _harvest(d, group_urls, nisza_label, max_posts)
        finally:
            try:
                d.quit()
            except Exception:
                pass
    # Windows/ABE: dedykowany profil (wymaga jednorazowego --login)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    d = Driver(uc=True, headless=headless, user_data_dir=str(PROFILE_DIR))
    try:
        d.get("https://www.facebook.com/")
        time.sleep(3)
        if not _logged_in(d):
            return [], LOGIN_HINT
        return _harvest(d, group_urls, nisza_label, max_posts)
    finally:
        try:
            d.quit()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="FB grupy keyless — browser_cookie3 / dedykowany profil seleniumbase UC (OPT-IN, ryzyko banu konta)")
    ap.add_argument("--login", action="store_true", help="JEDNORAZOWO: otwórz okno i zaloguj się do FB (dedykowany profil)")
    ap.add_argument("--grupa", help="bezpośredni URL grupy")
    ap.add_argument("--nisza", help="temat — discovery grup przez DuckDuckGo")
    ap.add_argument("--max-grup", type=int, default=3)
    ap.add_argument("--max-postow", type=int, default=40)
    ap.add_argument("--widoczna", action="store_true")
    ap.add_argument("--out-file")
    a = ap.parse_args()
    if a.login:
        try:
            ok = login()
        except Exception as e:
            print(json.dumps({"ok": False, "msg": f"Logowanie nie wystartowało: {str(e)[:100]}"}, ensure_ascii=False)); return
        print(json.dumps({"ok": ok, "msg": ("Zalogowano — profil FB zapisany, gotowe." if ok
                          else "Nie wykryto logowania w czasie. Spróbuj ponownie: --login")}, ensure_ascii=False))
        return
    if a.grupa:
        urls, label = [a.grupa], (a.nisza or a.grupa)
    elif a.nisza:
        urls, label = discover_groups(a.nisza, a.max_grup), a.nisza
    else:
        print(json.dumps({"error": "podaj --grupa albo --nisza (albo --login)"})); sys.exit(2)
    if not urls:
        print(json.dumps({"n": 0, "log": "brak grup z DuckDuckGo", "sygnaly": []}, ensure_ascii=False)); return
    try:
        out, log = run(urls, label, a.max_postow, headless=not a.widoczna)
    except Exception as e:
        # Graceful skip — Facebook NIGDY nie wywala całego researchu.
        print(json.dumps({"n": 0, "log": f"Facebook pominięty: {str(e)[:80]}", "sygnaly": []}, ensure_ascii=False))
        return
    res = {"n": len(out), "grupy": urls, "log": log, "sygnaly": out}
    if a.out_file:
        Path(a.out_file).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
