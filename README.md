# CITEVOX : signalement citoyen des problèmes urbains (Projet 13)

Plateforme Flask + SQLite : les habitants signalent un problème (avec photo), suivent son traitement avec un code, et les agents des services techniques gèrent les dossiers de leur service.

## 1. Prérequis
Python 3.10 ou plus récent (testé avec Python 3.12). Aucun autre logiciel.

## 2. Installation
```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux, macOS
pip install -r requirements.txt
```

## 3. Configuration
La clé secrète des sessions vient d'une variable d'environnement (voir `.env.example`). Sans elle, une clé aléatoire est créée à chaque lancement (les connexions sont alors perdues au redémarrage).
```bash
python -c "import secrets; print(secrets.token_hex(32))"   # génère une clé
set SECRET_KEY=la_cle_generee            # Windows
export SECRET_KEY=la_cle_generee         # Linux, macOS
```

## 4. Base de données
`projet.db` est fournie, déjà remplie. Pour la recréer (structure `schema.sql` + données de test + export `export_projet.sql`) :
```bash
python donnees_test.py
```
Le script supprime et recrée les tables : on peut le relancer sans créer de doublons. Il affiche les volumes obtenus (minimum du sujet : 5 catégories, 12 quartiers, 200 signalements sur 3 mois, 250 interventions, 8 agents). Les dates sont calculées par rapport au jour d'exécution : relancez-le avant la démonstration pour avoir des données récentes.

## 5. Lancement
```bash
python app.py
```
Ouvrir http://127.0.0.1:5000 (le mode `debug` est désactivé).

## 6. Comptes de démonstration (espace agent : /connexion)
Mot de passe de tous les comptes : `Citevox#2026` (modifiable avec la variable `MDP_DEMO` avant `python donnees_test.py`).

| Identifiant | Service |
|---|---|
| voirie1, voirie2 | Voirie et travaux |
| proprete1, proprete2 | Propreté urbaine |
| eclairage1, eclairage2 | Éclairage public |
| eau1 | Eau et assainissement |
| general1 | Services généraux |

Un agent ne voit et ne gère que les dossiers de son service (contrôle fait sur le serveur à chaque requête).

## 7. Routes principales
| Adresse | Méthode | Rôle |
|---|---|---|
| `/` | GET | Page d'accueil |
| `/signaler` | GET, POST | Formulaire de signalement avec photo |
| `/suivre?code=CV-...` | GET | Suivi par code et historique |
| `/signalements` | GET | Liste publique filtrée (quartier, catégorie, statut) |
| `/connexion`, `/deconnexion` | GET/POST, POST | Connexion et déconnexion des agents |
| `/admin` | GET | Tableau de bord et statistiques (agent) |
| `/admin/signalements` | GET | Dossiers du service de l'agent |
| `/admin/signalements/<id>` | GET | Détail d'un dossier |
| `/admin/signalements/<id>/intervention` | POST | Intervention, changement de statut ou rejet avec motif |
| `/api/statistiques` | GET | Les 4 statistiques en JSON |
| `/api/signalements?limite=4` | GET | Derniers signalements en JSON |

Règles de calcul des statistiques : délai de résolution = date du signalement jusqu'à la première intervention « résolu » (dossiers rejetés ou non résolus exclus) ; « non traité » = statut `nouveau` depuis plus de 7 jours.

## 8. Tests
```bash
python -m unittest tests.test_app -v
```
Les tests utilisent une base temporaire : `projet.db` n'est pas modifiée.

## 9. Validation W3C
Pages à valider sur https://validator.w3.org (onglet « Validate by direct input », coller le code source) : `/`, `/signaler`, `/suivre?code=<un code>`, `/signalements`, `/connexion`, page 404, `/admin`, `/admin/signalements`, un dossier `/admin/signalements/<id>`. Les pages d'administration se valident après connexion (copier le code source affiché).

## 10. Images à remplacer
Voir `static/images/README.md` : il suffit de déposer le fichier avec le bon nom, sans toucher au code.
