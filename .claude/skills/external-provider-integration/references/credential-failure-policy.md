# Credential Failure Policy

If a provider action requires credentials, missing credentials must fail clearly.

Do not:

- fake success
- silently skip the integration path
- replace the missing secret with a placeholder and continue
- reinterpret an auth failure as a domain success

## Acceptable behavior

- raise or return a clear configuration error
- surface which credential or auth precondition is missing
- stop the write path before side effects become ambiguous

## Narrow exception

Only allow a documented degraded mode, such as read-only lookup without write credentials,
when the integration contract explicitly defines that mode and callers can distinguish it
from full capability.
