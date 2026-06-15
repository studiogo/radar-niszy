# Konfiguracja — dossier-niszy-keyless

Skill **działa bez żadnego klucza** (tor keyless). Ta tabela jest dla usera, który MA własne
darmowe klucze i chce odporniejszego/dokładniejszego działania. Klucze są **Twoje** — nie są
wpisane w kod skilla.

## Kanały i czy potrzebują klucza

| Kanał | Tryb keyless (domyślnie) | Klucz (opcjonalny fallback) | Po co fallback |
|---|---|---|---|
| Wykop | scraping strony tagu | `WYKOP_KEY` + `WYKOP_SECRET` | pełnotekstowe szukanie gdy fraza nie ma tagu |
| Reddit | publiczny RSS (posty+komentarze) | — | (PRAW tylko dla usera z własnymi kluczami) |
| YouTube | `yt-dlp` (search+komentarze+lajki) | `YOUTUBE_DATA_API` | gdy yt-dlp zablokowany |
| Google Play | biblioteka `google-play-scraper` | `SERPAPI` | dobór apek gdy scraping HTML padnie |
| App Store | iTunes API + RSS recenzji | — | (czysto keyless) |
| Popyt (Trends/Autocomplete) | Google Trends + Autocomplete | `SERPAPI` | mocniejszy popyt + nasycenie Maps |
| Web/SERP | DuckDuckGo HTML | `TAVILY_API_KEY` | lepsze wyniki web |
| Google Maps (recenzje ≤3★) | seleniumbase UC headless | — | (czysto keyless; ~10/firma) |
| Facebook (grupy) | auto-cookies z Chrome + UC | `APIFY_TOKEN` | bez logowania własnym kontem |

## Darmowe limity (skąd wziąć klucz)

| Zmienna | Usługa | Darmowy limit | Link |
|---|---|---|---|
| `SERPAPI` | SerpApi | ~100 zapytań/mies. | serpapi.com |
| `YOUTUBE_DATA_API` | Google Cloud (YouTube Data API v3) | 10 000 jedn./dzień | console.cloud.google.com |
| `WYKOP_KEY` / `WYKOP_SECRET` | Wykop API v3 | darmowe (konto deweloperskie) | wykop.pl/dla-programistow |
| `APIFY_TOKEN` | Apify | ~5 USD kredytu/mies. | apify.com |
| `TAVILY_API_KEY` | Tavily | 1 000 zapytań/mies. | tavily.com |

## Gdzie trafiają klucze (warstwy, wyżej wygrywa)

1. **zmienna środowiskowa** — `export SERPAPI=...` (chwilowo / CI)
2. **plik projektu** — `./.dossier-niszy-keyless.env` w katalogu, z którego uruchamiasz (per klient)
3. **config globalny** — `~/.config/dossier-niszy-keyless/.env` (**chmod 600** — domyślne miejsce kreatora)
4. **Keychain (mac)** — usługa `dossier-niszy-keyless-<ZMIENNA>` (np. `dossier-niszy-keyless-SERPAPI`)

Format pliku `.env` (każda linia `KLUCZ=wartość`):
```
SERPAPI=twoj_klucz
TAVILY_API_KEY=twoj_klucz
FB_ENABLED=true
MAPS_ENABLED=true
LOCATION=Warszawa
SETUP_COMPLETE=true
```

## Ustawienia (nie-sekrety, pisze je kreator)

| Zmienna | Wartości | Znaczenie |
|---|---|---|
| `FB_ENABLED` | true/false | kanał Facebook (domyślnie true; ⚠ ryzyko banu konta) |
| `MAPS_ENABLED` | true/false | kanał Google Maps (domyślnie true gdy jest przeglądarka) |
| `LOCATION` | miasto | miasto dla recenzji Google Maps |
| `SETUP_COMPLETE` | true | znacznik, że kreator przeszedł (nie powtarza się) |

CLI nadpisuje config: `--no-fb`, `--no-maps`, `--location "Kraków"`, `--glebokosc N`.
