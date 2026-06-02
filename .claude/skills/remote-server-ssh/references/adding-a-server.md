# Adding a Server to This Catalogue

This skill is built to grow. Adding a server is two coordinated edits — never invent
connection values; record only documented ones and mark anything unconfirmed as pending.

## Steps

1. **Pick the role.** Reuse an existing type (webserver, NPM/TLS edge, Forgejo) or
   introduce a new one. The role is what the reader scans for first.

2. **Add a short blurb to `SKILL.md`** under "Server types", in the same shape as the
   existing three:
   - one or two sentences naming the role and its place in the topology,
   - a single `ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes ... user@host` line,
   - a link to the new reference file.
   Keep it short — SKILL.md is the index, not the detail.

3. **Create `references/<server>.md`** with the full entry:
   - a connection table (Role, IP, SSH user, SSH key, Admin SSH port),
   - a ready-to-run connect command,
   - the server's place in the topology,
   - role-specific inspection notes,
   - a "Pending / not-yet-determined" section for any unconfirmed value.

4. **Update the topology block in `SKILL.md`** if the new host changes the request path.

## Grounding rules (carry over the repo's "documented, not guessed" stance)

- Use a real value only if it is documented (an existing skill entry, a config/unit file,
  a project note) or the user states it directly.
- If a value isn't confirmed, write a clear placeholder (e.g. `<NEW_IP>`) and list it under
  "Pending" — do not fill the gap with a guess.
- Keep the key/connection convention consistent: explicit `-i ~/.ssh/id_ed25519` plus
  `-o IdentitiesOnly=yes`, non-default ports via `-p`.

## Connection-value template

```
| Field          | Value |
|----------------|-------|
| Role           |  |
| IP             |  |
| SSH user       |  |
| SSH key        | ~/.ssh/id_ed25519 |
| Admin SSH port |  |
```
