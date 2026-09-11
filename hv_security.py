"""Security controls.

Everything rendered through `unsafe_allow_html` must pass through `esc()` or
`attr()` first. Anything that becomes an iframe `src` must pass `embed_src()`.
Anything uploaded must pass `validate_upload()`.
"""
from __future__ import annotations

import hmac
import html
import re
import time
from urllib.parse import urlparse, parse_qs

import streamlit as st

# --------------------------------------------------------------------------
# Output encoding  (OWASP A03: Injection / XSS)
# --------------------------------------------------------------------------
def esc(value, default: str = "") -> str:
    """HTML-escape any value for use in element text."""
    if value is None:
        return default
    return html.escape(str(value), quote=True)


def attr(value, default: str = "") -> str:
    """Escape for use inside a double-quoted HTML attribute."""
    return esc(value, default).replace("\n", " ")


_SAFE_URL = re.compile(r"^https://[A-Za-z0-9.\-]+(:\d+)?(/|$)")


def safe_url(value: str, allow_mailto: bool = True, allow_data: bool = False) -> str:
    """Return the URL only if it is a safe, absolute https (or mailto/tel) URL.

    Blocks javascript:, vbscript:, data: (unless explicitly allowed for local
    preview), file: and protocol-relative tricks.
    """
    v = (value or "").strip()
    if not v:
        return ""
    low = v.lower().replace("\x00", "")
    if allow_data and low.startswith("data:image/"):
        return v
    if allow_data and low.startswith("data:video/"):
        return v
    if allow_mailto and (low.startswith("mailto:") or low.startswith("tel:")):
        if re.match(r"^(mailto:[^\s<>\"']+@[^\s<>\"']+|tel:\+?[0-9 \-()]+)$", v):
            return v
        return ""
    if _SAFE_URL.match(v):
        return v
    return ""


def img_src(value: str) -> str:
    """URL for an <img>/<video> src: https or a local data: preview URI."""
    return attr(safe_url(value, allow_mailto=False, allow_data=True))


# --------------------------------------------------------------------------
# Video embeds  (OWASP A10: SSRF / untrusted iframe sources)
# --------------------------------------------------------------------------
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_VIMEO_ID = re.compile(r"^\d{6,12}$")

EMBED_HOSTS = (
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
)


def embed_src(url: str) -> tuple[str, str]:
    """Map a user-supplied video link to a vetted embed.

    Returns (kind, src) where kind is "iframe", "file" or "" (unusable).
    Only YouTube and Vimeo are allowed as iframes; anything else must be a
    direct media file we host ourselves.
    """
    v = (url or "").strip()
    if not v:
        return "", ""

    if v.lower().startswith("data:video/"):
        return "file", v

    if not _SAFE_URL.match(v):
        return "", ""

    try:
        u = urlparse(v)
    except Exception:
        return "", ""
    host = (u.hostname or "").lower()

    if host in ("youtu.be",):
        vid = u.path.strip("/").split("/")[0]
        if _YT_ID.match(vid):
            return "iframe", f"https://www.youtube-nocookie.com/embed/{vid}?rel=0&modestbranding=1"
        return "", ""

    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        vid = ""
        if u.path.startswith("/watch"):
            vid = (parse_qs(u.query).get("v") or [""])[0]
        elif u.path.startswith(("/embed/", "/shorts/", "/live/", "/v/")):
            vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
        if _YT_ID.match(vid or ""):
            return "iframe", f"https://www.youtube-nocookie.com/embed/{vid}?rel=0&modestbranding=1"
        return "", ""

    if host.endswith("vimeo.com"):
        parts = [p for p in u.path.split("/") if p]
        vid = next((p for p in parts if _VIMEO_ID.match(p)), "")
        if vid:
            return "iframe", f"https://player.vimeo.com/video/{vid}?dnt=1"
        return "", ""

    # A file we uploaded ourselves (jsDelivr / raw.githubusercontent only).
    if host in ("cdn.jsdelivr.net", "raw.githubusercontent.com") and re.search(
        r"\.(mp4|webm|mov|m4v)$", u.path, re.I
    ):
        return "file", v

    return "", ""


# --------------------------------------------------------------------------
# Uploads  (OWASP A04/A08: insecure design / untrusted files)
# --------------------------------------------------------------------------
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}

_MAGIC = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}

MAX_IMAGE = 10 * 1024 * 1024
MAX_VIDEO = 20 * 1024 * 1024


def _sniff(blob: bytes) -> str:
    for sig, kind in _MAGIC.items():
        if blob.startswith(sig):
            return kind
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "webp"
    if blob[4:8] == b"ftyp":
        brand = blob[8:12]
        if brand in (b"avif", b"avis"):
            return "avif"
        return "mp4"
    if blob[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    return ""


def validate_upload(uploaded, kind: str = "image") -> tuple[bool, str]:
    """kind: 'image' | 'video'. Returns (ok, error message)."""
    if uploaded is None:
        return False, "No file."
    name = (uploaded.name or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    allowed = IMAGE_EXT if kind == "image" else VIDEO_EXT
    cap = MAX_IMAGE if kind == "image" else MAX_VIDEO

    if ext not in allowed:
        return False, f"{ext or 'That file type'} isn't allowed. Use: {', '.join(sorted(allowed))}"

    blob = uploaded.getvalue()
    if len(blob) == 0:
        return False, "That file is empty."
    if len(blob) > cap:
        return False, (
            f"{len(blob)/1048576:.1f} MB is over the {cap//1048576} MB limit. "
            + ("Compress the image." if kind == "image"
               else "Put long videos on YouTube or Vimeo and paste the link.")
        )

    sniffed = _sniff(blob)
    if not sniffed:
        return False, "That file's contents don't look like a real image or video."
    if kind == "image" and sniffed in ("mp4", "webm"):
        return False, "That's a video, not an image."
    if kind == "video" and sniffed in ("jpg", "png", "gif", "webp", "avif"):
        return False, "That's an image, not a video."

    # An SVG or HTML payload renamed to .png would fail the sniff above.
    head = blob[:512].lstrip().lower()
    if head.startswith((b"<", b"<?xml", b"<!doctype")):
        return False, "Markup files can't be uploaded as media."
    return True, ""


# --------------------------------------------------------------------------
# Admin authentication  (OWASP A01/A07: access control, auth failures)
# --------------------------------------------------------------------------
LOCKOUT_AFTER = 5
LOCKOUT_SECONDS = 300


def _configured_password() -> str:
    try:
        return str(st.secrets.get("admin_password", "") or "")
    except Exception:
        return ""


def password_is_configured() -> bool:
    return len(_configured_password()) >= 8


def is_admin() -> bool:
    return bool(st.session_state.get("_is_admin", False))


def lockout_remaining() -> int:
    until = st.session_state.get("_lock_until", 0)
    return max(0, int(until - time.time()))


def attempt_login(password: str) -> tuple[bool, str]:
    if lockout_remaining() > 0:
        return False, f"Too many attempts. Try again in {lockout_remaining()}s."
    real = _configured_password()
    if not real:
        return False, (
            "No admin password is configured. Add `admin_password` to the app's "
            "Secrets in Streamlit Cloud, then reload."
        )
    if len(real) < 8:
        return False, "The configured admin password is too short (needs 8+ characters)."
    # constant-time comparison
    ok = hmac.compare_digest(password.encode("utf-8"), real.encode("utf-8"))
    if ok:
        st.session_state["_is_admin"] = True
        st.session_state["_fails"] = 0
        st.session_state["_login_at"] = time.time()
        return True, ""
    fails = st.session_state.get("_fails", 0) + 1
    st.session_state["_fails"] = fails
    if fails >= LOCKOUT_AFTER:
        st.session_state["_lock_until"] = time.time() + LOCKOUT_SECONDS
        st.session_state["_fails"] = 0
        return False, f"Too many attempts. Locked for {LOCKOUT_SECONDS // 60} minutes."
    return False, f"Incorrect. {LOCKOUT_AFTER - fails} attempt(s) left."


SESSION_MAX_SECONDS = 8 * 3600


def enforce_session_timeout() -> None:
    if not is_admin():
        return
    started = st.session_state.get("_login_at", 0)
    if started and time.time() - started > SESSION_MAX_SECONDS:
        logout()


def logout() -> None:
    for k in ("_is_admin", "_login_at"):
        st.session_state.pop(k, None)


# --------------------------------------------------------------------------
# Public guestbook abuse limits
# --------------------------------------------------------------------------
MSG_MAX = 600
NAME_MAX = 60
POST_COOLDOWN = 45
MAX_STORED_MESSAGES = 500

_URL_IN_TEXT = re.compile(r"https?://|www\.", re.I)


def check_message(name: str, message: str, honeypot: str) -> tuple[bool, str]:
    if honeypot.strip():
        return False, "Something went wrong. Please try again."
    name = (name or "").strip()
    message = (message or "").strip()
    if len(name) < 2:
        return False, "Please add your name."
    if len(name) > NAME_MAX:
        return False, f"Name is too long (max {NAME_MAX})."
    if len(message) < 4:
        return False, "Please write a little more."
    if len(message) > MSG_MAX:
        return False, f"Message is too long (max {MSG_MAX} characters)."
    if len(_URL_IN_TEXT.findall(message)) > 1:
        return False, "Too many links — please write a plain message."
    last = st.session_state.get("_last_post", 0)
    wait = int(POST_COOLDOWN - (time.time() - last))
    if wait > 0:
        return False, f"Please wait {wait}s before posting again."
    return True, ""


def mark_posted() -> None:
    st.session_state["_last_post"] = time.time()
