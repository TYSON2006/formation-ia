# Chatbot documentaire (Ollama + RAG)

Cette version utilise Ollama en local. Les réponses sont générées sur ton
ordinateur ; aucune clé API Mistral n'est nécessaire.

## Fonctionnement

1. `rag.py` extrait le texte des PDF, le découpe et sauvegarde les embeddings
   dans `index/` avec ChromaDB.
2. À chaque question, ChromaDB retrouve des passages pertinents.
3. `llm.py` envoie les passages à Ollama et valide la réponse JSON.
4. `main.py` expose l'API `POST /ask` et sert l'interface web du chat.
5. L'interface garde les six derniers messages de la discussion pour aider à
   comprendre les questions de suivi. Le bouton « Nouvelle discussion » efface
   cet historique.

Les passages gardent le nom du PDF et le numéro de page pour afficher les sources.

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
OLLAMA_KEEP_ALIVE=10m
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=256
HF_HUB_OFFLINE=1
```

Ollama garde le modèle chargé pendant dix minutes après une réponse. La toute
première réponse après démarrage peut être plus lente, le temps de charger le
modèle. La taille de réponse est limitée à 256 tokens pour éviter les générations
trop longues.

## Indexer les documents

À chaque ajout ou modification d'un PDF, lance depuis ce dossier :

```powershell
.\.venv\Scripts\python.exe .\rag.py
```

Les PDF doivent être dans `documents/`. Les PDF scannés sans texte sélectionnable
ne seront pas indexés correctement. Le modèle d'embedding multilingue est distinct
du modèle Ollama. Il est déjà en cache après l'indexation précédente ;
`HF_HUB_OFFLINE=1` évite les vérifications réseau répétées. Sur un autre ordinateur
ou si le modèle n'est pas en cache, mets temporairement `HF_HUB_OFFLINE=0`, lance
`rag.py` avec Internet, puis remets `HF_HUB_OFFLINE=1`.

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
