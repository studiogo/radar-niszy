#!/usr/bin/env python3
"""
fb_keyless.py — posty grup Facebook BEZ klucza/Apify (auto-cookies + seleniumbase UC headless).

⚠️ OSTRZEŻENIE: automat na ZALOGOWANYM koncie FB łamie regulamin FB → ryzyko BANU konta usera.
KANAŁ OPCJONALNY, domyślnie WYŁĄCZONY, świadomy opt-in. Twoich kluczy nie ma — to sesja usera.

Metoda (wzorzec repo thanh2004nguyen/facebook-group-scraper, 2025-06):
  1. browser_cookie3 czyta zalogowaną sesję FB z Chrome (bezobsługowo).
  2. seleniumbase Driver(uc=True) — undetected, wstrzykuje cookies.
  3. goto grupy → scroll → harvest postów z `div[data-ad-rendering-role='story_message']`.
Discovery grup: DuckDuckGo (keyless), żeby nie palić requestów FB na szukaniu.

Kontrakt sygnału (zgodny z dossier-niszy.py): {text, src, autor, score, match}.

Użycie:
  fb_keyless.py --grupa "https://www.facebook.com/groups/<id>" [--max-postow 40]
  fb_keyless.py --nisza "fizjoterapia" [--max-grup 3] [--max-postow 40]
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, html, json, re, sys, time, urllib.parse, urllib.request

POST_SEL = "div[data-ad-rendering-role='story_message']"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def _fb_cookies():
    """Zalogowana sesja FB z Chrome (bezobsługowo). Zwraca (lista_cookies, zalogowany?)."""
    import browser_cookie3 as bc3
    cj = bc3.chrome(domain_name="facebook.com")
    out = [{"name": c.name, "value": c.value, "domain": c.domain or ".facebook.com",
            "path": c.path or "/"} for c in cj]
    have = {c["name"] for c in out}
    return out, ("c_user" in have and "xs" in have)


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


def scrape_group(d, group_url, max_posts=40, max_scroll=40):
    """Scroll + harvest postów grupy (story_message). d = już uwierzytelniony Driver."""
    d.get(group_url + ("?hl=pl" if "?" not in group_url else ""))
    time.sleep(5)
    posts, seen, idle = [], set(), 0
    for _ in range(max_scroll):
        n0 = len(seen)
        for e in d.find_elements("css selector", POST_SEL):
            try:
                t = (e.text or "").strip()
            except Exception:
                continue
            if t and len(t) > 25 and t not in seen:
                seen.add(t); posts.append(t)
        if len(posts) >= max_posts:
            break
        idle = idle + 1 if len(seen) == n0 else 0
        if idle >= 5:
            break
        d.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2.2)
    return posts


def run(group_urls, nisza_label, max_posts, headless=True):
    from seleniumbase import Driver
    cookies, logged = _fb_cookies()
    if not logged:
        return [], "brak zalogowanej sesji FB w Chrome (zaloguj się w przeglądarce) — kanał pominięty"
    out, log = [], []
    d = Driver(uc=True, headless=headless, incognito=False)
    try:
        d.get("https://www.facebook.com/")
        for c in cookies:
            try:
                d.add_cookie(c)
            except Exception:
                pass
        for url in group_urls:
            try:
                posts = scrape_group(d, url, max_posts)
            except Exception as e:
                log.append(f"{url[-30:]}: błąd {str(e)[:50]}"); continue
            for p in posts:
                out.append({"text": p[:1200], "src": f"FB grupa {url.rstrip('/').split('/')[-1][:20]}",
                            "autor": None, "score": None, "match": nisza_label})
            log.append(f"{url[-30:]}: {len(posts)} postów")
    finally:
        try:
            d.quit()
        except Exception:
            pass
    return out, ("; ".join(log) if log else None)


def main():
    ap = argparse.ArgumentParser(description="FB grupy keyless — auto-cookies + seleniumbase UC (OPT-IN, ryzyko banu konta)")
    ap.add_argument("--grupa", help="bezpośredni URL grupy")
    ap.add_argument("--nisza", help="temat — discovery grup przez DuckDuckGo")
    ap.add_argument("--max-grup", type=int, default=3)
    ap.add_argument("--max-postow", type=int, default=40)
    ap.add_argument("--widoczna", action="store_true")
    ap.add_argument("--out-file")
    a = ap.parse_args()
    if a.grupa:
        urls, label = [a.grupa], (a.nisza or a.grupa)
    elif a.nisza:
        urls, label = discover_groups(a.nisza, a.max_grup), a.nisza
    else:
        print(json.dumps({"error": "podaj --grupa albo --nisza"})); sys.exit(2)
    if not urls:
        print(json.dumps({"n": 0, "log": "brak grup z DuckDuckGo", "sygnaly": []}, ensure_ascii=False)); return
    try:
        out, log = run(urls, label, a.max_postow, headless=not a.widoczna)
    except Exception as e:
        print(json.dumps({"error": str(e), "hint": "pip install seleniumbase browser_cookie3 + Chrome zalogowany w FB"}, ensure_ascii=False)); sys.exit(1)
    res = {"n": len(out), "grupy": urls, "log": log, "sygnaly": out}
    if a.out_file:
        from pathlib import Path
        Path(a.out_file).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
