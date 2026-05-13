# Gestionnaire de CV

Application Flask pour gérer un profil, créer des CV ciblés et générer un PDF depuis les données enregistrées en base.

## Organisation

- `main.py` : application web Flask.
- `scripts/` : scripts de génération, dont `build_cv.py` et les paramètres par défaut du template.
- `latex/` : gabarit LaTeX.
- `assets/` : images utilisées par le CV.
- `database/` : schéma SQLite local.
- `uploads/` : photos de profil envoyées depuis l’interface.
- `build/` : sorties générées localement.
- `exports/` : PDF exportés à conserver.
- `references/` : documents sources ou références.
- `docs/` : documentation technique.

## Lancer l’application

```bash
pip install -r requirements.txt
python main.py
```

Ouvre ensuite `http://127.0.0.1:5000`, connecte-toi, crée un CV depuis les éléments du profil, puis génère et télécharge le PDF depuis la liste des CV.

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
export CV_APP_DEFAULT_EMAIL="ton-email@example.com"
export CV_APP_DEFAULT_PASSWORD="un-mot-de-passe"
export FLASK_SECRET_KEY="une-cle-secrete"
python main.py
```

## Génération

La génération PDF complète est prise en charge par l’application Flask à partir des données SQLite. Les paramètres du template `modern-cv` sont centralisés dans `scripts/build_cv.py`, et les fichiers YAML de profil ne sont plus utilisés par l’application.

Pour tester rapidement le template sans lancer Flask :

```bash
python3 scripts/build_cv.py --compile-pdf --pdf-output build/cv.local.pdf
```

Le script compile dans `build/local-build/` en copiant automatiquement le gabarit LaTeX et les assets nécessaires.

## Améliorations restantes

- Nettoyer les builds précédents à la génération d'un nouveau build pour ne pas faire exploser le stockage.
- Ajouter le petit logo de cv.
- Discrètement sous chaque champ de la page profil, préciser quel cv utilise ce champ.
- Warning en cas de supression d'un champ utilisé par un cv.
- Sécuriser les formulaires : champ date pour les dates.
- Problème de décalage entre la section "à propos" et les informations personnelles.

## Références

[Curriculum icons created by Freepik - Flaticon](https://www.flaticon.com/free-icons/curriculum)
