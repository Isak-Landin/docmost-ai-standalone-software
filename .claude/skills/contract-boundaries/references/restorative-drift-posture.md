# Restorative Drift Posture

When code, runtime, docs, and contract notes disagree, default to restoring drift toward
the established canon rather than redesigning the surface.

## What this means

- Missing documentation does not justify inventing a new rule.
- Weak test coverage does not justify changing behavior.
- Live drift does not become canonical just because it currently works.
- A surprising value may still be correct if it is the established owner value.

## Live-environment drift

If runtime behavior suggests the deployed environment drifted from the repo:

1. Verify the live state against the repo and any contract registry.
2. Confirm whether the difference is intentional or accidental.
3. Surface the drift explicitly.
4. Do not silently codify the drift and do not silently revert it without direction.

## True contract changes

Only broaden from restoration to reinterpretation when the task explicitly asks for a new
canonical value or a new boundary rule.
