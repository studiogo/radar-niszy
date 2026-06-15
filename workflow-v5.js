export const meta = {
  name: 'dossier-niszy-v5',
  description: 'Drążenie niszy: równolegli agenci per kanał → JEDEN sędzia trafności (wg konstytucji + profil A) → pomysły. Wejście: nisza + konstytucja + wybrane kanały/limity (po zwiadzie).',
  phases: [
    { title: 'Drążenie', detail: 'agent per kanał: zbiera (--kanal) + dedup po autorze + wstępny tag' },
    { title: 'Sędzia', detail: 'jeden spójny przebieg: trafność wg konstytucji + klastry wg progu profilu A' },
    { title: 'Pomysły', detail: 'pod potwierdzone klastry → pomysły + ocena founder-fit' },
  ],
}

// ---- Wejście (args) ----
// { nisza, konstytucja:{odbiorca,bol,szum}, kanaly:[{nazwa,limit}], klucze:"csv", frazy:"a;b;c" }
let A = args || {}
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
const nisza = A.nisza
const konst = A.konstytucja || {}
const kanaly = Array.isArray(A.kanaly) ? A.kanaly : []
const klucze = A.klucze || ''
const frazy = A.frazy || ''
if (!nisza || !kanaly.length) {
  throw new Error('Workflow v5 wymaga args: { nisza, konstytucja, kanaly:[{nazwa,limit}], klucze, frazy }')
}

const KONST = `KONSTYTUCJA NISZY (wzorzec oceny — trzymaj się jej ściśle):
- ODBIORCA (kto ma ból): ${konst.odbiorca || '(niezdefiniowany)'}
- REALNY BÓL (co się liczy): ${konst.bol || '(wyrażony problem/frustracja/potrzeba/pytanie odbiorcy)'}
- SZUM (co odrzucamy): ${konst.szum || 'wzmianka bez bólu, zła perspektywa, emocja-bez-treści, off-topic, polityka, żart, bot, homonim'}`

const CHANNEL_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    kanal: { type: 'string' },
    surowe: { type: 'integer' },
    po_dedup: { type: 'integer' },
    pokrycie: { type: 'string', description: 'ile realnie przeszukano (źródeł/wątków/postów)' },
    sygnaly: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          cytat: { type: 'string', description: 'parafraza/skrót sygnału (RODO: bez nazwisk)' },
          autor: { type: ['string', 'null'] },
          tag: { type: 'string', enum: ['bol_odbiorcy', 'watpliwy', 'szum'] },
          podbol: { type: 'string', description: 'krótka etykieta pod-bólu (np. "znaleźć cel", "utrzymać egzekucję")' },
        },
        required: ['cytat', 'tag', 'podbol'],
      },
    },
  },
  required: ['kanal', 'sygnaly', 'pokrycie'],
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    czyste_sygnaly: { type: 'integer', description: 'liczba niezależnych sygnałów-bólów po odsianiu szumu' },
    klastry: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          nazwa: { type: 'string' },
          sygnaly_niezalezne: { type: 'integer' },
          kanaly: { type: 'array', items: { type: 'string' } },
          status: { type: 'string', enum: ['potwierdzony', 'anegdota'] },
          intensywnosc: { type: 'string', enum: ['wysoka', 'srednia', 'niska'] },
          cytaty: { type: 'array', items: { type: 'string' } },
        },
        required: ['nazwa', 'sygnaly_niezalezne', 'kanaly', 'status', 'cytaty'],
      },
    },
    werdykt: { type: 'string', enum: ['silny', 'umiarkowany', 'slaby'] },
    uzasadnienie: { type: 'string' },
  },
  required: ['czyste_sygnaly', 'klastry', 'werdykt', 'uzasadnienie'],
}

const IDEAS_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    pomysly: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          nazwa: { type: 'string' },
          opis: { type: 'string' },
          pod_klaster: { type: 'string' },
          founder_fit: { type: 'string', enum: ['wysoki', 'sredni', 'niski'] },
          czas_do_kasy: { type: 'string' },
          moat: { type: 'string' },
          ryzyko: { type: 'string' },
        },
        required: ['nazwa', 'opis', 'founder_fit'],
      },
    },
    rekomendacja: { type: 'string' },
  },
  required: ['pomysly', 'rekomendacja'],
}

// ---- ETAP 3: DRĄŻENIE — równolegli agenci per kanał ----
phase('Drążenie')
const perChannel = (await parallel(kanaly.map(k => () =>
  agent(
    `Jesteś agentem researchu kanału "${k.nazwa}" dla niszy "${nisza}".

KROK 1 — ZBIERZ (uruchom przez Bash, dokładnie ten skrypt; klucze/frazy dobrane do języka kanału):
~/.claude/skills/dossier-niszy/bin/dossier-niszy.py --kanal "${k.nazwa}" --nisza "${nisza}" --klucze "${k.klucze || klucze}" --frazy "${k.frazy || frazy}" --limit ${k.limit || 40} --out-file /tmp/wf-${k.nazwa.replace(/[^a-zA-Z0-9]/g, '-')}.json
Następnie odczytaj ten plik JSON (pole "sygnaly" = lista {text, src, autor, score?}).

KROK 2 — DEDUP niezależności: scal sygnały tego samego autora (autor gdzie jest, inaczej po treści). Pięć wpisów jednej osoby = 1 sygnał.

KROK 3 — WSTĘPNY TAG każdego sygnału wg konstytucji (to NIE ostateczny werdykt — robi go sędzia):
${KONST}
tag: "bol_odbiorcy" (realny ból odbiorcy), "watpliwy" (niejasne), "szum" (homonim/zła perspektywa/off-topic/żart/polityka/emocja-bez-treści).
podbol: krótka etykieta o co chodzi.

WAŻNE: score/lajki to REZONANS, nie częstotliwość — NIE traktuj wysokiego score jako wielu sygnałów. Cytaty parafrazuj (RODO, bez nazwisk).
Zwróć strukturę: kanal, surowe (ile z JSON), po_dedup, pokrycie (ile realnie przeszukano), sygnaly[].`,
    { schema: CHANNEL_SCHEMA, label: `drąż:${k.nazwa}`, phase: 'Drążenie', agentType: 'general-purpose' }
  )
))).filter(Boolean)

// ---- ETAP 4: JEDEN SĘDZIA ----
phase('Sędzia')
const wsad = perChannel.map(c => `### Kanał ${c.kanal} (surowe ${c.surowe ?? '?'}, po_dedup ${c.po_dedup ?? '?'}, pokrycie: ${c.pokrycie || '?'})
${(c.sygnaly || []).map(s => `- [${s.tag}/${s.podbol}] ${s.cytat}${s.autor ? ' — @' + s.autor : ''}`).join('\n')}`).join('\n\n')

const klastry = await agent(
  `Jesteś JEDYNYM sędzią trafności dla niszy "${nisza}". Agenci kanałowe zebrały i wstępnie otagowały sygnały — Ty wydajesz spójny, ostateczny werdykt wg JEDNEJ konstytucji (inaczej oceny się rozjeżdżają).

${KONST}

ZASADY (profil A — rygorystyczny, D-2026-06-13):
1. Odrzuć szum wg konstytucji (homonim, zła perspektywa, emocja-bez-treści, off-topic, polityka, żart, bot). Zostaje wyłącznie wyrażony BÓL ODBIORCY.
2. CZĘSTOTLIWOŚĆ ≠ REZONANS: licz niezależne sygnały (różni autorzy/źródła). Score/lajki to rezonans — opisz jako kontekst, NIGDY jako liczbę sygnałów.
3. Klaster "potwierdzony" = ≥4 niezależne sygnały z ≥3 kanałów. Poniżej progu → status "anegdota". Bądź bezwzględny.
4. WERDYKT niszy na CZYSTYCH sygnałach: silny ≥20 / umiarkowany ≥10 / słaby <10.

SYGNAŁY ZEBRANE:
${wsad}

Zwróć: czyste_sygnaly (liczba), klastry (nazwa, sygnaly_niezalezne, kanaly[], status, intensywnosc, cytaty[]), werdykt, uzasadnienie (z liczbami).`,
  { schema: VERDICT_SCHEMA, label: 'sędzia trafności', phase: 'Sędzia', agentType: 'general-purpose' }
)

// ---- ETAP 5: POMYSŁY ----
phase('Pomysły')
const potwierdzone = (klastry.klastry || []).filter(k => k.status === 'potwierdzony')
const ideas = await agent(
  `Nisza "${nisza}". Werdykt: ${klastry.werdykt}. Potwierdzone klastry bólu (status=potwierdzony):
${potwierdzone.map(k => `- ${k.nazwa} (${k.sygnaly_niezalezne} sygnałów, kanały: ${k.kanaly.join(', ')})`).join('\n') || '(brak potwierdzonych — oprzyj się na najmocniejszych anegdotach, ale zaznacz niepewność)'}

Profil Łukasza: marketingowiec + automatyzacje (Make/n8n/AI) + edukacja (newsletter ~400, podcast), buduje SaaS, NIE programista. Marka "Ogarniam AI".
Pod 2-3 najmocniejsze klastry zaproponuj konkretne pomysły na produkt/usługę (NIE pisanie softu od zera — automatyzacje, AI, edukacja, usługa). Każdy: opis, pod_klaster, founder_fit, czas_do_kasy, moat, ryzyko. Na końcu rekomendacja (który tor + dlaczego). Oznacz że pomysły to interpretacja (⚠), bóle to fakty.`,
  { schema: IDEAS_SCHEMA, label: 'pomysły + ocena', phase: 'Pomysły', agentType: 'general-purpose' }
)

return {
  nisza,
  drazenie: perChannel.map(c => ({ kanal: c.kanal, surowe: c.surowe, po_dedup: c.po_dedup, pokrycie: c.pokrycie, sygnaly: (c.sygnaly || []).length })),
  werdykt: klastry.werdykt,
  czyste_sygnaly: klastry.czyste_sygnaly,
  klastry: klastry.klastry,
  uzasadnienie: klastry.uzasadnienie,
  pomysly: ideas.pomysly,
  rekomendacja: ideas.rekomendacja,
}
