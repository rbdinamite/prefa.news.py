# Project Guidelines

## Architecture

- This is a Python web application built with FastAPI, SQLAlchemy, and Jinja2.
- `app/main.py` defines page routes and API endpoints. Keep endpoint behavior and response schemas in sync with `app/schemas.py`.
- `app/crud.py` contains database queries and persistence operations; `app/models.py` defines ORM models.
- News ingestion and scoring live under `app/ingestion/` and `app/scoring.py`. The server-rendered pages and browser assets are in `app/templates/` and `app/static/`.

## Code Style and Conventions

- Follow the existing Python formatting, naming, and type-annotation patterns.
- Use SQLAlchemy queries and the existing database-session dependencies; avoid embedding database access in route handlers when it belongs in CRUD code.
- Preserve existing API response shapes and page behavior unless a change explicitly requires otherwise.
- Keep changes focused, and add or update tests in `tests/` for behavior changes.

## Build and Test

- Install dependencies from `requirements.txt`; local setup and run instructions are in `README.md`.
- Run the test suite with `pytest`. `pytest.ini` enables coverage reporting and configures `tests/` as the test directory.
- For a focused change, run the relevant test file or test case before the full suite.
