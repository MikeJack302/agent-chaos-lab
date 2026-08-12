# Security policy

Please report vulnerabilities through GitHub private vulnerability reporting. Include the configuration, command, and impact.

Agent Chaos Lab is a simulator, not a production recovery layer:

- It never calls real tools and cannot prove that an integration is idempotent, transactional, authorized, or correctly verified.
- Scenario probabilities and cost/latency values are trusted inputs. Calibrate them from controlled tests or sanitized telemetry.
- Do not put prompts, credentials, personal data, raw tool responses, or internal endpoints in public scenario files.
- A high simulated success rate is not evidence of application safety. Verify real postconditions and retain auditable receipts for consequential actions.
- The default independence assumptions do not model shared outages, time-correlated rate limits, regional failures, or adversarial behavior.
