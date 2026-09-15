"""The public-facing site. No login is required to read anything here.

Structure follows production paperwork: each section carries a slate rail
of monospaced metadata, and the work is laid out as a contact sheet.
"""
from __future__ import annotations

import time
from typing import Any

import streamlit as st

import hv_data as D
from hv_security import (
    MAX_STORED_MESSAGES,
    MSG_MAX,
    NAME_MAX,
    attr,
    check_message,
    embed_src,
    esc,
    img_src,
    mark_posted,
    safe_url,
)


def _watch_url(url: str) -> str:
    """The original, human-facing watch page for a video link."""
    u = safe_url(url, allow_mailto=False)
    return u


def _one_video(url: str, caption: str = "") -> str:
    """One 16:9 frame. A watch link sits behind the player, so the video is
    still reachable if an embed is ever blocked."""
    kind, src = embed_src(url)
    if not kind:
        return ""
    # Only an embed needs a fallback link: a <video> element survives
    # sanitisation and always renders, so it never needs one.
    watch = _watch_url(url) if kind == "iframe" else ""
    where = "Vimeo" if "vimeo" in watch else "YouTube"
    fallback = (
        f'<a class="hv-video-fallback" href="{attr(watch)}" target="_blank" '
        f'rel="noopener noreferrer">Watch on {where} &#8599;</a>'
        if watch
        else ""
    )
    if kind == "iframe":
        # Streamlit sanitises st.html and drops <iframe>, so the player is
        # described here and built by the enhancement script, which runs
        # outside the sanitiser. The watch link underneath stays as the
        # fallback if that script never runs.
        inner = (
            f'<div class="hv-embed" data-embed="{attr(src)}" '
            f'data-title="{attr(caption or "Video")}"></div>'
        )
    else:
        inner = f'<video src="{attr(src)}" controls preload="metadata" playsinline></video>'
    cap = f'<div class="hv-video-cap">{esc(caption)}</div>' if caption else ""
    return f'<figure class="hv-video-item"><div class="hv-video">{fallback}{inner}</div>{cap}</figure>'


def _videos_html(videos: list[dict], extra_style: str = "") -> str:
    """Every video on a project, each in its own labelled frame."""
    frames = []
    n_link = n_file = 0
    for v in videos or []:
        url = str((v or {}).get("url") or "")
        kind, _ = embed_src(url)
        if not kind:
            continue
        if (v or {}).get("type") == "file" or kind == "file":
            n_file += 1
            label = "Uploaded clip" if n_file == 1 else f"Uploaded clip {n_file}"
        else:
            n_link += 1
            host = "Vimeo" if "vimeo" in url else "YouTube"
            label = f"On {host}" if n_link == 1 else f"On {host} ({n_link})"
        frames.append(_one_video(url, label if len(videos) > 1 else ""))
    frames = [f for f in frames if f]
    if not frames:
        return ""
    cls = "hv-video-grid" + (" two" if len(frames) > 1 else "")
    return f'<div class="{cls}" style="{extra_style}">{"".join(frames)}</div>'


def _slug(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in str(s))
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "x"


def _md(html: str) -> None:
    """Inject raw HTML.

    Streamlit sanitises `st.markdown(unsafe_allow_html=True)` hard enough
    that <style> is rendered as visible text, so `st.html` is the supported
    route for this. Fall back to markdown on older versions.
    """
    writer = getattr(st, "html", None)
    if callable(writer):
        writer(html)
    else:  # pragma: no cover - Streamlit < 1.33
        st.markdown(html, unsafe_allow_html=True)


def _title(text: str) -> str:
    """Last word of a heading drops into the italic editorial face."""
    words = str(text).split()
    if len(words) < 2:
        return esc(text)
    return esc(" ".join(words[:-1])) + f" <em>{esc(words[-1])}</em>"


def _slate(reel: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<div class="hv-slate-k">{esc(k)} <span style="color:var(--paper-2)">{esc(v)}</span></div>'
        for k, v in rows
        if v
    )
    return (
        f'<div class="hv-slate"><div class="hv-slate-reel">Reel {esc(reel)}</div>{body}</div>'
    )


def _open(reel: str, slate_rows: list[tuple[str, str]], heading: str, anchor: str) -> str:
    return f"""
<section class="hv-section" id="{attr(anchor)}">
  <div class="hv-wrap"><div class="hv-cols">
    {_slate(reel, slate_rows)}
    <div>
      <h2 class="hv-h2 hv-rise">{heading}</h2>
"""


_CLOSE = "    </div>\n  </div></div>\n</section>"


# --------------------------------------------------------------------------
# Hero
# --------------------------------------------------------------------------
def _hero(site: dict) -> None:
    name = str(site.get("name") or D.DIRECTOR_NAME).strip()
    words = [w for w in name.split() if w] or [D.DIRECTOR_NAME]
    # One word per line, up to four; the closing word is drawn hollow so the
    # stack reads as a poster rather than a paragraph.
    if len(words) > 4:
        words = words[:3] + [" ".join(words[3:])]
    lines = []
    for i, w in enumerate(words):
        last = i == len(words) - 1
        cls = ' class="hollow"' if last and len(words) > 1 else ""
        tail = '<span class="dot">.</span>' if last else ""
        lines.append(f"<span{cls}>{esc(w)}{tail}</span>")
    name_html = "".join(lines)

    vid, im = img_src(site.get("hero_video", "")), img_src(site.get("hero_image", ""))
    if vid and site.get("cache_hero", True):
        # The video is kept in the browser's Cache Storage, so a returning
        # visitor pays for it once instead of on every visit. The still (or a
        # plain ground) holds the frame while it downloads, and the filename
        # changes whenever a new video is uploaded, which retires the old copy.
        still = f'<img class="hv-hero-still" src="{im}" alt="">' if im else ""
        bg = (
            '<div class="hv-hero-bg">'
            f"{still}"
            f'<video class="hv-hero-video" data-hv-src="{vid}" muted loop '
            'playsinline preload="none"></video>'
            '<div class="hv-hero-load" hidden><i></i></div>'
            "</div>"
        )
    elif vid:
        bg = f'<div class="hv-hero-bg"><video src="{vid}" autoplay muted loop playsinline></video></div>'
    elif im:
        bg = f'<div class="hv-hero-bg"><img src="{im}" alt=""></div>'
    else:
        bg = '<div class="hv-hero-bg"></div>'

    avail = (
        '<div><div class="hv-mk">Status</div><div class="hv-mv">'
        f'<span class="hv-dot"></span>{esc(site.get("available_text") or "Available")}</div></div>'
        if site.get("available")
        else ""
    )
    email = str(site.get("email") or "").strip()
    mail = safe_url("mailto:" + email) if email else ""
    email_block = (
        f'<div><div class="hv-mk">Contact</div><div class="hv-mv">'
        f'<a href="{attr(mail)}" style="color:inherit;text-decoration:none;'
        f'border-bottom:1px solid var(--accent)">{esc(email)}</a></div></div>'
        if mail
        else ""
    )

    _md(
        f"""
<div id="hv-spot"></div>
<header class="hv-hero" id="top">
  {bg}
  <div class="hv-hero-top">
    <span class="hv-mono">{esc(site.get('eyebrow') or 'Director')}</span>
    <span class="hv-mono">{esc(site.get('location') or '')}</span>
  </div>
  <div class="hv-hero-inner">
    <h1 class="hv-name hv-in">{name_html}</h1>
    <p class="hv-tagline hv-in">{esc(site.get('tagline') or '')}</p>
    <div class="hv-strip-meta hv-in">
      <div><div class="hv-mk">Discipline</div>
        <div class="hv-mv">{esc(' / '.join(site.get('roles') or []) or 'Director')}</div></div>
      {avail}
      {email_block}
      <div style="margin-left:auto"><div class="hv-mk">Index</div>
        <div class="hv-mv"><a href="#work" style="text-decoration:none">The work &#8595;</a></div></div>
    </div>
  </div>
</header>"""
    )


def _marquee(site: dict) -> None:
    roles = [r for r in (site.get("roles") or []) if str(r).strip()] or ["Director"]
    run = "".join(f"<span>{esc(r)}</span>" for r in roles)
    _md(f'<div class="hv-marquee" aria-hidden="true"><div class="hv-marquee-track">{run*4}</div></div>')


# --------------------------------------------------------------------------
# Statement
# --------------------------------------------------------------------------
def _statement(site: dict, ledger: list[tuple[str, Any]], reel: str) -> None:
    portrait = img_src(site.get("portrait", ""))
    right = (
        f'<div class="hv-portrait hv-rise"><img src="{portrait}" alt="Portrait of {attr(site.get("name"))}"></div>'
        if portrait
        else ""
    )
    rows = "".join(
        f'<div class="hv-ledger-row"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in ledger
    )
    _md(
        _open(
            reel,
            [("Sec", "Statement"), ("Base", site.get("location") or "—")],
            _title(site["section_titles"]["statement"]),
            "about",
        )
        + f"""
      <div class="hv-split">
        <div>
          <p class="hv-quote hv-rise">{esc(site.get('statement') or '')}</p>
          <div class="hv-ledger hv-rise">{rows}</div>
        </div>
        <div>
          {right}
          <p class="hv-p hv-rise" style="margin-top:18px">{esc(site.get('bio') or '')}</p>
        </div>
      </div>
"""
        + _CLOSE
    )


# --------------------------------------------------------------------------
# Work — contact sheet
# --------------------------------------------------------------------------
def _tech(p: dict) -> str:
    bits = []
    if p.get("year"):
        bits.append(f'<span><b>{esc(p["year"])}</b></span>')
    for v in (p.get("category"), p.get("runtime"), p.get("shot_on"), p.get("ratio")):
        if v:
            bits.append(f"<span>{esc(v)}</span>")
    if p.get("role"):
        bits.append(f'<span>{esc(p["role"])}</span>')
    return f'<div class="hv-techstrip">{"".join(bits)}</div>'


def _card(p: dict, idx: int) -> str:
    pid = esc(p.get("id") or idx)
    poster = img_src(p.get("poster", ""))
    frame = (
        f'<img src="{poster}" alt="{attr(p.get("title"))}" loading="lazy">'
        if poster
        else f'<div class="hv-frame-empty">{esc(str(p.get("title") or "?").strip()[:2].upper())}</div>'
    )
    flag = (
        f'<div class="hv-statusflag">{esc(p.get("status"))}</div>'
        if p.get("status") and p.get("status") != "Released"
        else ""
    )
    log = f'<div class="hv-card-log">{esc(p.get("logline"))}</div>' if p.get("logline") else ""
    playable = any(embed_src(str((v or {}).get("url") or ""))[0] for v in (p.get("videos") or []))
    play = '<div class="hv-play" aria-hidden="true">&#9654;</div>' if playable else ""
    return f"""
<a class="hv-card{' wide' if p.get('featured') else ''} hv-rise" data-cat="{attr(_slug(p.get('category') or 'other'))}"
   href="#p-{pid}" aria-label="Open {attr(p.get('title'))}">
  <div class="hv-frame">
    <div class="hv-sprocket" aria-hidden="true"></div>
    {frame}
    <div class="hv-slateno">SL {idx:02d}</div>
    {play}
    {flag}
  </div>
  <div class="hv-card-body">
    <h3 class="hv-card-title">{esc(p.get('title') or 'Untitled')}</h3>
    {_tech(p)}
    {log}
  </div>
</a>"""


def _modal(p: dict, idx: int) -> str:
    pid = esc(p.get("id") or idx)
    poster = img_src(p.get("poster", ""))
    hero = f'<div class="hv-modal-hero"><img src="{poster}" alt=""></div>' if poster else ""
    meta = "".join(
        f"<span>{esc(k)} <b>{esc(v)}</b></span>"
        for k, v in (
            ("Year", p.get("year")), ("Format", p.get("category")),
            ("Runtime", p.get("runtime")), ("Shot on", p.get("shot_on")),
            ("Ratio", p.get("ratio")), ("Role", p.get("role")), ("Status", p.get("status")),
        )
        if v
    )
    video = _videos_html(p.get("videos") or [], "margin-top:24px")
    gal = "".join(
        f'<img src="{img_src(g)}" alt="" loading="lazy">' for g in (p.get("gallery") or []) if img_src(g)
    )
    tags = "".join(f'<span class="hv-tag">{esc(t)}</span>' for t in (p.get("tags") or []) if str(t).strip())
    link = safe_url(p.get("link", ""))
    return f"""
<div class="hv-modal" id="p-{pid}" role="dialog" aria-label="{attr(p.get('title'))}">
  <a class="hv-modal-scrim" href="#work" aria-label="Close"></a>
  <div class="hv-modal-card">
    <a class="hv-modal-close" href="#work" aria-label="Close">&#10005;</a>
    {hero}
    <div class="hv-modal-body">
      <h3 class="hv-modal-title">{esc(p.get('title') or 'Untitled')}</h3>
      <div class="hv-modal-meta">{meta}</div>
      {f'<p class="hv-modal-log">{esc(p.get("logline"))}</p>' if p.get("logline") else ""}
      {f'<p class="hv-p">{esc(p.get("synopsis")).replace(chr(10), "<br>")}</p>' if p.get("synopsis") else ""}
      {video}
      {f'<div class="hv-modal-gal">{gal}</div>' if gal else ""}
      {f'<div class="hv-credits">{esc(p.get("credits"))}</div>' if p.get("credits") else ""}
      {f'<div class="hv-tags">{tags}</div>' if tags else ""}
      {f'<p style="margin-top:22px"><a class="hv-mono" href="{attr(link)}" target="_blank" rel="noopener noreferrer nofollow">Open external link &#8599;</a></p>' if link else ""}
    </div>
  </div>
</div>"""


def _work(site: dict, projects: list[dict], reel: str) -> None:
    items = D.sorted_projects(projects)
    years = [str(p.get("year")) for p in items if p.get("year")]
    span = f"{min(years)}–{max(years)}" if years else "—"
    head = _open(
        reel,
        [("Sec", "Work"), ("Titles", str(len(items))), ("Span", span)],
        _title(site["section_titles"]["work"]),
        "work",
    )
    if not items:
        _md(head + '<div class="hv-empty-state">The first title lands here soon.</div>' + _CLOSE)
        return

    cats: list[str] = []
    for p in items:
        c = p.get("category") or "Other"
        if c not in cats:
            cats.append(c)

    radios = ['<input type="radio" name="hvfilter" id="hvf-all" class="hv-filterbox" checked>']
    labels = [f'<label for="hvf-all">All &middot; {len(items)}</label>']
    rules = [
        '#hvf-all:checked ~ .hv-filters label[for="hvf-all"]'
        "{background:var(--accent);border-color:var(--accent);color:var(--ink)}"
    ]
    for c in cats:
        s = _slug(c)
        n = sum(1 for p in items if _slug(p.get("category") or "other") == s)
        radios.append(f'<input type="radio" name="hvfilter" id="hvf-{attr(s)}" class="hv-filterbox">')
        labels.append(f'<label for="hvf-{attr(s)}">{esc(c)} &middot; {n}</label>')
        rules.append(f'#hvf-{s}:checked ~ .hv-workzone .hv-card:not([data-cat="{s}"]){{display:none}}')
        rules.append(
            f'#hvf-{s}:checked ~ .hv-filters label[for="hvf-{s}"]'
            "{background:var(--accent);border-color:var(--accent);color:var(--ink)}"
        )
        rules.append(
            f'#hvf-{s}:focus-visible ~ .hv-filters label[for="hvf-{s}"]'
            "{outline:2px solid var(--accent);outline-offset:2px}"
        )

    _md(
        head
        + "<style>" + "".join(rules) + "</style>"
        + "".join(radios)
        + f'<div class="hv-filters hv-rise" role="group" aria-label="Filter work by format">{"".join(labels)}</div>'
        + f'<div class="hv-workzone"><div class="hv-grid">'
        + "".join(_card(p, i + 1) for i, p in enumerate(items))
        + "</div></div>"
        + _CLOSE
        + "".join(_modal(p, i + 1) for i, p in enumerate(items))
    )


# --------------------------------------------------------------------------
def _showreel(site: dict, reel: str) -> None:
    clips = [
        {"type": "file", "url": site.get("showreel_file", "")},
        {"type": "link", "url": site.get("showreel_url", "")},
    ]
    body = _videos_html(clips) or (
        '<div class="hv-video hv-rise"><div class="hv-video-empty">Reel in assembly</div></div>'
    )
    _md(
        _open(reel, [("Sec", "Reel"), ("Ratio", "16:9")], _title(site["section_titles"]["showreel"]), "reel")
        + body
        + (f'<p class="hv-muted" style="margin-top:14px">{esc(site.get("showreel_caption"))}</p>'
           if site.get("showreel_caption") else "")
        + _CLOSE
    )


def _timeline(site: dict, items: list[dict], reel: str) -> None:
    head = _open(reel, [("Sec", "Journey"), ("Entries", str(len(items)))],
                 _title(site["section_titles"]["timeline"]), "journey")
    if not items:
        _md(head + '<div class="hv-empty-state">Milestones appear here.</div>' + _CLOSE)
        return
    rows = sorted(items, key=lambda x: str(x.get("year") or ""), reverse=True)
    body = "".join(
        f'<div class="hv-tl-item hv-rise"><div class="hv-tl-year">{esc(r.get("year") or "")}</div>'
        f'<div><div class="hv-tl-title">{esc(r.get("title") or "")}</div>'
        f'<div class="hv-tl-body">{esc(r.get("body") or "")}</div></div></div>'
        for r in rows
    )
    _md(head + f'<div class="hv-tl">{body}</div>' + _CLOSE)


def _gallery(site: dict, items: list[dict], reel: str) -> None:
    head = _open(reel, [("Sec", "Stills"), ("Frames", str(len(items)))],
                 _title(site["section_titles"]["gallery"]), "stills")
    figs = []
    for g in items:
        src = img_src(g.get("url", ""))
        if not src:
            continue
        cap = f"<figcaption>{esc(g.get('caption'))}</figcaption>" if g.get("caption") else ""
        figs.append(f'<figure><img src="{src}" alt="{attr(g.get("caption"))}" loading="lazy">{cap}</figure>')
    if not figs:
        _md(head + '<div class="hv-empty-state">Stills appear here.</div>' + _CLOSE)
        return
    _md(head + f'<div class="hv-gal hv-rise">{"".join(figs)}</div>' + _CLOSE)


def _press(site: dict, items: list[dict], reel: str) -> None:
    head = _open(reel, [("Sec", "Press"), ("Items", str(len(items)))],
                 _title(site["section_titles"]["press"]), "press")
    if not items:
        _md(head + '<div class="hv-empty-state">Recognition appears here.</div>' + _CLOSE)
        return
    cards = "".join(
        f'<div class="hv-press-card hv-rise"><div class="hv-press-q">{esc(r.get("quote") or "")}</div>'
        f'<div class="hv-press-s">{esc(r.get("source") or "")}'
        f'{" &middot; " + esc(r.get("year")) if r.get("year") else ""}</div></div>'
        for r in items
    )
    _md(head + f'<div class="hv-press">{cards}</div>' + _CLOSE)


# --------------------------------------------------------------------------
def _guestbook(site: dict, messages: list[dict], reel: str) -> None:
    shown = [m for m in messages if m.get("approved")]
    _md(
        _open(reel, [("Sec", "Guestbook"), ("Notes", str(len(shown))), ("Login", "Not required")],
              _title(site["section_titles"]["guestbook"]), "guestbook")
        + '<p class="hv-p hv-rise">No account, no login. Leave a note, a question or an idea '
        .</p>"
        + "    </div>\n  </div></div>"
    )

    if site.get("guestbook_open", True):
        with st.container(key="hv_gbform"):
            with st.form("guestbook", clear_on_submit=True, border=False):
                c1, c2 = st.columns([1, 2])
                name = c1.text_input("Your name", max_chars=NAME_MAX, placeholder="Who's writing?")
                role = c2.text_input("Where you're from (optional)", max_chars=60,
                                     placeholder="City, or what you do")
                msg = st.text_area("Your message", max_chars=MSG_MAX, height=110,
                                   placeholder="Say anything…")
                hp = st.text_input("Leave this empty", key="hv_hp", label_visibility="collapsed")
                sent = st.form_submit_button("Send it", type="primary")

            if sent:
                ok, err = check_message(name, msg, hp)
                if not ok:
                    st.warning(err, icon="⚠️")
                else:
                    entry = {
                        "id": D.new_id(), "name": name.strip(), "role": (role or "").strip(),
                        "message": msg.strip(), "at": D.now_stamp(),
                        "approved": not site.get("guestbook_moderated", True),
                    }
                    try:
                        fresh = ([entry] + list(D.load_content()["messages"]))[:MAX_STORED_MESSAGES]
                        D.save(D.MESSAGES_PATH, fresh, "guestbook message")
                        mark_posted()
                        st.success(
                            "Thank you — your note is in. It appears once approved."
                            if site.get("guestbook_moderated", True)
                            else "Thank you — your note is up."
                        )
                        shown = [m for m in fresh if m.get("approved")]
                    except Exception:
                        st.error("Couldn't save that right now. Please try again in a moment.")
    else:
        _md('<div class="hv-wrap"><div class="hv-empty-state">The guestbook is closed for now.</div></div>')

    if shown[:24]:
        notes = "".join(
            f'<div class="hv-note hv-rise"><div class="hv-note-m">{esc(m.get("message") or "")}</div>'
            f'<div class="hv-note-n"><b>{esc(m.get("name") or "Anonymous")}</b>'
            f'{" &middot; " + esc(m.get("role")) if m.get("role") else ""}'
            f' &middot; {esc(m.get("at") or "")}</div></div>'
            for m in shown[:24]
        )
        _md(f'<div class="hv-wrap" style="padding-bottom:clamp(62px,9vw,132px)">'
            f'<div class="hv-press" style="margin-top:26px">{notes}</div></div></section>')
    else:
        _md('<div style="padding-bottom:clamp(62px,9vw,132px)"></div></section>')


def _contact(site: dict, reel: str) -> None:
    email = str(site.get("email") or "").strip()
    mail = safe_url("mailto:" + email) if email else ""
    cta = (
        f'<a class="hv-cta" style="--cta-len:{max(len(email), 8)}" '
        f'href="{attr(mail)}">{esc(email)}</a>'
        if mail
        else '<span class="hv-cta" style="--cta-len:12;color:var(--paper-3)">Get in touch</span>'
    )
    links = [
        f'<a href="{attr(u)}" target="_blank" rel="noopener noreferrer">{esc(s.get("label") or "Link")} &#8599;</a>'
        for s in (site.get("socials") or [])
        if (u := safe_url(s.get("url", "")))
    ]
    if site.get("phone") and (p := safe_url("tel:" + str(site["phone"]).replace(" ", ""))):
        links.append(f'<a href="{attr(p)}">{esc(site["phone"])}</a>')

    _md(
        _open(reel, [("Sec", "Contact"), ("Reply", "Usually same week")], "Let's make <em>something</em>", "contact")
        + f'<div class="hv-rise hv-cta-wrap">{cta}</div><div class="hv-links hv-rise">{"".join(links)}</div>'
        + _CLOSE
        + f"""
<footer class="hv-footer">
  <span>&copy; {time.strftime('%Y')} {esc(site.get('name'))}</span>
  <span>{esc(site.get('footer_note') or '')}</span>
  <span><a href="#top">Back to top &#8593;</a></span>
</footer>"""
    )


# --------------------------------------------------------------------------
def _enhance() -> None:
    """Progressive enhancement.

    Also builds the video embeds: Streamlit strips <iframe> out of st.html,
    so each embed is emitted as a placeholder and turned into a real iframe
    here. The host is re-checked against the allowlist before anything is
    created, so a tampered attribute cannot load a foreign frame.
    """
    import streamlit.components.v1 as components

    components.html(
        """
<script>
(function () {
  var ALLOWED = ["www.youtube-nocookie.com", "player.vimeo.com"];
  var HERO_CACHE = "hv-hero-v1";

  // Keep the hero video in Cache Storage so a returning visitor does not
  // re-download it. Anything cached under a different URL is dropped, so
  // uploading a new video replaces the stored copy instead of stacking up.
  async function cacheHero(v, w) {
    var url = v.getAttribute("data-hv-src");
    if (!url || v.dataset.hvStarted) return;
    v.dataset.hvStarted = "1";
    var box = v.parentElement;
    var bar = box && box.querySelector(".hv-hero-load");
    var fill = bar && bar.firstElementChild;
    function progress(pct) {
      if (!bar) return;
      bar.hidden = false;
      if (fill) fill.style.width = pct + "%";
    }
    var src = url;
    try {
      if (!w.caches) throw new Error("no cache storage");
      var absolute = new w.URL(url, w.location.href).href;
      var cache = await w.caches.open(HERO_CACHE);
      var keys = await cache.keys();
      for (var i = 0; i < keys.length; i++) {
        if (keys[i].url !== absolute) await cache.delete(keys[i]);
      }
      var hit = await cache.match(absolute);
      if (!hit) {
        var res = await w.fetch(absolute);
        if (!res.ok) throw new Error("fetch " + res.status);
        var total = Number(res.headers.get("content-length") || 0);
        var reader = res.body && res.body.getReader ? res.body.getReader() : null;
        var blob;
        if (reader) {
          var chunks = [], got = 0;
          for (;;) {
            var step = await reader.read();
            if (step.done) break;
            chunks.push(step.value);
            got += step.value.length;
            if (total) progress(Math.min(99, Math.round((got / total) * 100)));
          }
          blob = new w.Blob(chunks, { type: res.headers.get("content-type") || "video/mp4" });
        } else {
          blob = await res.blob();
        }
        await cache.put(absolute, new w.Response(blob, {
          headers: { "Content-Type": blob.type || "video/mp4" }
        }));
        hit = await cache.match(absolute);
      }
      var stored = await hit.blob();
      src = w.URL.createObjectURL(stored);
    } catch (err) {
      src = url;  // stream straight from the CDN instead
    }
    if (bar) bar.hidden = true;
    v.addEventListener("canplay", function () {
      if (box) box.classList.add("hv-hero-ready");
    }, { once: true });
    v.src = src;
    var go = v.play();
    if (go && go.catch) go.catch(function () {});
  }

  function build(box) {
    if (!box || box.dataset.hvBuilt) return;
    var src = box.getAttribute("data-embed") || "";
    var u;
    try { u = new URL(src); } catch (e) { return; }
    if (u.protocol !== "https:" || ALLOWED.indexOf(u.hostname) === -1) return;
    box.dataset.hvBuilt = "1";
    var f = box.ownerDocument.createElement("iframe");
    f.src = src;
    f.title = box.getAttribute("data-title") || "Video";
    f.loading = "lazy";
    f.allowFullscreen = true;
    f.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    f.setAttribute("allow",
      "accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture");
    f.setAttribute("sandbox",
      "allow-scripts allow-same-origin allow-presentation allow-popups");
    box.appendChild(f);
  }

  function hydrate(root) {
    (root || window.parent.document)
      .querySelectorAll(".hv-embed:not([data-hv-built])").forEach(build);
  }

  // Closing a project has to actually stop its players. A <video> is paused;
  // an embed is torn down to its placeholder, because a cross-origin frame
  // keeps playing (and keeps its audio) after the dialog is hidden. Reopening
  // the project rebuilds it.
  function quiet(modal) {
    modal.querySelectorAll("video").forEach(function (v) {
      try { v.pause(); } catch (e) { /* nothing to pause */ }
    });
    modal.querySelectorAll(".hv-embed[data-hv-built]").forEach(function (box) {
      var f = box.querySelector("iframe");
      if (f) f.remove();
      delete box.dataset.hvBuilt;
    });
  }

  function syncPlayers(d) {
    var h = d.defaultView.location.hash;
    d.querySelectorAll(".hv-modal").forEach(function (m) {
      if ("#" + m.id !== h) quiet(m);
    });
  }

  function hydrateTarget(d) {
    var h = d.defaultView.location.hash;
    if (!h || h.length < 2) return;
    var el = null;
    try { el = d.querySelector(h); } catch (e) { return; }
    if (el) hydrate(el);
  }

  try {
    var d = window.parent.document, w = window.parent;
    if (!d || d.body.dataset.hvEnhanced) return;
    d.body.dataset.hvEnhanced = "1";

    // players outside a dialog load right away; a project's players wait
    // until that project is opened, so the page does not pull down a dozen
    // embeds nobody asked for
    d.querySelectorAll(".hv-embed").forEach(function (box) {
      if (!box.closest(".hv-modal")) build(box);
    });
    d.querySelectorAll("video[data-hv-src]").forEach(function (v) { cacheHero(v, w); });
    hydrateTarget(d);
    w.addEventListener("hashchange", function () {
      syncPlayers(d);      // silence whatever was just closed
      hydrateTarget(d);    // then wake up whatever was just opened
    });
    // Leaving the page entirely (back button, tab close) also stops playback.
    w.addEventListener("pagehide", function () { syncPlayers(d); });

    var spot = d.getElementById("hv-spot");
    if (spot && w.matchMedia("(pointer:fine)").matches &&
        !w.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      d.body.classList.add("hv-hascursor");
      var x = 0, y = 0, cx = 0, cy = 0;
      d.addEventListener("mousemove", function (e) { x = e.clientX; y = e.clientY; });
      (function loop() {
        cx += (x - cx) * 0.08; cy += (y - cy) * 0.08;
        spot.style.transform = "translate(" + cx + "px," + cy + "px) translate(-50%,-50%)";
        w.requestAnimationFrame(loop);
      })();
    }
    d.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && w.location.hash.indexOf("#p-") === 0) w.location.hash = "#work";
    });
  } catch (err) { /* enhancement only */ }
})();
</script>""",
        height=0,
    )


def render(content: dict[str, Any]) -> None:
    site = content["site"]
    sec = site.get("sections", {})
    published = [p for p in content["projects"] if p.get("published", True)]
    stills = [g for g in content["gallery"] if img_src(g.get("url", ""))]
    notes = [m for m in content["messages"] if m.get("approved")]
    has_reel = bool(
        embed_src(site.get("showreel_file", ""))[0]
        or embed_src(site.get("showreel_url", ""))[0]
    )

    _hero(site)
    _marquee(site)

    ledger = [
        ("Titles directed", len(published)),
        ("Formats worked in", len({p.get("category") for p in published if p.get("category")})),
        ("Milestones logged", len(content["timeline"])),
        ("Frames published", len(stills)),
    ]
    # Only show the ledger rows that actually count something.
    ledger = [(k, v) for k, v in ledger if v]

    # A section appears only when it has something to say. An empty one is
    # hidden outright rather than showing a placeholder, and the reel numbers
    # stay sequential so there are never gaps.
    plan = [
        (sec.get("statement", True) and bool(
            str(site.get("statement") or "").strip()
            or str(site.get("bio") or "").strip()
            or img_src(site.get("portrait", ""))
        ), lambda r: _statement(site, ledger, r)),
        (sec.get("work", True) and bool(published),
         lambda r: _work(site, content["projects"], r)),
        (sec.get("showreel", True) and has_reel, lambda r: _showreel(site, r)),
        (sec.get("timeline", True) and bool(content["timeline"]),
         lambda r: _timeline(site, content["timeline"], r)),
        (sec.get("gallery", True) and bool(stills), lambda r: _gallery(site, stills, r)),
        (sec.get("press", True) and bool(content["press"]),
         lambda r: _press(site, content["press"], r)),
        (sec.get("guestbook", True) and (site.get("guestbook_open", True) or bool(notes)),
         lambda r: _guestbook(site, content["messages"], r)),
        (True, lambda r: _contact(site, r)),
    ]

    reel = 0
    for show, draw in plan:
        if not show:
            continue
        reel += 1
        draw(f"{reel:02d}")

    _enhance()
