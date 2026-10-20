const form = document.querySelector("#chat-form");
const questionField = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const uploadButton = document.querySelector("#upload-button");
const pdfInput = document.querySelector("#pdf-file");
const newChatButton = document.querySelector("#new-chat");
const messages = document.querySelector("#messages");
const welcome = document.querySelector("#welcome");
const status = document.querySelector(".connection-state");
const statusText = document.querySelector("#status-text");

let historique = [];
let requestEnCours = false;

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

function ajouterMessage(role, texte, sources = [], options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${options.error ? " is-error" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "TOI" : "IA";

  const main = document.createElement("div");
  main.className = "message-main";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "Toi" : "Assistant documentaire";

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
    titre.textContent = sources.length === 1 ? "SOURCE DU DOCUMENT" : "SOURCES DES DOCUMENTS";
    sourceList.append(titre);

    for (const source of sources) {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = `${source.source}, page ${source.page}`;
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

  welcome?.remove();
  ajouterMessage("user", texteQuestion);
  questionField.value = "";
  questionField.style.height = "auto";
  requestEnCours = true;
  newChatButton.disabled = true;
  mettreAJourBoutons();
  afficherStatut("Recherche dans les documents…", "loading");
  const messageAttente = ajouterMessage("assistant", "", [], { loading: true });

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: texteQuestion, historique: historique.slice(-6) }),
    });
    const resultat = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof resultat.detail === "string" ? resultat.detail : "Le serveur n'a pas pu traiter la question.";
      throw new Error(detail);
    }

    messageAttente.remove();
    ajouterMessage("assistant", resultat.reponse, resultat.sources ?? []);
    historique.push(
      { role: "user", content: texteQuestion },
      { role: "assistant", content: resultat.reponse },
    );
    afficherStatut("Réponse prête");
  } catch (erreur) {
    messageAttente.remove();
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
    const response = await fetch("/documents", { method: "POST", body: donnees });
    const resultat = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof resultat.detail === "string"
        ? resultat.detail
        : "Le serveur n'a pas pu ajouter ce PDF.";
      throw new Error(detail);
    }

    const resume = resultat.chunks > 0
      ? `Document ajouté : ${resultat.source}\n${resultat.pages} page(s), ${resultat.chunks} passage(s) indexé(s). Tu peux maintenant poser une question dessus.`
      : `Document ajouté : ${resultat.source}\nAucun texte sélectionnable n'a été trouvé. Ce PDF est peut-être scanné.`;
    ajouterMessage("assistant", resume);
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
  questionField.style.height = `${Math.min(questionField.scrollHeight, 130)}px`;
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

newChatButton.addEventListener("click", () => {
  historique = [];
  messages.replaceChildren(welcome);
  questionField.value = "";
  questionField.style.height = "auto";
  afficherStatut("Nouvelle discussion");
  mettreAJourBoutons();
  questionField.focus();
});
