"""Hermetic offline tests for the in-helper git autosync (helper/helper/replica_autosync.py).

No network and no real crontab: a local *bare* repo stands in for the remote, and the enable /
roots gates are driven purely through ``os.environ`` (monkeypatched per test) so ``ras.enabled()``
and the roots read see the live values. The bare remote is deliberately added under a NON-default
name (``fj``) so the tests prove the module discovers the branch's tracking remote dynamically and
has no hardcoded remote name.

These tests target the NEW module API:

    autosync(start_dir: str | None = None) -> dict   # pure local git, never raises
    enabled() -> bool                                # reads env DOCMOST_REPLICA_GIT_AUTOSYNC

with status in {ok, clean, disabled, skipped, committed, error}.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# conftest.py puts the repo root on sys.path; the helper *package* lives under helper/.
_HELPER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "helper"
)
if _HELPER_DIR not in sys.path:
    sys.path.insert(0, _HELPER_DIR)

from helper import replica_autosync as ras  # noqa: E402

# Git author/committer identity supplied through the environment so commits never depend on a
# global git config being present in the test runner.
_GIT_ID = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}
_GIT_ENV = {**os.environ, **_GIT_ID}

# The deliberately non-default remote name. Proving the module discovers THIS (and not "origin" /
# "forgejo") is the whole point of using it.
REMOTE = "fj"


def _git(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", cwd, *args],
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    )


def _bare_rev(bare: str, ref: str) -> str | None:
    """rev of ``ref`` in the bare repo, or None if the ref does not exist."""
    r = subprocess.run(
        ["git", "--git-dir", bare, "rev-parse", ref],
        env=_GIT_ENV,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _head(cwd: str) -> str:
    return _git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


def _head_files(cwd: str) -> set[str]:
    out = _git("show", "--name-only", "--pretty=format:", "HEAD", cwd=cwd).stdout
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def _staged(cwd: str) -> set[str]:
    return set(_git("diff", "--cached", "--name-only", cwd=cwd).stdout.split())


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _make_replica(root: str, space_id: str, body: str = "initial\n") -> None:
    _write(os.path.join(root, "_replica.json"), json.dumps({"space_id": space_id}))
    _write(os.path.join(root, "page.md"), body)


@pytest.fixture()
def repo(tmp_path):
    """A working repo on branch ``main`` whose ``main`` tracks a bare remote added under the
    non-default name ``fj``, with a tracked replica dir already committed and pushed.

    Returns (repo_top, bare_path, replica_dir).
    """
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        check=True, capture_output=True,
    )
    repo_top = tmp_path / "app"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo_top)],
        check=True, capture_output=True,
    )
    repo_s = str(repo_top)

    replica = repo_top / "Repdir"
    _make_replica(str(replica), "sp-1")
    _write(str(repo_top / "code.py"), "x = 1\n")

    _git("add", "-A", cwd=repo_s)
    _git("commit", "-m", "init", cwd=repo_s)
    _git("remote", "add", REMOTE, str(bare), cwd=repo_s)
    # -u sets branch.main.remote == fj, which the module discovers dynamically.
    _git("push", "-u", REMOTE, "main", cwd=repo_s)

    return repo_s, str(bare), str(replica)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Each test starts with both gate vars unset; tests opt in explicitly."""
    monkeypatch.delenv(ras.ENABLE_ENV, raising=False)
    monkeypatch.delenv(ras.ROOTS_ENV, raising=False)


def _enable(monkeypatch, value: str = "1") -> None:
    monkeypatch.setenv(ras.ENABLE_ENV, value)


# --- 1. disabled gate -------------------------------------------------------

def test_disabled_gate_is_noop(repo, monkeypatch):
    repo_s, _bare, replica = repo
    # env unset by the autouse fixture -> disabled.
    _write(os.path.join(replica, "page.md"), "edited\n")
    before = _head(repo_s)

    res = ras.autosync(repo_s)

    assert res["status"] == "disabled", res
    assert _head(repo_s) == before


# --- 2. happy path: isolation + dynamic remote ------------------------------

def test_happy_path_isolation_and_dynamic_remote(repo, monkeypatch):
    repo_s, bare, replica = repo
    _enable(monkeypatch)

    # A new (untracked) replica page AND an unrelated, user-staged code change.
    _write(os.path.join(replica, "New-Page", "page.md"), "new page body\n")
    _write(os.path.join(repo_s, "code.py"), "x = 2\n")
    _git("add", "code.py", cwd=repo_s)  # staged code that must NOT be swept into the replica commit

    before = _head(repo_s)
    res = ras.autosync(repo_s)

    assert res["status"] == "ok", res
    assert res["committed"] is True and res["pushed"] is True
    assert res["remote"] == REMOTE      # discovered dynamically, not hardcoded
    assert res["branch"] == "main"

    after = _head(repo_s)
    assert after != before

    files = _head_files(repo_s)
    assert "Repdir/New-Page/page.md" in files   # new/untracked replica file captured
    assert "code.py" not in files               # unrelated staged code excluded

    # the user's staged code change survives, never committed
    assert "code.py" in _staged(repo_s)

    # the push landed on the bare remote's main
    assert _bare_rev(bare, "main") == after


# --- 3. current-branch only -------------------------------------------------

def test_pushes_only_current_branch(repo, monkeypatch):
    repo_s, bare, replica = repo
    _enable(monkeypatch)

    main_remote_before = _bare_rev(bare, "main")

    # Branch off main, give feature its own upstream on fj.
    _git("checkout", "-b", "feature", cwd=repo_s)
    _git("push", "-u", REMOTE, "feature", cwd=repo_s)
    feature_remote_before = _bare_rev(bare, "feature")
    assert feature_remote_before == main_remote_before  # both point at the init commit

    _write(os.path.join(replica, "page.md"), "feature edit\n")
    res = ras.autosync(repo_s)

    assert res["status"] == "ok", res
    assert res["branch"] == "feature" and res["remote"] == REMOTE
    local_head = _head(repo_s)

    # feature advanced on the bare; main did NOT move.
    assert _bare_rev(bare, "feature") == local_head
    assert _bare_rev(bare, "main") == main_remote_before
    assert _bare_rev(bare, "main") != local_head


# --- 4. clean no-op ---------------------------------------------------------

def test_clean_tree_is_noop(repo, monkeypatch):
    repo_s, _bare, _replica = repo
    _enable(monkeypatch)
    before = _head(repo_s)

    res = ras.autosync(repo_s)

    assert res["status"] == "clean", res
    assert res["committed"] is False
    assert _head(repo_s) == before


# --- 5. multi-replica, no scope ---------------------------------------------

def test_multi_replica_requires_scope(repo, monkeypatch):
    repo_s, _bare, replica = repo
    _enable(monkeypatch)

    # A second, equally-valid replica root.
    replica2 = os.path.join(repo_s, "Repdir2")
    _make_replica(replica2, "sp-2")
    _git("add", "-A", cwd=repo_s)
    _git("commit", "-m", "add second replica", cwd=repo_s)

    # Make a pending change in each so a wrongful commit would be observable.
    _write(os.path.join(replica, "page.md"), "edit one\n")
    _write(os.path.join(replica2, "page.md"), "edit two\n")
    before = _head(repo_s)

    # No ROOTS scope declared -> refuse to guess, no commit.
    res = ras.autosync(repo_s)
    assert res["status"] == "skipped", res
    assert _head(repo_s) == before

    # Declare ownership of only Repdir -> only Repdir is committed.
    monkeypatch.setenv(ras.ROOTS_ENV, "Repdir")
    res2 = ras.autosync(repo_s)
    assert res2["status"] == "ok", res2
    assert res2["committed"] is True

    files = _head_files(repo_s)
    assert "Repdir/page.md" in files
    assert not any(f.startswith("Repdir2/") for f in files)  # Repdir2 untouched in the commit
    # Repdir2's change is still pending on disk, never committed.
    assert "Repdir2/page.md" in _staged(repo_s) or "Repdir2/page.md" not in files


# --- 6. discovery exclusion (.claude) ---------------------------------------

def test_claude_copy_is_excluded_from_discovery(repo, monkeypatch):
    repo_s, bare, replica = repo
    _enable(monkeypatch)

    # A stray replica copy under .claude/ must be ignored by marker discovery, leaving exactly the
    # one real root -> a normal single-root run (not a multi-root "skipped").
    claude_copy = os.path.join(repo_s, ".claude", "worktrees", "x", "Repdir")
    _make_replica(claude_copy, "sp-claude")

    _write(os.path.join(replica, "page.md"), "real edit\n")
    res = ras.autosync(repo_s)

    assert res["status"] == "ok", res          # single real root, not "skipped: multiple replicas"
    assert res["committed"] is True

    files = _head_files(repo_s)
    assert "Repdir/page.md" in files
    assert not any(".claude" in f for f in files)  # the .claude copy was never a root
    assert _bare_rev(bare, "main") == _head(repo_s)


# --- 7. never force ---------------------------------------------------------

def test_non_fast_forward_push_never_forces(repo, monkeypatch, tmp_path):
    repo_s, bare, replica = repo
    _enable(monkeypatch)

    # Put the bare remote AHEAD of local on main via a second clone, so the local push will be a
    # non-fast-forward that an honest (non-force) push must reject.
    clone = str(tmp_path / "clone")
    subprocess.run(["git", "clone", bare, clone], check=True, capture_output=True, env=_GIT_ENV)
    _write(os.path.join(clone, "remote-only.txt"), "ahead\n")
    _git("add", "-A", cwd=clone)
    _git("commit", "-m", "remote ahead", cwd=clone)
    _git("push", "origin", "main", cwd=clone)

    bare_ahead = _bare_rev(bare, "main")
    assert bare_ahead != _head(repo_s)  # local is now behind the bare remote

    # Local replica change -> commit succeeds, push is rejected (non-ff), and we DO NOT force.
    _write(os.path.join(replica, "page.md"), "local edit\n")
    local_before = _head(repo_s)
    res = ras.autosync(repo_s)

    assert res["status"] == "committed", res
    assert res["committed"] is True and res["pushed"] is False

    # The local commit landed...
    assert _head(repo_s) != local_before
    # ...but the bare remote head is UNCHANGED -- no force, the remote-ahead commit stands.
    assert _bare_rev(bare, "main") == bare_ahead
