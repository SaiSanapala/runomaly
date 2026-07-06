# Demo

This demo is designed to show the investigation loop, not every endpoint.

## Start

```bash
docker compose up --build
```

Open http://localhost:5173.

## Main Walkthrough

1. Click `Valid run`.
2. Select the successful row in the run table.
3. Point out the step timeline, snapshot path, and logs.
4. Click `Price type change`.
5. Select the failed row.
6. Open the investigation panel.
7. Show that `price` changed from numeric/decimal to string.
8. Show the downstream affected assets: `daily_revenue`, `sales_dashboard`, and `revenue_forecast`.
9. Click `Replay`.
10. Show that the replay reproduced the failure.
11. Click `Valid run` again to show the corrected path succeeds.

## CLI Version

Run a good file:

```bash
docker compose exec backend python -m investigator run \
  --pipeline daily_order_analytics \
  --input sample_data/valid/orders.csv
```

Run a broken file:

```bash
docker compose exec backend python -m investigator run \
  --pipeline daily_order_analytics \
  --input sample_data/failures/price_type_change.csv
```

Replay the failed run:

```bash
docker compose exec backend python -m investigator replay --run-id <failed_run_id>
```

## Other Scenarios To Show

The dashboard buttons cover the rest of the failure fixtures:

- missing `customer_id`
- duplicate `order_id`
- high null rate in `email`
- major row-count decrease
- empty input file

## Recording A Short GIF

A clean GIF only needs the main walkthrough:

1. Start from an empty or refreshed dashboard.
2. Run `Valid run`.
3. Run `Price type change`.
4. Select the failed run.
5. Show diagnosis, comparison, impact, and replay.

Keep it under a minute. The goal is to show that the tool shortens the "what changed?" investigation.

