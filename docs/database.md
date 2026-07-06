# Database

The metadata database stores runs, steps, profiles, dependency graph records, diagnoses, logs, and replay results.

## Core Tables

`pipelines`: pipeline identity and description.

`pipeline_runs`: one row per execution, including status, timing, git commit, input filename, snapshot path, error details, environment metadata, dependency versions, and pipeline parameters.

`pipeline_steps`: step-level status and timing for `load_input`, `profile_input`, `validate_schema`, `load_raw_orders`, `transform_orders`, and `calculate_revenue`.

`dataset_profiles`: dataset-level metrics: row count, column count, duplicate row count, file size.

`column_profiles`: per-column type, nulls, uniqueness, ranges, numeric stats, and common values.

`pipeline_nodes` and `pipeline_dependencies`: lineage graph for downstream impact.

`diagnosis_results`: ranked likely causes with category, severity, confidence, description, and supporting evidence.

`pipeline_logs`: structured run logs for the API and dashboard.

`replay_runs`: replay status, reproduced flag, linked replay run, and replay logs.

## Warehouse Tables

The sample pipeline creates or replaces:

- `raw_orders`
- `clean_orders`
- `daily_revenue`

## Migration Workflow

```bash
alembic upgrade head
```

The first migration creates the full initial schema from SQLAlchemy metadata.

