# Changelog

## Optional local hybrid adapter

- Opt-in in-process E5 encoder and reciprocal-rank fusion; lexical default unchanged.
- Pinned local safetensors, no remote code or inference API; model weights excluded.
- Up to three non-overlapping exact spans with bounded context, original source provenance and unchanged partial/unknown coverage.
- Stale index detection, scope checks and seventeen additional synthetic tests (45 total), including trusted manifest substitution rejection.
- Candidate retrieval is not answer verification: even the right source may have irrelevant top spans.
- Real-model synthetic demo is optional; default CI needs no ML dependencies or weights.

## Prototype v2

- Offline connector_evidence import preserving message IDs, role, source timestamps, HTTPS locator, offsets and evidence extent.
- Omitted text remains a coverage gap; unknown stays unknown.
- Connector-specific namespaces prevent collisions; empty imports retain source conversation provenance.
- Nine adapter tests; full suite contains 28 synthetic tests.

## Prototype v1

- Four synthetic export formats, SQLite FTS5 lexical search, exact source/context viewer, observed revisions and duplicate handling.
- Bounded ZIP import validation and atomicity; scope consistency checks.
- No live connectors, models or semantic backend.

## Public packaging

- Neutral README, privacy/security limitations and target specification separated from implemented capabilities.
- Only source, synthetic fixtures/tests and neutral design documents included. No license chosen.
