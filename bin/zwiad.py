#!/usr/bin/env python3
"""
zwiad.py — ETAP 1 dossier-niszy v5: tani sondaż kanałów → MAPA SYGNAŁU.

Cel: zanim odpalimy głębokie drążenie (drogie, równolegli agenci), sprawdź TANIO
która pod-nisza/kanał ma w ogóle sygnał. Mała próbka (~10/kanał), filtr substring
(grube sito), zgrubna ocena siły. To NIE werdykt — to mapa do decyzji usera:
gdzie drążyć i ile (limity ustala user, feedback_skill_limits_interactive_not_hardcoded).

FB świadomie POMINIĘTY w zwiadzie (Apify płatny — D-2026-06-13, zgoda Łukasza);
dostępny w etapie drążenia.

Użycie:
  zwiad.py --nisza "<pod-nisza>" --klucze "rdzeń1,rdzeń2" --frazy "fraza1;fraza2" [--probka 10]
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, json, sys, tempfile, importlib.util
from pathlib import Path

DN_PATH = Path(__file__).with_name("dossier-niszy.py")


def load_dn():
    spec = importlib.util.spec_from_file_location("dossier_niszy", DN_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sila(trafne, probka):
    """Zgrubna siła kanału na próbce (substring, grube sito — model weryfikuje w drążeniu)."""
    if trafne == 0:
        return "⚪ pusto"
    if trafne <= 2:
        return "🟤 słaby"
    if trafne <= probka // 2:
        return "🟡 średni"
    return "🟢 silny"


def main():
    ap = argparse.ArgumentParser(description="zwiad — tani sondaż kanałów (ETAP 1 v5)")
    ap.add_argument("--nisza", "-q", required=True)
    ap.add_argument("--klucze", help="rdzenie niszy (CSV) — filtr trafności substring")
    ap.add_argument("--frazy", help="frazy wyszukiwania rozdzielone ';'")
    ap.add_argument("--probka", type=int, default=10, help="próbka sondy na kanał (domyślnie 10)")
    ap.add_argument("--out-file")
    args = ap.parse_args()

    dn = load_dn()
    q = args.nisza.strip()
    klucze = [k.strip().lower() for k in (args.klucze or "").split(",") if k.strip()]
    frazy = [f.strip() for f in (args.frazy or "").split(";") if f.strip()]
    queries = frazy if frazy else [q]
    P = args.probka

    # --- POPYT (KEYLESS-FIRST: autocomplete ✅ bez klucza; Trends wymaga klucza usera) ---
    keys = dn.CFG.serpapi_keys()   # KEYLESS: [] gdy brak klucza (NIE sys.exit jak bp.get_api_keys)
    bp = dn.badaj_if_keys(keys)    # OPCJONALNY fallback z kluczem; None = tor w pełni keyless (bez badaj-popyt)
    pk = dn._load_sibling("popyt_keyless.py", "popyt_keyless")
    print("⏳ zwiad POPYT…", file=sys.stderr)
    # autocomplete: keyless najpierw (suggestqueries), fallback SerpApi tylko gdy keyless pusty i jest klucz
    sugg, _e = pk.autocomplete(q)
    if not sugg and bp:
        sugg = bp.fetch_autocomplete(q, keys)
    # Trends KEYLESS-FIRST (lokalnie, bez klucza; potwierdzone 14.06). Fallback SerpApi tylko
    # gdy keyless padł (np. IP zablokowany) I user ma WŁASNY klucz. Bez klucza i tak działa autocomplete.
    points, rising, _top, _terr = pk.trends(q, "PL", "today 12-m")
    if not points and bp:
        points = bp.fetch_trends_timeseries(q, "PL", "today 12-m", keys)
        rising, _t2 = bp.fetch_trends_related(q, "PL", "today 12-m", keys)
    tr = dn.analyze_trend(points)
    # bez klucza popyt opiera się na autocomplete (intencja) — len(sugg)>=3 wystarcza na „jest popyt"
    popyt_sila = "🟢 jest" if (tr["dir"] in ("rośnie", "stabilny") or len(sugg) >= 3) else "⚪ słaby/brak"

    # --- KANAŁY BÓLÓW (darmowe; FB pominięty) ---
    kanaly = [
        ("Wykop", lambda: dn.wykop_pains(q, queries, P)),
        ("Reddit", lambda: dn.reddit_pains(q, queries, P)),
        ("YouTube", lambda: dn.youtube_pains(q, queries, P)),
        ("Google Play", lambda: dn.google_play_pains(q, queries, P, n_apps=3)),
        ("App Store", lambda: dn.appstore_pains(q, queries, P, n_apps=3)),
    ]
    wyniki = {}
    for name, fn in kanaly:
        print(f"⏳ zwiad {name}…", file=sys.stderr)
        try:
            raw, err = fn()
        except Exception as e:
            raw, err = [], f"błąd: {e}"
        if err:
            wyniki[name] = {"trafne": 0, "surowe": 0, "sila": "⚠ błąd", "uwaga": err}
            continue
        kept, _rej, rawc = dn.filter_relevant(raw, klucze, P)
        wyniki[name] = {"trafne": len(kept), "surowe": rawc, "sila": sila(len(kept), P)}

    # FB — niesondowany świadomie
    wyniki["Facebook"] = {"trafne": None, "surowe": None, "sila": "⏭ niesondowany",
                          "uwaga": "Apify płatny — dostępny w drążeniu (etap 2)"}

    mapa = {
        "nisza": q, "probka": P,
        "strategia": {"klucze": klucze, "frazy": frazy},
        "popyt": {"trend": tr["dir"], "pct": tr["pct"], "autocomplete": len(sugg),
                  "wschodzace": len(rising), "sila": popyt_sila},
        "kanaly": wyniki,
    }

    slug = "".join(c if c.isalnum() else "-" for c in q.lower()).strip("-")[:50]
    out = Path(args.out_file) if args.out_file else Path(tempfile.gettempdir()) / f"zwiad-{slug}.json"
    out.write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- MAPA SYGNAŁU (dla usera) ---
    print(f'\n=== MAPA SYGNAŁU — „{q}" (próbka {P}/kanał) ===')
    print(f"POPYT: {popyt_sila}  (trend {tr['dir']} {tr['pct']:+d}% · autocomplete {len(sugg)} · wschodzące {len(rising)})")
    print("BÓLE (trafne/surowe po substring — grube sito):")
    for name in ["Wykop", "Reddit", "YouTube", "Google Play", "App Store", "Facebook"]:
        w = wyniki[name]
        if w["trafne"] is None:
            print(f"  {name:12} {w['sila']:16} {w.get('uwaga','')}")
        else:
            uwaga = f"  ⚠ {w['uwaga']}" if w.get("uwaga") else ""
            print(f"  {name:12} {w['sila']:16} {w['trafne']}/{w['surowe']}{uwaga}")
    print(f"\nMapa zapisana: {out}")
    print("➡ ETAP 2 (decyzja usera): wybierz kanały + limity do drążenia. Pamiętaj: to grube sito —")
    print('  „silny" oznacza dużo surowych trafień (z homonimami); ostrość daje model w drążeniu.')


if __name__ == "__main__":
    main()
