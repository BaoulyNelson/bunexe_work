# e-certificat

Portail Django de démonstration du MENFP d'Haïti pour la recherche de résultats du baccalauréat, la demande de relevés/certificats, leur émission PDF et leur vérification publique.

## Arborescence

```text
config/                 Réglages, URLs, ASGI et WSGI
applications/
  candidats/            Dossiers candidats et import CSV/XLSX
  paiements/            Tarifs, modes et stratégies de paiement
  documents/            Demandes, documents émis et PDF
  verification/         Vérifications publiques et audit
  core/                 Wizard, formulaires, pages publiques
templates/              Templates Django
static/                 CSS et JavaScript du portail
fixtures/               Référentiel CSV des matières
locale/ht/              Traductions créole haïtien (gettext)
```

## Modèles

- `Candidat` : résultat officiel indexé par année et code, avec unicité année/code.
- `Candidat.type_resultat` : catégorie BAC UNIQUE, PERM. NS4, PERM. PHILO ou 9ÈME A.F.
- `NoteMatiere` : note et coefficient d’une matière pour le relevé affiché.
- `Tarif` : prix HTG activable pour relevé, certificat ou pack.
- `ModePaiement` : fournisseur, logo, disponibilité et gratuité.
- `DemandeDocument` : choix, tarif, UUID de transaction, état, étapes et métadonnées de requête.
- `DocumentEmis` : PDF par type, code de vérification, compteur d'impressions et révocation.
- `AuditEvenement` : événements d'impression et de vérification.

## Démarrage local

Python 3.12 ou supérieur est nécessaire. Depuis ce dossier :

```powershell
python3 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Ouvrir `http://127.0.0.1:8000/`. Pour ajouter des résultats fictifs, lancer `python manage.py seed_demo_results`. L'admin se trouve sous `/admin/`; créer un compte avec `python manage.py createsuperuser`.

La base SQLite est utilisée par défaut. Pour PostgreSQL, définir `DATABASE_URL` dans `.env`, par exemple `postgres://utilisateur:motdepasse@localhost:5432/e_certificat`.

## Docker

Copier `.env.example` vers `.env`, définir `SECRET_KEY` et `POSTGRES_PASSWORD`, puis lancer :

```powershell
docker compose up --build
```

Le service web applique les migrations et collecte les fichiers statiques au démarrage. Les fichiers PDF sont conservés dans le volume `media_data`.

## Importer les résultats

```powershell
python manage.py import_candidats chemin/vers/resultats.csv
python manage.py import_candidats chemin/vers/resultats.xlsx
```

Colonnes requises : `annee`, `code`, `nom`, `prenom`. Le code doit contenir exactement 10 chiffres et commencer par `01` à `10`. Colonnes facultatives : `date_naissance`, `lieu_naissance`, `telephone`, `total_points`, `total_sur`, `mention`, `type_resultat`, `serie`, `ecole`, `matiere`, `note`, `coefficient`. Le statut est calculé automatiquement : admis à partir de 50 % du total, échoué en dessous; une colonne `statut` éventuellement présente dans le CSV est ignorée. Les candidats échoués ne peuvent pas demander ni télécharger de relevé ou de diplôme. Les types acceptés sont `bac_unique`, `perm_ns4`, `perm_philo` et `9e_af`; sans valeur, le dossier est classé `bac_unique`. Pour importer un relevé détaillé, répéter le dossier candidat sur plusieurs lignes et renseigner `matiere`, `note` et `coefficient` sur chaque ligne. Les dates acceptent `AAAA-MM-JJ` ou `JJ/MM/AAAA`. Garder le code candidat au format texte dans Excel pour préserver les zéros initiaux. Un import répété met à jour le dossier année/code et ses matières existantes.

Après l'import de `data/candidats_notes_import.csv`, les notes de chaque candidat sont visibles sur sa fiche admin, dans le tableau « Notes matière ». Pour importer le catalogue général `data/matieres_menfp.csv`, lancer :

```powershell
python manage.py import_matieres data/matieres_menfp.csv
```

Le catalogue apparaît sous **Admin → Candidats → Matières du programme**. Il est distinct des notes individuelles du candidat.

## Importer les modes de paiement et tarifs

```powershell
python manage.py import_paiements data/modepaiement.csv data/paiements_tarif.csv
```

Les modes apparaissent dans **Admin → Paiements → Modes de paiement** et les tarifs dans **Admin → Paiements → Tarifs**. La commande peut être relancée : elle met à jour les enregistrements par code ou type de document sans créer de doublons. Un champ logo vide dans le CSV ne remplace pas un logo déjà téléversé.

## Sauvegarder et restaurer en CSV

Avant de recréer la base, exporter les données métier dans un dossier CSV :

```powershell
python manage.py exporter_donnees_csv sauvegardes/2026-10-09
```

Après avoir créé une base vide et appliqué les migrations, restaurer l'export :

```powershell
python manage.py migrate
python manage.py importer_donnees_csv sauvegardes/2026-10-09
```

L'export contient les candidats, notes, tarifs, modes de paiement, demandes, documents émis, journaux d'audit, comptes, groupes et leurs relations. L'import met à jour les lignes par identifiant sans supprimer les lignes absentes du CSV; pour une restauration fidèle, l'utiliser après `migrate` sur une base vide. Les PDF et logos ne sont pas intégrés aux CSV : sauvegarder et restaurer aussi le dossier `media/`. Ces sauvegardes contiennent des renseignements personnels et des mots de passe hachés; les conserver dans un emplacement privé et protégé.

Pour ajouter 12 candidats fictifs par catégorie (48 au total), ainsi que les trois tarifs actifs et le mode `SÈVIS GRATIS`, dans une base locale, lancer :

```powershell
python manage.py migrate
python manage.py seed_demo_results
```

La commande est réexécutable sans créer de doublons. Elle affiche les matricules numériques de chaque candidat pour tester les quatre boutons de `/resultats/`. Ces dossiers de démonstration sont synthétiques et ne représentent pas de vrais élèves. Les lignes des examens permanents ne listent que les matières sous 50 %; le tarif s’affiche à l’étape de choix du document et le paiement gratuit se choisit à l’étape suivante.

## Traductions et tests

Les chaînes sont marquées pour gettext. Après modification des traductions, compiler avec `python manage.py compilemessages` (GNU gettext requis). Le portail prend en charge les langues `fr` et `ht`.

```powershell
python -m pytest
python manage.py check
```

## Paiements et sécurité

Le mode local `SÈVIS GRATIS` fonctionne sans fournisseur externe. Les intégrations payantes s'ajoutent en enregistrant une stratégie dans `applications/paiements/providers.py`; aucune passerelle réelle n'est activée par défaut. La recherche compare année, code, nom et prénom, est limitée par IP, et les étapes suivantes ne sont accessibles qu'après validation de la session. Utiliser HTTPS, définir une clé secrète unique, configurer `ALLOWED_HOSTS` et ajouter une politique de rétention adaptée avant toute mise en production.
