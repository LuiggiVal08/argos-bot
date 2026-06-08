# H4-A: Resilient Order Placement with CCXT

**Implementation**: domain VOs → Extend port → Use case → Infrastructure adapter → API → Tests

## Commit log

| Commit | Message |
|---|---|
| 1/7 | `feat(analytics-engine): h4-a-001 domain VOs OrderSide, OrderType, CompositeOrder, OrderResult` |
| 2/7 | `feat(analytics-engine): h4-a-002 extend ExchangeOrderClient port` |
| 3/7 | `feat(analytics-engine): h4-a-003 PlaceOrderUseCase with retry + emergency fallback` |
| 4/7 | `feat(analytics-engine): h4-a-004 extend CcxtOrderClient` |
| 5/7 | `feat(analytics-engine): h4-a-005 POST /order/place API` |
| 6/7 | `test(analytics-engine): h4-a-006 unit + integration tests` |
| 7/7 | `docs(tasks): h4-a-order-retry done` |

## Changes

### New files (5)
- `domain/value_objects/order.py` — `OrderSide`, `OrderType`, `OrderStatus`, `CompositeOrder`, `OrderResult` VOs
- `application/use_cases/place_order.py` — `PlaceOrderUseCase` with `SlPlacementError` catch → emergency market
- `api/order.py` — `POST /order/place` endpoint
- `tests/unit/test_place_order_usecase.py` — 6 tests
- `tests/integration/test_order_place_endpoint.py` — 5 tests

### Modified files (6)
- `application/ports/exchange_order_client.py` — added `SlPlacementError` (with `entry_order` attr), `place_composite_order`, `place_emergency_market`
- `infrastructure/exchange/ccxt_order_client.py` — implemented `place_composite_order` (entry + SL retry + TP) and `place_emergency_market`
- `composition.py` — wired `PlaceOrderUseCase` into `Composition`
- `api/__init__.py` — registered `order_router`
- `main.py` — included `order_router`
- `application/use_cases/__init__.py` — re-exported

## Key design decisions

1. **`SlPlacementError` carries `entry_order`**: since the entry order was already placed when the SL fails, the exception carries the entry `OrderResult` so the use case can return it in the response.
2. **Emergency side = opposite of entry**: if entry was BUY, emergency is SELL (and vice versa).
3. **TP failure is non-critical**: logged and ignored. Only SL failure triggers emergency.
4. **SL retry**: exponential backoff with jitter (base 100ms, 2^attempt * base + random 0-20ms), max 3 retries.
5. **Entry failure propagates immediately**: no retry on entry order (the use case raises `PlaceOrderError`).

## Test coverage

- **Unit**: happy path, minimal order, SL→emergency, opposite side, both fail, entry fail
- **Integration**: happy path, no SL/TP, SL→emergency response, entry error 422, both fail 422
