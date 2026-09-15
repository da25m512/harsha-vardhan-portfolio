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

    # -- whole-branch operations -------------------------------------------
    def full_tree(self, ref: str | None = None) -> list[dict]:
        """Every blob on a branch as {path, sha, bytes, mode}.

        Unlike list_media this covers the whole branch, so the caller can
        decide what to keep rather than assuming only media matters.
        """
        ref = ref or self.branch
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/git/trees/{ref}",
            params={"recursive": "1"},
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            raise StoreError(f"Branch `{ref}` does not exist.")
        if r.status_code >= 400:
            raise StoreError(f"Could not read branch `{ref}` ({r.status_code}).")
        body = r.json()
        if body.get("truncated"):
            raise StoreError(
                "GitHub truncated the file listing, so the rebuild cannot be "
                "certain it would carry every file across. Aborting."
            )
        return [
            {"path": t["path"], "sha": t["sha"],
             "bytes": int(t.get("size") or 0), "mode": t.get("mode", "100644")}
            for t in body.get("tree", [])
            if t.get("type") == "blob"
        ]

    def build_orphan_branch(self, name: str, entries: list[dict], message: str) -> str:
        """Create `name` as a single parentless commit holding `entries`.

        Entries carry the blob SHAs that already exist in the repository, so no
        file content is uploaded -- git simply points a new tree at objects it
        already has. Because the commit has no parents, none of the old history
        is reachable through this branch, which is the whole point: once the
        original branch is gone, the superseded blobs can be collected.

        Returns the new commit SHA. Never touches the branch it read from.
        """
        if not entries:
            raise StoreError("Refusing to build an empty branch.")
        if name == self.branch:
            raise StoreError(
                f"Refusing to overwrite the live branch `{self.branch}`. "
                "The rebuild must go to a different branch."
            )

        tree = [
            {"path": e["path"], "mode": e.get("mode", "100644"),
             "type": "blob", "sha": e["sha"]}
            for e in entries
        ]
        r = self._session.post(
            f"{API}/repos/{self.owner}/{self.repo}/git/trees",
            json={"tree": tree},
            timeout=90,
        )
        if r.status_code >= 400:
            raise StoreError(f"Could not create the tree ({r.status_code}): {r.text[:200]}")
        tree_sha = r.json()["sha"]

        r = self._session.post(
            f"{API}/repos/{self.owner}/{self.repo}/git/commits",
            json={"message": message, "tree": tree_sha, "parents": []},
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            raise StoreError(f"Could not create the commit ({r.status_code}): {r.text[:200]}")
        commit_sha = r.json()["sha"]

        ref = f"refs/heads/{name}"
        r = self._session.post(
            f"{API}/repos/{self.owner}/{self.repo}/git/refs",
            json={"ref": ref, "sha": commit_sha},
            timeout=TIMEOUT,
        )
        if r.status_code == 422:  # branch already there -- move it
            r = self._session.patch(
                f"{API}/repos/{self.owner}/{self.repo}/git/refs/heads/{name}",
                json={"sha": commit_sha, "force": True},
                timeout=TIMEOUT,
            )
        if r.status_code >= 400:
            raise StoreError(f"Could not point `{name}` at the new commit ({r.status_code}).")
        return commit_sha

    # -- refs ---------------------------------------------------------------
    def ref_sha(self, name: str) -> str:
        """Commit a branch points at, or "" if the branch is absent."""
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/git/ref/heads/{name}",
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            return ""
        if r.status_code >= 400:
            raise StoreError(f"Could not read branch `{name}` ({r.status_code}).")
        return r.json()["object"]["sha"]

    def set_ref(self, name: str, sha: str) -> None:
        """Point a branch at a commit, creating it if it is not there yet.

        Used instead of renaming: a rename deletes the old name first, and the
        app recreates a missing content branch on its next write, so the branch
        never stops existing this way.

        Creating and moving are different endpoints, and GitHub does not answer
        404 for a reference that is absent -- updating one returns 422, the same
        code as a genuine validation failure. So which call to make is decided by
        looking first, and each is still prepared for the other to be right, in
        case the branch appears or vanishes in between.
        """
        create_url = f"{API}/repos/{self.owner}/{self.repo}/git/refs"
        update_url = f"{API}/repos/{self.owner}/{self.repo}/git/refs/heads/{name}"

        def _create():
            return self._session.post(
                create_url, json={"ref": f"refs/heads/{name}", "sha": sha},
                timeout=TIMEOUT,
            )

        def _update():
            return self._session.patch(
                update_url, json={"sha": sha, "force": True}, timeout=TIMEOUT,
            )

        exists = bool(self.ref_sha(name))
        r = _update() if exists else _create()
        if r.status_code >= 400:
            r = _create() if exists else _update()   # the other one, just in case
        if r.status_code >= 400:
            detail = ""
            try:
                detail = str(r.json().get("message") or "")
            except Exception:
                detail = (r.text or "")[:120]
            raise StoreError(
                f"Could not point `{name}` at {sha[:7]} ({r.status_code})"
                + (f": {detail}" if detail else "")
            )

    def list_branches(self) -> list[dict]:
        """Every branch as {name, sha}."""
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/branches",
            params={"per_page": "100"},
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            raise StoreError(f"Could not list branches ({r.status_code}).")
        return [{"name": b["name"], "sha": b["commit"]["sha"]} for b in r.json()]

    def default_branch(self) -> str:
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}", timeout=TIMEOUT
        )
        if r.status_code >= 400:
            return "main"
        return str(r.json().get("default_branch") or "main")

    def delete_ref(self, name: str) -> None:
        if name == self.branch:
            raise StoreError(
                f"Refusing to delete `{name}` -- the site is served from it."
            )
        r = self._session.delete(
            f"{API}/repos/{self.owner}/{self.repo}/git/refs/heads/{name}",
            timeout=TIMEOUT,
        )
        if r.status_code >= 400 and r.status_code != 404:
            raise StoreError(f"Could not remove branch `{name}` ({r.status_code}).")

    def repo_size_bytes(self) -> int:
        """Repository size as GitHub reports it. Recalculated hourly, so it lags."""
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}", timeout=TIMEOUT
        )
        if r.status_code >= 400:
            return 0
        return int(r.json().get("size") or 0) * 1024

    def media_url(self, path: str) -> str:
        raise NotImplementedError

    def list_media(self) -> list[dict]:
        """Every stored media file as {path, bytes}. Empty when unsupported."""
        return []

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
        r = self._session.delete(
            self._url(path),
            json={"message": message, "sha": sha, "branch": self.branch},
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            raise StoreError(
                f"Could not delete {path} ({r.status_code}). "
                "Check the token still has Contents: Read and write."
            )
        self._sha_cache.pop(path, None)

    def media_url(self, path: str) -> str:
        p = path.lstrip("/")
        return (
            f"https://cdn.jsdelivr.net/gh/{self.owner}/{self.repo}@{self.branch}/{p}"
        )

    def list_media(self) -> list[dict]:
        """List every blob under media/ on the content branch.

        One trees call with recursive=1 returns the whole subtree, which is far
        cheaper than walking directories. GitHub truncates very large trees; the
        flag is passed through so the caller can say the figure is a floor
        rather than quietly reporting a wrong total.
        """
        r = self._session.get(
            f"{API}/repos/{self.owner}/{self.repo}/git/trees/{self.branch}:media",
            params={"recursive": "1"},
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            return []
        if r.status_code >= 400:
            raise StoreError(f"Could not read the media tree ({r.status_code}).")
        body = r.json()
        out = [
            {"path": f"media/{t['path']}", "bytes": int(t.get("size") or 0)}
            for t in body.get("tree", [])
            if t.get("type") == "blob"
        ]
        if body.get("truncated"):
            out.append({"path": "", "bytes": 0, "truncated": True})
        return out

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

    def list_media(self) -> list[dict]:
        root = self._p("media")
        if not root.exists():
            return []
        return [
            {"path": str(f.relative_to(self.root)).replace("\\", "/"),
             "bytes": f.stat().st_size}
            for f in root.rglob("*")
            if f.is_file()
        ]

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
