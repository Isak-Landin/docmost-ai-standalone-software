# Official Contract First

All endpoints, methods, authentication rules, field meanings, and response shapes must
come from the provider's official published documentation.

Never:

- invent an endpoint
- infer a contract only from another codebase
- treat observed payloads as authoritative when they conflict with official docs

## Wrapper method contract

Each method that wraps a provider call should make these facts easy to verify:

- HTTP method and path
- authentication mechanism
- required parameters
- important request fields
- return shape summary

Docstrings, inline contract blocks, or nearby comments are acceptable as long as the
information stays with the wrapper method and is easy to audit.
