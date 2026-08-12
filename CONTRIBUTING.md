# Contributing

Contributions are welcome when the experiment stays deterministic and inspectable.

1. Keep the core package free of runtime dependencies and network calls.
2. Preserve common-random-number pairing across policies.
3. Add a test for every new fault, recovery action, or metric.
4. Document whether a result represents success, safe success, degradation, or an unsafe side effect.
5. Never commit production traces, credentials, customer data, or private endpoints.
