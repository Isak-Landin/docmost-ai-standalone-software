# Environment Owner Classification

Before fixing a provider-facing bug, classify which owner is actually wrong.

## Three-way classification

### A. Application bug

The application is sending the wrong request, misreading the documented response, or
making the wrong state decision.

### B. Mock or harness drift

A local mock, contract harness, fixture set, or simulated provider does not match the
documented provider contract.

### C. Provider-side behavior, credentials, or environment mismatch

The live sandbox or provider account behaves differently because of real account state,
missing credentials, permissions, feature flags, or documented provider constraints.

## Workflow

1. Compare the failing behavior to official docs.
2. Compare app requests to mock or harness behavior.
3. Compare mock or harness behavior to the real provider sandbox when possible.
4. Fix the actual owner instead of changing every layer to match the wrong one.
