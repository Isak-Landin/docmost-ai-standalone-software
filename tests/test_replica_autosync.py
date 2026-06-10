"""Hermetic offline tests for helper/helper/replica_autosync.py.

No network and no real crontab: a local bare repo stands in for the 'forgejo' remote, and the
crontab read/write functions are monkeypatched. The live enable gate (_resolve_repo_env) is
monkeypatched so the tests do not depend on direnv or a .envrc.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# Make the helper package importable (helper/ holds the `helper` package).
_HELPER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "helper"
)
if _HELPER_DIR not in sys.path:
    sys.path.insert(0, _HELPER_DIR)

from helper import replica_autosync as ras  # noqa: E402

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", cwd, *args], env=_GIT_ENV,
                          capture_output=True, text=True, check=True)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


@pytest.fixture()
def repo(tmp_path):
    """A working repo on branch 'main' with a 'forgejo' remote (a local bare repo) and a tracked
    replica dir already pushed. Returns (repo_top, bare_path, replica_dir)."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True,
                   capture_output=True)
    repo_top = tmp_path / "app"
    subprocess.run(["git", "init", "-b", "main", str(repo_top)], check=True, capture_output=True)
    repo_s = str(repo_top)
    replica = repo_top / "Docmost-mcp-crud"
    _write(str(replica / "_replica.json"), json.dumps({"space_id": "sp-123", "slug": "x"}))
    _write(str(replica / "Overview" / "page.md"), "initial\n")
    _write(str(repo_top / "code.py"), "x = 1\n")
    _git("add", "-A", cwd=repo_s)
    _git("commit", "-m", "init", cwd=repo_s)
    _git("remote", "add", "forgejo", str(bare), cwd=repo_s)
    _git("push", "forgejo", "main", cwd=repo_s)
    return repo_s, str(bare), str(replica)


def _enable(monkeypatch, value="1"):
    monkeypatch.setattr(ras, "_resolve_repo_env", lambda repo_top: {ras.ENABLE_ENV: value})


def _head_files(repo_s: str) -> set[str]:
    out = _git("show", "--name-only", "--pretty=format:", "HEAD", cwd=repo_s).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def test_commits_only_replica_captures_new_and_pushes(repo, monkeypatch):
    repo_s, bare, replica = repo
    _enable(monkeypatch)

    # A new (untracked) replica page + a staged unrelated code change.
    _write(os.path.join(replica, "New-Page", "page.md"), "new page body\n")
    _write(os.path.join(repo_s, "code.py"), "x = 2\n")
    _git("add", "code.py", cwd=repo_s)  # user staged code that must NOT be swept in

    head_before = _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip()
    res = ras.sync(repo_s)

    assert res["status"] == "ok", res
    assert res["committed"] is True and res["pushed"] is True
    head_after = _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip()
    assert head_after != head_before

    files = _head_files(repo_s)
    assert "Docmost-mcp-crud/New-Page/page.md" in files  # new/untracked captured
    assert "code.py" not in files                         # staged code excluded
    # the user's staged code change is still staged, never committed
    staged = _git("diff", "--cached", "--name-only", cwd=repo_s).stdout.split()
    assert "code.py" in staged
    # push landed on the bare 'forgejo' remote
    remote_head = subprocess.run(["git", "--git-dir", bare, "rev-parse", "main"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    assert remote_head == head_after


def test_clean_tree_is_noop(repo, monkeypatch):
    repo_s, _bare, _replica = repo
    _enable(monkeypatch)
    head_before = _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip()
    res = ras.sync(repo_s)
    assert res["status"] == "ok" and res["committed"] is False
    assert _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip() == head_before


def test_disabled_gate_is_noop(repo, monkeypatch):
    repo_s, _bare, replica = repo
    monkeypatch.setattr(ras, "_resolve_repo_env", lambda repo_top: {})  # flag absent
    _write(os.path.join(replica, "Overview", "page.md"), "edited\n")
    head_before = _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip()
    res = ras.sync(repo_s)
    assert res["status"] == "disabled", res
    assert _git("rev-parse", "HEAD", cwd=repo_s).stdout.strip() == head_before


def test_commit_only_mode_does_not_push(repo, monkeypatch):
    repo_s, bare, replica = repo
    _enable(monkeypatch, value="commit")
    _write(os.path.join(replica, "Overview", "page.md"), "edited\n")
    remote_before = subprocess.run(["git", "--git-dir", bare, "rev-parse", "main"],
                                   capture_output=True, text=True, check=True).stdout.strip()
    res = ras.sync(repo_s)
    assert res["status"] == "ok" and res["committed"] is True and res["pushed"] is False
    remote_after = subprocess.run(["git", "--git-dir", bare, "rev-parse", "main"],
                                  capture_output=True, text=True, check=True).stdout.strip()
    assert remote_after == remote_before  # nothing pushed


def test_ownership_guard_drops_foreign_root(repo, monkeypatch):
    repo_s, _bare, _replica = repo
    _enable(monkeypatch)
    # An embedded, independent git repo carrying its own _replica.json: it is NOT part of this repo
    # (its rev-parse toplevel differs), so it must be dropped and never committed here.
    embedded = os.path.join(repo_s, "embedded")
    subprocess.run(["git", "init", "-b", "main", embedded], check=True, capture_output=True)
    _write(os.path.join(embedded, "_replica.json"), json.dumps({"space_id": "other"}))
    # Remove the legitimate replica so the only candidate is the foreign one.
    import shutil
    shutil.rmtree(_replica)
    res = ras.sync(repo_s)
    assert res["status"] == "skipped" and res["reason"] == "no valid replica roots", res


def test_not_a_git_repo_skips(tmp_path, monkeypatch):
    _enable(monkeypatch)
    res = ras.sync(str(tmp_path))
    assert res["status"] == "skipped"


def test_ensure_cron_idempotent_and_prunes(repo, monkeypatch, tmp_path):
    repo_s, _bare, _replica = repo
    monkeypatch.chdir(repo_s)
    captured: dict[str, list[str]] = {}
    vanished = str(tmp_path / "gone")  # a tagged repo path that no longer exists
    existing = [
        "0 3 * * * /usr/bin/backup-something  # unrelated user job",
        f"*/9 * * * * py x sync --repo {vanished}  {ras.TAG_PREFIX}{vanished}",
        f"*/9 * * * * py x sync --repo {repo_s}  {ras.TAG_PREFIX}{repo_s}",  # stale current-repo line
    ]
    monkeypatch.setattr(ras, "_read_crontab", lambda: list(existing))
    monkeypatch.setattr(ras, "_write_crontab", lambda lines: captured.__setitem__("lines", lines))

    res = ras.ensure_cron(interval_min=5)
    assert res["status"] == "ensured"
    lines = captured["lines"]
    # unrelated job preserved verbatim
    assert "0 3 * * * /usr/bin/backup-something  # unrelated user job" in lines
    # vanished-repo tagged line pruned
    assert not any(ras._tag_repo(l) == vanished for l in lines)
    # exactly one tagged line for the current repo, with the new interval
    mine = [l for l in lines if ras._tag_repo(l) == os.path.realpath(repo_s)]
    assert len(mine) == 1 and mine[0].startswith("*/5 ")

    # second run replaces, never duplicates
    monkeypatch.setattr(ras, "_read_crontab", lambda: list(lines))
    ras.ensure_cron(interval_min=5)
    lines2 = captured["lines"]
    assert len([l for l in lines2 if ras._tag_repo(l) == os.path.realpath(repo_s)]) == 1
