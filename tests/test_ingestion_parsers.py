from app.ingestion.parsers import clean_malformed_entities, parse_feed, strip_html

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Prefeitura Exemplo</title>
    <item>
      <title>Prefeitura inaugura &#8220;Praça Nova&#8221;</title>
      <link>https://exemplo.gov.br/noticia/1</link>
      <pubDate>Mon, 01 Jun 2026 10:00:00 -0300</pubDate>
      <description><![CDATA[<p>Texto da <b>notícia</b> de exemplo com detalhes.</p>]]></description>
    </item>
    <item>
      <title>Segunda notícia do feed</title>
      <link>https://exemplo.gov.br/noticia/2</link>
      <pubDate>Mon, 01 Jun 2026 09:00:00 -0300</pubDate>
      <description>Resumo simples sem HTML.</description>
    </item>
  </channel>
</rss>
"""


def test_strip_html_removes_tags_and_unescapes_entities():
    assert strip_html("<p>Olá <b>mundo</b>&nbsp;!</p>") == "Olá mundo !"


def test_clean_malformed_entities_removes_numeric_and_named_entities():
    text = 'Prefeitura inaugura &#8220;Praça Nova&#8221; &nbsp;'
    cleaned = clean_malformed_entities(text)
    assert "&#8220;" not in cleaned
    assert "&nbsp;" not in cleaned


def test_parse_feed_extracts_normalized_items():
    items = parse_feed(SAMPLE_RSS, feed_type="P1", limit=5)
    assert len(items) == 2
    first = items[0]
    assert "Praça Nova" in first.title
    assert first.link == "https://exemplo.gov.br/noticia/1"
    assert "<" not in first.description  # HTML deve ter sido removido
    assert first.published_at.year == 2026


def test_parse_feed_respects_limit():
    items = parse_feed(SAMPLE_RSS, feed_type="P1", limit=1)
    assert len(items) == 1
