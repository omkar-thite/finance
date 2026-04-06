# Finance Tracker API

This project is a FastAPI-based personal finance backend (with server-rendered pages) for managing users, authentication, transactions, and holdings in an investment-style portfolio flow. It provides JWT-based login, user profile and holdings endpoints, transaction CRUD operations, and static/template assets for the web UI, while persisting data through SQLAlchemy models and async database sessions.

## Current status

- JWT auth complete
- Core users/transactions/holdings APIs are implemented
- PostgreSQL integration in progress (current default DB is SQLite)
- Deployment target: April 2026

## Stack

- Python 3.12+
- FastAPI (including templating/static mounts)
- SQLAlchemy 2.x (async engine/session)
- Pydantic + pydantic-settings
- JWT (`pyjwt`) for token auth
- `pwdlib` (Argon2) for password hashing
- SQLite (`aiosqlite`) currently; PostgreSQL planned
- Pytest for tests

## Run locally

The steps below are based on the current repo state and should get the app running for local development.

1. Clone and enter the project folder.
2. Create and activate a Python 3.12+ virtual environment.
3. Install dependencies:

```bash
pip install -e .
```

4. Create a `.env` file in the project root with at least:

```env
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. Start the app:

```bash
uvicorn main:app --reload
```

6. Open:
- App: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

Notes:
- On startup, tables are auto-created via the FastAPI lifespan handler.
- The current DB URL is set in `database.py` and points to `sqlite+aiosqlite:///./portfolio.db`.
- If startup fails with settings errors, confirm `.env` exists and `SECRET_KEY` is set.
