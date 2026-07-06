# Design Notes

This file captures the main decisions behind Runomaly. It is intentionally more reflective than the API/database docs.

## Project Shape

I treated this as a focused developer tool, not a generic observability platform. The most important workflow is:

1. A pipeline run fails.
2. The system already has the input snapshot and profile from that run.
3. The failed run is compared to the latest successful baseline.
4. The user sees likely causes and downstream impact quickly.
5. The failure can be replayed from the captured input.

That is why the first version supports one pipeline deeply instead of many pipelines shallowly.

## Why Rule-Based Diagnosis

The first version uses explicit rules because the failure scenarios are concrete and inspectable. For example, if `price` used to profile as numeric and now profiles as string, and the transform fails during numeric conversion, that is a strong signal. A model would be harder to debug and unnecessary for this scope.

The downside is that rules need maintenance. In a larger version, I would keep the rule engine but make thresholds and rule packs configurable per pipeline.

## Why Snapshot Inputs

The input snapshot is the anchor for replay. Logs and metadata explain what happened, but the snapshot lets the user reproduce it. Runomaly stores snapshots under:

```text
snapshots/daily_order_analytics/<run_id>/
```

For a production version, I would move this to object storage and keep only references in Postgres.

## Why Compare To The Latest Successful Run

The question is not just "what failed?" It is "what changed since it last worked?" The latest successful run is a practical baseline because it gives the user a concrete before/after view without requiring long historical analysis.

This does have limits: if the last successful run was already abnormal, the comparison can be misleading. A future version could compare against rolling baselines or known-good promoted runs.

## What I Kept Out

I intentionally did not add Kafka, Kubernetes, authentication, many orchestrators, or automatic code repair. Those would make the project bigger but not necessarily better. The core value is the investigation loop, so the implementation stays centered on that.

