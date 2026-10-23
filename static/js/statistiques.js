const section = document.querySelector("#statistiques");

function barres(selecteur, lignes) {
    const zone = document.querySelector(selecteur);
    const max = Math.max(1, ...lignes.map((l) => l.valeur || 0));
    zone.replaceChildren();
    for (const l of lignes) {
        const ligne = document.createElement("div");
        ligne.className = "barre";
        const nom = document.createElement("span");
        nom.textContent = l.nom;
        const jauge = document.createElement("span");
        jauge.className = "jauge";
        const rempli = document.createElement("span");
        rempli.style.width = (100 * (l.valeur || 0)) / max + "%";
        jauge.appendChild(rempli);
        const valeur = document.createElement("strong");
        valeur.textContent = l.valeur === null ? "n/a" : l.valeur;
        ligne.append(nom, jauge, valeur);
        zone.appendChild(ligne);
    }
}

function tableau(selecteur, entetes, lignes) {
    const table = document.createElement("table");
    const tete = table.createTHead().insertRow();
    for (const e of entetes) {
        const th = document.createElement("th");
        th.scope = "col";
        th.textContent = e;
        tete.appendChild(th);
    }
    const corps = table.createTBody();
    for (const ligne of lignes) {
        const tr = corps.insertRow();
        for (const cellule of ligne) tr.insertCell().textContent = cellule;
    }
    document.querySelector(selecteur).replaceChildren(table);
}

async function charger() {
    try {
        const reponse = await fetch(section.dataset.api);
        if (!reponse.ok) throw new Error("Erreur " + reponse.status);
        const d = await reponse.json();
        barres("#stat-categories", d.par_categorie.map((x) => ({ nom: x.nom, valeur: x.nombre })));
        barres("#stat-quartiers", d.par_quartier.map((x) => ({ nom: x.nom, valeur: x.nombre })));
        barres("#stat-delais", d.delai_par_service.map((x) => ({ nom: x.service, valeur: x.jours })));
        barres("#stat-semaines", d.par_semaine.map((x) => ({ nom: "Sem. du " + x.semaine, valeur: x.nombre })));
        tableau("#stat-croise", ["Quartier", ...d.croise.categories], d.croise.lignes.map((l) => [l.quartier, ...l.valeurs]));
        document.querySelector("#nb-non-traites").textContent = d.non_traites.nombre;
        tableau("#stat-non-traites", ["Code", "Catégorie", "Quartier", "Jours d'attente"],
            d.non_traites.exemples.map((x) => [x.code_suivi, x.categorie, x.quartier, x.jours]));
    } catch (e) {
        section.querySelector("h2").insertAdjacentText("afterend", "Impossible de charger les statistiques.");
    }
}

charger();
