def test_main_news_returns_ordered_blocks(client, seeded_data):
    resp = client.get("/api/news/main")
    assert resp.status_code == 200
    data = resp.json()
    assert "main" in data and "side" in data and "roller" in data and "more" in data
    # A notícia com maior "value" (200, do norte) deve vir primeiro
    assert data["main"][0]["title"].startswith("Notícia especial do norte")


def test_inactive_news_never_appears(client, seeded_data):
    resp = client.get("/api/news/main")
    titles = [n["title"] for block in resp.json().values() for n in block]
    assert "Notícia ainda não ativada" not in titles


def test_sector_filter_only_returns_matching_region(client, seeded_data):
    resp = client.get("/api/news/main", params={"sector": "SUL"})
    data = resp.json()
    all_items = data["main"] + data["side"] + data["roller"] + data["more"]
    assert all_items, "esperava ao menos uma notícia da região SUL"
    assert all(item["city"] == "Cidade Sul" for item in all_items)


def test_search_filter_matches_title_case_insensitively(client, seeded_data):
    resp = client.get("/api/news/main", params={"search": "PRÊMIO NACIONAL".lower()})
    data = resp.json()
    all_items = data["main"] + data["side"] + data["roller"] + data["more"]
    assert len(all_items) == 1
    assert "prêmio nacional" in all_items[0]["title"].lower()


def test_search_is_not_vulnerable_to_sql_injection(client, seeded_data):
    """
    O controller.php original concatenava o parâmetro `search` direto na
    query SQL. Aqui garantimos que um payload clássico de SQLi apenas
    retorna zero resultados (busca literal), sem quebrar a aplicação.
    """
    resp = client.get("/api/news/main", params={"search": '" OR 1=1 --'})
    assert resp.status_code == 200
    data = resp.json()
    assert data["main"] == [] and data["side"] == [] and data["roller"] == [] and data["more"] == []


def test_sectors_endpoint_groups_by_region(client, seeded_data):
    resp = client.get("/api/news/sectors")
    data = resp.json()
    assert len(data["south"]) == 6  # limitado a 6 por região
    assert len(data["north"]) == 1


def test_active_cities_endpoint(client, seeded_data):
    resp = client.get("/api/cities/active")
    assert resp.status_code == 200
    assert set(resp.json()) == {"Cidade Sul", "Cidade Norte"}


def test_save_click_registers_access(client, seeded_data, db_session):
    from app.models import News, Access

    news = db_session.query(News).first()
    resp = client.post("/api/access", json={"news_id": news.id, "type": "test"})
    assert resp.status_code == 200
    assert resp.json()["result"] is True
    assert db_session.query(Access).count() == 1


def test_newsletter_signup_and_duplicate_rejection(client):
    resp = client.post("/api/newsletter", json={"mail": "leitor@example.com"})
    assert resp.status_code == 200

    resp_dup = client.post("/api/newsletter", json={"mail": "leitor@example.com"})
    assert resp_dup.status_code == 409


def test_home_page_renders(client, seeded_data):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Prefa" in resp.text
    # Página não deve mais referenciar tags <img> de notícia
    assert "news_card.jpg" not in resp.text


def test_region_page_renders(client, seeded_data):
    resp = client.get("/regiao/sul")
    assert resp.status_code == 200
    assert "Cidade Sul" in resp.text


def test_region_page_invalid_slug_returns_404(client):
    resp = client.get("/regiao/inexistente")
    assert resp.status_code == 404
