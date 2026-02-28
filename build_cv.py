#!/usr/bin/env python3
"""Generate cv.generated.tex from cv.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

LATEX_SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

ICON_MAP = {
    "phone": r"\faPhone*",
    "envelope": r"\faEnvelope",
    "email": r"\faEnvelope",
    "globe": r"\faGlobe",
    "web": r"\faGlobe",
    "map-marker": r"\faMapMarker*",
    "location": r"\faMapMarker*",
}


def escape_latex(text: str) -> str:
    return "".join(LATEX_SPECIAL_CHARS.get(ch, ch) for ch in text)


def as_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")
    return value


def require(mapping: dict[str, Any], key: str, field_name: str) -> Any:
    if key not in mapping:
        raise KeyError(f"Missing key: {field_name}.{key}")
    return mapping[key]


def render_text(value: Any, field_name: str) -> str:
    if isinstance(value, dict):
        if set(value.keys()) == {"latex"}:
            latex_value = value["latex"]
            if not isinstance(latex_value, str):
                raise TypeError(f"{field_name}.latex must be a string")
            return latex_value
        raise ValueError(
            f"{field_name} supports only {{latex: ...}} for raw LaTeX injection"
        )

    if value is None:
        return ""

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return escape_latex(value)

    raise TypeError(f"Unsupported value type for {field_name}: {type(value).__name__}")


def render_literal(value: Any, field_name: str) -> str:
    if isinstance(value, dict):
        if set(value.keys()) == {"latex"}:
            latex_value = value["latex"]
            if not isinstance(latex_value, str):
                raise TypeError(f"{field_name}.latex must be a string")
            return latex_value
        raise ValueError(
            f"{field_name} supports only {{latex: ...}} for raw LaTeX injection"
        )

    if value is None:
        return ""

    if isinstance(value, (int, float, str)):
        return str(value)

    raise TypeError(f"Unsupported literal type for {field_name}: {type(value).__name__}")


def render_icon(value: Any, field_name: str) -> str:
    if isinstance(value, dict):
        return render_text(value, field_name)

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or {{latex: ...}}")

    if value.startswith("\\"):
        return value

    icon_key = value.strip().lower()
    if icon_key not in ICON_MAP:
        supported = ", ".join(sorted(ICON_MAP.keys()))
        raise ValueError(f"Unknown icon '{value}' in {field_name}. Supported: {supported}")

    return ICON_MAP[icon_key]


def command(name: str, value: str) -> str:
    return f"\\renewcommand{{\\{name}}}{{{value}}}"


def block_command(name: str, lines: list[str]) -> str:
    if lines:
        body = "\n".join(f"  {line}" for line in lines)
    else:
        body = "  %"
    return f"\\renewcommand{{\\{name}}}{{%\n{body}\n}}"


def render_contacts(items: list[Any], field_name: str) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(f"{field_name}[{idx}] must be an object")

        icon = render_icon(require(item, "icon", f"{field_name}[{idx}]"), f"{field_name}[{idx}].icon")

        if "value" in item and "value_lines" in item:
            raise ValueError(f"{field_name}[{idx}] cannot define both value and value_lines")

        if "value_lines" in item:
            value_lines = as_list(item["value_lines"], f"{field_name}[{idx}].value_lines")
            value = r"\newline\small ".join(
                render_text(part, f"{field_name}[{idx}].value_lines[{line_idx}]")
                for line_idx, part in enumerate(value_lines)
            )
        else:
            value = render_text(require(item, "value", f"{field_name}[{idx}]"), f"{field_name}[{idx}].value")

        lines.append(rf"\contactitem{{{icon}}}{{\small {value}}}")

    return lines


def render_formations(entries: list[Any], field_name: str) -> list[str]:
    lines: list[str] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise TypeError(f"{field_name}[{idx}] must be an object")

        diploma = render_text(require(entry, "diploma", f"{field_name}[{idx}]"), f"{field_name}[{idx}].diploma")
        institution = render_text(
            require(entry, "institution", f"{field_name}[{idx}]"),
            f"{field_name}[{idx}].institution",
        )
        dates = render_text(require(entry, "dates", f"{field_name}[{idx}]"), f"{field_name}[{idx}].dates")

        lines.append(rf"\textbf{{{diploma}}}\par")
        if idx < len(entries) - 1:
            lines.append(rf"{institution}\hfill {dates}\par\vspace{{2mm}}")
        else:
            lines.append(rf"{institution}\hfill {dates}\par")

    return lines


def render_experience_description(entry: dict[str, Any], field_name: str) -> str:
    has_description = "description" in entry
    has_bullets = "bullets" in entry

    if has_description and has_bullets:
        raise ValueError(f"{field_name} cannot define both description and bullets")

    if has_description:
        return render_text(entry["description"], f"{field_name}.description")

    if has_bullets:
        bullets = as_list(entry["bullets"], f"{field_name}.bullets")
        rendered = [
            rf"$\bullet$ {render_text(item, f'{field_name}.bullets[{idx}]')}"
            for idx, item in enumerate(bullets)
        ]
        return r" \\ ".join(rendered)

    raise KeyError(f"{field_name} requires either description or bullets")


def render_experiences(entries: list[Any], field_name: str) -> list[str]:
    lines: list[str] = []

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise TypeError(f"{field_name}[{idx}] must be an object")

        role = render_text(require(entry, "role", f"{field_name}[{idx}]"), f"{field_name}[{idx}].role")
        organization = render_text(
            require(entry, "organization", f"{field_name}[{idx}]"),
            f"{field_name}[{idx}].organization",
        )
        dates = render_text(require(entry, "dates", f"{field_name}[{idx}]"), f"{field_name}[{idx}].dates")
        description = render_experience_description(entry, f"{field_name}[{idx}]")

        lines.extend(
            [
                r"\job",
                rf"  {{{role}}}",
                rf"  {{{organization}}}",
                rf"  {{{description}}}",
                rf"  {{{dates}}}",
            ]
        )

    return lines


def render_digital(categories: list[Any], field_name: str) -> list[str]:
    lines: list[str] = []

    for idx, category in enumerate(categories):
        if not isinstance(category, dict):
            raise TypeError(f"{field_name}[{idx}] must be an object")

        label = render_text(require(category, "label", f"{field_name}[{idx}]"), f"{field_name}[{idx}].label")

        if "values" in category:
            values_obj = category["values"]
            if isinstance(values_obj, list):
                values = ", ".join(
                    render_text(v, f"{field_name}[{idx}].values[{value_idx}]")
                    for value_idx, v in enumerate(values_obj)
                )
            else:
                values = render_text(values_obj, f"{field_name}[{idx}].values")
        elif "items" in category:
            items_obj = as_list(category["items"], f"{field_name}[{idx}].items")
            values = ", ".join(
                render_text(v, f"{field_name}[{idx}].items[{value_idx}]")
                for value_idx, v in enumerate(items_obj)
            )
        else:
            raise KeyError(f"{field_name}[{idx}] requires either values or items")

        lines.append(rf"\textbf{{{label} :}} {values}\par")

    return lines


def render_item_lines(items: list[Any], field_name: str) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(items):
        text = render_text(item, f"{field_name}[{idx}]")
        lines.append(rf"\item {text}")
    return lines


def build_document(data: dict[str, Any]) -> str:
    layout = require(data, "layout", "root")
    if not isinstance(layout, dict):
        raise TypeError("layout must be an object")

    header = require(data, "header", "root")
    if not isinstance(header, dict):
        raise TypeError("header must be an object")

    photo = require(data, "photo", "root")
    if not isinstance(photo, dict):
        raise TypeError("photo must be an object")

    contacts = require(data, "contacts", "root")
    if not isinstance(contacts, dict):
        raise TypeError("contacts must be an object")

    sidebar = require(data, "sidebar", "root")
    if not isinstance(sidebar, dict):
        raise TypeError("sidebar must be an object")

    main = require(data, "main", "root")
    if not isinstance(main, dict):
        raise TypeError("main must be an object")

    header_bar = require(layout, "header_bar", "layout")
    if not isinstance(header_bar, dict):
        raise TypeError("layout.header_bar must be an object")

    about = require(sidebar, "about", "sidebar")
    if not isinstance(about, dict):
        raise TypeError("sidebar.about must be an object")

    formations = require(sidebar, "formations", "sidebar")
    if not isinstance(formations, dict):
        raise TypeError("sidebar.formations must be an object")

    certifications = require(sidebar, "certifications", "sidebar")
    if not isinstance(certifications, dict):
        raise TypeError("sidebar.certifications must be an object")

    skills = require(sidebar, "skills", "sidebar")
    if not isinstance(skills, dict):
        raise TypeError("sidebar.skills must be an object")

    languages = require(sidebar, "languages", "sidebar")
    if not isinstance(languages, dict):
        raise TypeError("sidebar.languages must be an object")

    experiences = require(main, "experiences", "main")
    if not isinstance(experiences, dict):
        raise TypeError("main.experiences must be an object")

    digital = require(main, "digital", "main")
    if not isinstance(digital, dict):
        raise TypeError("main.digital must be an object")

    out: list[str] = [
        "% AUTO-GENERATED DO NOT EDIT.",
        "% Generated by build_cv.py from cv.yaml",
        "% !TeX root = main.tex",
        "",
        command("CVSidebarWidthValue", render_literal(require(layout, "sidebar_width", "layout"), "layout.sidebar_width")),
        command("CVPadValue", render_literal(require(layout, "pad", "layout"), "layout.pad")),
        command("CVMainGapValue", render_literal(require(layout, "main_gap", "layout"), "layout.main_gap")),
        command(
            "CVContentTopOffset",
            render_literal(require(layout, "content_top_offset", "layout"), "layout.content_top_offset"),
        ),
        command(
            "CVContactBlockTopShift",
            render_literal(
                require(layout, "contact_block_top_shift", "layout"),
                "layout.contact_block_top_shift",
            ),
        ),
        command(
            "CVHeaderBarLeftOverlap",
            render_literal(
                require(header_bar, "left_overlap", "layout.header_bar"),
                "layout.header_bar.left_overlap",
            ),
        ),
        command(
            "CVHeaderBarTopShift",
            render_literal(
                require(header_bar, "top_shift", "layout.header_bar"),
                "layout.header_bar.top_shift",
            ),
        ),
        command(
            "CVHeaderBarBottomShift",
            render_literal(
                require(header_bar, "bottom_shift", "layout.header_bar"),
                "layout.header_bar.bottom_shift",
            ),
        ),
        "",
        command("CVPhotoPath", render_text(require(photo, "path", "photo"), "photo.path")),
        command("CVPhotoWidth", render_literal(require(photo, "width", "photo"), "photo.width")),
        command("CVPhotoRadius", render_literal(require(photo, "radius", "photo"), "photo.radius")),
        command("CVPhotoXFromPad", render_literal(require(photo, "x_from_pad", "photo"), "photo.x_from_pad")),
        command("CVPhotoYShift", render_literal(require(photo, "y_shift", "photo"), "photo.y_shift")),
        command(
            "CVPhotoBorderWidth",
            render_literal(require(photo, "border_width", "photo"), "photo.border_width"),
        ),
        "",
        command("CVHeaderName", render_text(require(header, "name", "header"), "header.name")),
        command("CVHeaderTitle", render_text(require(header, "title", "header"), "header.title")),
        command(
            "CVHeaderNameSize",
            render_literal(require(header, "name_font_size", "header"), "header.name_font_size"),
        ),
        command(
            "CVHeaderNameLetterSpace",
            render_literal(require(header, "letter_space", "header"), "header.letter_space"),
        ),
        command(
            "CVHeaderNameTitleGap",
            render_literal(require(header, "name_title_gap", "header"), "header.name_title_gap"),
        ),
        "",
        command(
            "CVSidebarAboutHeading",
            render_text(require(about, "heading", "sidebar.about"), "sidebar.about.heading"),
        ),
        command(
            "CVSidebarFormationsHeading",
            render_text(
                require(formations, "heading", "sidebar.formations"),
                "sidebar.formations.heading",
            ),
        ),
        command(
            "CVSidebarCertificationsHeading",
            render_text(
                require(certifications, "heading", "sidebar.certifications"),
                "sidebar.certifications.heading",
            ),
        ),
        command(
            "CVSidebarSkillsHeading",
            render_text(require(skills, "heading", "sidebar.skills"), "sidebar.skills.heading"),
        ),
        command(
            "CVSidebarLanguagesHeading",
            render_text(require(languages, "heading", "sidebar.languages"), "sidebar.languages.heading"),
        ),
        command(
            "CVExperienceHeading",
            render_text(require(experiences, "heading", "main.experiences"), "main.experiences.heading"),
        ),
        command(
            "CVDigitalHeading",
            render_text(require(digital, "heading", "main.digital"), "main.digital.heading"),
        ),
        "",
    ]

    about_paragraphs = as_list(require(about, "paragraphs", "sidebar.about"), "sidebar.about.paragraphs")
    about_lines = [
        f"{render_text(paragraph, f'sidebar.about.paragraphs[{idx}]')}\\par"
        for idx, paragraph in enumerate(about_paragraphs)
    ]
    out.append(block_command("CVSidebarAboutBody", about_lines))
    out.append("")

    formation_entries = as_list(
        require(formations, "entries", "sidebar.formations"),
        "sidebar.formations.entries",
    )
    out.append(block_command("CVSidebarFormationsBody", render_formations(formation_entries, "sidebar.formations.entries")))
    out.append("")

    certification_entries = as_list(
        require(certifications, "entries", "sidebar.certifications"),
        "sidebar.certifications.entries",
    )
    out.append(
        block_command(
            "CVSidebarCertificationsBody",
            render_formations(certification_entries, "sidebar.certifications.entries"),
        )
    )
    out.append("")

    skills_items = as_list(require(skills, "items", "sidebar.skills"), "sidebar.skills.items")
    out.append(
        block_command(
            "CVSidebarSkillsItems",
            render_item_lines(skills_items, "sidebar.skills.items"),
        )
    )
    out.append("")

    language_items = as_list(require(languages, "items", "sidebar.languages"), "sidebar.languages.items")
    out.append(
        block_command(
            "CVSidebarLanguagesItems",
            render_item_lines(language_items, "sidebar.languages.items"),
        )
    )
    out.append("")

    left_contacts = as_list(require(contacts, "left", "contacts"), "contacts.left")
    right_contacts = as_list(require(contacts, "right", "contacts"), "contacts.right")
    out.append(block_command("CVContactLeftBlock", render_contacts(left_contacts, "contacts.left")))
    out.append("")
    out.append(block_command("CVContactRightBlock", render_contacts(right_contacts, "contacts.right")))
    out.append("")

    experience_entries = as_list(
        require(experiences, "entries", "main.experiences"),
        "main.experiences.entries",
    )
    out.append(block_command("CVExperiencesBody", render_experiences(experience_entries, "main.experiences.entries")))
    out.append("")

    categories = as_list(require(digital, "categories", "main.digital"), "main.digital.categories")
    out.append(block_command("CVDigitalBody", render_digital(categories, "main.digital.categories")))
    out.append("")

    return "\n".join(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate cv.generated.tex from cv.yaml")
    parser.add_argument("--input", "-i", default="cv.yaml", help="Input YAML file")
    parser.add_argument("--output", "-o", default="cv.generated.tex", help="Output TeX file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise TypeError("Root YAML node must be an object")

    generated = build_document(data)
    output_path.write_text(generated, encoding="utf-8")

    print(f"Generated {output_path} from {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
