# Aiogram Platform Baseline

Source family: current aiogram documentation at `https://docs.aiogram.dev/en/latest/`.

## Concepts to preserve in migration plans

- Aiogram is asynchronous and Python asyncio-based.
- `Dispatcher` handles incoming updates and is a subclass/root of `Router`.
- Handlers attach to `Router` or `Dispatcher`; larger bots should include feature routers into a composition root.
- Filters decide which updates reach handlers.
- Middlewares can enrich or guard handler data.
- FSM storage and scenes support stateful conversations; choose storage deliberately for dev/prod.
- Webhook setup can use aiohttp helpers such as `setup_application` or request handlers with a secret token; reverse proxies must preserve safe request identity headers.
- Polling remains useful for local/dev contours when production webhook safety is not needed.
- Dependency injection can pass services through dispatcher/startup context and handler type hints.
- `CallbackAnswerMiddleware` can acknowledge callback queries consistently, but callbacks that trigger sensitive changes still need explicit authorization checks.

## Migration implications

- Router boundaries should match product domains, not file convenience.
- Handler tests should simulate updates at the router/dispatcher boundary where practical.
- Webhook tests should validate secret-token handling and reverse-proxy assumptions without real tokens.
- Callback tests should assert acknowledgement and business outcome separately.
- FSM tests should cover state transitions, cancellation, stale state, and retries.
