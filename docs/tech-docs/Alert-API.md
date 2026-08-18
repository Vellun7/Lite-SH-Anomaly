# Alert API

The alert module persists anomaly notifications raised by the detection service and exposes authenticated endpoints under `/api/v1/logs/alerts/`.

## Alert lifecycle

1. A detection result is saved as a `DetectionRecord`.
2. An anomalous result creates one pending `AlertLog` linked to that record.
3. An operator changes the alert to `confirmed`, `resolved`, or `ignored`.
4. The status update is recorded in the audit log.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/logs/alerts/` | List alerts with pagination and filters. |
| `PATCH` | `/api/v1/logs/alerts/{id}/` | Update one alert status and optional handling note. |
| `POST` | `/api/v1/logs/alerts/batch-update/` | Update a bounded batch of alerts. |
| `GET` | `/api/v1/logs/alerts/stats/` | Return dashboard alert statistics. |

## List filters

`level`, `status`, `device_id`, `start_time`, `end_time`, `page`, and `page_size` are accepted by the list endpoint. Time values use ISO-8601 format.

## Status update payload

```json
{
  "status": "resolved",
  "handling_note": "Blocked the source IP at the gateway."
}
```

`status` must be one of `confirmed`, `resolved`, or `ignored`. Moving an alert back to `pending` is rejected.

## Batch update payload

```json
{
  "alert_ids": [12, 13, 14],
  "status": "confirmed",
  "handling_note": "Reviewed during the daily security check."
}
```

The request is rejected when any requested alert ID does not exist, so callers do not receive partial updates.
