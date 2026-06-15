#!/usr/bin/env python3
"""
web_keyless.py — wyszukiwanie w sieci BEZ klucza (DuckDuckGo HTML).

Zastępuje SerpApi/Tavily w ETAP0 (odkrywanie źródeł/pod-nisz) i ETAP5 (sprawdzanie
konkurencji) wersji keyless. DuckDuckGo HTML (`html.duckduckgo.com/html`) zwraca wyniki
bez klucza i bez JS. fallback (gdy user ma klucz): SerpApi/Tavily — poza tym modułem.

Uzycie:
  web_keyless.py --q "automatyzacja małej firmy" [--n 12]
Wyjście JSON: {n, wyniki:[{tytul, url, opis}]}
"""
import argparse, html, json, re, urllib.parse, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def _unwrap(href):
    """DDG owija linki w /l/?uddg=<url> — odpakuj do prawdziwego URL."""
    if "uddg=" in href:
        try:
            return urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
        except Exception:
            return href
    return href


def search(q, n=12):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q, "kl": "pl-pl"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    out = []
    # blok wyniku: <a class="result__a" href="...">tytuł</a> ... <a class="result__snippet">opis</a>
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', raw, re.S):
        href, title = _unwrap(html.unescape(m.group(1))), html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if href.startswith("http") and title:
            out.append({"tytul": title, "url": href, "opis": ""})
        if len(out) >= n:
            break
    # dopnij opisy (snippet) w kolejności
    snips = [html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
             for s in re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', raw, re.S)]
    for i, s in enumerate(snips[:len(out)]):
        out[i]["opis"] = s
    return out


def main():
    ap = argparse.ArgumentParser(description="Web keyless — DuckDuckGo HTML (bez klucza)")
    ap.add_argument("--q", required=True)
    ap.add_argument("--n", type=int, default=12)
    a = ap.parse_args()
    try:
        w = search(a.q, a.n)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False)); return
    print(json.dumps({"n": len(w), "wyniki": w}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
