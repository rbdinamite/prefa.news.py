# Prefa.News — v2 (Python)

A complete rewrite of Prefa.News, migrating the back-end from **PHP** to **Python (FastAPI + SQLAlchemy)** and modernizing the front-end (typography, spacing, and colors).

> The original PHP version has been preserved, without changes, and can be
> viewed [here](https://github.com/rbdinamite/prefa.news)

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -m scripts.seed_demo_data  # optional: sample data

uvicorn app.main:app --reload
```

Access `http://localhost:8000`.

## AI chat

The home page includes a RAG assistant that retrieves cities, active news and
stored insights before asking Groq for an answer. Configure these variables in
`.env`:

```dotenv
GROQ_ENABLED=true
GROQ_API_KEY=your-groq-key
GROQ_MODEL=your-groq-model
GROQ_API_BASE_URL=https://api.groq.com/openai/v1
READONLY_DATABASE_URL=your-select-only-database-url
```

`READONLY_DATABASE_URL` is optional in local development and should point to a
database user with SELECT-only permissions in production. The assistant never
writes to the database.

## Running tests

```bash
pytest
```

The `pytest.ini` file already enables coverage reporting (`pytest-cov`). The tests
cover:

- **`tests/test_api.py`** — all REST endpoints (`/api/news/*`,
`/api/cities/*`, `/api/access`, `/api/newsletter`), including a specific test
ensuring the search function is not vulnerable to SQL injection, as well as
tests for the HTML pages.
- **`tests/test_scoring.py`** — news scoring rules (good/bad words,
uppercase titles, duplicate words, RAKE, news age, access count).
- **`tests/test_ingestion_parsers.py`** — RSS feed parsing and HTML/entity
cleaning.

## News ingestion

```bash
python -m app.ingestion.fetch_news
```

See `DEPLOY.md` to schedule this
routine in production (cron/systemd timer).
