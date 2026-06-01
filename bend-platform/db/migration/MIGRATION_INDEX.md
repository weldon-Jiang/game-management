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

## Legacy locations (removed)

Scripts previously under `bend-platform/db/V*.sql` or `docker/*.sql` have been consolidated here.
