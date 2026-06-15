# Scenariusz kreatora pierwszego uruchomienia — dossier-niszy-keyless

> **Dla modelu prowadzącego.** Czytasz ten plik przy PIERWSZYM uruchomieniu skilla
> (gdy `~/.config/dossier-niszy-keyless/.env` z `SETUP_COMPLETE=true` nie istnieje).
> Prowadzisz rozmowę po polsku, plain language, krok po kroku. Pytania zadajesz
> DOKŁADNIE wg tego scenariusza — nie wymyślasz własnych. Mechanikę (wykrywanie,
> instalacja, zapis) robi `bin/onboarding.py`; Ty pytasz i decydujesz co zapisać.
>
> **Zasady prowadzenia:**
> - Jeden krok = jedno pytanie. Czekaj na odpowiedź, nie wysyłaj wszystkiego naraz.
> - Skill DZIAŁA bez kreatora (tor keyless). Kreator tylko dostraja — nie strasz, nie blokuj.
> - User jest NIETECHNICZNY. **KOMUNIKATY DO NIEGO = ZERO ŻARGONU.** W cytatach do usera NIGDY
>   nie pisz: „skill", „kanał", „keyless", „API"/„klucz API", „config", „yt-dlp", „deno", „token",
>   „sygnały", „bóle", „wolumen". Zamiast tego: „narzędzie", „źródło", „bez kont", „dodatek",
>   „ustawienia", „opinie/problemy". Jeśli MUSISZ użyć trudnego słowa — wyjaśnij od razu w nawiasie
>   prostymi słowami (np. „klucz = hasło dostępu do usługi"). Każdy komunikat ma zrozumieć osoba
>   zupełnie nietechniczna — babcia, nie programista.
> - Klucze należą do USERA. Nigdy nie podajesz żadnych swoich/cudzych kluczy.
> - Na końcu KAŻDY wybór trafia do `onboarding.py --save`.

---

## KROK 0 — Preflight: dociągnij czego trzeba (ZANIM cokolwiek)

> Ścieżki w tym pliku są WZGLĘDNE wobec katalogu tego skilla — Claude Code podaje go przy
> uruchomieniu jako „Base directory for this skill". Uruchamiaj `bin/...` z tego katalogu.
> `<PY>` = polecenie Pythona ustalone niżej (`python` na Windows, `python3` na mac/Linux).

Skill to Python 3 — bez niego nic nie ruszy. Sprawdź i w razie braku **ZAINSTALUJ za zgodą usera**,
komendą powłoki (NIE przez `onboarding.py` — bez Pythona on też nie ruszy).

**1) Sprawdź Pythona:**
- Windows: `python --version` (oraz `py -3 --version`)
- macOS/Linux: `python3 --version`

⚠ Windows: `python` bywa atrapą Microsoft Store („Python was not found…"). Jeśli wynik nie zaczyna
się od „Python 3." → traktuj jak BRAK.

**2) Jeśli brak Pythona — zaproponuj i zainstaluj ZA ZGODĄ usera:**

> „Brakuje **Pythona** — darmowego silnika, na którym chodzi narzędzie. Mam go zainstalować teraz? [tak/nie]"

- **Windows:** `winget install -e --id Python.Python.3.12` (jeśli po instalacji `python` dalej pokazuje
  atrapę → używaj `py -3`, albo poproś o ponowne otwarcie terminala / wyłączenie aliasu w Ustawieniach →
  Aliasy wykonywania aplikacji).
- **macOS:** `brew install python` (gdy brak `brew` → https://brew.sh).
- **Linux:** `sudo apt install -y python3 python3-pip`.

Po instalacji potwierdź, że `--version` zwraca „Python 3.x".

**3) Ustal `<PY>`** na tę sesję: `python` (Windows) lub `python3` (mac/Linux). Pozostałych zależności
(yt-dlp, seleniumbase…) NIE instaluj tutaj — to robi KROK 2 (`onboarding.py --check` → `--install`),
gdy Python już jest.

Nie idź do KROK 1, dopóki `<PY> --version` nie zwróci „Python 3.x".

## KROK 1 — Powitanie

Powiedz (1-2 zdania, własnymi słowami w tym duchu):

> „Cześć! To pierwsze uruchomienie, więc w 4 krótkich pytaniach ustawię narzędzie pod Ciebie.
> Ono wyszukuje, na co ludzie narzekają i czego szukają w wybranym temacie (zagląda m.in. na
> Wykop, Reddita, YouTube, do opinii w sklepach i do Google). **Działa od razu, za darmo, bez
> zakładania żadnych kont.** Te pytania tylko dopasują je do Twojego komputera."

Nie pytaj nic jeszcze. Przejdź do KROK 2.

## KROK 2 — Co działa na tym komputerze

Uruchom:
```bash
<PY> bin/onboarding.py --check --json
```
Z JSON-a zbuduj userowi PROSTĄ mapę (plain Polish), np.:

> „Sprawdziłem Twój komputer. **Działa od ręki:** Wykop, Reddit, App Store, trendy Google,
> wyszukiwarka. **Wymaga doinstalowania paru darmowych dodatków** (zrobię to za Ciebie): np.
> żeby zadziałał YouTube albo Facebook."

Jeśli `missing_pip` NIEpuste → zadaj **PYTANIE A**:

> „Chcesz, żebym teraz doinstalował te brakujące dodatki? Są darmowe i bezpieczne, zajmie
> chwilę. — [tak, doinstaluj / nie, zostawmy bez nich]"

- **tak** → uruchom `onboarding.py --install <lista z missing_pip>`, potem ponów `--check --json` i pokaż zaktualizowaną mapę.
- **nie** → idź dalej; te kanały po prostu będą pomijane.

Dla `missing_other` (deno, Chrome — nie z pip) pokaż komendę z `install_cmds`, ale NIE instaluj sam. Powiedz, że to opcjonalne i można później.

## KROK 3 — Facebook (domyślnie WŁĄCZONY) — PYTANIE B

Zadaj pytanie spokojnym tonem (bez straszenia):

> „Narzędzie może też zaglądać do **publicznych grup na Facebooku** — to dobre źródło
> problemów ludzi. Czyta z Twojego konta zalogowanego w Chrome, więc wcześniej musisz być
> na nim zalogowany w przeglądarce. Widzi tylko grupy publiczne/widoczne.
> Drobna uwaga: automatyczne przeszukiwanie Facebooka jest niezgodne z jego regulaminem —
> jest **niewielkie ryzyko blokady konta**, głównie gdybyś używał narzędzia bardzo intensywnie.
> Włączyć szukanie na Facebooku? — [tak / nie]"

- **tak** → `FB_ENABLED=true`
- **nie** → `FB_ENABLED=false`

## KROK 4 — Google Maps + miasto (best-effort) — PYTANIE C

Wyjaśnij i zapytaj:

> „Narzędzie może też zebrać **słabe oceny firm z Map Google (do 3 gwiazdek)** — to skargi
> klientów, czyli gotowe problemy do rozwiązania. Włącza się samo, jeśli masz przeglądarkę
> Chrome. Szczerze: w testach wyciągało **około 10 najgorszych opinii z jednej firmy** (u Ciebie
> może być więcej). Im więcej firm sprawdzimy, tym więcej opinii zbierzemy.
> Potrzebuję tylko **miasta**, w którym mam szukać firm (np. Warszawa). Podaj miasto albo napisz
> „pomiń". — [miasto / pomiń / wyłącz]"

- podane miasto → `MAPS_ENABLED=true`, `LOCATION=<miasto>`
- „pomiń" → `MAPS_ENABLED=true`, bez `LOCATION` (kanał uśpiony do czasu podania miasta)
- „wyłącz" → `MAPS_ENABLED=false`

## KROK 5 — Opcjonalne klucze usera — PYTANIE D

Wyjaśnij, że to NIEobowiązkowe:

> „Ostatnia rzecz, całkowicie nieobowiązkowa. Narzędzie działa bez żadnych kont. Ale jeśli masz
> własne **klucze dostępu** (to takie hasła do paru usług, np. SerpApi albo Tavily), mogę je
> dodać — wtedy narzędzie rzadziej się blokuje i jest dokładniejsze.
> Masz takie hasła, czy lecimy bez nich? — [mam / bez nich]"

- **bez kluczy** → nic nie zbieraj, idź do KROK 6.
- **mam klucze** → pokaż tabelę (z `CONFIGURATION.md`) co do czego służy i gdzie wziąć darmowy:

  | Klucz (zmienna) | Do czego (fallback) | Darmowy limit |
  |---|---|---|
  | `SERPAPI` | mocniejszy popyt + dobór apek | ~100 zapytań/mies. |
  | `YOUTUBE_DATA_API` | YouTube gdy yt-dlp zablokowany | 10 000 jedn./dzień |
  | `WYKOP_KEY` + `WYKOP_SECRET` | Wykop: pełnotekstowe szukanie | darmowe (konto dev) |
  | `APIFY_TOKEN` | Facebook bez logowania (zamiast konta) | ~5 USD kredytu/mies. |
  | `TAVILY_API_KEY` | lepsze wyniki web | 1 000 zapytań/mies. |

  Zbieraj **tylko te, które user poda** — pojedynczo, bez nacisku. Klucz wklejony przez usera
  trzymaj w zmiennej o nazwie z kolumny pierwszej.

## KROK 6 — Zapis configu

Złóż JSON ze WSZYSTKICH zebranych decyzji i zapisz:
```bash
<PY> bin/onboarding.py --save '{
  "FB_ENABLED":"true","MAPS_ENABLED":"true","LOCATION":"Warszawa",
  "SERPAPI":"<jeśli podał>","TAVILY_API_KEY":"<jeśli podał>"
}'
```
(Pomiń klucze, których user nie podał — nie wpisuj pustych.) Skrypt sam dopisze
`SETUP_COMPLETE=true` i ustawi `chmod 600`. Potwierdź userowi krótko, co zapisałeś
(bez pokazywania wartości kluczy).

## KROK 7 — Pierwszy research

Powiedz, że gotowe, i zaproś do startu:

> „Gotowe — ustawienia zapisane. Możemy zacząć. Napisz, jaki **temat albo branżę** mam
> przebadać (np. „automatyzacja małej firmy", „AI dla nauczycieli"), a ja poszukam w
> internecie, na co ludzie narzekają, i zrobię z tego raport."

Dalej działasz wg głównego procesu skilla (`SKILL.md`: ETAP 0 → … → raport). Kreatora
**nie powtarzasz** przy kolejnych uruchomieniach (jest `SETUP_COMPLETE=true`).
