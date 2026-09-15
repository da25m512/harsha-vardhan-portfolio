"""Content model, defaults, and cached load/save helpers."""
from __future__ import annotations

import time
import uuid
from typing import Any

import streamlit as st

from hv_store import MAX_MEDIA_BYTES, GitHubStore, LocalStore, Store

SITE_PATH = "data/site.json"
PROJECTS_PATH = "data/projects.json"
TIMELINE_PATH = "data/timeline.json"
GALLERY_PATH = "data/gallery.json"
PRESS_PATH = "data/press.json"
MESSAGES_PATH = "data/messages.json"

OWNER_NAME = "Marothu Harsha Vardhan"

DEFAULT_SITE: dict[str, Any] = {
    "name": OWNER_NAME,
    "short_name": "Harsha Vardhan",
    "eyebrow": "Portfolio",
    "roles": ["Storyteller", "Visual Thinker"],
    "tagline": "Building a body of work, one frame at a time.",
    "location": "India",
    "available": True,
    "available_text": "Open to new projects",
    "statement": (
        "I am at the beginning of the road, and that is exactly the point. "
        "Every short, every frame, every late night on set is a sentence in a "
        "longer story I am still learning how to tell. This page is where that "
        "story gets written down as it happens."
    ),
    "bio": (
        "Marothu Harsha Vardhan is an emerging artist whose work is driven by "
        "character, silence, and the things people don't say out loud. He is "
        "currently developing his first slate of independent projects."
    ),
    "hero_image": "",
    "hero_video": "",
    "portrait": "",
    "showreel_url": "",
    "showreel_file": "",
    "showreel_caption": "The reel so far",
    "email": "",
    "phone": "",
    "socials": [],
    "accent": "#57C8B0",
    "accent_2": "#E4813F",
    "grain": True,
    "cache_hero": True,
    "sections": {
        "statement": True,
        "work": True,
        "showreel": True,
        "timeline": True,
        "gallery": True,
        "press": True,
        "guestbook": True,
    },
    "section_titles": {
        "statement": "The Idea",
        "work": "Selected Work",
        "showreel": "Showreel",
        "timeline": "The Journey",
        "gallery": "Stills",
        "press": "Words & Recognition",
        "guestbook": "Say Something",
    },
    "guestbook_open": True,
    "guestbook_moderated": True,
    "footer_note": "Made with intention.",
    "updated_at": "",
}

DEFAULT_PROJECT: dict[str, Any] = {
    "id": "",
    "title": "",
    "year": "",
    "category": "Short Film",
    "role": "",
    "status": "Released",
    "runtime": "",
    "ratio": "",
    "shot_on": "",
    "logline": "",
    "synopsis": "",
    "credits": "",
    "poster": "",
    "gallery": [],
    "videos": [],          # [{"type": "link"|"file", "url": str}]
    "video_url": "",       # legacy single link, migrated into `videos`
    "video_file": "",      # legacy single upload, migrated into `videos`
    "tags": [],
    "featured": False,
    "published": True,
    "order": 0,
    "link": "",
}

CATEGORIES = [
    "Short Film",
    "Feature Film",
    "Music Video",
    "Advertisement",
    "Documentary",
    "Web Series",
    "Concept / Spec",
    "Other",
]

STATUSES = ["Released", "In Post", "In Production", "Development", "Concept"]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime())


# --------------------------------------------------------------------------
# Store wiring
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _build_store(token: str, owner: str, repo: str, branch: str) -> Store:
    """Cached on its arguments, so editing the app's secrets swaps the
    backend on the next rerun instead of needing a reboot."""
    if token and owner and repo:
        return GitHubStore(token, owner, repo, branch)
    return LocalStore()


def _github_secrets() -> tuple[str, str, str, str]:
    try:
        gh = dict(st.secrets.get("github", {}))
    except Exception:
        gh = {}
    return (
        str(gh.get("token", "") or "").strip(),
        str(gh.get("owner", "") or "").strip(),
        str(gh.get("repo", "") or "").strip(),
        str(gh.get("branch", "") or "content").strip() or "content",
    )


def get_store() -> Store:
    return _build_store(*_github_secrets())


# --------------------------------------------------------------------------
# Private storage
# --------------------------------------------------------------------------
# Visitor messages are other people's names and words, so they do not belong
# in a public repository. Point `[private]` at a private repo and the files
# listed there are read and written through the API with the token instead of
# sitting where anyone can read them. Media stays public, because a browser
# has to be able to fetch it without credentials.
DEFAULT_PRIVATE_FILES = ("messages",)

_PATH_BY_NAME = {
    "site": SITE_PATH,
    "projects": PROJECTS_PATH,
    "timeline": TIMELINE_PATH,
    "gallery": GALLERY_PATH,
    "press": PRESS_PATH,
    "messages": MESSAGES_PATH,
}


def _private_secrets() -> tuple[str, str, str, str, tuple[str, ...]]:
    try:
        pv = dict(st.secrets.get("private", {}))
    except Exception:
        pv = {}
    token, owner, repo, branch = _github_secrets()
    names = pv.get("files") or DEFAULT_PRIVATE_FILES
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]
    return (
        str(pv.get("token", "") or token).strip(),
        str(pv.get("owner", "") or owner).strip(),
        str(pv.get("repo", "") or "").strip(),
        str(pv.get("branch", "") or "main").strip() or "main",
        tuple(str(n).strip() for n in names if str(n).strip()),
    )


@st.cache_data(ttl=300, show_spinner=False)
def _private_reachable(token: str, owner: str, repo: str, branch: str) -> bool:
    """Can the token actually read and write that private repo?

    Checked before anything is routed there, so a half-finished setup falls
    back to the public repo instead of silently dropping messages.
    """
    if not (token and owner and repo):
        return False
    try:
        ok, _msg = GitHubStore(token, owner, repo, branch).check()
        return bool(ok)
    except Exception:
        return False


def private_paths() -> set[str]:
    """Which data files actually live in the private repo right now."""
    token, owner, repo, branch, names = _private_secrets()
    if not _private_reachable(token, owner, repo, branch):
        return set()
    return {_PATH_BY_NAME[n] for n in names if n in _PATH_BY_NAME}


def get_private_store() -> Store:
    token, owner, repo, branch, _names = _private_secrets()
    if _private_reachable(token, owner, repo, branch):
        return _build_store(token, owner, repo, branch)
    return get_store()


def store_for(path: str) -> Store:
    """The backend that owns this file."""
    return get_private_store() if path in private_paths() else get_store()


def private_status() -> tuple[bool, str]:
    token, owner, repo, branch, names = _private_secrets()
    if not repo:
        return False, "Not set up — messages are stored in the public repo."
    if not token:
        return False, "A private repo is named but no token can reach it."
    if not _private_reachable(token, owner, repo, branch):
        try:
            _ok, why = GitHubStore(token, owner, repo, branch).check()
        except Exception as exc:
            why = str(exc)
        return False, (
            f"Can't reach {owner}/{repo} — {why} Messages are still going to the "
            "public repo until this is fixed."
        )
    return True, f"{owner}/{repo}@{branch} · holding: {', '.join(names)}"


def reset_store() -> None:
    """Drop the cached backend so the next call re-reads the secrets.

    Streamlit keeps a cached resource for the life of the app process, so an
    app that booted before its secrets were saved would otherwise keep using
    temporary storage until someone rebooted it."""
    for cached in (_build_store, _private_reachable):
        fn = getattr(cached, "clear", None)
        if callable(fn):
            fn()
    clear_cache()


def storage_diagnosis() -> list[str]:
    """Plain-language reasons the GitHub backend is not in use."""
    token, owner, repo, _ = _github_secrets()
    missing = []
    if not token:
        missing.append("`token` is empty")
    elif not (token.startswith("github_pat_") or token.startswith("ghp_")):
        missing.append("`token` doesn't look like a GitHub token (should start with `github_pat_`)")
    if not owner:
        missing.append("`owner` is empty")
    if not repo:
        missing.append("`repo` is empty")
    return missing


def store_status() -> tuple[bool, str]:
    s = get_store()
    if isinstance(s, GitHubStore):
        return s.check()
    return True, s.label + " (set GitHub secrets to persist across restarts)"


def bump() -> None:
    """Invalidate every cached read after a write."""
    st.session_state["_content_version"] = st.session_state.get("_content_version", 0) + 1
    clear_cache()


def clear_cache() -> None:
    fn = getattr(_fetch, "clear", None)
    if callable(fn):
        fn()


def _version() -> int:
    return st.session_state.get("_content_version", 0)


@st.cache_data(ttl=90, show_spinner=False)
def _fetch(path: str, default_json: str, version: int) -> Any:
    import json

    return store_for(path).read_json(path, json.loads(default_json))


def load_content() -> dict[str, Any]:
    """Everything the page needs, in one dict."""
    import json

    v = _version()
    site = _fetch(SITE_PATH, json.dumps(DEFAULT_SITE), v)
    # forward-compatible merge so new default keys appear for old saved files
    merged = {**DEFAULT_SITE, **(site or {})}
    merged["sections"] = {**DEFAULT_SITE["sections"], **(site or {}).get("sections", {})}
    merged["section_titles"] = {
        **DEFAULT_SITE["section_titles"],
        **(site or {}).get("section_titles", {}),
    }
    return {
        "site": merged,
        "projects": normalise_projects(_fetch(PROJECTS_PATH, "[]", v) or []),
        "timeline": _fetch(TIMELINE_PATH, "[]", v) or [],
        "gallery": _fetch(GALLERY_PATH, "[]", v) or [],
        "press": _fetch(PRESS_PATH, "[]", v) or [],
        "messages": _fetch(MESSAGES_PATH, "[]", v) or [],
    }



def save(path: str, obj: Any, what: str) -> None:
    store_for(path).write_json(path, obj, f"content: update {what}")
    bump()


def save_site(site: dict) -> None:
    site["updated_at"] = now_stamp()
    save(SITE_PATH, site, "site settings")


def upload_bytes(folder: str, filename: str, blob: bytes) -> str:
    """Persist raw bytes as media and return a public URL."""
    from hv_store import new_media_path

    path = new_media_path(folder, filename)
    return get_store().write_binary(path, blob, f"content: add {path}")


def upload(folder: str, uploaded_file) -> str:
    """Persist a Streamlit UploadedFile and return a public URL."""
    return upload_bytes(folder, uploaded_file.name, uploaded_file.getvalue())


def normalise_project(p: dict) -> dict:
    """Bring a stored project up to the current shape.

    Projects used to carry one link and one uploaded file. Both now live in
    an ordered `videos` list so a project can have as many of each as it
    likes; the old fields are folded in once and then left alone.
    """
    out = {**DEFAULT_PROJECT, **(p or {})}
    videos = [
        v for v in (out.get("videos") or [])
        if isinstance(v, dict) and str(v.get("url") or "").strip()
    ]
    known = {str(v.get("url")).strip() for v in videos}
    for legacy_key, vtype in (("video_file", "file"), ("video_url", "link")):
        url = str(out.get(legacy_key) or "").strip()
        if url and url not in known:
            videos.append({"type": vtype, "url": url})
            known.add(url)
    out["videos"] = videos
    out["gallery"] = [g for g in (out.get("gallery") or []) if str(g or "").strip()]
    return out


def normalise_projects(items: list[dict]) -> list[dict]:
    return [normalise_project(p) for p in (items or [])]


def project_videos(p: dict) -> list[dict]:
    return normalise_project(p)["videos"]


def sorted_projects(projects: list[dict], include_drafts: bool = False) -> list[dict]:
    items = [p for p in projects if include_drafts or p.get("published", True)]

    def key(p: dict):
        try:
            year = int(str(p.get("year") or "0")[:4])
        except ValueError:
            year = 0
        try:
            order = int(p.get("order") or 0)
        except (TypeError, ValueError):
            order = 0
        return (0 if p.get("featured") else 1, -order, -year, str(p.get("title") or ""))

    return sorted(items, key=key)


# --------------------------------------------------------------------------
# Storage accounting
# --------------------------------------------------------------------------
def _media_path(url: str) -> str:
    """Reduce a stored reference to its `media/...` path, or "" if external.

    References are kept as full CDN URLs, so the same file is recognised whether
    it came back from jsDelivr, from raw.githubusercontent, or as a bare path.
    A YouTube or Vimeo link resolves to "" and is simply not our storage.
    """
    u = str(url or "").strip()
    if not u:
        return ""
    if "/media/" in u:
        return "media/" + u.split("/media/", 1)[1].split("?")[0].split("#")[0]
    if u.startswith("media/"):
        return u.split("?")[0]
    return ""


def referenced_media(content: dict) -> set[str]:
    """Every media path the site still points at, across all content files."""
    site = content.get("site") or {}
    out: set[str] = set()

    def add(u) -> None:
        if p := _media_path(u):
            out.add(p)

    for key in ("hero_image", "hero_video", "showreel_file"):
        add(site.get(key))

    for p in content.get("projects") or []:
        add(p.get("poster"))
        add(p.get("video_url"))
        add(p.get("video_file"))
        for g in p.get("gallery") or []:
            add(g)
        for v in p.get("videos") or []:
            add(v.get("url") if isinstance(v, dict) else v)

    for g in content.get("gallery") or []:
        add(g.get("url") if isinstance(g, dict) else g)

    return out


def _kind(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return "video" if ext in {"mp4", "mov", "webm", "m4v"} else "image"


def storage_report(content: dict, files: list[dict]) -> dict:
    """Group stored media into live vs orphaned, by folder and kind.

    `files` comes from Store.list_media(). Anything the content no longer
    points at is orphaned: it still occupies the repository but nothing on the
    site will ever request it.
    """
    truncated = any(f.get("truncated") for f in files)
    files = [f for f in files if f.get("path")]
    live = referenced_media(content)

    rows, groups = [], {}
    for f in files:
        path, size = f["path"], int(f.get("bytes") or 0)
        folder = path.split("/")[1] if path.count("/") >= 2 else "misc"
        kind = _kind(path)
        used = path in live
        rows.append({"path": path, "bytes": size, "folder": folder,
                     "kind": kind, "used": used})
        g = groups.setdefault((folder, kind), {"files": 0, "bytes": 0,
                                               "live_files": 0, "live_bytes": 0})
        g["files"] += 1
        g["bytes"] += size
        if used:
            g["live_files"] += 1
            g["live_bytes"] += size

    total = sum(r["bytes"] for r in rows)
    live_bytes = sum(r["bytes"] for r in rows if r["used"])
    missing = sorted(live - {r["path"] for r in rows})
    return {
        "rows": sorted(rows, key=lambda r: -r["bytes"]),
        "groups": groups,
        "files": len(rows),
        "bytes": total,
        "live_files": sum(1 for r in rows if r["used"]),
        "live_bytes": live_bytes,
        "orphan_files": sum(1 for r in rows if not r["used"]),
        "orphan_bytes": total - live_bytes,
        "missing": missing,
        "truncated": truncated,
    }


def human_size(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def slim_plan(content: dict, tree: list[dict]) -> dict:
    """Work out what a rebuilt content branch should contain.

    The rule is deliberately lopsided: a file is dropped ONLY if it is media
    and nothing in the content points at it. Everything else -- the JSON, and
    any file we do not recognise -- is kept. A mistake in the reference
    scanner can therefore only ever keep too much, never lose something.

    Returns a dict with the keeper entries, the droppable ones, and `blocked`,
    which is a human-readable reason when the rebuild must not run at all.
    """
    live = referenced_media(content)
    blobs = [t for t in tree if t.get("path")]

    keep, drop = [], []
    for t in blobs:
        path = t["path"]
        if path.startswith("media/") and path not in live:
            drop.append(t)
        else:
            keep.append(t)

    present = {t["path"] for t in blobs}
    missing = sorted(live - present)

    blocked = ""
    if not blobs:
        blocked = "the branch appears to be empty"
    elif not live:
        # Every media file would look unused -- almost certainly a failed read
        # rather than a genuinely media-free site.
        blocked = "the site's content could not be read, so nothing looks referenced"
    elif missing:
        blocked = (
            f"{len(missing)} file(s) the site points at are not on the branch "
            "(fix or remove those references first)"
        )
    elif not keep:
        blocked = "nothing would be kept"

    return {
        "keep": keep,
        "drop": drop,
        "missing": missing,
        "blocked": blocked,
        "keep_bytes": sum(t.get("bytes", 0) for t in keep),
        "drop_bytes": sum(t.get("bytes", 0) for t in drop),
        "data_files": sum(1 for t in keep if not t["path"].startswith("media/")),
    }


def verify_rebuild(plan: dict, rebuilt: list[dict]) -> list[str]:
    """Confirm a rebuilt branch really carries every keeper, byte for byte.

    Compares blob SHAs, so a file that arrived with different content is caught
    as well as one that never arrived. Returns a list of problems; empty means
    the new branch is a faithful copy of everything that had to survive.
    """
    got = {t["path"]: t["sha"] for t in rebuilt}
    problems = []
    for t in plan["keep"]:
        if t["path"] not in got:
            problems.append(f"missing: {t['path']}")
        elif got[t["path"]] != t["sha"]:
            problems.append(f"content differs: {t['path']}")
    for path in got:
        if path.startswith("media/") and path not in {t["path"] for t in plan["keep"]}:
            problems.append(f"unexpected extra file: {path}")
    return problems
