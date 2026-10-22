-- CITEVOX : structure de la base SQLite (Projet 13)
DROP TABLE IF EXISTS interventions;
DROP TABLE IF EXISTS signalements;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS quartiers;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,          -- nom des images : images/categories/<slug>.jpg
    service TEXT NOT NULL               -- service responsable
);

CREATE TABLE quartiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE
);

CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    service TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    empreinte TEXT NOT NULL             -- empreinte du mot de passe, jamais le mot de passe
);

CREATE TABLE signalements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_suivi TEXT NOT NULL UNIQUE,
    categorie_id INTEGER NOT NULL REFERENCES categories(id),
    quartier_id INTEGER NOT NULL REFERENCES quartiers(id),
    description TEXT NOT NULL CHECK (length(description) >= 20),
    reperage TEXT NOT NULL,
    telephone TEXT NOT NULL CHECK (length(telephone) = 9),
    photo TEXT,                         -- nom généré par le serveur (facultatif)
    statut TEXT NOT NULL DEFAULT 'nouveau'
        CHECK (statut IN ('nouveau', 'en_cours', 'resolu', 'rejete')),
    cree_le TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP   -- UTC
);

CREATE TABLE interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signalement_id INTEGER NOT NULL REFERENCES signalements(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    date_intervention TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    commentaire TEXT NOT NULL,          -- pour un rejet : le motif
    nouveau_statut TEXT NOT NULL CHECK (nouveau_statut IN ('en_cours', 'resolu', 'rejete'))
);

CREATE INDEX idx_signalements_date ON signalements(cree_le);
CREATE INDEX idx_signalements_filtres ON signalements(statut, categorie_id, quartier_id);
CREATE INDEX idx_interventions_signalement ON interventions(signalement_id);
