"""Content model, defaults, and cached load/save helpers."""
from __future__ import annotations

import time
import uuid
from typing import Any

import streamlit as st

from hv_store import GitHubStore, LocalStore, Store

SITE_PATH = "data/site.json"
PROJECTS_PATH = "data/projects.json"
TIMELINE_PATH = "data/timeline.json"
GALLERY_PATH = "data/gallery.json"
PRESS_PATH = "data/press.json"
MESSAGES_PATH = "data/messages.json"

DIRECTOR_NAME = "Marothu Harsha Vardhan"

DEFAULT_SITE: dict[str, Any] = {
    "name": DIRECTOR_NAME,
    "short_name": "Harsha Vardhan",
    "eyebrow": "Director · Writer",
    "roles": ["Director", "Writer", "Storyteller", "Visual Thinker"],
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
        "Marothu Harsha Vardhan is an emerging director whose work is driven by "
        "character, silence, and the things people don't say out loud. He is "
        "currently developing his first slate of independent projects."
    ),
    "hero_image": "",
    "hero_video": "",
    "portrait": "",
    "showreel_url": "",
    "showreel_caption": "The reel so far",
    "email": "",
    "phone": "",
    "socials": [],
    "accent": "#57C8B0",
    "accent_2": "#E4813F",
    "grain": True,
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
    "role": "Director",
    "status": "Released",
    "runtime": "",
    "ratio": "",
    "shot_on": "",
    "logline": "",
    "synopsis": "",
    "credits": "",
    "poster": "",
    "gallery": [],
    "video_url": "",
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

    return get_store().read_json(path, json.loads(default_json))


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
        "projects": _fetch(PROJECTS_PATH, "[]", v) or [],
        "timeline": _fetch(TIMELINE_PATH, "[]", v) or [],
        "gallery": _fetch(GALLERY_PATH, "[]", v) or [],
        "press": _fetch(PRESS_PATH, "[]", v) or [],
        "messages": _fetch(MESSAGES_PATH, "[]", v) or [],
    }



def save(path: str, obj: Any, what: str) -> None:
    get_store().write_json(path, obj, f"content: update {what}")
    bump()


def save_site(site: dict) -> None:
    site["updated_at"] = now_stamp()
    save(SITE_PATH, site, "site settings")


def upload(folder: str, uploaded_file) -> str:
    """Persist a Streamlit UploadedFile and return a public URL."""
    from hv_store import new_media_path

    blob = uploaded_file.getvalue()
    path = new_media_path(folder, uploaded_file.name)
    return get_store().write_binary(path, blob, f"content: add {path}")


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
