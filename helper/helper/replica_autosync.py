"""Automatic git backup of an in-repo Docmost replica.

Ownership model (see the plan): cron is a DUMB trigger. Its tagged line only invokes
`sync --repo <repo-top>`; it never runs git or touches files itself. This module is the single
owner of both the cron lifecycle (`ensure_cron`) and the git decision + execution (`sync`).
`sync` is the gatekeeper: it re-checks the enable gate LIVE, re-validates that each replica root
truly belongs to the given repo, and only then commits and pushes the replica subtree to the
repo's existing remote. Trusting a directly-targeting cron would leave the behaviour vulnerable to
later changes (disabled flag, moved replica, key change); routing everything through this module
keeps the gate authoritative.

This is a helper-client concern (the replica lives on the helper's machine), NOT a bridge route.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running both as `python -m helper.replica_autosync` and as a direct script path
# (the cron entry uses the direct path), mirroring server.py's sys.path bootstrap.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helper.replica import read_replica_header  # noqa: E402

# --- contract constants -----------------------------------------------------

ENABLE_ENV = "DOCMOST_REPLICA_GIT_AUTOSYNC"        # opt-in flag, loaded per repo via direnv/.envrc
INTERVAL_ENV = "DOCMOST_REPLICA_GIT_AUTOSYNC_INTERVAL"  # cron interval in minutes (optional)
REMOTE_ENV = "DOCMOST_REPLICA_GIT_REMOTE"          # push remote name (optional; default below)
DEFAULT_INTERVAL_MIN = 10
DEFAULT_REMOTE = "forgejo"
TAG_PREFIX = "# docmost-replica-autosync:"          # crontab line tag -> "<TAG_PREFIX><repo-top>"
COMMIT_USER_NAME = "replica-autosync"
COMMIT_USER_EMAIL = "replica-autosync@docmost-helper.local"
COMMIT_MESSAGE = "replica"
LOG_PATH = os.path.expanduser("~/.cache/docmost-replica-autosync.log")

log = logging.getLogger("docmost.replica_autosync")


# --- small process helpers --------------------------------------------------

def _run(args: list[str], cwd: str | None = None, env: dict | None = None,
         input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd, env=env, input=input_text,
        capture_output=True, text=True, timeout=timeout,
    )


def _result(status: str, **kw) -> dict:
    return {"status": status, **kw}


# --- git / repo introspection ----------------------------------------------

def _repo_top(start: str) -> str | None:
    """The git work-tree top containing `start`, or None if `start` is not in a git repo."""
    r = _run(["git", "-C", start, "rev-parse", "--show-toplevel"])
    if r.returncode != 0:
        return None
    top = r.stdout.strip()
    return os.path.realpath(top) if top else None


def _find_replica_roots(repo_top: str) -> list[str]:
    """Every directory under repo_top that carries a `_replica.json` marker (excluding .git).
    Same marker the helper itself uses (replica.discover_replica_root), so there is no hardcoded
    path and a renamed/restructured replica is found automatically."""
    roots: list[str] = []
    for header in Path(repo_top).rglob("_replica.json"):
        if ".git" in header.parts:
            continue
        roots.append(str(header.parent))
    return roots


def _current_branch(repo_top: str) -> str | None:
    r = _run(["git", "-C", repo_top, "rev-parse", "--abbrev-ref", "HEAD"])
    branch = r.stdout.strip()
    if r.returncode != 0 or not branch or branch == "HEAD":  # HEAD => detached
        return None
    return branch


def _has_remote(repo_top: str, name: str) -> bool:
    r = _run(["git", "-C", repo_top, "remote"])
    return name in r.stdout.split()


# --- live environment gate --------------------------------------------------

def _resolve_repo_env(repo_top: str) -> dict[str, str]:
    """Resolve the repo's CURRENT environment exactly as direnv would for that directory, so the
    enable gate and GIT_SSH_COMMAND reflect the live `.envrc` (not whatever was true when the cron
    line was written). Falls back to the inherited process env if direnv is unavailable or the dir
    is not allowed (in which case the enable flag is simply absent -> fail closed)."""
    direnv = shutil.which("direnv")
    if direnv:
        r = _run([direnv, "exec", repo_top, "env"], cwd=repo_top, timeout=30)
        if r.returncode == 0:
            env: dict[str, str] = {}
            for line in r.stdout.splitlines():
                key, sep, value = line.partition("=")
                if sep:
                    env[key] = value
            return env
    return dict(os.environ)


def _enabled_mode(env: dict) -> str | None:
    """None = disabled; 'push' = commit+push; 'commit' = commit only."""
    val = (env.get(ENABLE_ENV) or "").strip().lower()
    if val in ("", "0", "false", "off", "no"):
        return None
    if val == "commit":
        return "commit"
    return "push"


# --- per-repo lock (prevents overlapping cron runs) -------------------------

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


# --- the gatekeeper route ---------------------------------------------------

def sync(repo: str) -> dict:
    """Validate and, if everything passes, commit + push the repo's replica subtree.

    Order: live enable gate -> ownership validation -> preconditions -> locked commit/push.
    Never raises; returns a status dict and logs the outcome. A failure never corrupts or blocks.
    """
    repo_top = _repo_top(repo)
    if not repo_top:
        return _result("skipped", reason="not a git repo", repo=repo)
    if os.path.realpath(repo) != repo_top:
        # cron must pass the repo top exactly; a mismatch means a stale/moved entry.
        return _result("skipped", reason="repo arg is not the work-tree top", repo=repo, top=repo_top)

    env = _resolve_repo_env(repo_top)
    mode = _enabled_mode(env)
    if not mode:
        return _result("disabled", repo=repo_top)

    # Ownership validation: keep only replica roots that genuinely live in THIS repo.
    roots: list[str] = []
    for root in _find_replica_roots(repo_top):
        root_top = _repo_top(root)
        if root_top != repo_top:
            log.warning("dropping replica root outside repo (%s -> %s)", root, root_top)
            continue
        if not (Path(root) / "_replica.json").is_file():
            continue
        if not read_replica_header(root).get("space_id"):
            log.warning("dropping replica root without a space_id: %s", root)
            continue
        roots.append(root)
    if not roots:
        return _result("skipped", reason="no valid replica roots", repo=repo_top)

    # Preconditions.
    branch = _current_branch(repo_top)
    if not branch:
        return _result("skipped", reason="detached HEAD", repo=repo_top)
    remote = (env.get(REMOTE_ENV) or DEFAULT_REMOTE).strip()
    if mode == "push" and not _has_remote(repo_top, remote):
        return _result("skipped", reason=f"no '{remote}' remote", repo=repo_top)

    lock = _acquire_lock(repo_top)
    if lock is None:
        return _result("skipped", reason="another autosync run holds the lock", repo=repo_top)
    try:
        return _commit_and_push(repo_top, roots, branch, mode, remote, env)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        except OSError:
            pass


def _commit_and_push(repo_top: str, roots: list[str], branch: str, mode: str,
                     remote: str, env: dict) -> dict:
    rels = [os.path.relpath(r, repo_top) for r in roots]

    # Stage adds/modifications/deletions within the replica subtree only.
    add = _run(["git", "-C", repo_top, "add", "-A", "--", *rels])
    if add.returncode != 0:
        log.error("git add failed: %s", add.stderr.strip())
        return _result("error", stage="add", detail=add.stderr.strip(), repo=repo_top)

    # Nothing staged for the replica paths -> clean no-op (scoped to rels, so unrelated staged
    # code never makes this fire). --quiet exits 0 when there is no diff, 1 when there is.
    if _run(["git", "-C", repo_top, "diff", "--cached", "--quiet", "--", *rels]).returncode == 0:
        log.info("no replica changes to commit (%s)", repo_top)
        return _result("ok", committed=False, pushed=False, repo=repo_top, branch=branch)

    # Partial (pathspec) commit: commits ONLY the replica paths, never unrelated staged code.
    commit = _run([
        "git", "-C", repo_top,
        "-c", f"user.name={COMMIT_USER_NAME}",
        "-c", f"user.email={COMMIT_USER_EMAIL}",
        "commit", "-m", COMMIT_MESSAGE, "--", *rels,
    ])
    if commit.returncode != 0:
        log.error("git commit failed: %s", (commit.stderr or commit.stdout).strip())
        return _result("error", stage="commit",
                       detail=(commit.stderr or commit.stdout).strip(), repo=repo_top)

    if mode != "push":
        log.info("committed replica (commit-only mode) on %s", repo_top)
        return _result("ok", committed=True, pushed=False, repo=repo_top, branch=branch)

    # Push to the existing remote with the live deploy key; never force.
    git_env = dict(os.environ)
    if env.get("GIT_SSH_COMMAND"):
        git_env["GIT_SSH_COMMAND"] = env["GIT_SSH_COMMAND"]
    push = _run(["git", "-C", repo_top, "push", remote, branch], env=git_env, timeout=120)
    if push.returncode != 0:
        log.warning("push to %s %s failed (commit kept): %s", remote, branch, push.stderr.strip())
        return _result("committed", committed=True, pushed=False,
                       detail=push.stderr.strip(), repo=repo_top, branch=branch)
    log.info("committed + pushed replica to %s %s (%s)", remote, branch, repo_top)
    return _result("ok", committed=True, pushed=True, repo=repo_top, branch=branch)


# --- cron lifecycle (helper-owned) -----------------------------------------

def _read_crontab() -> list[str]:
    r = _run(["crontab", "-l"])
    if r.returncode != 0:  # no crontab installed yet
        return []
    return r.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    data = "\n".join(lines).rstrip("\n") + "\n"
    r = _run(["crontab", "-"], input_text=data)
    if r.returncode != 0:
        raise RuntimeError(f"crontab install failed: {r.stderr.strip()}")


def _tag_repo(line: str) -> str | None:
    """Return the repo path encoded in a tagged autosync line, else None."""
    idx = line.find(TAG_PREFIX)
    if idx == -1:
        return None
    return line[idx + len(TAG_PREFIX):].strip()


def ensure_cron(interval_min: int | None = None) -> dict:
    """Ensure exactly one tagged cron line for the current repo, pruning dead ones. Only ever
    touches this module's own tagged lines; all other crontab entries are preserved verbatim."""
    repo_top = _repo_top(os.getcwd())
    if not repo_top:
        return _result("skipped", reason="cwd is not a git repo", cwd=os.getcwd())

    if interval_min is None:
        try:
            interval_min = int(os.environ.get(INTERVAL_ENV, DEFAULT_INTERVAL_MIN))
        except ValueError:
            interval_min = DEFAULT_INTERVAL_MIN

    python = sys.executable
    script = os.path.abspath(__file__)
    tag = f"{TAG_PREFIX}{repo_top}"
    new_line = f"*/{interval_min} * * * * {python} {script} sync --repo {repo_top}  {tag}"

    kept: list[str] = []
    for line in _read_crontab():
        repo_of_line = _tag_repo(line)
        if repo_of_line is None:
            kept.append(line)            # not ours -> preserve verbatim
            continue
        if repo_of_line == repo_top:
            continue                     # our current repo -> drop, we re-add fresh below
        if os.path.isdir(repo_of_line):
            kept.append(line)            # another repo that still exists -> keep
        # else: tagged line for a vanished repo -> prune (drop)
    kept.append(new_line)
    _write_crontab(kept)
    return _result("ensured", repo=repo_top, interval_min=interval_min, line=new_line)


# --- logging + CLI ----------------------------------------------------------

def _setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        handlers.append(logging.FileHandler(LOG_PATH))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="replica_autosync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sync", help="validate + commit/push a repo's replica subtree")
    sp.add_argument("--repo", required=True, help="git work-tree top of the repo to sync")
    sub.add_parser("ensure-cron", help="ensure the tagged cron line for the cwd repo")

    args = parser.parse_args(argv)
    _setup_logging()

    if args.cmd == "sync":
        res = sync(args.repo)
        print(json.dumps(res))
        return 1 if res.get("status") == "error" else 0
    if args.cmd == "ensure-cron":
        res = ensure_cron()
        print(json.dumps(res))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
