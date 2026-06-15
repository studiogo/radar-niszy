#!/usr/bin/env python3
"""
gplay_keyless.py — dobór aplikacji Google Play BEZ klucza (scraping HTML wyszukiwarki).

Po co: google_play_pains ciągnie recenzje keyless (google-play-scraper), ale DOBÓR apek
robił przez płatne SerpApi, bo `search()` biblioteki jest zepsuty (TypeError 'NoneType' —
Google zmieniło strukturę odpowiedzi, potwierdzone 14.06.2026). Ten adapter dobiera app_id
ze strony wyszukiwarki Play (HTML, SSR) — zero klucza.

Uzycie:
  gplay_keyless.py --fraza "automatyzacja" [--n 8]
"""
import argparse, json, re, urllib.parse, urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def search_app_ids(query, n=8, lang="pl", country="pl"):
    """Zwraca (lista_app_id, err). app_id w kolejności trafności Play (pierwsze = najtrafniejsze)."""
    url = "https://play.google.com/store/search?" + urllib.parse.urlencode(
        {"q": query, "c": "apps", "hl": lang, "gl": country})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        h = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception as e:
        return [], f"play html err: {e}"
    ids = list(dict.fromkeys(re.findall(r"/store/apps/details\?id=([a-zA-Z0-9_.]+)", h)))
    return ids[:n], None


def main():
    ap = argparse.ArgumentParser(description="Google Play keyless — dobór apek ze strony wyszukiwarki")
    ap.add_argument("--fraza", required=True)
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args()
    ids, err = search_app_ids(a.fraza, a.n)
    print(json.dumps({"ids": ids, "err": err}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
