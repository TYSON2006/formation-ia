# Tyson AI — tuteur pédagogique (Ollama + RAG)

Cette version utilise Ollama en local. Les réponses sont générées sur ton
ordinateur ; aucune clé API Mistral n'est nécessaire. Une clé Tavily facultative
active la recherche web et les liens vers les pages réellement trouvées.

## Objectif pédagogique

Le projet est un tuteur qui aide les apprenants, notamment les débutants, à
comprendre leurs supports de cours. Il explique avec des mots simples, peut donner
un exemple lorsque les sources le permettent et indique les pages ou liens qui
justifient sa réponse. Il reconnaît aussi quand les sources consultées ne
contiennent pas la réponse.

## Identité du projet

L'application s'appelle **Tyson AI** et son interface affiche sa création par
Tyson. Le prompt de comportement porte l'identifiant
`VERSION_PROMPT = "tuteur-pedagogique-v3-by-tyson"` dans `rag.py` : il sert à
repérer la version du tuteur et fait partie de la clé du cache. Quand les
consignes ou la stratégie de recherche changent de façon importante, incrémente
cette version pour éviter de réutiliser les réponses produites par une ancienne
version.

Le tuteur n'a pas été réentraîné sur un domaine. Ses capacités sont renforcées par
le RAG : une recherche sémantique trouve des passages proches par le sens, puis
un classement BM25 tient compte des termes exacts et diversifie les pages
sélectionnées. Les comptes sont personnels, tandis que les dossiers et discussions
restent partagés par les membres du même serveur. Une recherche web facultative fournit au modèle des extraits et
des URL retournés par Tavily ; le modèle ne fabrique pas les liens.

## Fonctionnement

1. `rag.py` extrait le texte des PDF, le découpe et sauvegarde les embeddings
   dans `index/chroma/` avec ChromaDB, séparément des bases SQLite.
2. À chaque question, ChromaDB retrouve des passages pertinents.
3. `recherche_web.py` peut compléter ces passages avec des résultats web facultatifs.
4. `llm.py` envoie le contexte à Ollama et valide la réponse JSON.
5. `main.py` expose les routes de connexion et protège l'API du chat, des PDF,
   des dossiers et des discussions.
6. `espaces.py` conserve les comptes, les sessions, le journal des réponses, les
   dossiers et les discussions dans SQLite.
7. L'interface retrouve les conversations enregistrées et conserve leur historique
   pour les questions de suivi. L'accueil varie lors du rechargement de la page.

Les passages gardent le nom du PDF et le numéro de page pour afficher les sources.
Les PDF de formation ne sont pas publiés dans ce dépôt ; chacun peut ajouter ses
propres documents dans `documents/`.

## Organisation des fichiers

| Fichier ou dossier | Rôle dans le projet |
| --- | --- |
| `main.py` | API FastAPI : inscription, connexion, sessions, journal administrateur, `POST /ask`, import de PDF, dossiers et discussions. |
| `rag.py` | Extrait le texte des PDF, le découpe en passages de 350 mots avec 50 mots de chevauchement, les stocke dans ChromaDB, récupère jusqu'à 24 candidats et les reclasse avec recherche sémantique, BM25 et diversité des pages ; prépare les sources et gère le cache des réponses. |
| `espaces.py` | Enregistre dans SQLite les comptes, sessions sécurisées, résultats des réponses, dossiers communs, discussions, messages et sources. |
| `recherche_web.py` | Interroge Tavily avec une clé serveur facultative, limite les résultats transmis au modèle et écarte les URL non HTTP(S). |
| `llm.py` | Envoie les passages à Ollama, démarre automatiquement le service local s'il est arrêté, puis vérifie que le JSON reçu est valide. |
| `static/index.html` | Structure de la connexion, du chat, de la barre des dossiers et du journal administrateur. |
| `static/style.css` | Apparence de la connexion, du chat et du journal, avec une barre latérale adaptée aux téléphones. |
| `static/app.js` | Connexion/inscription, navigation partagée, envoi des questions et PDF, affichage des sources et du journal administrateur. |
| `documents/` | PDF locaux à indexer. Les fichiers PDF sont ignorés par Git et ne sont donc pas publiés. |
| `index/` | Index vectoriel ChromaDB (`chroma/`), cache des réponses et données des discussions, tous locaux et ignorés par Git. |
| `evaluation/questions.json` | Questions de référence, réponses attendues et pages à retrouver dans le cours d'introduction à l'IA. |
| `evaluer_rag.py` | Mesure si les bonnes pages sont retrouvées avec `k = 1, 2, 4, 6`. Le script n'appelle pas Ollama. |
| `requirements.txt` | Dépendances Python nécessaires au projet. |
| `lancer_famille.ps1` | Détecte l'adresse Wi-Fi et démarre le serveur web pour un essai sur le réseau local. |
| `.env.example` | Exemple des réglages Ollama et de la clé web facultative ; à copier vers `.env`. |
| `.env` | Réglages privés de ta machine. Ce fichier est ignoré par Git. |
| `.gitignore` | Empêche l'envoi de `.env`, des environnements Python, de l'index et des PDF locaux. |

### Modifications récentes

Les fichiers suivants ont été ajoutés ou modifiés pour les dernières étapes :

- `static/index.html`, `static/style.css` et `static/app.js` : champ de saisie du
  chat agrandi, affiché sur deux lignes au repos et extensible jusqu'à 150 px.
- `llm.py` : si l'API Ollama locale ne répond pas, recherche `ollama.exe`, lance
  `ollama serve` en tâche de fond et attend jusqu'à 30 secondes que l'API soit prête.
  `OLLAMA_START_TIMEOUT` permet d'ajuster cette attente. Le script familial indique
  maintenant que le démarrage sera tenté à la première question.
- `main.py` : ajout de `POST /documents`. Cette route accepte un PDF, vérifie son
  extension et son contenu, limite sa taille à 20 Mo, refuse une copie exacte déjà
  importée et ajoute un suffixe si un PDF différent porte le même nom.
- `rag.py` : ajout de durées dans le terminal du serveur pour distinguer le temps
  de recherche documentaire du temps de génération par Ollama, et d'un cache local
  qui peut réutiliser les réponses identiques sans rappeler le modèle.
- `rag.py`, `static/index.html` et `static/app.js` : positionnement du chatbot comme
  tuteur pédagogique pour apprenants ; le prompt demande des explications simples,
  des exemples tirés des supports et des sources vérifiables.
- `rag.py` : identification de la version du prompt pédagogique sous le nom Tyson ;
  cet identifiant permet aussi de renouveler le cache lorsque le prompt évolue.
- `rag.py` : recherche élargie à 24 passages candidats au maximum, reclassement
  hybride sémantique et BM25 pour mieux retrouver les termes exacts, sélection
  jusqu'à trois passages issus de pages différentes, et meilleur ciblage des
  questions de suivi courtes.
- `rag.py` : consignes pédagogiques enrichies pour définir les termes, expliquer
  les notions avec des exemples issus des supports et guider les exercices par
  étapes ; version du prompt passée à `tuteur-pedagogique-v2-by-tyson`.
- `evaluer_rag.py` : l'évaluation utilise maintenant le même reclassement hybride
  que le chatbot afin de mesurer le parcours réellement utilisé.
- `main.py`, `static/index.html`, `static/style.css` et `static/tyson-logo.svg` :
  personnalisation du nom Tyson AI, ajout de la signature dans l'interface,
  création d'un logo original et nouvelle palette vert canard, avec mise en page
  adaptée aux téléphones.
- `llm.py` et `.env.example` : modèle conservé en mémoire plus longtemps et limite
  de génération réduite pour obtenir des réponses plus courtes.
- `requirements.txt` : ajout de `python-multipart`, utilisé par FastAPI pour
  recevoir le fichier envoyé par le navigateur.
- `static/index.html` : ajout du bouton `+ PDF` et du sélecteur de fichier dans
  la zone de saisie.
- `static/index.html` : précision que les PDF téléversés depuis les téléphones
  sont enregistrés sur l'ordinateur qui héberge le chatbot.
- `static/app.js` : envoi du PDF à l'API, désactivation temporaire des actions
  pendant l'indexation, et affichage du résultat ou d'une erreur dans le chat.
- `lancer_famille.ps1` et `README.md` : démarrage du chatbot sur l'adresse Wi-Fi de
  l'ordinateur hôte, étapes d'accès depuis les appareils familiaux et réglage du
  pare-feu Windows si nécessaire.
- `static/style.css` : style du bouton PDF et ajustement de la zone de saisie.
- `evaluer_rag.py` : nouveau script de mesure qui compare la recherche à
  `k = 1, 2, 4, 6` sans démarrer Ollama.
- `evaluation/questions.json` : nouveau jeu de 12 questions, avec réponses de
  référence et pages utiles du cours.
- `README.md` : ajout de cet inventaire et des instructions d'indexation et
  d'évaluation.
- `espaces.py`, `main.py` : création de dossiers partagés, stockage SQLite des
  discussions et de leurs messages, reprise des conversations et déplacement
  d'une discussion entre dossiers.
- `static/index.html`, `static/style.css`, `static/app.js` : ajout de la barre
  latérale, des filtres par dossier, de la reprise des conversations, des liens
  de sources cliquables et d'un accueil aléatoire à chaque rechargement.
- `recherche_web.py`, `rag.py`, `main.py`, `.env.example` : ajout d'une recherche
  web facultative avec Tavily et citations fondées sur les résultats retournés.
- `README.md` : explication des dossiers partagés et configuration de Tavily.
- `espaces.py` : ajout des tables SQLite pour les comptes, les sessions et le
  journal des réponses. Ces tables sont créées sans supprimer les dossiers et
  discussions déjà enregistrés.
- `main.py` : ajout de l'inscription, de la connexion, de sessions par cookie,
  de la protection des routes et du suivi des réponses réussies ou échouées.
  Le journal stocke les durées, catégories d'erreur et nombres de sources, jamais
  le texte des questions ou des réponses.
- `static/index.html`, `static/style.css`, `static/app.js` : ajout de l'écran de
  connexion, du formulaire d'inscription, de la déconnexion et du journal pour
  l'administrateur.
- `README.md` : instructions sur les comptes et le journal des réponses.

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

L'ordinateur hôte doit avoir Python et Ollama installés. Pour un essai familial
sur le même Wi-Fi, les autres personnes ont besoin d'un navigateur et d'un compte. Le
fichier `.env` est local et ne doit pas être envoyé sur GitHub.

## Préparation

Installe Ollama et vérifie que le modèle `llama3.2:3b` est disponible. Si l'API
locale n'est pas démarrée, `llm.py` tentera de lancer Ollama automatiquement lors
de la première question et attendra jusqu'à 30 secondes. Le modèle est déjà installé
sur cet ordinateur. Si tu dois le télécharger de nouveau dans PowerShell, utilise :

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
OLLAMA_START_TIMEOUT=30
OLLAMA_KEEP_ALIVE=30m
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=160
HF_HUB_OFFLINE=1
TAVILY_API_KEY=
COOKIE_SECURE=false
```

Pour activer la recherche web, crée un compte Tavily, récupère ta clé API et
remplace la ligne vide `TAVILY_API_KEY=` dans `.env`. Ne colle jamais cette clé
dans `static/app.js`, dans GitHub ou dans un message partagé. Redémarre FastAPI
après avoir modifié `.env`. L'option « Ajouter des sources web vérifiées » est
alors activée dans le chat ; tu peux la décocher pour une question. Les résultats
reçus sont présentés sous forme de liens cliquables. Sans clé Tavily, le chatbot
continue à utiliser ses PDF et Ollama normalement.
Quand cette option est active, la question (et le contexte de la dernière question
pour une relance courte) sont envoyés à Tavily pour effectuer la recherche ; le
contenu des PDF n'est pas envoyé à ce service.

Tavily annonce actuellement 1 000 crédits API gratuits par mois sans carte
bancaire. Consulte [la page officielle des tarifs Tavily](https://www.tavily.com/pricing)
pour vérifier le quota et les conditions au moment de l'inscription.

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
ont besoin d'un cache OCR en français dans `index/ocr/`. `rag.py` vérifie que le
cache correspond toujours au PDF, puis indexe son texte avec le nom du document
et les numéros de page. Sans cache, les pages scannées restent ignorées. Les PDF
et caches OCR sont des données locales ignorées par Git. Le modèle d'embedding
multilingue est distinct
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
une question proposée ou écrire la tienne. Après la réponse, les sources PDF et
leurs pages ou les liens web apparaissent sous le message. Pour vérifier le
contexte, pose une question de suivi, par exemple « Peux-tu expliquer cela plus
simplement ? ». Le bouton « Nouvelle discussion » crée une conversation partagée
qui reste dans la liste après un rechargement.

La première réponse après le démarrage peut prendre plus de temps : Ollama doit
charger son modèle. Pendant la recherche, l'interface affiche une animation.
Après avoir ajouté un PDF, attends le message « Document prêt », puis pose une
question sur son contenu. Un PDF scanné peut nécessiter une reconnaissance de texte
(OCR), qui n'est pas encore incluse dans le projet.

## Faire un essai avec la famille sur le même Wi-Fi

Le chatbot peut tourner sur ton ordinateur et être ouvert depuis les téléphones
ou ordinateurs connectés au même réseau Wi-Fi. Ollama et les PDF restent sur ton
ordinateur ; les autres appareils utilisent seulement le navigateur. En mode
local seul, aucune clé API n'est requise. La recherche web facultative utilise le
quota Tavily configuré sur l'ordinateur hôte.

1. Ouvre PowerShell dans le dossier `formation-ia` et lance :

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\lancer_famille.ps1
   ```

   Ce réglage de stratégie ne vaut que pour cette fenêtre PowerShell.

2. Le script affiche une adresse locale, par exemple
   `http://192.168.1.7:8000/?v=tyson-ai-v1`. Ouvre cette adresse sur l'ordinateur
   hôte et transmets-la aux membres de la famille, qui doivent être sur le même
   Wi-Fi.
3. Si Windows affiche une demande de pare-feu, autorise Python sur les réseaux
   privés. Laisse la fenêtre PowerShell ouverte pendant l'essai ; `Ctrl+C` arrête
   le serveur.

Si le téléphone n'arrive pas à ouvrir la page et que Windows n'a pas affiché de
demande de pare-feu, vérifie que le Wi-Fi de la maison est défini comme réseau
privé dans **Paramètres > Réseau et Internet > Wi-Fi**. Puis ouvre PowerShell en
tant qu'administrateur et ajoute une règle limitée au port du chatbot et au réseau
local :

```powershell
New-NetFirewallRule -DisplayName "Tyson AI - essai famille TCP 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet
```

Les PDF ajoutés depuis un téléphone sont envoyés et enregistrés dans le dossier
`documents/` de l'ordinateur hôte ; ils deviennent disponibles aux autres
utilisateurs du chatbot. Le serveur dépend de cet ordinateur : s'il se met en
veille ou se déconnecte du Wi-Fi, le chatbot devient inaccessible. Pour un premier
essai, posez les questions à tour de rôle afin de ne pas ralentir le modèle local.
Chaque personne crée un compte. Le premier compte devient administrateur et les
suivants deviennent membres ; crée ton compte avant de partager l'adresse. Les
dossiers et discussions restent communs à tous les comptes. Garde le serveur sur
un réseau de confiance et ne l'expose pas directement à Internet.

## Tester les dossiers partagés et les sources web

1. Dans l'interface, clique sur `＋` à côté de « Dossiers », crée par exemple
   `Développement web`, puis sélectionne ce dossier.
2. Clique sur `＋` à côté de « Discussions », pose une question et attends la
   réponse. La discussion prend automatiquement le titre de ta première question.
3. Recharge la page : le dossier et la discussion doivent rester dans la barre
   latérale. Ouvre la discussion pour retrouver les messages et leurs sources.
4. L'espace étant commun au serveur, les mêmes dossiers et discussions seront
   visibles aux autres utilisateurs lorsqu'ils accéderont à cette application.
5. Pour la recherche web, configure `TAVILY_API_KEY` dans `.env`, redémarre le
   serveur et vérifie que la case « Ajouter des sources web » est active.
   Pose une question factuelle, puis ouvre un lien affiché sous la réponse.

## Créer les comptes et vérifier le journal

1. Redémarre FastAPI après la mise à jour. Sur la page d'accueil, crée ton compte
   avec un mot de passe d'au moins 10 caractères : le premier compte devient admin.
2. Pour simuler un collègue, déconnecte-toi et crée un second compte. Il doit voir
   les mêmes dossiers et discussions, mais pas le bouton **Journal**.
3. Reconnecte-toi avec le compte admin, pose une question et ouvre **Journal**.
   Une ligne doit afficher le compte, la réussite, la durée et les sources.
4. Pour voir un échec enregistré, arrête Ollama temporairement, pose une question,
   puis rouvre **Journal** : l'état doit être « Échec » avec un code d'erreur.
   Redémarre Ollama après cet essai.

L'inscription reste ouverte aux personnes qui ont accès au serveur. Sur le Wi-Fi,
crée le compte administrateur avant de partager l'adresse. Les mots de passe sont
stockés sous forme d'empreintes PBKDF2 avec sel individuel ; les sessions utilisent
un cookie HttpOnly valable 30 jours. Le journal est réservé au premier compte
administrateur et ne contient pas le contenu des échanges. Pour un hébergement
HTTPS, active `COOKIE_SECURE=true` ; sur le Wi-Fi local en HTTP, garde le serveur
sur un réseau de confiance.

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

- Si Ollama ne répond toujours pas après le démarrage automatique, démarre
  l'application Ollama manuellement et vérifie `http://127.0.0.1:11434/api/tags`.
- Si Ollama ne trouve pas `llama3.2:3b`, télécharge-le avec la commande indiquée
  dans la section Préparation.
- Si ChromaDB signale `DLL load failed while importing chromadb_rust_bindings`,
  installe le Microsoft Visual C++ Redistributable x64, puis redémarre VS Code.
