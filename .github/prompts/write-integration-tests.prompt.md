# Write Integration Tests

You are a senior backend engineer writing integration tests for a Python/FastAPI project.

Target: write integration tests covering all real interactions between components, including the database, external services, and API endpoints. Consider existing unit tests and write integration tests that complement them by testing real wiring and interactions, consider existing integration tests and write new ones that cover gaps.

Rules:
- Output goes in `tests/integration/` mirroring the concern (deployment/, services/, api/)
- NEVER mock infrastructure— the entire point is testing real wiring
- Every test must be marked `@pytest.mark.integration`
- Assume a real running environment (DB up, migrations ran, env vars set)

Cover:
1. **Deployment health** (`integration/deployment/`) — live endpoint reachability,
   env vars and secrets present, DB connected, migrations applied cleanly
2. **Real DB constraints** — actually attempt to violate unique/nullable/FK constraints
   against a real DB, assert correct exceptions raised
3. **End-to-end flows** — full request → DB write → response cycle with no mocks
4. **External services** (`integration/services/`) — Use mocks by default, but test real Redis, Celery, third-party APIs when added; assert actual connectivity and behavior.
5. **Config correctness** — assert that production config values are valid and
   within expected ranges/formats

Naming: `test_<what>_<outcome>_when_<condition>`
Mark every test: `@pytest.mark.integration`
After writing, list any infra assumptions you made that may not hold in all environments.