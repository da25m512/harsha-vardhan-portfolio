"""Second half of the stylesheet: CSS-only interactions.

Project detail panels use :target and category filtering uses radio inputs
with sibling selectors, so browsing the work needs no JavaScript and no
server round-trip.
"""

EXTRA = """
/* ---------- CSS-only category filter ---------- */
.hv-filterbox { position:absolute; opacity:0; width:1px; height:1px; pointer-events:none; }
.hv-filters { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 clamp(20px,2.4vw,34px); }
.hv-filters label {
  cursor:pointer; user-select:none;
  font-family: var(--mono); font-size:9.5px; letter-spacing:.16em;
  text-transform:uppercase; font-weight:500;
  padding:8px 13px; border:1px solid var(--line); color:var(--paper-3);
  transition: all .28s cubic-bezier(.16,1,.3,1);
  font-variant-numeric: tabular-nums;
}
.hv-filters label:hover { color:var(--paper); border-color:rgba(233,231,223,.3); }
/* the inputs sit before .hv-workzone so the filter rules can reach it, so
   the checked state is matched through the general sibling combinator */
.hv-filters label[data-on] { background:var(--accent); border-color:var(--accent); color:var(--ink); }

/* ---------- CSS-only project detail (:target) ---------- */
.hv-modal {
  /* Above Streamlit's own toolbar (z-index 999990), so an open dialog is
     genuinely on top and its close button is the thing you click. */
  position:fixed; inset:0; z-index:1000000; display:grid; place-items:center;
  padding: clamp(10px,2.4vw,40px);
  background: rgba(8,10,9,.86); backdrop-filter: blur(12px) saturate(.65);
  opacity:0; pointer-events:none; visibility:hidden;
  transition: opacity .4s cubic-bezier(.16,1,.3,1), visibility .4s;
}
.hv-modal:target { opacity:1; pointer-events:auto; visibility:visible; }
.hv-modal-scrim { position:absolute; inset:0; }
.hv-modal-card {
  position:relative; z-index:2; width:min(1060px,100%); max-height:90svh; overflow-y:auto;
  background:var(--ink-2); border:1px solid var(--line);
  transform: translateY(22px); transition: transform .5s cubic-bezier(.16,1,.3,1);
}
.hv-modal:target .hv-modal-card { transform:none; }
.hv-modal-close {
  position:sticky; top:0; float:right; z-index:5; margin:10px 10px 0 0;
  width:36px; height:36px; display:grid; place-items:center;
  border:1px solid var(--line); background:rgba(16,18,17,.82); color:var(--paper);
  text-decoration:none; font-size:15px; line-height:1; transition:.28s;
}
.hv-modal-close:hover { background:var(--accent); border-color:var(--accent); color:var(--ink); transform:rotate(90deg); }
.hv-modal-hero { width:100%; aspect-ratio:21/9; overflow:hidden; background:var(--ink-3); }
.hv-modal-hero img { width:100%; height:100%; object-fit:cover; filter:grayscale(.3) brightness(.8); }
.hv-modal-body { padding: clamp(20px,3vw,46px); }
.hv-modal-title {
  font-family:var(--display); font-weight:900; text-transform:uppercase;
  font-size: clamp(28px,5vw,68px); line-height:.92; margin:0 0 14px; color:var(--paper);
}
.hv-modal-meta {
  display:flex; flex-wrap:wrap; gap:8px 22px; margin-bottom:22px; padding-bottom:18px;
  border-bottom:1px solid var(--line);
  font-family:var(--mono); font-size:9.5px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--paper-3); font-variant-numeric: tabular-nums;
}
.hv-modal-meta b { color:var(--accent); font-weight:500; }
.hv-modal-log {
  font-family:var(--quote); font-style:italic; font-weight:300;
  font-size: clamp(17px,1.7vw,25px); line-height:1.44; color:var(--paper);
  margin:0 0 22px; max-width:46ch;
}
.hv-modal-gal { display:grid; gap:8px; margin-top:26px; grid-template-columns: repeat(auto-fit,minmax(min(100%,190px),1fr)); }
.hv-modal-gal img { width:100%; aspect-ratio:4/3; object-fit:cover; border:1px solid var(--line); display:block; }
.hv-credits {
  white-space:pre-wrap; font-family:var(--mono); font-size:11.5px; line-height:1.95;
  color:var(--paper-2); border-left:2px solid var(--accent); padding-left:16px; margin-top:24px;
}
.hv-tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:18px; }
.hv-tag {
  font-family:var(--mono); font-size:9.5px; letter-spacing:.16em; text-transform:uppercase;
  padding:6px 10px; border:1px solid var(--line); color:var(--paper-2); transition:.28s;
}
.hv-tag:hover { border-color:var(--accent); color:var(--accent); }

/* ---------- hero video: still holds the frame until the video is ready ---------- */
.hv-hero-still {
  position:absolute; inset:0; width:100%; height:100%; object-fit:cover;
  transition: opacity .7s ease;
}
.hv-hero-video { opacity:0; transition: opacity .7s ease; }
.hv-hero-ready .hv-hero-video { opacity:1; }
.hv-hero-ready .hv-hero-still { opacity:0; }
.hv-hero-load {
  position:absolute; left:var(--gut); right:var(--gut); bottom:14px; height:2px;
  background: rgba(233,231,223,.14); z-index:3; overflow:hidden;
}
.hv-hero-load i {
  display:block; height:100%; width:0%; background:var(--accent);
  transition: width .25s linear;
}

/* ---------- several videos on one project ---------- */
.hv-video-grid { display:grid; gap: clamp(10px,1.2vw,18px); }
.hv-video-grid.two { grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); }
.hv-video-item { margin:0; }
.hv-video-cap {
  font-family: var(--mono); font-size:9.5px; letter-spacing:.16em;
  text-transform:uppercase; color:var(--paper-3); margin-top:8px;
}

/* ---------- play badge on cards that carry a video ---------- */
.hv-play {
  position:absolute; left:22px; top:9px; z-index:3;
  width:26px; height:26px; display:grid; place-items:center;
  font-size:9px; color:var(--ink); background:var(--accent);
  border-radius:50%; padding-left:2px;
  transition: transform .4s cubic-bezier(.16,1,.3,1);
}
.hv-card:hover .hv-play { transform: scale(1.18); }

/* ---------- video fallback link (sits behind the embed) ---------- */
.hv-video-fallback {
  position:absolute; inset:0; z-index:0; display:grid; place-items:center;
  font-family: var(--mono); font-size:10.5px; letter-spacing:.22em;
  text-transform:uppercase; color:var(--accent); text-decoration:none;
  background: repeating-linear-gradient(135deg, rgba(233,231,223,.025) 0 1px, transparent 1px 9px);
  transition: background .3s;
}
.hv-video-fallback:hover { background: rgba(87,200,176,.07); }
.hv-video iframe, .hv-video video, .hv-embed { z-index:1; }
.hv-embed { position:absolute; inset:0; }
.hv-embed:empty { pointer-events:none; }
.hv-embed iframe { position:absolute; inset:0; width:100%; height:100%; border:0; }

/* ---------- cursor spotlight (enhancement only) ---------- */
#hv-spot {
  position:fixed; width:440px; height:440px; border-radius:50%;
  pointer-events:none; z-index:1; opacity:0;
  background: radial-gradient(circle, rgba(var(--accent-rgb),.085), transparent 64%);
  transform: translate(-50%,-50%); transition: opacity .6s; mix-blend-mode: screen;
}
body.hv-hascursor #hv-spot { opacity:1; }

/* ---------- misc ---------- */
a { color: var(--accent); }
.hv-muted { font-family:var(--mono); color:var(--paper-3); font-size:10px; letter-spacing:.16em; text-transform:uppercase; }
.hv-empty-state {
  border:1px dashed var(--line); padding: clamp(24px,3.4vw,48px); text-align:center;
  font-family:var(--mono); color:var(--paper-3); font-size:10px; letter-spacing:.2em; text-transform:uppercase;
}
@media (max-width:640px) {
  .hv-gal { columns:1; }
  .hv-name .l2 { -webkit-text-stroke-width:1px; }
}

/* ---------- Streamlit blocks that sit inside the design ---------- */
.st-key-hv_gbform, .st-key-hv_login, .st-key-hv_admin { padding-inline: var(--gut); }
.st-key-hv_admin { padding-block: 22px 80px; }
.st-key-hv_login { padding-bottom: 80px; max-width: 620px; }
.st-key-hv_gbform { padding-bottom: 10px; }
.st-key-hv_gbform [data-testid="stForm"] {
  border:1px solid var(--line); padding: clamp(16px,1.8vw,26px); background: var(--ink-2);
}
.st-key-hv_gbform [data-testid="stTextInput"]:has(input[aria-label="Leave this empty"]) {
  position:absolute !important; left:-9999px !important; width:1px !important; height:1px !important; overflow:hidden !important;
}
.st-key-hv_admin h3 {
  font-family: var(--display); font-weight:800; text-transform:uppercase;
  font-size: clamp(18px,1.7vw,25px); margin-top:14px; color: var(--paper);
}
.st-key-hv_admin [data-testid="stExpander"] { margin-bottom:7px; }

/* ============ Toolkit ============ */
/* Borders live on the cells, not as gaps over a coloured container: with
   auto-fill the last row is usually partial, and a container background would
   show through the empty tail as a grey slab. */
.hv-tools {
  display:grid; gap:0;
  border-top:1px solid var(--line); border-left:1px solid var(--line);
  grid-template-columns: repeat(auto-fill, minmax(min(100%,150px), 1fr));
}
.hv-tool {
  border-right:1px solid var(--line); border-bottom:1px solid var(--line);
  padding: clamp(16px,1.8vw,22px) 12px; min-height:104px;
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:12px;
  transition: background .35s;
}
.hv-tool:hover { background:var(--ink-2); }
.hv-tool-mark {
  height:46px; width:100%; display:grid; place-items:center;
}
.hv-tool-mark img {
  max-height:46px; max-width:76%; object-fit:contain; display:block;
  filter: grayscale(1) brightness(1.7) contrast(.9); opacity:.82;
  transition: filter .35s, opacity .35s;
}
.hv-tool:hover .hv-tool-mark img { filter:none; opacity:1; }
.hv-tool-word {
  font-family:var(--display); font-weight:900; text-transform:uppercase;
  font-size: clamp(15px,1.5vw,22px); line-height:1.02; letter-spacing:-.01em;
  color:var(--paper-2); text-align:center;
  overflow-wrap:break-word; word-break:normal; hyphens:none;
  transition:color .35s;
}
.hv-tool:hover .hv-tool-word { color:var(--accent); }
.hv-tool-name {
  font-family:var(--mono); font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:var(--paper-2); text-align:center;
  overflow-wrap:break-word; word-break:normal;
}
"""
