const bouton = document.querySelector("#bouton-menu");
const menu = document.querySelector("#menu");
bouton.addEventListener("click", () =>{
    const ouvert = menu.classList.toggle('ouvert');
    bouton.setAttribute("aria-expanded", ouvert);
});

const zone = document.querySelector("#derniers");

async function chargerDerniers() {
    try {
        const reponse = await fetch(zone.dataset.api + "?limite=4");
        if (!reponse.ok) throw new Error("Erreur " + reponse.status);
        const donnees = await reponse.json();
        if (donnees.signalements.length === 0) {
            zone.textContent = "Aucun signalement pour le moment.";
            return;
        }
        const liste = document.createElement("ul");
        for (const s of donnees.signalements) {
            const li = document.createElement("li");
            const lien = document.createElement("a");
            lien.href = zone.dataset.suivi + "?code=" + encodeURIComponent(s.code_suivi);
            lien.textContent = `${s.categorie} à ${s.quartier} (${s.statut_libelle})`;
            li.appendChild(lien);
            liste.appendChild(li);
        }
        zone.replaceChildren(liste);
    } catch (e) {
        zone.textContent = "Impossible de charger les signalements pour le moment.";
    }
}

if (zone) chargerDerniers();