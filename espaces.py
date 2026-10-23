"""Stockage SQLite des comptes, sessions, réponses et espaces partagés."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DOSSIER = Path(__file__).resolve().parent
BASE = DOSSIER / "index" / "espaces.sqlite3"


@contextmanager
def connecter() -> Iterator[sqlite3.Connection]:
    BASE.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(BASE, timeout=10)
    connexion.row_factory = sqlite3.Row
    connexion.execute("PRAGMA foreign_keys = ON")
    try:
        yield connexion
        connexion.commit()
    except Exception:
        connexion.rollback()
        raise
    finally:
        connexion.close()


def initialiser() -> None:
    with connecter() as connexion:
        connexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS dossiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL COLLATE NOCASE UNIQUE,
                cree_le REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS discussions (
                id TEXT PRIMARY KEY,
                dossier_id INTEGER REFERENCES dossiers(id) ON DELETE SET NULL,
                titre TEXT NOT NULL,
                cree_le REAL NOT NULL,
                modifie_le REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discussion_id TEXT NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                contenu TEXT NOT NULL,
                sources TEXT NOT NULL DEFAULT '[]',
                cree_le REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_utilisateur TEXT NOT NULL COLLATE NOCASE UNIQUE,
                sel_mot_de_passe TEXT NOT NULL,
                empreinte_mot_de_passe TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'membre')),
                cree_le REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                empreinte_jeton TEXT PRIMARY KEY,
                utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
                expire_le REAL NOT NULL,
                cree_le REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_expiration ON sessions(expire_le);
            CREATE TABLE IF NOT EXISTS journal_reponses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
                discussion_id TEXT,
                statut TEXT NOT NULL CHECK (statut IN ('reussite', 'echec')),
                duree_ms INTEGER NOT NULL,
                code_erreur TEXT,
                sources_pdf INTEGER NOT NULL DEFAULT 0,
                sources_web INTEGER NOT NULL DEFAULT 0,
                cree_le REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_journal_reponses_date
                ON journal_reponses(cree_le DESC);
            CREATE INDEX IF NOT EXISTS idx_discussions_dossier_modifie
                ON discussions(dossier_id, modifie_le DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_discussion
                ON messages(discussion_id, id);
            """
        )


def creer_utilisateur(nom_utilisateur: str, sel: str, empreinte: str) -> dict[str, Any]:
    """Crée le premier compte comme administrateur, puis des comptes membres."""
    with connecter() as connexion:
        # Sérialise l'attribution du premier rôle admin en cas d'inscriptions
        # simultanées : un seul compte peut devenir le premier.
        connexion.execute("BEGIN IMMEDIATE")
        role = "admin" if connexion.execute(
            "SELECT 1 FROM utilisateurs LIMIT 1"
        ).fetchone() is None else "membre"
        curseur = connexion.execute(
            "INSERT INTO utilisateurs "
            "(nom_utilisateur, sel_mot_de_passe, empreinte_mot_de_passe, role, cree_le) "
            "VALUES (?, ?, ?, ?, ?)",
            (nom_utilisateur, sel, empreinte, role, time.time()),
        )
        ligne = connexion.execute(
            "SELECT id, nom_utilisateur, role, cree_le FROM utilisateurs WHERE id = ?",
            (curseur.lastrowid,),
        ).fetchone()
    return dict(ligne)


def obtenir_utilisateur(nom_utilisateur: str) -> dict[str, Any] | None:
    with connecter() as connexion:
        ligne = connexion.execute(
            "SELECT id, nom_utilisateur, sel_mot_de_passe, empreinte_mot_de_passe, "
            "role, cree_le FROM utilisateurs WHERE nom_utilisateur = ?",
            (nom_utilisateur,),
        ).fetchone()
    return dict(ligne) if ligne else None


def creer_session(empreinte_jeton: str, utilisateur_id: int, expire_le: float) -> None:
    maintenant = time.time()
    with connecter() as connexion:
        connexion.execute("DELETE FROM sessions WHERE expire_le <= ?", (maintenant,))
        connexion.execute(
            "INSERT INTO sessions (empreinte_jeton, utilisateur_id, expire_le, cree_le) "
            "VALUES (?, ?, ?, ?)",
            (empreinte_jeton, utilisateur_id, expire_le, maintenant),
        )


def obtenir_utilisateur_session(empreinte_jeton: str) -> dict[str, Any] | None:
    with connecter() as connexion:
        ligne = connexion.execute(
            "SELECT u.id, u.nom_utilisateur, u.role, u.cree_le "
            "FROM sessions s JOIN utilisateurs u ON u.id = s.utilisateur_id "
            "WHERE s.empreinte_jeton = ? AND s.expire_le > ?",
            (empreinte_jeton, time.time()),
        ).fetchone()
    return dict(ligne) if ligne else None


def supprimer_session(empreinte_jeton: str) -> None:
    with connecter() as connexion:
        connexion.execute(
            "DELETE FROM sessions WHERE empreinte_jeton = ?", (empreinte_jeton,)
        )


def enregistrer_evenement_reponse(
    utilisateur_id: int,
    discussion_id: str | None,
    statut: str,
    duree_ms: int,
    code_erreur: str | None,
    sources_pdf: int,
    sources_web: int,
) -> None:
    with connecter() as connexion:
        connexion.execute(
            "INSERT INTO journal_reponses "
            "(utilisateur_id, discussion_id, statut, duree_ms, code_erreur, "
            "sources_pdf, sources_web, cree_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (utilisateur_id, discussion_id, statut, duree_ms, code_erreur,
             sources_pdf, sources_web, time.time()),
        )


def lister_journal_reponses(limite: int = 100) -> list[dict[str, Any]]:
    with connecter() as connexion:
        lignes = connexion.execute(
            "SELECT j.id, u.nom_utilisateur, j.discussion_id, j.statut, j.duree_ms, "
            "j.code_erreur, j.sources_pdf, j.sources_web, j.cree_le "
            "FROM journal_reponses j JOIN utilisateurs u ON u.id = j.utilisateur_id "
            "ORDER BY j.cree_le DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(ligne) for ligne in lignes]


def creer_dossier(nom: str) -> dict[str, Any]:
    nom_nettoye = " ".join(nom.split())
    if not nom_nettoye or len(nom_nettoye) > 60:
        raise ValueError("Le nom du dossier doit contenir de 1 à 60 caractères.")
    with connecter() as connexion:
        curseur = connexion.execute(
            "INSERT INTO dossiers (nom, cree_le) VALUES (?, ?)",
            (nom_nettoye, time.time()),
        )
        ligne = connexion.execute(
            "SELECT id, nom, cree_le FROM dossiers WHERE id = ?", (curseur.lastrowid,)
        ).fetchone()
    return dict(ligne)


def supprimer_dossier(dossier_id: int) -> bool:
    with connecter() as connexion:
        curseur = connexion.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    return curseur.rowcount > 0


def creer_discussion(dossier_id: int | None = None) -> dict[str, Any]:
    identifiant = uuid.uuid4().hex
    maintenant = time.time()
    with connecter() as connexion:
        if dossier_id is not None and not connexion.execute(
            "SELECT 1 FROM dossiers WHERE id = ?", (dossier_id,)
        ).fetchone():
            raise LookupError("Ce dossier partagé n'existe pas.")
        connexion.execute(
            "INSERT INTO discussions (id, dossier_id, titre, cree_le, modifie_le) "
            "VALUES (?, ?, ?, ?, ?)",
            (identifiant, dossier_id, "Nouvelle discussion", maintenant, maintenant),
        )
    return obtenir_discussion(identifiant)


def obtenir_discussion(identifiant: str) -> dict[str, Any] | None:
    with connecter() as connexion:
        ligne = connexion.execute(
            "SELECT d.id, d.dossier_id, d.titre, d.cree_le, d.modifie_le, f.nom AS dossier "
            "FROM discussions d LEFT JOIN dossiers f ON f.id = d.dossier_id WHERE d.id = ?",
            (identifiant,),
        ).fetchone()
        if ligne is None:
            return None
        resultat = dict(ligne)
        messages = connexion.execute(
            "SELECT role, contenu, sources, cree_le FROM messages "
            "WHERE discussion_id = ? ORDER BY id",
            (identifiant,),
        ).fetchall()
    resultat["messages"] = [
        {
            "role": message["role"],
            "content": message["contenu"],
            "sources": json.loads(message["sources"]),
            "created_at": message["cree_le"],
        }
        for message in messages
    ]
    return resultat


def lister_espace() -> dict[str, Any]:
    with connecter() as connexion:
        dossiers = connexion.execute(
            "SELECT id, nom FROM dossiers ORDER BY nom COLLATE NOCASE"
        ).fetchall()
        discussions = connexion.execute(
            "SELECT id, dossier_id, titre, modifie_le FROM discussions "
            "ORDER BY modifie_le DESC"
        ).fetchall()
    par_dossier: dict[int | None, list[dict[str, Any]]] = {}
    for discussion in discussions:
        par_dossier.setdefault(discussion["dossier_id"], []).append(dict(discussion))
    return {
        "dossiers": [
            {"id": dossier["id"], "nom": dossier["nom"],
             "discussions": par_dossier.pop(dossier["id"], [])}
            for dossier in dossiers
        ],
        "sans_dossier": par_dossier.get(None, []),
    }


def deplacer_discussion(identifiant: str, dossier_id: int | None) -> bool:
    with connecter() as connexion:
        if dossier_id is not None and not connexion.execute(
            "SELECT 1 FROM dossiers WHERE id = ?", (dossier_id,)
        ).fetchone():
            raise LookupError("Ce dossier partagé n'existe pas.")
        curseur = connexion.execute(
            "UPDATE discussions SET dossier_id = ?, modifie_le = ? WHERE id = ?",
            (dossier_id, time.time(), identifiant),
        )
    return curseur.rowcount > 0


def supprimer_discussion(identifiant: str) -> bool:
    with connecter() as connexion:
        curseur = connexion.execute("DELETE FROM discussions WHERE id = ?", (identifiant,))
    return curseur.rowcount > 0


def historique(identifiant: str, limite: int = 6) -> list[dict[str, str]] | None:
    with connecter() as connexion:
        existe = connexion.execute(
            "SELECT 1 FROM discussions WHERE id = ?", (identifiant,)
        ).fetchone()
        if not existe:
            return None
        lignes = connexion.execute(
            "SELECT role, contenu FROM messages WHERE discussion_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (identifiant, limite),
        ).fetchall()
    return [
        {"role": ligne["role"], "content": ligne["contenu"]}
        for ligne in reversed(lignes)
    ]


def enregistrer_tour(
    identifiant: str, question: str, reponse: str, sources: list[dict[str, Any]]
) -> bool:
    maintenant = time.time()
    with connecter() as connexion:
        discussion = connexion.execute(
            "SELECT titre FROM discussions WHERE id = ?", (identifiant,)
        ).fetchone()
        if discussion is None:
            return False
        a_deja_des_messages = connexion.execute(
            "SELECT 1 FROM messages WHERE discussion_id = ? LIMIT 1", (identifiant,)
        ).fetchone()
        if not a_deja_des_messages:
            titre = " ".join(question.split())[:56].strip()
            if len(" ".join(question.split())) > 56:
                titre = titre.rsplit(" ", 1)[0] + "…"
            connexion.execute(
                "UPDATE discussions SET titre = ? WHERE id = ?", (titre, identifiant)
            )
        connexion.executemany(
            "INSERT INTO messages (discussion_id, role, contenu, sources, cree_le) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (identifiant, "user", question, "[]", maintenant),
                (identifiant, "assistant", reponse,
                 json.dumps(sources, ensure_ascii=False), maintenant),
            ),
        )
        connexion.execute(
            "UPDATE discussions SET modifie_le = ? WHERE id = ?", (maintenant, identifiant)
        )
    return True


initialiser()
