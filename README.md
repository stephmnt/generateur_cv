# Gestionnaire de CV

![logo](/templates/assets/logo.png)

Application Flask permettant de gérer un profil, de créer des CV et de générer des PDF à partir des données enregistrées en base.

L’application repose sur un profil centralisé qui regroupe toutes les informations du candidat : expériences, formations, compétences, langues, certifications et informations personnelles.

À partir de ce profil unique, il est possible de créer plusieurs CV ciblés. Lors de la création d’un CV, l’utilisateur sélectionne uniquement les données du profil qu’il souhaite afficher. Un même profil peut donc servir à générer différents CV, adaptés à des postes, secteurs ou candidatures spécifiques.

![logo](/templates/assets/demo.png)

## Organisation du projet

- `main.py` : application web Flask.
- `templates/` : gabarits HTML Flask et sous-dossier `templates/assets/` pour les images statiques.
- `scripts/` : scripts de génération, dont `build_cv.py`, ainsi que le registre des canvas disponibles.
- `canvases/` : modèles LaTeX. Chaque sous-dossier correspond à un canvas de CV.
- `database/` : schéma SQLite utilisé pour initialiser la base locale.
- `uploads/` : photos de profil envoyées depuis l’interface, ignorées par Git.
- `build/` : fichiers générés localement, ignorés par Git.

## Technologies utilisées

- Flask
- SQLite
- Jinja2
- LaTeX
- Python

## Prérequis

- Python 3.11+
- TeX Live ou MiKTeX
- pip

Exemple Debian/Ubuntu :

```bash
sudo apt install texlive-full
```

## Lancement de l’application

Installer les dépendances, puis lancer l’application :

```bash
python -m venv .venv
source .venv/bin/activate
```

Pour windows :

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
python main.py
```

Ouvrir ensuite `http://127.0.0.1:5000`, se connecter, créer un CV à partir des éléments du profil, puis générer et télécharger le PDF depuis la liste des CV.

La page `Profil` permet de gérer les données structurées prévues par le cahier des charges :

- informations personnelles ;
- expériences ;
- formations ;
- certifications ;
- compétences ;
- langues ;
- catégories de compétences numériques.

Les pages `Créer un CV`, `Modifier un CV` et `Liste des CV` permettent de créer et modifier un CV avec son titre professionnel, sa description et les éléments du profil à associer au CV. La génération PDF se lance depuis la liste des CV.

Au premier lancement, l’application crée une base SQLite locale dans `instance/app.sqlite3` et initialise un utilisateur de développement :

- e-mail : `admin@example.com`
- mot de passe : `change-me`

Ces valeurs peuvent être remplacées avant le premier lancement :

```bash
export CV_APP_DEFAULT_EMAIL="email@example.com"
export CV_APP_DEFAULT_PASSWORD="mot-de-passe"
export FLASK_SECRET_KEY="cle-secrete"
python main.py
```

## Schéma de base de données

L'application utilise SQLite. Au premier lancement, `main.py` crée la base locale dans `instance/app.sqlite3` à partir de `database/schema.sql`.

### Tables principales

- `users` : comptes applicatifs, avec email, mot de passe hashé, rôle et statut actif.
- `profiles` : informations personnelles du profil unique d'un utilisateur.
- `cvs` : CV créés depuis un profil, avec titre professionnel, description, canvas choisi, chemin du PDF généré et date de génération.

### Données du profil

- `experiences` : expériences professionnelles.
- `educations` : formations.
- `certifications` : certifications.
- `skills` : compétences générales.
- `languages` : langues.
- `digital_categories` : catégories numériques.
- `digital_skills` : compétences numériques associées à une catégorie.

Les expériences, formations et certifications sont ordonnées par dates dans l'application. Les compétences, langues et catégories numériques utilisent `sort_order`, manipulé par drag and drop dans la page Profil.

### Association entre CV et profil

Chaque CV référence les éléments du profil à afficher via des tables de jointure :

- `cv_experiences`
- `cv_educations`
- `cv_certifications`
- `cv_skills`
- `cv_languages`
- `cv_digital_categories`

Ces tables permettent de créer plusieurs CV ciblés à partir du même profil, sans dupliquer les données sources.

### Génération

- `cv_generations` : historique des tentatives de génération PDF, avec statut, chemin de sortie ou message d'erreur.

Le PDF final est généré depuis les données SQLite, puis stocké dans `build/generated/`. Les fichiers de build, les uploads et la base locale sont ignorés par Git.

## Génération PDF

La génération PDF complète est prise en charge par l’application Flask à partir des données SQLite. Le canvas par défaut est `modern-cv`. Il est déclaré dans `scripts/build_cv.py` et stocké dans `canvases/modern-cv/`.

Pour tester rapidement le template sans lancer Flask :

```bash
python3 scripts/build_cv.py --canvas modern-cv --compile-pdf --pdf-output build/cv.local.pdf
```

Le script compile le projet dans `build/local-build/` en copiant automatiquement le canvas choisi et les images nécessaires depuis `templates/assets/`.

## Ajout d’un canvas

1. Créer un dossier dans `canvases/`, par exemple `canvases/mon-canvas/`.
2. Ajouter au minimum un fichier racine LaTeX, généralement `main.tex`.
3. Déclarer le canvas dans `CANVAS_CONFIGS`, dans `scripts/build_cv.py`, avec son nom, son libellé, son dossier, son fichier racine et ses valeurs par défaut.
4. Le modèle apparaît ensuite dans la liste déroulante de la page `Créer un CV`.

La documentation du canvas existant se trouve dans `canvases/modern-cv/README.md`.

## Travail local sur les canvas

Pour générer uniquement le fichier `.tex` :

```bash
python3 scripts/build_cv.py --canvas modern-cv --output build/cv.generated.tex
```

Pour générer et compiler le PDF en une seule commande :

```bash
python3 scripts/build_cv.py --canvas modern-cv --compile-pdf --pdf-output build/cv.local.pdf
```

Pour itérer rapidement sur la mise en page, modifier `canvases/modern-cv/main.tex` ou les paramètres du canvas dans `scripts/build_cv.py`, puis relancer la commande de compilation locale.

## Références

[Curriculum icons created by Freepik - Flaticon](https://www.flaticon.com/free-icons/curriculum)
