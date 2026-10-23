"""API FastAPI du chatbot documentaire."""

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Literal

import requests
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf.errors import PdfReadError

from espaces import (
    creer_discussion,
    creer_dossier,
    creer_session,
    creer_utilisateur,
    deplacer_discussion,
    enregistrer_evenement_reponse,
    enregistrer_tour,
    historique as historique_persistant,
    lister_espace,
    lister_journal_reponses,
    obtenir_discussion,
    obtenir_utilisateur,
    obtenir_utilisateur_session,
    supprimer_discussion,
    supprimer_dossier,
    supprimer_session,
)
from rag import DOSSIER_DOCUMENTS, indexer_pdf, repondre
from recherche_web import recherche_web_disponible, rechercher


app = FastAPI(title="Tyson AI — Tuteur pédagogique", version="0.1.0")
DOSSIER = Path(__file__).resolve().parent
TAILLE_MAX_PDF = 20 * 1024 * 1024
NOM_COOKIE_SESSION = "tyson_session"
DUREE_SESSION_SECONDES = 30 * 24 * 60 * 60
ITERATIONS_MOT_DE_PASSE = 310_000
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes"}
LOGGER = logging.getLogger(__name__)
app.mount("/static", StaticFiles(directory=DOSSIER / "static"), name="static")


def empreinte_fichier(chemin: Path) -> str:
    """Calcule l'empreinte d'un fichier sans le charger entièrement en mémoire."""
    empreinte = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def empreinte_jeton(jeton: str) -> str:
    """Retourne l'empreinte stockable d'un jeton de session opaque."""
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def empreinte_mot_de_passe(mot_de_passe: str, sel_hex: str) -> str:
    empreinte = hashlib.pbkdf2_hmac(
        "sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel_hex), ITERATIONS_MOT_DE_PASSE
    )
    return empreinte.hex()


def utilisateur_connecte(request: Request) -> dict:
    jeton = request.cookies.get(NOM_COOKIE_SESSION)
    if not jeton:
        raise HTTPException(status_code=401, detail="Connecte-toi pour continuer.")
    utilisateur = obtenir_utilisateur_session(empreinte_jeton(jeton))
    if utilisateur is None:
        raise HTTPException(status_code=401, detail="Ta session a expiré. Connecte-toi à nouveau.")
    return utilisateur


def creer_cookie_session(response: Response, utilisateur_id: int) -> None:
    jeton = secrets.token_urlsafe(32)
    expire_le = time.time() + DUREE_SESSION_SECONDES
    creer_session(empreinte_jeton(jeton), utilisateur_id, expire_le)
    response.set_cookie(
        NOM_COOKIE_SESSION,
        jeton,
        max_age=DUREE_SESSION_SECONDES,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def utilisateur_public(utilisateur: dict) -> dict:
    return {
        "id": utilisateur["id"],
        "nom_utilisateur": utilisateur["nom_utilisateur"],
        "role": utilisateur["role"],
    }


@app.get("/", include_in_schema=False)
def accueil() -> FileResponse:
    """Affiche l'interface web du chatbot."""
    return FileResponse(
        DOSSIER / "static" / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/documents")
def ajouter_document(
    fichier: UploadFile = File(...), _utilisateur: dict = Depends(utilisateur_connecte)
) -> dict:
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
        LOGGER.exception("Le PDF reçu est illisible : %s", destination.name)
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="Ce PDF est illisible ou protégé par un mot de passe.",
        ) from erreur
    except Exception as erreur:
        LOGGER.exception("L'indexation du PDF a échoué : %s", destination.name)
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
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    rechercher_sur_web: bool = False


class NouveauDossier(BaseModel):
    nom: str = Field(min_length=1, max_length=60)


class NouvelleDiscussion(BaseModel):
    dossier_id: int | None = None


class DeplacementDiscussion(BaseModel):
    dossier_id: int | None = None


class Source(BaseModel):
    source: str | None = None
    page: int | None = None
    title: str | None = None
    url: str | None = None


class Reponse(BaseModel):
    reponse: str
    sources: list[Source]


class Identifiants(BaseModel):
    nom_utilisateur: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    mot_de_passe: str = Field(min_length=10, max_length=128)


@app.get("/api/auth/me")
def verifier_session(utilisateur: dict = Depends(utilisateur_connecte)) -> dict:
    return {"utilisateur": utilisateur_public(utilisateur)}


@app.post("/api/auth/register", status_code=201)
def inscrire(body: Identifiants, response: Response) -> dict:
    nom = body.nom_utilisateur.strip()
    sel = secrets.token_hex(16)
    empreinte = empreinte_mot_de_passe(body.mot_de_passe, sel)
    try:
        utilisateur = creer_utilisateur(nom, sel, empreinte)
    except sqlite3.IntegrityError as erreur:
        raise HTTPException(
            status_code=409, detail="Ce nom d'utilisateur est déjà utilisé."
        ) from erreur
    creer_cookie_session(response, utilisateur["id"])
    return {"utilisateur": utilisateur_public(utilisateur)}


@app.post("/api/auth/login")
def connecter_utilisateur(body: Identifiants, response: Response) -> dict:
    utilisateur = obtenir_utilisateur(body.nom_utilisateur.strip())
    if utilisateur is None or not hmac.compare_digest(
        empreinte_mot_de_passe(body.mot_de_passe, utilisateur["sel_mot_de_passe"]),
        utilisateur["empreinte_mot_de_passe"],
    ):
        raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe incorrect.")
    creer_cookie_session(response, utilisateur["id"])
    return {"utilisateur": utilisateur_public(utilisateur)}


@app.post("/api/auth/logout", status_code=204)
def deconnecter(request: Request, response: Response) -> None:
    jeton = request.cookies.get(NOM_COOKIE_SESSION)
    if jeton:
        supprimer_session(empreinte_jeton(jeton))
    response.delete_cookie(
        NOM_COOKIE_SESSION,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


@app.get("/api/admin/journal")
def consulter_journal(
    limite: int = 100, utilisateur: dict = Depends(utilisateur_connecte)
) -> dict:
    if utilisateur["role"] != "admin":
        raise HTTPException(status_code=403, detail="Le journal est réservé à l'administrateur.")
    return {"evenements": lister_journal_reponses(max(1, min(limite, 200)))}


@app.get("/api/espace")
def consulter_espace(_utilisateur: dict = Depends(utilisateur_connecte)) -> dict:
    """Renvoie les dossiers et discussions partagés sur ce serveur."""
    return lister_espace()


@app.get("/api/config")
def consulter_configuration(_utilisateur: dict = Depends(utilisateur_connecte)) -> dict:
    """Expose uniquement l'état des options, jamais leurs clés secrètes."""
    return {"recherche_web_disponible": recherche_web_disponible()}


@app.post("/api/dossiers", status_code=201)
def ajouter_dossier(
    body: NouveauDossier, _utilisateur: dict = Depends(utilisateur_connecte)
) -> dict:
    """Crée un dossier commun à tous les utilisateurs de l'application."""
    try:
        return creer_dossier(body.nom)
    except ValueError as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except sqlite3.IntegrityError as erreur:
        raise HTTPException(status_code=409, detail="Un dossier porte déjà ce nom.") from erreur


@app.delete("/api/dossiers/{dossier_id}", status_code=204)
def retirer_dossier(
    dossier_id: int, _utilisateur: dict = Depends(utilisateur_connecte)
) -> None:
    """Supprime un dossier; ses discussions restent visibles sans dossier."""
    if not supprimer_dossier(dossier_id):
        raise HTTPException(status_code=404, detail="Dossier introuvable.")


@app.post("/api/discussions", status_code=201)
def nouvelle_discussion(
    body: NouvelleDiscussion, _utilisateur: dict = Depends(utilisateur_connecte)
) -> dict:
    """Crée une discussion partagée, éventuellement dans un dossier."""
    try:
        return creer_discussion(body.dossier_id)
    except LookupError as erreur:
        raise HTTPException(status_code=404, detail=str(erreur)) from erreur


@app.get("/api/discussions/{discussion_id}")
def charger_discussion(
    discussion_id: str, _utilisateur: dict = Depends(utilisateur_connecte)
) -> dict:
    """Charge les messages et sources d'une discussion partagée."""
    discussion = obtenir_discussion(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion introuvable.")
    return discussion


@app.patch("/api/discussions/{discussion_id}/dossier")
def ranger_discussion(
    discussion_id: str,
    body: DeplacementDiscussion,
    _utilisateur: dict = Depends(utilisateur_connecte),
) -> dict:
    """Déplace une discussion vers un autre dossier ou la retire d'un dossier."""
    try:
        modifiee = deplacer_discussion(discussion_id, body.dossier_id)
    except LookupError as erreur:
        raise HTTPException(status_code=404, detail=str(erreur)) from erreur
    if not modifiee:
        raise HTTPException(status_code=404, detail="Discussion introuvable.")
    return {"id": discussion_id, "dossier_id": body.dossier_id}


@app.delete("/api/discussions/{discussion_id}", status_code=204)
def retirer_discussion(
    discussion_id: str, _utilisateur: dict = Depends(utilisateur_connecte)
) -> None:
    """Supprime une discussion et les messages qu'elle contient."""
    if not supprimer_discussion(discussion_id):
        raise HTTPException(status_code=404, detail="Discussion introuvable.")


@app.post("/ask", response_model=Reponse)
def ask(body: Question, utilisateur: dict = Depends(utilisateur_connecte)) -> dict:
    """Répond avec les PDF indexés et, si demandé, des sources web."""
    debut = time.perf_counter()
    sources_pdf = 0
    sources_web_comptees = 0

    def journaliser(statut: str, code_erreur: str | None = None) -> None:
        try:
            enregistrer_evenement_reponse(
                utilisateur["id"],
                body.conversation_id,
                statut,
                max(0, round((time.perf_counter() - debut) * 1000)),
                code_erreur,
                sources_pdf,
                sources_web_comptees,
            )
        except Exception as erreur:
            # L'échec du journal ne doit pas masquer la réponse du chatbot.
            LOGGER.error("Enregistrement du journal impossible (%s)", type(erreur).__name__)

    try:
        if not body.question.strip():
            raise HTTPException(status_code=422, detail="La question ne peut pas être vide.")
        if body.conversation_id:
            historique = historique_persistant(body.conversation_id)
            if historique is None:
                raise HTTPException(status_code=404, detail="Discussion introuvable.")
        else:
            historique = [
                {"role": message.role, "content": message.content}
                for message in body.historique
            ]
        question_recherche_web = body.question
        if len(body.question.split()) <= 5 and historique:
            derniere_question = next(
                (message["content"] for message in reversed(historique)
                 if message.get("role") == "user"),
                "",
            )
            if derniere_question:
                question_recherche_web = f"{derniere_question} — question de suivi : {body.question}"
        sources_web = rechercher(question_recherche_web) if (
            body.rechercher_sur_web and recherche_web_disponible()
        ) else []
        resultat = repondre(
            body.question,
            historique=historique,
            sources_web=sources_web,
        )
        if body.conversation_id:
            enregistrer_tour(
                body.conversation_id,
                body.question.strip(),
                resultat["reponse"],
                resultat["sources"],
            )
        sources_pdf = sum(1 for source in resultat.get("sources", []) if not source.get("url"))
        sources_web_comptees = sum(1 for source in resultat.get("sources", []) if source.get("url"))
        journaliser("reussite")
        return resultat
    except HTTPException as erreur:
        journaliser("echec", f"http_{erreur.status_code}")
        raise
    except requests.Timeout as erreur:
        journaliser("echec", "delai_depasse")
        raise HTTPException(
            status_code=504,
            detail="Ollama met trop de temps à répondre. Le premier chargement peut être plus long.",
        ) from erreur
    except requests.HTTPError as erreur:
        code = erreur.response.status_code if erreur.response is not None else 502
        journaliser("echec", f"ollama_http_{code}")
        if code == 404:
            detail = "Modèle Ollama introuvable : vérifie LLM_MODEL et les modèles installés."
        else:
            detail = f"Ollama a renvoyé une erreur HTTP {code}."
        raise HTTPException(status_code=502, detail=detail) from erreur
    except requests.RequestException as erreur:
        journaliser("echec", "service_injoignable")
        raise HTTPException(
            status_code=502,
            detail="Impossible de joindre Ollama sur http://127.0.0.1:11434.",
        ) from erreur
    except ImportError as erreur:
        journaliser("echec", "dependance_manquante")
        raise HTTPException(
            status_code=503,
            detail=(
                "Une dépendance native est manquante. Sous Windows, installe le "
                "Microsoft Visual C++ Redistributable x64, puis redémarre l'API."
            ),
        ) from erreur
    except FileNotFoundError as erreur:
        journaliser("echec", "fichier_manquant")
        raise HTTPException(status_code=503, detail=str(erreur)) from erreur
    except ValueError as erreur:
        journaliser("echec", "donnee_invalide")
        raise HTTPException(status_code=502, detail=str(erreur)) from erreur
    except RuntimeError as erreur:
        journaliser("echec", "erreur_execution")
        raise HTTPException(status_code=503, detail=str(erreur)) from erreur
    except Exception as erreur:
        journaliser("echec", "erreur_interne")
        LOGGER.error("Erreur inattendue pendant une réponse (%s)", type(erreur).__name__)
        raise HTTPException(
            status_code=500,
            detail="Une erreur interne est survenue pendant la génération de la réponse.",
        ) from erreur
