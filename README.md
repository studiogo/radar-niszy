# radar-niszy

Skill do **Claude Code**, który szuka realnych problemów ludzi w wybranej niszy (bólów, popytu, sygnałów rynkowych) i składa z nich raport. Działa **keyless** — bez żadnych kont i kluczy API; korzysta z publicznych danych (Wykop, Reddit, YouTube, App Store, Google Play, Google Trends, wyszukiwarka, opcjonalnie Google Maps i Facebook).

> Wewnętrzna nazwa skilla: `dossier-niszy-keyless`. To repozytorium = paczka do instalacji.

## Wymagania

- **Claude Code** (zainstalowany i działający).
- **Python 3** — jedyny twardy wymóg. Jeśli go nie masz, **skill sam zaproponuje instalację przy pierwszym uruchomieniu** (Windows `winget`, macOS `brew`, Linux `apt`) — nie musisz nic robić ręcznie.
- Pozostałe biblioteki (yt-dlp, seleniumbase…) są **opcjonalne** — potrzebne tylko pod niektóre kanały; kreator dociągnie je za Twoją zgodą. Rdzeń (Wykop, Reddit, App Store, Trends, wyszukiwarka) działa na samym Pythonie.

**Gita NIE potrzebujesz.** Instalacja idzie przez ZIP.

## Instalacja — Windows (najprościej, przez Claude)

Otwórz Claude Code i wklej polecenie:

```
Zainstaluj skill z https://github.com/studiogo/radar-niszy :
1. Pobierz ZIP: https://github.com/studiogo/radar-niszy/archive/refs/heads/main.zip
2. Rozpakuj go (PowerShell: Expand-Archive).
3. Zawartość folderu radar-niszy-main przenieś do: %USERPROFILE%\.claude\skills\radar-niszy
   (utwórz ten folder, ma w nim być plik SKILL.md i folder bin).
4. Potwierdź, że plik %USERPROFILE%\.claude\skills\radar-niszy\SKILL.md istnieje.
```

Claude zrobi to wbudowanym PowerShellem (bez gita). Potem napisz np. „przebadaj niszę: aplikacje do nauki angielskiego" — przy pierwszym uruchomieniu kreator sprawdzi Pythona (i w razie braku zainstaluje za Twoją zgodą), a potem poprowadzi przez resztę.

## Instalacja — ręcznie (każdy system)

1. Wejdź na https://github.com/studiogo/radar-niszy → **Code → Download ZIP**.
2. Rozpakuj.
3. Skopiuj zawartość do katalogu skilli Claude Code:
   - Windows: `%USERPROFILE%\.claude\skills\radar-niszy\`
   - macOS/Linux: `~/.claude/skills/radar-niszy/`
   (w środku ma być `SKILL.md` i folder `bin/`).
4. Uruchom Claude Code w tym katalogu / przeładuj skille.

## Użycie

W Claude Code napisz po ludzku, co chcesz przebadać, np.:
- „przebadaj niszę: kursy jogi dla seniorów"
- „poszukaj pomysłu na biznes w obszarze: automatyzacja małych firm"

Skill przeprowadzi zwiad, zbierze sygnały z kanałów i złoży raport HTML.

## Klucze API (opcjonalne)

Skill działa bez żadnych kluczy. Jeśli masz własne (SerpApi, YouTube Data API, Wykop, Apify, Tavily), możesz je dodać dla większej odporności i dokładności — szczegóły i darmowe limity w [`CONFIGURATION.md`](CONFIGURATION.md). Twoje klucze trafiają wyłącznie do lokalnego pliku konfiguracyjnego na Twoim komputerze — nigdy do tego repozytorium.

## Licencja

MIT — patrz [`LICENSE`](LICENSE).
