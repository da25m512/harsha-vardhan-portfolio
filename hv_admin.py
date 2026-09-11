"""Password-protected admin console. Everything the director can change."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

import hv_data as D
from hv_security import (
    attempt_login,
    enforce_session_timeout,
    esc,
    is_admin,
    lockout_remaining,
    logout,
    password_is_configured,
    safe_url,
    validate_upload,
)
from hv_store import GitHubStore, StoreError


def _guarded(action, ok_message: str = "Saved.") -> bool:
    """Run a save and turn any storage failure into a readable message
    instead of a redacted crash screen."""
    try:
        action()
    except StoreError as exc:
        st.error(str(exc), icon="🚫")
        return False
    except Exception as exc:  # network, JSON, anything unexpected
        st.error(
            f"Couldn't save: {type(exc).__name__}. Check the Overview tab for the "
            "storage status, then try again.",
            icon="🚫",
        )
        return False
    st.success(ok_message, icon="✅")
    return True


def _md(html: str) -> None:
    writer = getattr(st, "html", None)
    if callable(writer):
        writer(html)
    else:  # pragma: no cover
        st.markdown(html, unsafe_allow_html=True)


# --------------------------------------------------------------------------
def login_gate() -> bool:
    enforce_session_timeout()
    if is_admin():
        return True

    _md(
        """
<div class="hv-wrap" style="padding-block:clamp(60px,10vw,130px);max-width:620px">
  <div class="hv-eyebrow"><span class="n">—</span> / Restricted</div>
  <h2 class="hv-h2">Admin <em>access</em></h2>
  <p class="hv-p">This is the private side of the site. The public pages need no login.</p>
</div>"""
    )
    with st.container(key="hv_login"):
        if not password_is_configured():
            st.error(
                "No admin password is set yet. In Streamlit Cloud open "
                "**Manage app → Settings → Secrets** and add:\n\n"
                '```toml\nadmin_password = "your-strong-password"\n```',
                icon="🔒",
            )
        rem = lockout_remaining()
        if rem:
            st.warning(f"Locked for {rem} more seconds after too many attempts.", icon="⏳")
        with st.form("login", border=False):
            pw = st.text_input("Password", type="password", autocomplete="current-password")
            go = st.form_submit_button("Enter", type="primary", disabled=bool(rem))
        if go:
            ok, err = attempt_login(pw)
            if ok:
                st.rerun()
            else:
                st.error(err, icon="🚫")
        st.link_button("← Back to the site", "?", use_container_width=False)
    return False


# --------------------------------------------------------------------------
def _upload(label: str, folder: str, kind: str, key: str) -> str | None:
    """Render an uploader; return a stored URL, or None if nothing new."""
    types = (
        ["png", "jpg", "jpeg", "webp", "gif", "avif"]
        if kind == "image"
        else ["mp4", "webm", "mov", "m4v"]
    )
    f = st.file_uploader(label, type=types, key=key, accept_multiple_files=False)
    if f is None:
        st.session_state.pop(f"_up_done_{key}", None)
        return None

    # Streamlit hands back the same file on every rerun. Fingerprint it so one
    # pick uploads once, instead of committing a duplicate on each interaction.
    blob = f.getvalue()
    stamp = f"{f.name}:{len(blob)}:{hashlib.sha256(blob).hexdigest()[:16]}"
    done = st.session_state.get(f"_up_done_{key}")
    if done and done[0] == stamp:
        return done[1]

    ok, err = validate_upload(f, kind)
    if not ok:
        st.error(err, icon="🚫")
        return None
    try:
        with st.spinner("Uploading…"):
            url = D.upload(folder, f)
        st.session_state[f"_up_done_{key}"] = (stamp, url)
        st.success(f"Uploaded {f.name}", icon="✅")
        return url
    except Exception as exc:
        st.error(f"Upload failed: {exc}", icon="🚫")
        return None


def _preview(url: str, kind: str = "image") -> None:
    if not url:
        return
    if kind == "image":
        _md(
            f'<img src="{esc(url)}" style="max-height:150px;border:1px solid var(--line);'
            'object-fit:cover" alt="preview">'
        )
    else:
        _md(f'<video src="{esc(url)}" style="max-height:190px" controls muted></video>')


# --------------------------------------------------------------------------
def _tab_overview(c: dict) -> None:
    ok, msg = D.store_status()
    cls = "ok" if ok else "bad"
    store = D.get_store()
    kind = "GitHub (permanent)" if isinstance(store, GitHubStore) else "Local disk (temporary)"
    _md(
        f'<div style="margin-bottom:20px"><span class="hv-pill {cls}">{esc(msg)}</span> '
        f'<span class="hv-pill">Storage: {esc(kind)}</span></div>'
    )
    if not isinstance(store, GitHubStore):
        why = D.storage_diagnosis()
        if why:
            st.warning(
                "Running on temporary storage — anything saved now is **lost when the "
                "app restarts**.\n\nIn the app's Secrets: " + "; ".join(why) + "."
                "\n\nOpen **Manage app → Settings → Secrets**, fix that, and save. "
                "The change takes about a minute.",
                icon="⚠️",
            )
        else:
            # The secrets are complete, so the app simply started before they
            # were saved and cached the temporary backend.
            st.warning(
                "Your GitHub secrets look complete, but this app started **before** "
                "they were saved, so it is still holding the temporary storage it "
                "picked up at boot. Reconnect to pick them up — no reboot needed.",
                icon="🔌",
            )
            if st.button("🔌 Reconnect storage", type="primary"):
                D.reset_store()
                st.rerun()
    elif not ok:
        st.error(msg, icon="🚫")

    pending = sum(1 for m in c["messages"] if not m.get("approved"))
    cols = st.columns(5)
    for col, (k, v) in zip(
        cols,
        [
            ("Projects", len(c["projects"])),
            ("Milestones", len(c["timeline"])),
            ("Stills", len(c["gallery"])),
            ("Press", len(c["press"])),
            ("Messages waiting", pending),
        ],
    ):
        col.metric(k, v)

    st.divider()
    a, b, c = st.columns(3)
    if a.button("↻ Refresh content", use_container_width=True):
        D.bump()
        st.rerun()
    if b.button("🔌 Reconnect storage", use_container_width=True,
                help="Re-reads the app's secrets and rebuilds the GitHub connection."):
        D.reset_store()
        st.rerun()
    c.link_button("View the public site ↗", "?", use_container_width=True)

    st.caption(f"Last saved: {c['site'].get('updated_at') or 'never'}")


# --------------------------------------------------------------------------
def _tab_profile(c: dict) -> None:
    s = dict(c["site"])
    st.subheader("Identity")
    a, b = st.columns(2)
    s["name"] = a.text_input("Full name", s.get("name", ""))
    s["short_name"] = b.text_input("Short name (intro screen)", s.get("short_name", ""))
    a, b = st.columns(2)
    s["eyebrow"] = a.text_input("Job label", s.get("eyebrow", ""), help="Shown top-left of the hero")
    s["location"] = b.text_input("Location", s.get("location", ""))
    s["roles"] = [
        r.strip()
        for r in st.text_input(
            "Disciplines (comma separated) — these also scroll in the marquee",
            ", ".join(s.get("roles") or []),
        ).split(",")
        if r.strip()
    ]
    s["tagline"] = st.text_area("Tagline (big italic line in the hero)", s.get("tagline", ""), height=80)

    st.subheader("Words")
    s["statement"] = st.text_area("Statement (the big pull quote)", s.get("statement", ""), height=130)
    s["bio"] = st.text_area("Short bio", s.get("bio", ""), height=130)

    st.subheader("Contact")
    a, b = st.columns(2)
    s["email"] = a.text_input("Email", s.get("email", ""))
    s["phone"] = b.text_input("Phone (optional)", s.get("phone", ""))
    a, b = st.columns([1, 2])
    s["available"] = a.toggle("Show availability badge", value=bool(s.get("available", True)))
    s["available_text"] = b.text_input("Availability text", s.get("available_text", ""))

    st.markdown("**Social links**")
    socials = list(s.get("socials") or [])
    rows = st.number_input(
        "How many links", min_value=0, max_value=10, value=len(socials), step=1, key="nsoc"
    )
    new_socials = []
    for i in range(int(rows)):
        cur = socials[i] if i < len(socials) else {"label": "", "url": ""}
        a, b = st.columns([1, 3])
        lab = a.text_input(f"Label {i+1}", cur.get("label", ""), key=f"sl{i}", label_visibility="collapsed", placeholder="Instagram")
        url = b.text_input(f"URL {i+1}", cur.get("url", ""), key=f"su{i}", label_visibility="collapsed", placeholder="https://…")
        if lab.strip() and url.strip():
            if not safe_url(url):
                st.caption(f"⚠️ “{lab}” — links must start with https://")
            else:
                new_socials.append({"label": lab.strip(), "url": url.strip()})
    s["socials"] = new_socials

    st.subheader("Hero & portrait media")
    a, b, cc = st.columns(3)
    with a:
        st.caption("Hero background image")
        _preview(s.get("hero_image", ""))
        u = _upload("Replace hero image", "hero", "image", "up_hero")
        if u:
            s["hero_image"] = u
        if s.get("hero_image") and st.button("Remove hero image", key="rm_hero"):
            s["hero_image"] = ""
    with b:
        st.caption("Hero background video (loops, muted, ≤20 MB)")
        _preview(s.get("hero_video", ""), "video")
        u = _upload("Replace hero video", "hero", "video", "up_herov")
        if u:
            s["hero_video"] = u
        if s.get("hero_video") and st.button("Remove hero video", key="rm_herov"):
            s["hero_video"] = ""
    with cc:
        st.caption("Portrait")
        _preview(s.get("portrait", ""))
        u = _upload("Replace portrait", "portrait", "image", "up_portrait")
        if u:
            s["portrait"] = u
        if s.get("portrait") and st.button("Remove portrait", key="rm_port"):
            s["portrait"] = ""

    st.subheader("Showreel")
    s["showreel_url"] = st.text_input(
        "YouTube or Vimeo link", s.get("showreel_url", ""),
        help="Only YouTube and Vimeo links are embedded, for safety.",
    )
    if s["showreel_url"]:
        from hv_security import embed_src

        if not embed_src(s["showreel_url"])[0]:
            st.warning("That link isn't a recognised YouTube or Vimeo video.", icon="⚠️")
    st.caption("Or upload the reel directly (up to 20 MB). An uploaded file wins over the link.")
    if s.get("showreel_file"):
        _preview(s["showreel_file"], "video")
    u = _upload("Upload showreel video", "showreel", "video", "up_reel")
    if u:
        s["showreel_file"] = u
    if s.get("showreel_file") and st.button("Remove uploaded reel", key="rm_reel"):
        s["showreel_file"] = ""
    s["showreel_caption"] = st.text_input("Caption under the reel", s.get("showreel_caption", ""))

    st.divider()
    if st.button("💾 Save profile", type="primary", use_container_width=True):
        if _guarded(lambda: D.save_site(s)):
            st.rerun()


# --------------------------------------------------------------------------
def _tab_projects(c: dict) -> None:
    projects = list(c["projects"])
    labels = ["➕ New project"] + [
        f"{p.get('title') or 'Untitled'} · {p.get('year') or '—'}" for p in projects
    ]
    choice = st.selectbox("Pick a project to edit", labels, key="proj_pick")
    idx = labels.index(choice) - 1
    p = dict(D.DEFAULT_PROJECT) if idx < 0 else {**D.DEFAULT_PROJECT, **projects[idx]}

    a, b, cc = st.columns([3, 1, 1])
    p["title"] = a.text_input("Title", p.get("title", ""))
    p["year"] = b.text_input("Year", str(p.get("year") or ""))
    p["order"] = cc.number_input("Sort weight", value=int(p.get("order") or 0), step=1,
                                 help="Higher shows first")
    a, b, cc = st.columns(3)
    p["category"] = a.selectbox(
        "Format", D.CATEGORIES,
        index=D.CATEGORIES.index(p["category"]) if p.get("category") in D.CATEGORIES else 0,
    )
    p["role"] = b.text_input("Your role", p.get("role", ""))
    p["status"] = cc.selectbox(
        "Status", D.STATUSES,
        index=D.STATUSES.index(p["status"]) if p.get("status") in D.STATUSES else 0,
    )
    a, b, cc = st.columns(3)
    p["runtime"] = a.text_input("Runtime", str(p.get("runtime") or ""), placeholder="18 min")
    p["shot_on"] = b.text_input("Shot on", str(p.get("shot_on") or ""), placeholder="Digital / 16mm")
    p["ratio"] = cc.text_input("Aspect ratio", str(p.get("ratio") or ""), placeholder="2.39:1")
    p["logline"] = st.text_input("Logline (one line, shown on hover)", p.get("logline", ""))
    p["synopsis"] = st.text_area("Synopsis", p.get("synopsis", ""), height=140)
    p["credits"] = st.text_area("Credits (one per line)", p.get("credits", ""), height=110)
    a, b = st.columns(2)
    p["video_url"] = a.text_input(
        "YouTube / Vimeo link", p.get("video_url", ""),
        help="Best for anything longer than a minute or two.",
    )
    p["link"] = b.text_input("External link (optional)", p.get("link", ""))

    st.markdown("**Video file for this project**")
    st.caption(
        "Upload a clip directly (MP4, WebM or MOV, up to 20 MB). An uploaded file "
        "plays instead of the link above. For anything longer, put it on YouTube or "
        "Vimeo and paste the link — there is no size limit that way."
    )
    if p.get("video_file"):
        _preview(p["video_file"], "video")
    u = _upload("Upload a video", "projects", "video", f"up_vid_{idx}")
    if u:
        p["video_file"] = u
    if p.get("video_file") and st.button("Remove uploaded video", key=f"rmv{idx}"):
        p["video_file"] = ""
    p["tags"] = [t.strip() for t in st.text_input("Tags (comma separated)", ", ".join(p.get("tags") or [])).split(",") if t.strip()]
    a, b = st.columns(2)
    p["featured"] = a.toggle("Feature it (wide card)", value=bool(p.get("featured")))
    p["published"] = b.toggle("Visible on the public site", value=bool(p.get("published", True)))

    st.markdown("**Poster**")
    _preview(p.get("poster", ""))
    u = _upload("Upload poster / key frame", "projects", "image", f"up_poster_{idx}")
    if u:
        p["poster"] = u
    if p.get("poster") and st.button("Remove poster", key=f"rmp{idx}"):
        p["poster"] = ""

    st.markdown("**Gallery stills for this project**")
    gal = list(p.get("gallery") or [])
    if gal:
        cols = st.columns(min(4, len(gal)))
        for i, gurl in enumerate(gal):
            with cols[i % len(cols)]:
                _preview(gurl)
                if st.button("Remove", key=f"rmg{idx}_{i}"):
                    gal.pop(i)
                    p["gallery"] = gal
                    if _guarded(lambda: _persist_projects(projects, idx, p), "Still removed."):
                        st.rerun()
    u = _upload("Add a still", "projects", "image", f"up_gal_{idx}")
    if u:
        gal.append(u)
    p["gallery"] = gal

    st.divider()
    a, b = st.columns([3, 1])
    if a.button("💾 Save project", type="primary", use_container_width=True):
        if not p.get("title", "").strip():
            st.error("Give the project a title first.", icon="🚫")
        elif _guarded(lambda: _persist_projects(projects, idx, p)):
            st.rerun()
    if idx >= 0:
        if b.button("🗑 Delete", use_container_width=True):
            if st.session_state.get(f"confirm_del_{idx}"):
                projects.pop(idx)
                if _guarded(lambda: D.save(D.PROJECTS_PATH, projects, "delete project"),
                            "Project deleted."):
                    st.session_state.pop(f"confirm_del_{idx}", None)
                    st.rerun()
            else:
                st.session_state[f"confirm_del_{idx}"] = True
                st.warning("Press Delete once more to confirm.", icon="⚠️")


def _persist_projects(projects: list[dict], idx: int, p: dict) -> None:
    if not p.get("id"):
        p["id"] = D.new_id()
    if idx < 0:
        projects.append(p)
    else:
        projects[idx] = p
    D.save(D.PROJECTS_PATH, projects, "project")


# --------------------------------------------------------------------------
def _simple_list(
    c: dict, key: str, path: str, fields: list[tuple[str, str, str]], title: str,
    required: str | None = None, heading: str | None = None,
) -> None:
    """Generic editor for timeline / press / gallery style lists."""
    items = list(c[key])
    st.caption(f"{len(items)} item(s)")

    with st.expander(f"➕ Add {title}", expanded=not items):
        new: dict[str, Any] = {}
        for fkey, flabel, ftype in fields:
            if ftype == "text":
                new[fkey] = st.text_input(flabel, key=f"n_{key}_{fkey}")
            elif ftype == "area":
                new[fkey] = st.text_area(flabel, key=f"n_{key}_{fkey}", height=110)
            elif ftype == "image":
                u = _upload(flabel, key, "image", f"n_{key}_{fkey}_up")
                new[fkey] = u or ""
        req = required or fields[0][0]
        req_label = next((lbl for k, lbl, _ in fields if k == req), req)
        if st.button(f"Add {title}", key=f"add_{key}", type="primary"):
            if not str(new.get(req) or "").strip():
                st.error(f"{req_label} is required.", icon="🚫")
            else:
                new["id"] = D.new_id()
                items.append(new)
                if not _guarded(lambda: D.save(path, items, f"add {title}"), f"{title} added."):
                    return
                for fk, _l, ft in fields:
                    st.session_state.pop(f"n_{key}_{fk}", None)
                    st.session_state.pop(f"_up_done_n_{key}_{fk}_up", None)
                st.rerun()

    for i, it in enumerate(items):
        head = str(it.get(heading or fields[0][0]) or "Untitled")[:70]
        with st.expander(f"{i+1}. {head}"):
            edited = dict(it)
            for fkey, flabel, ftype in fields:
                if ftype == "text":
                    edited[fkey] = st.text_input(flabel, it.get(fkey, ""), key=f"e_{key}_{i}_{fkey}")
                elif ftype == "area":
                    edited[fkey] = st.text_area(flabel, it.get(fkey, ""), key=f"e_{key}_{i}_{fkey}", height=110)
                elif ftype == "image":
                    _preview(it.get(fkey, ""))
                    u = _upload("Replace image", key, "image", f"e_{key}_{i}_{fkey}_up")
                    if u:
                        edited[fkey] = u
            a, b = st.columns([3, 1])
            if a.button("Save", key=f"s_{key}_{i}", type="primary", use_container_width=True):
                items[i] = edited
                if _guarded(lambda: D.save(path, items, f"edit {title}")):
                    st.rerun()
            if b.button("Delete", key=f"d_{key}_{i}", use_container_width=True):
                items.pop(i)
                if _guarded(lambda: D.save(path, items, f"delete {title}"), f"{title} deleted."):
                    st.rerun()


# --------------------------------------------------------------------------
def _tab_messages(c: dict) -> None:
    msgs = list(c["messages"])
    if not msgs:
        st.info("No messages yet.", icon="📭")
        return
    pending = [m for m in msgs if not m.get("approved")]
    st.caption(f"{len(pending)} waiting · {len(msgs) - len(pending)} published")

    view = st.radio("Show", ["Waiting", "Published", "All"], horizontal=True, key="msgview")
    for i, m in enumerate(msgs):
        appr = bool(m.get("approved"))
        if view == "Waiting" and appr:
            continue
        if view == "Published" and not appr:
            continue
        with st.container(border=True):
            st.markdown(
                f"**{m.get('name')}** · {m.get('role') or '—'} · {m.get('at')}"
            )
            st.write(m.get("message", ""))
            a, b = st.columns(2)
            if not appr:
                if a.button("✓ Approve", key=f"ap{i}", type="primary", use_container_width=True):
                    msgs[i]["approved"] = True
                    if _guarded(lambda: D.save(D.MESSAGES_PATH, msgs, "approve message"),
                                "Published."):
                        st.rerun()
            else:
                if a.button("Hide", key=f"hd{i}", use_container_width=True):
                    msgs[i]["approved"] = False
                    if _guarded(lambda: D.save(D.MESSAGES_PATH, msgs, "hide message"), "Hidden."):
                        st.rerun()
            if b.button("🗑 Delete", key=f"dm{i}", use_container_width=True):
                msgs.pop(i)
                if _guarded(lambda: D.save(D.MESSAGES_PATH, msgs, "delete message"), "Deleted."):
                    st.rerun()


# --------------------------------------------------------------------------
def _tab_appearance(c: dict) -> None:
    s = dict(c["site"])
    a, b, cc = st.columns(3)
    s["accent"] = a.color_picker("Accent colour", s.get("accent", "#57C8B0"),
                                 help="Leads every rule, label and active state.")
    s["accent_2"] = b.color_picker("Highlight colour", s.get("accent_2", "#E4813F"),
                                   help="Used sparingly — availability dot and status flags.")
    s["grain"] = cc.toggle("Film grain overlay", value=bool(s.get("grain", True)))

    st.subheader("Sections")
    st.caption("Turn a section off to hide it from the public site, and rename any heading.")
    secs = dict(s.get("sections", {}))
    titles = dict(s.get("section_titles", {}))
    for k in D.DEFAULT_SITE["sections"]:
        a, b = st.columns([1, 3])
        secs[k] = a.toggle(k.title(), value=bool(secs.get(k, True)), key=f"sec_{k}")
        titles[k] = b.text_input(
            f"{k} heading", titles.get(k, ""), key=f"tit_{k}", label_visibility="collapsed"
        )
    s["sections"] = secs
    s["section_titles"] = titles

    st.subheader("Guestbook")
    a, b = st.columns(2)
    s["guestbook_open"] = a.toggle("Accept new messages", value=bool(s.get("guestbook_open", True)))
    s["guestbook_moderated"] = b.toggle(
        "Approve before publishing", value=bool(s.get("guestbook_moderated", True)),
        help="Strongly recommended — stops spam appearing on the site.",
    )
    s["footer_note"] = st.text_input("Footer note", s.get("footer_note", ""))

    st.divider()
    if st.button("💾 Save appearance", type="primary", use_container_width=True):
        if _guarded(lambda: D.save_site(s)):
            st.rerun()

    st.subheader("Backup")
    st.download_button(
        "⬇ Download everything as JSON",
        data=json.dumps(c, indent=2, ensure_ascii=False),
        file_name="portfolio-backup.json",
        mime="application/json",
        use_container_width=True,
    )


# --------------------------------------------------------------------------
def render(content: dict) -> None:
    site = content["site"]
    _md(
        f"""
<div class="hv-admin-head">
  <h1 class="hv-admin-title">Control <i>room</i></h1>
  <div><span class="hv-pill">{esc(site.get('name'))}</span></div>
</div>"""
    )
    with st.container(key="hv_admin"):
        top = st.columns([1, 1, 6])
        if top[0].button("← Public site", use_container_width=True):
            st.query_params.clear()
            st.rerun()
        if top[1].button("Log out", use_container_width=True):
            logout()
            st.query_params.clear()
            st.rerun()

        tabs = st.tabs(
            ["Overview", "Profile", "Work", "Journey", "Stills", "Press", "Messages", "Appearance"]
        )
        with tabs[0]:
            _tab_overview(content)
        with tabs[1]:
            _tab_profile(content)
        with tabs[2]:
            _tab_projects(content)
        with tabs[3]:
            _simple_list(
                content, "timeline", D.TIMELINE_PATH,
                [("year", "Year", "text"), ("title", "What happened", "text"), ("body", "Details", "area")],
                "milestone",
            )
        with tabs[4]:
            _simple_list(
                content, "gallery", D.GALLERY_PATH,
                [("caption", "Caption", "text"), ("url", "Image", "image")],
                "still", required="url", heading="caption",
            )
        with tabs[5]:
            _simple_list(
                content, "press", D.PRESS_PATH,
                [("quote", "Quote or award", "area"), ("source", "Source", "text"), ("year", "Year", "text")],
                "mention",
            )
        with tabs[6]:
            _tab_messages(content)
        with tabs[7]:
            _tab_appearance(content)
