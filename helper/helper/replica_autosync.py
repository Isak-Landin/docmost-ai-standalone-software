"""In-helper git backup of an in-repo Docmost replica.

This module does PURE local git backup of the in-repo Docmost replica. It NEVER talks to Docmost
or the bridge server; it only commits the replica subtree and pushes the current branch to the
repo's existing git remote. It runs INSIDE the live helper process, whose cwd is the repo and
whose `os.environ` already carries the repo's git deploy key (GIT_SSH_COMMAND) via direnv.

`autosync` is the single gatekeeper: it re-checks the enable gate, re-validates that each replica
root truly belongs to the discovered repo, dynamically discovers the branch's remote (never a
hardcoded name), takes a per-repo lock, and only then commits the replica subtree (pathspec commit,
so unrelated staged code is never swept in) and pushes the current branch (never `--force`). It
NEVER raises; every failure returns a status dict and does no git mutation beyond what already
succeeded.

This replaces the old cron-based trigger: backup now happens in-process via `autosync_async` /
`autosync_after`. `cleanup_legacy_cron` migrates away from any leftover tagged cron lines.

This is a helper-client concern (the replica lives on the helper's machine), NOT a bridge route.
"""

from __future__ import annotations

import fcntl
import functools
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

# Allow importing as `helper.replica_autosync` regardless of how the process was started,
# mirroring server.py's sys.path bootstrap.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helper.replica import read_replica_header  # noqa: E402

# --- contract constants -----------------------------------------------------

ENABLE_ENV = "DOCMOST_REPLICA_GIT_AUTOSYNC"          # opt-in flag, loaded per repo via direnv/.envrc
ROOTS_ENV = "DOCMOST_REPLICA_AUTOSYNC_ROOTS"          # optional explicit owned replica roots (comma-split)
LEGACY_CRON_TAG = "# docmost-replica-autosync:"       # tag of the old cron trigger we now migrate away
COMMIT_USER_NAME = "replica-autosync"
COMMIT_USER_EMAIL = "replica-autosync@docmost-helper.local"
COMMIT_MESSAGE = "replica"
LOG_PATH = os.path.expanduser("~/.cache/docmost-replica-autosync.log")
SKIP_DIRS = {".git", ".claude", ".venv", "node_modules", "__pycache__"}

log = logging.getLogger("docmost.replica_autosync")

_logging_ready = False


# --- small process helpers --------------------------------------------------

def _run(args: list[str], cwd: str | None = None, env: dict | None = None,
         input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd, env=env, input=input_text,
        capture_output=True, text=True, timeout=timeout,
    )


def _result(status: str, **kw) -> dict:
    return {"status": status, **kw}


def _setup_logging() -> None:
    """Lazy, idempotent logging setup (NOT done at import time)."""
    global _logging_ready
    if _logging_ready:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        handlers.append(logging.FileHandler(LOG_PATH))
    except OSError:
        pass
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    for h in handlers:
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False
    _logging_ready = True


# --- live enable gate -------------------------------------------------------

def enabled() -> bool:
    """True unless the enable flag is empty/off-like."""
    val = (os.environ.get(ENABLE_ENV) or "").strip().lower()
    return val not in ("", "0", "false", "off", "no")


# --- git / repo introspection ----------------------------------------------

def _repo_top(start: str) -> str | None:
    """The git work-tree top containing `start`, or None if `start` is not in a git repo."""
    try:
        r = _run(["git", "-C", start, "rev-parse", "--show-toplevel"])
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    top = r.stdout.strip()
    return os.path.realpath(top) if top else None


def _current_branch(repo_top: str) -> str | None:
    r = _run(["git", "-C", repo_top, "rev-parse", "--abbrev-ref", "HEAD"])
    branch = r.stdout.strip()
    if r.returncode != 0 or not branch or branch == "HEAD":  # HEAD => detached
        return None
    return branch


def _discover_remote(repo_top: str, branch: str) -> str | None:
    """Dynamically resolve the remote for `branch` -- NEVER a hardcoded name.

    Prefer the branch's tracking remote; otherwise use the sole remote iff exactly one exists.
    Then verify the remote actually has a URL. Returns the remote name or None.
    """
    tracking = _run(["git", "-C", repo_top, "config", "--get", f"branch.{branch}.remote"]).stdout.strip()
    if tracking:
        remote = tracking
    else:
        remotes = _run(["git", "-C", repo_top, "remote"]).stdout.split()
        if len(remotes) != 1:
            return None
        remote = remotes[0]
    if _run(["git", "-C", repo_top, "remote", "get-url", remote]).returncode != 0:
        return None
    return remote


# --- owned replica root resolution -----------------------------------------

def _discover_replica_roots(repo_top: str) -> list[str]:
    """Every directory under repo_top carrying a `_replica.json` marker, excluding noise dirs.
    Same marker the helper itself uses, so a renamed/restructured replica is found automatically."""
    roots: list[str] = []
    for header in Path(repo_top).rglob("_replica.json"):
        if set(header.parts) & SKIP_DIRS:
            continue
        roots.append(str(header.parent))
    return roots


def _candidate_roots(repo_top: str) -> tuple[list[str], bool]:
    """Resolve candidate replica roots. Returns (candidates, raw_was_set).

    If ROOTS_ENV is set, candidates are its comma-split items (relative ones joined onto repo_top),
    realpath'd. Otherwise candidates come from `_replica.json` marker discovery.
    """
    raw = (os.environ.get(ROOTS_ENV) or "").strip()
    if raw:
        candidates: list[str] = []
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            abspath = item if os.path.isabs(item) else os.path.join(repo_top, item)
            candidates.append(os.path.realpath(abspath))
        return candidates, True
    return _discover_replica_roots(repo_top), False


def _valid_root(cand: str, repo_top: str) -> bool:
    """A candidate is owned by this repo iff its own git top is repo_top, it carries a
    `_replica.json`, and that header has a truthy space_id."""
    cand_top = _repo_top(cand)
    if cand_top != repo_top:
        log.warning("dropping replica root outside repo (%s -> %s)", cand, cand_top)
        return False
    if not (Path(cand) / "_replica.json").is_file():
        log.warning("dropping replica root without _replica.json: %s", cand)
        return False
    if not read_replica_header(cand).get("space_id"):
        log.warning("dropping replica root without a space_id: %s", cand)
        return False
    return True


# --- per-repo lock (prevents overlapping autosync runs) ---------------------

def _acquire_lock(repo_top: str):
    """Return an open, exclusively-flocked file handle, or None if another run holds it."""
    lock_path = os.path.join(repo_top, ".git", "docmost-replica-autosync.lock")
    try:
        fh = open(lock_path, "w")
    except OSError:
        return None
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        fh.close()
        return None
    return fh


def _release_lock(lock) -> None:
    try:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    except OSError:
        pass


# --- the gatekeeper ---------------------------------------------------------

def autosync(start_dir: str | None = None) -> dict:
    """Validate and, if everything passes, commit + push the repo's replica subtree.

    Pure local git. Order: enable gate -> repo discovery -> owned-root validation -> branch ->
    remote -> lock -> staged commit -> push. NEVER raises; returns a status dict and logs the
    outcome. Each failed precondition returns a status and performs no git mutation.
    """
    try:
        return _autosync(start_dir)
    except Exception as exc:  # never raise out of a background backup
        try:
            log.error("autosync crashed: %s", exc)
        except Exception:
            pass
        return _result("error", detail=str(exc))


def _autosync(start_dir: str | None) -> dict:
    _setup_logging()

    if not enabled():
        return _result("disabled")

    start = start_dir or os.getcwd()
    repo_top = _repo_top(start)
    if not repo_top:
        return _result("skipped", reason="not a git repo")

    # Resolve + validate the owned replica roots.
    candidates, raw_was_set = _candidate_roots(repo_top)
    roots = [c for c in candidates if _valid_root(c, repo_top)]
    if not roots:
        return _result("skipped", reason="no owned replica roots")
    if not raw_was_set and len(roots) > 1:
        # A multi-replica repo must declare which roots this helper owns; refuse to guess.
        log.warning("multiple replica roots in %s; set %s to declare ownership", repo_top, ROOTS_ENV)
        return _result("skipped", reason=f"multiple replicas; set {ROOTS_ENV}")

    branch = _current_branch(repo_top)
    if not branch:
        return _result("skipped", reason="detached HEAD")

    remote = _discover_remote(repo_top, branch)
    if not remote:
        return _result("skipped", reason="no unambiguous remote for branch")

    lock = _acquire_lock(repo_top)
    if lock is None:
        return _result("skipped", reason="another autosync in progress")
    try:
        return _commit_and_push(repo_top, roots, branch, remote)
    finally:
        _release_lock(lock)


def _commit_and_push(repo_top: str, roots: list[str], branch: str, remote: str) -> dict:
    rels = [os.path.relpath(r, repo_top) for r in roots]

    # Stage adds/modifications/deletions within the replica subtree only.
    add = _run(["git", "-C", repo_top, "add", "-A", "--", *rels])
    if add.returncode != 0:
        log.error("git add failed: %s", add.stderr.strip())
        return _result("error", stage="add", detail=add.stderr.strip())

    # Nothing staged for the replica paths -> clean no-op (scoped to rels, so unrelated staged code
    # never makes this fire). --quiet exits 0 when there is no diff, 1 when there is.
    if _run(["git", "-C", repo_top, "diff", "--cached", "--quiet", "--", *rels]).returncode == 0:
        log.info("no replica changes to commit (%s)", repo_top)
        return _result("clean", committed=False, pushed=False)

    # Partial (pathspec) commit: commits ONLY the replica paths, never unrelated staged code.
    commit = _run([
        "git", "-C", repo_top,
        "-c", f"user.name={COMMIT_USER_NAME}",
        "-c", f"user.email={COMMIT_USER_EMAIL}",
        "commit", "-m", COMMIT_MESSAGE, "--", *rels,
    ])
    if commit.returncode != 0:
        log.error("git commit failed: %s", (commit.stderr or commit.stdout).strip())
        return _result("error", stage="commit", detail=(commit.stderr or commit.stdout).strip())

    # Push the CURRENT branch only to its discovered remote; NEVER force.
    push = _run(["git", "-C", repo_top, "push", remote, branch], timeout=120)
    if push.returncode != 0:
        log.warning("push to %s %s failed (commit kept): %s", remote, branch, push.stderr.strip())
        return _result("committed", committed=True, pushed=False, detail=push.stderr.strip())
    log.info("committed + pushed replica to %s %s (%s)", remote, branch, repo_top)
    return _result("ok", committed=True, pushed=True, remote=remote, branch=branch)


# --- async + decorator entry points ----------------------------------------

def autosync_async(start_dir: str | None = None) -> None:
    """Fire-and-forget the backup on a non-daemon thread. Never raises."""
    try:
        if not enabled():
            return
        start = start_dir if start_dir is not None else os.getcwd()
        thread = threading.Thread(target=autosync, args=(start,), name="docmost-replica-autosync")
        thread.start()
    except Exception:
        pass


def autosync_after(fn):
    """Decorator: run `fn`, then best-effort trigger a background autosync, then return fn's result."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        result = fn(*a, **k)
        try:
            autosync_async()
        except Exception:
            pass
        return result
    return wrapper


# --- legacy cron migration --------------------------------------------------

def cleanup_legacy_cron() -> dict:
    """Best-effort removal of any leftover tagged cron lines from the old cron-based trigger.

    Reads the crontab; if there is none, returns {"status": "none"}. Otherwise drops every line
    containing the legacy tag, preserves all other lines verbatim, and reinstalls. Never raises.
    """
    try:
        listing = _run(["crontab", "-l"])
        if listing.returncode != 0:
            return _result("none")
        lines = listing.stdout.splitlines()
        kept = [ln for ln in lines if LEGACY_CRON_TAG not in ln]
        removed = len(lines) - len(kept)
        if removed == 0:
            return _result("none")
        data = "\n".join(kept).rstrip("\n")
        if data:
            data += "\n"
        install = _run(["crontab", "-"], input_text=data)
        if install.returncode != 0:
            return _result("error", detail=install.stderr.strip())
        return _result("cleaned", removed=removed)
    except Exception as exc:
        return _result("error", detail=str(exc))
