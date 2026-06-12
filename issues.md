# Known Issues

Status:
- ISSUE-2 (Markdown INGEST re-interpretation): RESOLVED for the manifested case (flanking
  `_`/`__`) by write-path escaping deployed 2026-06-12 (f3eaf1a); the latent `$`/`$$` math variant
  is not auto-escaped and stays mitigated by the backtick convention. Symptom, mechanism, recipe,
  and resolution below.

This file is the dedicated issues log for docmost-mcp-server.

---

## ISSUE-2: Markdown INGEST re-interpretation - unescaped markdown-special tokens are rewritten on first push (RESOLVED for flanking underscores; $/math residual)

Severity: LOW-MEDIUM. It is NOT whole-page and NOT silent on untouched sections:
it only rewrites the specific token, and only on the first push of the unescaped form (it is stable
thereafter). It still loses the author's literal intent and yields wrong-looking docs.
Discovered: 2026-06-11, during a HostNodex security-docs sync of the `hostnodexdocs` space.

### Symptom (observed, exact)

A literal code/path token that contains a double-underscore pair flanked by non-alphanumeric
characters - canonically the Python dunder file `app/__init__.py` - is rewritten after a
push + round-trip so that the `__init__` becomes bold `**init**`:

    app/__init__.py   ->   app/**init**.py

The surrounding `app/`, the `.py`, and any `:LINE` / `:LINE-RANGE` suffix are preserved; only the
`__...__` pair is converted. Exact strings observed this run:

    app/__init__.py around lines 70 to 106   ->   app/**init**.py around lines 70 to 106
    app/__init__.py:90                        ->   app/**init**.py:90
    app/__init__.py:259-288 / :283 / :291-306 / :310-364 / :356-364 / :388-408   ->   ...**init**.py...

### Affected pages (this run, space `hostnodexdocs` = 019dc725-9a37-7b91-b1a0-7f30a408efc0)

Every page whose pushed source referenced `app/__init__.py` unescaped. 9 pages:

Newly created this session (the security tree, 8 pages - each discusses the shared app factory at
`app/__init__.py`, so each carried the token):
- Hardening Plan                                  (security/hardening-plan)
- Authentication and Session                      (security/authentication-and-session)
- Access Control and IDOR                         (security/access-control-and-idor)
- Injection                                       (security/injection)
- Request Forgery, Origin and Webhook Integrity   (security/request-forgery-origin-and-webhook-integrity)
- Secrets and Configuration                       (security/secrets-and-configuration)
- Transport and Security Headers                  (security/transport-and-security-headers)
- Cross-Site Scripting and CSP                    (security/xss-and-content-security-policy)

Pre-existing, already carrying the artifact from an earlier push (1 page):
- Developer Guide                                 (slug K1zWyVTqAq/XlU4TYLLgP)

NOT affected: pages that reference other paths only (e.g. `app/security/throttle.py`,
`app/config.py`, `app/blueprints/auth/routes.py`, `docker/nginx/nginx.conf`). Those contain no
`__word__` pair, so Docmost leaves them literal - e.g. the Rate Limiting page round-tripped clean.

### Root cause (an INGEST asymmetry owned by Docmost, NOT an egress bug)

1. The write layer ships the raw local markdown string to Docmost with `format: "markdown"`
   (`app/write/docmost.py`). Docmost parses it server-side with `marked` (CommonMark, pinned
   v0.71.1, `packages/editor-ext/src/lib/markdown/`), plus its callout and math extensions. This
   repo does not configure or constrain that parser.
2. CommonMark strong-emphasis rule: `__text__` becomes `<strong>` when the opening `__` is
   left-flanking and the closing `__` is right-flanking. In `app/__init__.py` the `__` before
   `init` is preceded by `/` and the `__` after `init` is followed by `.`; both pairs sit at a
   non-alphanumeric boundary, so the "no intraword underscore emphasis" restriction does NOT block
   them, and `__init__` is parsed as strong `init`. (By contrast `a__b__c` between letters would
   NOT emphasize - the boundary chars `/` and `.` are what enable it here.)
3. The now-correct egress renderer faithfully serializes the stored `<strong>` node as `**init**`
   (turndown uses `*` for emphasis). So the round-trip is "correct" for how Docmost INTERPRETED
   the input - the loss happened at INGEST, before egress ever runs. The egress renderer fix
   cannot prevent it.
4. Idempotency: it is a ONE-TIME transform on the first push of the unescaped form. `app/**init**.py`
   re-ingests as the same `<strong>` and re-egresses identically, so there is no ongoing per-sync
   drift (this is why it is far less severe).

Same family, latent (did not manifest this run only because the content had none): a bare `$...$`
or `$$...$$` is grabbed by Docmost's math extension on ingest (already noted in the roundtrip
memory). In general, ANY token meaningful to `marked` that is shipped unescaped and outside a code
span is at risk: a line-leading `#` / `>` / `-` / `+` / `*` / `|`, `__bold__`, flanking `*em*` /
`_em_`, `[text](`, a backtick run, `$...$`.

### How to reproduce (safely, in a throwaway page)

1. In a throwaway test page, set the body to a single line:
   `the factory at app/__init__.py:90 builds the app`.
2. Push it (`sync_space` / `sync_page`).
3. Read the local `page.md` back (the helper overwrites it with the round-tripped canonical form).
   Observe `app/**init**.py:90`.
4. Generalize: any `X__Y__Z` where the `__` pairs sit at non-alphanumeric boundaries bolds `Y`;
   `$x$` / `$$x$$` become math. A backticked `` `app/__init__.py` `` round-trips literally.

### Resolution (implemented + deployed 2026-06-12, f3eaf1a)

Option A (write-path escaping) was implemented for the manifested case. `app/write/ingest_escape.py`
(`escape_markdown_for_ingest`) escapes flanking `_`/`__` that are NOT inside inline code or a fenced
block before `app/write/docmost.py` sends the markdown with `format:"markdown"`, so `marked` stores
them as literal text. It mirrors the egress convention (emphasis is `*`/`**`, flanking `_`/`__` is
literal - `_apply_marks` / `_UNDER_RUN`), is code-aware, and is idempotent: a `(?<!\\)` guard never
re-escapes an already-escaped `\_`, so the canonical read-back re-pushes as a no-op and the revision
hash stays stable. Verified live against Docmost - `app/__init__.py:90` now reads back as literal
`app/\_\_init\_\_.py:90` (not bold `**init**`), a backticked path and a real `**bold**` are
untouched, and re-pushing the escaped form returns an identical revision hash. Tests:
`tests/test_ingest_escape.py`.

Residual (not auto-fixed): the `$...$` / `$$` math variant of the same asymmetry. The escaper
deliberately leaves `$` alone - stably escaping it would also require the egress to escape literal
`$`, and would turn any genuinely-intended math literal. Math is effectively never used in these
technical docs, so it stays covered by the backtick convention below; auto-escaping `$` is a
follow-up only if math is confirmed never-wanted.

### Still recommended: authoring convention

Backtick code, paths, and dunders (`` `app/__init__.py` ``). Docmost leaves code-span content
literal, so it round-trips faithfully regardless - and it is still required for the `$`/math
residual above.

### Key references

- Write / ingest: `app/write/docmost.py` sends markdown with `format: "markdown"`, now after
  `app/write/ingest_escape.py` neutralizes flanking `_`/`__` outside code (the ISSUE-2 fix).
- Docmost ingest grammar (NOT in this repo): `marked` CommonMark + callout + math extensions,
  `packages/editor-ext/src/lib/markdown/` (Docmost v0.71.1).
- Egress (correct, faithful to the stored node - not the cause): `app/query/prosemirror.py`.
- Asymmetry list / authoring guidance: the `docmost-mcp-roundtrip-bug` note in the HostNodex
  Claude home memory.
