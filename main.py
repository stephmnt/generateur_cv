#!/usr/bin/env python3
"""Minimal Flask app to generate a CV PDF from a YAML profile."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, render_template, request, send_file

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "configs"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_cv.py"
LATEX_DIR = PROJECT_ROOT / "latex"
ASSETS_DIR = PROJECT_ROOT / "assets"
BUILD_DIR = PROJECT_ROOT / "build"

app = Flask(__name__)


def available_yaml_files() -> list[Path]:
    return sorted(CONFIG_DIR.glob("*.yaml"))


def resolve_config(filename: str) -> Path:
    candidates = {path.name: path for path in available_yaml_files()}
    if filename not in candidates:
        raise ValueError("Fichier YAML inconnu.")
    return candidates[filename]


def copy_build_inputs(work_dir: Path) -> None:
    for path in LATEX_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, work_dir / path.name)

    for path in ASSETS_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, work_dir / path.name)


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
        raise RuntimeError(output.strip() or f"Commande échouée : {' '.join(command)}")


def generate_pdf(config_path: Path) -> Path:
    if not shutil.which("lualatex"):
        raise RuntimeError("lualatex est introuvable. Installe une distribution TeX pour compiler le PDF.")

    run_id = uuid.uuid4().hex[:12]
    work_dir = BUILD_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    generated_tex = work_dir / "cv.generated.tex"
    copy_build_inputs(work_dir)

    run_command(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(config_path),
            "--output",
            str(generated_tex),
        ],
        cwd=PROJECT_ROOT,
    )

    env = os.environ.copy()
    env["TEXMFVAR"] = str(work_dir / "texmf-var")
    run_command(
        ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
        cwd=work_dir,
        env=env,
    )

    pdf_path = work_dir / "main.pdf"
    if not pdf_path.exists():
        raise RuntimeError("La compilation LaTeX n’a pas produit de PDF.")

    return pdf_path


@app.get("/")
def index():
    yaml_files = available_yaml_files()
    return render_template("index.html", yaml_files=yaml_files, selected=None, error=None)


@app.post("/generate")
def generate():
    selected = request.form.get("yaml_file", "")
    yaml_files = available_yaml_files()

    try:
        config_path = resolve_config(selected)
        pdf_path = generate_pdf(config_path)
    except Exception as exc:
        return render_template(
            "index.html",
            yaml_files=yaml_files,
            selected=selected,
            error=str(exc),
        ), 400

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f"{config_path.stem}.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(debug=True)
