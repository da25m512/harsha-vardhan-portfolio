"""Persistence layer.

Content (JSON + uploaded media) lives in a *separate branch* of the same
GitHub repo -- by default `content`. Streamlit Community Cloud only watches
the branch it deployed from (`main`), so writing content to `content` keeps
the live app from rebooting every time the admin saves something.

Two backends:
  * GitHubStore -- production. Reads/writes through the GitHub Contents API.
  * LocalStore  -- fallback for running on a laptop with no token.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API = "https://api.github.com"
TIMEOUT = 30

# jsDelivr refuses files above this; it is also a sane ceiling for a
# base64 GitHub API upload body.
MAX_MEDIA_BYTES = 20 * 1024 * 1024


class StoreError(RuntimeError):
    pass


@dataclass
class Store:
    """Common interface."""

    def read_json(self, path: str, default: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    def write_json(self, path: str, obj: Any, message: str) -> None:
        raise NotImplementedError

    def write_binary(self, path: str, blob: bytes, message: str) -> str:
        raise NotImplementedError

    def delete(self, path: str, message: str) -> None:
        raise NotImplementedError

    def media_url(self, path: str) -> str:
        raise NotImplementedError

    @property
    def writable(self) -> bool:
        return False

    @property
    def label(self) -> str:
        return "none"


# --------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------
class GitHubStore(Store):
    def __init__(self, token: str, owner: str, repo: str, branch: str = "content"):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self._sha_cache: dict[str, str] = {}
        self._branch_ready = False
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "harsha-portfolio-cms",
            }
        )

    # -- plumbing ----------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{API}/repos/{self.owner}/{self.repo}/contents/{path.lstrip('/')}"

    def ensure_branch(self) -> None:
        """Create the content branch off the default branch if missing."""
        if self._branch_ready:
            return
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/branches/{self.branch}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            self._branch_ready = True
            return
        repo = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}", timeout=TIMEOUT
        )
        repo.raise_for_status()
        base = repo.json()["default_branch"]
        ref = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/git/ref/heads/{base}",
            timeout=TIMEOUT,
        )
        ref.raise_for_status()
        sha = ref.json()["object"]["sha"]
        made = self._session.post(
            f"{API}/repos/{self.owner}/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{self.branch}", "sha": sha},
            timeout=TIMEOUT,
        )
        if made.status_code == 403:
            raise StoreError(
                f"The token cannot create the `{self.branch}` branch (403). Either set "
                "its **Contents** permission to **Read and write**, or create a branch "
                f"named `{self.branch}` by hand in GitHub — the app will use it."
            )
        if made.status_code not in (200, 201, 422):
            raise StoreError(f"Could not create branch: {made.status_code} {made.text[:200]}")
        self._branch_ready = True

    def check(self) -> tuple[bool, str]:
        """Verify token + repo + write scope. Returns (ok, human message)."""
        try:
            r = self._session.get(
                f"{API}/repos/{self.owner}/{self.repo}", timeout=TIMEOUT
            )
        except Exception as exc:  # network
            return False, f"Could not reach GitHub: {exc}"
        if r.status_code == 404:
            return False, (
                f"Repo {self.owner}/{self.repo} not found, or the token cannot see it."
            )
        if r.status_code == 401:
            return False, "GitHub token is invalid or expired."
        if r.status_code != 200:
            return False, f"GitHub returned {r.status_code}: {r.text[:160]}"
        perms = r.json().get("permissions") or {}
        if not perms.get("push", False):
            return False, "Token can read the repo but has no write access."

        # `permissions.push` reflects the account, not the token's own scope,
        # so probe the branch the app actually writes to.
        br = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/branches/{self.branch}",
            timeout=TIMEOUT,
        )
        if br.status_code == 404:
            made = self._session.post(
                f"{API}/repos/{self.owner}/{self.repo}/git/refs",
                json={"ref": f"refs/heads/{self.branch}", "sha": self._default_sha()},
                timeout=TIMEOUT,
            )
            if made.status_code == 403:
                return False, (
                    f"The token cannot create the `{self.branch}` branch "
                    "(GitHub said 403). Set the token's **Contents** permission to "
                    "**Read and write**, or create the branch by hand in GitHub."
                )
            if made.status_code not in (200, 201, 422):
                return False, f"Could not create the `{self.branch}` branch: {made.status_code}"
        elif br.status_code == 403:
            return False, (
                "The token cannot read this repository's branches. Check that it is "
                "scoped to this repo with **Contents: Read and write**."
            )
        self._branch_ready = True
        return True, f"Connected to {self.owner}/{self.repo}@{self.branch}"

    def _default_sha(self) -> str:
        repo = self._session.get(f"{API}/repos/{self.owner}/{self.repo}", timeout=TIMEOUT)
        repo.raise_for_status()
        base = repo.json()["default_branch"]
        ref = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/git/ref/heads/{base}", timeout=TIMEOUT
        )
        ref.raise_for_status()
        return ref.json()["object"]["sha"]

    # -- reads -------------------------------------------------------------
    def read_json(self, path: str, default: Any) -> Any:
        try:
            r = self._session.get(
                self._url(path),
                params={"ref": self.branch},
                headers={"Cache-Control": "no-cache"},
                timeout=TIMEOUT,
            )
        except Exception:
            return default
        if r.status_code == 404:
            return default
        if r.status_code != 200:
            return default
        payload = r.json()
        self._sha_cache[path] = payload.get("sha", "")
        raw = payload.get("content") or ""
        if not raw:
            return default
        try:
            return json.loads(base64.b64decode(raw).decode("utf-8"))
        except Exception:
            return default

    def _current_sha(self, path: str) -> str | None:
        r = self._session.get(
            self._url(path), params={"ref": self.branch}, timeout=TIMEOUT
        )
        if r.status_code == 200:
            return r.json().get("sha")
        return None

    # -- writes ------------------------------------------------------------
    def _put(self, path: str, blob: bytes, message: str) -> dict:
        self.ensure_branch()
        encoded = base64.b64encode(blob).decode("ascii")
        last = ""
        # 409/422 means someone else wrote the file between our read and write
        # (two visitors signing the guestbook at once). Re-read the sha and retry.
        for attempt in range(3):
            body = {"message": message, "content": encoded, "branch": self.branch}
            sha = self._current_sha(path)
            if sha:
                body["sha"] = sha
            r = self._session.put(self._url(path), json=body, timeout=90)
            if r.status_code in (200, 201):
                return r.json()
            last = f"{r.status_code} {r.text[:240]}"
            if r.status_code == 403:
                raise StoreError(
                    "GitHub refused the save (403). The access token's "
                    "**Contents** permission needs to be **Read and write** for this "
                    "repository. Fix it at Settings -> Developer settings -> "
                    "Fine-grained tokens, then update the app's Secrets."
                )
            if r.status_code == 401:
                raise StoreError(
                    "GitHub rejected the access token (401). It may have expired — "
                    "generate a new one and update the app's Secrets."
                )
            if r.status_code not in (409, 422):
                break
            time.sleep(0.6 * (attempt + 1))
        raise StoreError(f"GitHub write failed for {path}: {last}")

    def write_json(self, path: str, obj: Any, message: str) -> None:
        blob = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self._put(path, blob, message)

    def write_binary(self, path: str, blob: bytes, message: str) -> str:
        if len(blob) > MAX_MEDIA_BYTES:
            raise StoreError(
                f"File is {len(blob)/1048576:.1f} MB. The limit is "
                f"{MAX_MEDIA_BYTES//1048576} MB -- host longer videos on "
                "YouTube or Vimeo and paste the link instead."
            )
        self._put(path, blob, message)
        return self.media_url(path)

    def delete(self, path: str, message: str) -> None:
        sha = self._current_sha(path)
        if not sha:
            return
        self._session.delete(
            self._url(path),
            json={"message": message, "sha": sha, "branch": self.branch},
            timeout=TIMEOUT,
        )

    def media_url(self, path: str) -> str:
        p = path.lstrip("/")
        return (
            f"https://cdn.jsdelivr.net/gh/{self.owner}/{self.repo}@{self.branch}/{p}"
        )

    def raw_url(self, path: str) -> str:
        p = path.lstrip("/")
        return (
            "https://raw.githubusercontent.com/"
            f"{self.owner}/{self.repo}/{self.branch}/{p}"
        )

    @property
    def writable(self) -> bool:
        return True

    @property
    def label(self) -> str:
        return f"GitHub · {self.owner}/{self.repo}@{self.branch}"


# --------------------------------------------------------------------------
# Local disk
# --------------------------------------------------------------------------
class LocalStore(Store):
    """Used when no GitHub token is configured. Survives reruns, not restarts
    on Streamlit Cloud -- fine for local development and for previewing."""

    def __init__(self, root: str | Path = "local_content"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, path: str) -> Path:
        p = (self.root / path.lstrip("/")).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise StoreError("Refusing to write outside the content root.")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def read_json(self, path: str, default: Any) -> Any:
        p = self._p(path)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            return default

    def write_json(self, path: str, obj: Any, message: str) -> None:
        self._p(path).write_text(
            json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def write_binary(self, path: str, blob: bytes, message: str) -> str:
        self._p(path).write_bytes(blob)
        return self.media_url(path)

    def delete(self, path: str, message: str) -> None:
        p = self._p(path)
        if p.exists():
            p.unlink()

    def media_url(self, path: str) -> str:
        """Inline as a data URI so it renders inside injected HTML."""
        p = self._p(path)
        if not p.exists():
            return ""
        mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")

    @property
    def writable(self) -> bool:
        return True

    @property
    def label(self) -> str:
        return f"Local disk · ./{self.root}"


_SAFE_FOLDER = re.compile(r"[^a-z0-9_-]+")
_SAFE_EXT = re.compile(r"^\.[a-z0-9]{1,5}$")


def new_media_path(folder: str, filename: str) -> str:
    """Build a storage path that cannot escape media/<folder>/.

    Dots are stripped from the stem entirely, so no traversal sequence can
    survive, and the extension must match a short alphanumeric pattern.
    """
    folder = _SAFE_FOLDER.sub("-", str(folder).lower()).strip("-") or "misc"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(filename).stem).strip("-.").lower()
    stem = re.sub(r"-{2,}", "-", stem)[:40] or "file"
    ext = Path(filename).suffix.lower()
    if not _SAFE_EXT.match(ext):
        ext = ".bin"
    return f"media/{folder}/{int(time.time())}-{stem}{ext}"
