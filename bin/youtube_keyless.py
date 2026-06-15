#!/usr/bin/env python3
"""
youtube_keyless.py — sygnaly z YouTube BEZ klucza API (yt-dlp).

Po co: youtube_pains uzywa youtube-data-api (search.list = 100 jednostek kwoty/zapytanie,
limit ~100 zapytan/dzien). yt-dlp robi to samo BEZ klucza i bez kwoty: wyszukiwanie
(ytsearchN:), komentarze (--write-comments) + polubienia (like_count). Bonus vs Reddit RSS:
keyless YT NIESIE score (polubienia komentarza).

Wymaga: yt-dlp (jest w stacku via yt-transcribe.py), deno (rozwiazuje JS challenge YT).
Kontrakt sygnalu (zgodny z dossier-niszy.py): {text, src, autor, score}.

Uzycie:
  youtube_keyless.py --frazy "automatyzacja firmy;agent ai" [--n-wideo 3] [--max-kom 15] [--wszystkie]
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, json, re, subprocess, sys
from pathlib import Path

# markery bolu/pytania (jak w oryginalnym youtube_pains) — komentarze YT to w wiekszosci szum „super!"
PAIN_KEYS = ("jak ", "czy ", "problem", "nie wiem", "nie dziala", "nie działa", "szukam",
             "poleci", "narzędz", "narzedz", "automat", "?", "pomóż", "pomoz", "da się",
             "da sie", "błąd", "blad", "trudno", "nie umiem", "nie potrafię")


def _clean(t):
    return re.sub(r"\s+", " ", (t or "").replace("\n", " ")).strip()


def search(query, n=5):
    """ytsearchN: -> [{id,title}] (bez klucza)."""
    try:
        r = subprocess.run(["yt-dlp", f"ytsearch{n}:{query}", "--flat-playlist",
                            "--print", "%(id)s\t%(title)s", "--no-warnings"],
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        return [], f"search err: {e}"
    out = []
    for line in r.stdout.splitlines():
        if "\t" in line:
            vid, tit = line.split("\t", 1)
            if vid.strip():
                out.append({"id": vid.strip(), "title": tit.strip()})
    return out, None


def comments(video_id, max_comments=20):
    """Komentarze wideo (bez klucza) -> [{text,author,likes}]."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        r = subprocess.run(
            ["yt-dlp", url, "--skip-download", "--write-comments",
             "--extractor-args", f"youtube:max_comments={max_comments},all,0,0;comment_sort=top",
             "-J", "--no-warnings"],
            capture_output=True, text=True, timeout=240)
        d = json.loads(r.stdout)
    except Exception as e:
        return [], f"kom err: {e}"
    out = []
    for c in (d.get("comments") or []):
        out.append({"text": _clean(c.get("text")),
                    "author": (c.get("author") or "").lstrip("@") or None,
                    "likes": c.get("like_count")})
    return out, None


def collect(queries, n_videos=3, max_comments=15, tylko_bole=True):
    """L1 keyless: dla kazdej frazy szukaj wideo -> ciagnij komentarze -> sygnaly bolu.
    Zwraca (lista_sygnalow, log[])."""
    out, seen, log = [], set(), []
    for q in [x for x in (queries or []) if x]:
        vids, err = search(q, n_videos)
        log.append(f"search '{q}': {len(vids)} wideo" + (f" ({err})" if err else ""))
        for v in vids:
            koms, kerr = comments(v["id"], max_comments)
            log.append(f"  {v['id']}: {len(koms)} kom" + (f" ({kerr})" if kerr else ""))
            for c in koms:
                t = c["text"]
                if not t or len(t) < 25:
                    continue
                if tylko_bole and not any(k in t.lower() for k in PAIN_KEYS):
                    continue
                key = (c["author"], t[:60])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"text": t, "src": f"YouTube „{v['title'][:40]}” (bez klucza)",
                            "autor": c["author"], "score": c["likes"]})
    return out, log


def main():
    ap = argparse.ArgumentParser(description="YouTube keyless — yt-dlp (bez klucza API)")
    ap.add_argument("--frazy", required=True, help="frazy rozdzielone ';'")
    ap.add_argument("--n-wideo", type=int, default=3, help="ile wideo na frazę")
    ap.add_argument("--max-kom", type=int, default=15, help="ile komentarzy na wideo")
    ap.add_argument("--wszystkie", action="store_true", help="nie filtruj po markerach bólu")
    ap.add_argument("--out-file")
    a = ap.parse_args()
    qs = [f.strip() for f in a.frazy.split(";") if f.strip()]
    out, log = collect(qs, n_videos=a.n_wideo, max_comments=a.max_kom, tylko_bole=not a.wszystkie)
    res = {"n": len(out), "log": log, "sygnaly": out}
    if a.out_file:
        Path(a.out_file).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
