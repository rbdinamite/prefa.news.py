"""
Popula o banco com cidades e notícias de exemplo, para você rodar o
projeto localmente sem depender dos feeds reais das prefeituras.

Uso:
    python -m scripts.seed_demo_data
"""
from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import City, News, Region, FeedType

CITIES = [
    ("Florianópolis", Region.GRANDE_FLORIPA),
    ("São José", Region.GRANDE_FLORIPA),
    ("Blumenau", Region.VALE),
    ("Joinville", Region.NORTE),
    ("Chapecó", Region.OESTE),
    ("Lages", Region.SERRANA),
    ("Criciúma", Region.SUL),
    ("Garopaba", Region.SUL),
]

SAMPLE_TITLES = [
    "Prefeitura entrega nova unidade de saúde no bairro",
    "Município recebe prêmio estadual de gestão pública",
    "Programa de reciclagem amplia coleta seletiva na cidade",
    "Nova ciclovia é inaugurada na região central",
    "Cidade lança edital de incentivo a pequenos negócios",
    "Escola municipal é destaque nacional em avaliação de ensino",
    "Prefeitura anuncia investimento em pavimentação de ruas",
    "Feira de agricultura familiar movimenta economia local",
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(City).count() > 0:
            print("Banco já possui dados. Nada a fazer.")
            return

        cities = []
        for name, regiao in CITIES:
            city = City(
                name=name,
                regiao=regiao,
                url_type=FeedType.PROPRIO,  # demo: não aponta para feed real
                url_path=None,
                active=True,
            )
            db.add(city)
            cities.append(city)
        db.flush()

        now = datetime.utcnow()
        for i, city in enumerate(cities):
            for j, title in enumerate(SAMPLE_TITLES):
                db.add(
                    News(
                        city_id=city.id,
                        title=f"{title} de {city.name}",
                        date=now - timedelta(hours=i + j),
                        news_url=f"https://exemplo.gov.br/noticia/{i}-{j}",
                        description=(
                            "Notícia de exemplo gerada para fins de demonstração "
                            "e testes locais do Prefa.News."
                        ),
                        active=True,
                        value=100 - (i + j),
                    )
                )
        db.commit()
        print(f"Seed concluído: {len(cities)} cidades e {len(cities) * len(SAMPLE_TITLES)} notícias.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
