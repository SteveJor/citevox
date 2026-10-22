"""CITEVOX : signalement citoyen des problèmes urbains (Projet 13)."""
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

DOSSIER = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.update(
    DATABASE=os.path.join(DOSSIER, "projet.db"),
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),  # jamais écrite dans le code
    MAX_CONTENT_LENGTH=3 * 1024 * 1024,  # taille maximale d'une requête
    SESSION_COOKIE_SAMESITE="Lax",
)
STATUTS = {"nouveau": "Nouveau", "en_cours": "En cours", "resolu": "Résolu", "rejete": "Rejeté"}
MESSAGES = {400: "Requête invalide", 403: "Accès interdit", 404: "Page introuvable",
            405: "Méthode non autorisée", 413: "Fichier trop volumineux", 500: "Erreur du serveur"}
TAILLE_PHOTO_MAX = 2 * 1024 * 1024  # 2 Mo
SIGNATURES = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}  # début réel d'un JPEG / d'un PNG


# ------------------------------ Base de données ------------------------------
def get_db():
    """Une connexion par requête, avec les clés étrangères activées."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def fermer_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def requete(sql, params=(), un=False):
    """SELECT paramétré (valeurs toujours passées par des ?)."""
    curseur = get_db().execute(sql, params)
    return curseur.fetchone() if un else curseur.fetchall()


def listes():
    return {"categories": requete("SELECT * FROM categories ORDER BY id"),
            "quartiers": requete("SELECT * FROM quartiers ORDER BY nom")}


# ------------------------------ Sécurité et gabarits ------------------------------
@app.template_global()
def jeton_csrf():
    """Jeton secret de la session, placé dans chaque formulaire POST."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def preparer_requete():
    """Contrôle CSRF de tout POST, puis chargement de l'agent connecté."""
    if request.method == "POST":
        attendu, recu = session.get("csrf", ""), request.form.get("csrf", "")
        if not attendu or not hmac.compare_digest(recu.encode(), attendu.encode()):
            abort(400)
    g.agent = None
    if "agent_id" in session:
        g.agent = requete("SELECT * FROM agents WHERE id = ?", (session["agent_id"],), un=True)


@app.after_request
def entetes_securite(reponse):
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:"
    return reponse


@app.context_processor
def contexte():
    return {"agent": g.get("agent"), "STATUTS": STATUTS}


@app.template_filter()
def date_fr(valeur):
    return datetime.strptime(valeur, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")


@app.template_global()
def image(chemin, alt, classe=""):
    """Affiche l'image si le fichier existe, sinon un bloc de remplacement (voir static/images/README.md)."""
    if os.path.exists(os.path.join(app.static_folder, chemin)):
        return Markup('<img class="{}" src="{}" alt="{}" loading="lazy">').format(
            classe, url_for("static", filename=chemin), alt)
    return Markup('<div class="placeholder {}" role="img" aria-label="{}" data-fichier="{}"></div>').format(
        classe, alt, chemin)


@app.errorhandler(HTTPException)
def erreur(e):
    message = MESSAGES.get(e.code, "Une erreur est survenue")
    if request.path.startswith("/api/"):
        return jsonify(erreur=message), e.code
    return render_template("erreur.html", code=e.code, message=message), e.code


def agent_requis(vue):
    """Réserve une route aux agents connectés."""
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        if g.agent is None:
            flash("Connectez-vous pour accéder à l'espace agent.", "erreur")
            return redirect(url_for("connexion"))
        return vue(*args, **kwargs)
    return enveloppe


# ------------------------------ Partie publique ------------------------------
@app.route("/")
def accueil():
    chiffres = requete(
        "SELECT COUNT(*) AS total, COALESCE(SUM(statut = 'resolu'), 0) AS resolus,"
        " COALESCE(SUM(statut = 'en_cours'), 0) AS en_cours, COALESCE(SUM(statut = 'nouveau'), 0) AS nouveaux"
        " FROM signalements", un=True)
    return render_template("accueil.html", chiffres=chiffres, categories=listes()["categories"])


def verifier_photo(fichier):
    """Contrôle la photo envoyée. Retourne (octets, extension, message d'erreur)."""
    if fichier is None or fichier.filename == "":
        return None, None, "Photo : ajoutez une photo du problème."
    if os.path.splitext(fichier.filename)[1].lower() not in (".jpg", ".jpeg", ".png"):
        return None, None, "Photo : formats acceptés .jpg, .jpeg et .png."
    octets = fichier.read(TAILLE_PHOTO_MAX)  # on ne lit jamais plus de 2 Mo
    if len(octets) >= TAILLE_PHOTO_MAX:
        return None, None, "Photo : le fichier doit faire moins de 2 Mo."
    for signature, extension in SIGNATURES.items():  # on regarde le contenu, pas le nom
        if octets.startswith(signature):
            return octets, extension, None
    return None, None, "Photo : ce fichier n'est pas une vraie image JPEG ou PNG."


@app.route("/signaler", methods=["GET", "POST"])
def signaler():
    if request.method == "POST":
        f = request.form
        categorie, quartier = f.get("categorie", ""), f.get("quartier", "")
        reperage, description = f.get("reperage", "").strip(), f.get("description", "").strip()
        tel = f.get("telephone", "").replace(" ", "")
        octets, extension, erreur_photo = verifier_photo(request.files.get("photo"))

        erreurs = []
        if not categorie.isdigit() or requete("SELECT 1 FROM categories WHERE id = ?", (categorie,), un=True) is None:
            erreurs.append("Choisissez une catégorie.")
        if not quartier.isdigit() or requete("SELECT 1 FROM quartiers WHERE id = ?", (quartier,), un=True) is None:
            erreurs.append("Choisissez un quartier.")
        if not 3 <= len(reperage) <= 150:
            erreurs.append("Indiquez une adresse ou un repère (3 à 150 caractères).")
        if not 20 <= len(description) <= 1000:
            erreurs.append("La description doit faire entre 20 et 1000 caractères.")
        if not re.fullmatch(r"6\d{8}", tel):
            erreurs.append("Téléphone invalide : 9 chiffres commençant par 6.")
        if erreur_photo:
            erreurs.append(erreur_photo)
        if erreurs:
            for e in erreurs:
                flash(e, "erreur")
            return render_template("signaler.html", donnees=f, **listes()), 400

        nom_photo = None
        if octets:  # le nom est généré par le serveur : celui de l'utilisateur n'est jamais utilisé
            nom_photo = secrets.token_hex(16) + extension
            os.makedirs(os.path.join(app.static_folder, "uploads"), exist_ok=True)
            with open(os.path.join(app.static_folder, "uploads", nom_photo), "wb") as fichier:
                fichier.write(octets)
        code = "CV-" + secrets.token_hex(5).upper()
        db = get_db()  # statut 'nouveau' et date : valeurs par défaut du schéma
        db.execute("INSERT INTO signalements (code_suivi, categorie_id, quartier_id, description, reperage,"
                   " telephone, photo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (code, int(categorie), int(quartier), description, reperage, tel, nom_photo))
        db.commit()
        flash(f"Signalement enregistré. Conservez votre code de suivi : {code}", "succes")
        return redirect(url_for("suivre", code=code))
    return render_template("signaler.html", donnees={}, **listes())


@app.route("/suivre")
def suivre():
    code = request.args.get("code", "").strip().upper()
    s = historique = None
    if code:
        s = requete("SELECT s.*, c.nom AS categorie, q.nom AS quartier FROM signalements s"
                    " JOIN categories c ON c.id = s.categorie_id JOIN quartiers q ON q.id = s.quartier_id"
                    " WHERE s.code_suivi = ?", (code,), un=True)
        if s is None:
            flash("Aucun signalement ne correspond à ce code.", "erreur")
        else:  # ni téléphone, ni agent, ni identifiant interne
            historique = requete("SELECT date_intervention, commentaire, nouveau_statut FROM interventions"
                                 " WHERE signalement_id = ? ORDER BY date_intervention, id", (s["id"],))
    return render_template("suivre.html", code=code, s=s, historique=historique), (404 if code and s is None else 200)


SQL_LISTE = ("SELECT s.id, s.code_suivi, s.description, s.statut, s.cree_le, s.photo,"
             " c.nom AS categorie, q.nom AS quartier FROM signalements s JOIN categories c ON c.id = s.categorie_id"
             " JOIN quartiers q ON q.id = s.quartier_id WHERE 1 = 1")


def lister(service=None):
    """Liste filtrée par quartier, catégorie et statut (et par service pour un agent)."""
    f = {"quartier": request.args.get("quartier", type=int), "categorie": request.args.get("categorie", type=int),
         "statut": request.args.get("statut", "")}
    sql, params = SQL_LISTE, []
    if service:
        sql += " AND c.service = ?"
        params.append(service)
    if f["quartier"]:
        sql += " AND s.quartier_id = ?"
        params.append(f["quartier"])
    if f["categorie"]:
        sql += " AND s.categorie_id = ?"
        params.append(f["categorie"])
    if f["statut"] in STATUTS:
        sql += " AND s.statut = ?"
        params.append(f["statut"])
    return f, requete(sql + " ORDER BY s.cree_le DESC, s.id DESC LIMIT 60", params)


@app.route("/signalements")
def signalements():
    f, lignes = lister()
    return render_template("signalements.html", f=f, lignes=lignes, admin=False, **listes())


# ------------------------------ Espace agent ------------------------------
@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        agent = requete("SELECT * FROM agents WHERE login = ?", (request.form.get("login", "").strip(),), un=True)
        if agent and check_password_hash(agent["empreinte"], request.form.get("mdp", "")):
            session.clear()  # nouvelle session après connexion
            session["agent_id"] = agent["id"]
            return redirect(url_for("admin"))
        flash("Identifiant ou mot de passe incorrect.", "erreur")
        return render_template("connexion.html"), 401
    return render_template("connexion.html")


@app.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    flash("Vous êtes déconnecté.", "succes")
    return redirect(url_for("accueil"))


@app.route("/admin")
@agent_requis
def admin():
    lignes = requete("SELECT s.statut, COUNT(*) AS n FROM signalements s JOIN categories c ON c.id = s.categorie_id"
                     " WHERE c.service = ? GROUP BY s.statut", (g.agent["service"],))
    return render_template("admin/tableau_bord.html", compteurs={r["statut"]: r["n"] for r in lignes})


@app.route("/admin/signalements")
@agent_requis
def admin_signalements():
    f, lignes = lister(g.agent["service"])
    return render_template("signalements.html", f=f, lignes=lignes, admin=True, **listes())


def dossier_du_service(id_signalement):
    """Retourne le signalement s'il relève du service de l'agent, sinon 404 ou 403 (contrôle côté serveur)."""
    s = requete("SELECT s.*, c.nom AS categorie, c.service, q.nom AS quartier FROM signalements s"
                " JOIN categories c ON c.id = s.categorie_id JOIN quartiers q ON q.id = s.quartier_id"
                " WHERE s.id = ?", (id_signalement,), un=True)
    if s is None:
        abort(404)
    if s["service"] != g.agent["service"]:
        abort(403)
    return s


@app.route("/admin/signalements/<int:id_signalement>")
@agent_requis
def admin_detail(id_signalement):
    s = dossier_du_service(id_signalement)
    historique = requete("SELECT i.*, a.nom AS agent FROM interventions i JOIN agents a ON a.id = i.agent_id"
                         " WHERE i.signalement_id = ? ORDER BY i.date_intervention, i.id", (s["id"],))
    return render_template("admin/detail.html", s=s, historique=historique)


@app.route("/admin/signalements/<int:id_signalement>/intervention", methods=["POST"])
@agent_requis
def admin_intervention(id_signalement):
    """Ajoute une intervention ; elle change le statut du dossier (le rejet exige un motif)."""
    s = dossier_du_service(id_signalement)
    statut = request.form.get("statut", "")
    commentaire = request.form.get("commentaire", "").strip()
    if s["statut"] in ("resolu", "rejete"):
        flash("Ce dossier est clos : il ne peut plus être modifié.", "erreur")
    elif statut not in ("en_cours", "resolu", "rejete"):
        flash("Statut invalide.", "erreur")
    elif len(commentaire) < (10 if statut == "rejete" else 5):
        flash("Le motif du rejet est obligatoire (10 caractères minimum)." if statut == "rejete"
              else "Le commentaire est trop court.", "erreur")
    else:
        db = get_db()
        db.execute("INSERT INTO interventions (signalement_id, agent_id, commentaire, nouveau_statut)"
                   " VALUES (?, ?, ?, ?)", (s["id"], g.agent["id"], commentaire, statut))
        db.execute("UPDATE signalements SET statut = ? WHERE id = ?", (statut, s["id"]))
        db.commit()  # intervention et statut sont enregistrés ensemble
        flash("Intervention enregistrée.", "succes")
    return redirect(url_for("admin_detail", id_signalement=s["id"]))


# ------------------------------ API JSON ------------------------------
@app.route("/api/signalements")
def api_signalements():
    """Derniers signalements, sans donnée personnelle."""
    limite = min(max(request.args.get("limite", 10, type=int), 1), 50)
    lignes = requete("SELECT s.code_suivi, s.statut, s.cree_le, c.nom AS categorie, q.nom AS quartier"
                     " FROM signalements s JOIN categories c ON c.id = s.categorie_id"
                     " JOIN quartiers q ON q.id = s.quartier_id ORDER BY s.cree_le DESC, s.id DESC LIMIT ?", (limite,))
    return jsonify(signalements=[{**dict(r), "statut_libelle": STATUTS[r["statut"]]} for r in lignes])


@app.route("/api/statistiques")
def api_statistiques():
    """Les quatre statistiques du sujet, calculées dans SQLite (données agrégées, publiques)."""
    par_categorie = requete("SELECT c.nom, COUNT(s.id) AS nombre FROM categories c"
                            " LEFT JOIN signalements s ON s.categorie_id = c.id GROUP BY c.id ORDER BY c.id")
    par_quartier = requete("SELECT q.nom, COUNT(s.id) AS nombre FROM quartiers q"
                           " LEFT JOIN signalements s ON s.quartier_id = q.id GROUP BY q.id ORDER BY nombre DESC, q.nom")
    croise = requete("SELECT q.nom AS quartier, c.nom AS categorie, COUNT(*) AS n FROM signalements s"
                     " JOIN categories c ON c.id = s.categorie_id JOIN quartiers q ON q.id = s.quartier_id"
                     " GROUP BY q.id, c.id")
    noms = [r["nom"] for r in par_categorie]
    matrice = {r["nom"]: dict.fromkeys(noms, 0) for r in par_quartier}
    for r in croise:
        matrice[r["quartier"]][r["categorie"]] = r["n"]
    # Délai de résolution = date du signalement -> première intervention « résolu ».
    # Les dossiers rejetés ou non résolus sont exclus ; un service sans dossier résolu n'a pas de délai (null).
    delais = requete(
        "SELECT c.service, COUNT(r.signalement_id) AS resolus,"
        " ROUND(AVG(julianday(r.date_resolution) - julianday(s.cree_le)), 1) AS jours FROM categories c"
        " LEFT JOIN signalements s ON s.categorie_id = c.id AND s.statut = 'resolu'"
        " LEFT JOIN (SELECT signalement_id, MIN(date_intervention) AS date_resolution FROM interventions"
        "            WHERE nouveau_statut = 'resolu' GROUP BY signalement_id) r ON r.signalement_id = s.id"
        " GROUP BY c.service ORDER BY c.service")
    # Non traité = statut « nouveau » (aucune intervention) depuis plus de 7 jours.
    condition = "s.statut = 'nouveau' AND s.cree_le < datetime('now', '-7 days')"
    nombre = requete("SELECT COUNT(*) FROM signalements s WHERE " + condition, un=True)[0]
    anciens = requete("SELECT s.code_suivi, c.nom AS categorie, q.nom AS quartier,"
                      " CAST(julianday('now') - julianday(s.cree_le) AS INTEGER) AS jours FROM signalements s"
                      " JOIN categories c ON c.id = s.categorie_id JOIN quartiers q ON q.id = s.quartier_id"
                      " WHERE " + condition + " ORDER BY s.cree_le LIMIT 10")
    semaines = requete("SELECT strftime('%d/%m', date(cree_le, 'weekday 0', '-6 days')) AS semaine,"
                       " COUNT(*) AS nombre FROM signalements"
                       " GROUP BY date(cree_le, 'weekday 0', '-6 days') ORDER BY date(cree_le, 'weekday 0', '-6 days')")
    return jsonify(
        par_categorie=[dict(r) for r in par_categorie], par_quartier=[dict(r) for r in par_quartier],
        croise={"categories": noms, "lignes": [{"quartier": q, "valeurs": [v[n] for n in noms]}
                                               for q, v in matrice.items()]},
        delai_par_service=[dict(r) for r in delais],
        non_traites={"nombre": nombre, "exemples": [dict(r) for r in anciens]},
        par_semaine=[dict(r) for r in semaines])


if __name__ == "__main__":
    app.run(debug=False)
