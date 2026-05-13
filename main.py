#!/usr/bin/env python3
"""Minimal Flask app to manage CV profiles and generate PDF output."""

from __future__ import annotations

import os
import secrets
import shutil
import sqlite3
import subprocess
import uuid
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from scripts.build_cv import build_document, default_cv_data

PROJECT_ROOT = Path(__file__).resolve().parent
LATEX_DIR = PROJECT_ROOT / "latex"
ASSETS_DIR = PROJECT_ROOT / "assets"
BUILD_DIR = PROJECT_ROOT / "build"
GENERATED_PDF_DIR = BUILD_DIR / "generated"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
DATABASE_DIR = PROJECT_ROOT / "instance"
DATABASE_PATH = DATABASE_DIR / "app.sqlite3"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
BUILD_RUN_ID_LENGTH = 12

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DEFAULT_USER_EMAIL = os.environ.get("CV_APP_DEFAULT_EMAIL", "admin@example.com")
DEFAULT_USER_PASSWORD = os.environ.get("CV_APP_DEFAULT_PASSWORD", "change-me")

PROFILE_FIELDS = [
    "first_name",
    "last_name",
    "website",
    "linkedin",
    "github",
    "phone",
    "email",
    "address_line_1",
    "address_line_2",
    "postal_code",
    "city",
    "country",
]

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

SECTION_CONFIG = {
    "experiences": {
        "table": "experiences",
        "fields": ["role", "organization", "description", "start_date", "end_date", "sort_order"],
        "booleans": ["is_current"],
    },
    "educations": {
        "table": "educations",
        "fields": ["diploma", "institution", "start_date", "end_date", "sort_order"],
        "booleans": [],
    },
    "certifications": {
        "table": "certifications",
        "fields": ["diploma", "institution", "date_obtained", "sort_order"],
        "booleans": [],
    },
    "skills": {
        "table": "skills",
        "fields": ["label", "category", "sort_order"],
        "booleans": [],
    },
    "languages": {
        "table": "languages",
        "fields": ["language", "level", "sort_order"],
        "booleans": [],
    },
}

REORDERABLE_PROFILE_SECTIONS = {"skills", "languages", "digital_categories"}

CV_SELECTION_CONFIG = {
    "experiences": {
        "source_table": "experiences",
        "join_table": "cv_experiences",
        "join_column": "experience_id",
    },
    "educations": {
        "source_table": "educations",
        "join_table": "cv_educations",
        "join_column": "education_id",
    },
    "certifications": {
        "source_table": "certifications",
        "join_table": "cv_certifications",
        "join_column": "certification_id",
    },
    "skills": {
        "source_table": "skills",
        "join_table": "cv_skills",
        "join_column": "skill_id",
    },
    "languages": {
        "source_table": "languages",
        "join_table": "cv_languages",
        "join_column": "language_id",
    },
    "digital_categories": {
        "source_table": "digital_categories",
        "join_table": "cv_digital_categories",
        "join_column": "digital_category_id",
    },
}


def get_db() -> sqlite3.Connection:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_db() as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        migrate_db(connection)
        existing_user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (DEFAULT_USER_EMAIL,),
        ).fetchone()

        if existing_user is None:
            connection.execute(
                """
                INSERT INTO users (email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?)
                """,
                (
                    DEFAULT_USER_EMAIL,
                    generate_password_hash(DEFAULT_USER_PASSWORD),
                    "admin",
                    1,
                ),
            )


def migrate_db(connection: sqlite3.Connection) -> None:
    profile_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(profiles)").fetchall()
    }
    if profile_columns and "github" not in profile_columns:
        connection.execute("ALTER TABLE profiles ADD COLUMN github TEXT NOT NULL DEFAULT ''")


def find_active_user_by_email(email: str) -> sqlite3.Row | None:
    with get_db() as connection:
        return connection.execute(
            """
            SELECT id, email, password_hash, role, is_active
            FROM users
            WHERE lower(email) = lower(?) AND is_active = 1
            """,
            (email.strip(),),
        ).fetchone()


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, email, role, is_active FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()

    return dict(user) if user else None


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf_token() -> bool:
    token = session.get("_csrf_token")
    submitted = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    return bool(token and submitted and secrets.compare_digest(token, submitted))


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("latex", "")).replace("~", " ")
    if isinstance(value, list):
        return ", ".join(clean_text(item) for item in value)
    return str(value).strip()


def form_text(name: str) -> str:
    return request.form.get(name, "").strip()


def form_int(name: str, default: int = 0) -> int:
    value = request.form.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def allowed_photo(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def save_profile_photo(user_id: int) -> str | None:
    file = request.files.get("photo")
    if file is None or not file.filename:
        return None

    if not allowed_photo(file.filename):
        raise ValueError("La photo doit être au format JPG, PNG ou WebP.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"profile-{user_id}-{uuid.uuid4().hex[:10]}.{extension}"
    destination = UPLOAD_DIR / filename
    file.save(destination)
    return f"uploads/{filename}"


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def next_sort_order(connection: sqlite3.Connection, table: str, owner_column: str, owner_id: int) -> int:
    row = connection.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM {table} WHERE {owner_column} = ?",
        (owner_id,),
    ).fetchone()
    return int(row["next_order"]) if row else 1


def insert_record(connection: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(values.keys())
    placeholders = ", ".join("?" for _ in values)
    cursor = connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    return int(cursor.lastrowid)


def default_profile_payload(user_id: int, user_email: str) -> dict[str, Any]:
    payload: dict[str, Any] = {field: "" for field in PROFILE_FIELDS}
    payload["user_id"] = user_id
    payload["email"] = user_email
    return payload


def get_or_create_profile(user_id: int) -> dict[str, Any]:
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)

        user = connection.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        profile_id = insert_record(
            connection,
            "profiles",
            default_profile_payload(user_id, user["email"] if user else ""),
        )
        row = connection.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row)


def section_rows(connection: sqlite3.Connection, table: str, profile_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"SELECT * FROM {table} WHERE profile_id = ? ORDER BY sort_order, id",
        (profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def date_section_rows(connection: sqlite3.Connection, table: str, profile_id: int) -> list[dict[str, Any]]:
    order_by = {
        "experiences": "is_current DESC, start_date DESC, end_date DESC, id DESC",
        "educations": "start_date DESC, end_date DESC, id DESC",
        "certifications": "date_obtained DESC, id DESC",
    }[table]
    rows = connection.execute(
        f"SELECT * FROM {table} WHERE profile_id = ? ORDER BY {order_by}",
        (profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def digital_categories(connection: sqlite3.Connection, profile_id: int) -> list[dict[str, Any]]:
    categories = section_rows(connection, "digital_categories", profile_id)
    for category in categories:
        skills = connection.execute(
            """
            SELECT * FROM digital_skills
            WHERE digital_category_id = ?
            ORDER BY sort_order, id
            """,
            (category["id"],),
        ).fetchall()
        category["skills"] = [dict(skill) for skill in skills]
        category["skills_text"] = "\n".join(
            (
                f"{skill['value']} || {skill['value_latex']}"
                if skill["value_latex"]
                else skill["value"]
            )
            for skill in category["skills"]
        )
    return categories


def load_profile_data(user_id: int) -> dict[str, Any]:
    profile = get_or_create_profile(user_id)
    profile_id = int(profile["id"])
    with get_db() as connection:
        return {
            "profile": profile,
            "experiences": date_section_rows(connection, "experiences", profile_id),
            "educations": date_section_rows(connection, "educations", profile_id),
            "certifications": date_section_rows(connection, "certifications", profile_id),
            "skills": section_rows(connection, "skills", profile_id),
            "languages": section_rows(connection, "languages", profile_id),
            "digital_categories": digital_categories(connection, profile_id),
        }


def section_form_payload(section: str, connection: sqlite3.Connection, profile_id: int, is_insert: bool) -> dict[str, Any]:
    config = SECTION_CONFIG[section]
    payload: dict[str, Any] = {"profile_id": profile_id} if is_insert else {}
    default_order = next_sort_order(connection, config["table"], "profile_id", profile_id) if is_insert else 0

    for field in config["fields"]:
        if field == "sort_order":
            if is_insert:
                payload[field] = default_order
            elif field in request.form:
                payload[field] = form_int(field)
        else:
            payload[field] = form_text(field)

    for field in config["booleans"]:
        payload[field] = int(request.form.get(field) == "1")

    return payload


def update_record(connection: sqlite3.Connection, table: str, item_id: int, profile_id: int, values: dict[str, Any]) -> None:
    assignments = ", ".join(f"{field} = ?" for field in values)
    connection.execute(
        f"UPDATE {table} SET {assignments} WHERE id = ? AND profile_id = ?",
        (*values.values(), item_id, profile_id),
    )


def replace_digital_skills(connection: sqlite3.Connection, category_id: int, values_text: str) -> None:
    connection.execute("DELETE FROM digital_skills WHERE digital_category_id = ?", (category_id,))

    lines = [line.strip() for line in values_text.splitlines() if line.strip()]
    for index, line in enumerate(lines, start=1):
        if "||" in line:
            value, value_latex = [part.strip() for part in line.split("||", 1)]
        else:
            value, value_latex = line, ""

        insert_record(
            connection,
            "digital_skills",
            {
                "digital_category_id": category_id,
                "value": value,
                "value_latex": value_latex,
                "sort_order": index,
            },
        )


def selected_ids(name: str) -> list[int]:
    ids: list[int] = []
    for raw_id in request.form.getlist(name):
        try:
            ids.append(int(raw_id))
        except ValueError:
            continue
    return ids


def allowed_profile_item_ids(connection: sqlite3.Connection, table: str, profile_id: int) -> set[int]:
    rows = connection.execute(
        f"SELECT id FROM {table} WHERE profile_id = ?",
        (profile_id,),
    ).fetchall()
    return {int(row["id"]) for row in rows}


def insert_cv_selections(
    connection: sqlite3.Connection,
    cv_id: int,
    profile_id: int,
    selections: dict[str, list[int]],
) -> None:
    for section, config in CV_SELECTION_CONFIG.items():
        allowed_ids = allowed_profile_item_ids(connection, config["source_table"], profile_id)
        ordered_ids = [item_id for item_id in selections.get(section, []) if item_id in allowed_ids]

        for sort_order, item_id in enumerate(ordered_ids, start=1):
            connection.execute(
                f"""
                INSERT OR IGNORE INTO {config['join_table']} (cv_id, {config['join_column']}, sort_order)
                VALUES (?, ?, ?)
                """,
                (cv_id, item_id, sort_order),
            )


def replace_cv_selections(
    connection: sqlite3.Connection,
    cv_id: int,
    profile_id: int,
    selections: dict[str, list[int]],
) -> None:
    for config in CV_SELECTION_CONFIG.values():
        connection.execute(
            f"DELETE FROM {config['join_table']} WHERE cv_id = ?",
            (cv_id,),
        )
    insert_cv_selections(connection, cv_id, profile_id, selections)


def create_cv_for_profile(user_id: int, profile_id: int) -> int:
    title = form_text("title")
    about = form_text("about")
    template_name = form_text("template_name") or "modern-cv"
    selections = {
        section: selected_ids(section)
        for section in CV_SELECTION_CONFIG
    }

    with get_db() as connection:
        cv_id = insert_record(
            connection,
            "cvs",
            {
                "user_id": user_id,
                "profile_id": profile_id,
                "title": title,
                "about": about,
                "cv_type": "personnalisé",
                "template_name": template_name,
            },
        )
        insert_cv_selections(connection, cv_id, profile_id, selections)
        return cv_id


def update_cv_for_profile(user_id: int, cv_id: int, profile_id: int) -> bool:
    title = form_text("title")
    about = form_text("about")
    template_name = form_text("template_name") or "modern-cv"
    selections = {
        section: selected_ids(section)
        for section in CV_SELECTION_CONFIG
    }

    with get_db() as connection:
        cv = connection.execute(
            "SELECT id FROM cvs WHERE id = ? AND user_id = ? AND profile_id = ?",
            (cv_id, user_id, profile_id),
        ).fetchone()
        if cv is None:
            return False

        connection.execute(
            """
            UPDATE cvs
            SET title = ?, about = ?, template_name = ?, pdf_path = '', generated_at = NULL
            WHERE id = ? AND user_id = ?
            """,
            (title, about, template_name, cv_id, user_id),
        )
        replace_cv_selections(connection, cv_id, profile_id, selections)
        return True


def cv_selection_ids(connection: sqlite3.Connection, cv_id: int) -> dict[str, list[int]]:
    selections: dict[str, list[int]] = {}
    for section, config in CV_SELECTION_CONFIG.items():
        rows = connection.execute(
            f"""
            SELECT {config['join_column']} AS item_id
            FROM {config['join_table']}
            WHERE cv_id = ?
            ORDER BY sort_order, {config['join_column']}
            """,
            (cv_id,),
        ).fetchall()
        selections[section] = [int(row["item_id"]) for row in rows]
    return selections


def form_selection_ids() -> dict[str, list[int]]:
    return {
        section: selected_ids(section)
        for section in CV_SELECTION_CONFIG
    }


def load_user_cv(user_id: int, cv_id: int) -> dict[str, Any] | None:
    with get_db() as connection:
        row = connection.execute(
            """
            SELECT id, profile_id, title, about, template_name
            FROM cvs
            WHERE id = ? AND user_id = ?
            """,
            (cv_id, user_id),
        ).fetchone()
        if row is None:
            return None

        cv = dict(row)
        cv["selection_ids"] = cv_selection_ids(connection, cv_id)
        return cv


def cv_selection_counts(connection: sqlite3.Connection, cv_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for section, config in CV_SELECTION_CONFIG.items():
        row = connection.execute(
            f"SELECT COUNT(*) AS count FROM {config['join_table']} WHERE cv_id = ?",
            (cv_id,),
        ).fetchone()
        counts[section] = int(row["count"]) if row else 0
    return counts


def load_user_cvs(user_id: int) -> list[dict[str, Any]]:
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT id, title, about, cv_type, template_name, pdf_path, generated_at, created_at, updated_at
            FROM cvs
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

        cvs = [dict(row) for row in rows]
        for cv in cvs:
            cv["selection_counts"] = cv_selection_counts(connection, int(cv["id"]))
            cv["selection_total"] = sum(cv["selection_counts"].values())
        return cvs


def format_period(start_date: str, end_date: str, is_current: int = 0) -> str:
    start = clean_text(start_date)
    end = "présent" if is_current else clean_text(end_date)

    if start and end:
        return f"{start} -- {end}"
    return start or end


def profile_display_name(profile: dict[str, Any]) -> str:
    name = " ".join(
        part
        for part in [
            clean_text(profile.get("first_name")),
            clean_text(profile.get("last_name")),
        ]
        if part
    ).strip()
    return name.upper() if name else "CV"


def profile_address_lines(profile: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    address_line_1 = clean_text(profile.get("address_line_1"))
    address_line_2 = clean_text(profile.get("address_line_2"))
    locality = " ".join(
        part
        for part in [
            clean_text(profile.get("postal_code")),
            clean_text(profile.get("city")),
        ]
        if part
    ).strip()

    if address_line_1:
        lines.append(address_line_1)
    if address_line_2:
        lines.append(address_line_2)
    elif locality:
        lines.append(locality)

    return lines


def normalize_contact_url(value: str) -> str:
    value = clean_text(value)
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def cv_contact_blocks(profile: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []

    linkedin = clean_text(profile.get("linkedin"))
    if linkedin:
        left.append({"icon": "linkedin", "value": linkedin, "url": normalize_contact_url(linkedin)})
    github = clean_text(profile.get("github"))
    if github:
        right.append({"icon": "github", "value": github, "url": normalize_contact_url(github)})
    if clean_text(profile.get("email")):
        left.append({"icon": "envelope", "value": clean_text(profile.get("email"))})
    if clean_text(profile.get("phone")):
        right.append({"icon": "phone", "value": clean_text(profile.get("phone"))})

    website = clean_text(profile.get("website"))
    if website:
        left.append({"icon": "globe", "value": website, "url": normalize_contact_url(website)})

    address_lines = profile_address_lines(profile)
    if address_lines:
        right.append({"icon": "map-marker", "value_lines": address_lines})

    return {"left": left, "right": right}


def cv_selected_rows(
    connection: sqlite3.Connection,
    cv_id: int,
    section: str,
) -> list[dict[str, Any]]:
    config = CV_SELECTION_CONFIG[section]
    rows = connection.execute(
        f"""
        SELECT source.*
        FROM {config['source_table']} AS source
        JOIN {config['join_table']} AS selected
          ON selected.{config['join_column']} = source.id
        WHERE selected.cv_id = ?
        ORDER BY selected.sort_order, source.sort_order, source.id
        """,
        (cv_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def cv_digital_categories(connection: sqlite3.Connection, cv_id: int) -> list[dict[str, Any]]:
    categories = cv_selected_rows(connection, cv_id, "digital_categories")
    for category in categories:
        skills = connection.execute(
            """
            SELECT value, value_latex
            FROM digital_skills
            WHERE digital_category_id = ?
            ORDER BY sort_order, id
            """,
            (category["id"],),
        ).fetchall()
        category["skills"] = [dict(skill) for skill in skills]
    return categories


def paragraph_list(text: str) -> list[str]:
    normalized = clean_text(text).replace("\r\n", "\n")
    paragraphs = [
        paragraph.strip()
        for paragraph in normalized.split("\n\n")
        if paragraph.strip()
    ]
    return paragraphs or ([normalized] if normalized else [])


def cv_data_from_database(cv_id: int, user_id: int) -> dict[str, Any]:
    data = default_cv_data()

    with get_db() as connection:
        cv = connection.execute(
            """
            SELECT
                c.id AS cv_id,
                c.title AS cv_title,
                c.about AS cv_about,
                c.template_name,
                p.id AS profile_id,
                p.first_name,
                p.last_name,
                p.photo_path,
                p.website,
                p.linkedin,
                p.github,
                p.phone,
                p.email,
                p.address_line_1,
                p.address_line_2,
                p.postal_code,
                p.city,
                p.country
            FROM cvs AS c
            JOIN profiles AS p ON p.id = c.profile_id
            WHERE c.id = ? AND c.user_id = ?
            """,
            (cv_id, user_id),
        ).fetchone()

        if cv is None:
            raise ValueError("CV introuvable.")

        cv_data = dict(cv)
        experiences = cv_selected_rows(connection, cv_id, "experiences")
        educations = cv_selected_rows(connection, cv_id, "educations")
        certifications = cv_selected_rows(connection, cv_id, "certifications")
        skills = cv_selected_rows(connection, cv_id, "skills")
        languages = cv_selected_rows(connection, cv_id, "languages")
        digital = cv_digital_categories(connection, cv_id)

    header = data.setdefault("header", {})
    header["name"] = profile_display_name(cv_data)
    header["title"] = clean_text(cv_data.get("cv_title"))

    photo = data.setdefault("photo", {})
    if clean_text(cv_data.get("photo_path")):
        photo["path"] = clean_text(cv_data.get("photo_path"))

    data["contacts"] = cv_contact_blocks(cv_data)

    sidebar = data.setdefault("sidebar", {})
    about = sidebar.setdefault("about", {})
    about.setdefault("heading", "À propos")
    about["paragraphs"] = paragraph_list(cv_data.get("cv_about", ""))

    formations = sidebar.setdefault("formations", {})
    formations.setdefault("heading", "Formations")
    formations["entries"] = [
        {
            "diploma": education["diploma"],
            "institution": education["institution"],
            "dates": format_period(education["start_date"], education["end_date"]),
        }
        for education in educations
    ]

    certifications_section = sidebar.setdefault("certifications", {})
    certifications_section.setdefault("heading", "Certifications")
    certifications_section.setdefault("subtitle", "")
    certifications_section["entries"] = [
        {
            "diploma": certification["diploma"],
            "institution": certification["institution"],
            "dates": certification["date_obtained"],
        }
        for certification in certifications
    ]

    skills_section = sidebar.setdefault("skills", {})
    skills_section.setdefault("heading", "Compétences")
    skills_section["items"] = [skill["label"] for skill in skills if clean_text(skill["label"])]

    languages_section = sidebar.setdefault("languages", {})
    languages_section.setdefault("heading", "Langues")
    languages_section["items"] = [
        (
            f"{language['language']} ({language['level']})"
            if clean_text(language["level"])
            else language["language"]
        )
        for language in languages
        if clean_text(language["language"])
    ]

    main = data.setdefault("main", {})
    experiences_section = main.setdefault("experiences", {})
    experiences_section.setdefault("heading", "Expérience")
    experiences_section["entries"] = [
        {
            "role": experience["role"],
            "organization": experience["organization"],
            "description": experience["description"],
            "dates": format_period(
                experience["start_date"],
                experience["end_date"],
                int(experience["is_current"] or 0),
            ),
        }
        for experience in experiences
    ]

    digital_section = main.setdefault("digital", {})
    digital_section.setdefault("heading", "Numérique")
    digital_section["categories"] = [
        {
            "label": category["label"],
            "values": [
                {"latex": skill["value_latex"]}
                if clean_text(skill["value_latex"])
                else skill["value"]
                for skill in category["skills"]
                if clean_text(skill["value"]) or clean_text(skill["value_latex"])
            ],
        }
        for category in digital
        if clean_text(category["label"])
    ]

    return data


def copy_build_inputs(work_dir: Path) -> None:
    for path in LATEX_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, work_dir / path.name)

    for path in ASSETS_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, work_dir / path.name)


def copy_photo_input(work_dir: Path, photo_path: str) -> None:
    if not photo_path:
        return

    relative_path = Path(photo_path)
    if relative_path.is_absolute():
        return

    source_path = (PROJECT_ROOT / relative_path).resolve()
    try:
        source_path.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return

    if not source_path.exists():
        return

    destination = work_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)


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


def compile_latex_pdf(work_dir: Path) -> Path:
    if not shutil.which("lualatex"):
        raise RuntimeError("lualatex est introuvable. Installe une distribution TeX pour compiler le PDF.")

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


def is_generated_build_dir(path: Path) -> bool:
    return (
        path.parent == BUILD_DIR
        and path.is_dir()
        and not path.is_symlink()
        and len(path.name) == BUILD_RUN_ID_LENGTH
        and all(character in "0123456789abcdef" for character in path.name)
    )


def cleanup_build_work_dirs() -> None:
    if not BUILD_DIR.exists():
        return

    for path in BUILD_DIR.iterdir():
        if is_generated_build_dir(path):
            shutil.rmtree(path, ignore_errors=True)


def cleanup_previous_generated_pdfs(cv_id: int, keep_pdf: Path) -> None:
    if not GENERATED_PDF_DIR.exists():
        return

    keep_path = keep_pdf.resolve()
    for path in GENERATED_PDF_DIR.glob(f"cv-{cv_id}-*.pdf"):
        if path.resolve() == keep_path or not path.is_file():
            continue
        try:
            path.unlink()
        except OSError:
            pass


def cleanup_previous_build_artifacts(cv_id: int, keep_pdf: Path) -> None:
    cleanup_build_work_dirs()
    cleanup_previous_generated_pdfs(cv_id, keep_pdf)


def generate_pdf_from_data(data: dict[str, Any], source_label: str, cv_id: int) -> Path:
    run_id = uuid.uuid4().hex[:12]
    work_dir = BUILD_DIR / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        copy_build_inputs(work_dir)
        copy_photo_input(work_dir, clean_text(data.get("photo", {}).get("path", "")))

        generated_tex = work_dir / "cv.generated.tex"
        generated_tex.write_text(
            build_document(data, source_file=source_label),
            encoding="utf-8",
        )

        compiled_pdf = compile_latex_pdf(work_dir)

        GENERATED_PDF_DIR.mkdir(parents=True, exist_ok=True)
        output_pdf = GENERATED_PDF_DIR / f"cv-{cv_id}-{run_id}.pdf"
        shutil.copy2(compiled_pdf, output_pdf)
        return output_pdf
    finally:
        if is_generated_build_dir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


def relative_project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def record_failed_cv_generation(cv_id: int, user_id: int, error_message: str) -> None:
    with get_db() as connection:
        cv = connection.execute(
            "SELECT id FROM cvs WHERE id = ? AND user_id = ?",
            (cv_id, user_id),
        ).fetchone()
        if cv is None:
            return

        connection.execute(
            """
            INSERT INTO cv_generations (cv_id, status, error_message, generated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (cv_id, "error", error_message[:4000]),
        )


def generate_cv_pdf_from_database(cv_id: int, user_id: int) -> Path:
    data = cv_data_from_database(cv_id, user_id)
    output_pdf = generate_pdf_from_data(data, f"database:cv:{cv_id}", cv_id)
    stored_path = relative_project_path(output_pdf)

    with get_db() as connection:
        connection.execute(
            """
            UPDATE cvs
            SET pdf_path = ?, generated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (stored_path, cv_id, user_id),
        )
        connection.execute(
            """
            INSERT INTO cv_generations (cv_id, status, pdf_path, generated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (cv_id, "success", stored_path),
        )

    cleanup_previous_build_artifacts(cv_id, output_pdf)
    return output_pdf


def stored_pdf_path(path_value: str) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    resolved = candidate.resolve()

    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None

    return resolved if resolved.exists() else None


@app.get("/")
@login_required
def index():
    return redirect(url_for("list_cvs"))


@app.post("/generate")
@login_required
def generate():
    return redirect(url_for("list_cvs"))


@app.get("/profile")
@login_required
def profile():
    user = current_user()
    assert user is not None
    data = load_profile_data(int(user["id"]))
    return render_template("profile.html", user=user, saved=False, error=None, active_page="profile", **data)


@app.post("/profile")
@login_required
def update_profile():
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))
    values = {field: form_text(field) for field in PROFILE_FIELDS}
    error = None

    try:
        uploaded_photo = save_profile_photo(int(user["id"]))
        if uploaded_photo:
            values["photo_path"] = uploaded_photo
    except ValueError as exc:
        error = str(exc)

    assignments = ", ".join(f"{field} = ?" for field in values)

    if error is None:
        with get_db() as connection:
            connection.execute(
                f"UPDATE profiles SET {assignments} WHERE id = ? AND user_id = ?",
                (*values.values(), profile_data["id"], user["id"]),
            )

    data = load_profile_data(int(user["id"]))
    return render_template(
        "profile.html",
        user=user,
        saved=error is None,
        error=error,
        active_page="profile",
        **data,
    )


@app.post("/profile/<section>/add")
@login_required
def add_profile_section(section: str):
    user = current_user()
    assert user is not None

    if section not in SECTION_CONFIG or not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))
    config = SECTION_CONFIG[section]

    with get_db() as connection:
        payload = section_form_payload(section, connection, int(profile_data["id"]), is_insert=True)
        insert_record(connection, config["table"], payload)

    return redirect(url_for("profile"))


@app.post("/profile/<section>/<int:item_id>/update")
@login_required
def update_profile_section(section: str, item_id: int):
    user = current_user()
    assert user is not None

    if section not in SECTION_CONFIG or not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))
    config = SECTION_CONFIG[section]

    with get_db() as connection:
        payload = section_form_payload(section, connection, int(profile_data["id"]), is_insert=False)
        update_record(connection, config["table"], item_id, int(profile_data["id"]), payload)

    return redirect(url_for("profile"))


@app.post("/profile/<section>/<int:item_id>/delete")
@login_required
def delete_profile_section(section: str, item_id: int):
    user = current_user()
    assert user is not None

    if section not in SECTION_CONFIG or not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))
    table = SECTION_CONFIG[section]["table"]

    with get_db() as connection:
        connection.execute(
            f"DELETE FROM {table} WHERE id = ? AND profile_id = ?",
            (item_id, profile_data["id"]),
        )

    return redirect(url_for("profile"))


@app.post("/profile/<section>/reorder")
@login_required
def reorder_profile_section(section: str):
    user = current_user()
    assert user is not None

    if section not in REORDERABLE_PROFILE_SECTIONS:
        return jsonify({"ok": False, "error": "Section non réordonnable."}), 400

    if not validate_csrf_token():
        return jsonify({"ok": False, "error": "Session expirée."}), 400

    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("item_ids", [])
    item_ids: list[int] = []
    for raw_id in raw_ids:
        try:
            item_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    profile_data = get_or_create_profile(int(user["id"]))
    table = "digital_categories" if section == "digital_categories" else SECTION_CONFIG[section]["table"]

    with get_db() as connection:
        allowed_ids = allowed_profile_item_ids(connection, table, int(profile_data["id"]))
        ordered_ids = [item_id for item_id in item_ids if item_id in allowed_ids]

        for sort_order, item_id in enumerate(ordered_ids, start=1):
            connection.execute(
                f"UPDATE {table} SET sort_order = ? WHERE id = ? AND profile_id = ?",
                (sort_order, item_id, profile_data["id"]),
            )

    return jsonify({"ok": True})


@app.post("/profile/digital-categories/add")
@login_required
def add_digital_category():
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))

    with get_db() as connection:
        category_id = insert_record(
            connection,
            "digital_categories",
            {
                "profile_id": profile_data["id"],
                "label": form_text("label"),
                "sort_order": form_int(
                    "sort_order",
                    next_sort_order(connection, "digital_categories", "profile_id", int(profile_data["id"])),
                ),
            },
        )
        replace_digital_skills(connection, category_id, form_text("skills_text"))

    return redirect(url_for("profile"))


@app.post("/profile/digital-categories/<int:category_id>/update")
@login_required
def update_digital_category(category_id: int):
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))

    with get_db() as connection:
        if "sort_order" in request.form:
            connection.execute(
                """
                UPDATE digital_categories
                SET label = ?, sort_order = ?
                WHERE id = ? AND profile_id = ?
                """,
                (
                    form_text("label"),
                    form_int("sort_order"),
                    category_id,
                    profile_data["id"],
                ),
            )
        else:
            connection.execute(
                """
                UPDATE digital_categories
                SET label = ?
                WHERE id = ? AND profile_id = ?
                """,
                (
                    form_text("label"),
                    category_id,
                    profile_data["id"],
                ),
            )
        owned = connection.execute(
            "SELECT id FROM digital_categories WHERE id = ? AND profile_id = ?",
            (category_id, profile_data["id"]),
        ).fetchone()
        if owned:
            replace_digital_skills(connection, category_id, form_text("skills_text"))

    return redirect(url_for("profile"))


@app.post("/profile/digital-categories/<int:category_id>/delete")
@login_required
def delete_digital_category(category_id: int):
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("profile"))

    profile_data = get_or_create_profile(int(user["id"]))

    with get_db() as connection:
        connection.execute(
            "DELETE FROM digital_categories WHERE id = ? AND profile_id = ?",
            (category_id, profile_data["id"]),
        )

    return redirect(url_for("profile"))


@app.get("/cvs")
@login_required
def list_cvs():
    user = current_user()
    assert user is not None
    notice = None
    if request.args.get("generated"):
        notice = "CV généré. Le téléchargement est disponible dans la liste."
    return render_template(
        "cvs.html",
        user=user,
        cvs=load_user_cvs(int(user["id"])),
        notice=notice,
        error=None,
        active_page="cvs",
    )


@app.get("/cvs/new")
@login_required
def new_cv():
    user = current_user()
    assert user is not None
    data = load_profile_data(int(user["id"]))
    return render_template(
        "cv_form.html",
        user=user,
        error=None,
        form={},
        selected_item_ids={},
        page_title="Créer un CV",
        form_action=url_for("create_cv"),
        submit_label="Créer le CV",
        active_page="new_cv",
        **data,
    )


@app.post("/cvs")
@login_required
def create_cv():
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("new_cv"))

    profile_data = get_or_create_profile(int(user["id"]))
    title = form_text("title")
    about = form_text("about")

    if not title or not about:
        data = load_profile_data(int(user["id"]))
        return render_template(
            "cv_form.html",
            user=user,
            error="Le titre professionnel et la description sont obligatoires.",
            form=request.form,
            selected_item_ids=form_selection_ids(),
            page_title="Créer un CV",
            form_action=url_for("create_cv"),
            submit_label="Créer le CV",
            active_page="new_cv",
            **data,
        ), 400

    create_cv_for_profile(int(user["id"]), int(profile_data["id"]))
    return redirect(url_for("list_cvs"))


@app.get("/cvs/<int:cv_id>/edit")
@login_required
def edit_cv(cv_id: int):
    user = current_user()
    assert user is not None

    cv = load_user_cv(int(user["id"]), cv_id)
    if cv is None:
        return redirect(url_for("list_cvs"))

    data = load_profile_data(int(user["id"]))
    return render_template(
        "cv_form.html",
        user=user,
        error=None,
        form=cv,
        selected_item_ids=cv["selection_ids"],
        page_title="Modifier un CV",
        form_action=url_for("update_cv", cv_id=cv_id),
        submit_label="Enregistrer le CV",
        active_page="cvs",
        **data,
    )


@app.post("/cvs/<int:cv_id>/edit")
@login_required
def update_cv(cv_id: int):
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("edit_cv", cv_id=cv_id))

    profile_data = get_or_create_profile(int(user["id"]))
    title = form_text("title")
    about = form_text("about")

    if not title or not about:
        data = load_profile_data(int(user["id"]))
        return render_template(
            "cv_form.html",
            user=user,
            error="Le titre professionnel et la description sont obligatoires.",
            form=request.form,
            selected_item_ids=form_selection_ids(),
            page_title="Modifier un CV",
            form_action=url_for("update_cv", cv_id=cv_id),
            submit_label="Enregistrer le CV",
            active_page="cvs",
            **data,
        ), 400

    updated = update_cv_for_profile(int(user["id"]), cv_id, int(profile_data["id"]))
    if not updated:
        return redirect(url_for("list_cvs"))

    return redirect(url_for("list_cvs"))


@app.post("/cvs/<int:cv_id>/generate")
@login_required
def generate_cv(cv_id: int):
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("list_cvs"))

    try:
        generate_cv_pdf_from_database(cv_id, int(user["id"]))
    except Exception as exc:
        error = str(exc)
        record_failed_cv_generation(cv_id, int(user["id"]), error)
        return render_template(
            "cvs.html",
            user=user,
            cvs=load_user_cvs(int(user["id"])),
            notice=None,
            error=error[:1200],
            active_page="cvs",
        ), 400

    return redirect(url_for("list_cvs", generated=cv_id))


@app.get("/cvs/<int:cv_id>/download")
@login_required
def download_cv(cv_id: int):
    user = current_user()
    assert user is not None

    with get_db() as connection:
        cv = connection.execute(
            "SELECT title, pdf_path FROM cvs WHERE id = ? AND user_id = ?",
            (cv_id, user["id"]),
        ).fetchone()

    if cv is None:
        return redirect(url_for("list_cvs"))

    pdf_path = stored_pdf_path(cv["pdf_path"])
    if pdf_path is None:
        return render_template(
            "cvs.html",
            user=user,
            cvs=load_user_cvs(int(user["id"])),
            notice=None,
            error="Le PDF généré est introuvable. Relance la génération du CV.",
            active_page="cvs",
        ), 404

    filename = secure_filename(cv["title"]) or f"cv-{cv_id}"
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f"{filename}.pdf",
        mimetype="application/pdf",
    )


@app.post("/cvs/<int:cv_id>/delete")
@login_required
def delete_cv(cv_id: int):
    user = current_user()
    assert user is not None

    if not validate_csrf_token():
        return redirect(url_for("list_cvs"))

    with get_db() as connection:
        connection.execute(
            "DELETE FROM cvs WHERE id = ? AND user_id = ?",
            (cv_id, user["id"]),
        )

    return redirect(url_for("list_cvs"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("list_cvs"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        user = find_active_user_by_email(email)

        if not validate_csrf_token():
            error = "Session expirée. Recharge la page et réessaie."
        elif user is None or not check_password_hash(user["password_hash"], password):
            error = "Identifiants incorrects."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(request.args.get("next") or url_for("list_cvs"))

    return render_template("login.html", error=error, default_email=DEFAULT_USER_EMAIL)


@app.post("/logout")
def logout():
    if not validate_csrf_token():
        return redirect(url_for("list_cvs"))

    session.clear()
    return redirect(url_for("login"))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
