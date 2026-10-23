const form = document.querySelector("#chat-form");
const questionField = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const uploadButton = document.querySelector("#upload-button");
const pdfInput = document.querySelector("#pdf-file");
const newChatButton = document.querySelector("#new-chat");
const messages = document.querySelector("#messages");
const welcome = document.querySelector("#welcome");
const welcomeTitle = document.querySelector("#welcome-title");
const folderList = document.querySelector("#folder-list");
const conversationList = document.querySelector("#conversation-list");
const newFolderButton = document.querySelector("#new-folder");
const sidebarNewChatButton = document.querySelector("#sidebar-new-chat");
const sidebar = document.querySelector("#workspace-sidebar");
const sidebarToggle = document.querySelector("#toggle-sidebar");
const moveConversation = document.querySelector("#move-conversation");
const webSearchToggle = document.querySelector("#web-search");
const webSearchStatus = document.querySelector("#web-search-status");
const status = document.querySelector(".connection-state");
const statusText = document.querySelector("#status-text");
const authScreen = document.querySelector("#auth-screen");
const appShell = document.querySelector("#app-shell");
const authForm = document.querySelector("#auth-form");
const authUsername = document.querySelector("#auth-username");
const authPassword = document.querySelector("#auth-password");
const authTitle = document.querySelector("#auth-title");
const authDescription = document.querySelector("#auth-description");
const authMessage = document.querySelector("#auth-message");
const authSubmit = document.querySelector("#auth-submit");
const authSwitch = document.querySelector("#auth-switch");
const authSwitchPrompt = document.querySelector("#auth-switch-prompt");
const authFirstAccount = document.querySelector("#auth-first-account");
const accountName = document.querySelector("#account-name");
const logoutButton = document.querySelector("#logout");
const openJournalButton = document.querySelector("#open-journal");
const journalDialog = document.querySelector("#journal-dialog");
const closeJournalButton = document.querySelector("#close-journal");
const journalRows = document.querySelector("#journal-rows");
const journalEmpty = document.querySelector("#journal-empty");
const journalError = document.querySelector("#journal-error");

let historique = [];
let requestEnCours = false;
let espacePartage = { dossiers: [], sans_dossier: [] };
let filtreDossier = "tous";
let discussionActive = null;
let modeAuthentification = "login";
let utilisateurActuel = null;

function afficherAccueilAleatoire() {
  const accueils = [
    "Bienvenue, agent X ! De quel sujet veux-tu parler aujourd’hui ?",
    "Nouvelle session, agent X. Quelle notion veux-tu éclaircir ?",
    "Ravi de te retrouver, agent X. Quel défi veux-tu relever aujourd’hui ?",
    "Briefing prêt, agent X. Qu’aimerais-tu apprendre ou construire ?",
    "Agent X, quelle idée veux-tu transformer en code aujourd’hui ?",
    "Bienvenue dans ton espace d’apprentissage, agent X. On commence par quoi ?",
  ];

  let dernierIndex = -1;
  try {
    dernierIndex = Number.parseInt(localStorage.getItem("tyson-ai-accueil-index"), 10);
    if (!Number.isInteger(dernierIndex)) dernierIndex = -1;
  } catch {
    // Le stockage peut être bloqué dans certains modes de navigation privée.
  }

  const choixPossibles = accueils
    .map((_, index) => index)
    .filter((index) => index !== dernierIndex);
  const nouvelIndex = choixPossibles[Math.floor(Math.random() * choixPossibles.length)];
  const nomAgent = utilisateurActuel?.nom_utilisateur || "X";
  welcomeTitle.textContent = accueils[nouvelIndex]
    .replaceAll("agent X", `agent ${nomAgent}`)
    .replaceAll("Agent X", `Agent ${nomAgent}`);

  try {
    localStorage.setItem("tyson-ai-accueil-index", String(nouvelIndex));
  } catch {
    // L’accueil reste aléatoire même si le navigateur refuse de mémoriser le choix.
  }
}

function mettreAJourBoutons() {
  sendButton.disabled = requestEnCours || !questionField.value.trim();
  uploadButton.disabled = requestEnCours;
}

function afficherStatut(texte, etat = "") {
  statusText.textContent = texte;
  status.classList.toggle("is-loading", etat === "loading");
  status.classList.toggle("is-error", etat === "error");
}

function faireDefilerEnBas() {
  messages.scrollTop = messages.scrollHeight;
}

async function appelerAPI(url, options = {}) {
  const response = await fetch(url, options);
  const resultat = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !url.startsWith("/api/auth/")) {
      afficherEcranConnexion("Ta session a expiré. Connecte-toi à nouveau.");
    }
    throw new Error(typeof resultat.detail === "string" ? resultat.detail : "La demande n'a pas abouti.");
  }
  return resultat;
}

function afficherEcranConnexion(message = "") {
  utilisateurActuel = null;
  appShell.hidden = true;
  authScreen.hidden = false;
  authMessage.textContent = message;
  authUsername.focus();
}

async function afficherApplication(utilisateur) {
  utilisateurActuel = utilisateur;
  accountName.textContent = utilisateur.nom_utilisateur;
  openJournalButton.hidden = utilisateur.role !== "admin";
  authScreen.hidden = true;
  appShell.hidden = false;
  afficherAccueilAleatoire();

  try {
    await actualiserEspace();
  } catch (erreur) {
    afficherStatut(`Les dossiers partagés ne sont pas disponibles : ${erreur.message}`, "error");
  }

  try {
    const configuration = await appelerAPI("/api/config");
    webSearchToggle.disabled = !configuration.recherche_web_disponible;
    webSearchToggle.checked = configuration.recherche_web_disponible;
    webSearchStatus.textContent = configuration.recherche_web_disponible
      ? "Tavily actif · une recherche par question"
      : "Clé TAVILY_API_KEY requise dans .env";
  } catch {
    webSearchStatus.textContent = "Recherche web indisponible";
  }
}

function mettreAJourModeAuthentification() {
  const inscription = modeAuthentification === "register";
  authTitle.textContent = inscription ? "Créer ton compte." : "Content de te revoir.";
  authDescription.textContent = inscription
    ? "Choisis un nom d’utilisateur et un mot de passe pour rejoindre l’espace partagé."
    : "Connecte-toi pour retrouver les dossiers et discussions partagés.";
  authSubmit.textContent = inscription ? "Créer mon compte" : "Se connecter";
  authSwitchPrompt.textContent = inscription ? "Tu as déjà un compte ?" : "Pas encore de compte ?";
  authSwitch.textContent = inscription ? "Se connecter" : "Créer un compte";
  authFirstAccount.hidden = !inscription;
  authPassword.autocomplete = inscription ? "new-password" : "current-password";
  authMessage.textContent = "";
}

function fermerMenuMobile() {
  sidebar.classList.remove("is-open");
  sidebarToggle.setAttribute("aria-expanded", "false");
}

function creerBoutonDossier(id, nom, compte, actif) {
  const bouton = document.createElement("button");
  bouton.className = `folder-row${actif ? " is-active" : ""}`;
  bouton.type = "button";
  bouton.setAttribute("aria-pressed", String(actif));
  const icone = document.createElement("span");
  icone.className = "folder-icon";
  icone.setAttribute("aria-hidden", "true");
  icone.textContent = id === "tous" ? "◫" : "▱";
  const libelle = document.createElement("span");
  libelle.textContent = nom;
  const nombre = document.createElement("span");
  nombre.className = "folder-count";
  nombre.textContent = String(compte);
  bouton.append(icone, libelle, nombre);
  bouton.addEventListener("click", () => {
    filtreDossier = String(id);
    afficherEspace();
  });
  return bouton;
}

function afficherEspace() {
  folderList.replaceChildren();
  const toutesLesDiscussions = [
    ...espacePartage.sans_dossier,
    ...espacePartage.dossiers.flatMap((dossier) => dossier.discussions),
  ];
  folderList.append(
    creerBoutonDossier("tous", "Tous les dossiers", toutesLesDiscussions.length, filtreDossier === "tous"),
    creerBoutonDossier("aucun", "Sans dossier", espacePartage.sans_dossier.length, filtreDossier === "aucun"),
  );
  for (const dossier of espacePartage.dossiers) {
    folderList.append(
      creerBoutonDossier(dossier.id, dossier.nom, dossier.discussions.length, filtreDossier === String(dossier.id)),
    );
  }

  const discussions = filtreDossier === "tous"
    ? toutesLesDiscussions.sort((a, b) => b.modifie_le - a.modifie_le)
    : filtreDossier === "aucun"
      ? espacePartage.sans_dossier
      : espacePartage.dossiers.find((dossier) => String(dossier.id) === filtreDossier)?.discussions ?? [];
  conversationList.replaceChildren();
  if (discussions.length === 0) {
    const vide = document.createElement("p");
    vide.className = "empty-list";
    vide.textContent = "Aucune discussion ici. Utilise + pour en créer une.";
    conversationList.append(vide);
  } else {
    for (const discussion of discussions) {
      const bouton = document.createElement("button");
      bouton.className = `conversation-row${discussion.id === discussionActive ? " is-active" : ""}`;
      bouton.type = "button";
      bouton.title = discussion.titre;
      const icone = document.createElement("span");
      icone.className = "conversation-icon";
      icone.setAttribute("aria-hidden", "true");
      icone.textContent = "◌";
      const titre = document.createElement("span");
      titre.textContent = discussion.titre;
      bouton.append(icone, titre);
      bouton.addEventListener("click", () => ouvrirDiscussion(discussion.id));
      conversationList.append(bouton);
    }
  }

  const dossierActif = espacePartage.dossiers.find((dossier) => String(dossier.id) === filtreDossier);
  const dossierDeLaDiscussion = espacePartage.dossiers.find((dossier) =>
    dossier.discussions.some((discussion) => discussion.id === discussionActive));
  moveConversation.replaceChildren();
  const optionSansDossier = document.createElement("option");
  optionSansDossier.value = "";
  optionSansDossier.textContent = "Sans dossier";
  moveConversation.append(optionSansDossier);
  for (const dossier of espacePartage.dossiers) {
    const option = document.createElement("option");
    option.value = String(dossier.id);
    option.textContent = dossier.nom;
    moveConversation.append(option);
  }
  moveConversation.disabled = !discussionActive;
  if (discussionActive && dossierDeLaDiscussion) {
    moveConversation.value = String(dossierDeLaDiscussion.id);
  } else {
    moveConversation.value = "";
  }
  if (dossierActif && filtreDossier === "tous") moveConversation.value = "";
}

async function actualiserEspace() {
  espacePartage = await appelerAPI("/api/espace");
  afficherEspace();
}

function afficherDiscussionVide() {
  historique = [];
  messages.replaceChildren(welcome);
  questionField.value = "";
  questionField.style.height = "auto";
  afficherStatut("Nouvelle discussion");
  mettreAJourBoutons();
}

async function creerDiscussion(dossierId = null) {
  const discussion = await appelerAPI("/api/discussions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dossier_id: dossierId }),
  });
  discussionActive = discussion.id;
  afficherDiscussionVide();
  await actualiserEspace();
  fermerMenuMobile();
  return discussion;
}

async function ouvrirDiscussion(identifiant) {
  try {
    const discussion = await appelerAPI(`/api/discussions/${encodeURIComponent(identifiant)}`);
    discussionActive = discussion.id;
    historique = discussion.messages.map((message) => ({ role: message.role, content: message.content }));
    messages.replaceChildren();
    if (discussion.messages.length === 0) {
      messages.append(welcome);
    } else {
      for (const message of discussion.messages) {
        ajouterMessage(message.role, message.content, message.sources ?? []);
      }
    }
    afficherEspace();
    afficherStatut(`Discussion : ${discussion.titre}`);
    fermerMenuMobile();
    questionField.focus();
  } catch (erreur) {
    ajouterMessage("assistant", erreur.message, [], { error: true });
    afficherStatut("Impossible d’ouvrir la discussion", "error");
  }
}

function ajouterMessage(role, texte, sources = [], options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${options.error ? " is-error" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "MEM" : "IA";

  const main = document.createElement("div");
  main.className = "message-main";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "Membre du groupe" : "Tuteur pédagogique";

  const content = document.createElement("div");
  content.className = "message-content";
  if (options.loading) {
    content.setAttribute("aria-label", "L'assistant prépare une réponse");
    const typing = document.createElement("span");
    typing.className = "typing";
    typing.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) {
      typing.append(document.createElement("span"));
    }
    content.append(typing);
  } else {
    content.textContent = texte;
  }

  main.append(meta, content);

  if (sources.length > 0) {
    const sourceList = document.createElement("div");
    sourceList.className = "source-list";
    const titre = document.createElement("div");
    titre.className = "source-heading";
    const sourcesWeb = sources.filter((source) => source.url).length;
    titre.textContent = sourcesWeb === sources.length
      ? (sources.length === 1 ? "SOURCE WEB" : "SOURCES WEB")
      : (sources.length === 1 ? "SOURCE DU DOCUMENT" : "SOURCES DES DOCUMENTS");
    sourceList.append(titre);

    for (const source of sources) {
      const chip = source.url ? document.createElement("a") : document.createElement("span");
      chip.className = "source-chip";
      if (source.url) {
        chip.href = source.url;
        chip.target = "_blank";
        chip.rel = "noopener noreferrer";
        chip.textContent = source.title || source.url;
      } else {
        chip.textContent = `${source.source}, page ${source.page}`;
      }
      sourceList.append(chip);
    }
    main.append(sourceList);
  }

  article.append(avatar, main);
  messages.append(article);
  faireDefilerEnBas();
  return article;
}

async function envoyerQuestion(question) {
  const texteQuestion = question.trim();
  if (!texteQuestion || requestEnCours) return;

  requestEnCours = true;
  newChatButton.disabled = true;
  mettreAJourBoutons();
  afficherStatut("Recherche dans tes supports de cours…", "loading");
  let messageAttente = null;

  try {
    if (!discussionActive) {
      const dossierId = /^\d+$/.test(filtreDossier) ? Number(filtreDossier) : null;
      const discussion = await creerDiscussion(dossierId);
      discussionActive = discussion.id;
    }
    welcome?.remove();
    ajouterMessage("user", texteQuestion);
    questionField.value = "";
    questionField.style.height = "auto";
    messageAttente = ajouterMessage("assistant", "", [], { loading: true });

    const resultat = await appelerAPI("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: texteQuestion,
        historique: historique.slice(-6),
        conversation_id: discussionActive,
        rechercher_sur_web: webSearchToggle.checked,
      }),
    });

    messageAttente.remove();
    ajouterMessage("assistant", resultat.reponse, resultat.sources ?? []);
    historique.push(
      { role: "user", content: texteQuestion },
      { role: "assistant", content: resultat.reponse },
    );
    await actualiserEspace();
    afficherStatut("Réponse prête");
  } catch (erreur) {
    messageAttente?.remove();
    const detail = erreur instanceof TypeError
      ? "Impossible de joindre le serveur. Vérifie que FastAPI est démarré dans le terminal."
      : erreur.message;
    ajouterMessage("assistant", detail, [], { error: true });
    afficherStatut("La réponse n’a pas pu être chargée", "error");
  } finally {
    requestEnCours = false;
    newChatButton.disabled = false;
    mettreAJourBoutons();
    questionField.focus();
  }
}

async function importerPDF(fichier) {
  if (!fichier || requestEnCours) return;

  welcome?.remove();
  requestEnCours = true;
  newChatButton.disabled = true;
  mettreAJourBoutons();
  afficherStatut(`Indexation de ${fichier.name}…`, "loading");

  const donnees = new FormData();
  donnees.append("fichier", fichier);

  try {
    const resultat = await appelerAPI("/documents", { method: "POST", body: donnees });

    const resume = resultat.chunks > 0
      ? `Document ajouté : ${resultat.source}\n${resultat.pages} page(s), ${resultat.chunks} passage(s) indexé(s). Tu peux maintenant poser une question dessus.`
      : `Document ajouté : ${resultat.source}\nAucun texte sélectionnable n'a été trouvé. Ce PDF est peut-être scanné.`;
    ajouterMessage("assistant", resume);
    await actualiserEspace();
    afficherStatut("Document prêt");
  } catch (erreur) {
    const detail = erreur instanceof TypeError
      ? "Impossible de joindre le serveur. Vérifie que FastAPI est démarré dans le terminal."
      : erreur.message;
    ajouterMessage("assistant", detail, [], { error: true });
    afficherStatut("Le PDF n’a pas pu être ajouté", "error");
  } finally {
    requestEnCours = false;
    newChatButton.disabled = false;
    pdfInput.value = "";
    mettreAJourBoutons();
    questionField.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  envoyerQuestion(questionField.value);
});

uploadButton.addEventListener("click", () => pdfInput.click());

pdfInput.addEventListener("change", () => {
  const fichier = pdfInput.files?.[0];
  importerPDF(fichier);
});

questionField.addEventListener("input", () => {
  questionField.style.height = "auto";
  questionField.style.height = `${Math.min(questionField.scrollHeight, 150)}px`;
  mettreAJourBoutons();
});

questionField.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((suggestion) => {
  suggestion.addEventListener("click", () => envoyerQuestion(suggestion.dataset.question));
});

async function nouvelleDiscussionDepuisInterface() {
  if (requestEnCours) return;
  try {
    const dossierId = /^\d+$/.test(filtreDossier) ? Number(filtreDossier) : null;
    await creerDiscussion(dossierId);
    questionField.focus();
  } catch (erreur) {
    afficherStatut(erreur.message, "error");
  }
}

newChatButton.addEventListener("click", nouvelleDiscussionDepuisInterface);
sidebarNewChatButton.addEventListener("click", nouvelleDiscussionDepuisInterface);

newFolderButton.addEventListener("click", async () => {
  const nom = window.prompt("Quel nom donner à ce dossier partagé ?")?.trim();
  if (!nom) return;
  try {
    const dossier = await appelerAPI("/api/dossiers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom }),
    });
    filtreDossier = String(dossier.id);
    await actualiserEspace();
    afficherStatut(`Dossier « ${dossier.nom} » créé`);
  } catch (erreur) {
    afficherStatut(erreur.message, "error");
  }
});

moveConversation.addEventListener("change", async () => {
  if (!discussionActive) return;
  try {
    await appelerAPI(`/api/discussions/${encodeURIComponent(discussionActive)}/dossier`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dossier_id: moveConversation.value ? Number(moveConversation.value) : null }),
    });
    await actualiserEspace();
    afficherStatut("Discussion rangée");
  } catch (erreur) {
    afficherStatut(erreur.message, "error");
  }
});

sidebarToggle.addEventListener("click", () => {
  const ouvert = sidebar.classList.toggle("is-open");
  sidebarToggle.setAttribute("aria-expanded", String(ouvert));
});

authSwitch.addEventListener("click", () => {
  modeAuthentification = modeAuthentification === "login" ? "register" : "login";
  mettreAJourModeAuthentification();
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authSubmit.disabled = true;
  authMessage.textContent = "";
  const endpoint = modeAuthentification === "register" ? "/api/auth/register" : "/api/auth/login";
  try {
    const resultat = await appelerAPI(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nom_utilisateur: authUsername.value.trim(),
        mot_de_passe: authPassword.value,
      }),
    });
    authPassword.value = "";
    await afficherApplication(resultat.utilisateur);
  } catch (erreur) {
    authMessage.textContent = erreur.message;
  } finally {
    authSubmit.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await appelerAPI("/api/auth/logout", { method: "POST" });
  } catch {
    // L'écran de connexion reste accessible même si la session a déjà expiré.
  } finally {
    authPassword.value = "";
    modeAuthentification = "login";
    mettreAJourModeAuthentification();
    afficherEcranConnexion("Tu es déconnecté.");
  }
});

async function chargerJournal() {
  journalError.textContent = "";
  journalRows.replaceChildren();
  journalEmpty.hidden = true;
  try {
    const resultat = await appelerAPI("/api/admin/journal?limite=100");
    const evenements = resultat.evenements ?? [];
    journalEmpty.hidden = evenements.length > 0;
    for (const evenement of evenements) {
      const ligne = document.createElement("tr");
      const date = new Date(evenement.cree_le * 1000).toLocaleString("fr-FR");
      const duree = evenement.duree_ms >= 1000
        ? `${(evenement.duree_ms / 1000).toFixed(1)} s`
        : `${evenement.duree_ms} ms`;
      const sources = `${evenement.sources_pdf} PDF · ${evenement.sources_web} web`;
      const valeurs = [
        date,
        evenement.nom_utilisateur,
        evenement.statut === "reussite" ? "Réussie" : "Échec",
        evenement.code_erreur ?? "—",
        duree,
        sources,
      ];
      for (const valeur of valeurs) {
        const cellule = document.createElement("td");
        cellule.textContent = String(valeur);
        ligne.append(cellule);
      }
      const resultatCellule = ligne.children[2];
      resultatCellule.className = evenement.statut === "reussite"
        ? "journal-result-success"
        : "journal-result-failure";
      journalRows.append(ligne);
    }
  } catch (erreur) {
    journalError.textContent = erreur.message;
  }
}

openJournalButton.addEventListener("click", async () => {
  journalDialog.showModal();
  await chargerJournal();
});

closeJournalButton.addEventListener("click", () => journalDialog.close());
journalDialog.addEventListener("click", (event) => {
  if (event.target === journalDialog) journalDialog.close();
});

async function demarrerInterface() {
  try {
    const resultat = await appelerAPI("/api/auth/me");
    await afficherApplication(resultat.utilisateur);
  } catch (erreur) {
    afficherEcranConnexion(erreur instanceof TypeError
      ? "Impossible de joindre l’API. Vérifie que FastAPI est démarré."
      : "Connecte-toi ou crée un compte pour continuer.");
  }
}

mettreAJourModeAuthentification();
demarrerInterface();
