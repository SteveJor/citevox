"""Recrée la base SQLite avec des données de test : python donnees_test.py"""
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

DOSSIER = os.path.dirname(os.path.abspath(__file__))
# Mot de passe des comptes de démonstration (modifiable par la variable MDP_DEMO)
MOT_DE_PASSE_DEMO = os.environ.get("MDP_DEMO", "Citevox#2026")
MINIMUM = {"categories": 5, "quartiers": 12, "signalements": 200, "interventions": 250, "agents": 8}

CATEGORIES = [("Voirie", "voirie", "Voirie et travaux"), ("Ordures", "ordures", "Propreté urbaine"),
              ("Éclairage", "eclairage", "Éclairage public"), ("Eau", "eau", "Eau et assainissement"),
              ("Autre", "autre", "Services généraux")]
QUARTIERS = ["Akwa", "Bonanjo", "Bonapriso", "Bonamoussadi", "Deido", "Bali",
             "New Bell", "Makepe", "Logbessou", "Kotto", "Ndokotti", "Bepanda"]
AGENTS = [("Paul Essomba", "Voirie et travaux", "voirie1"), ("Marie Tchoumi", "Voirie et travaux", "voirie2"),
          ("Joseph Nkeng", "Propreté urbaine", "proprete1"), ("Aline Mbarga", "Propreté urbaine", "proprete2"),
          ("Samuel Fotso", "Éclairage public", "eclairage1"), ("Carine Ndjock", "Éclairage public", "eclairage2"),
          ("Éric Kamga", "Eau et assainissement", "eau1"), ("Nadine Ewane", "Services généraux", "general1")]
DESCRIPTIONS = [  # une liste par catégorie, dans le même ordre que CATEGORIES
    ["Un nid-de-poule profond ralentit la circulation et menace les motos.",
     "La chaussée s'est effondrée après les dernières pluies, danger pour les piétons."],
    ["Un dépôt d'ordures sauvage s'étend sur le trottoir depuis une semaine.",
     "Le bac à ordures déborde et dégage une forte odeur."],
    ["Le lampadaire est éteint depuis plusieurs jours, la rue est très sombre.",
     "Plusieurs lampadaires clignotent en permanence sur cette avenue."],
    ["Le caniveau est bouché et l'eau stagne devant les habitations.",
     "Une canalisation fuit et l'eau coule dans la rue en continu."],
    ["Un panneau de signalisation est tombé au carrefour.",
     "Un arbre menace de tomber sur la route après la tempête."]]
REPERES = ["Près du marché", "Face à l'école publique", "Carrefour de la pharmacie",
           "Derrière la chefferie", "À côté de la station-service", "Devant le centre de santé"]
MOTIFS = ["Doublon d'un signalement déjà traité.", "Le problème relève d'une propriété privée.",
          "Localisation introuvable malgré la visite de l'équipe."]


def horodatage(date):
    return date.strftime("%Y-%m-%d %H:%M:%S")


def remplir(chemin):
    """Recrée la base `chemin` et la remplit. Retourne le nombre de lignes par table."""
    random.seed(13)
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
    db = sqlite3.connect(chemin)
    db.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(DOSSIER, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())  # supprime puis recrée les tables : pas de doublons
    db.executemany("INSERT INTO categories (nom, slug, service) VALUES (?, ?, ?)", CATEGORIES)
    db.executemany("INSERT INTO quartiers (nom) VALUES (?)", [(q,) for q in QUARTIERS])
    empreinte = generate_password_hash(MOT_DE_PASSE_DEMO)
    db.executemany("INSERT INTO agents (nom, service, login, empreinte) VALUES (?, ?, ?, ?)",
                   [(nom, service, login, empreinte) for nom, service, login in AGENTS])

    plan = ["nouveau"] * 40 + ["en_cours"] * 50 + ["resolu"] * 90 + ["rejete"] * 20
    random.shuffle(plan)
    for statut in plan:
        n = random.randrange(len(CATEGORIES))
        service = CATEGORIES[n][2]
        agents = [i + 1 for i, a in enumerate(AGENTS) if a[1] == service]
        delai = random.randint(1, 14)  # durée de traitement des dossiers résolus
        if statut == "nouveau":        # beaucoup de dossiers non traités depuis plus de 7 jours
            age = random.randint(8, 90) if random.random() < 0.65 else random.randint(0, 6)
        elif statut == "resolu":
            age = random.randint(delai + 1, 90)
        else:
            age = random.randint(5, 80)
        cree = maintenant - timedelta(days=age, hours=random.randint(0, 23))
        cur = db.execute(
            "INSERT INTO signalements (code_suivi, categorie_id, quartier_id, description, reperage,"
            " telephone, statut, cree_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"CV-{random.getrandbits(40):010X}", n + 1, random.randint(1, len(QUARTIERS)),
             random.choice(DESCRIPTIONS[n]), random.choice(REPERES),
             f"69900{random.randint(0, 9999):04d}", statut, horodatage(cree)))
        etapes = []  # historique cohérent avec le statut final du dossier
        if statut == "en_cours":
            etapes = [(cree + timedelta(days=1), "en_cours", "Équipe envoyée sur place pour évaluer le problème.")]
            if random.random() < 0.3:
                etapes.append((cree + timedelta(days=3), "en_cours", "Matériel commandé, travaux programmés."))
        elif statut == "resolu":
            etapes = [(cree + timedelta(days=delai * 0.4), "en_cours", "Intervention en cours sur le site."),
                      (cree + timedelta(days=delai), "resolu", "Problème résolu, intervention terminée.")]
        elif statut == "rejete":
            etapes = [(cree + timedelta(days=random.randint(1, 3)), "rejete", random.choice(MOTIFS))]
        for date, nouveau_statut, commentaire in etapes:
            db.execute("INSERT INTO interventions (signalement_id, agent_id, date_intervention, commentaire,"
                       " nouveau_statut) VALUES (?, ?, ?, ?, ?)",
                       (cur.lastrowid, random.choice(agents), horodatage(date), commentaire, nouveau_statut))
    db.commit()
    compteurs = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in MINIMUM}
    db.close()
    return compteurs


if __name__ == "__main__":
    chemin = os.path.join(DOSSIER, "projet.db")
    compteurs = remplir(chemin)
    for table, minimum in MINIMUM.items():
        print(f"{table:14}{compteurs[table]:5}  (minimum {minimum}) "
              f"{'OK' if compteurs[table] >= minimum else 'INSUFFISANT'}")
    with sqlite3.connect(chemin) as db, open(os.path.join(DOSSIER, "export_projet.sql"), "w", encoding="utf-8") as f:
        f.write("\n".join(db.iterdump()))
    print("Export écrit dans export_projet.sql")
