# Guia de Deploy em Produção — Prefa.News v2

Este documento descreve, passo a passo, como colocar a versão Python do
Prefa.News em produção. Há dois caminhos: **Docker (recomendado)** e
**instalação manual em VPS (systemd + Nginx)**. Escolha um dos dois.

Pré-requisitos gerais:
- Um servidor Linux (Ubuntu 22.04/24.04 ou Debian 12 recomendados).
- Um domínio apontando para o IP do servidor (ex.: `prefa.news`).
- Acesso SSH com um usuário com permissão de sudo.

---

## Caminho A — Deploy com Docker (recomendado)

### 1. Instalar Docker e Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# saia e entre novamente na sessão SSH para o grupo docker fazer efeito
```

### 2. Enviar o código para o servidor

```bash
# na sua máquina local, dentro da pasta do projeto
rsync -avz --exclude .venv --exclude data ./ usuario@SEU_SERVIDOR:/opt/prefa-news/
```

Ou, se preferir, use um repositório Git privado e faça `git clone` direto
no servidor.

### 3. Configurar variáveis de ambiente

```bash
cd /opt/prefa-news
cp .env.example .env
nano .env
```

No mínimo, ajuste em produção:
- `APP_ENV=production`
- `DEBUG=false`
- `SECRET_KEY=` (gere um valor aleatório, ex.: `openssl rand -hex 32`)
- `DATABASE_URL=` (mantenha SQLite para começar, ou aponte para Postgres
  gerenciado — ver seção "Banco de dados" abaixo)
- `PUBLIC_BASE_URL=https://prefa.news`
- Credenciais de e-mail e Instagram, se forem usadas

### 4. Subir os containers

```bash
docker compose up -d --build
```

Isso sobe dois serviços:
- `web`: aplicação FastAPI servida por Gunicorn+Uvicorn na porta 8000
- `news-fetcher`: roda a ingestão de notícias a cada 30 minutos

Verifique os logs:

```bash
docker compose logs -f web
docker compose logs -f news-fetcher
```

### 5. Popular o banco (primeira vez)

```bash
docker compose exec web python -m scripts.seed_demo_data   # opcional, dados de exemplo
docker compose exec web python -m app.ingestion.fetch_news # ingestão real, a partir das cidades cadastradas
```

> **Importante**: diferente da v1, o cadastro de cidades/feeds
> (`city.url_path`, `city.url_type`, `city.regiao`) agora deve ser feito
> via uma migração/seed própria ou diretamente no banco (não há mais
> painel administrativo neste pacote). Se você tinha o `bd.db` da versão
> PHP, veja a seção "Migrando dados da v1" mais abaixo.

### 6. Configurar Nginx como proxy reverso + HTTPS

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Crie `/etc/nginx/sites-available/prefa-news`:

```nginx
server {
    listen 80;
    server_name prefa.news www.prefa.news;

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
sudo certbot --nginx -d prefa.news -d www.prefa.news
```

Pronto: o site estará em `https://prefa.news` com renovação automática
de certificado (o certbot já agenda o cron/systemd timer de renovação).

### 7. Atualizações futuras

```bash
cd /opt/prefa-news
git pull   # ou rsync novamente
docker compose up -d --build
```

---

## Caminho B — Instalação manual (systemd + Nginx, sem Docker)

### 1. Instalar dependências do sistema

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv nginx certbot python3-certbot-nginx
```

### 2. Criar usuário de serviço e enviar o código

```bash
sudo useradd -r -m -s /bin/bash prefanews
sudo mkdir -p /opt/prefa-news
sudo chown prefanews:prefanews /opt/prefa-news
# copie o código para /opt/prefa-news (rsync/git clone), como usuário prefanews
```

### 3. Ambiente virtual e dependências

```bash
sudo -u prefanews bash -c "
  cd /opt/prefa-news &&
  python3.12 -m venv .venv &&
  source .venv/bin/activate &&
  pip install -r requirements.txt
"
```

### 4. Configurar `.env`

```bash
sudo -u prefanews cp /opt/prefa-news/.env.example /opt/prefa-news/.env
sudo -u prefanews nano /opt/prefa-news/.env
```

### 5. Criar o serviço systemd da aplicação web

Crie `/etc/systemd/system/prefa-news.service`:

```ini
[Unit]
Description=Prefa.News (FastAPI/Gunicorn)
After=network.target

[Service]
Type=simple
User=prefanews
Group=prefanews
WorkingDirectory=/opt/prefa-news
EnvironmentFile=/opt/prefa-news/.env
ExecStart=/opt/prefa-news/.venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 60
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prefa-news
sudo systemctl status prefa-news
```

### 6. Agendar a ingestão de notícias com systemd timer

Crie `/etc/systemd/system/prefa-news-fetch.service`:

```ini
[Unit]
Description=Prefa.News - ingestão de notícias

[Service]
Type=oneshot
User=prefanews
Group=prefanews
WorkingDirectory=/opt/prefa-news
EnvironmentFile=/opt/prefa-news/.env
ExecStart=/opt/prefa-news/.venv/bin/python -m app.ingestion.fetch_news
```

Crie `/etc/systemd/system/prefa-news-fetch.timer`:

```ini
[Unit]
Description=Executa a ingestão de notícias do Prefa.News a cada 30 minutos

[Timer]
OnBootSec=2min
OnUnitActiveSec=30min
Unit=prefa-news-fetch.service

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prefa-news-fetch.timer
systemctl list-timers | grep prefa-news
```

### 7. Nginx + HTTPS

Igual ao Caminho A, passo 6 (ajuste o `alias` do `/static/` para
`/opt/prefa-news/app/static/`).

---

## Banco de dados

Por padrão o projeto usa **SQLite** (`./data/prefa_news.db`), suficiente
para o volume de leitura de um portal de notícias regional. Para crescer
com segurança:

1. Faça backup diário do arquivo SQLite (ele é um único arquivo,
   simples de copiar):
   ```bash
   0 3 * * * cp /opt/prefa-news/data/prefa_news.db /opt/backups/prefa_news_$(date +\%F).db
   ```
2. Se o tráfego crescer e você precisar de múltiplos workers escrevendo
   simultaneamente, migre para Postgres apenas trocando `DATABASE_URL`
   no `.env` (ex.: `postgresql+psycopg://usuario:senha@host:5432/prefa_news`)
   e instalando o driver (`pip install psycopg[binary]`). O SQLAlchemy
   cuida do resto — não é necessário alterar `models.py`.
3. Para gerenciar migrações de schema de forma segura em produção
   (adicionar colunas sem perder dados), recomenda-se introduzir o
   **Alembic** (`pip install alembic && alembic init migrations`). O
   projeto cria as tabelas automaticamente via `Base.metadata.create_all`
   por simplicidade, mas o Alembic é o próximo passo natural assim que
   o schema começar a evoluir com frequência.

---

## Migrando dados da v1 (PHP)

Se você tem o `bd.db` (SQLite) da versão PHP e quer aproveitar as
cidades e notícias já cadastradas:

1. Copie o `bd.db` antigo para o servidor novo.
2. Como o schema é equivalente (mesmas tabelas/colunas principais), é
   possível fazer um `ATTACH DATABASE` no SQLite e copiar linha a linha:

   ```sql
   -- rode isso com sqlite3 apontando para o banco novo
   ATTACH DATABASE '/caminho/para/bd_v1.db' AS old;

   INSERT INTO city (id, name, regiao, url_type, url_path, instagram, active, lastcheck_date, lastnews_date)
   SELECT id, name, regiao, url_type, url_path, instagram, active, lastcheck_date, lastnews_date FROM old.city;

   INSERT INTO news (id, city_id, title, date, news_url, img_url, description, active, value, pub_instagram)
   SELECT id, city_id, title, date, news_url, img_url, description, active, value, pub_instagram FROM old.news;
   ```

3. A coluna `img_url` continua existindo no schema novo (não a
   removemos do banco, apenas paramos de exibi-la no front-end), então a
   migração acima funciona sem alterações.

---

## Checklist final de produção

- [ ] `.env` com `DEBUG=false` e `SECRET_KEY` forte e único
- [ ] HTTPS ativo (certbot) e renovação automática confirmada
- [ ] `docker compose ps` (ou `systemctl status prefa-news`) mostrando
      os serviços saudáveis
- [ ] Timer/cron de ingestão rodando e gerando logs
- [ ] Backup diário do banco configurado
- [ ] `pytest` rodando verde no pipeline de CI antes de cada deploy
- [ ] Monitoramento básico (ex.: Uptime Kuma, Healthchecks.io ou similar)
      apontando para `https://prefa.news/`
