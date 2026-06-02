# Frontend Targets

Use this file when the repo owns a frontend application or reusable frontend package.

This file is still about repo, package, and directory structure - not CSS or component
implementation inside files.

---

## 1. SPA target

Use for React, Vue, Svelte, Solid, or similar client-side applications.

```text
repo/
  package.json
  src/
    app/ or router/
    pages/
      <route>.tsx
    features/
      <domain>/
    components/
      <component>/
    hooks/ or composables/
    services/ or api/
    state/
    styles/
    assets/
  public/ or static/
  tests/
```

### Rules

- `pages/` own route composition
- `features/` exist only when 2 or more files share a product/domain concern
- `components/` are for reusable UI, not route-specific page assemblies
- `services/api/` own outbound API access

---

## 2. SSR or full-stack frontend target

Use for Next.js, Nuxt, SvelteKit, Remix, Astro SSR, or similar frameworks.

```text
repo/
  package.json
  src/ or app/
    routes/ or pages/ or app/
    components/
    features/
    lib/ or services/
    hooks/ or composables/
    styles/
    assets/
  public/
  tests/
```

### Rules

- route tree stays framework-native
- reusable UI stays under `components/`
- app/business utilities stay under `lib/` or `services/`
- keep route-specific loaders/actions close to route structure when framework-native

---

## 3. Static site target

Use for documentation sites, marketing sites, or generators such as Astro static mode,
Eleventy, Hugo wrappers, or similar setups.

```text
repo/
  package.json or generator config
  src/ or site/
    pages/
    layouts/
    components/
    content/
    styles/
    assets/
  public/
```

### Rules

- content owns authored documents/content entries
- layouts own reusable shell structures
- components own reusable content/UI fragments

---

## 4. Component library target

Use when the repo publishes reusable UI components rather than one app.

```text
repo/
  package.json
  src/
    index.ts
    components/
      <component>/
        index.ts
        <component>.tsx
        styles.ts or styles/
    hooks/
    tokens/ or theme/
    utils/
  stories/ or .storybook/
  tests/
  examples/ or demo/
```

### Rules

- component domain folder justified when a component has multiple sibling files
- tokens/theme are shared design system concerns
- example/demo app stays separate from published component source

---

## 5. Backend-owned frontend exception

If the "frontend" is actually owned by a backend that renders the UI, do **not** force
a standalone frontend tree. Use the backend-owned structures documented in
`target-structure.md` instead.
