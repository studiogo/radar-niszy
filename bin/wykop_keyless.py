#!/usr/bin/env python3
"""
wykop_keyless.py — pobiera sygnaly z Wykopu BEZ klucza API (scraping strony tagu, SSR).

Tor bezkluczowy dla nietechnicznych: zero rejestracji aplikacji, zero OAuth.
Strona https://wykop.pl/tag/<tag> renderuje sie serwerowo (Vue SSR) — pelna tresc
wpisow, autorzy i glosy sa w HTML. robots.txt zabrania tylko /api/, sciezki /tag/ sa Allow.

Roznica vs API v3 (tor z kluczem):
  - API v3: pelnotekstowe wyszukiwanie po DOWOLNEJ frazie (search/entries).
  - keyless: przegladanie konkretnego TAGU (fraza musi miec odpowiadajacy tag).

Kontrakt sygnalu (zgodny z dossier-niszy.py): {text, src, autor, score}.

Uzycie:
  wykop_keyless.py --tag sztucznainteligencja [--strony 2] [--limit 60] [--out-file /tmp/x.json]
  wykop_keyless.py --nisza "sztuczna inteligencja"   # tag wyprowadzony z niszy
"""
import argparse, json, re, sys, time, urllib.request, urllib.error
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) dossier-niszy-research/1.0"
WYKOP_BOT_MARKERS = ("mirko-anonim", "wsparcie-ai", "mirko.pro")


def is_bot(txt):
    t = (txt or "").strip().lower()
    return t.startswith("✨") or any(m in t for m in WYKOP_BOT_MARKERS)


def nisza_to_tag(nisza):
    """Tag Wykopu = fraza bez spacji/myslnikow (np. 'sztuczna inteligencja' -> 'sztucznainteligencja')."""
    return re.sub(r"[^a-z0-9ąćęłńóśźż]", "", nisza.lower())


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace"), r.status


def strip_html(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_entries(html):
    """Tnie strone na wpisy top-level (id='comment-<ID>' class='entry stream-tag') i ekstrahuje pola."""
    # granice wpisow top-level
    bounds = [(m.group(1), m.start()) for m in
              re.finditer(r'id="comment-(\d+)"\s+class="entry stream-tag"', html)]
    out = []
    for i, (wid, pos) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else len(html)
        chunk = html[pos:end]
        # autor — link profilu /ludzie/<nick> (pewniejsze niz username w zagniezdzonym span)
        au = re.search(r'/ludzie/([A-Za-z0-9_-]+)', chunk)
        if not au:
            au = re.search(r'class="username[^"]*"[^>]*>(?:<span[^>]*>)?\s*([A-Za-z0-9_-]+)', chunk)
        autor = au.group(1).strip() if au else None
        # data
        dt = re.search(r'datetime="([^"]+)"', chunk)
        data = dt.group(1) if dt else None
        # glosy — rating-box: <li class="zero">0 lub liczba w srodku
        score = 0
        rb = re.search(r'class="rating-box".*?</section>', chunk, re.S)
        if rb:
            num = re.search(r'>\s*(\d+)\s*<', re.sub(r'class="zero"', 'class="z">0<x ', rb.group(0)))
            mscore = re.search(r"<li[^>]*>\s*(\d+)\s*</li>", rb.group(0))
            if mscore:
                score = int(mscore.group(1))
        # tresc — pierwszy entry-content w chunku (top-level wpis, nie komentarze)
        ec = re.search(r'class="entry-content"[^>]*>(.*?)</section>', chunk, re.S)
        text = strip_html(ec.group(1)) if ec else ""
        if text and len(text) > 25 and not is_bot(text):
            out.append({"text": text, "src": "Wykop tag (keyless)",
                        "autor": autor, "score": score, "wid": wid, "data": data})
    return out


def collect(tag, strony=2, limit=60, pauza=2.0):
    """Zbiera wpisy z tagu (bez klucza). Zwraca (lista_sygnalow, log[]).
    Reuzywalne z poziomu skilla (dossier-niszy) jako warstwa L1 keyless."""
    out, seen, log = [], set(), []
    for strona in range(1, strony + 1):
        url = f"https://wykop.pl/tag/{tag}" if strona == 1 else f"https://wykop.pl/tag/{tag}/strona/{strona}"
        try:
            html, status = fetch(url)
        except urllib.error.HTTPError as e:
            log.append(f"strona {strona}: HTTP {e.code}"); break
        except Exception as e:
            log.append(f"strona {strona}: blad {e}"); break
        ents = parse_entries(html)
        log.append(f"strona {strona}: HTTP {status}, {len(html)} B, {len(ents)} wpisow")
        for e in ents:
            if e["wid"] not in seen:
                seen.add(e["wid"]); out.append(e)
        if len(out) >= limit:
            break
        if strona < strony:
            time.sleep(pauza)  # throttle — uprzejmy scraping
    return out[:limit], log


def main():
    ap = argparse.ArgumentParser(description="Wykop keyless — scraping strony tagu (bez API)")
    ap.add_argument("--tag")
    ap.add_argument("--nisza", "-q")
    ap.add_argument("--strony", type=int, default=2, help="ile stron paginacji (po ~14 wpisow)")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--out-file")
    args = ap.parse_args()

    tag = args.tag or (nisza_to_tag(args.nisza) if args.nisza else None)
    if not tag:
        print("podaj --tag albo --nisza", file=sys.stderr); sys.exit(2)

    out, log = collect(tag, strony=args.strony, limit=args.limit)
    result = {"tag": tag, "url": f"https://wykop.pl/tag/{tag}", "n": len(out),
              "log": log, "sygnaly": out}
    if args.out_file:
        Path(args.out_file).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
