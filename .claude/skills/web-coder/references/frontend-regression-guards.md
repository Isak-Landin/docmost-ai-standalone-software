# Frontend Regression Guards

Use this reference when fixing or reviewing customer-visible HTML/CSS/JS changes where
the main risk is regression, drift, or accidental redesign rather than lack of
implementation knowledge.

## Why this exists

Recent frontend regressions were not caused by advanced browser tricks. They came from
scope drift:

- responsive containment bugs widened into broader shell changes
- page-local styling had no clear owner and fell through shared CSS
- customer-visible panels showed placeholder copy instead of real synced state
- markup/CSS changes risked breaking the JS and data hooks already wired to the page

This reference exists to keep web fixes restorative and contract-aware.

## What this file is for

**Todo**
- containment fixes
- dynamic-state rendering fixes
- markup/CSS/JS hook preservation
- deciding how to keep a narrow UI bug narrow

**Not todo**
- product redesign by accident
- changing repo ownership boundaries by yourself
- replacing broken dynamic state with fake placeholder state

## Guardrails

### 1. Fix the regression before redesigning the surface

- restore the broken behavior first
- avoid unrelated typography, spacing, or stylistic rewrites
- if a fix requires changing unrelated surfaces, stop and confirm scope rather than assuming cleanup is safe

### 2. Preserve real state, not placeholder state

Customer-visible UI must render one of:

- loading
- synced-empty
- explicit error
- real dynamic or provider-synced data

Do not replace broken dynamic rendering with fake example data or generic placeholder copy
that hides the actual state bug.

Legitimate empty/loading/error states are not placeholders. Hardcoded fake customer data is.
Synced-empty is also legitimate state: the data source was read successfully and the authoritative answer was an empty collection.

### 3. Preserve DOM and data hooks

Before changing markup:

- read the paired template/partial, CSS, and page JS together
- preserve IDs, data attributes, form names, ARIA relationships, and hook classes that existing JS or tests depend on
- do not rename or collapse structure just because the visual bug looks CSS-only

### 4. Containment first for responsive regressions

For shell/header/menu/dashboard overlap, clipping, or width drift:

1. treat it as a containment issue first
2. use the responsive shell containment pattern in `references/css-styling.md`
3. keep the change restorative

Preferred fixes:

- `minmax(0, 1fr)` for shared grid tracks
- `min-width: 0` on shrinkable flex/grid children
- explicit `max-width` / `width: min(...)` bounds for action controls and floating panels
- `overflow: hidden`, `text-overflow: ellipsis`, and `white-space: nowrap` for labels that must stay on one line

Avoid:

- unconstrained widths on mobile shell controls
- moving page-local bugs into a full shell redesign
- fixing overlap by hiding data that should remain visible

### 5. Pick the correct CSS owner before editing

`web-coder` does not decide repo ownership by itself.

Before choosing where the fix lives:

- consult the repo ownership/contract skill first (`contract-boundaries`, and `module-decomposition` when file placement/ownership is unclear)
- if the bug is page-local, prefer the page-owned CSS surface
- if the bug belongs to the shared shell, fix the shared shell surgically

Do not push a page-local regression into umbrella shell CSS just because that file is already loaded everywhere.

### 6. Check all real states that the same surface can enter

For a customer/admin panel, verify at least:

- populated state
- synced-empty state
- loading state
- error state when one exists
- narrow-width layout if the bug touched containment

### 7. Unknown-regression rule

If the change touches HTML/CSS on an existing interactive surface and you have not yet read
the paired JS/template owner, assume hidden dependencies exist and read them first.
