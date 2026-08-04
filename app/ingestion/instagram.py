"""
Publicação opcional no Instagram (Graph API), equivalente ao trecho final
de sys/commands/get_news.php que usava jstolpe/instagram-graph-api-php-sdk.

Este módulo é INTENCIONALMENTE simples e só é executado se
INSTAGRAM_ENABLED=true no .env, pois:
  1) Requer uma imagem pública para publicar (a nova versão do site não
     usa mais imagens de notícia, então essa é uma trilha opcional/
     independente que precisaria de uma fonte própria de imagem, ex.: um
     card gerado dinamicamente — não coberto por este pacote).
  2) Depende de credenciais de produção (Meta Business/Graph API) que não
     fazem sentido em ambiente de desenvolvimento/testes.

A lógica de duas chamadas HTTP (criar container de mídia + publicar) foi
mantida fiel ao fluxo original.
"""
from __future__ import annotations

import logging

import requests

from app.config import get_settings

logger = logging.getLogger("prefa_news.instagram")

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def publish_image(*, image_url: str, caption: str) -> dict:
    settings = get_settings()
    if not settings.INSTAGRAM_ENABLED:
        logger.info("Integração com Instagram desabilitada (INSTAGRAM_ENABLED=false). Ignorando.")
        return {"skipped": True}

    if not settings.INSTAGRAM_USER_ID or not settings.INSTAGRAM_ACCESS_TOKEN:
        logger.warning("Credenciais do Instagram não configuradas. Publicação abortada.")
        return {"skipped": True, "reason": "missing_credentials"}

    # 1) Cria o container de mídia
    container_resp = requests.post(
        f"{GRAPH_API_BASE}/{settings.INSTAGRAM_USER_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=30,
    )
    container_resp.raise_for_status()
    container = container_resp.json()
    container_id = container.get("id")
    if not container_id:
        logger.error("Falha ao criar container de mídia: %s", container)
        return {"error": True, "detail": container}

    # 2) Publica o container criado
    publish_resp = requests.post(
        f"{GRAPH_API_BASE}/{settings.INSTAGRAM_USER_ID}/media_publish",
        data={
            "creation_id": container_id,
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    result = publish_resp.json()
    logger.info("Publicado no Instagram: %s", result)
    return result
