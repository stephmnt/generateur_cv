# Schéma de base de données

L'application utilise SQLite. Au premier lancement, `main.py` crée la base locale dans `instance/app.sqlite3` à partir de `database/schema.sql`.

## Tables principales

- `users` : comptes applicatifs, avec email, mot de passe hashé, rôle et statut actif.
- `profiles` : informations personnelles du profil unique d'un utilisateur.
- `cvs` : CV créés depuis un profil, avec titre professionnel, description, canvas choisi, chemin du PDF généré et date de génération.

## Données du profil

- `experiences` : expériences professionnelles.
- `educations` : formations.
- `certifications` : certifications.
- `skills` : compétences générales.
- `languages` : langues.
- `digital_categories` : catégories numériques.
- `digital_skills` : compétences numériques associées à une catégorie.

Les expériences, formations et certifications sont ordonnées par dates dans l'application. Les compétences, langues et catégories numériques utilisent `sort_order`, manipulé par drag and drop dans la page Profil.

## Association entre CV et profil

Chaque CV référence les éléments du profil à afficher via des tables de jointure :

- `cv_experiences`
- `cv_educations`
- `cv_certifications`
- `cv_skills`
- `cv_languages`
- `cv_digital_categories`

Ces tables permettent de créer plusieurs CV ciblés à partir du même profil, sans dupliquer les données sources.

## Génération

- `cv_generations` : historique des tentatives de génération PDF, avec statut, chemin de sortie ou message d'erreur.

Le PDF final est généré depuis les données SQLite, puis stocké dans `build/generated/`. Les fichiers de build, les uploads et la base locale sont ignorés par Git.
