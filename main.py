"""API FastAPI du chatbot documentaire."""

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf.errors import PdfReadError

from rag import DOSSIER_DOCUMENTS, indexer_pdf, repondre


app = FastAPI(title="Chatbot documentaire", version="0.1.0")
DOSSIER = Path(__file__).resolve().parent
TAILLE_MAX_PDF = 20 * 1024 * 1024
app.mount("/static", StaticFiles(directory=DOSSIER / "static"), name="static")


def empreinte_fichier(chemin: Path) -> str:
    """Calcule l'empreinte d'un fichier sans le charger entièrement en mémoire."""
    empreinte = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


@app.get("/", include_in_schema=False)
def accueil() -> FileResponse:
    """Affiche l'interface web du chatbot."""
    return FileResponse(DOSSIER / "static" / "index.html")


@app.post("/documents")
def ajouter_document(fichier: UploadFile = File(...)) -> dict:
    """Enregistre un PDF dans documents/ puis l'ajoute à l'index RAG."""
    nom_original = fichier.filename or ""
    nom = Path(nom_original.replace("\\", "/")).name
    if not nom.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Choisis un fichier au format PDF.")

    nom_sans_extension = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(nom).stem)
    nom_sans_extension = re.sub(r"\s+", " ", nom_sans_extension).strip(" .")[:150]
    if not nom_sans_extension:
        raise HTTPException(status_code=400, detail="Le nom du fichier PDF est invalide.")
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", nom_sans_extension, re.IGNORECASE):
        nom_sans_extension = f"_{nom_sans_extension}"

    DOSSIER_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    temporaire: Path | None = None
    total = 0
    premier_bloc = True
    empreinte = hashlib.sha256()
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=DOSSIER_DOCUMENTS, suffix=".uploading", delete=False
        ) as sortie:
            temporaire = Path(sortie.name)
            while True:
                bloc = fichier.file.read(min(64 * 1024, TAILLE_MAX_PDF + 1 - total))
                if not bloc:
                    break
                total += len(bloc)
                if total > TAILLE_MAX_PDF:
                    raise HTTPException(
                        status_code=413,
                        detail="Le PDF dépasse la limite de 20 Mo.",
                    )
                if premier_bloc and b"%PDF-" not in bloc[:1024]:
                    raise HTTPException(
                        status_code=415,
                        detail="Le fichier envoyé n'est pas un PDF valide.",
                    )
                premier_bloc = False
                empreinte.update(bloc)
                sortie.write(bloc)

        if premier_bloc:
            raise HTTPException(status_code=415, detail="Le fichier PDF est vide ou invalide.")

        empreinte_pdf = empreinte.hexdigest()
        for pdf_existant in DOSSIER_DOCUMENTS.rglob("*.pdf"):
            if pdf_existant.is_file() and empreinte_fichier(pdf_existant) == empreinte_pdf:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ce PDF a déjà été importé sous « {pdf_existant.name} ».",
                )

        # Un même nom peut désigner deux PDF différents. On conserve les deux en
        # donnant automatiquement un suffixe au nouveau fichier.
        destination = DOSSIER_DOCUMENTS / f"{nom_sans_extension}.pdf"
        numero = 2
        while destination.exists():
            destination = DOSSIER_DOCUMENTS / f"{nom_sans_extension} ({numero}).pdf"
            numero += 1

        # Sur Windows, os.rename refuse de remplacer un fichier déjà présent.
        os.rename(temporaire, destination)
        temporaire = None
    except HTTPException:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)
        raise
    except FileExistsError as erreur:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="Un fichier portant ce nom vient d'être ajouté. Réessaie l'importation.",
        ) from erreur
    except OSError as erreur:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Impossible d'enregistrer le PDF dans le dossier documents.",
        ) from erreur
    except Exception as erreur:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue pendant la réception du PDF.",
        ) from erreur

    try:
        return indexer_pdf(destination)
    except PdfReadError as erreur:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Ce PDF est illisible ou protégé par un mot de passe.",
        ) from erreur
    except Exception as erreur:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Le PDF a été reçu, mais son indexation a échoué. Vérifie le terminal de l'API.",
        ) from erreur


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
