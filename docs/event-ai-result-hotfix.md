# Event AI result/accounting hotfix (2026-09-15)

## Evidence

At baseline d1aa1a2, `analyzeEvent` declares `reserveMaxCostUsd` but uses an undeclared `reservedMaxCostUsd` shorthand in BOTH usage writes. A complete valid mock response reproduces `ReferenceError: reservedMaxCostUsd is not defined`, the reported UI message, settled daily/monthly costs, a saved success analysis, and no usage row. This proves a code defect that explains the symptom; the specific production request is not confirmed without its Cloud Logging/Firestore records. Undefined config/SDK fields can independently fail Firestore writes; those are covered defensively.

## Behavior

- Parse all text blocks; accept a complete JSON object or a single JSON fence; validate every required field, type and enum. Reject truncation, refusal, extra prose, unknown fields and incomplete answers.
- Sanitize plain API/config data recursively before Firestore writes. Add Firestore timestamp sentinels afterward. Do not invent investment facts.
- Reserve budget and claim the analysis fingerprint atomically. Keep existing successful cache entries and fingerprint versions unchanged. Concurrent calls, failures and uncertain provider outcomes cannot automatically make another paid call for that fingerprint. Disable SDK automatic retries.
- Commit the usage ledger marker and daily/monthly reconciliation together. Retry only that idempotent transaction, never the provider call. Unknown usage retains the maximum reserve as unreconciled. Repeated commits do not add cost again.
- Label provider, parse and persistence failures separately. Report cost status rather than falsely claiming a usage record exists. Log identifiers and fixed error codes, never provider response text or secrets.
- Save validated output in the usage ledger before publishing the analysis, so an operator can recover a failed analysis write without calling the provider again.

## Operations / limits

A failed/processing fingerprint remains blocked for manual review; there is intentionally no automatic paid retry or lock expiry. For a persisted usage output, an operator may restore the analysis from that record without changing cost totals. For historical success analyses missing usage rows, reconstruct a ledger only after inspecting the saved analysis and existing totals; do NOT add the existing cost again. Historical failures with no saved response cannot be recovered from this patch alone. No historical production accounting is changed by deployment.

Tests use a fake Anthropic constructor and in-memory Firestore transactions, including rollback and lost acknowledgements. They execute the actual callable handler source without importing the provider SDK. Firebase imports and deployment do not invoke `messages.create`. This does not prove a new live paid response succeeds; that test is deliberately excluded.
