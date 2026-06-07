docmost-helper dev-branch test log  
date: 2026-06-04  
server (dev branch): http://64.112.126.69:8099 (helper/.env DOCMOST_MCP_SERVER_URL)  
helper: /home/isakuser/docmost-mcp-server/helper/server.py (stdio MCP "docmost-helper")

## WHAT WAS DONE

Exercised the docmost-helper surface end to end via the reconcile-first path:

1. create_space("general_docs", "generaldocs") -> space 019e9286-32eb-740c-84cc-a74bc133ef39
2. sync_space (empty) -> initialized local replica root at:  
  /home/isakuser/general_docs/generaldocs-replica/ (\_replica.json written)
3. Authored local-only pages (page.md per dir), one space, root child = each project we have docs on,  
  plus one nested sub-page to test nesting:  
  generaldocs-replica/forgejo/page.md  
  generaldocs-replica/vpn-psqlcluster/page.md  
  generaldocs-replica/vpn-psqlcluster/wireguard-vpn-concepts/page.md
4. sync_space -> created all three remotely (applied=created x3), nesting resolved correctly.
5. sync_space again -> idempotent (synced_count=3, applied=\[\]). Remote == local.

Final remote tree (get_space_tree):  
forgejo 019e9288-ffb9-7d60-9f61-dd69fa85629f (root)  
vpn-psqlcluster 019e9289-0064-7c7b-bd67-d2f1ad1b14f3 (root)  
WireGuard VPN concepts 019e9289-0100-7fdf-a54f-4145dc8a83c4 (child of vpn-psqlcluster)

OVERALL: no missing helper surfaces and no hard errors. Every tool used worked  
(list_spaces, create_space, sync_space, get_space_tree). The complications are  
markdown-fidelity bugs in the server round-trip and a few contract/semantic  
gotchas, detailed below.

# \================================================================================  
COMPLICATIONS / FINDINGS

FINDING 1 (significant) - Server mangles markdown emphasis that touches inline code.  
Referent: page content as stored/returned by the dev-branch server after sync.  
Conclusion: bold/italic spans (\*\* or \*) that contain or abut an inline `code`  
span get their markers relocated or duplicated, producing broken markdown.  
Evidence (concepts page, after sync; this is what came back AND what is now on disk):  
authored: the **peer's single tunnel address as a** `/32` (not a remote subnet).  
returned: the \*\*peer's single tunnel address as a \*\*`/32` (not a remote subnet).  
authored: **binds and is firewalled to its** `10.x` **tunnel address**  
returned: **binds and is firewalled to its** `10.x` **tunnel address**  
authored: _(This_ `/32` _+ no-forwarding adaptation ..._  
returned: \*(This `/32` + no-forwarding adaptation ...  
Mechanism / impact: the server normalizes markdown (likely a markdown&lt;-&gt;ProseMirror  
round-trip). The helper then writes the server's normalized content back to the  
LOCAL replica (sync.py \_apply_applied_item -> write_page), so the corruption is  
pushed into generaldocs-replica/.../page.md too. Net: emphasis next to inline code  
is unsafe; both remote render and local copy drift from the source.  
Workaround: avoid putting \*\* / \* immediately adjacent to `code`; add a space, or  
drop the emphasis around code spans.

FINDING 2 - synced_count does not mean "changes applied this run".  
Referent: the summary object returned by sync_space.  
Conclusion: synced_count counts pages already in sync (result\["synced"\]), NOT pages  
created/changed (those are in applied\[\]). A fresh create returns synced_count=0  
with 3 entries in applied\[\]; a later no-op re-sync returns synced_count=3, applied=\[\].  
Impact: checking "synced_count > 0" to confirm a push SUCCEEDED is wrong - it reads  
a successful create as if nothing happened. Check applied\[\]/errors\[\] instead.

FINDING 3 - Title derivation contradicts the tool-level content rule; causes duplicate H1.  
Referent: how a NEW local-only page gets its title vs. the helper's stated content rule.  
Conclusion: for reconcile/local-only pages the title is taken from the first line /  
H1 of page.md (replica.extract_title_from_page), whereas the MCP instructions and  
create_page/update_page say "title is a separate parameter, never an H1 in the body."  
Impact: the H1 stays in the body AND becomes the page title, so the rendered Docmost  
page shows the title plus a duplicate H1. (Observed: pages titled "forgejo" etc. whose  
body still starts with "# forgejo".)  
Note: there is no documented way to set a new local-only page's title WITHOUT a body H1  
except writing \_meta.json "title" by hand - which the docs say is helper-owned / do  
not edit. So the two rules are in tension for the create path.

FINDING 4 - Lossless normalization still mutates content and drifts the local replica.  
Referent: non-emphasis markdown normalization on sync.  
Conclusion: bare URLs are auto-linked ("https://x" -> "https://x") and a  
blank line is inserted before lists. Benign for rendering, but because the helper  
writes the normalized content back locally, generaldocs-replica/\*.md no longer matches  
the repo source even when the user changed nothing.  
Impact: do not expect the local replica page.md to be byte-identical to the source you  
authored; treat Docmost's normalized form as the post-sync truth.

FINDING 5 (positive) - Replica location resolves correctly via cwd; no override needed.  
Referent: where the replica root materialized.  
Conclusion: with the standard registration (env {}), DOCMOST_REPLICA_BASE defaults to "."  
and the helper process cwd is the repo (/home/isakuser/general_docs), so the replica  
landed at /home/isakuser/general_docs/generaldocs-replica/ with no local_root argument.  
Impact: the "replica in this repo" goal holds through the standard pattern; the earlier  
explicit-path override was unnecessary.

# \================================================================================  
STATE AT END

- Remote space general_docs is populated and matches the local replica (idempotent re-sync).
- Local replica: generaldocs-replica/ with \_replica.json, \_tree.json, and per-page  
  page.md + \_meta.json (helper-owned \_meta written correctly: id, slug_id, parent_page_id,  
  base_revision_hash, paths).
- Source repo docs under forgejo/ and vpn-psqlcluster/ were NOT modified by the sync.
