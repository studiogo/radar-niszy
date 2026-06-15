---
name: dossier-niszy-keyless
description: Wersja dossier-niszy KEYLESS-FIRST (do rozdania nietechnicznym) — domyślnie szuka BEZ kluczy API (scraping danych publicznych), klucze/konta wchodzą tylko jako fallback. Reszta procesu jak w dossier-niszy. Use gdy Łukasz mówi "dossier bez kluczy", "wersja keyless dossier", "skill dla ludzi bez kluczy".
---

# Skill: dossier-niszy-keyless (KEYLESS-FIRST)

> **Wariant `dossier-niszy` z domyślnym torem bez kluczy.** Każdy kanał ma kaskadę: **L1 keyless** (scraping danych publicznych) → **L3 fallback** (klucz/konto, jeśli user go ma). Proces, sędzia, profil A, raport — bez zmian. Kopia powstała 14.06.2026.
>
> **Status wpięcia keyless (na bieżąco):**
> - ✅ **Wykop** — L1 scraping strony tagu (`bin/wykop_keyless.py`, bez klucza, niesie też głosy); L3 fallback = API v3 (klucz) gdy fraza nie ma tagu. Przetestowane na żywo.
> - ✅ **Reddit** — L1 publiczny RSS (`bin/reddit_keyless.py`, BEZ aplikacji/klucza): globalny `search.rss` (posty) **+ komentarze przez `post.rss`** (najbogatsze źródło bólów) + opcjonalnie per-sub; throttle + retry/backoff (RSS ma ciasny limit per IP). `.json` Reddita dziś = 403, więc keyless = wyłącznie RSS; jedyna strata vs API = `score`. **Klucze Łukasza NIE idą do rozdania** — keyless pokrywa posty I komentarze; PRAW (`reddit-search.py`) tylko jako opcja dla usera z WŁASNYMI kluczami. Przetestowane na żywo (posty + komentarze).
> - ✅ **YouTube** — L1 `yt-dlp` (`bin/youtube_keyless.py`, BEZ klucza ani kwoty): `ytsearchN:` (wyszukiwanie) + komentarze + **polubienia** (`like_count` — keyless YT niesie score, inaczej niż Reddit RSS); filtr markerów bólu tnie szum „super!". L3 fallback = `youtube-data-api` (kwota 100 jedn./search) gdy yt-dlp zablokowany. Wymaga `yt-dlp` + `deno` (JS challenge) — oba w stacku. Przetestowane na żywo (search + komentarze).
> - ✅ **Google Play** — recenzje keyless (biblioteka `google-play-scraper`); dobór apek keyless przez scraping HTML wyszukiwarki (`bin/gplay_keyless.py`, bo `search()` biblioteki jest dziś zepsuty — `NoneType`). L3 fallback doboru = SerpApi (`_gplay_ids_serpapi`). Przetestowane na żywo.
> - ✅ **App Store** — w 100% keyless od początku (iTunes Search API + RSS recenzji, zero klucza). **FIX 14.06:** `sortby=mostrecent` zwraca dziś 0 wpisów → przełączone na `mosthelpful` (z fallbackiem). ⚠ ten sam błąd jest w ORYGINALNYM `dossier-niszy` (zwraca 0 z App Store) — do backportu. PL RSS ma recenzje tylko dla apek, które je mają (niszowe/małe apki bywają puste — to natura danych, nie klucz). Przetestowane na żywo.
> - ◑ **Popyt (Trends/Autocomplete/Maps)** — `bin/popyt_keyless.py`, wpięte keyless-first w `zwiad.py`. **Autocomplete keyless ✅** (suggestqueries, `client=chrome` utf-8 — „język klienta"). **Trends keyless ✅** (explore→widgetdata LOKALNIE na maszynie usera, bez klucza/VPS; rozgrzewka cookie + backoff na 429; potwierdzone 14.06 na Macu Łukasza: 53 pkt + rising). Świeże IP usera → działa dla lekkiego użycia; przy zajechaniu IP → miękkie zejście (fallback SerpApi tylko jeśli user ma WŁASNY klucz). **Maps-popyt (nasycenie)** = key-only (Nominatim zaniża, OSM bez ocen). Przetestowane na żywo (autocomplete + Trends).
> - ⚠️ **Google Maps (recenzje wizytówek)** — kanał `bin/maps_keyless.py` (Python **seleniumbase uc=True** — undetected headless, BEZ klucza). Port rdzenia repo `georgekhananaev/google-reviews-scraper-pro` (MIT, ⭐251). Wyciąga **recenzje ≤3★ = skargi** (treść+autor+ocena), sort „najniższe" + scroll-harvest po `data-review-id`. **KANAŁ OPCJONALNY** (`_browser_ready()` = seleniumbase + Chrome; guard pomija po cichu). Lokalny (`--location`). **TWARDY LIMIT środowiska: ~10 recenzji/firma w tym sandboxie — głębia headless NIE działa tu nawet w oryginalnym repo (0 recenzji, „Reviews tab not found").** Wolumen tylko przez liczbę firm. ⚠ Na realnym desktopie usera (ekran + residential IP) UC może sięgać głębiej — NIEzweryfikowane stąd (pewność ~50%). Wpięty w `CHANNELS` + `gmaps_pains`.
> - ✅ **Web/SERP (odkrywanie + konkurencja)** — `bin/web_keyless.py` (DuckDuckGo HTML, BEZ klucza, 12 wyników z tytułem+URL+opisem). Zastępuje SerpApi/Tavily w ETAP0/ETAP5. Bing zmienił markup (DDG prostszy). Przetestowane.
> - 🟡 **Google Groups (nowy)** — keyless DZIAŁA technicznie (`/g/<grupa>` SSR, 200, 90 wątków w HTML, brak Angulara; RSS martwy 404), ALE **niska wartość dla PL nisz biznesowych** (Groups dziś głównie martwe/anglojęzyczne/techniczne — comp.lang.*). Nie wpięte jako kanał — decyzja Łukasza czy warto. (pewność niskiej wartości ~70%)
> - ✅ **Facebook grupy (DOMYŚLNIE WŁĄCZONY)** — `bin/fb_keyless.py`: **auto-cookies z przeglądarki** (`browser_cookie3` — bezobsługowo czyta zalogowaną sesję usera) → **seleniumbase UC headless** → posty grup z `div[data-ad-rendering-role='story_message']` + scroll; discovery grup przez DuckDuckGo (keyless). Wzorzec: repo `thanh2004nguyen/facebook-group-scraper` (2025-06). Przetestowane na żywo (20 postów, realna treść). **DOMYŚLNIE WŁĄCZONY** (`FB_OPTIN=True`); user **wyłącza w onboardingu** (`--no-fb`). ⚠ automat na zalogowanym koncie FB łamie ToS = ryzyko banu KONTA usera (komunikat w onboardingu); widać tylko grupy publiczne/widoczne (prywatne member-only = puste). L3 fallback = Apify (`_fb_apify`, własny token usera). Twoich kluczy/konta nie embedujemy.
> - ✅ **Onboarding (Faza D)** — kreator pierwszego uruchomienia: scenariusz `nux-wizard.md` (model prowadzi rozmowę) + backend `bin/onboarding.py` (wykrywa zależności, instaluje lekkie za zgodą, zapisuje config) + warstwowy config `bin/config.py` (klucze usera; bez kluczy = keyless). Patrz **Step 0** niżej.

## Step 0a — PREFLIGHT: czy jest Python? (ZANIM uruchomisz JAKIKOLWIEK `.py`)
Cały skill to Python 3. Jeśli go nie ma, ŻADEN skrypt się nie odpali — więc sprawdź to PIERWSZE **komendą powłoki, nie przez `onboarding.py`** (bez Pythona on też nie ruszy):
- Windows: `python --version`  oraz  `py -3 --version`
- macOS/Linux: `python3 --version`

⚠ **Windows — pułapka zaślepki Microsoft Store:** `python` często jest atrapą, która wypisuje „Python was not found; run without arguments to install from the Microsoft Store". Traktuj jako BRAK Pythona, jeśli wynik NIE zaczyna się od „Python 3.".

Jeśli realnego Pythona 3 NIE ma → **zaproponuj userowi instalację i wykonaj ją ZA JEGO ZGODĄ** (model ma dostęp do powłoki — nie odsyłaj usera do ręcznej roboty, zrób to za niego po „tak"):
- **Windows:** `winget install -e --id Python.Python.3.12`. Jeśli po instalacji `python` dalej zwraca atrapę → używaj `py -3`, albo poproś usera o ponowne otwarcie terminala / wyłączenie aliasu (Ustawienia → Aplikacje → Aliasy wykonywania aplikacji → `python.exe`/`python3.exe`).
- **macOS:** `brew install python` (gdy brak `brew` → https://brew.sh).
- **Linux:** `sudo apt install -y python3 python3-pip`.

Po instalacji potwierdź `--version` = „Python 3.x" i ustal `<PY>` = `python` (Windows) / `python3` (mac/Linux). Resztę zależności (yt-dlp, seleniumbase…) dociągnie Step 0b (`onboarding.py --check` → `--install`). **Git NIE jest potrzebny** — instalacja skilla idzie przez ZIP (patrz README).

## Step 0b — Kreator pierwszego uruchomienia (onboarding)
**Trigger:** jeśli `~/.config/dossier-niszy-keyless/.env` z `SETUP_COMPLETE=true` NIE istnieje → to pierwsze uruchomienie. Przeczytaj **`nux-wizard.md`** i poprowadź kreator po polsku (sprawdzenie zależności przez `bin/onboarding.py --check --json` → FB/Maps/miasto → opcjonalne klucze usera → `bin/onboarding.py --save '<json>'`). Przy kolejnych uruchomieniach Step 0 pomijasz po cichu.
**Ważne:** skill DZIAŁA bez kreatora (tor keyless) — kreator tylko dostraja. Klucze usera trzymane w warstwowym configu (`config.py`: env > `.env` projektu > `~/.config/dossier-niszy-keyless/.env` chmod 600 > Keychain mac); kluczy autora NIGDY nie shippujemy. Klucze CLI: `--no-fb`, `--no-maps`, `--location`, `--glebokosc`. Tabela kluczy + darmowych limitów: `CONFIGURATION.md`.

# Skill: dossier-niszy v5 (sekwencyjny + agentowy)

## Trzy żelazne zasady
1. **Skrypt ZBIERA, model/agenci ANALIZUJĄ.** Skrypty (`bin/`) tylko ciągną surowiec. Trafność, klastry, werdykt — robi model sesji / agenci Workflow, NIE reguły w skrypcie (werdykt regułowy skryptu = tylko pomocniczy, liczony na surowcu z homonimami).
2. **Każda liczba ma źródło.** Pokazuj tok: ile zebrano, ile odrzucono, ile niezależnych w klastrze. Zero liczb „z czapy".
3. **Limity ustala USER, nie kod.** Żadnych zaszytych ograniczeń. Po tanim zwiadzie pokazujesz mapę sygnału i pytasz ile drążyć per kanał (`feedback_skill_limits_interactive_not_hardcoded`).

## Wymagania
Klucze (Keychain): `serpapi`(+`serpapi-backup`), `wykop-key`, `wykop-secret`, `youtube-data-api`, `apify-token`. `TAVILY_API_KEY` w `~/.claude/.env`. Biblioteka `google-play-scraper`. Reddit przez `~/.claude/scripts/reddit-search.py` (PRAW). Reużywa `badaj-popyt`.

## PROCES — 5 etapów (sekwencyjnie; checkpointy z userem)

### ETAP 0 — Odkrywanie pod-nisz + konstytucja (model)
```bash
~/.claude/skills/dossier-niszy/bin/dossier-niszy.py --odkryj "<obszar>"
```
Skrypt zwraca kandydatów pod-nisz (Trends rising/top + autocomplete). **Model wybiera 2-3** (najsilniejszy sygnał + founder-fit Łukasza: automatyzacje/AI/edukacja) i dla każdej spisuje **KONSTYTUCJĘ** (wzorzec oceny na wszystkie kolejne etapy):
- **Odbiorca** — KTO ma ból (np. „nauczyciel", NIE uczeń; „sprzedawca", NIE kupujący). Bez tego sygnały się rozjeżdżają (walidacja 11.06: rozjazd sędziów 45% vs 94% precyzji).
- **Realny ból** — co się liczy: wyrażony problem/frustracja/potrzeba/pytanie odbiorcy.
- **Szum** — co odrzucamy: wzmianka bez bólu, zła perspektywa, emocja-bez-treści, off-topic, polityka, żart, bot, homonim.
Konstytucja + słowa-klucze rdzenia + frazy → wejście do dalszych etapów.

### ETAP 1 — ZWIAD (tani sondaż → mapa sygnału)
```bash
~/.claude/skills/dossier-niszy/bin/zwiad.py --nisza "<pod-nisza>" \
  --klucze "rdzeń1,rdzeń2,…" --frazy "fraza1;fraza2;fraza3" [--probka 10]
```
Mała próbka/kanał (domyślnie 10), darmowe kanały (Trends, Wykop, Reddit, YouTube, Google Play, App Store). FB **pominięty** (Apify płatny — dostępny w drążeniu). Zwraca **MAPĘ SYGNAŁU**: „Wykop silny · Reddit silny · YouTube średni · apki pusto". **CHECKPOINT: pokaż mapę Łukaszowi.**
⚠ Zwiad to grube sito (substring, z homonimami) — „silny" = dużo surowych trafień, NIE werdykt. Ostrość daje model w drążeniu.

### ETAP 2 — WYBÓR (user) — CHECKPOINT
Na podstawie mapy Łukasz wybiera: które kanały drążyć + **ile w każdym** (limit per kanał) + które pod-nisze. Zero zaszytych limitów. FB włączasz tu świadomie, jeśli chcesz.

### ETAP 3+4 — DRĄŻENIE (równolegli agenci) + JEDEN SĘDZIA — Workflow
Wywołaj **Workflow** ze skryptem skilla:
```
Workflow({ scriptPath: "~/.claude/skills/dossier-niszy/workflow-v5.js",
  args: { nisza, konstytucja:{odbiorca,bol,szum},
          kanaly:[{nazwa:"Wykop",limit:40},{nazwa:"Reddit",limit:40,klucze:"goal,habit,…",frazy:"how to…;I keep…"},…],
          klucze:"rdzeń1,rdzeń2", frazy:"fraza1;fraza2" } })
```
Każdy kanał przyjmuje **opcjonalne `klucze`/`frazy`** (język per kanał — Reddit po angielsku, Wykop po polsku); brak → globalne.
- **ETAP 3 (parallel):** 1 agent / kanał — uruchamia `dossier-niszy.py --kanal <X> --limit N`, dedup po autorze, **wstępny tag** wg konstytucji, zwraca strukturę (+ pole „pokrycie": ile realnie przeszukał).
- **ETAP 4 (jeden agent-sędzia):** scala wszystkie kanały, wydaje **spójny** werdykt trafności wg JEDNEJ konstytucji (krytyczne — inaczej rozjazd sędziów), buduje klastry wg **progu profilu A**, oddziela częstotliwość od rezonansu.
Workflow zwraca: mapa drążenia + klastry + werdykt + pomysły + rekomendacja.

### ETAP 5 — Dossier (model składa raport HTML)
Z wyniku Workflow + mapy zwiadu złóż raport HTML pokazujący CAŁY tok: pod-nisze (+czemu) → mapa zwiadu → klastry z liczbami (status: potwierdzony/anegdota) → werdykt → konkurencja (sprawdź w sieci: WebSearch/Tavily, czy rynek obsadzony) → pomysły + ocena → rekomendacja. Oznacz wiarygodność: bóle ✅ (cytaty), pomysły ⚠ (interpretacja). `open` na końcu.

## Profil A — progi częstotliwości (D-2026-06-13-01)
- **Klaster „potwierdzony" = ≥4 niezależne sygnały z ≥3 kanałów.** Poniżej → „⚠ anegdota, do potwierdzenia", zero decyzji biznesowych na tym.
- **Niezależny sygnał** = osobny autor (dedup po autorze gdzie jest ID: Reddit/Wykop/YouTube; inaczej po treści). 5 komentarzy jednej osoby = 1.
- **Częstotliwość ≠ rezonans:** score/lajki to modyfikator pewności, NIGDY liczba sygnałów.
- **Werdykt niszy** na CZYSTYCH sygnałach (po sędzim): silny ≥20 / umiarkowany ≥10 / słaby <10.

## Kanały (rejestr `CHANNELS` w bin/dossier-niszy.py — jedno źródło prawdy)
Wykop · Reddit · YouTube · Google Play (dobór apek przez SerpApi) · App Store · Facebook (wiele grup, Apify płatny). Tryb pojedynczego kanału (dla agentów):
```bash
~/.claude/skills/dossier-niszy/bin/dossier-niszy.py --kanal "<nazwa>" --nisza "<q>" --klucze "…" --frazy "…" --limit N --out-file /tmp/x.json
```
Limity per kanał: `N_APPS`, `N_FB_GROUPS`, `N_YT_VIDEOS` (domyślne, nadpisywalne). `--gleboki` = próbka 40/200 dla pełnego przejazdu jednym strzałem (alternatywa do Workflow).

## Koszt
Zwiad: kilka–kilkanaście zapytań (tanio). Drążenie (Workflow): zależne od liczby kanałów × limit; równolegli agenci. FB/Apify = płatny (świadomie). Reguła: drąż tylko kanały z sygnałem (po zwiadzie).

## Stan
v5 — 13.06.2026. **Przebudowa na sekwencyjny + agentowy** (D-2026-06-13-02): ETAP zwiad → wybór → drążenie agentami (Workflow `workflow-v5.js`) → jeden sędzia → pomysły. Zdjęte zaszyte limity (FB 1 grupa, Google Play regex→SerpApi, YouTube/App Store skalują), limity ustala user (faza 2). Reddit dodany jako natywny kanał. Zachowane: konstytucja niszy (etap 0), sędzia trafności, próg profilu A (≥4 z ≥3 kanałów, częstotliwość≠rezonans — D-01). Wcześniej: v4 (próg częstotliwości), v3 (konstytucja + sędzia po walidacji ground truth), v2 (proces fazowy, analiza = model nie DeepSeek).
