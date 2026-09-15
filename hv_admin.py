"""Password-protected admin console. Everything the owner can change."""
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
        st.link_button("← Back to the site", "?", width="content")
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
        if kind == "video":
            from hv_security import has_audio_track
            st.session_state[f"_audio_{url}"] = has_audio_track(blob)
        st.session_state[f"_up_done_{key}"] = (stamp, url)
        st.success(f"Uploaded {f.name}", icon="✅")
        return url
    except Exception as exc:
        st.error(f"Upload failed: {exc}", icon="🚫")
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _probe(url: str) -> tuple[str, str]:
    from hv_security import probe_embed
    return probe_embed(url)


def _link_status(url: str) -> None:
    """Tell the owner straight away whether a link will actually play."""
    if not (url or "").strip():
        return
    with st.spinner("Checking the link…"):
        status, message = _probe(url.strip())
    if not status:
        return
    if status == "ok":
        st.success(message, icon="▶️")
    elif status == "private":
        st.error(message, icon="🔒")
    elif status in ("missing", "unsupported"):
        st.warning(message, icon="⚠️")
    elif status == "blocked":
        st.warning(message, icon="🚫")
    else:
        st.info(message, icon="ℹ️")



# --------------------------------------------------------------------------
# Media fields
# --------------------------------------------------------------------------
# A Streamlit file_uploader keeps holding the chosen file across reruns, and a
# widget's state cannot be cleared after the widget exists. So "Remove" has to
# retire the uploader by giving it a fresh key, or the next rerun immediately
# re-applies the file that was just removed.
def _uploader_key(base: str) -> str:
    return f"{base}__{st.session_state.get(f'_gen_{base}', 0)}"


def _retire_uploader(base: str) -> None:
    st.session_state.pop(f"_up_done_{_uploader_key(base)}", None)
    st.session_state[f"_gen_{base}"] = st.session_state.get(f"_gen_{base}", 0) + 1


def _media_field(
    holder: dict,
    field: str,
    *,
    base: str,
    folder: str,
    kind: str,
    label: str,
    on_change=None,
) -> None:
    """Preview + upload + remove for one media field.

    `on_change` persists the record straight away, so Remove actually removes
    rather than quietly reverting on the next interaction.
    """
    if holder.get(field):
        _preview(holder[field], "video" if kind == "video" else "image")

    new_url = _upload(f"Upload {label}", folder, kind, _uploader_key(base))
    if new_url and new_url != holder.get(field):
        holder[field] = new_url
        if on_change is not None:
            _guarded(on_change, f"{label.capitalize()} saved.")
        _retire_uploader(base)
        st.rerun()

    if holder.get(field) and st.button(f"Remove {label}", key=f"rm_{base}"):
        holder[field] = ""
        _retire_uploader(base)
        if on_change is not None:
            _guarded(on_change, f"{label.capitalize()} removed.")
        else:
            st.success(f"{label.capitalize()} removed.", icon="✅")
        st.rerun()


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

    ok_p, msg_p = D.private_status()
    if ok_p:
        _md(f'<div style="margin-bottom:18px"><span class="hv-pill ok">🔒 Messages private · {esc(msg_p)}</span></div>')
    else:
        _md(f'<div style="margin-bottom:18px"><span class="hv-pill warn">🔓 Messages public · {esc(msg_p)}</span></div>')

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
    col_a, col_b, col_c = st.columns(3)
    if col_a.button("↻ Refresh content", width="stretch"):
        D.bump()
        st.rerun()
    if col_b.button("🔌 Reconnect storage", width="stretch",
                    help="Re-reads the app's secrets and rebuilds the GitHub connection."):
        D.reset_store()
        st.rerun()
    col_c.link_button("View the public site ↗", "?", width="stretch")

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
    st.caption("Uploading or removing here saves the profile straight away.")
    save_profile = lambda: D.save_site(s)  # noqa: E731
    a, b, cc = st.columns(3)
    with a:
        st.caption("Hero background image")
        _media_field(s, "hero_image", base="up_hero", folder="hero",
                     kind="image", label="hero image", on_change=save_profile)
    with b:
        st.caption("Hero background video (loops, muted, ≤20 MB)")
        _media_field(s, "hero_video", base="up_herov", folder="hero",
                     kind="video", label="hero video", on_change=save_profile)
    with cc:
        st.caption("Portrait")
        _media_field(s, "portrait", base="up_portrait", folder="portrait",
                     kind="image", label="portrait", on_change=save_profile)

    st.subheader("Showreel")
    s["showreel_url"] = st.text_input(
        "YouTube or Vimeo link", s.get("showreel_url", ""),
        help="Only YouTube and Vimeo links are embedded, for safety.",
    )
    _link_status(s.get("showreel_url", ""))
    st.caption(
        "You can also upload the reel directly (up to 20 MB). If you have both a "
        "link and an uploaded file, the site shows both players."
    )
    _media_field(s, "showreel_file", base="up_reel", folder="showreel",
                 kind="video", label="uploaded reel", on_change=save_profile)
    s["showreel_caption"] = st.text_input("Caption under the reel", s.get("showreel_caption", ""))

    st.divider()
    if st.button("💾 Save profile", type="primary", width="stretch"):
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
    p["link"] = st.text_input(
        "External link (optional)", p.get("link", ""),
        help="A festival page, a review — anything worth linking out to.",
    )
    p["tags"] = [t.strip() for t in st.text_input("Tags (comma separated)", ", ".join(p.get("tags") or [])).split(",") if t.strip()]
    a, b = st.columns(2)
    p["featured"] = a.toggle("Feature it (wide card)", value=bool(p.get("featured")))
    p["published"] = b.toggle("Visible on the public site", value=bool(p.get("published", True)))

    st.markdown("**Poster**")
    st.caption("The single frame that represents this project on the contact sheet.")
    _media_field(p, "poster", base=f"up_poster_{idx}", folder="projects",
                 kind="image", label="poster",
                 on_change=(lambda: _persist_projects(projects, idx, p)) if idx >= 0 else None)

    st.divider()
    st.markdown("**Videos**")
    st.caption(
        "Add as many as you like — YouTube/Vimeo links, uploaded clips, or both. "
        "Every one of them appears on the project page."
    )
    _video_manager(p, projects, idx)

    st.divider()
    st.markdown("**Stills**")
    st.caption("Images shown in a grid on the project page.")
    _gallery_manager(p, projects, idx)

    st.divider()
    a, b = st.columns([3, 1])
    if a.button("💾 Save project", type="primary", width="stretch"):
        if not p.get("title", "").strip():
            st.error("Give the project a title first.", icon="🚫")
        elif _guarded(lambda: _persist_projects(projects, idx, p)):
            st.rerun()
    if idx >= 0:
        if b.button("🗑 Delete", width="stretch"):
            if st.session_state.get(f"confirm_del_{idx}"):
                projects.pop(idx)
                if _guarded(lambda: D.save(D.PROJECTS_PATH, projects, "delete project"),
                            "Project deleted."):
                    st.session_state.pop(f"confirm_del_{idx}", None)
                    st.rerun()
            else:
                st.session_state[f"confirm_del_{idx}"] = True
                st.warning("Press Delete once more to confirm.", icon="⚠️")


def _save_project_now(projects: list[dict], idx: int, p: dict):
    """Persist immediately, but only for a project that already exists."""
    if idx < 0:
        return None
    return lambda: _persist_projects(projects, idx, p)


def _video_manager(p: dict, projects: list[dict], idx: int) -> None:
    """Any number of links and uploads, each removable."""
    videos = list(p.get("videos") or [])
    persist = _save_project_now(projects, idx, p)

    notice = st.session_state.pop("_silent_notice", None)
    if notice:
        st.warning(
            "That clip has **no audio track** — the file itself is silent, so it will "
            "play without sound. Re-export it with audio if it should have any.",
            icon="🔇",
        )

    for i, v in enumerate(videos):
        url = str((v or {}).get("url") or "")
        is_file = (v or {}).get("type") == "file"
        with st.container(border=True):
            head, act = st.columns([5, 1])
            tag = ("🎞 Uploaded clip" if is_file else "▶️ Link") + f" · {i + 1}"
            if (v or {}).get("silent"):
                tag += "  ·  🔇 no audio track"
            head.caption(tag)
            if is_file:
                _preview(url, "video")
            else:
                st.text_input("Link", url, key=f"vlink_{idx}_{i}", disabled=True,
                              label_visibility="collapsed")
                _link_status(url)
            if act.button("Remove", key=f"rmvid_{idx}_{i}", width="stretch"):
                videos.pop(i)
                p["videos"] = videos
                p["video_url"] = ""
                p["video_file"] = ""
                if persist:
                    _guarded(persist, "Video removed.")
                else:
                    st.success("Video removed.", icon="✅")
                st.rerun()

    st.markdown("**Add a YouTube or Vimeo link**")
    new_link = st.text_input(
        "Paste the link", key=f"newvid_{idx}", label_visibility="collapsed",
        placeholder="https://youtu.be/…",
    )
    if new_link.strip():
        _link_status(new_link.strip())
    if st.button("➕ Add this link", key=f"addvid_{idx}"):
        u = new_link.strip()
        from hv_security import embed_src
        if not u:
            st.warning("Paste a link first.", icon="⚠️")
        elif not embed_src(u)[0]:
            st.error("Only YouTube and Vimeo links can be embedded.", icon="🚫")
        elif any(str((v or {}).get("url")) == u for v in videos):
            st.warning("That video is already on this project.", icon="⚠️")
        else:
            videos.append({"type": "link", "url": u})
            p["videos"] = videos
            st.session_state.pop(f"newvid_{idx}", None)
            if persist:
                _guarded(persist, "Link added.")
            else:
                st.success("Link added.", icon="✅")
            st.rerun()

    st.caption(
        "A **Private** YouTube video will never play here — YouTube blocks embedding "
        "for private videos on every website. Set it to **Unlisted** in YouTube "
        "Studio instead: unlisted stays out of search and off your channel, but "
        "plays fine on this site."
    )

    st.markdown("**Or upload a clip** (MP4, WebM, MOV — up to 20 MB)")
    base = f"up_vid_{idx}"
    got = _upload("Upload a video", "projects", "video", _uploader_key(base))
    if got and not any(str((v or {}).get("url")) == got for v in videos):
        entry = {"type": "file", "url": got}
        audio = st.session_state.get(f"_audio_{got}")
        if audio is False:
            entry["silent"] = True
        videos.append(entry)
        p["videos"] = videos
        _retire_uploader(base)
        if persist:
            _guarded(persist, "Video added.")
        else:
            st.success("Video added.", icon="✅")
        if audio is False:
            st.session_state["_silent_notice"] = got
        st.rerun()


def _gallery_manager(p: dict, projects: list[dict], idx: int) -> None:
    """Any number of stills, each removable."""
    gal = [g for g in (p.get("gallery") or []) if str(g or "").strip()]
    persist = _save_project_now(projects, idx, p)

    if gal:
        per_row = 4
        for row_start in range(0, len(gal), per_row):
            row = gal[row_start:row_start + per_row]
            cols = st.columns(per_row)
            for offset, url in enumerate(row):
                i = row_start + offset
                with cols[offset]:
                    _preview(url)
                    if st.button("Remove", key=f"rmstill_{idx}_{i}", width="stretch"):
                        gal.pop(i)
                        p["gallery"] = gal
                        if persist:
                            _guarded(persist, "Still removed.")
                        else:
                            st.success("Still removed.", icon="✅")
                        st.rerun()
    else:
        st.caption("No stills yet.")

    base = f"up_gal_{idx}"
    got = _upload("Add a still", "projects", "image", _uploader_key(base))
    if got and got not in gal:
        gal.append(got)
        p["gallery"] = gal
        _retire_uploader(base)
        if persist:
            _guarded(persist, "Still added.")
        else:
            st.success("Still added.", icon="✅")
        st.rerun()


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
            if a.button("Save", key=f"s_{key}_{i}", type="primary", width="stretch"):
                items[i] = edited
                if _guarded(lambda: D.save(path, items, f"edit {title}")):
                    st.rerun()
            if b.button("Delete", key=f"d_{key}_{i}", width="stretch"):
                items.pop(i)
                if _guarded(lambda: D.save(path, items, f"delete {title}"), f"{title} deleted."):
                    st.rerun()


# --------------------------------------------------------------------------
def _tab_messages(c: dict) -> None:
    ok_p, msg_p = D.private_status()
    if ok_p:
        st.caption(f"🔒 Stored privately — {msg_p}")
    else:
        st.warning(
            "These messages are stored in your **public** repository, so anyone can "
            "read the names and text people send you. Add a `[private]` section to the "
            "app's Secrets pointing at a private repo to move them out of public view.",
            icon="🔓",
        )
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
                if a.button("✓ Approve", key=f"ap{i}", type="primary", width="stretch"):
                    msgs[i]["approved"] = True
                    if _guarded(lambda: D.save(D.MESSAGES_PATH, msgs, "approve message"),
                                "Published."):
                        st.rerun()
            else:
                if a.button("Hide", key=f"hd{i}", width="stretch"):
                    msgs[i]["approved"] = False
                    if _guarded(lambda: D.save(D.MESSAGES_PATH, msgs, "hide message"), "Hidden."):
                        st.rerun()
            if b.button("🗑 Delete", key=f"dm{i}", width="stretch"):
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
    st.caption(
        "Turn a section off to hide it from the public site, and rename any heading. "
        "A section with nothing in it is hidden automatically, so you only need these "
        "for hiding something that *does* have content."
    )
    WHAT = {
        "statement": "your statement, bio and portrait",
        "work": "the project contact sheet — every film you've added",
        "showreel": "the single reel player",
        "timeline": "your milestones, year by year",
        "gallery": "the grid of stills",
        "press": "quotes, awards and recognition",
        "guestbook": "**the contact box visitors write messages to you in**",
    }
    secs = dict(s.get("sections", {}))
    titles = dict(s.get("section_titles", {}))
    for k in D.DEFAULT_SITE["sections"]:
        a, b = st.columns([1, 3])
        secs[k] = a.toggle(k.title(), value=bool(secs.get(k, True)), key=f"sec_{k}")
        titles[k] = b.text_input(
            f"{k} heading", titles.get(k, ""), key=f"tit_{k}", label_visibility="collapsed"
        )
        st.caption(f"↳ {WHAT.get(k, '')}")

    if not secs.get("guestbook", True):
        st.warning(
            "**Guestbook is off, so visitors have no way to message you.** That section "
            "is the contact box on the public site. Turn it back on unless you meant to "
            "remove it.",
            icon="✉️",
        )
    s["sections"] = secs
    s["section_titles"] = titles

    st.subheader("Loading & data use")
    s["cache_hero"] = st.toggle(
        "Keep the hero video on the visitor's device",
        value=bool(s.get("cache_hero", True)),
        help="Stores the background video in the browser's own storage after "
             "the first visit.",
    )
    if s.get("cache_hero", True):
        st.caption(
            "**On.** A visitor downloads the hero video once; every later visit "
            "plays it straight from their device, using no data. A thin progress "
            "line shows while it downloads the first time, and the still image "
            "holds the frame until it's ready. When you upload a new hero video "
            "the old one is deleted from their device automatically and the new "
            "one is fetched — nothing stale is left behind."
        )
    else:
        st.caption(
            "**Off.** The video streams from the CDN on every visit. Browsers "
            "still cache it for about a week on their own, but large files get "
            "evicted and re-downloaded, so returning visitors may pay for it again."
        )

    st.subheader("Guestbook")
    a, b = st.columns(2)
    s["guestbook_open"] = a.toggle("Accept new messages", value=bool(s.get("guestbook_open", True)))
    s["guestbook_moderated"] = b.toggle(
        "Approve before publishing", value=bool(s.get("guestbook_moderated", True)),
        help="Strongly recommended — stops spam appearing on the site.",
    )
    s["footer_note"] = st.text_input("Footer note", s.get("footer_note", ""))

    st.divider()
    if st.button("💾 Save appearance", type="primary", width="stretch"):
        if _guarded(lambda: D.save_site(s)):
            st.rerun()

    st.subheader("Backup")
    st.download_button(
        "⬇ Download everything as JSON",
        data=json.dumps(c, indent=2, ensure_ascii=False),
        file_name="portfolio-backup.json",
        mime="application/json",
        width="stretch",
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
        if top[0].button("← Public site", width="stretch"):
            st.query_params.clear()
            st.rerun()
        if top[1].button("Log out", width="stretch"):
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
