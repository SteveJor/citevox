// Formulaire de signalement : aperçu de la photo et vérifications avant l'envoi
const form = document.querySelector("#form-signalement");
const erreur = document.querySelector("#erreur");
const apercu = document.querySelector("#apercu");
const TAILLE_MAX = 2 * 1024 * 1024; // 2 Mo

function erreurPhoto() {
  const fichier = form.photo.files[0];
  if (!fichier) return "Photo : ajoutez une photo du problème.";
  if (!["image/jpeg", "image/png"].includes(fichier.type)) return "Photo : formats acceptés .jpg, .jpeg et .png.";
  if (fichier.size >= TAILLE_MAX) return "Photo : le fichier doit faire moins de 2 Mo.";
  return "";
}

form.photo.addEventListener("change", () => {
  const message = erreurPhoto();
  erreur.textContent = message;
  apercu.replaceChildren();
  if (message) {
    form.photo.value = ""; // on retire le fichier refusé
  } else if (form.photo.files[0]) {
    const img = document.createElement("img");
    img.alt = "Aperçu de la photo choisie";
    img.src = URL.createObjectURL(form.photo.files[0]);
    apercu.appendChild(img);
  }
});

form.addEventListener("submit", (evenement) => {
  const messages = [];
  if (form.description.value.trim().length < 20) messages.push("La description doit faire au moins 20 caractères.");
  if (!/^6\d{8}$/.test(form.telephone.value.replace(/\s/g, ""))) messages.push("Téléphone invalide : 9 chiffres commençant par 6.");
  if (erreurPhoto()) messages.push(erreurPhoto());
  if (messages.length > 0) {
    evenement.preventDefault(); // bloque l'envoi
    erreur.textContent = messages.join(" ");
  }
});
