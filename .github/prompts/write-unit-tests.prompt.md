# Copilot Instructions — Finance Tracker API (Unit Tests)

Target: For the specific file or feature currently in context, write comprehensive unit tests covering its functions, methods, routes, and schemas. Assert exact expected behavior. Complement existing tests by covering gaps and edge cases.
Consider following  rules strictly to ensure high-quality, maintainable tests that provide strong regression protection and documentation of expected behavior. 

## Project Stack
- Python, FastAPI, SQLAlchemy (async), PostgreSQL, Pydantic v2, pytest
- Apply all rules below to any new libraries introduced.

## Test Writing Rules

Act as a senior backend engineer. When writing or updating tests, follow these rules strictly:

1. Scope and Isolation
- Mock ALL external boundaries (Database, HTTP calls, file I/O, env vars). Test the logic, not the infrastructure.
- Output goes in `tests/unit_tests/` mirroring the source path exactly.
- Mark every test with `@pytest.mark.unit`.
- Use pytest fixtures for all setup/teardown; never repeat setup inline.

2. API Endpoint Tests
For every FastAPI route, test all expected behaviors:
- Happy path → assert exact expected status code (e.g., 200, 201) and JSON response shape.
- Missing/Invalid input → assert 422 (Unprocessable Entity).
- Unauthorized / unauthenticated → assert 401 or 403.
- Resource not found → assert 404.
- Business logic conflicts (e.g., duplicates) → assert 409.

3. Schema & Model Tests
Focus on custom logic, do not test framework internals:
- Test custom Pydantic `@field_validator` or `@model_validator` logic (both valid and invalid inputs).
- Test computed properties or custom methods on SQLAlchemy models.
- Assert that default factories generate the expected default values.

4. Regression Anchors & Negative Paths
- For every business logic function, pin at least one known input to an exact expected output.
- For every happy-path test, write a corresponding negative test (boundary values, empty payloads, missing auth).
- Assert the *exact* exception raised using `pytest.raises()`, not just generic failures.

## Naming Convention
Strictly use: `test_<what_is_being_tested>_<expected_outcome>_when_<condition>`
Example: `test_create_transaction_returns_422_when_amount_is_missing`

## File Structure
Each test file must start with a descriptive module docstring:
```python
"""
Guards: app/routes/transactions.py
Contract: creates, reads, updates, deletes transactions.
"""