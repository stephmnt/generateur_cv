# Générateur de CV

Application Flask pour générer un CV PDF à partir d’un fichier YAML.

## Organisation

- `main.py` : application web Flask.
- `configs/` : profils CV au format YAML.
- `scripts/` : scripts de génération, dont `build_cv.py`.
- `latex/` : gabarit LaTeX.
- `assets/` : images utilisées par le CV.
- `build/` : sorties générées localement.
- `exports/` : PDF exportés à conserver.
- `references/` : documents sources ou références.
- `docs/` : documentation technique.

## Lancer l’application

```bash
pip install -r requirements.txt
python main.py
```

Ouvre ensuite `http://127.0.0.1:5000`, choisis un YAML et télécharge le PDF généré.

## Génération CLI

```bash
python scripts/build_cv.py --input configs/cv-data.yaml --output build/cv.generated.tex
```

La compilation PDF complète est prise en charge par l’application Flask.
