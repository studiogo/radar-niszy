#!/usr/bin/env python3
"""
render_raport.py — raport „Dossier niszy" jako SAMODZIELNY HTML (wg designu Claude Design).

Odtworzenie prototypu x-dc (Dossier niszy.dc.html) jako 1 plik HTML bez frameworka —
zasilany danymi z pipeline'u skilla. Ikony marek: resources/icons.json (real brand SVG).
Wiersz w sekcji źródeł = jeden kafelek → grid rośnie sam, gdy dokładamy kanały.

Wejście: JSON z agregatem (--data) ALBO --demo (przykład z designu).
Kształt JSON:
{
 "meta": {"niche": "...", "date": "14.06.2026", "glebokosc": 3},
 "verdict": {"key": "TAK|TROCHE|NIE", "sentence": "...", "score": 82},
 "facts": [{"value":"37","label":"...","good":false}, ...],
 "clusters": [{"name":"...","signals":12,"channels":4,"isNew":false,
               "quotes":[{"text":"...","source":"Reddit"}]}],
 "recommendation": {"title":"...","body":"..."},
 "ideas": [{"text":"..."}],
 "sources": [{"name":"Reddit","icon":"reddit","people":11,"skip":false}, ...]
}

Użycie:
  render_raport.py --demo --open
  render_raport.py --data /tmp/agg.json --out-file /tmp/raport.html --open
"""
try:  # Windows: konsola bywa cp1250 — wymuś UTF-8, by emoji w wyjściu nie wywalały printów
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8"); _s.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse, html, json, os, subprocess, sys, tempfile
from pathlib import Path


def _open_file(path):
    """Otwórz plik domyślną aplikacją — cross-platform (mac/Windows/Linux)."""
    p = str(path)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", p])
        elif sys.platform.startswith("win"):
            os.startfile(p)  # Windows-only
        else:
            subprocess.run(["xdg-open", p])
    except Exception:
        pass

ICONS = json.loads((Path(__file__).parent.parent / "resources" / "icons.json").read_text(encoding="utf-8"))
G, B = "#15A150", "#2F6BFF"
VERDICTS = {
    "TAK":    {"dot": "🟢", "headline": "Tak, jest problem",  "grad": "linear-gradient(135deg,#16A34A,#10B981)", "shadow": "rgba(16,163,74,0.32)"},
    "TROCHE": {"dot": "🟡", "headline": "Trochę, ale słabo",  "grad": "linear-gradient(135deg,#E08A0B,#F2B43C)", "shadow": "rgba(224,138,11,0.32)"},
    "NIE":    {"dot": "🔴", "headline": "Nie, raczej nie ma", "grad": "linear-gradient(135deg,#E5484D,#F2766F)", "shadow": "rgba(229,72,77,0.32)"},
}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def _lerp(a, b, t):
    pa = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(pa[i]+(pb[i]-pa[i])*t):02x}" for i in range(3))


def gauge_svg(score):
    n = 19
    filled = round(score / 100 * n)
    if score >= 67:
        lo, hi, word, wc, wb = "#0B8F45", "#5FE09A", "Mocny", "#0F8C45", "#E7F6EC"
    elif score >= 34:
        lo, hi, word, wc, wb = "#C77A06", "#F3C25A", "Średni", "#B5710A", "#FCF2DD"
    else:
        lo, hi, word, wc, wb = "#C9343A", "#F2877F", "Słaby", "#C9343A", "#FCEBEC"
    rects = []
    for i in range(n):
        deg = (i / (n - 1)) * 180 - 90
        on = i < filled
        t = i / (filled - 1) if filled > 1 else 0
        fill = _lerp(lo, hi, t) if on else "#E6E9EE"
        rects.append(f'<rect x="132" y="18" width="16" height="42" rx="8" fill="{fill}" transform="rotate({deg:.2f} 140 150)"></rect>')
    return "".join(rects), word, wc, wb


def icon_svg(key):
    ic = ICONS.get(key) or ICONS.get("web")
    return f'<svg width="22" height="22" viewBox="0 0 24 24" fill="{ic["color"]}"><path d="{ic["d"]}"></path></svg>'


def tip(text):
    """Tooltip „i" na hover (czysty CSS)."""
    return (f'<span class="gr-tip"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#A2A9B4" '
            f'stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 16v-4M12 8h.01"></path></svg>'
            f'<span class="gr-tip-box">{esc(text)}</span></span>')


def render(d):
    m = d["meta"]; v = d["verdict"]
    vd = VERDICTS.get(v.get("key", "TAK"), VERDICTS["TAK"])
    g_rects, g_word, g_wc, g_wb = gauge_svg(int(v.get("score", 0)))

    facts = "".join(
        f'<div class="gr-card" style="padding:24px;"><div style="font-size:34px;font-weight:800;letter-spacing:-0.02em;'
        f'color:{G if f.get("good") else "#14171C"};line-height:1;">{esc(f["value"])}</div>'
        f'<div style="margin-top:10px;font-size:15px;color:#4B515C;line-height:1.4;">{esc(f["label"])}</div></div>'
        for f in d["facts"])

    clusters = ""
    for i, c in enumerate(d["clusters"]):
        many = c["signals"] >= 4 and c["channels"] >= 3
        dot = G if many else "#E8A33D"
        slabel = "Dużo osób mówi to samo" if many else "Tylko kilka osób — mniej pewne"
        sfg, sbg = ("#0F8C45", "#E7F6EC") if many else ("#B5710A", "#FCF2DD")
        border = "rgba(18,161,80,0.18)" if many else "rgba(16,24,40,0.06)"
        newbadge = ('<span style="position:absolute;top:-10px;right:20px;background:#2F6BFF;color:#fff;font-size:12px;'
                    'font-weight:700;padding:5px 11px;border-radius:8px;box-shadow:0 4px 10px rgba(47,107,255,0.35);">Nowe</span>') if c.get("isNew") else ""
        quotes = "".join(
            f'<div style="background:#F0FAF3;border:1px solid rgba(18,161,80,0.18);border-radius:14px;padding:15px 17px;">'
            f'<div style="font-size:15px;line-height:1.5;color:#1B2430;">„{esc(q["text"])}”</div>'
            f'<div style="margin-top:10px;font-size:13px;color:#8A92A0;font-weight:600;">{esc(q["source"])}</div></div>'
            for q in c["quotes"])
        open_first = i == 0
        clusters += f'''<div class="gr-card" style="padding:26px;position:relative;border-color:{border};">{newbadge}
      <div style="display:inline-flex;align-items:center;gap:8px;background:{sbg};color:{sfg};border-radius:999px;padding:7px 14px;font-size:14px;font-weight:700;">
        <span style="width:9px;height:9px;border-radius:50%;background:{dot};display:inline-block;"></span>{slabel}</div>
      <h4 style="margin:16px 0 0;font-size:21px;font-weight:700;letter-spacing:-0.01em;line-height:1.3;">„{esc(c["name"])}”</h4>
      <p style="margin:12px 0 0;font-size:15px;color:#6B7280;">Tak mówi <b style="color:#14171C;">{c["signals"]} osób</b> w internecie.</p>
      <button class="dd-noprint gr-toggle" data-t="cl{i}" style="margin-top:18px;width:100%;display:flex;align-items:center;justify-content:center;gap:8px;background:#F4F6F9;border:1px solid rgba(16,24,40,0.06);border-radius:14px;padding:13px;font-family:'Manrope',sans-serif;font-size:14px;font-weight:600;color:#3B4250;cursor:pointer;">{'Ukryj wypowiedzi ▲' if open_first else 'Zobacz, co napisali ▼'}</button>
      <div id="cl{i}" class="gr-quotes" style="margin-top:14px;flex-direction:column;gap:11px;display:{'flex' if open_first else 'none'};">{quotes}</div>
    </div>'''

    ideas = "".join(
        f'<div class="gr-card" style="padding:22px;"><div style="font-size:13.5px;color:#8A92A0;font-weight:700;">Inny pomysł</div>'
        f'<p style="margin:9px 0 0;font-size:15.5px;line-height:1.5;color:#2A323E;font-weight:600;">{esc(i["text"])}</p></div>'
        for i in d["ideas"])

    maxp = max([s["people"] for s in d["sources"]] + [1])
    sources = ""
    for s in d["sources"]:
        skip = s.get("skip") or s["people"] == 0
        pct = 0 if skip else round(s["people"] / maxp * 100)
        bar = "#D5D9E0" if skip else B
        label = "Pominięte" if skip else f'{s["people"]} sygnałów'
        sources += f'''<div style="background:{'#F4F6F9' if skip else '#fff'};border:1px solid rgba(16,24,40,0.06);border-radius:20px;padding:20px;box-shadow:0 1px 2px rgba(16,24,40,0.04);opacity:{0.7 if skip else 1};">
        <div style="display:flex;align-items:center;gap:11px;"><span style="width:40px;height:40px;border-radius:11px;background:#F1F3F6;display:flex;align-items:center;justify-content:center;">{icon_svg(s.get("icon"))}</span><span style="font-size:16px;font-weight:700;">{esc(s["name"])}</span></div>
        <div style="margin-top:18px;height:10px;border-radius:999px;background:#EDEFF3;overflow:hidden;"><div style="height:100%;width:{pct}%;background:{bar};border-radius:999px;"></div></div>
        <div style="margin-top:10px;font-size:13.5px;color:#8A92A0;font-weight:600;">{esc(label)}</div></div>'''

    rec = d["recommendation"]
    return f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossier niszy — {esc(m["niche"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;}} body{{margin:0;}}
.gr-card{{background:#fff;border:1px solid rgba(16,24,40,0.06);border-radius:22px;box-shadow:0 1px 2px rgba(16,24,40,0.04),0 8px 22px rgba(16,24,40,0.05);}}
.gr-tip{{position:relative;display:inline-flex;align-items:center;cursor:help;}}
.gr-tip-box{{position:absolute;bottom:140%;left:0;width:255px;background:#14171C;color:#fff;font-size:12.5px;font-weight:500;line-height:1.45;padding:11px 13px;border-radius:12px;box-shadow:0 10px 28px rgba(0,0,0,0.28);z-index:60;opacity:0;visibility:hidden;transition:opacity .15s;}}
.gr-tip:hover .gr-tip-box{{opacity:1;visibility:visible;}}
@media print{{ .dd-noprint{{display:none!important;}} body{{background:#fff!important;}} .gr-quotes{{display:flex!important;}} }}
</style></head>
<body style="background:#EDEFF2;font-family:'Manrope',system-ui,sans-serif;color:#14171C;padding:28px 22px 64px;">
<div style="max-width:1060px;margin:0 auto;display:flex;flex-direction:column;gap:26px;">

  <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="width:42px;height:42px;border-radius:13px;background:linear-gradient(150deg,#2F6BFF,#5B9BFF);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(47,107,255,0.35);">
        <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg></div>
      <div style="display:flex;flex-direction:column;line-height:1.2;"><span style="font-weight:800;font-size:17px;">Dossier niszy</span><span style="font-size:13px;color:#8A92A0;">sprawdzamy, czy pomysł ma sens</span></div></div>
    <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:14px;color:#8A92A0;">głębokość {esc(m.get("glebokosc","?"))}/10 · {esc(m["date"])}</span>
      <button class="dd-noprint" onclick="window.print()" style="display:flex;align-items:center;gap:7px;background:#fff;color:#14171C;border:1px solid rgba(16,24,40,0.10);border-radius:12px;padding:10px 16px;font-family:'Manrope',sans-serif;font-weight:600;font-size:14px;cursor:pointer;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#14171C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M8 7l4-4 4 4"></path><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"></path></svg>Zapisz</button></div></div>

  <div style="padding:2px 2px 0;"><p style="margin:0 0 8px;font-size:15px;color:#8A92A0;font-weight:600;">Pomysł, który sprawdzamy:</p>
    <h1 style="margin:0;font-size:36px;font-weight:800;letter-spacing:-0.025em;line-height:1.08;">{esc(m["niche"])}</h1></div>

  <section style="border-radius:26px;padding:34px;color:#fff;background:{vd["grad"]};box-shadow:0 16px 40px {vd["shadow"]};position:relative;overflow:hidden;display:flex;gap:30px;flex-wrap:wrap;align-items:center;justify-content:space-between;">
    <div style="position:absolute;right:-70px;top:-70px;width:280px;height:280px;border-radius:50%;background:rgba(255,255,255,0.08);"></div>
    <div style="position:relative;z-index:1;flex:1;min-width:330px;"><p style="margin:0;font-size:15px;font-weight:700;opacity:0.9;">Krótka odpowiedź:</p>
      <div style="display:flex;align-items:center;gap:14px;margin-top:14px;flex-wrap:wrap;"><span style="font-size:44px;line-height:1;">{vd["dot"]}</span>
        <h2 style="margin:0;font-size:34px;font-weight:800;letter-spacing:-0.02em;line-height:1.1;">{vd["headline"]}</h2></div>
      <p style="margin:18px 0 0;font-size:18px;line-height:1.5;max-width:560px;opacity:0.97;">{esc(v["sentence"])}</p></div>
    <div style="position:relative;z-index:1;background:#fff;border-radius:22px;padding:22px 24px 18px;box-shadow:0 14px 34px rgba(0,0,0,0.20);width:300px;max-width:100%;color:#14171C;">
      <div style="position:relative;width:248px;max-width:100%;margin:0 auto;"><svg viewBox="0 0 280 178" style="width:100%;display:block;">{g_rects}</svg>
        <div style="position:absolute;left:0;right:0;bottom:14px;text-align:center;"><div style="font-size:42px;font-weight:800;letter-spacing:-0.02em;line-height:1;">{int(v.get("score",0))}%</div>
          <div style="display:inline-flex;align-items:center;gap:5px;margin-top:5px;"><span style="font-size:13px;color:#8A92A0;font-weight:600;">Siła problemu</span>{tip("Im wyższy wynik, tym mocniejszy problem. Liczymy, ilu osobom to przeszkadza i w ilu miejscach o tym piszą.")}</div></div></div>
      <div style="text-align:center;margin-top:8px;"><span style="display:inline-block;background:{g_wb};color:{g_wc};border-radius:999px;padding:6px 16px;font-weight:700;font-size:14px;">{g_word}</span></div></div>
  </section>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;">{facts}</div>

  <div style="padding:14px 2px 0;"><div style="display:flex;align-items:center;gap:10px;"><h3 style="margin:0;font-size:26px;font-weight:800;letter-spacing:-0.02em;">Na co ludzie narzekają</h3>{tip("Zielona kropka znaczy, że narzeka dużo osób w wielu miejscach — problem jest pewny. Żółta znaczy, że głosów jest mało, więc to mniej pewne.")}</div>
    <p style="margin:8px 0 0;font-size:16px;color:#6B7280;">Kliknij „Zobacz, co napisali”, żeby przeczytać prawdziwe wypowiedzi.</p></div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;">{clusters}</div>

  <div style="padding:14px 2px 0;display:flex;align-items:center;gap:12px;flex-wrap:wrap;"><h3 style="margin:0;font-size:26px;font-weight:800;letter-spacing:-0.02em;">Jak można to rozwiązać</h3>
    <span style="display:inline-flex;align-items:center;gap:6px;background:#FCF2DD;color:#B5710A;border-radius:999px;padding:6px 13px;font-size:13.5px;font-weight:700;">💡 to nasz pomysł, nie pewnik</span>{tip("To nasze propozycje rozwiązania — mogą zadziałać, ale to nie pewnik. Cytaty wyżej to prawdziwe wypowiedzi ludzi.")}</div>
  <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:16px;">
    <div style="background:linear-gradient(160deg,#fff,#FBFCFF);border:1.5px solid rgba(47,107,255,0.28);border-radius:22px;padding:28px;box-shadow:0 8px 24px rgba(47,107,255,0.08);">
      <div style="font-size:14px;font-weight:700;color:#2F6BFF;">Najlepszy pomysł</div>
      <h4 style="margin:12px 0 0;font-size:22px;font-weight:800;letter-spacing:-0.015em;line-height:1.2;">{esc(rec["title"])}</h4>
      <p style="margin:14px 0 0;font-size:16px;line-height:1.55;color:#3B4250;">{esc(rec["body"])}</p></div>
    <div style="display:flex;flex-direction:column;gap:16px;">{ideas}</div></div>

  <div style="padding:14px 2px 0;"><div style="display:flex;align-items:center;gap:10px;"><h3 style="margin:0;font-size:26px;font-weight:800;letter-spacing:-0.02em;">Gdzie to sprawdziliśmy</h3>{tip("Pasek pokazuje, ile sygnałów przeskanowaliśmy w danym miejscu. Im dłuższy, tym więcej tam znaleźliśmy.")}</div>
    <p style="margin:8px 0 0;font-size:16px;color:#6B7280;">Przeszukaliśmy {esc(m["channels"])} miejsc w internecie. Każde nowe miejsce to po prostu jeden kafelek.</p></div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;">{sources}</div>

  <p style="text-align:center;font-size:13.5px;color:#9AA1AC;margin:8px 0 0;">{esc(m["niche"])} · sprawdzone {esc(m["date"])} · {esc(m["channels"])} miejsc w internecie</p>
</div>
<script>
document.querySelectorAll('.gr-toggle').forEach(function(b){{b.addEventListener('click',function(){{
  var box=document.getElementById(b.dataset.t); var open=box.style.display!=='none';
  box.style.display=open?'none':'flex'; b.textContent=open?'Zobacz, co napisali ▼':'Ukryj wypowiedzi ▲';}});}});
</script>
</body></html>'''


DEMO = {
    "meta": {"niche": "Narzędzia AI do pisania postów na LinkedIn", "date": "14.06.2026", "glebokosc": 3, "channels": "5"},
    "verdict": {"key": "TAK", "score": 82,
                "sentence": "Ludzie chcą wrzucać posty regularnie, ale ręczne pisanie zabiera za dużo czasu — a kiedy robi to za nich AI, brzmi to sztucznie. Utknęli w środku i to ich naprawdę denerwuje."},
    "facts": [{"value": "37", "label": "osób narzeka na ten problem"},
              {"value": "5", "label": "różnych miejsc w internecie — niezależnie od siebie"},
              {"value": "Rośnie ↑", "label": "coraz więcej osób szuka rozwiązania", "good": True}],
    "clusters": [
        {"name": "AI pisze za mnie, ale brzmi sztucznie", "signals": 12, "channels": 4, "isNew": False, "quotes": [
            {"text": "Wrzuciłem 3 posty z ChatGPT i od razu ktoś napisał „to pisał bot”. Skasowałem je.", "source": "Reddit"},
            {"text": "Każde narzędzie AI brzmi tak samo. Czuję, że tracę swój styl.", "source": "LinkedIn"}]},
        {"name": "Nie daję rady pisać regularnie", "signals": 9, "channels": 3, "isNew": False, "quotes": [
            {"text": "Zaczynam mocno, po dwóch tygodniach znikam. Nie mam na to systemu.", "source": "Reddit"},
            {"text": "Wiem, że trzeba publikować często, ale nie mam na to godziny dziennie.", "source": "YouTube"}]},
        {"name": "Boję się, że stracę swój styl", "signals": 7, "channels": 3, "isNew": False, "quotes": [
            {"text": "Im więcej oddaję AI, tym mniej to brzmi jak ja. To pułapka.", "source": "LinkedIn"}]},
        {"name": "Nie wiem, o czym pisać", "signals": 4, "channels": 2, "isNew": True, "quotes": [
            {"text": "Pisanie to nie problem. Problem to o czym pisać piąty dzień z rzędu.", "source": "YouTube"}]},
    ],
    "recommendation": {"title": "Pomocnik, który uczy się Twojego stylu",
                       "body": "Program czyta 10 Twoich starych postów i podpowiada szkice w Twoim stylu — nie gotowce do skopiowania, tylko punkt startu, który brzmi jak Ty. Załatwia od razu dwie rzeczy: „za wolno” i „brzmi sztucznie”."},
    "ideas": [{"text": "Zbiór Twoich własnych zdań i historii — program miesza to, co już powiedziałeś, zamiast pisać od zera."},
              {"text": "Podpowiadacz tematów z Twojej branży — celuje w „nie wiem, o czym pisać”."}],
    "sources": [{"name": "Reddit", "icon": "reddit", "people": 11}, {"name": "Wykop", "icon": "wykop", "people": 9},
                {"name": "YouTube", "icon": "youtube", "people": 7}, {"name": "Opinie z apek", "icon": "reviews", "people": 6},
                {"name": "Google Maps", "icon": "google_maps", "people": 4}, {"name": "Facebook", "icon": "facebook", "people": 8},
                {"name": "App Store", "icon": "app_store", "people": 0, "skip": True}],
}


def main():
    ap = argparse.ArgumentParser(description="Raport Dossier niszy → samodzielny HTML")
    ap.add_argument("--data", help="JSON z agregatem")
    ap.add_argument("--demo", action="store_true", help="przykład z designu")
    ap.add_argument("--out-file", default=str(Path(tempfile.gettempdir()) / "dossier-raport.html"))
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    if a.data:
        d = json.loads(Path(a.data).read_text(encoding="utf-8"))
    elif a.demo:
        d = DEMO
    else:
        print("podaj --data <json> albo --demo", file=sys.stderr); sys.exit(2)
    Path(a.out_file).write_text(render(d), encoding="utf-8")
    print(a.out_file)
    if a.open:
        _open_file(a.out_file)


if __name__ == "__main__":
    main()
