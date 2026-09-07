# Guia de Deploy em Produção — Prefa.News v2

This document describe, step by step, how to put the project in production using **Docker**

Requirements:
- Linux server (Ubuntu 22.04/24.04 or Debian 12).
- A domain ponting for a server IP (ex.: `prefa.news`).
- SSH access and user with root privilegies.

---

### 1. Install Docker and Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# logout and login in SSH session to Docket activation
```

### 2. Send code to server

```bash
# on localhost, indice folder's project
rsync -avz --exclude .venv --exclude data ./ usuario@YOUR_SERVER:/opt/prefa-news/
```

Or, if you prefer, use a private Git repository and run `git clone` directly on the server.

### 3. Configure environment variables

```bash
cd /opt/prefa-news
cp .env.example .env
nano .env
```

At the very least, adjust in production:
- `APP_ENV=production`
- `DEBUG=false`
- `SECRET_KEY=` (generate a random value, ex.: `openssl rand -hex 32`)
- `DATABASE_URL=` (keep SQLite to start, or point to a managed Postgres instance — see the "Database" section below)
- `PUBLIC_BASE_URL=YOUR_URL`
- Email and Instagram credentials, if used

### 4. Load the containers

```bash
docker compose up -d --build
```

This spins up two services:
- `web`: FastAPI application served by Gunicorn+Uvicorn on port 8000
- `news-fetcher`: runs the news ingestion process every 30 minutes

Check the logs:

```bash
docker compose logs -f web
docker compose logs -f news-fetcher
```

### 5. Populate the database (initial load)

```bash
docker compose exec web python -m scripts.seed_demo_data # insert cities
docker compose exec web python -m app.ingestion.fetch_news # get news from cities
```

### 6. Configure Nginx as a reverse proxy + HTTPS

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/prefa-news`:

```nginx
server {
    listen 80;
    server_name YOUR_URL www.YOUR_URL;

    location /static/ {
        alias /opt/prefa-news/app/static/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/prefa-news /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d YOUR_URL -d www.YOUR_URL
```

All set: the site will be at `YOUR_URL` with automatic
certificate renewal (certbot already schedules the cron/systemd renewal timer).

### 7. Future updates

```bash
cd /opt/prefa-news
git pull
docker compose up -d --build
```

---

## Database

By default, the project uses **SQLite** (`./data/prefa_news.db`), which is sufficient for the readership volume of a regional news portal. To scale safely:

1. Back up the SQLite file daily (it is a single file,
simple to copy):
   ```bash
   0 3 * * * cp /opt/prefa-news/data/prefa_news.db /opt/backups/prefa_news_$(date +\%F).db
   ```
2. If traffic grows and you need multiple workers writing
simultaneously, migrate to Postgres simply by swapping `DATABASE_URL`
   no `.env` (ex.: `postgresql+psycopg://user:pass@host:5432/prefa_news`)
   and installing the driver (`pip install psycopg[binary]`). SQLAlchemy handles the rest — there is no need to modify `models.py`.
3. Schema migrations are managed with **Alembic**. After
updating the code, run the following before restarting the application:
  ```bash
  source .venv/bin/activate
  alembic upgrade head
  ```
  The startup still uses `Base.metadata.create_all` for local installations, but it does not replace migrations in production.

4. To generate insights linking news from different cities, configure `GROQ_ENABLED=true` and `GROQ_API_KEY` in the `.env` file. The integration uses Groq's chat-compatible API; free limits depend on the
current Groq account plan.

---