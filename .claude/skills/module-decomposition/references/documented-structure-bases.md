# Documented Structure Bases

This document records the official documentation anchors used to generalize repo and
directory structures in this skill.

It is not a framework tutorial. Its purpose is to show that the generalized patterns in
`target-structure.md` are grounded in documented framework structure, then widened into
reusable repo guidance.

---

## Flask

Official docs:

- https://flask.palletsprojects.com/en/stable/tutorial/layout/

Documented basis:

- Flask's tutorial shows a package-owned application layout
- templates live under the app package
- static assets live under the app package
- tests live separately at repo level

Generalized rule:

- when Flask owns the rendered UI, keep `templates/` and `static/` inside the Flask app
  package or code root, and organize by route/blueprint family

---

## FastAPI

Official docs:

- https://fastapi.tiangolo.com/tutorial/bigger-applications/

Documented basis:

- FastAPI documents a package layout centered around `app/`
- routers are separated into their own package
- shared dependencies are separated into their own module
- the documented pattern is API-first and modular

Generalized rule:

- use `app/` or another single backend root for routers, services, schemas, and
  dependencies
- only add backend-owned `templates/` and `static/` when the FastAPI app truly renders
  HTML or serves first-party assets

---

## Django

Official docs:

- https://docs.djangoproject.com/en/stable/intro/reusable-apps/

Documented basis:

- Django documents reusable apps as self-contained packages
- `templates/<app_name>/` and `static/<app_name>/` live inside the app package
- project-level templates may also exist separately

Generalized rule:

- when Django apps own UI surfaces, keep template/static ownership at the app level
- use project-level template/static directories only for truly project-wide concerns

---

## Express

Official docs:

- https://expressjs.com/en/starter/generator.html

Documented basis:

- Express's documented generator creates separate `routes/`, `views/`, and `public/`
  directories
- public assets are split into stylesheets, javascripts, and images

Generalized rule:

- when Express (or similar Node backends) renders templates directly, use explicit
  route/view/public ownership and split assets into dedicated directories

---

## Nest

Official docs:

- https://docs.nestjs.com/first-steps

Documented basis:

- Nest's first-steps docs present a server-side application structure centered on `src/`
- the default documented shape is backend-first rather than template/static-first

Generalized rule:

- treat Nest as API/backend-first by default
- if the overall repo also owns HTML/CSS/JS, prefer a visible separate `frontend/`
  workspace unless the Nest app is explicitly responsible for server-rendered output

---

## Interpretation rule

This skill does **not** copy framework skeletons literally.

Instead it uses official docs to derive stable, generalized ownership rules:

- keep backend-owned frontend surfaces with the backend that renders them
- keep API-only backends free of fake template/static trees
- keep frontend apps as separate workspaces when they are truly separate applications
- keep repo structure guidance focused on package, directory, and ownership boundaries
