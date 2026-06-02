# Local Authoring and Delivery

Keep the working locations distinct:

1. **Local repo** - where source code is edited and committed
2. **Forgejo source remote** - where commits are pushed; the remote is named `forgejo` (it replaces the previous `origin`)
3. **Remote runtime** - where services run and are observed

## Rules

- Make source changes in the local repo.
- Use the remote runtime for logs, process state, and validation.
- Deliver code through the repo's existing source path: `git push forgejo <branch>` from local, then `git pull forgejo <branch>` (or deploy) on the remote. The remote is `forgejo`, not `origin`.
- Do not treat an emergency remote file edit as the final fix.

## Why this matters

If local code and deployed code stop matching, debugging gets harder and later deploys
silently undo ad hoc remote changes.
