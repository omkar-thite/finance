# Finance App

FastAPI application for personal finance tracking with both JSON APIs and server-rendered pages.

Current implementation includes:
- JWT-based authentication
- User profile management
- Transactions and holdings flows
- Profile picture upload/delete
- Password reset endpoints with email delivery
- Frontend pages rendered with Jinja2 templates

## Tech stack

- Python 3.12+
- FastAPI
- SQLAlchemy async ORM
- Pydantic and pydantic-settings
- SQLite (aiosqlite)
- JWT (pyjwt)
- Password hashing (pwdlib[argon2])
- SMTP email sending (aiosmtplib)
- Pillow for profile image processing
- Pytest for unit tests

## Project structure

- API and app entrypoint: main.py
- User API routes: routes/users.py
- Transaction API routes: routes/transactions.py
- Frontend page routes: routes/front_view.py
- Models: models.py
- Schemas: schema.py
- Templates: templates/
- Static files: static/
- Uploaded media: media/profile_pics/

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

   pip install -e .

3. Create .env in project root.

Required environment variables:
- SECRET_KEY

Optional mail environment variables:
- MAIL_SERVER
- MAIL_PORT
- MAIL_USERNAME
- MAIL_PASSWORD
- MAIL_FROM
- MAIL_USE_TLS

If mail settings are not configured, the password reset endpoints and the forgot/reset password pages are disabled. In that case, the app will still run, but password reset functionality will return a 503 response and related links/forms will be hidden in the UI.

4. Start the app:

   uvicorn main:app --reload

5. Open:
- App home: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

Notes:
- Database tables are auto-created at startup.
- The local SQLite database file is portfolio.db.
- `dummy_data.py` is available for local development and can seed example users, instruments, and transactions. It clears existing local app data before seeding, so use it only in a development environment.

## API overview

Base API prefixes:
- /api/users
- /api/transactions

Users/auth endpoints (high level):
- POST /api/users/ (create user)
- POST /api/users/token (login, OAuth2 password form)
- GET /api/users/me
- PATCH /api/users/me/password
- POST /api/users/forgot-password
- POST /api/users/reset-password
  - Note: if mail settings are not configured, these routes return 503 and password reset is unavailable.
- PATCH /api/users/{user_id}/picture
- DELETE /api/users/{user_id}/picture
- GET /api/users/{user_id}/transactions
- GET /api/users/{user_id}/holdings

Transactions endpoints (high level):
- GET /api/transactions/
- GET /api/transactions/{id}
- POST /api/transactions/
- PATCH /api/transactions/
- DELETE /api/transactions/

## Frontend routes

Server-rendered pages currently include:
- /
- /login
- /register
- /account
- /users/{user_id}
- /users/{user_id}/transactions
- /users/{user_id}/assets
- /transactions/
- /forgot-password
- /reset-password

## Testing

Run all tests:

pytest

Run unit tests only:

pytest -m unit

Test configuration is in pyproject.toml and tests/conftest.py.
