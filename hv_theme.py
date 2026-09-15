"""Visual identity.

The look is built from the subject's own materials: a film shadow's
green-shifted charcoal, poster-condensed display type, and monospaced
production-paperwork metadata (call sheets and shot lists are monospaced,
so every label, runtime and aspect ratio on this site is too).

Committed single visual world -- a cinema is dark -- so every colour is
painted explicitly rather than inherited from the host theme.
"""
from __future__ import annotations

from hv_theme_extra import EXTRA


def _rgb(h: str, fallback=(87, 200, 176)) -> tuple[int, int, int]:
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except Exception:
        return fallback


GRAIN = (
    "data:image/svg+xml;charset=utf-8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='320'%3E"
    "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9'"
    " numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E"
    "%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.4'/%3E%3C/svg%3E"
)

FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Big+Shoulders+Display:wght@500;700;800;900"
    "&family=IBM+Plex+Mono:wght@400;500;600"
    "&family=IBM+Plex+Sans:wght@300;400;500;600"
    "&family=Newsreader:ital,opsz,wght@1,6..72,300;1,6..72,400"
    "&display=swap"
)


def css(accent: str = "#57C8B0", warm: str = "#E4813F", grain: bool = True) -> str:
    ar, ag, ab = _rgb(accent)
    wr, wg, wb = _rgb(warm, (228, 129, 63))
    grain_display = "block" if grain else "none"
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>
@import url('{FONTS}');
:root {{
  --ink:      #101211;
  --ink-2:    #171A18;
  --ink-3:    #202421;
  --ink-4:    #2B302C;
  --line:     rgba(233,231,223,.14);
  --line-soft:rgba(233,231,223,.07);
  --paper:    #E9E7DF;
  --paper-2:  rgba(233,231,223,.66);
  --paper-3:  rgba(233,231,223,.38);
  --accent:   {accent};
  --accent-rgb: {ar},{ag},{ab};
  --warm:     {warm};
  --warm-rgb: {wr},{wg},{wb};

  --display: 'Big Shoulders Display', 'Haettenschweiler', 'Arial Narrow', sans-serif;
  --mono:    'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace;
  --sans:    'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --quote:   'Newsreader', Georgia, 'Times New Roman', serif;

  --gut:  clamp(18px, 4.6vw, 84px);
  --rail: clamp(0px, 13vw, 190px);
}}

/* ============ Streamlit chrome ============ */
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stDecoration"] {{ display:none !important; }}
[data-testid="stHeader"] {{ background:transparent !important; height:0 !important; }}
[data-testid="stToolbar"] {{ right:8px; top:6px; opacity:.2; }}
[data-testid="stToolbar"]:hover {{ opacity:1; }}
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMainBlockContainer"], .block-container {{ padding:0 !important; max-width:100% !important; }}
[data-testid="stVerticalBlock"] {{ gap:0 !important; }}

html {{ scroll-behavior:smooth; }}
body, .stApp, [data-testid="stAppViewContainer"] {{
  background: var(--ink);
  color: var(--paper);
  font-family: var(--sans);
  font-weight: 300;
  -webkit-font-smoothing: antialiased;
}}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}
::selection {{ background: var(--accent); color: var(--ink); }}
::-webkit-scrollbar {{ width:8px; height:8px; }}
::-webkit-scrollbar-track {{ background: var(--ink); }}
::-webkit-scrollbar-thumb {{ background: var(--ink-4); }}
::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}

/* ============ grain ============ */
.stApp::after {{
  content:''; position:fixed; inset:-220px; z-index:9998; pointer-events:none;
  display: {grain_display};
  background-image: url("{GRAIN}");
  opacity:.045; mix-blend-mode: overlay;
  animation: hv-grain 720ms steps(3) infinite;
}}
@keyframes hv-grain {{
  0%{{transform:translate(0,0)}} 33%{{transform:translate(-13px,8px)}}
  66%{{transform:translate(10px,-11px)}} 100%{{transform:translate(0,0)}}
}}

/* ============ motion ============ */
.hv-in {{ animation: hv-fade .8s cubic-bezier(.16,1,.3,1) both; }}
@keyframes hv-fade {{ from{{opacity:0;transform:translateY(16px)}} to{{opacity:1;transform:none}} }}
.hv-rise {{ opacity:1; }}
@supports (animation-timeline: view()) {{
  @media (prefers-reduced-motion: no-preference) {{
    .hv-rise {{ animation: hv-rise-kf linear both; animation-timeline: view(); animation-range: entry 0% cover 22%; }}
  }}
}}
@keyframes hv-rise-kf {{ from{{opacity:.15; transform:translateY(26px)}} to{{opacity:1;transform:none}} }}
@media (prefers-reduced-motion: reduce) {{
  .stApp::after {{ animation:none; }}
  html {{ scroll-behavior:auto; }}
  .hv-in {{ animation:none; }}
}}

/* ============ type primitives ============ */
.hv-mono {{
  font-family: var(--mono); font-size: 10.5px; font-weight: 500;
  letter-spacing: .18em; text-transform: uppercase; color: var(--paper-3);
  font-variant-numeric: tabular-nums;
}}
.hv-h2 {{
  font-family: var(--display); font-weight: 800;
  font-size: clamp(40px, 8.4vw, 118px); line-height: .86;
  letter-spacing: -.005em; text-transform: uppercase;
  margin: 0 0 clamp(24px,3vw,46px); color: var(--paper); text-wrap: balance;
}}
.hv-h2 em {{
  font-family: var(--quote); font-style: italic; font-weight: 300;
  text-transform: none; font-size: .62em; letter-spacing: -.01em; color: var(--accent);
}}
.hv-p {{
  font-size: clamp(14.5px,1.05vw,16.5px); line-height: 1.78;
  color: var(--paper-2); max-width: 64ch; margin: 0 0 16px; font-weight: 300;
}}

/* ============ section shell (slate rail + content) ============ */
.hv-section {{ padding-block: clamp(62px,9vw,132px); position: relative; }}
.hv-section + .hv-section {{ border-top: 1px solid var(--line-soft); }}
.hv-wrap {{ padding-inline: var(--gut); }}
.hv-cols {{ display: grid; grid-template-columns: var(--rail) minmax(0,1fr); gap: clamp(0px,2.4vw,40px); }}
@media (max-width: 860px) {{ .hv-cols {{ grid-template-columns: 1fr; gap: 18px; }} }}

.hv-slate {{ position: sticky; top: 22px; align-self: start; }}
.hv-slate-reel {{
  font-family: var(--mono); font-size: 10.5px; font-weight:600; letter-spacing:.2em;
  text-transform: uppercase; color: var(--accent); font-variant-numeric: tabular-nums;
  padding-bottom: 9px; margin-bottom: 9px; border-bottom: 1px solid var(--line);
}}
.hv-slate-k {{
  font-family: var(--mono); font-size: 10px; letter-spacing:.16em; text-transform:uppercase;
  color: var(--paper-3); line-height: 1.95; font-variant-numeric: tabular-nums;
}}
@media (max-width: 860px) {{
  .hv-slate {{ position:static; display:flex; gap:16px; flex-wrap:wrap; align-items:baseline; }}
  .hv-slate-reel {{ border:0; padding:0; margin:0; }}
}}

/* ============ hero ============ */
.hv-hero {{
  min-height: 84svh; display:flex; flex-direction:column; justify-content:flex-end;
  position:relative; overflow:hidden;
  padding: clamp(62px,7vw,96px) var(--gut) clamp(22px,2.8vw,38px);
}}
.hv-hero-bg {{ position:absolute; inset:0; z-index:0; }}
.hv-hero-bg img, .hv-hero-bg video {{
  width:100%; height:100%; object-fit:cover;
  filter: grayscale(.45) contrast(1.12) brightness(.62) sepia(.1);
  transform: scale(1.05); animation: hv-kb 30s ease-in-out infinite alternate;
}}
@keyframes hv-kb {{ from{{transform:scale(1.03)}} to{{transform:scale(1.12) translateY(-1.5%)}} }}
.hv-hero-bg::after {{
  content:''; position:absolute; inset:0;
  background:
    radial-gradient(130% 90% at 12% 105%, rgba(var(--accent-rgb),.18), transparent 52%),
    linear-gradient(to top, var(--ink) 0%, rgba(16,18,17,.46) 48%, rgba(16,18,17,.66) 100%);
}}
.hv-hero-top {{
  position:absolute; top: clamp(20px,3vw,34px); left:var(--gut); right:var(--gut); z-index:3;
  display:flex; justify-content:space-between; gap:14px; flex-wrap:wrap;
  padding-bottom: 11px; border-bottom: 1px solid var(--line);
}}
.hv-hero-inner {{ position:relative; z-index:2; width:100%; }}
.hv-name {{
  font-family: var(--display); font-weight:900;
  font-size: clamp(34px, 7.4vw, 112px); line-height:.9;
  letter-spacing:-.008em; text-transform:uppercase;
  margin:0 0 clamp(14px,1.6vw,22px); color: var(--paper);
}}
.hv-name > span {{ display:block; white-space:nowrap; }}
.hv-name .hollow {{
  color: transparent; -webkit-text-stroke: 1.1px rgba(233,231,223,.72);
  text-stroke: 1.1px rgba(233,231,223,.72);
}}
.hv-name .dot {{ display:inline; -webkit-text-stroke:0; text-stroke:0; color: var(--accent); }}
@supports not (-webkit-text-stroke: 1px black) {{
  .hv-name .hollow {{ color: rgba(233,231,223,.42); }}
}}
.hv-tagline {{
  font-family: var(--quote); font-style:italic; font-weight:300;
  font-size: clamp(18px,2.2vw,32px); line-height:1.34; color: var(--paper);
  max-width: 24ch; margin: 0 0 clamp(20px,2.6vw,34px);
}}
.hv-strip-meta {{
  display:flex; flex-wrap:wrap; gap: clamp(16px,3.4vw,48px); align-items:flex-end;
  border-top:1px solid var(--line); padding-top:16px;
}}
.hv-mk {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.2em; text-transform:uppercase; color:var(--paper-3); margin-bottom:6px; }}
.hv-mv {{ font-size:14px; color:var(--paper); font-weight:400; }}
.hv-dot {{
  display:inline-block; width:6px; height:6px; border-radius:50%;
  background: var(--warm); margin-right:8px; box-shadow:0 0 0 0 rgba(var(--warm-rgb),.65);
  animation: hv-pulse 2.4s infinite;
}}
@keyframes hv-pulse {{ 70%{{box-shadow:0 0 0 8px rgba(var(--warm-rgb),0)}} 100%{{box-shadow:0 0 0 0 rgba(var(--warm-rgb),0)}} }}

/* ============ marquee ============ */
.hv-marquee {{
  overflow:hidden; border-block:1px solid var(--line); background: var(--ink-2);
  padding-block: clamp(9px,1.1vw,15px); white-space:nowrap;
}}
.hv-marquee-track {{ display:inline-flex; animation: hv-scrollx 38s linear infinite; }}
.hv-marquee:hover .hv-marquee-track, .hv-marquee:focus-within .hv-marquee-track {{ animation-play-state:paused; }}
.hv-marquee-track span {{
  font-family: var(--display); font-weight:700; text-transform:uppercase;
  font-size: clamp(19px,2.8vw,42px); color: var(--paper);
  padding-inline: clamp(14px,2vw,28px); display:inline-flex; align-items:center;
  gap: clamp(14px,2vw,28px);
}}
.hv-marquee-track span::after {{ content:'/'; color: var(--accent); font-weight:500; }}
.hv-marquee-track span:nth-child(3n+2) {{ color:transparent; -webkit-text-stroke:1px rgba(233,231,223,.42); }}
@keyframes hv-scrollx {{ to{{transform:translateX(-50%)}} }}

/* ============ contact sheet (work grid) ============ */
.hv-grid {{
  display:grid; gap: clamp(10px,1.1vw,18px); align-items: stretch;
  grid-template-columns: repeat(auto-fill, minmax(min(100%,280px),1fr));
}}
.hv-card {{
  display:flex; flex-direction:column; text-decoration:none; color:inherit;
  border:1px solid var(--line); background: var(--ink-2);
  transition: border-color .4s, transform .5s cubic-bezier(.16,1,.3,1);
}}
.hv-card.wide {{ grid-column: span 2; }}
@media (max-width:780px) {{ .hv-card.wide {{ grid-column: span 1; }} }}
.hv-card:hover {{ border-color: rgba(var(--accent-rgb),.7); transform: translateY(-3px); }}
.hv-frame {{
  position:relative; overflow:hidden; background: var(--ink-3);
  flex: 1 1 auto; min-height: clamp(190px, 21vw, 300px);
}}
.hv-card-body {{ flex: 0 0 auto; }}
.hv-frame img {{
  width:100%; height:100%; object-fit:cover; display:block;
  filter: grayscale(.66) contrast(1.05) brightness(.76);
  transition: transform .85s cubic-bezier(.16,1,.3,1), filter .55s;
}}
.hv-card:hover .hv-frame img {{ transform:scale(1.05); filter:grayscale(0) brightness(.94); }}
.hv-frame-empty {{
  position:absolute; inset:0; display:grid; place-items:center;
  background: repeating-linear-gradient(135deg, rgba(233,231,223,.03) 0 1px, transparent 1px 8px);
  font-family: var(--display); font-weight:900; font-size: clamp(36px,5vw,72px);
  color: rgba(233,231,223,.08);
}}
.hv-sprocket {{
  position:absolute; top:0; bottom:0; left:0; width:13px; z-index:2;
  background: repeating-linear-gradient(to bottom, transparent 0 7px, rgba(16,18,17,.85) 7px 15px);
  border-right:1px solid rgba(16,18,17,.6);
}}
.hv-slateno {{
  position:absolute; top:9px; right:10px; z-index:3;
  font-family: var(--mono); font-size:9.5px; font-weight:600; letter-spacing:.14em;
  color: var(--paper); background: rgba(16,18,17,.74); padding:3px 6px;
  backdrop-filter: blur(3px); font-variant-numeric: tabular-nums;
}}
.hv-statusflag {{
  position:absolute; bottom:9px; left:22px; z-index:3;
  font-family: var(--mono); font-size:9px; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; color: var(--ink); background: var(--warm); padding:3px 7px;
}}
.hv-card-body {{ padding: clamp(12px,1.2vw,17px); border-top:1px solid var(--line); }}
.hv-card-title {{
  font-family: var(--display); font-weight:800; text-transform:uppercase;
  font-size: clamp(20px,1.9vw,29px); line-height:.98; margin:0 0 9px; color:var(--paper);
}}
.hv-techstrip {{
  display:flex; flex-wrap:wrap; gap:4px 12px;
  font-family: var(--mono); font-size:9.5px; letter-spacing:.13em; text-transform:uppercase;
  color: var(--paper-3); font-variant-numeric: tabular-nums;
}}
.hv-techstrip b {{ color: var(--accent); font-weight:500; }}
.hv-card-log {{
  font-size:12.5px; line-height:1.62; color: var(--paper-2); margin-top:10px;
  max-height:0; opacity:0; overflow:hidden;
  transition: max-height .5s cubic-bezier(.16,1,.3,1), opacity .35s, margin-top .4s;
}}
.hv-card:hover .hv-card-log, .hv-card:focus-visible .hv-card-log {{ max-height:110px; opacity:1; }}

/* ============ statement ============ */
.hv-quote {{
  font-family: var(--quote); font-style:italic; font-weight:300;
  font-size: clamp(21px,2.9vw,44px); line-height:1.3; color:var(--paper);
  max-width:21ch; margin:0;
}}
.hv-split {{ display:grid; gap: clamp(26px,4vw,68px); grid-template-columns: minmax(0,1.1fr) minmax(0,.85fr); align-items:start; }}
@media (max-width:900px) {{ .hv-split {{ grid-template-columns:1fr; }} }}
.hv-portrait {{ position:relative; }}
.hv-portrait img {{
  width:100%; aspect-ratio:4/5; object-fit:cover; display:block;
  border:1px solid var(--line); filter:grayscale(.6) contrast(1.06) brightness(.85);
  transition: filter .7s;
}}
.hv-portrait:hover img {{ filter:none; }}
.hv-ledger {{ margin-top: clamp(24px,3vw,40px); border-top:1px solid var(--line); }}
.hv-ledger-row {{
  display:flex; justify-content:space-between; align-items:baseline; gap:16px;
  padding: 11px 0; border-bottom:1px solid var(--line-soft);
}}
.hv-ledger-row span {{ font-family:var(--mono); font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:var(--paper-3); }}
.hv-ledger-row b {{ font-family:var(--display); font-weight:800; font-size: clamp(24px,2.6vw,38px); line-height:1; color:var(--paper); font-variant-numeric: tabular-nums; }}

/* ============ timeline ============ */
.hv-tl {{ position:relative; }}
.hv-tl-item {{
  display:grid; grid-template-columns: 92px minmax(0,1fr); gap: clamp(14px,2vw,32px);
  padding: clamp(16px,2vw,26px) 0; border-top:1px solid var(--line);
  transition: background .4s;
}}
.hv-tl-item:hover {{ background: linear-gradient(90deg, rgba(var(--accent-rgb),.05), transparent 40%); }}
.hv-tl-item:last-child {{ border-bottom:1px solid var(--line); }}
@media (max-width:600px) {{ .hv-tl-item {{ grid-template-columns:1fr; gap:8px; }} }}
.hv-tl-year {{
  font-family: var(--display); font-weight:800; font-size: clamp(26px,2.8vw,44px);
  line-height:.9; color: var(--accent); font-variant-numeric: tabular-nums;
}}
.hv-tl-title {{ font-size: clamp(16px,1.3vw,20px); font-weight:500; margin-bottom:6px; color:var(--paper); }}
.hv-tl-body {{ font-size:14px; line-height:1.72; color:var(--paper-2); max-width:60ch; font-weight:300; }}

/* ============ stills ============ */
.hv-gal {{ columns: 3 250px; column-gap: clamp(9px,1.1vw,16px); }}
.hv-gal figure {{ break-inside:avoid; margin:0 0 clamp(9px,1.1vw,16px); position:relative; overflow:hidden; border:1px solid var(--line); }}
.hv-gal img {{ width:100%; display:block; filter:grayscale(.55) brightness(.82); transition: transform .8s cubic-bezier(.16,1,.3,1), filter .5s; }}
.hv-gal figure:hover img {{ transform:scale(1.04); filter:none; }}
.hv-gal figcaption {{
  position:absolute; inset:auto 0 0 0; padding:11px 13px;
  font-family: var(--mono); font-size:9.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--paper); background:linear-gradient(transparent, rgba(16,18,17,.94));
  opacity:0; transform:translateY(6px); transition:.35s;
}}
.hv-gal figure:hover figcaption {{ opacity:1; transform:none; }}

/* ============ press ============ */
.hv-press {{ display:grid; gap: clamp(10px,1.2vw,18px); grid-template-columns: repeat(auto-fit,minmax(min(100%,290px),1fr)); }}
.hv-press-card {{
  border-left:2px solid var(--accent); background: var(--ink-2);
  padding: clamp(18px,2vw,28px); transition: background .4s, transform .45s cubic-bezier(.16,1,.3,1);
}}
.hv-press-card:hover {{ background: var(--ink-3); transform: translateY(-3px); }}
.hv-press-q {{ font-family:var(--quote); font-style:italic; font-weight:300; font-size: clamp(16px,1.4vw,21px); line-height:1.46; margin-bottom:14px; color:var(--paper); }}
.hv-press-s {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.18em; text-transform:uppercase; color:var(--accent); }}

/* ============ guestbook ============ */
.hv-note {{ border:1px solid var(--line); background:var(--ink-2); padding:16px 18px; transition:border-color .35s; }}
.hv-note:hover {{ border-color: rgba(var(--accent-rgb),.45); }}
.hv-note-m {{ font-size:14px; line-height:1.68; color:var(--paper); margin-bottom:11px; font-weight:300; }}
.hv-note-n {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--paper-3); }}
.hv-note-n b {{ color:var(--accent); font-weight:500; }}

/* ============ video ============ */
.hv-video {{ position:relative; width:100%; aspect-ratio:16/9; border:1px solid var(--line); background:var(--ink-2); overflow:hidden; }}
.hv-video iframe, .hv-video video {{ position:absolute; inset:0; width:100%; height:100%; border:0; }}
.hv-video-empty {{
  position:absolute; inset:0; display:grid; place-items:center;
  font-family:var(--mono); font-size:10px; letter-spacing:.24em; text-transform:uppercase; color:var(--paper-3);
  background: repeating-linear-gradient(135deg, rgba(233,231,223,.025) 0 1px, transparent 1px 9px);
}}

/* ============ contact / footer ============ */
.hv-cta {{
  font-family: var(--display); font-weight:900; text-transform:uppercase;
  /* Shrink to fit: the longer the address, the smaller the type. --cta-len is
     set inline from the real string length and 0.52em is the measured average
     advance of this face at weight 900 (~0.486em, plus headroom). The vw form
     below is the fallback; the container query under it is the accurate one. */
  font-size: clamp(14px, min(7vw, calc(76vw / (var(--cta-len, 14) * 0.52))), 104px);
  line-height:.92; letter-spacing:-.015em;
  color: var(--paper); text-decoration:none; display:inline-block;
  max-width:100%; overflow-wrap:anywhere; word-break:normal;
  transition: color .35s, transform .55s cubic-bezier(.16,1,.3,1);
}}
.hv-cta:hover {{ color: var(--accent); transform: translateX(6px); }}
/* The column the address sits in is narrower than the viewport (Streamlit adds
   its own max-width), so measure against the column, not the window. */
.hv-cta-wrap {{ container-type: inline-size; }}
@supports (container-type: inline-size) {{
  .hv-cta {{ font-size: clamp(14px, calc(100cqi / (var(--cta-len, 14) * 0.52)), 104px); }}
}}
.hv-links {{ display:flex; flex-wrap:wrap; gap: clamp(12px,1.8vw,26px); margin-top:28px; }}
.hv-links a {{
  font-family:var(--mono); font-size:10px; letter-spacing:.2em; text-transform:uppercase;
  color:var(--paper-2); text-decoration:none; padding-bottom:4px; border-bottom:1px solid var(--line); transition:.3s;
}}
.hv-links a:hover {{ color:var(--accent); border-color:var(--accent); }}
.hv-footer {{
  border-top:1px solid var(--line); padding: 26px var(--gut) 34px;
  display:flex; flex-wrap:wrap; gap:14px; justify-content:space-between;
  font-family:var(--mono); font-size:9.5px; letter-spacing:.18em; text-transform:uppercase; color:var(--paper-3);
}}
.hv-footer a {{ color:inherit; text-decoration:none; }}
.hv-footer a:hover {{ color: var(--accent); }}

/* ============ Streamlit widgets ============ */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button, .stLinkButton > a {{
  border-radius:0 !important; border:1px solid var(--line) !important;
  background:transparent !important; color:var(--paper) !important;
  font-family: var(--mono) !important; font-weight:500 !important;
  letter-spacing:.16em !important; text-transform:uppercase !important;
  font-size:10.5px !important; padding:.66rem 1.15rem !important; transition:all .28s !important;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover,
.stDownloadButton > button:hover, .stLinkButton > a:hover {{
  border-color: var(--accent) !important; color: var(--accent) !important;
  background: rgba(var(--accent-rgb),.07) !important;
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--accent) !important; border-color: var(--accent) !important; color: var(--ink) !important;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
  filter: brightness(1.1); color: var(--ink) !important;
}}
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {{
  border-radius:0 !important; background: var(--ink-2) !important;
  border-color: var(--line) !important; color: var(--paper) !important;
  font-family: var(--sans) !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{ border-color: var(--accent) !important; }}
label, .stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label,
.stNumberInput label, .stCheckbox label, .stFileUploader label, .stRadio label,
.stSlider label, .stColorPicker label, .stToggle label {{
  font-family: var(--mono) !important; font-size:9.5px !important; letter-spacing:.17em !important;
  text-transform:uppercase !important; color: var(--paper-3) !important; font-weight:500 !important;
}}
[data-testid="stFileUploaderDropzone"] {{ border-radius:0 !important; background:var(--ink-2) !important; border:1px dashed var(--line) !important; }}
[data-testid="stExpander"] {{ border-radius:0 !important; border:1px solid var(--line) !important; background:var(--ink-2) !important; }}
[data-testid="stSidebar"] {{ background: var(--ink-2) !important; border-right:1px solid var(--line); }}
.stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{
  border-radius:0 !important; font-family:var(--mono) !important; font-size:10px !important;
  letter-spacing:.15em !important; text-transform:uppercase !important; color:var(--paper-3) !important;
}}
.stTabs [aria-selected="true"] {{ color: var(--accent) !important; }}
[data-testid="stMetricValue"] {{ font-family: var(--display) !important; font-weight:800 !important; color: var(--paper) !important; }}
[data-testid="stMetricLabel"] p {{ font-family: var(--mono) !important; font-size:9.5px !important; letter-spacing:.16em; text-transform:uppercase; }}
hr {{ border-color: var(--line) !important; }}

.hv-admin-head {{
  padding: 22px var(--gut) 15px; border-bottom:1px solid var(--line);
  display:flex; flex-wrap:wrap; gap:12px; align-items:baseline; justify-content:space-between;
}}
.hv-admin-title {{ font-family:var(--display); font-weight:900; text-transform:uppercase; font-size: clamp(24px,3vw,44px); line-height:1; margin:0; }}
.hv-admin-title i {{ color: var(--accent); font-style:normal; }}
.hv-pill {{
  font-family:var(--mono); font-size:9.5px; letter-spacing:.17em; text-transform:uppercase;
  padding:5px 10px; border:1px solid var(--line); color:var(--paper-2); display:inline-block; margin-right:6px;
}}
.hv-pill.ok {{ border-color: rgba(var(--accent-rgb),.6); color: var(--accent); }}
.hv-pill.warn {{ border-color: rgba(var(--warm-rgb),.65); color: var(--warm); }}
.hv-pill.bad {{ border-color: rgba(226,90,80,.6); color:#E8736A; }}
{EXTRA}
</style>
"""
