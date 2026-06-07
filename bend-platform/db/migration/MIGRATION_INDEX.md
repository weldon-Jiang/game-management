# Database Migrations

All incremental migration scripts live in this directory. The canonical full schema is
[`../schema.sql`](../schema.sql) — update it whenever you add a migration.

## Naming convention

```
V{YYYYMMDD}_{seq}_{description}.sql
```

Examples:

- `V20260518_001_add_new_columns.sql`
- `V20260522_001_add_task_columns.sql`

Non-versioned maintenance scripts use the `utility_` prefix (e.g. `utility_reset_account_status.sql`).

## Apply order

Run migrations in lexicographic (filename) order on an existing database. For fresh installs, use
`schema.sql` only.

## Current migrations

- `V20260607_004_task_event_session_id.sql` — add session grouping to task events.
- `V20260607_005_game_account_billing_fields.sql` — add game account execution limits and billing metric fields.
- `V20260607_006_automation_billing_event.sql` — add idempotent Step4 billable event records.
- `V20260607_007_fix_billing_comment_charset.sql` — repair comments for environments that ran V005/V006 before utf8mb4 client charset was enforced.
- `V20260607_008_system_metrics_trend_index.sql` — add composite index for bounded monitoring trend queries.

## Legacy locations (removed)

Scripts previously under `bend-platform/db/V*.sql` or `docker/*.sql` have been consolidated here.
