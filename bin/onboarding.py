#!/usr/bin/env python3
"""Backend kreatora pierwszego uruchomienia dla dossier-niszy-keyless.

PODZIAŁ RÓL: rozmowę prowadzi MODEL wg scenariusza `../nux-wizard.md`.
Ten skrypt robi tylko mechanikę (sam NIE pyta):
  --check                 wykryj zależności → raport (co działa / czego brak) [+ --json]
  --install A B …         pip-instaluj lekkie zależności (yt-dlp, seleniumbase, …)
  --save '<json>'         zapisz ustawienia + klucze usera do configu (+ SETUP_COMPLETE)

Klucze NIGDY nie są w kodzie — trafiają wyłącznie do lokalnego configu usera
(`config.py`: warstwa 3 plik .env chmod 600 lub warstwa 4 Keychain na macu).
"""
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _load_config():
    p = Path(__file__).with_name("config.py")
    spec = importlib.util.spec_from_file_location("dnk_config", str(p))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CFG = _load_config()
PLAT = "mac" if sys.platform == "darwin" else ("win" if sys.platform.startswith("win") else "linux")
PIP = f"{Path(sys.executable).name} -m pip install -U"

# zależność → jak doinstalować (pip-instalowalne lub komenda per OS)
HINTS = {
    "yt-dlp":               {"pip": "yt-dlp",               "cmd": f"{PIP} yt-dlp"},
    "seleniumbase":         {"pip": "seleniumbase",         "cmd": f"{PIP} seleniumbase"},
    "google-play-scraper":  {"pip": "google-play-scraper",  "cmd": f"{PIP} google-play-scraper"},
    "browser-cookie3":      {"pip": "browser-cookie3",      "cmd": f"{PIP} browser-cookie3"},
    "deno":                 {"pip": None, "cmd": {
        "mac":   "brew install deno",
        "linux": "curl -fsSL https://deno.land/install.sh | sh",
        "win":   "irm https://deno.land/install.ps1 | iex"}},
    "Chrome":               {"pip": None, "cmd": "Pobierz przeglądarkę: https://www.google.com/chrome/"},
}


def _has_mod(name):
    return importlib.util.find_spec(name) is not None


def _has_cmd(name):
    return shutil.which(name) is not None


def _has_chrome():
    if Path("/Applications/Google Chrome.app").exists():
        return True
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(c):
            return True
    if PLAT == "win":
        for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
            if Path(p).exists():
                return True
    return False


def _fb_logged_in():
    """True/False jeśli umiemy sprawdzić sesję FB w Chrome; None gdy nie wiadomo."""
    if not _has_mod("browser_cookie3"):
        return None
    try:
        import browser_cookie3 as bc
        cj = bc.chrome(domain_name="facebook.com")
        return any(c.name == "c_user" for c in cj)
    except Exception:
        return None


def detect():
    return {
        "platform": PLAT,
        "python": sys.version.split()[0],
        "yt_dlp": _has_cmd("yt-dlp"),
        "deno": _has_cmd("deno"),
        "seleniumbase": _has_mod("seleniumbase"),
        "chrome": _has_chrome(),
        "browser_cookie3": _has_mod("browser_cookie3"),
        "google_play_scraper": _has_mod("google_play_scraper"),
        "fb_logged_in": _fb_logged_in(),
    }


ALWAYS = "✅ działa od ręki (zero instalacji)"


def channels(d):
    """[(kanał, gotowy?, opis)] — stan każdego kanału wg wykrytych zależności."""
    def need(*pairs):  # pairs: (warunek_brak, nazwa)
        miss = [n for cond, n in pairs if cond]
        return ("✅ gotowe", True) if not miss else ("⚠ wymaga: " + ", ".join(miss), False)

    rows = [
        ("Wykop", True, ALWAYS),
        ("Reddit", True, ALWAYS),
        ("App Store", True, ALWAYS),
        ("Popyt (Trends/Autocomplete)", True, ALWAYS),
        ("Web/SERP (DuckDuckGo)", True, ALWAYS),
    ]
    txt, ok = need((not d["yt_dlp"], "yt-dlp"), (not d["deno"], "deno"))
    rows.append(("YouTube", ok, txt))
    txt, ok = need((not d["google_play_scraper"], "google-play-scraper"))
    rows.append(("Google Play", ok, txt))
    txt, ok = need((not d["seleniumbase"], "seleniumbase"), (not d["chrome"], "Chrome"))
    if ok:
        txt = "✅ gotowe (best-effort, ~10 recenzji/firma; podaj miasto)"
    rows.append(("Google Maps (recenzje ≤3★)", ok, txt))
    txt, ok = need((not d["seleniumbase"], "seleniumbase"), (not d["chrome"], "Chrome"),
                   (not d["browser_cookie3"], "browser-cookie3"))
    if ok and d["fb_logged_in"] is False:
        txt = "⚠ zaloguj się do Facebooka w Chrome (sesja nie wykryta)"
        ok = False
    rows.append(("Facebook (grupy)", ok, txt))
    return rows


def missing_deps(d):
    """Lista brakujących zależności (do instalacji), z podziałem pip / inne."""
    pip, other = [], []
    checks = [
        (not d["yt_dlp"], "yt-dlp"), (not d["deno"], "deno"),
        (not d["seleniumbase"], "seleniumbase"),
        (not d["google_play_scraper"], "google-play-scraper"),
        (not d["browser_cookie3"], "browser-cookie3"),
        (not d["chrome"], "Chrome"),
    ]
    for cond, name in checks:
        if not cond:
            continue
        h = HINTS[name]
        (pip if h["pip"] else other).append(name)
    return pip, other


def cmd_for(name):
    h = HINTS.get(name, {})
    c = h.get("cmd")
    return c.get(PLAT) if isinstance(c, dict) else c


def do_check(as_json):
    d = detect()
    rows = channels(d)
    pip, other = missing_deps(d)
    if as_json:
        print(json.dumps({
            "platform": d["platform"], "detect": d,
            "channels": [{"kanal": k, "ok": ok, "opis": t} for k, ok, t in rows],
            "missing_pip": pip, "missing_other": other,
            "install_cmds": {n: cmd_for(n) for n in (pip + other)},
            "setup_complete": CFG.is_setup_complete(),
        }, ensure_ascii=False, indent=2))
        return
    print(f"\n  System: {d['platform']} · Python {d['python']}\n")
    print("  KANAŁY — co działa od ręki:")
    for k, ok, t in rows:
        print(f"   {'✅' if ok else '⚠️ '} {k:<32} {t}")
    if pip:
        print("\n  Do doinstalowania (lekkie, jedna komenda):")
        print(f"   {PIP} {' '.join(pip)}")
        print(f"   lub przez kreator: onboarding.py --install {' '.join(pip)}")
    for n in other:
        print(f"\n  {n}: {cmd_for(n)}")
    print(f"\n  Config: {CFG.CONFIG_FILE}  (SETUP_COMPLETE: {CFG.is_setup_complete()})")
    print("  Skill DZIAŁA już teraz na kanałach ✅ — reszta to dodatki.\n")


def do_install(names):
    pip_pkgs, manual = [], []
    for n in names:
        h = HINTS.get(n)
        if not h:
            print(f"  ✗ nieznana zależność: {n}", file=sys.stderr)
            continue
        if h["pip"]:
            pip_pkgs.append(h["pip"])
        else:
            manual.append(n)
    if pip_pkgs:
        cmd = [sys.executable, "-m", "pip", "install", "-U"] + pip_pkgs
        print(f"  ⏳ {' '.join(cmd)}")
        r = subprocess.run(cmd)
        print("  ✅ zainstalowane" if r.returncode == 0 else "  ✗ instalacja nie powiodła się")
    for n in manual:
        print(f"  ↪ {n} zainstaluj ręcznie: {cmd_for(n)}")


def do_save(payload):
    try:
        data = json.loads(payload)
    except Exception as e:
        sys.exit(f"--save: zły JSON ({e})")
    vals = {}
    for k in CFG.SECRET_KEYS:
        if data.get(k):
            vals[k] = str(data[k]).strip()
    for k in CFG.SETTING_KEYS:
        if k in data and data[k] is not None and str(data[k]) != "":
            vals[k] = str(data[k]).strip()
    vals["SETUP_COMPLETE"] = "true"
    path = CFG.save(vals)
    saved_secrets = [k for k in CFG.SECRET_KEYS if k in vals]
    print(f"  ✅ zapisano: {path} (chmod 600)")
    print(f"     ustawienia: " + ", ".join(f"{k}={vals[k]}" for k in CFG.SETTING_KEYS if k in vals))
    print(f"     klucze usera: " + (", ".join(saved_secrets) if saved_secrets else "brak (tryb keyless)"))


def main():
    ap = argparse.ArgumentParser(description="Backend kreatora dossier-niszy-keyless (mechanika; pytania prowadzi model wg nux-wizard.md)")
    ap.add_argument("--check", action="store_true", help="wykryj zależności → raport kanałów")
    ap.add_argument("--json", action="store_true", help="(z --check) wynik jako JSON dla modelu")
    ap.add_argument("--install", nargs="+", metavar="DEP", help="pip-instaluj zależności (yt-dlp seleniumbase …)")
    ap.add_argument("--save", metavar="JSON", help="zapisz config: '{\"FB_ENABLED\":\"false\",\"SERPAPI\":\"...\"}'")
    args = ap.parse_args()
    if args.install:
        do_install(args.install)
    elif args.save is not None:
        do_save(args.save)
    else:
        do_check(args.json)  # domyślnie --check


if __name__ == "__main__":
    main()
