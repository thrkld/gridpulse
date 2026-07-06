# Design Decisions

Format: what was decided, why, what was rejected, and current status. Status is honest: `implemented`, `partial`, or `planned`.

---

## Architecture
### ELT with a raw JSONB layer

Load untouched API responses directly into postgres as JSONB first; all transformation happens afterwards in dbt/SQL.

**Why:** Keeps ingestion lossless and fully repayable. Any transformation logic can be re-derived from raw history without re-ingestion.

**Rejected:** ETL (transforming in Python before load), which would permanently discard source fidelity.

**Status:** implemented.

### Append-only raw layer with idempotent ingestion

No overwriting raw tables: append-only, meaning re-running ingestion inserts new records rather than modifying existing one.

**Why:** Makes ingestion safe to retry and preserves full historical revisions (e.g forecast updates over time).

**Rejected:** UPSERT/ON CONFLICT updates in raw tables, which would destroy historical revisions and make ingestion order-dependent.

**Status** partial (raw layer implemented; mart-side dedup planned).

### UTC as the canonical settlement-time model

All sources are normalised to a UTC half-hour timeline. `start_time` (UTC instant) is the primary join key across all datasets. Settlement periods are defined on the UTC clock rather than source-specific local conventions

**Why:** Eliminates DST and source-local settlement inconsistencies. Ensures joins are temporally consistent.

**Rejected:** Keeping source-specific settlement periods and reconciling during joins, which introduces repeated DST edge-case handling.

**Status:** implemented across staging models.

### Cross-source joins occur in marts, not staging

No cross-source joining within staging tables. Staging serves as cleaning and standardising jsonb data pre-mart processing

**Why:** Keeps staging models independently testable and prevents cross-soruce logic from contaminating raw transformations.

**Rejected:** Performing joins in staging, which couples datasets and makes validation harder.

**Status:** staging implemented; marts planned.

### One raw table per source with endpoint discriminator

Each source has a single raw table. Multiple endpoints are distinguished using an 'endpoint' column rather than separate tables.

**Why:** Keeps raw schema minimal and avoids duplication of identical table structures.

**Rejected:** table-per-endpoint design, which introduces unnecessary schema duplication.

**Status:** implemented
