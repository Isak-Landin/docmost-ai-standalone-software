# Real Values Policy

This skill applies only when all of the following are true:

- the project is private
- the environment is controlled and the example file is intended to help the system boot correctly

## Required behavior

- Keep real working values in example env files when they are known.
- Keep cross-shared values coherent across every env file that mirrors them.
- Remove deprecated variables from examples instead of preserving stale placeholders.
- Resolve unknown real values from the correct source instead of inventing fake ones.

## Do not use placeholders for

- sandbox or internal API keys
- local or internal database URLs
- webhook signing secrets for controlled environments
- internal base URLs and ports
- any other value that must be correct for the system to work

## Unknown value workflow

When a real value is required but not known yet:

1. Check the repo's existing env files and contract registries.
2. Check the running dev environment or container inspect output.
3. Check the provider dashboard or sandbox configuration.
4. Add the real value once confirmed.

Do not leave a fake stand-in if the point of the example file is to be runnable.

## Outside this skill

If the repo is public, broadly distributed, or governed by a stricter secret-management
policy, follow that repo policy instead of this skill.
