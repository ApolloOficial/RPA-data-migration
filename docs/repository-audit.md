# Repository quality audit

## Scope and expected load

At the start of this work the repository contained only a one-line README and a license. It had no executable migration, CI, tests, dependency declaration, PR template or operational instructions. The expected load is one scheduled or manual process reading a small registration set from PostgreSQL and writing one batch at a time. The supplied database contract defines four registration entities for this RPA.

## Findings and action

1. **Must fix — no migration existed.** There was no way to move or reshape legacy data. Added a snapshot reader, field mapping, staging batch insertion, and invocation of the destination's existing synchronization procedure.
2. **Must fix — source IDs collide with destination demo data.** Both supplied datasets use administrator IDs beginning at 1. Running a source-ID upsert against the demo destination could overwrite a different person. Added a preflight comparison of source IDs and stable identities, and a schema-only derivation for an isolated destination.
3. **Must fix — failures and retries had no operational path.** A partial load needs visible counts and row errors. The robot reports batch status, exits nonzero when any row fails, and documents the destination error table and retry behavior.
4. **Must fix — database ownership was implicit.** `DatabaseConnections` now owns both connections, sets the legacy transaction read only, and closes the destination first so exceptions roll it back.
5. **Should fix — no reproducible review gate.** Added focused mapping and connection tests, a Python syntax check in CI, a PR template, and branch/commit guidance.

## Remaining contract gaps

The destination RPA procedure does not accept contracts, equipment or maintenance rows. The target schema has no contract table and requires operational roles and physical equipment fields absent from the legacy source. The robot reports counts for those tables and does not invent values. Expanding this scope requires an approved mapping and real operators/technicians in the destination.

An isolated PostgreSQL 16 test used the immutable first-year SQL and a schema-only derivation of the immutable second-year SQL. The first run processed 9/9 registration rows; a repeat processed 9/9 with unchanged entity counts (1 administrator, 2 companies, 3 units, 1 segment, 3 addresses, 3 managers). A deliberately invalid hash in the disposable source produced `COMPLETED_WITH_ERRORS` with 8 processed and 1 failed; its error payload omitted the hash. A deliberately conflicting administrator identity in the disposable target was rejected by `--check` before writing. CI runs pure tests; it does not provision the reference databases.

## Lean review

One runtime dependency (`psycopg`) is needed for PostgreSQL. The rest uses the Python standard library and the destination's existing ETL procedure. No ORM, scheduler, container image, duplicate target schema, or copied reference SQL was added.
