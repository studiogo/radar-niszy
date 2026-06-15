#!/usr/bin/env python3
"""
reddit_keyless.py — sygnaly z Reddita BEZ klucza/aplikacji (publiczny RSS, Atom).

Po co osobny tor: reddit-search.py (PRAW) ma ZASZYTE klucze aplikacji Reddita —
dziala u Lukasza, ale przy ROZDANIU nietechniczny user ich nie ma. Ten adapter nie
wymaga zadnej rejestracji: czyta publiczny feed Atom (.rss), ktory Reddit nadal serwuje.

Stan na 14.06.2026 (sprawdzone curl):
  - .json (search.json, /r/<sub>/search.json, old.reddit) -> HTTP 403 (Reddit blokuje
    nieautoryzowany JSON, ~190 KB strona blokady).
  - .rss (search.rss globalne + /r/<sub>/search.rss?restrict_sr=1) -> HTTP 200, Atom.
RSS niesie: tytul, autor (/u/...), pelna tresc, subreddit (z linku), date. BRAK score
(to jedyna strata vs PRAW; score zostaje w fallbacku).

Kontrakt sygnalu (zgodny z dossier-niszy.py): {text, src, autor, score, pid, sub, link}.

Uzycie:
  reddit_keyless.py --frazy "adhd focus;procrastination" [--subreddity ADHD,productivity] [--limit 60]
"""
import argparse, html as _html, json, re, sys, time, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
NS = {"a": "http://www.w3.org/2005/Atom"}


def _fetch(url, retries=3, pauza=4.0):
    """GET z retry/backoff na 429/403 (Reddit RSS ma ciasny limit per IP)."""
    last = None
    for proba in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read(), r.status, None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 500, 503) and proba < retries:
                time.sleep(pauza * (proba + 1))  # backoff narastający: 4s, 8s, 12s
                continue
            return None, e.code, last
        except Exception as e:
            last = f"blad {e}"
            if proba < retries:
                time.sleep(pauza * (proba + 1)); continue
            return None, None, last
    return None, None, last


def _strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = _html.unescape(s)  # pełne dekodowanie encji (&#39; &#x27; &amp; itd.)
    return re.sub(r"\s+", " ", s).strip()


def _parse_atom(raw):
    out = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return out
    for e in root.findall("a:entry", NS):
        title = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
        a = e.find("a:author/a:name", NS)
        autor = a.text.replace("/u/", "").strip() if (a is not None and a.text) else None
        link_el = e.find("a:link", NS)
        href = link_el.get("href") if link_el is not None else ""
        cont = _strip(e.findtext("a:content", default="", namespaces=NS) or "")
        sub = re.search(r"/r/([^/]+)/", href)
        sub = sub.group(1) if sub else "?"
        text = (title + ". " + cont).strip(". ").strip()[:1200]
        if text and len(text) > 30:
            out.append({"text": text, "src": f"Reddit r/{sub} (bez klucza)",
                        "autor": autor, "score": None, "pid": href, "sub": sub, "link": href})
    return out


def fetch_comments(post_link, sub, max_kom=15):
    """Dociąga komentarze posta z <link>.rss (keyless). Atom: entry[0]=post, reszta=komentarze.
    Komentarze = najbogatsze źródło bólów. Zwraca (lista_sygnalow, err)."""
    url = post_link.rstrip("/") + ".rss"
    raw, code, err = _fetch(url)
    if not raw:
        return [], (err or f"HTTP {code}")
    try:
        root = ET.fromstring(raw)
    except Exception:
        return [], "parse"
    out = []
    for e in root.findall("a:entry", NS)[1:]:  # [0] = sam post (już mamy), reszta = komentarze
        a = e.find("a:author/a:name", NS)
        autor = a.text.replace("/u/", "").strip() if (a is not None and a.text) else None
        cont = _strip(e.findtext("a:content", default="", namespaces=NS) or "")
        link_el = e.find("a:link", NS)
        href = link_el.get("href") if link_el is not None else ""
        if cont and len(cont) > 25:
            out.append({"text": cont[:1200], "src": f"Reddit r/{sub} komentarz (bez klucza)",
                        "autor": autor, "score": None, "pid": href or cont[:60], "sub": sub, "link": href})
        if len(out) >= max_kom:
            break
    return out, None


def collect(queries, subreddits=None, limit=60, per_query=25, pauza=3.0, pauza_kom=7.0,
            z_komentarzami=False, max_postow_kom=6, max_kom_na_post=15):
    """L1 keyless: dla każdej frazy globalny search.rss; gdy podano subreddity —
    dodatkowo per-sub restrict_sr. Opcjonalnie dociąga komentarze top postów (post.rss).
    Zwraca (lista_sygnalow, log[]). Komentarze są DODATKIEM ponad limit postów."""
    posty, seen, log = [], set(), []
    queries = [q for q in (queries or []) if q]

    def add(raw):
        for s in _parse_atom(raw):
            if s["pid"] not in seen:
                seen.add(s["pid"]); posty.append(s)

    for q in queries:
        # 1) globalnie po całym Reddicie (bez listy subów)
        url = "https://www.reddit.com/search.rss?" + urllib.parse.urlencode(
            {"q": q, "sort": "relevance", "limit": per_query, "t": "year"})
        raw, code, err = _fetch(url)
        log.append(f"global '{q}': HTTP {code}" + (f" ({err})" if err else f", +{len(_parse_atom(raw)) if raw else 0}"))
        if raw:
            add(raw)
        time.sleep(pauza)
        # 2) opcjonalnie precyzyjnie w podanych subach
        for sub in (subreddits or []):
            if len(posty) >= limit:
                break
            surl = f"https://www.reddit.com/r/{sub}/search.rss?" + urllib.parse.urlencode(
                {"q": q, "restrict_sr": 1, "sort": "top", "t": "year", "limit": per_query})
            sraw, scode, serr = _fetch(surl)
            log.append(f"r/{sub} '{q}': HTTP {scode}" + (f" ({serr})" if serr else f", +{len(_parse_atom(sraw)) if sraw else 0}"))
            if sraw:
                add(sraw)
            time.sleep(pauza)
        if len(posty) >= limit:
            break

    posty = posty[:limit]
    out = list(posty)

    # 3) DOCIĄGNIĘCIE KOMENTARZY top postów (post.rss) — najbogatsze źródło bólów
    if z_komentarzami and posty:
        kandydaci = [s for s in posty if "/comments/" in (s.get("link") or "")][:max_postow_kom]
        for s in kandydaci:
            koment, kerr = fetch_comments(s["link"], s["sub"], max_kom=max_kom_na_post)
            log.append(f"komentarze r/{s['sub']} …{s['link'][-14:]}: +{len(koment)}" + (f" ({kerr})" if kerr else ""))
            for k in koment:
                if k["pid"] not in seen:
                    seen.add(k["pid"]); out.append(k)
            time.sleep(pauza_kom)  # komentarze: dłuższa pauza (ciasny limit RSS per IP)
    return out, log


def main():
    ap = argparse.ArgumentParser(description="Reddit keyless — publiczny RSS (bez aplikacji/klucza)")
    ap.add_argument("--frazy", required=True, help="frazy rozdzielone ';'")
    ap.add_argument("--subreddity", help="opcjonalnie CSV subow do precyzyjnego szukania")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--komentarze", action="store_true", help="dociągnij komentarze top postów (post.rss)")
    ap.add_argument("--max-postow-kom", type=int, default=6)
    ap.add_argument("--max-kom-na-post", type=int, default=15)
    ap.add_argument("--out-file")
    args = ap.parse_args()
    queries = [f.strip() for f in args.frazy.split(";") if f.strip()]
    subs = [s.strip() for s in (args.subreddity or "").split(",") if s.strip()]
    out, log = collect(queries, subreddits=subs, limit=args.limit,
                       z_komentarzami=args.komentarze,
                       max_postow_kom=args.max_postow_kom, max_kom_na_post=args.max_kom_na_post)
    res = {"n": len(out), "log": log, "sygnaly": out}
    if args.out_file:
        Path(args.out_file).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
