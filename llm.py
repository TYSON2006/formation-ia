"""Appelle le modèle local Ollama et valide sa réponse JSON."""

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


DOSSIER_PROJET = Path(__file__).resolve().parent
load_dotenv(DOSSIER_PROJET / ".env")

URL = os.getenv("LLM_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))


def appeler_llm(system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
    """Envoie deux messages à Ollama et renvoie la réponse JSON parsée."""
    try:
        reponse = requests.post(
            URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",
                "keep_alive": KEEP_ALIVE,
                "options": {
                    "temperature": temperature,
                    "num_ctx": NUM_CTX,
                    "num_predict": NUM_PREDICT,
                },
            },
            timeout=TIMEOUT,
        )
    except requests.ConnectionError as erreur:
        raise RuntimeError(
            "Ollama ne répond pas sur le port local 11434. "
            "Vérifie que l'application Ollama est démarrée."
        ) from erreur

    if not reponse.ok:
        try:
            detail = reponse.json().get("error", reponse.text)
        except ValueError:
            detail = reponse.text
        raise requests.HTTPError(
            f"Erreur Ollama HTTP {reponse.status_code} : {str(detail)[:1000]}",
            response=reponse,
        )

    try:
        contenu = reponse.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as erreur:
        raise ValueError("Ollama n'a pas renvoyé le format de réponse attendu.") from erreur

    if not isinstance(contenu, str):
        raise ValueError("Ollama n'a pas renvoyé un contenu textuel JSON.")

    resultat = json.loads(contenu)
    if not isinstance(resultat, dict):
        raise ValueError("La réponse du LLM doit être un objet JSON.")
    return resultat


if __name__ == "__main__":
    resultat = appeler_llm(
        """Tu réponds en français uniquement avec un objet JSON valide.
        Utilise exactement ces clés :
        - reponse : une explication en deux phrases maximum ;
        - notions_cles : une liste de deux ou trois termes importants.
        N'ajoute aucun texte en dehors de l'objet JSON.""",
        "Dans un modèle de langage (LLM), qu'est-ce qu'un token ?",
    )
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
