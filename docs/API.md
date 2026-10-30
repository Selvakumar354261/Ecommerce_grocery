# API guide
# API guide

Interactive schemas are generated at `/api/docs`. Every path below is prefixed with `/api/v1`.

Use the same-origin cookie session. Login/register returns `{user, csrf}`. Retain the HttpOnly cookie automatically and send `X-CSRF-Token` on authenticated writes. Do not store a password or a session token in localStorage. Cart data and a local held bill are the only persistent browser business state.

For writes that create financial or stock effects, send a unique `Idempotency-Key` and retain it for retries of the same payload. Same key with changed input is a conflict. 401 means sign in; 403 means no permission or invalid session/origin; 409 means business-state/stock conflict; 422 means input validation; 503 means retry the same operation safely.

| Area | Routes |
|---|---|
| Session | POST /auth/register, POST /auth/login, GET /auth/session, GET /auth/me, POST /auth/logout |
| Browse | GET /catalogue, GET /branches |
| Checkout | POST /checkout/branches, POST /orders |
| Orders | GET /orders, GET /orders/{id}, POST /orders/{id}/transition, POST /orders/{id}/payment |
| Stock | GET /inventory?branch_id=, GET /movements?branch_id=, POST /inventory/change |
| POS | POST /sales, GET /sales?branch_id=, POST /sales/{id}/returns |
| Shifts | GET /shifts?branch_id=, POST /shifts/open, POST /shifts/{id}/close |
| Counts | GET /stock-counts?branch_id=, POST /stock-counts, POST /stock-counts/{id}/approve or /reject |
| Transfers | GET /transfers, POST /transfers, POST /transfers/{id}/receive |
| Purchasing | GET/POST /suppliers, GET/POST /purchases, POST /purchases/{id}/receive |
| Administration | POST /admin/products, POST /admin/products/{id}/archive, PATCH /admin/variants/{id}/price, POST /admin/branches, PUT /admin/branches/{id}, GET/POST /admin/users, POST /admin/users/{id}/toggle |
| Reporting | GET /dashboard?branch_id=, GET /reports/sales.csv?branch_id=, GET /admin/audit |
| Readiness | GET /health |

Every catalogue product has an immutable numeric database ID and a formatted public ID such as `PRD-000001`. Every selling variant also has its own unique SKU/barcode.

## Checkout branch request

```json
{
  "method": "delivery",
  "latitude": 11.3410,
  "longitude": 77.7172,
  "items": [{"variant_id": 1, "quantity": "2"}]
}
```

Response options contain `eligible`, `recommended`, `distance_km`, `covered`, `missing`, `hours`, and `delivery_fee`. Recommendation does not reserve stock. The final order request also contains `branch_id`, `address`, `phone`, and `expected_subtotal`. Checkout locks/revalidates availability before reserving.

## POS request

```json
{
  "branch_id": 1,
  "payment_method": "cash",
  "amount_tendered": "200.00",
  "expected_subtotal": "156.00",
  "items": [{"variant_id": 1, "quantity": "2"}]
}
```

An open shift is required for the current cashier and branch. The backend calculates price from the catalogue and rejects conflicting expected totals. Receipt lines preserve their price/unit/name snapshots.

## Inventory change request

```json
{
  "branch_id": 1,
  "variant_id": 1,
  "quantity": "10",
  "kind": "receive",
  "reason": "Supplier delivery reference ABC123"
}
```

Kinds are `receive`, `damage`, `adjust_up`, `adjust_down`. Adjustment access is manager/admin only; other stock staff can receive and quarantine. Stock-count approval is the separate two-person variance flow.

## Bounded history

The UI returns the latest 200 orders/sales/movements/audit events and 100 shifts/counts per request. Catalogue and branches return the active master lists. Large installations should add server pagination and date filters before historical records exceed these operational views. CSV exports currently include all matched records; schedule large exports outside busy trading hours.
