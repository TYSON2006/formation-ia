"""Recherche web facultative avec l'API Tavily pour fournir des liens vérifiés."""

import logging
import os
from urllib.parse import urlparse

import requests

LOGGER = logging.getLogger(__name__)
URL_RECHERCHE = "https://api.tavily.com/search"


def recherche_web_disponible() -> bool:
    """Indique si la clé Tavily est configurée côté serveur."""
    return bool(os.getenv("TAVILY_API_KEY", "").strip())


def rechercher(question: str, nombre: int = 3) -> list[dict[str, str]]:
    """Retourne quelques extraits web accompagnés de leurs URL réelles."""
    cle = os.getenv("TAVILY_API_KEY", "").strip()
    if not cle:
        return []

    try:
        reponse = requests.post(
            URL_RECHERCHE,
            headers={"Authorization": f"Bearer {cle}"},
            json={
                "query": question[:500],
                "topic": "general",
                "search_depth": "basic",
                "max_results": max(1, min(nombre, 5)),
                "include_raw_content": False,
            },
            timeout=(4, 12),
        )
        reponse.raise_for_status()
        donnees = reponse.json()
    except (requests.RequestException, ValueError) as erreur:
        LOGGER.warning("La recherche web Tavily a échoué : %s", erreur)
        return []

    if not isinstance(donnees, dict):
        LOGGER.warning("Tavily a renvoyé une réponse au format inattendu.")
        return []

    resultats: list[dict[str, str]] = []
    for element in donnees.get("results", []):
        if not isinstance(element, dict):
            continue
        url = element.get("url")
        titre = element.get("title")
        contenu = element.get("content")
        if not all(isinstance(valeur, str) and valeur.strip() for valeur in (url, titre, contenu)):
            continue
        url_parsee = urlparse(url)
        if url_parsee.scheme not in {"https", "http"} or not url_parsee.netloc:
            continue
        resultats.append(
            {
                "title": titre.strip()[:180],
                "url": url.strip()[:1000],
                "content": contenu.strip()[:900],
            }
        )
        if len(resultats) >= nombre:
            break
    return resultats
