"""Compare les pages retrouvées par la recherche RAG pour plusieurs valeurs de k."""

import json
import unicodedata
from pathlib import Path
from typing import Any

from rag import obtenir_collection


DOSSIER = Path(__file__).resolve().parent
FICHIER_QUESTIONS = DOSSIER / "evaluation" / "questions.json"
VALEURS_K = (1, 2, 4, 6)


def normaliser(texte: str) -> str:
    """Compare les noms de fichiers sans distinguer casse ni accents."""
    decompose = unicodedata.normalize("NFD", texte.casefold())
    return "".join(
        caractere
        for caractere in decompose
        if unicodedata.category(caractere) != "Mn"
    )


def pages_retrouvees(
    extraits: list[tuple[str, dict[str, Any]]],
    source_attendue: str,
    k: int,
) -> set[int]:
    """Renvoie les pages attendues présentes dans les k premiers passages."""
    cle_source = normaliser(source_attendue)
    pages: set[int] = set()
    for _, metadonnees in extraits[:k]:
        source = normaliser(str(metadonnees.get("source", "")))
        if cle_source in source:
            pages.add(int(metadonnees["page"]))
    return pages


def pourcentage(valeur: float) -> str:
    return f"{valeur * 100:5.1f}%"


def main() -> int:
    donnees = json.loads(FICHIER_QUESTIONS.read_text(encoding="utf-8"))
    questions = donnees["questions"]
    source_attendue = donnees["source_contains"]

    collection = obtenir_collection()
    nombre_chunks = collection.count()
    if nombre_chunks == 0:
        print("L'index est vide. Ajoute des PDF dans documents/ puis lance rag.py.")
        return 1

    maximum_k = max(VALEURS_K)
    resultat_recherche = collection.query(
        query_texts=[element["question"] for element in questions],
        n_results=min(maximum_k, nombre_chunks),
        include=["documents", "metadatas"],
    )
    documents_trouves = resultat_recherche.get("documents") or []
    metadonnees_trouvees = resultat_recherche.get("metadatas") or []

    observations: list[dict[str, Any]] = []
    for index, element in enumerate(questions):
        textes = documents_trouves[index] if index < len(documents_trouves) else []
        metas = metadonnees_trouvees[index] if index < len(metadonnees_trouvees) else []
        extraits = [
            (texte, meta)
            for texte, meta in zip(textes, metas)
            if texte and meta
        ]
        pages_attendues = set(element["pages_attendues"])
        mesures: dict[int, tuple[float, float, float]] = {}

        for k in VALEURS_K:
            pages = pages_retrouvees(extraits, source_attendue, k)
            bonnes_pages = pages & pages_attendues
            rappel = len(bonnes_pages) / len(pages_attendues)
            rangs_pertinents = [
                rang
                for rang, (_, metadonnees) in enumerate(extraits[:k], start=1)
                if normaliser(source_attendue) in normaliser(
                    str(metadonnees.get("source", ""))
                )
                and int(metadonnees["page"]) in pages_attendues
            ]
            hit = 1.0 if bonnes_pages else 0.0
            reciprocal_rank = 1 / min(rangs_pertinents) if rangs_pertinents else 0.0
            mesures[k] = (hit, rappel, reciprocal_rank)

        observations.append(
            {
                "id": element["id"],
                "question": element["question"],
                "reponse_attendue": element["reponse_attendue"],
                "pages_attendues": pages_attendues,
                "extraits": extraits,
                "mesures": mesures,
            }
        )

    print(f"Évaluation de la recherche sur {len(observations)} questions")
    print(f"Document de référence : {source_attendue}")
    print("Ces scores mesurent la recherche des pages, pas la qualité des réponses Ollama.\n")
    print("k   Hit@k   Recall@k   MRR@k")
    for k in VALEURS_K:
        hit_moyen = sum(item["mesures"][k][0] for item in observations) / len(observations)
        rappel_moyen = sum(item["mesures"][k][1] for item in observations) / len(observations)
        mrr_moyen = sum(item["mesures"][k][2] for item in observations) / len(observations)
        print(
            f"{k:<3} {pourcentage(hit_moyen):>7}"
            f" {pourcentage(rappel_moyen):>10} {mrr_moyen:7.3f}"
        )

    print("\nDétail des passages retrouvés (maximum 6 par question) :")
    for item in observations:
        references = [
            f"{rang}. {unicodedata.normalize('NFC', str(metadonnees.get('source', '?')))}, "
            f"page {metadonnees.get('page', '?')}"
            for rang, (_, metadonnees) in enumerate(item["extraits"], start=1)
        ]
        print(f"\n{item['id']} — {item['question']}")
        print(f"  Réponse de référence : {item['reponse_attendue']}")
        print(f"  Page(s) attendue(s) : {', '.join(map(str, sorted(item['pages_attendues'])))}")
        print(f"  Retrouvé : {' | '.join(references) if references else 'aucun passage'}")

    if all(not item["mesures"][maximum_k][0] for item in observations):
        print(
            "\nAucune page attendue n'a été retrouvée. Vérifie que le PDF de référence "
            "est présent dans documents/ et qu'il a été indexé."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
