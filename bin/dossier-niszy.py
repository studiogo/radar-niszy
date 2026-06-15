#!/usr/bin/env python3
"""
dossier-niszy — jeden raport ze WSZYSTKICH kanałów dla zadanej niszy.

POPYT (reużycie skilla badaj-popyt): Google Trends + Autocomplete + Maps
BÓLE: Wykop (API v3) + YouTube (komentarze) + Google Play + App Store + grupy FB (Apify)

Werdykt łączony: popyt × ból × rynek. Raport HTML.
Każdy kanał izolowany try/except — awaria jednego nie wywala raportu.

Klucze (OPCJONALNE, tylko fallback): warstwowy config usera — config.py (env > .env projektu >
~/.config/dossier-niszy-keyless/.env > Keychain > fallback wsteczny do kluczy autora). Bez kluczy = tor keyless.
Stack: stdlib + google_play_scraper.
"""

try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

HOME = Path.home()
BADAJ = HOME / ".claude/skills/badaj-popyt/bin/badaj-popyt.py"


# ---------- warstwowy config usera (Faza D — onboarding) ----------
def _load_config():
    spec = importlib.util.spec_from_file_location("dnk_config", str(Path(__file__).with_name("config.py")))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CFG = _load_config()
cfg = CFG.get  # cfg(KLUCZ) → warstwy: env > .env projektu > config globalny > Keychain > fallback autora


def tmpdir():
    """Katalog tymczasowy cross-platform (Windows nie ma /tmp)."""
    return Path(tempfile.gettempdir())


def open_file(path):
    """Otwórz plik domyślną aplikacją — cross-platform (mac/Windows/Linux)."""
    p = str(path)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", p])
        elif sys.platform.startswith("win"):
            os.startfile(p)  # noqa: chmod — Windows-only
        else:
            subprocess.run(["xdg-open", p])
    except Exception:
        pass


def badaj_if_keys(keys):
    """Leniwy, OPCJONALNY dostęp do badaj-popyt — TYLKO gdy user ma własne klucze (fallback z kluczem)
    i skill badaj-popyt jest dostępny. Bez tego skill jest w PEŁNI SAMODZIELNY (tor keyless działa bez
    badaj-popyt). Dzięki temu da się go rozdać/uruchomić na obcej maszynie (Windows) bez innych skilli."""
    if not keys:
        return None
    try:
        return load_badaj()
    except Exception:
        return None


# Współrzędne miast dla Maps-popytu — wciągnięte z badaj-popyt (samodzielność, D-2026-06-14-14)
CITY_LL = {
    "warszawa": "@52.2297,21.0122,11z",
    "kraków": "@50.0647,19.9450,11z", "krakow": "@50.0647,19.9450,11z",
    "gdańsk": "@54.3520,18.6466,11z", "gdansk": "@54.3520,18.6466,11z",
    "wrocław": "@51.1079,17.0385,11z", "wroclaw": "@51.1079,17.0385,11z",
    "poznań": "@52.4064,16.9252,11z", "poznan": "@52.4064,16.9252,11z",
    "łódź": "@51.7592,19.4560,11z", "lodz": "@51.7592,19.4560,11z",
    "katowice": "@50.2649,19.0238,11z", "lublin": "@51.2465,22.5684,11z",
    "białystok": "@53.1325,23.1688,11z", "bialystok": "@53.1325,23.1688,11z",
    "szczecin": "@53.4285,14.5528,11z", "bydgoszcz": "@53.1235,18.0084,11z",
    "gdynia": "@54.5189,18.5305,11z", "sopot": "@54.4418,18.5601,11z",
    "rzeszów": "@50.0413,21.9990,11z", "rzeszow": "@50.0413,21.9990,11z",
    "olsztyn": "@53.7784,20.4801,11z",
    "toruń": "@53.0138,18.5984,11z", "torun": "@53.0138,18.5984,11z",
}


def analyze_trend(points):
    """Kierunek trendu: średnia 1. vs ostatniej ćwiartki (wciągnięte z badaj-popyt → samodzielność)."""
    if len(points) < 8:
        return {"dir": "brak danych", "pct": 0, "current": 0, "max": 0, "emoji": "⚪"}
    vals = [p["value"] for p in points]
    qq = max(2, len(vals) // 4)
    first = sum(vals[:qq]) / qq
    last = sum(vals[-qq:]) / qq
    pct = round((last - first) / first * 100) if first else 0
    if pct > 15:
        d, e = "rośnie", "🟢"
    elif pct < -15:
        d, e = "spada", "🔴"
    else:
        d, e = "stabilny", "🟡"
    return {"dir": d, "pct": pct, "current": vals[-1], "max": max(vals), "emoji": e}


def sparkline(points):
    """Mini-wykres trendu (wciągnięte z badaj-popyt → samodzielność)."""
    if not points:
        return ""
    vals = [p["value"] for p in points]
    mx = max(vals) or 1
    bars = "".join(
        f'<div title="{html.escape(str(p["date"]))}: {p["value"]}" style="flex:1;'
        f'height:{max(2, round(p["value"] / mx * 60))}px;background:#3b82f6;margin:0 1px;'
        f'border-radius:1px 1px 0 0;"></div>'
        for p in points
    )
    return f'<div style="display:flex;align-items:flex-end;height:64px;margin:12px 0;">{bars}</div>'


# ---------- reużycie warstwy POPYTU z badaj-popyt ----------
def load_badaj():
    spec = importlib.util.spec_from_file_location("badaj_popyt", str(BADAJ))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def kc(service):
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                           capture_output=True, text=True, check=True)
        k = r.stdout.strip()
        return k if len(k) >= 10 else None
    except subprocess.CalledProcessError:
        return None


def env_val(key):
    try:
        for line in (HOME / ".claude/.env").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def clean(t):
    return re.sub(r"\s+", " ", (t or "").replace("\n", " ")).strip()


RAW_LIMIT = 60  # ile surowych sygnałów ciągnie kanał ZANIM zadziała filtr trafności
FINAL_LIMIT = 12  # ile trafnych zostaje po filtrze (próbka — decyzja D-2026-06-11-06)
MIN_TRAFNE = 3  # < tylu trafnych po filtrze → kanał oznaczony jako „ubogi" (zmiana 4)
CORE_POS_LIMIT = 300  # D-11: dla wpisów tekstowych rdzeń musi paść w pierwszych N znakach (temat, nie wtręt w długim eseju)
# Parametry doboru źródeł per kanał (D-2026-06-13-02 — zdjęte zaszyte limity; skalują z --gleboki).
# Domyślne bezpieczne; orkiestrator v5 / CLI je nadpisuje wg wyboru usera (feedback_skill_limits_interactive_not_hardcoded).
N_APPS = 8       # ile aplikacji przejrzeć (Google Play / App Store) — było zaszyte 4/5
N_FB_GROUPS = 3  # ile grup FB scrape'ować — było zaszyte 1
N_YT_VIDEOS = 3  # ile wideo / frazę na YouTube — było zaszyte 2
GLEBOKOSC_DOMYSLNA = 3  # skala 0-10 (D-2026-06-14-06)


def depth_to_limits(d):
    """Skala głębokości 0-10 → raw_limit (cel sygnałów/kanał). 0/1=płytko, 10=~100.
    Każdy kanał dziedziczy swoje sub-limity z raw_limit (strony/wideo/apki/firmy/grupy)
    → jedno pokrętło steruje całością, kanały pozostają niezależne."""
    d = max(0, min(10, int(d)))
    return 5 if d == 0 else d * 10


def _ceil_div(a, b):
    return -(-a // b)


def core_match(it, klucze):
    """Czy sygnał dotyczy NISZY — zawiera ≥1 słowo-klucz rdzenia (OR, substring po lowercase).
    - Recenzje apek (pole `match` = tytuł+opis apki): pełny substring, bez reguły pozycji (apka jest „o tym" całością).
    - Wpisy tekstowe (Wykop/YouTube/FB): rdzeń tylko w pierwszych CORE_POS_LIMIT znakach — temat wpisu,
      nie słowo zakopane w środku długiego eseju (D-2026-06-11-11)."""
    if not klucze:
        return True  # filtr wyłączony (brak --klucze) — zachowanie wsteczne
    if it.get("match"):
        t = it["match"].lower()
        return any(k in t for k in klucze)
    t = (it.get("text") or "").lower()[:CORE_POS_LIMIT]
    return any(k in t for k in klucze)


def filter_relevant(raw, klucze, limit=FINAL_LIMIT):
    """Zwraca (trafne[:limit], odrzucone_off_topic, surowych_łącznie).
    Przegląda CAŁY surowiec, by uczciwie policzyć odrzucone."""
    if not klucze:
        return raw[:limit], 0, len(raw)
    kept, rejected = [], 0
    for it in raw:
        if core_match(it, klucze):
            kept.append(it)
        else:
            rejected += 1
    return kept[:limit], rejected, len(raw)


# ---------- KANAŁY BÓLU ----------
# Każda funkcja zwraca SUROWE sygnały (raw) + err. Filtr trafności (zmiana 3)
# i obcięcie do FINAL_LIMIT aplikuje centralnie main(). Sygnatura: fn(q, queries, raw_limit).

WYKOP_BOT_MARKERS = ("mirko-anonim", "wsparcie-ai", "mirko.pro")


def _wykop_is_bot(txt):
    """Wpisy generowane przez bota AI Wykopu (✨️ wsparcie AI / mirko-anonim) — nie ludzie z bólami (D-11)."""
    t = (txt or "").strip().lower()
    return t.startswith("✨") or any(m in t for m in WYKOP_BOT_MARKERS)


def _load_sibling(fname, modname):
    """Ładuje sąsiedni moduł keyless (np. wykop_keyless.py / reddit_keyless.py) z tego samego bin/."""
    spec = importlib.util.spec_from_file_location(
        modname, str(Path(__file__).with_name(fname)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wykop_pains(nisza, queries, raw_limit=RAW_LIMIT):
    """KEYLESS-FIRST (wersja do rozdania): L1 = scraping strony tagu (BEZ klucza),
    L3 fallback = API v3 (klucz) gdy żaden tag nie ma wpisów (np. fraza bez tagu).
    Tag wyprowadzany z niszy i fraz. Bonus vs API: tor keyless niesie też głosy (score)."""
    wk = _load_sibling("wykop_keyless.py", "wykop_keyless")
    tags, out, seen = [], [], set()
    for q in ([nisza] + list(queries or [])):
        t = wk.nisza_to_tag(q)
        if t and t not in tags:
            tags.append(t)
    strony = max(1, _ceil_div(raw_limit, 14))  # ~14 wpisów/strona → głębokość steruje liczbą stron
    for t in tags:
        try:
            res, _log = wk.collect(t, strony=strony, limit=raw_limit)
        except Exception:
            res = []
        for s in res:
            wid = s.get("wid")
            if wid and wid not in seen and not _wykop_is_bot(s.get("text")):
                seen.add(wid)
                out.append({"text": s["text"], "src": f"Wykop #{t} (bez klucza)",
                            "autor": s.get("autor"), "score": s.get("score")})
        if len(out) >= raw_limit:
            break
    if out:
        return out[:raw_limit], None
    # L3 fallback: żaden tag nie dał wpisów → pełnotekstowe API po frazie (wymaga klucza)
    return _wykop_api(nisza, queries, raw_limit)


def _wykop_api(nisza, queries, raw_limit=RAW_LIMIT):
    """L3 FALLBACK: Wykop API v3 (klucz) — pełnotekstowe search/entries po FRAZACH.
    Używane tylko gdy tor keyless nie znalazł tagu z wpisami."""
    key, secret = cfg("WYKOP_KEY"), cfg("WYKOP_SECRET")
    if not (key and secret):
        return [], "tor keyless pusty, a brak kluczy wykop w Keychain (fallback niedostępny)"
    body = json.dumps({"data": {"key": key, "secret": secret}}).encode()
    req = urllib.request.Request("https://wykop.pl/api/v3/auth", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    token = json.loads(urllib.request.urlopen(req, timeout=20).read()).get("data", {}).get("token")
    if not token:
        return [], "auth nieudany"
    out, seen = [], set()
    for fraza in (queries or [nisza]):
        url = "https://wykop.pl/api/v3/search/entries?" + urllib.parse.urlencode({"query": fraza})
        r = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        try:
            data = json.loads(urllib.request.urlopen(r, timeout=20).read())
        except Exception:
            continue
        for it in data.get("data", []):
            txt = clean(it.get("content") or it.get("body"))
            iid = it.get("id")
            if txt and len(txt) > 25 and iid not in seen and not _wykop_is_bot(txt):
                seen.add(iid)
                autor = (it.get("author") or {}).get("username")
                out.append({"text": txt, "src": f"Wykop „{fraza}”", "autor": autor})
        if len(out) >= raw_limit:
            break
    return out[:raw_limit], None


def youtube_pains(nisza, queries, raw_limit=RAW_LIMIT):
    """KEYLESS-FIRST (wersja do rozdania): L1 = yt-dlp (search + komentarze + polubienia, BEZ klucza),
    L3 fallback = youtube-data-api (kwota 100 jedn./search) gdy yt-dlp zablokowany/pusty."""
    yk = _load_sibling("youtube_keyless.py", "youtube_keyless")
    qs = [q for q in (queries or [nisza]) if q][:max(2, raw_limit // 15)]
    n_videos = max(1, min(8, _ceil_div(raw_limit, 20)))  # ~20 komentarzy-bólów/wideo → głębokość steruje
    try:
        out, _log = yk.collect(qs, n_videos=n_videos, max_comments=20)
    except Exception:
        out = []
    if out:
        return out[:raw_limit], None
    # L3 fallback: yt-dlp pusty/zablokowany → API v3
    return _youtube_api(nisza, queries, raw_limit)


def _youtube_api(nisza, queries, raw_limit=RAW_LIMIT):
    """L3 FALLBACK: YouTube Data API v3 (klucz, kwota). Używane gdy yt-dlp zawiedzie."""
    key = cfg("YOUTUBE_DATA_API")
    if not key:
        return [], "tor keyless pusty, a brak youtube-data-api (fallback niedostępny)"
    def api(path, params):
        params["key"] = key
        return json.loads(urllib.request.urlopen(
            f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params), timeout=20).read())
    # szukaj wideo po każdej frazie; liczba wideo/frazę skaluje z N_YT_VIDEOS (było zaszyte 2)
    vids = []
    n_q = max(2, raw_limit // 15)  # przy głębszym przejeździe więcej fraz
    for query in (queries or [nisza])[:n_q]:
        try:
            d = api("search", {"part": "snippet", "q": query, "type": "video", "maxResults": N_YT_VIDEOS,
                               "regionCode": "PL", "relevanceLanguage": "pl"})
        except Exception:
            continue
        for it in d.get("items", []):
            vid = it.get("id", {}).get("videoId")
            if vid and vid not in vids:
                vids.append(vid)
    keys = ("jak ", "czy ", "problem", "nie wiem", "szukam", "poleci", "narzędz", "automat", "?")
    out = []
    for v in vids:
        try:
            c = api("commentThreads", {"part": "snippet", "videoId": v, "maxResults": 20,
                                       "order": "relevance", "textFormat": "plainText"})
        except Exception:
            continue
        for it in c.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            t = clean(sn["textDisplay"])
            if t and any(k in t.lower() for k in keys):
                out.append({"text": t, "src": "YouTube", "autor": sn.get("authorDisplayName")})
    return out[:raw_limit], None


def reddit_pains(nisza, queries, raw_limit=RAW_LIMIT, subreddits=None, z_komentarzami=None):
    """KEYLESS-FIRST (wersja do rozdania): L1 = publiczny RSS (reddit_keyless, BEZ aplikacji/klucza),
    L3 fallback = PRAW (reddit-search.py) gdy RSS pusty/zablokowany. RSS niesie posty I KOMENTARZE
    (post.rss), nie niesie tylko score. Komentarze = najbogatsze źródło bólów.
    z_komentarzami=None → auto: drążenie (raw_limit≥30) z komentarzami, tani zwiad (mała próbka) bez."""
    rk = _load_sibling("reddit_keyless.py", "reddit_keyless")
    qs = [q for q in (queries or [nisza]) if q][:8]
    if z_komentarzami is None:
        z_komentarzami = raw_limit >= 30
    try:
        out, _log = rk.collect(qs, subreddits=subreddits, limit=raw_limit,
                               z_komentarzami=z_komentarzami)
    except Exception:
        out = []
    if out:
        return out, None  # NIE tniemy do raw_limit — komentarze są dodatkiem; filtr i FINAL_LIMIT obetną dalej
    # L3 fallback: żaden feed nie dał wpisów (np. 403/429 na IP) → PRAW
    return _reddit_praw(nisza, queries, raw_limit, subreddits)


def _reddit_praw(nisza, queries, raw_limit=RAW_LIMIT, subreddits=None):
    """L3 FALLBACK: Reddit przez ~/.claude/scripts/reddit-search.py (PRAW, klucze aplikacji).
    Daje też score (RSS go nie ma). Do rozdania user musiałby podać własne klucze aplikacji Reddita."""
    import subprocess, os
    script = os.path.expanduser("~/.claude/scripts/reddit-search.py")
    if not os.path.exists(script):
        return [], "tor keyless pusty, a brak reddit-search.py (fallback niedostępny)"
    subs = subreddits or ["getdisciplined", "productivity", "selfimprovement", "DecidingToBeBetter", "ADHD"]
    qs = (queries or [nisza])[:8]
    cmd = [sys.executable, script, "--subreddits", ",".join(subs),
           "--queries"] + qs + ["--time", "year", "--limit", str(max(raw_limit, 30)), "--output", "json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        data = json.loads(res.stdout)
    except Exception as e:
        return [], f"reddit err: {e}"
    posts = data if isinstance(data, list) else data.get("posts", data.get("results", []))
    out, seen = [], set()
    for p in (posts or []):
        if not isinstance(p, dict):
            continue
        txt = clean((p.get("title", "") + ". " + (p.get("selftext") or p.get("text") or ""))[:1200])
        pid = p.get("post_id") or p.get("url") or txt[:60]
        if txt and len(txt) > 30 and pid not in seen:
            seen.add(pid)
            out.append({"text": txt, "src": f"Reddit r/{p.get('subreddit','?')}",
                        "autor": p.get("author"), "score": p.get("score")})
        if len(out) >= raw_limit:
            break
    return out[:raw_limit], None


def google_play_pains(nisza, queries, raw_limit=RAW_LIMIT, n_apps=N_APPS):
    try:
        from google_play_scraper import reviews, app, Sort
    except Exception:
        return [], "brak biblioteki google-play-scraper"
    n_apps = max(2, min(12, _ceil_div(raw_limit, 8)))  # głębokość steruje liczbą apek
    # KEYLESS-FIRST: recenzje i tak keyless (biblioteka); jedyny klucz był w DOBORZE apek.
    # L1 = scraping HTML wyszukiwarki Play (bez klucza); L3 fallback = SerpApi (search() biblioteki zepsuty).
    gk = _load_sibling("gplay_keyless.py", "gplay_keyless")
    ids, seen = [], set()
    for query in (queries or [nisza]):
        got, _e = gk.search_app_ids(query, n=n_apps)
        for pid in got:
            if pid not in seen:
                seen.add(pid); ids.append(pid)
        if len(ids) >= n_apps:
            break
    if not ids:  # L3 fallback: SerpApi gdy HTML nic nie zwrócił
        ids = _gplay_ids_serpapi(queries or [nisza], n_apps)
    if not ids:
        return [], "brak app_id (keyless HTML i SerpApi puste)"
    zrodlo = " (bez klucza)" if seen else " (fallback SerpApi)"
    out = []
    for a in ids[:n_apps]:
        try:
            meta = app(a, lang="pl", country="pl")
            rv, _ = reviews(a, lang="pl", country="pl", sort=Sort.MOST_RELEVANT, count=40)
        except Exception:
            continue
        # match trafności = tytuł + opis apki (a NIE treść recenzji)
        appmatch = clean((meta.get("title") or "") + " " + (meta.get("description") or ""))[:400]
        for r in rv:
            if (r.get("score") or 5) <= 3 and clean(r.get("content")):
                out.append({"text": clean(r["content"]), "src": f"Google Play: {meta.get('title','?')[:24]}{zrodlo}",
                            "score": r.get("score"), "match": appmatch})
        if len(out) >= raw_limit:
            break
    return out[:raw_limit], None


def _gplay_ids_serpapi(queries, n_apps):
    """L3 FALLBACK doboru apek Play: SerpApi engine=google_play (gdy scraping HTML zawiedzie)."""
    sk = cfg("SERPAPI") or cfg("SERPAPI_BACKUP")
    if not sk:
        return []
    ids, seen = [], set()
    for query in queries:
        try:
            u = "https://serpapi.com/search.json?" + urllib.parse.urlencode(
                {"engine": "google_play", "store": "apps", "q": query, "gl": "pl", "hl": "pl", "api_key": sk})
            d = json.loads(urllib.request.urlopen(u, timeout=25).read())
        except Exception:
            continue
        for sec in d.get("organic_results", []):
            if not isinstance(sec, dict):
                continue
            cands = sec.get("items") if isinstance(sec.get("items"), list) else [sec]
            for it in cands:
                pid = it.get("product_id") if isinstance(it, dict) else None
                if pid and pid not in seen:
                    seen.add(pid); ids.append(pid)
        if len(ids) >= n_apps:
            break
    return ids[:n_apps]


def appstore_pains(nisza, queries, raw_limit=RAW_LIMIT, n_apps=N_APPS):
    def j(url):
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore"))
    n_apps = max(2, min(12, _ceil_div(raw_limit, 8)))  # głębokość steruje liczbą apek
    # zbierz apki po każdej frazie (limit/frazę skaluje z n_apps)
    apps, seen = [], set()
    per_q = max(5, n_apps)
    for query in (queries or [nisza]):
        try:
            res = j("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": query, "country": "pl", "entity": "software", "limit": per_q})).get("results", [])
        except Exception:
            continue
        for r in res:
            if r.get("trackId") and r["trackId"] not in seen:
                seen.add(r["trackId"]); apps.append(r)
    if not apps:
        return [], "itunes err: brak apek"
    out = []
    for r in apps[:n_apps]:
        a, t = r.get("trackId"), r.get("trackName", "?")
        # match trafności = nazwa + opis apki (NIE treść recenzji)
        appmatch = clean((t or "") + " " + (r.get("description") or ""))[:400]
        # FIX 14.06: sortby=mostrecent zwraca dziś 0 wpisów; mosthelpful daje recenzje (oba keyless).
        entries = []
        for sortby in ("mosthelpful", "mostrecent"):
            try:
                feed = j(f"https://itunes.apple.com/pl/rss/customerreviews/id={a}/sortby={sortby}/json")
            except Exception:
                continue
            ent = feed.get("feed", {}).get("entry", [])
            if isinstance(ent, dict):
                ent = [ent]
            ent = [e for e in ent if "im:rating" in e]
            if ent:
                entries = ent
                break
        for e in entries:
            if int(e.get("im:rating", {}).get("label", "5")) <= 3:
                body = clean(e.get("content", {}).get("label", ""))
                if body:
                    out.append({"text": body, "src": f"App Store: {t[:24]} (bez klucza)",
                                "score": int(e['im:rating']['label']), "match": appmatch})
        if len(out) >= raw_limit:
            break
    return out[:raw_limit], None


def fb_pains(nisza, queries, raw_limit=RAW_LIMIT, n_groups=N_FB_GROUPS):
    """KEYLESS-FIRST OPT-IN (⚠ ryzyko banu konta usera): L1 = fb_keyless (auto-cookies z przeglądarki +
    seleniumbase UC, posty grup publicznych/widocznych przez story_message); L3 fallback = Apify (własny
    token usera). Domyślnie WŁĄCZONY; user wyłącza w onboardingu (--no-fb). ⚠ automat na FB = ryzyko banu konta."""
    if not FB_OPTIN:
        return [], "kanał FB wyłączony przez usera (--no-fb)"
    n_groups = max(1, min(6, _ceil_div(raw_limit, 15)))  # głębokość steruje liczbą grup
    fk = _load_sibling("fb_keyless.py", "fb_keyless")
    note = None
    try:
        groups = fk.discover_groups(nisza, n=n_groups)
        if groups:
            out, note = fk.run(groups, nisza, max_posts=max(10, raw_limit // max(1, len(groups))))
        else:
            out, note = [], "brak grup z DuckDuckGo"
    except Exception:
        out = []
    if out:
        return out[:raw_limit], None
    if note:  # np. „zaloguj się raz: --login" — pokaż userowi zamiast cichego fallbacku Apify
        return [], note
    return _fb_apify(nisza, queries, raw_limit, n_groups)  # L3: własny Apify usera


def _fb_apify(nisza, queries, raw_limit=RAW_LIMIT, n_groups=N_FB_GROUPS):
    """L3 FALLBACK: Tavily znajdź grupy → Apify scrape (WŁASNE klucze usera). Gdy keyless pusty."""
    apt = cfg("APIFY_TOKEN")
    tav = cfg("TAVILY_API_KEY")
    if not apt:
        return [], "brak apify-token"
    if not tav:
        return [], "brak TAVILY_API_KEY"
    # 1) znajdź grupy przez Tavily — BEZ zaszytych kategorii (kontekst z niszy, nie „przedsiębiorcy")
    try:
        body = json.dumps({"api_key": tav, "query": f"grupa Facebook {nisza}", "max_results": 12,
                           "include_domains": ["facebook.com"]}).encode()
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.tavily.com/search", data=body, headers={"Content-Type": "application/json"}), timeout=25).read())
    except Exception as e:
        return [], f"tavily err: {e}"
    groups = []
    for r in d.get("results", []):
        u = r.get("url", "")
        if "/groups/" in u:
            gid = u.split("/groups/")[1].split("/")[0].split("?")[0]
            gu = "https://www.facebook.com/groups/" + gid
            if gid and gu not in groups:
                groups.append(gu)
    if not groups:
        return [], "tavily nie znalazł grup FB"
    # 2) scrape KILKU grup, akumuluj do raw_limit
    use = groups[:n_groups]
    per_group = max(5, raw_limit // max(1, len(use)))
    out = []
    for gu in use:
        try:
            b = json.dumps({"startUrls": [{"url": gu}], "resultsLimit": per_group}).encode()
            data = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://api.apify.com/v2/acts/apify~facebook-groups-scraper/run-sync-get-dataset-items?token={apt}&timeout=180",
                data=b, headers={"Content-Type": "application/json"}), timeout=200).read())
        except Exception:
            continue
        for p in (data if isinstance(data, list) else []):
            t = clean(p.get("text"))
            if t and len(t) > 30:
                out.append({"text": t, "src": f"FB: {p.get('groupTitle','grupa')[:24]}"})
        if len(out) >= raw_limit:
            break
    return out[:raw_limit], None


# ---------- FAZA 0: ODKRYWANIE POD-NISZ ----------
def _fraza_of(x):
    """popyt_keyless oddaje stringi, badaj-popyt słowniki — ujednolicenie."""
    return x if isinstance(x, str) else (x.get("query") or x.get("value") or "")


def discover_subniches(obszar, bp, keys):
    """Z szerokiego obszaru → ranking kandydatów pod-nisz (autocomplete + Trends related).
    KEYLESS-FIRST (popyt_keyless); badaj-popyt tylko jako fallback gdy user ma klucz."""
    pk = _load_sibling("popyt_keyless.py", "popyt_keyless")
    cands, rising, top, auto = [], [], [], []
    try:
        _pts, rising, top, _e = pk.trends(obszar, "PL", "today 12-m")
    except Exception:
        rising, top = [], []
    try:
        auto, _ea = pk.autocomplete(obszar)
    except Exception:
        auto = []
    if bp and not rising and not top:  # fallback z kluczem (opcjonalny)
        try:
            rising, top = bp.fetch_trends_related(obszar, "PL", "today 12-m", keys)
        except Exception:
            pass
    if bp and not auto:
        try:
            auto = bp.fetch_autocomplete(obszar, keys)
        except Exception:
            auto = []
    for r in rising:
        cands.append({"fraza": _fraza_of(r), "src": "Trends rising",
                      "sygnal": (r.get("value") if isinstance(r, dict) else "rising"), "sort": 100000})
    for s in auto:
        val = s if isinstance(s, str) else s.get("value", "")
        rel = 0 if isinstance(s, str) else s.get("relevance", 0)
        cands.append({"fraza": val, "src": "autocomplete",
                      "sygnal": (f"relevance {rel}" if rel else "autocomplete"), "sort": rel or 50})
    for r in top:
        cands.append({"fraza": _fraza_of(r), "src": "Trends top",
                      "sygnal": (r.get("value") if isinstance(r, dict) else "top"), "sort": 1})
    seen, uniq = set(), []
    for c in sorted(cands, key=lambda x: -x["sort"]):
        k = c["fraza"].lower().strip()
        if k and k != obszar.lower().strip() and k not in seen:
            seen.add(k); uniq.append(c)
    return uniq


# ---------- RENDER ----------
def esc(s):
    return html.escape(str(s))


def pain_section(name, items, err, rejected=0, raw_count=0):
    if err:
        return f'<div class="ch"><h3>{esc(name)} <span class="warn">⚠ {esc(err)}</span></h3></div>'
    # nota o filtrze trafności (ile surowych, ile off-topic odrzucono)
    note = f' <span class="src">({len(items)} trafnych z {raw_count} surowych · odrzucono {rejected} off-topic)</span>' if raw_count else ""
    if not items:
        ubogi = f' — kanał ubogi (0 trafnych z {raw_count}, odrzucono {rejected})' if raw_count else ' — 0 sygnałów'
        return f'<div class="ch"><h3>{esc(name)} <span class="muted">{esc(ubogi)}</span></h3></div>'
    poor = ' <span class="warn">· ubogi (&lt;3)</span>' if len(items) < MIN_TRAFNE else ""
    rows = "".join(
        f'<li>{("<b>"+str(it["score"])+"★</b> ") if it.get("score") else ""}{esc(it["text"][:220])} '
        f'<span class="src">· {esc(it["src"])}</span></li>'
        for it in items[:8])
    return f'<div class="ch"><h3>{esc(name)} <span class="cnt">{len(items)}</span>{poor}{note}</h3><ul>{rows}</ul></div>'


def render(nisza, location, popyt, pains, verdict, n_calls, strategia=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tr = popyt["trend"]
    spark = popyt["spark"]
    rising = "".join(f'<tr><td>{esc(r["query"])}</td><td style="text-align:right">{esc(r["value"])}</td></tr>' for r in popyt["rising"]) or '<tr><td colspan=2 class="muted">brak</td></tr>'
    top = "".join(f'<tr><td>{esc(r["query"])}</td><td style="text-align:right">{esc(r["value"])}</td></tr>' for r in popyt["top"]) or '<tr><td colspan=2 class="muted">brak</td></tr>'
    sugg = "".join(f"<li>{esc(s['value'])}</li>" for s in popyt["suggestions"][:12]) or '<li class="muted">brak</li>'
    if popyt["has_maps"]:
        maps = "".join(f'<tr><td>{esc(p["title"])}</td><td style="text-align:right">{p["rating"]}★</td><td style="text-align:right">{p["reviews"]}</td></tr>' for p in popyt["maps"]) or '<tr><td colspan=3 class="muted">brak</td></tr>'
        maps_block = f'<table><thead><tr><th>Firma</th><th>Ocena</th><th>Opinie</th></tr></thead><tbody>{maps}</tbody></table>'
    else:
        maps_block = '<p class="muted">Maps pominięty (nisza bez lokalizacji).</p>'
    pains_html = "".join(pain_section(n, it, er, rej, raw) for n, it, er, rej, raw in pains)
    total_pains = sum(len(it) for _, it, er, _, _ in pains if not er)
    n_active = sum(1 for _, it, er, _, _ in pains if not er and len(it) >= MIN_TRAFNE)
    total_rejected = sum(rej for _, _, er, rej, _ in pains if not er)
    reasons = "".join(f"<li>{esc(r)}</li>" for r in verdict["reasons"])

    if strategia and strategia.get("klucze"):
        strat_html = (
            '<section style="background:#eef2ff;border-radius:8px;padding:10px 16px;margin:14px 0;font-size:13px">'
            '<b>🎯 Strategia zbierania (definiuje model, nie skrypt):</b><br>'
            f'Słowa-klucze rdzenia: <code>{esc(", ".join(strategia["klucze"]))}</code><br>'
            f'Frazy wyszukiwania: {esc(" · ".join(strategia.get("frazy") or [nisza]))}<br>'
            f'<span class="muted">Filtr trafności: każdy sygnał musi zawierać ≥1 rdzeń, inaczej odrzucony. '
            f'Łącznie odrzucono <b>{total_rejected}</b> off-topic.</span></section>')
    else:
        strat_html = ('<section style="background:#fff7ed;border-radius:8px;padding:10px 16px;margin:14px 0;font-size:13px">'
                      '<span class="warn">⚠ Filtr trafności WYŁĄCZONY (brak --klucze) — surowiec może zawierać szum off-topic.</span></section>')

    return f"""<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><title>Dossier: {esc(nisza)}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:920px;margin:24px auto;padding:0 18px;color:#1f2937;line-height:1.5}}
 h1{{font-size:25px;margin:0 0 4px}} h2{{font-size:18px;margin:30px 0 8px;border-bottom:2px solid #eef2ff;padding-bottom:4px}}
 h3{{font-size:15px;margin:14px 0 4px}}
 .meta{{color:#6b7280;font-size:13px;margin-bottom:16px}}
 .verdict{{border-left:6px solid {verdict["color"]};background:#f9fafb;padding:14px 18px;border-radius:8px;margin:14px 0}}
 .verdict .label{{font-size:19px;font-weight:700;color:{verdict["color"]}}}
 table{{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}} th,td{{border-bottom:1px solid #eee;padding:5px 9px;text-align:left}}
 th{{background:#f8fafc;font-size:11px;text-transform:uppercase;color:#64748b}}
 ul{{margin:4px 0;padding-left:18px}} li{{margin:3px 0}}
 .cols{{display:flex;gap:24px;flex-wrap:wrap}} .cols>div{{flex:1;min-width:240px}}
 .ch{{margin:10px 0;padding:10px 14px;background:#fafafa;border-radius:8px}}
 .cnt{{background:#dc2626;color:#fff;border-radius:999px;padding:1px 9px;font-size:12px}}
 .src{{color:#9ca3af;font-size:11px}} .muted{{color:#9ca3af}} .warn{{color:#b45309;font-size:12px}}
 .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
 footer{{margin-top:30px;color:#9ca3af;font-size:12px;border-top:1px solid #eee;padding-top:10px}}
</style></head><body>
<h1>🧭 Dossier niszy: „{esc(nisza)}”</h1>
<div class="meta">PL{(' · Maps: '+esc(location)) if popyt["has_maps"] else ''} · {now} · 8 kanałów (popyt + bóle)</div>
{strat_html}
<section style="border:2px solid #4f46e5;border-radius:10px;padding:16px 20px;margin:16px 0;background:#f5f3ff">
<h2 style="border:none;color:#4f46e5;margin-top:0">🧠 CZEGO SIĘ DOWIADUJESZ</h2>
<!--ANALIZA-->
<p class="muted"><i>Tę sekcję wypełnia model prowadzący sesję (analiza surowca z kanałów poniżej) — nie skrypt.</i></p>
</section>
<div class="verdict"><div class="label" style="font-size:14px">Wstępny sygnał liczbowy (regułowy, pomocniczy): {esc(verdict["label"])}</div><ul>{reasons}</ul></div>

<h2>📈 POPYT</h2>
<p>Trend 12 mies.: <b>{esc(tr["dir"])} ({tr["pct"]:+d}% r/r)</b> {tr["emoji"]} · aktualnie {tr["current"]}/100</p>
{spark}
<div class="cols">
 <div><h3>🚀 Wschodzące</h3><table><tbody>{rising}</tbody></table></div>
 <div><h3>⭐ Utrwalone</h3><table><tbody>{top}</tbody></table></div>
</div>
<h3>Intencje (autocomplete)</h3><ul>{sugg}</ul>
<h3>Nasycenie rynku (Maps)</h3>{maps_block}

<h2>😣 BÓLE — {total_pains} trafnych sygnałów z {n_active} kanałów (≥{MIN_TRAFNE} trafnych) · odrzucono {total_rejected} off-topic</h2>
<div class="grid2">{pains_html}</div>

<footer>Skill <b>dossier-niszy</b> · ~{n_calls} zapytań (SerpApi + Wykop + YouTube + Apify) · werdykt regułowy</footer>
</body></html>"""


def build_verdict(tr, popyt, total_pains, n_pain_channels):
    # ⚠ POMOCNICZY (D-2026-06-13). Liczony na surowcu PO substring (z homonimami — np. „celi"=cela vs cel),
    # więc total_pains bywa ZAWYŻONY. To NIE jest werdykt niszy. Werdykt niszy robi MODEL w fazie 4 na
    # CZYSTYCH sygnałach (po sędzim trafności), progi profilu A: silny ≥20 / umiark ≥10 / słaby <10.
    # Rezonans (score/lajki) ≠ częstotliwość — modyfikator pewności, nie liczy się jako sygnał.
    score, reasons = 0, []
    if tr["dir"] == "rośnie":
        score += 2; reasons.append(f"popyt rośnie ({tr['pct']:+d}% r/r)")
    elif tr["dir"] == "stabilny":
        score += 1; reasons.append("popyt stabilny (utrwalony)")
    elif tr["dir"] == "spada":
        score -= 1; reasons.append(f"popyt spada ({tr['pct']:+d}% r/r)")
    strong = [r for r in popyt["rising"] if (r.get("ev", 0) if isinstance(r, dict) else 0) >= 100]
    if strong:
        score += 2; reasons.append(f"{len(strong)} wschodzących zapytań (świeży popyt)")
    if total_pains >= 30:
        score += 2; reasons.append(f"dużo surowych sygnałów — {total_pains} z {n_pain_channels} kanałów ⚠ z homonimami, oczyść w fazie 2")
    elif total_pains >= 10:
        score += 1; reasons.append(f"umiarkowanie surowych sygnałów — {total_pains} ⚠ przed oczyszczeniem modelem")
    else:
        reasons.append(f"mało surowych sygnałów — {total_pains} (sprawdź dobór niszy/fraz)")
    if score >= 5:
        return {"label": "🟢 NISZA WARTA UWAGI — popyt rośnie + realny ból", "color": "#16a34a", "reasons": reasons}
    if score >= 3:
        return {"label": "🟡 NISZA OBIECUJĄCA — sygnał jest, dopracuj kąt", "color": "#ca8a04", "reasons": reasons}
    if score >= 1:
        return {"label": "⚪ NISZA SŁABA — sygnał niejednoznaczny", "color": "#6b7280", "reasons": reasons}
    return {"label": "🔴 NISZA RYZYKOWNA — popyt nie rośnie, mało bólu", "color": "#dc2626", "reasons": reasons}


# Rejestr kanałów bólu — jedno źródło prawdy (main + zwiad + tryb --kanal dla agentów v5).
# Sygnatura każdej fn: fn(nisza, queries, raw_limit). Reddit dodany jako natywny kanał (D-2026-06-13-02).
GMAPS_LOCATION = None  # miasto dla recenzji wizytówek Google (z --location/config LOCATION); kanał lokalny
FB_OPTIN = True        # kanał Facebook (auto-cookies + UC) — DOMYŚLNIE WŁĄCZONY; config FB_ENABLED / --no-fb. ⚠ ryzyko banu konta usera
MAPS_OPTIN = True      # kanał Google Maps best-effort ON gdy jest przeglądarka; config MAPS_ENABLED / --no-maps (D-2026-06-14-03)


def _browser_ready():
    """Czy jest seleniumbase + Chrome (kanał headless 'Google Maps' opcjonalny, tryb undetected)."""
    import importlib.util, shutil
    if importlib.util.find_spec("seleniumbase") is None:
        return False, "brak seleniumbase (pip install seleniumbase)"
    if not (Path("/Applications/Google Chrome.app").exists()
            or shutil.which("google-chrome") or shutil.which("chromium")):
        return False, "brak Chrome/Chromium"
    return True, None


def gmaps_pains(nisza, queries, raw_limit=RAW_LIMIT, n_apps=N_APPS):
    """KANAŁ OPCJONALNY (headless, BEZ klucza): recenzje wizytówek Google ≤3★ = skargi/bóle klientów
    firm lokalnych. Wymaga przeglądarki (Playwright) → guard; bez niej kanał po cichu pominięty.
    'Jak najwięcej': wolumen z wielu firm (maxFirm skaluje z raw_limit; per firma Maps ładuje ~8-20
    najniższych). Lokalny — wymaga miasta (GMAPS_LOCATION z --location/config). Tylko ≤3★ (filtr w .cjs)."""
    if not MAPS_OPTIN:
        return [], "kanał Google Maps wyłączony (config MAPS_ENABLED=false / --no-maps)"
    if not GMAPS_LOCATION:
        return [], "kanał lokalny — podaj --location (miasto) lub LOCATION w configu, inaczej pomijany"
    ok, err = _browser_ready()
    if not ok:
        return [], f"kanał opcjonalny (recenzje Google) — {err}; reszta skilla działa bez tego"
    import subprocess
    term = (queries[0] if queries else nisza)
    maxfirm = max(2, min(15, _ceil_div(raw_limit, 10)))  # ~10 recenzji/firma (sufit środ.) → głębokość = liczba firm
    py = str(Path(__file__).with_name("maps_keyless.py"))
    try:
        r = subprocess.run([sys.executable, py, "--nisza", term, "--location", GMAPS_LOCATION,
                            "--max-firm", str(maxfirm), "--max-rec", "200"],
                           capture_output=True, text=True, timeout=1200, cwd=str(Path(__file__).parent))
        data = json.loads(r.stdout)
    except Exception as e:
        return [], f"recenzje Google błąd: {e}"
    return data.get("sygnaly", []), None


CHANNELS = {
    "Wykop": wykop_pains,
    "Reddit": reddit_pains,
    "YouTube": youtube_pains,
    "Google Play": google_play_pains,
    "App Store": appstore_pains,
    "Google Maps": gmaps_pains,
    "Facebook": fb_pains,
}

# Kanał → klucz ikony w resources/icons.json (dla raportu; dodajesz kanał = dodaj ikonę)
CHANNEL_ICONS = {
    "Wykop": "wykop", "Reddit": "reddit", "YouTube": "youtube",
    "Google Play": "google_play", "App Store": "app_store",
    "Google Maps": "google_maps", "Facebook": "facebook", "Web/SERP": "web",
}


def collect_one(name, q, queries, raw_limit, klucze, final_limit):
    """Zbiera JEDEN kanał → (kept, rejected, raw_count, err). Używane przez --kanal (agenci v5)."""
    fn = CHANNELS.get(name)
    if not fn:
        return [], 0, 0, f"nieznany kanał: {name} (dostępne: {', '.join(CHANNELS)})"
    try:
        raw, err = fn(q, queries, raw_limit)
    except Exception as e:
        return [], 0, 0, f"błąd: {e}"
    if err:
        return [], 0, 0, err
    kept, rejected, raw_count = filter_relevant(raw, klucze, final_limit)
    return kept, rejected, raw_count, None


def main():
    ap = argparse.ArgumentParser(description="dossier-niszy — pełny raport popyt+bóle dla niszy (8 kanałów)")
    ap.add_argument("--nisza", "-q")
    ap.add_argument("--odkryj", help="szeroki OBSZAR → faza 0: odkryj kandydatów pod-nisz (nie zbiera danych)")
    ap.add_argument("--location", help="miasto PL dla Maps (warszawa…)")
    ap.add_argument("--no-fb", action="store_true", help="WYŁĄCZ kanał Facebook (domyślnie WŁĄCZONY; auto-cookies+UC). ⚠ automat na koncie FB grozi banem — user decyduje w onboardingu")
    ap.add_argument("--no-maps", action="store_true", help="WYŁĄCZ kanał Google Maps (domyślnie WŁĄCZONY best-effort gdy jest przeglądarka)")
    ap.add_argument("--klucze", help="słowa-klucze rdzenia niszy (CSV), np. 'nauczyciel,lekcj,uczeń,szkoł,klas,edukacj'. Filtr trafności — sygnał bez żadnego rdzenia = odrzucony.")
    ap.add_argument("--frazy", help="frazy wyszukiwania rozdzielone ';', np. 'ai dla nauczycieli;chatgpt w szkole;generator sprawdzianów'. Bóle ciągane po tych frazach (zamiast samej niszy).")
    ap.add_argument("--out-file")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--glebokosc", type=int, default=GLEBOKOSC_DOMYSLNA,
                    help="GŁĘBOKOŚĆ searchy 0-10 (0/1=płytko, 10=~100 sygnałów/kanał). Steruje całością; "
                         "kanały dziedziczą sub-limity. Domyślnie 3.")
    ap.add_argument("--gleboki", action="store_true", help="alias: głębokość 8 (wsteczna zgodność)")
    ap.add_argument("--surowiec-json", help="ORKIESTRATOR (Faza B): zbierz WSZYSTKIE kanały+popyt → JSON surowca dla sędziego/raportu (zamiast starego HTML).")
    ap.add_argument("--kanal", help="zbierz TYLKO jeden kanał (Wykop|Reddit|YouTube|Google Play|App Store|Facebook) → JSON. Dla agentów v5.")
    ap.add_argument("--limit", type=int, help="limit surowych dla --kanal (ile drążyć — ustala user/orkiestrator).")
    args = ap.parse_args()
    M = sys.modules[__name__]
    # Ustawienia: config usera (Faza D) jako baza, CLI nadpisuje. FB/Maps domyślnie ON.
    loc = args.location or cfg("LOCATION")
    if loc:  # miasto dla kanału recenzji Google (czytane przez gmaps_pains)
        M.GMAPS_LOCATION = loc.strip()
    M.FB_OPTIN = False if getattr(args, "no_fb", False) else CFG.get_bool("FB_ENABLED", True)
    M.MAPS_OPTIN = False if getattr(args, "no_maps", False) else CFG.get_bool("MAPS_ENABLED", True)
    gleb = 8 if args.gleboki else max(0, min(10, args.glebokosc))  # skala głębokości 0-10

    # TRYB --kanal: pojedynczy kanał → JSON surowiec (wejście dla agenta v5; limit ustala orkiestrator)
    if args.kanal:
        if not args.nisza:
            sys.exit("--kanal wymaga --nisza")
        q = args.nisza.strip()
        klucze = [k.strip().lower() for k in (args.klucze or "").split(",") if k.strip()]
        frazy = [f.strip() for f in (args.frazy or "").split(";") if f.strip()]
        queries = frazy if frazy else [q]
        lim = args.limit or depth_to_limits(gleb)  # głębokość 0-10 → raw_limit (override --limit)
        kept, rejected, raw_count, err = collect_one(args.kanal, q, queries, lim, klucze, lim)
        res = {"kanal": args.kanal, "nisza": q, "limit": lim, "err": err,
               "surowe": raw_count, "trafne_substring": len(kept), "odrzucone": rejected,
               "sygnaly": kept}
        txt = json.dumps(res, ensure_ascii=False, indent=2)
        if args.out_file:
            Path(args.out_file).write_text(txt, encoding="utf-8")
            print(f"{args.kanal}: {len(kept)} trafnych / {raw_count} surowych → {args.out_file}", file=sys.stderr)
        else:
            print(txt)
        return

    keys = CFG.serpapi_keys()  # KEYLESS: pusta lista gdy brak klucza (NIE sys.exit jak bp.get_api_keys)
    bp = badaj_if_keys(keys)   # OPCJONALNY fallback z kluczem; None = tor w pełni keyless (bez badaj-popyt)

    # FAZA 0 — odkrywanie pod-nisz z szerokiego obszaru
    if args.odkryj:
        cands = discover_subniches(args.odkryj.strip(), bp, keys)
        print(f"=== FAZA 0 — kandydaci pod-nisz dla obszaru: {args.odkryj} ===")
        for i, c in enumerate(cands[:25], 1):
            print(f"{i:2}. {c['fraza']}   [{c['src']}: {c['sygnal']}]")
        slug0 = "".join(ch if ch.isalnum() else "-" for ch in args.odkryj.lower()).strip("-")[:40]
        p0 = tmpdir() / f"odkryj-{slug0}.md"
        p0.write_text("# Kandydaci pod-nisz: " + args.odkryj + "\n\n" +
                      "\n".join(f"- {c['fraza']}  [{c['src']}: {c['sygnal']}]" for c in cands), encoding="utf-8")
        print(f"\nLista zapisana: {p0}")
        print("➡ NASTĘPNY KROK (model prowadzący): wybierz 2-3 pod-nisze i odpal --nisza dla każdej.")
        return

    if not args.nisza:
        sys.exit("Podaj --nisza '<fraza>' (zbieranie) albo --odkryj '<obszar>' (faza 0 odkrywania).")
    q = args.nisza.strip()
    # STRATEGIA ZBIERANIA (definiuje model przed runem) — zmiana 1
    klucze = [k.strip().lower() for k in (args.klucze or "").split(",") if k.strip()]
    frazy = [f.strip() for f in (args.frazy or "").split(";") if f.strip()]
    queries = frazy if frazy else [q]
    strategia = {"klucze": klucze, "frazy": frazy}
    # Głębokość 0-10 (D-2026-06-14-06) → raw_limit (cel sygnałów/kanał); final = trafne po filtrze
    raw_limit = depth_to_limits(gleb)
    final_limit = max(12, raw_limit * 4 // 10)
    print(f"🔬 Głębokość {gleb}/10 → próbka ~{final_limit} trafnych / {raw_limit} surowych na kanał", file=sys.stderr)
    if not klucze:
        print("⚠ Brak --klucze → filtr trafności WYŁĄCZONY (surowiec może mieć szum). "
              "Podaj rdzenie niszy, np. --klucze 'nauczyciel,lekcj,szkoł'.", file=sys.stderr)
    n_calls = 0

    # POPYT — KEYLESS-FIRST (autocomplete + Trends bez klucza); fallback SerpApi tylko gdy user ma klucz
    print("⏳ POPYT: Autocomplete + Trends (keyless)…", file=sys.stderr)
    pk = _load_sibling("popyt_keyless.py", "popyt_keyless")
    suggestions, _e = pk.autocomplete(q); n_calls += 1
    if not suggestions and bp:  # fallback SerpApi tylko gdy user ma własny klucz
        suggestions = bp.fetch_autocomplete(q, keys)
    points, rising, top, _terr = pk.trends(q, "PL", "today 12-m"); n_calls += 1
    if not points and bp:
        points = bp.fetch_trends_timeseries(q, "PL", "today 12-m", keys)
        rising, top = bp.fetch_trends_related(q, "PL", "today 12-m", keys)
    # popyt_keyless oddaje listy STRINGÓW, badaj-popyt listy SŁOWNIKÓW — ujednolicamy do słowników,
    # by werdykt/raport/surowiec działały spójnie niezależnie od źródła (D-2026-06-14-14).
    suggestions = [s if isinstance(s, dict) else {"value": s, "relevance": 0} for s in suggestions]
    rising = [r if isinstance(r, dict) else {"query": r, "value": "", "ev": 0} for r in rising]
    top = [r if isinstance(r, dict) else {"query": r, "value": "", "ev": 0} for r in top]
    ll, has_maps, maps = None, False, []
    if args.location:
        loc = args.location.strip().lower()
        if loc in CITY_LL:
            ll, has_maps = CITY_LL[loc], True
        elif args.location.startswith("@"):
            ll, has_maps = args.location, True
    if has_maps and bp:  # nasycenie Maps = key-only; bez klucza pomijamy (keyless)
        maps = bp.fetch_maps(q, ll, keys, 20); n_calls += 1
    tr = analyze_trend(points)
    popyt = {"trend": tr, "rising": rising, "top": top, "suggestions": suggestions,
             "maps": maps, "has_maps": has_maps, "spark": sparkline(points)}

    # BÓLE — kanały z rejestru CHANNELS (w tym Reddit), izolowane. Każdy ciągnie SUROWIEC, potem filtr trafności.
    pains = []
    for name in CHANNELS:
        print(f"⏳ BÓL: {name}…", file=sys.stderr)
        try:
            raw, err = CHANNELS[name](q, queries, raw_limit)
        except Exception as e:
            raw, err = [], f"błąd: {e}"
        if err:
            pains.append((name, [], err, 0, 0))
        else:
            kept, rejected, raw_count = filter_relevant(raw, klucze, final_limit)
            status = "ubogi" if len(kept) < MIN_TRAFNE else "ok"
            print(f"   {name}: {len(kept)} trafnych / {raw_count} surowych (odrzucono {rejected})"
                  + (f"  ⚠ {status}" if status == "ubogi" else ""), file=sys.stderr)
            pains.append((name, kept, None, rejected, raw_count))
        n_calls += 1

    total_pains = sum(len(it) for _, it, er, _, _ in pains if not er)
    n_pain_ch = sum(1 for _, it, er, _, _ in pains if not er and len(it) >= MIN_TRAFNE)
    verdict = build_verdict(tr, popyt, total_pains, n_pain_ch)

    # ORKIESTRATOR Faza B: zrzut surowca (sygnały + źródła + popyt) dla sędziego → render_raport.py
    if args.surowiec_json:
        sources_out, signals_out = [], {}
        for name, kept, err, rejected, raw_count in pains:
            sources_out.append({"name": name, "icon": CHANNEL_ICONS.get(name, "web"),
                                "people": len(kept), "skip": bool(err) or len(kept) == 0,
                                "uwaga": err})
            signals_out[name] = [{"text": s.get("text"), "src": s.get("src"),
                                  "autor": s.get("autor"), "score": s.get("score")} for s in kept]
        surowiec = {
            "meta": {"niche": q, "date": datetime.now().strftime("%d.%m.%Y"), "glebokosc": gleb,
                     "channels": str(sum(1 for s in sources_out if not s["skip"]))},
            "popyt": {"trend_dir": tr["dir"], "trend_pct": tr["pct"],
                      "autocomplete_n": len(suggestions),
                      "autocomplete": [s.get("value", "") for s in suggestions][:15],
                      "rising": [r.get("query", "") for r in rising][:8], "has_maps": has_maps},
            "verdict_regulowy": verdict, "total_pains": total_pains, "n_pain_channels": n_pain_ch,
            "sources": sources_out, "signals": signals_out,
            "_jak_dalej": "Sędzia (model/agent) czyta signals → klastry + werdykt TAK/TROCHĘ/NIE + score + pomysły → agregat dla render_raport.py --data",
        }
        Path(args.surowiec_json).write_text(json.dumps(surowiec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Surowiec: {total_pains} sygnałów z {n_pain_ch} kanałów → {args.surowiec_json}", file=sys.stderr)
        print(args.surowiec_json)
        return

    out = render(q, args.location or "", popyt, pains, verdict, n_calls, strategia)
    slug = "".join(c if c.isalnum() else "-" for c in q.lower()).strip("-")[:50]
    path = Path(args.out_file) if args.out_file else tmpdir() / f"dossier-{slug}.html"
    path.write_text(out, encoding="utf-8")

    # SUROWIEC dla modelu prowadzącego — to ON analizuje, nie skrypt
    total_rejected = sum(rej for _, _, er, rej, _ in pains if not er)
    md = [f"# SUROWIEC dossier: {q}", "",
          "## STRATEGIA ZBIERANIA (zdefiniowana przed runem)",
          "Słowa-klucze rdzenia: " + (", ".join(klucze) if klucze else "BRAK — filtr trafności WYŁĄCZONY (możliwy szum)"),
          "Frazy wyszukiwania: " + (" · ".join(frazy) if frazy else f"(brak — użyto samej niszy „{q}”)"),
          f"Filtr trafności: sygnał musi zawierać ≥1 rdzeń (recenzje apek filtrowane po tytule+opisie apki). Łącznie odrzucono {total_rejected} off-topic.",
          "", "## POPYT",
          f"Trend 12 mies.: {tr['dir']} ({tr['pct']:+d}% r/r), aktualnie {tr['current']}/100",
          "Wschodzące zapytania: " + ("; ".join(f"{r['query']} ({r['value']})" for r in rising) or "brak"),
          "Utrwalone zapytania: " + ("; ".join(f"{r['query']} ({r['value']})" for r in top) or "brak"),
          "Autocomplete: " + ("; ".join(s['value'] for s in suggestions) or "brak"),
          "", "## BÓLE (tylko TRAFNE cytaty per kanał — po filtrze)"]
    for name, it, er, rej, raw_count in pains:
        if er:
            md.append(f"\n### {name} — BŁĄD: {er}")
        else:
            poor = "  ⚠ KANAŁ UBOGI" if len(it) < MIN_TRAFNE else ""
            md.append(f"\n### {name} ({len(it)} trafnych z {raw_count} surowych · odrzucono {rej} off-topic){poor}")
        for x in it:
            sc = f"{x['score']}★ " if x.get('score') else ""
            md.append(f"- {sc}{x['text']}  [{x['src']}]")
    raw_path = path.with_name(path.stem + "-surowiec.md")
    raw_path.write_text("\n".join(md), encoding="utf-8")

    print(f"\n=== DOSSIER: {q} ===")
    print(f"Werdykt: {verdict['label']}")
    print(f"Strategia: klucze={klucze or 'BRAK (filtr off)'} | frazy={frazy or [q]}")
    print(f"POPYT: trend {tr['dir']} ({tr['pct']:+d}%), wschodzące {len(rising)}, autocomplete {len(suggestions)}")
    for name, it, er, rej, raw_count in pains:
        if er:
            print(f"BÓL {name}: ⚠ {er}")
        else:
            poor = "  ⚠ ubogi" if len(it) < MIN_TRAFNE else ""
            print(f"BÓL {name}: {len(it)} trafnych / {raw_count} surowych (odrzucono {rej}){poor}")
    print(f"Odrzucono łącznie off-topic: {total_rejected}")
    print(f"Raport HTML (placeholder analizy): {path}")
    print(f"SUROWIEC do analizy przez model: {raw_path}")
    print("➡ NASTĘPNY KROK (robi model prowadzący sesję): przeczytaj surowiec, zanalizuj,")
    print("   wstaw wnioski w miejsce znacznika <!--ANALIZA--> w pliku HTML (Edit), potem otwórz.")
    if args.open:
        open_file(path)


if __name__ == "__main__":
    main()
