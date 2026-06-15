#!/usr/bin/env python3
"""Warstwowy config dla dossier-niszy-keyless (wzorzec last30days).

Priorytet (warstwa wyżej WYGRYWA):
  1. zmienna środowiskowa    os.environ[KEY]
  2. plik projektu           ./.dossier-niszy-keyless.env   (CWD — per klient)
  3. config globalny         ~/.config/dossier-niszy-keyless/.env
  4. Keychain (mac)          usługa 'dossier-niszy-keyless-<KEY>'
  5. FALLBACK WSTECZNY        klucze AUTORA (Keychain 'serpapi'/'wykop-key'/… +
                             ~/.claude/.env) — żeby istniejące uruchomienia
                             Łukasza działały bez zmiany. Wyłączany przez
                             DNK_DISABLE_BACKCOMPAT=1 (test 'czystej maszyny').

ŻADEN klucz obcego usera NIE jest wpisany w kod — moduł je tylko CZYTA z lokalnych
warstw. Wersja do rozdania nie niesie kluczy Łukasza (te żyją w jego Keychain,
nie w plikach skilla).
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "dossier-niszy-keyless"
CONFIG_FILE = CONFIG_DIR / ".env"
PROJECT_FILE = Path.cwd() / ".dossier-niszy-keyless.env"
NS = "dossier-niszy-keyless"

# logiczny KLUCZ → (usługa Keychain autora, nazwa w ~/.claude/.env) — TYLKO fallback wsteczny
_BACKCOMPAT = {
    "SERPAPI":          ("serpapi", None),
    "SERPAPI_BACKUP":   ("serpapi-backup", None),
    "WYKOP_KEY":        ("wykop-key", None),
    "WYKOP_SECRET":     ("wykop-secret", None),
    "YOUTUBE_DATA_API": ("youtube-data-api", None),
    "APIFY_TOKEN":      ("apify-token", None),
    "TAVILY_API_KEY":   (None, "TAVILY_API_KEY"),
}

# klucze-sekrety (klucze API usera) i ustawienia nie-sekretne (preferencje)
SECRET_KEYS = tuple(_BACKCOMPAT.keys())
SETTING_KEYS = ("FB_ENABLED", "MAPS_ENABLED", "LOCATION", "GLEBOKOSC", "SETUP_COMPLETE")


def _parse_env(path):
    out = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _keychain(service):
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                           capture_output=True, text=True, check=True)
        v = r.stdout.strip()
        return v or None
    except Exception:
        return None


def _claude_env(name):
    try:
        for line in (HOME / ".claude/.env").read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def get(key, default=None):
    """Wartość klucza wg warstw (góra wygrywa); None gdy nigdzie nie ma."""
    v = os.environ.get(key)
    if v:
        return v
    v = _parse_env(PROJECT_FILE).get(key)
    if v:
        return v
    v = _parse_env(CONFIG_FILE).get(key)
    if v:
        return v
    if sys.platform == "darwin":
        v = _keychain(f"{NS}-{key}")
        if v:
            return v
    # fallback wsteczny do kluczy autora (test czystej maszyny: DNK_DISABLE_BACKCOMPAT=1)
    if not os.environ.get("DNK_DISABLE_BACKCOMPAT") and key in _BACKCOMPAT:
        svc, envname = _BACKCOMPAT[key]
        if svc and sys.platform == "darwin":
            v = _keychain(svc)
            if v:
                return v
        if envname:
            v = _claude_env(envname)
            if v:
                return v
    return default


def get_bool(key, default=False):
    v = get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "tak", "on")


def serpapi_keys():
    """Lista (usługa, klucz) dla warstwy POPYTU (badaj-popyt). PUSTA gdy brak —
    NIGDY sys.exit. To naprawia crash na czystej maszynie keyless (badaj-popyt
    `get_api_keys()` robił sys.exit bez klucza SerpApi)."""
    out = []
    for k, label in (("SERPAPI", "serpapi"), ("SERPAPI_BACKUP", "serpapi-backup")):
        v = get(k)
        if v and len(v) >= 20:
            out.append((label, v))
    return out


def is_setup_complete():
    return _parse_env(CONFIG_FILE).get("SETUP_COMPLETE", "").lower() in ("1", "true", "yes", "tak")


def save(values: dict):
    """Merge i zapis configu globalnego (chmod 600). Zwraca ścieżkę pliku."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cur = _parse_env(CONFIG_FILE)
    for k, v in values.items():
        if v is None or str(v) == "":
            continue
        cur[k] = str(v)
    lines = [
        "# dossier-niszy-keyless — config usera (NIE commituj; chmod 600).",
        "# Klucze są TWOJE; skill działa też BEZ nich (tor keyless).",
        "",
    ]
    for k in sorted(cur):
        lines.append(f"{k}={cur[k]}")
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass
    return CONFIG_FILE


if __name__ == "__main__":
    # szybki podgląd stanu configu (bez ujawniania wartości sekretów)
    print(f"config globalny: {CONFIG_FILE}  (istnieje: {CONFIG_FILE.exists()})")
    print(f"SETUP_COMPLETE: {is_setup_complete()}")
    for k in SECRET_KEYS:
        print(f"  {k}: {'ustawiony' if get(k) else '—'}")
    for k in SETTING_KEYS:
        print(f"  {k}: {get(k) or '—'}")
