# Tuteur pédagogique IA (Ollama + RAG)

Cette version utilise Ollama en local. Les réponses sont générées sur ton
ordinateur ; aucune clé API Mistral n'est nécessaire.

## Objectif pédagogique

Le projet est un tuteur qui aide les apprenants, notamment les débutants, à
comprendre leurs supports de cours. Il explique avec des mots simples, peut donner
un exemple lorsque les PDF le permettent et indique les pages qui justifient sa
réponse. Il reconnaît aussi quand les supports indexés ne contiennent pas la
réponse.

Le tuteur n'a pas été réentraîné sur un domaine. Avec le RAG, son sujet dépend des
PDF ajoutés : le cours de départ porte sur l'IA pour développeurs. Pour le
spécialiser dans une autre matière, ajoute des supports de cours de cette matière
et des questions de référence pour évaluer ses réponses.

## Fonctionnement

1. `rag.py` extrait le texte des PDF, le découpe et sauvegarde les embeddings
   dans `index/` avec ChromaDB.
2. À chaque question, ChromaDB retrouve des passages pertinents.
3. `llm.py` envoie les passages à Ollama et valide la réponse JSON.
4. `main.py` expose l'API `POST /ask`, reçoit les PDF sur `POST /documents` et sert l'interface web du chat.
5. L'interface garde les six derniers messages de la discussion pour aider à
   comprendre les questions de suivi. Le bouton « Nouvelle discussion » efface
   cet historique.

Les passages gardent le nom du PDF et le numéro de page pour afficher les sources.
Les PDF de formation ne sont pas publiés dans ce dépôt ; chacun peut ajouter ses
propres documents dans `documents/`.

## Organisation des fichiers

| Fichier ou dossier | Rôle dans le projet |
| --- | --- |
| `main.py` | API FastAPI et interface web : `POST /ask` répond aux questions, `POST /documents` reçoit un PDF (20 Mo maximum), détecte les copies exactes et l'indexe. |
| `rag.py` | Extrait le texte des PDF, le découpe en passages de 350 mots avec 50 mots de chevauchement, le stocke dans ChromaDB, retrouve les passages, prépare les sources et gère le cache des réponses. |
| `llm.py` | Envoie les passages à Ollama, demande une réponse JSON concise et vérifie que le JSON reçu est valide. |
| `static/index.html` | Structure de la page du chat, de la zone de saisie et du bouton d'ajout PDF. |
| `static/style.css` | Apparence de l'interface et adaptation aux petits écrans. |
| `static/app.js` | Envoi des questions, historique de discussion, ajout de PDF et affichage des réponses, erreurs et sources. |
| `documents/` | PDF locaux à indexer. Les fichiers PDF sont ignorés par Git et ne sont donc pas publiés. |
| `index/` | Base ChromaDB et cache SQLite des réponses créés localement ; ils sont régénérables et ignorés par Git. |
| `evaluation/questions.json` | Questions de référence, réponses attendues et pages à retrouver dans le cours d'introduction à l'IA. |
| `evaluer_rag.py` | Mesure si les bonnes pages sont retrouvées avec `k = 1, 2, 4, 6`. Le script n'appelle pas Ollama. |
| `requirements.txt` | Dépendances Python nécessaires au projet. |
| `.env.example` | Exemple de réglages locaux pour Ollama ; à copier vers `.env`. |
| `.env` | Réglages privés de ta machine. Ce fichier est ignoré par Git. |
| `.gitignore` | Empêche l'envoi de `.env`, des environnements Python, de l'index et des PDF locaux. |

### Modifications récentes

Les fichiers suivants ont été ajoutés ou modifiés pour les dernières étapes :

- `main.py` : ajout de `POST /documents`. Cette route accepte un PDF, vérifie son
  extension et son contenu, limite sa taille à 20 Mo, refuse une copie exacte déjà
  importée et ajoute un suffixe si un PDF différent porte le même nom.
- `rag.py` : ajout de durées dans le terminal du serveur pour distinguer le temps
  de recherche documentaire du temps de génération par Ollama, et d'un cache local
  qui peut réutiliser les réponses identiques sans rappeler le modèle.
- `rag.py`, `static/index.html` et `static/app.js` : positionnement du chatbot comme
  tuteur pédagogique pour apprenants ; le prompt demande des explications simples,
  des exemples tirés des supports et des sources vérifiables.
- `llm.py` et `.env.example` : modèle conservé en mémoire plus longtemps et limite
  de génération réduite pour obtenir des réponses plus courtes.
- `requirements.txt` : ajout de `python-multipart`, utilisé par FastAPI pour
  recevoir le fichier envoyé par le navigateur.
- `static/index.html` : ajout du bouton `+ PDF` et du sélecteur de fichier dans
  la zone de saisie.
- `static/app.js` : envoi du PDF à l'API, désactivation temporaire des actions
  pendant l'indexation, et affichage du résultat ou d'une erreur dans le chat.
- `static/style.css` : style du bouton PDF et ajustement de la zone de saisie.
- `evaluer_rag.py` : nouveau script de mesure qui compare la recherche à
  `k = 1, 2, 4, 6` sans démarrer Ollama.
- `evaluation/questions.json` : nouveau jeu de 12 questions, avec réponses de
  référence et pages utiles du cours.
- `README.md` : ajout de cet inventaire et des instructions d'indexation et
  d'évaluation.

`llm.py` appelle toujours Ollama et valide le JSON reçu. Les durées affichées par
`rag.py` permettent de voir si l'attente vient surtout de la recherche ou de la
génération locale.

## Installer le projet après l'avoir cloné

Dans PowerShell, clone le dépôt, crée un environnement Python et installe les
dépendances :

```powershell
git clone https://github.com/TYSON2006/formation-ia.git
cd formation-ia
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Chaque personne doit avoir Python et Ollama installés sur son ordinateur. Le
fichier `.env` est local et ne doit pas être envoyé sur GitHub.

## Préparation

Installe et démarre l'application Ollama pour Windows. Le modèle configuré est
`llama3.2:3b`, qui est déjà installé dans cette configuration. Si tu dois le
télécharger de nouveau dans PowerShell, utilise :

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull llama3.2:3b
```

L'API locale d'Ollama doit répondre sur `http://127.0.0.1:11434`. Tu peux vérifier
qu'elle tourne avec :

```powershell
Invoke-WebRequest http://127.0.0.1:11434/api/tags
```

Le fichier `.env` contient les réglages locaux :

```dotenv
LLM_URL=http://127.0.0.1:11434/api/chat
LLM_MODEL=llama3.2:3b
LLM_TIMEOUT=180
OLLAMA_KEEP_ALIVE=30m
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=160
HF_HUB_OFFLINE=1
```

Ollama garde le modèle chargé pendant 30 minutes après une réponse. Cela peut
accélérer la première question après une courte pause, en utilisant la mémoire de
l'ordinateur pendant ce temps. La génération est limitée à 160 tokens et les
réponses demandées sont courtes.

## Indexer les documents

Tu peux ajouter un PDF directement dans l'interface avec le bouton « + PDF » près
de la zone de saisie. Le fichier est enregistré dans `documents/` puis indexé
automatiquement. La limite est de 20 Mo par fichier. Plusieurs PDF peuvent porter
le même nom : si leur contenu diffère, l'application ajoute un suffixe
(`Document (2).pdf`). Une copie exacte déjà importée est refusée et indique le nom
du fichier existant.

L'autre méthode consiste à déposer les PDF dans `documents/`, puis à lancer depuis
ce dossier :

```powershell
.\.venv\Scripts\python.exe .\rag.py
```

Les PDF doivent être dans `documents/`. Les PDF scannés sans texte sélectionnable
ne seront pas indexés correctement. Le modèle d'embedding multilingue est distinct
du modèle Ollama. Il est déjà en cache après l'indexation précédente ;
`HF_HUB_OFFLINE=1` évite les vérifications réseau répétées. Sur un autre ordinateur
ou si le modèle n'est pas en cache, mets temporairement `HF_HUB_OFFLINE=0`, lance
`rag.py` avec Internet, puis remets `HF_HUB_OFFLINE=1`.

## Mesurer la recherche RAG

Le jeu de référence `evaluation/questions.json` s'appuie sur le PDF
`Comprendre l'IA pour développeurs.pdf`, qui n'est pas inclus dans GitHub. Il doit
être présent dans `documents/` et indexé. Après avoir mis à jour l'index, lance :

```powershell
.\.venv\Scripts\python.exe .\evaluer_rag.py
```

Le script compare les pages retrouvées parmi les 1, 2, 4 ou 6 premiers passages.
`Hit@k` indique la proportion de questions pour lesquelles au moins une page
attendue apparaît. `Recall@k` indique la proportion moyenne des pages attendues
retrouvées. `MRR@k` favorise les réglages qui placent une bonne page plus haut dans
les résultats. Le tableau aide à voir si envoyer plus de passages améliore la
recherche ou ajoute surtout du contexte moins pertinent. Le détail affiche aussi
les passages et les réponses de référence pour inspection manuelle.
La toute première exécution peut prendre du temps car le modèle d'embedding doit
se charger ; cette évaluation ne démarre pas Ollama.

Ces scores ne signifient pas automatiquement que les réponses générées sont
correctes : ils vérifient seulement que la recherche retrouve les bonnes pages.
Pour tester avec d'autres PDF, adapte `evaluation/questions.json` : écris des
questions, leurs réponses de référence, le nom du document et ses pages utiles.

Pour mettre à jour une installation déjà clonée afin d'ajouter le bouton PDF,
installe la nouvelle dépendance de réception des fichiers depuis PowerShell :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Tester Ollama seul

Cette commande demande une petite réponse JSON au modèle local :

```powershell
.\.venv\Scripts\python.exe .\llm.py
```

La réponse attendue contient les clés `reponse` et `notions_cles`.

## Démarrer le chatbot et ouvrir l'interface

Dans le terminal VS Code, place-toi dans le dossier `formation-ia`, puis lance :

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Laisse ce terminal ouvert et va sur <http://127.0.0.1:8000>. Tu peux cliquer sur
une question proposée ou écrire la tienne. Après la réponse, les sources et leurs
pages apparaissent sous le message. Pour vérifier le contexte, pose une question
de suivi, par exemple « Peux-tu expliquer cela plus simplement ? ». « Nouvelle
discussion » efface les messages affichés et le contexte transmis au modèle.

La première réponse après le démarrage peut prendre plus de temps : Ollama doit
charger son modèle. Pendant la recherche, l'interface affiche une animation.
Après avoir ajouté un PDF, attends le message « Document prêt », puis pose une
question sur son contenu. Un PDF scanné peut nécessiter une reconnaissance de texte
(OCR), qui n'est pas encore incluse dans le projet.

Les réponses sont gardées dans `index/reponses_cache.sqlite3` (au plus 500 entrées).
Une réponse est réutilisée quand la question, l'historique pertinent, les passages
retrouvés et le modèle sont identiques. Si un nouveau PDF change les passages
retrouvés, le chatbot génère une nouvelle réponse. Le terminal affiche `cache=hit`
quand Ollama a été évité, ou `cache=miss` quand une nouvelle génération a été
nécessaire, ainsi que les durées de recherche et de génération.
L'ajout d'un PDF peut ralentir son indexation ; la génération dépend surtout du
modèle local et de l'ordinateur.

## Tester l'API directement

Tu peux aussi ouvrir <http://127.0.0.1:8000/docs>, choisir `POST /ask`, cliquer
sur « Try it out », puis envoyer :

```json
{
  "question": "Qu'est-ce qu'un token dans un modèle de langage ?",
  "historique": []
}
```

La réponse contient une explication et les références aux PDF, par exemple :

```json
{
  "reponse": "... (Comprendre l'IA pour développeurs.pdf, page 3)",
  "sources": [
    {
      "source": "Comprendre l'IA pour développeurs.pdf",
      "page": 3
    }
  ]
}
```

Si les extraits ne contiennent pas la réponse, le chatbot répond qu'il ne trouve
pas l'information et renvoie `"sources": []`.

## Dépannage Windows

- Si `llm.py` dit qu'Ollama ne répond pas, démarre l'application Ollama et vérifie
  `http://127.0.0.1:11434/api/tags`.
- Si Ollama ne trouve pas `llama3.2:3b`, télécharge-le avec la commande indiquée
  dans la section Préparation.
- Si ChromaDB signale `DLL load failed while importing chromadb_rust_bindings`,
  installe le Microsoft Visual C++ Redistributable x64, puis redémarre VS Code.
