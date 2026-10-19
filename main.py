"""API FastAPI du chatbot documentaire."""

from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag import repondre


app = FastAPI(title="Chatbot documentaire", version="0.1.0")
DOSSIER = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=DOSSIER / "static"), name="static")


@app.get("/", include_in_schema=False)
def accueil() -> FileResponse:
    """Affiche l'interface web du chatbot."""
    return FileResponse(DOSSIER / "static" / "index.html")


class MessageConversation(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1500)


class Question(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Question à poser aux documents indexés",
    )
    historique: list[MessageConversation] = Field(default_factory=list, max_length=6)


class Source(BaseModel):
    source: str
    page: int


class Reponse(BaseModel):
    reponse: str
    sources: list[Source]


@app.post("/ask", response_model=Reponse)
def ask(body: Question) -> dict:
    """Répond à une question avec des sources issues des PDF indexés."""
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="La question ne peut pas être vide.")
    try:
        historique = [
            {"role": message.role, "content": message.content}
            for message in body.historique
        ]
        return repondre(body.question, historique=historique)
    except requests.Timeout as erreur:
        raise HTTPException(
            status_code=504,
            detail="Ollama met trop de temps à répondre. Le premier chargement peut être plus long.",
        ) from erreur
    except requests.HTTPError as erreur:
        code = erreur.response.status_code if erreur.response is not None else 502
        if code == 404:
            detail = "Modèle Ollama introuvable : vérifie LLM_MODEL et les modèles installés."
        else:
            detail = f"Ollama a renvoyé une erreur HTTP {code}."
        raise HTTPException(status_code=502, detail=detail) from erreur
    except requests.RequestException as erreur:
        raise HTTPException(
            status_code=502,
            detail="Impossible de joindre Ollama sur http://127.0.0.1:11434.",
        ) from erreur
    except ImportError as erreur:
        raise HTTPException(
            status_code=503,
            detail=(
                "Une dépendance native est manquante. Sous Windows, installe le "
                "Microsoft Visual C++ Redistributable x64, puis redémarre l'API."
            ),
        ) from erreur
    except FileNotFoundError as erreur:
        raise HTTPException(status_code=503, detail=str(erreur)) from erreur
    except ValueError as erreur:
        raise HTTPException(status_code=502, detail=str(erreur)) from erreur
    except RuntimeError as erreur:
        raise HTTPException(status_code=503, detail=str(erreur)) from erreur
