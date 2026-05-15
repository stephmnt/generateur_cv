# Canvas modern-cv

`modern-cv` est le canvas LaTeX utilisé par défaut. Il est composé de :

- `main.tex` : gabarit LaTeX réellement compilé.
- `modern-cv.cls` : ancienne classe conservée comme référence, non utilisée par le build principal.
- `cv.generated.tex` : fichier généré au moment du build dans le dossier temporaire, jamais à modifier à la main.

Le build copie ce dossier dans un répertoire de travail, copie aussi `templates/assets/`, écrit `cv.generated.tex`, puis compile `main.tex` avec `lualatex`.

## Paramètres du canvas

Les valeurs par défaut sont dans `MODERN_CV_TEMPLATE`, dans `scripts/build_cv.py`. Elles sont transformées en commandes LaTeX dans `cv.generated.tex`, puis consommées par `main.tex`.

### `layout`

- `sidebar_width` : largeur du bandeau latéral gauche. Exemple : `0.367\paperwidth`. Augmenter cette valeur élargit la colonne beige et réduit la colonne principale.
- `pad` : marge interne générale. Elle sert aux marges de page, au padding de la sidebar et au positionnement horizontal de la photo.
- `main_gap` : espace entre la sidebar et la colonne principale. La valeur par défaut `24mm` reproduit l'ancien écart calculé avec `2 * pad`.
- `content_top_offset` : hauteur de départ du contenu sous la barre de titre. Diminuer la valeur remonte à la fois `À propos` et la colonne principale. Augmenter la valeur les descend.
- `contact_block_top_shift` : décalage vertical appliqué uniquement au bloc d'informations personnelles dans la colonne principale. Une valeur négative le remonte ; une valeur positive le descend.

### `layout.header_bar`

- `left_overlap` : quantité de chevauchement de la barre noire dans la sidebar. Augmenter la valeur décale le bord gauche de la barre vers la gauche.
- `top_shift` : position du haut de la barre noire depuis le haut de page. La valeur est généralement négative ; plus elle est proche de `0mm`, plus la barre remonte.
- `bottom_shift` : position du bas de la barre noire depuis le haut de page. Plus la valeur est négative, plus la barre descend et devient haute.

### `photo`

- `path` : chemin de l'image de profil. Une valeur vide masque la photo ; les photos envoyées depuis l'interface utilisent `uploads/...`.
- `width` : largeur de l'image insérée dans le cercle.
- `radius` : rayon du masque circulaire.
- `x_from_pad` : décalage horizontal de la photo depuis la marge interne gauche.
- `y_shift` : position verticale de la photo depuis le haut de page. La valeur est généralement négative ; plus elle est proche de `0mm`, plus la photo remonte.
- `border_width` : épaisseur du contour blanc autour de la photo.

### `header`

- `name` : nom affiché dans la barre noire. Il est rempli depuis la base de données.
- `title` : titre professionnel du CV. Il est rempli depuis le CV choisi.
- `name_font_size` : taille du nom.
- `letter_space` : espacement des lettres du nom.
- `name_title_gap` : espace vertical entre le nom et le titre.

### `contacts`

Le bloc est divisé en deux colonnes :

- `left` : LinkedIn, email, site web.
- `right` : GitHub, téléphone, adresse.

Chaque entrée utilise `icon`, `value`, `url` ou `value_lines`. Les icônes sont résolues dans `ICON_MAP` dans `scripts/build_cv.py` et utilisent FontAwesome (`\faEnvelope`, `\faLinkedin`, `\faGithub`, etc.).

### `sidebar`

- `about.heading` et `about.paragraphs` : titre et contenu de la section `À propos`.
- `formations.heading` et `formations.entries` : titre et entrées de formation.
- `certifications.heading`, `certifications.subtitle` et `certifications.entries` : titre, sous-titre optionnel et entrées de certification.
- `skills.heading` et `skills.items` : titre et liste des compétences.
- `languages.heading` et `languages.items` : titre et liste des langues.

Les espaces entre les sections de la sidebar sont réglés directement dans `main.tex` avec `\sideheading` et `\sideheadingfirst`.

### `main`

- `experiences.heading` et `experiences.entries` : titre et entrées d'expérience.
- `digital.heading` et `digital.categories` : titre et catégories numériques.

La mise en page d'une expérience est définie par `\job` dans `main.tex`.

## Espacements typographiques dans `main.tex`

Les espacements fins du canvas ne sont pas tous dans `MODERN_CV_TEMPLATE`. Les espacements propres au rendu LaTeX sont dans `canvases/modern-cv/main.tex`, principalement dans la section `Typographic helpers`.

### Headings de sidebar

Les sections `Formations`, `Certifications`, `Compétences` et `Langues` utilisent `\sideheading` :

```tex
\newcommand{\sideheading}[1]{%
  \vspace{10mm}%  % espace avant le heading
  {\color{TextDark}\bfseries\large\MakeUppercase{#1}}\par
  \vspace{2mm}%   % espace entre le heading et son contenu
}
```

- `\vspace{10mm}` : espace entre le bloc précédent et le heading suivant. Le diminuer rapproche `Formations`, `Certifications`, etc. du texte au-dessus.
- `\vspace{2mm}` : espace entre le heading et le contenu de la section. Le diminuer rapproche le texte du titre.

La première section `À propos` utilise `\sideheadingfirst` :

```tex
\newcommand{\sideheadingfirst}[1]{%
  {\color{TextDark}\bfseries\large\MakeUppercase{#1}}\par
  \vspace{2mm}%   % espace entre À PROPOS et son contenu
}
```

Cette macro n'a pas d'espace avant le heading, car `À propos` est le premier bloc de la sidebar. Pour remonter ou descendre toute la section `À propos`, il faut plutôt modifier `layout.content_top_offset` dans `scripts/build_cv.py`.

### Sections de colonne principale

Les sections `Expérience` et `Numérique` utilisent `\cvsection` :

```tex
\newcommand{\cvsection}[1]{%
  \vspace{2mm}%   % espace avant le titre de section
  \noindent{\color{TextDark}\bfseries\Large\MakeUppercase{#1}}\par
  \vspace{3mm}%   % espace entre le titre et son contenu
}
```

- `\vspace{2mm}` : espace avant `EXPÉRIENCE` ou `NUMÉRIQUE`.
- `\vspace{3mm}` : espace entre le titre de section et les entrées.

### Informations personnelles

Chaque ligne du bloc de contact utilise `\contactitem` :

```tex
\newcommand{\contactitem}[2]{%
  \begin{tabularx}{\linewidth}{@{}p{6mm}X@{}}
    {\color{TextDark}#1} & {\color{TextDark}#2}
  \end{tabularx}\vspace{1mm}
}
```

- `p{6mm}` : largeur réservée à l'icône.
- `\vspace{1mm}` : espace vertical après chaque ligne de contact.

La position verticale globale du bloc d'informations personnelles est réglée par `layout.contact_block_top_shift` dans `scripts/build_cv.py`.

### Entrées d'expérience

Chaque expérience utilise `\job` :

```tex
\newcommand{\job}[4]{%
  ...
  \vspace{4mm}
}
```

- `p{5mm}` : largeur de la colonne du marqueur rond.
- `p{28mm}` : largeur de la colonne des dates.
- `\vspace{4mm}` : espace vertical après chaque expérience.

## Réglages fréquents

- Remonter ou descendre toute la zone de contenu : modifier `layout.content_top_offset`.
- Corriger uniquement l'alignement des informations personnelles : modifier `layout.contact_block_top_shift`.
- Remonter la barre noire et la photo : modifier `layout.header_bar.top_shift`, `layout.header_bar.bottom_shift` et `photo.y_shift` ensemble.
- Modifier la largeur de la sidebar : modifier `layout.sidebar_width`.
- Modifier l'espace entre sidebar et colonne principale : modifier `layout.main_gap`.
- Modifier l'espace entre deux sections de sidebar : modifier le premier `\vspace` dans `\sideheading`.
- Modifier l'espace entre un heading de sidebar et son texte : modifier le second `\vspace` dans `\sideheading` ou `\sideheadingfirst`.
