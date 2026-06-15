#!/usr/bin/env python3
"""
popyt_keyless.py — warstwa POPYTU bez klucza (dla dossier-niszy-keyless / badaj-popyt).

Wyniki testów 14.06.2026 (curl, na żywo) — keyless ma tu różny stan per sygnał:
  - AUTOCOMPLETE  ✅ solidny:  suggestqueries.google.com (client=chrome, utf-8). „Język klienta".
  - MAPS          ✅ częściowy: OSM Overpass/Nominatim = LICZBA firm (nasycenie), ale BEZ ocen/recenzji.
  - TRENDS        ✗ kruchy:    trends.google.com bez klucza zwraca 429/302 (blok per IP). Miękkie zejście.

Zasada (D-2026-06-14-01): kluczy Łukasza nie shippujemy. Trends/oceny Maps tylko jeśli
user poda WŁASNY klucz SerpApi (fallback po stronie badaj-popyt). Bez klucza: popyt opiera
się na autocomplete (intencja) + kanałach bólu — to wystarcza na werdykt „jest/słaby popyt".
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, http.cookiejar, json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def _get(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.status


def autocomplete(q, hl="pl"):
    """KEYLESS ✅ — podpowiedzi Google (co ludzie realnie wpisują). Zwraca (lista, err)."""
    url = "http://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "chrome", "hl": hl, "ie": "utf-8", "oe": "utf-8", "q": q})
    try:
        raw, _ = _get(url)
        d = json.loads(raw.decode("utf-8", "replace"))
        return (d[1] if len(d) > 1 else []), None
    except Exception as e:
        return [], f"autocomplete err: {e}"


def maps_count(q, city, hl="pl"):
    """KEYLESS częściowy — liczba miejsc pasujących do frazy w mieście (OSM Nominatim).
    Nasycenie rynku (proxy). BEZ ocen/recenzji — luka jakości jest niedostępna bez klucza.
    Zwraca (liczba|None, err)."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": f"{q} {city}", "format": "json", "limit": 50, "accept-language": hl})
    try:
        raw, _ = _get(url, headers={"User-Agent": "dossier-niszy-keyless/1.0 (research)"})
        d = json.loads(raw.decode("utf-8", "replace"))
        return len(d), None
    except Exception as e:
        return None, f"nominatim err: {e}"


def trends(q, geo="PL", okres="today 12-m"):
    """KEYLESS ✅ (lokalnie na maszynie usera) — Google Trends bez klucza: explore → widgetdata.
    Potwierdzone 14.06 na Macu Łukasza (54 punkty). Rozgrzewka cookie + backoff na 429; miękkie
    zejście gdy IP zablokowany. Zwraca (points[{date,value}], rising[str], top[str], err).
    points w kształcie zgodnym z badaj-popyt.analyze_trend (lista {date,value})."""
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def g(url, tries=4):
        for i in range(tries):
            try:
                r = op.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25)
                return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 429 and i < tries - 1:
                    time.sleep(12 * (i + 1)); continue  # backoff: 12s, 24s, 36s
                return None
            except Exception:
                if i < tries - 1:
                    time.sleep(6); continue
                return None
        return None

    # 0) rozgrzewka cookie NID (429 na warmupie bywa normą — cookie i tak się ustawia)
    try:
        op.open(urllib.request.Request(
            f"https://trends.google.com/trends/explore?geo={geo}&q={urllib.parse.quote(q)}&hl=pl",
            headers={"User-Agent": UA}), timeout=20)
    except Exception:
        pass
    time.sleep(1)
    # 1) explore → tokeny widgetów
    ex = g("https://trends.google.com/trends/api/explore?" + urllib.parse.urlencode(
        {"hl": "pl", "tz": "0",
         "req": json.dumps({"comparisonItem": [{"keyword": q, "geo": geo, "time": okres}], "category": 0, "property": ""}),
         "geo": geo}))
    if not ex or not ex.lstrip().startswith(")]}"):
        return [], [], [], "blok keyless (429/302) — Trends pominięty"
    try:
        widgets = json.loads(ex[ex.find("{"):]).get("widgets", [])
    except Exception:
        return [], [], [], "parse explore"
    # 2) TIMESERIES → realne punkty trendu
    points = []
    tsw = [x for x in widgets if x.get("id") == "TIMESERIES"]
    if tsw:
        w = tsw[0]; time.sleep(1)
        md = g("https://trends.google.com/trends/api/widgetdata/multiline?" + urllib.parse.urlencode(
            {"hl": "pl", "tz": "0", "req": json.dumps(w["request"]), "token": w["token"], "geo": geo}))
        if md and md.lstrip().startswith(")]}"):
            try:
                for p in json.loads(md[md.find("{"):])["default"]["timelineData"]:
                    if p.get("isPartial"):
                        continue  # ostatni niepełny okres — pomijamy (jak SerpApi partial_data)
                    v = p.get("value", [0])
                    points.append({"date": p.get("formattedTime") or str(p.get("time", "")),
                                   "value": v[0] if v else 0})
            except Exception:
                pass
    # 3) RELATED_QUERIES → rising/top (świeży vs utrwalony popyt)
    rising, top = [], []
    rqw = [x for x in widgets if x.get("id") == "RELATED_QUERIES"]
    if rqw:
        w2 = rqw[0]; time.sleep(1)
        rd = g("https://trends.google.com/trends/api/widgetdata/relatedsearches?" + urllib.parse.urlencode(
            {"hl": "pl", "tz": "0", "req": json.dumps(w2["request"]), "token": w2["token"], "geo": geo}))
        if rd and rd.lstrip().startswith(")]}"):
            try:
                rl = json.loads(rd[rd.find("{"):])["default"]["rankedList"]
                if len(rl) >= 1:
                    top = [k["query"] for k in rl[0]["rankedKeyword"][:8]]
                if len(rl) >= 2:
                    rising = [k["query"] for k in rl[1]["rankedKeyword"][:8]]
            except Exception:
                pass
    return points, rising, top, None


def main():
    ap = argparse.ArgumentParser(description="Popyt keyless — autocomplete (✅) + maps count (◐) + trends (✗ kruchy)")
    ap.add_argument("--nisza", "-q", required=True)
    ap.add_argument("--location", help="miasto dla Maps (nasycenie)")
    a = ap.parse_args()
    sugg, e1 = autocomplete(a.nisza)
    out = {"nisza": a.nisza, "autocomplete": {"n": len(sugg), "lista": sugg[:15], "err": e1}}
    pts, rising, top, e3 = trends(a.nisza)
    out["trends"] = {"punkty": len(pts), "ostatnie": [p["value"] for p in pts[-6:]],
                     "rising": rising[:5], "err": e3}
    if a.location:
        cnt, e2 = maps_count(a.nisza, a.location)
        out["maps"] = {"miasto": a.location, "liczba_firm": cnt, "oceny": "niedostępne keyless", "err": e2}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
