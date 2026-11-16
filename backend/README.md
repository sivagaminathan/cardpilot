# CardPilot Backend

FastAPI backend application for the CardPilot rewards optimizer and benefits tracker.

## Structure

- `app/api/`: Route handlers and dependencies
- `app/engine/`: Pure deterministic calculation engine
- `app/models/`: SQLAlchemy ORM models
- `app/schemas/`: Pydantic request/response schemas
- `app/services/`: Application services and orchestration
- `app/seeds/`: Idempotent seed data loader
- `app/telemetry/`: Logging and metrics instrumentation
