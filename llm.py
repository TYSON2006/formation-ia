"""Appelle le modèle local Ollama et valide sa réponse JSON."""

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv


DOSSIER_PROJET = Path(__file__).resolve().parent
load_dotenv(DOSSIER_PROJET / ".env")

URL = os.getenv("LLM_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "160"))
OLLAMA_START_TIMEOUT = float(os.getenv("OLLAMA_START_TIMEOUT", "30"))

LOGGER = logging.getLogger(__name__)
_OLLAMA_START_LOCK = threading.Lock()


def _url_api_tags() -> str | None:
    """Renvoie /api/tags si LLM_URL désigne Ollama local sur le port standard."""
    morceaux = urlsplit(URL)
    if morceaux.scheme != "http":
        return None
    if morceaux.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    if morceaux.port != 11434:
        return None
    return f"{morceaux.scheme}://{morceaux.netloc}/api/tags"


def _trouver_ollama() -> str | None:
    """Trouve l'exécutable Ollama dans le PATH ou son emplacement Windows courant."""
    executable = shutil.which("ollama")
    if executable:
        return executable

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidat = Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
        if candidat.is_file():
            return str(candidat)
    return None


def _demarrer_ollama_local(url_tags: str) -> None:
    """Démarre Ollama s'il est installé et attend que son API réponde."""
    with _OLLAMA_START_LOCK:
        try:
            disponible = requests.get(url_tags, timeout=2)
            if disponible.ok:
                return
        except requests.RequestException:
            pass

        executable = _trouver_ollama()
        if not executable:
            raise RuntimeError(
                "Ollama ne répond pas et son exécutable est introuvable. "
                "Démarre l'application Ollama ou réinstalle-la."
            )

        LOGGER.info("Ollama ne répond pas ; démarrage automatique du service local.")
        try:
            options: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.Popen([executable, "serve"], **options)
        except OSError as erreur:
            raise RuntimeError(
                "Ollama ne répond pas et son démarrage automatique a échoué. "
                "Démarre l'application Ollama manuellement."
            ) from erreur

        limite = time.monotonic() + OLLAMA_START_TIMEOUT
        while time.monotonic() < limite:
            try:
                disponible = requests.get(url_tags, timeout=2)
                if disponible.ok:
                    LOGGER.info("Le service Ollama est prêt.")
                    return
            except requests.RequestException:
                pass
            time.sleep(1)

        raise RuntimeError(
            f"Ollama n'a pas répondu après son démarrage automatique "
            f"({OLLAMA_START_TIMEOUT:g} secondes). Vérifie qu'il est installé "
            "et réessaie."
        )


def appeler_llm(
    system: str,
    user: str,
    temperature: float = 0.2,
    num_predict: int | None = None,
) -> dict[str, Any]:
    """Envoie deux messages à Ollama et renvoie la réponse JSON parsée."""
    limite_generation = NUM_PREDICT if num_predict is None else max(1, min(num_predict, 3000))
    requete = {
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
            "num_predict": limite_generation,
        },
    }
    try:
        reponse = requests.post(
            URL,
            json=requete,
            timeout=TIMEOUT,
        )
    except requests.ConnectionError as erreur:
        url_tags = _url_api_tags()
        if not url_tags:
            raise RuntimeError(
                "Ollama ne répond pas à l'adresse configurée dans LLM_URL. "
                "Vérifie que le service est démarré."
            ) from erreur

        _demarrer_ollama_local(url_tags)
        try:
            reponse = requests.post(URL, json=requete, timeout=TIMEOUT)
        except requests.ConnectionError as nouvelle_erreur:
            raise RuntimeError(
                "Ollama a été démarré, mais ne répond toujours pas sur le port local 11434."
            ) from nouvelle_erreur

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

    try:
        resultat = json.loads(contenu)
    except json.JSONDecodeError as erreur:
        raise ValueError(
            "Ollama a renvoyé un JSON incomplet. Essaie de réduire le nombre de questions."
        ) from erreur
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
