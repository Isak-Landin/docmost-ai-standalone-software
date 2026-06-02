---
name: documented-answers
description: Answer any software, tooling, configuration, API, protocol, standards, or otherwise factual question by grounding it in authoritative documented sources (official docs, specs/standards, vendor docs, source code) rather than recollection or best-guess. Use whenever a prompt turns on how something actually behaves, version-specific behavior, defaults, configuration, supported features, or any claim checkable against primary documentation.
when_to_use: Any technical or factual question — "how does X work", "what does this flag/option do", "is Y supported", API/CLI/config behavior, error messages, version differences, standards/specs. Trigger phrases include "how do I", "does X support", "what's the correct", "is it true that", "why does".
---

# Documented Answers

Ground every factual or technical claim in authoritative documentation. Never present a recollection or an inference as established fact. When there is no verified source, say so plainly instead of guessing.

## Procedure

1. **Separate checkable claims from opinion.** Identify each factual claim the answer depends on (behavior, defaults, feature support, syntax, version differences).
2. **Find the primary source.** Use WebSearch/WebFetch to locate the *authoritative* source: official documentation, the spec/standard (e.g. RFC, W3C/WHATWG, ECMA, POSIX), vendor docs, or the project's own source code. Use blogs, forums, and Q&A sites only to *locate* a primary source — then verify against the primary source itself.
3. **Check version and context.** Confirm the source applies to the relevant version, platform, or edition. Call out when behavior is version-specific.
4. **Quote and cite.** Quote the relevant line(s) and include the URL. The reader should be able to follow the link and see the same thing.
5. **Mark confidence explicitly.**
   - *Verified* — backed by a cited source; state it plainly.
   - *Unverified* — you believe it but could not confirm it; label it as such and never blend it into verified claims.
6. **When sources are missing or conflict**, say so directly: what you searched for, what you found, and what would resolve it. Do not fabricate a confident answer to fill the gap.

## Rules

- No best-guessing presented as fact. "I couldn't find a source to confirm this" is a valid and preferred answer over a confident fabrication.
- Primary sources beat secondary. Official docs / specs / source code over articles and forum posts.
- Cite with working URLs, preferring the canonical/official domain.
- If a question can be settled by reading code or config already in the workspace, read it rather than assuming.
