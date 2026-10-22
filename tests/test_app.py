"""Tests : python -m unittest tests.test_app -v (la base de démonstration n'est jamais touchée)."""
import io
import os
import sqlite3
import tempfile
import unittest

import donnees_test
from app import app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
UPLOADS = os.path.join(app.static_folder, "uploads")
VALIDE = {"categorie": "1", "quartier": "1", "reperage": "Près du marché",
          "description": "Un nid-de-poule profond au milieu de la route.", "telephone": "699 00 12 34"}


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chemin = os.path.join(tempfile.mkdtemp(), "test.db")
        app.config.update(TESTING=True, DATABASE=cls.chemin)
        cls.compteurs = donnees_test.remplir(cls.chemin)

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as s:
            s["csrf"] = "jeton"
        self.avant = set(os.listdir(UPLOADS))

    def tearDown(self):  # supprime les photos créées par les tests
        for nom in set(os.listdir(UPLOADS)) - self.avant:
            os.remove(os.path.join(UPLOADS, nom))

    def sql(self, requete, params=()):
        with sqlite3.connect(self.chemin) as db:
            return db.execute(requete, params).fetchall()

    def post(self, url, **donnees):
        return self.client.post(url, data={"csrf": "jeton", **donnees})

    def connecter(self, login):
        reponse = self.post("/connexion", login=login, mdp=donnees_test.MOT_DE_PASSE_DEMO)
        with self.client.session_transaction() as s:  # la connexion renouvelle la session : on refixe le jeton
            s["csrf"] = "jeton"
        return reponse

    def test_volumes_minimum(self):
        for table, minimum in donnees_test.MINIMUM.items():
            self.assertGreaterEqual(self.compteurs[table], minimum, table)

    def test_pages_publiques(self):
        for url in ["/", "/signaler", "/suivre", "/signalements", "/connexion",
                    "/signalements?quartier=1&categorie=2&statut=nouveau", "/api/statistiques", "/api/signalements"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_erreur_404_personnalisee(self):
        reponse = self.client.get("/inexistante")
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("Page introuvable", reponse.get_data(as_text=True))

    def test_post_sans_jeton_csrf_refuse(self):
        self.assertEqual(self.client.post("/signaler", data=VALIDE).status_code, 400)

    def test_formulaire_invalide(self):
        reponse = self.post("/signaler", **{**VALIDE, "description": "trop court", "telephone": "123"})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("entre 20 et 1000", reponse.get_data(as_text=True))
        self.assertIn("Près du marché", reponse.get_data(as_text=True))  # les saisies sont conservées

    def test_signalement_valide_avec_photo(self):
        reponse = self.client.post("/signaler", data={"csrf": "jeton", **VALIDE, "photo": (io.BytesIO(PNG), "../../evil.png")},
                                   follow_redirects=True)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("CV-", reponse.get_data(as_text=True))
        photo = self.sql("SELECT photo FROM signalements ORDER BY id DESC LIMIT 1")[0][0]
        self.assertRegex(photo, r"^[0-9a-f]{32}\.png$")  # nom généré par le serveur
        self.assertTrue(os.path.exists(os.path.join(UPLOADS, photo)))
        self.assertIn("uploads/" + photo, self.client.get("/signalements").get_data(as_text=True))  # miniature dans la liste

    def test_photo_obligatoire(self):
        reponse = self.post("/signaler", **VALIDE)  # aucune photo envoyée
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("ajoutez une photo", reponse.get_data(as_text=True))

    def test_photos_refusees(self):
        cas = {"faux PNG": (b"ceci n'est pas une image", "a.png"), "extension .gif": (PNG, "a.gif"),
               "trop lourde": (b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024), "a.jpg")}
        for nom, (contenu, fichier) in cas.items():
            reponse = self.client.post("/signaler", data={"csrf": "jeton", **VALIDE, "photo": (io.BytesIO(contenu), fichier)})
            self.assertEqual(reponse.status_code, 400, nom)
        self.assertEqual(set(os.listdir(UPLOADS)), self.avant)  # rien n'a été enregistré

    def test_suivi_et_injection_sql(self):
        code = self.sql("SELECT code_suivi FROM signalements WHERE statut = 'resolu' LIMIT 1")[0][0]
        page = self.client.get("/suivre?code=" + code).get_data(as_text=True)
        self.assertIn("Historique des interventions", page)
        self.assertNotIn("699", page)  # le téléphone n'est jamais public
        self.assertEqual(self.client.get("/suivre?code=' OR '1'='1").status_code, 404)

    def test_admin_protege(self):
        for url in ["/admin", "/admin/signalements", "/admin/signalements/1"]:
            reponse = self.client.get(url)
            self.assertEqual(reponse.status_code, 302, url)
            self.assertIn("/connexion", reponse.headers["Location"])

    def test_mauvais_mot_de_passe(self):
        reponse = self.post("/connexion", login="voirie1", mdp="faux")
        self.assertEqual(reponse.status_code, 401)

    def test_isolation_des_services(self):
        self.connecter("voirie1")
        autre = self.sql("SELECT s.id FROM signalements s JOIN categories c ON c.id = s.categorie_id"
                         " WHERE c.service != 'Voirie et travaux' LIMIT 1")[0][0]
        propre = self.sql("SELECT s.id FROM signalements s JOIN categories c ON c.id = s.categorie_id"
                          " WHERE c.service = 'Voirie et travaux' LIMIT 1")[0][0]
        self.assertEqual(self.client.get(f"/admin/signalements/{autre}").status_code, 403)
        self.assertEqual(self.post(f"/admin/signalements/{autre}/intervention", statut="resolu",
                                   commentaire="tentative interdite").status_code, 403)
        self.assertEqual(self.client.get(f"/admin/signalements/{propre}").status_code, 200)
        self.assertNotIn("Éclairage", self.client.get("/admin/signalements").get_data(as_text=True).split("<ul class=\"cartes\">")[1])

    def test_intervention_rejet_et_deconnexion(self):
        self.connecter("eclairage1")
        id_s = self.sql("SELECT s.id FROM signalements s JOIN categories c ON c.id = s.categorie_id"
                        " WHERE c.service = 'Éclairage public' AND s.statut = 'nouveau' LIMIT 1")[0][0]
        statut = lambda: self.sql("SELECT statut FROM signalements WHERE id = ?", (id_s,))[0][0]
        url = f"/admin/signalements/{id_s}/intervention"
        self.post(url, statut="en_cours", commentaire="Équipe prévenue")
        self.assertEqual(statut(), "en_cours")
        self.post(url, statut="rejete", commentaire="court")  # motif trop court
        self.assertEqual(statut(), "en_cours")
        self.post(url, statut="rejete", commentaire="Doublon d'un dossier existant")
        self.assertEqual(statut(), "rejete")
        self.post(url, statut="resolu", commentaire="Dossier déjà clos")  # dossier clos
        self.assertEqual(statut(), "rejete")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM interventions WHERE signalement_id = ?", (id_s,))[0][0], 2)
        self.post("/deconnexion")
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_api_statistiques(self):
        d = self.client.get("/api/statistiques").get_json()
        self.assertEqual(len(d["par_categorie"]), 5)
        self.assertGreaterEqual(sum(x["nombre"] for x in d["par_quartier"]), 200)
        self.assertEqual(len(d["croise"]["lignes"]), 12)
        self.assertGreater(d["non_traites"]["nombre"], 0)
        self.assertTrue(any(x["jours"] for x in d["delai_par_service"]))
        self.assertGreater(len(d["par_semaine"]), 8)  # environ 13 semaines de données

    def test_api_signalements(self):
        d = self.client.get("/api/signalements?limite=3").get_json()
        self.assertEqual(len(d["signalements"]), 3)
        self.assertNotIn("telephone", d["signalements"][0])


if __name__ == "__main__":
    unittest.main()
