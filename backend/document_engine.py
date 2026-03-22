from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor


COVER_LETTER_MAX_PARAGRAPHS = 4
COVER_LETTER_TARGET_TOTAL_CHARS = 1100
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ThemeSpec:
    theme_id: str
    density: str
    body_font: str
    body_size_pt: float
    body_color: tuple[int, int, int]
    heading_font: str
    heading_size_pt: float
    heading_color: tuple[int, int, int]
    name_size_pt: float
    title_size_pt: float
    title_color: tuple[int, int, int]
    top_margin_in: float
    right_margin_in: float
    bottom_margin_in: float
    left_margin_in: float
    line_spacing: float
    paragraph_after_pt: float
    section_before_pt: float
    section_after_pt: float
    bullet_indent_in: float
    max_resume_experiences: int
    max_bullets_per_experience: int
    summary_target_chars: int
    skills_target_chars: int


@dataclass
class DocumentPlan:
    doc_type: str
    page_budget: int
    theme_id: str
    density: str
    normalized_sections: dict[str, Any]
    section_order: list[str]
    layout_metrics: dict[str, Any]


THEMES: dict[str, ThemeSpec] = {
    "classic_professional": ThemeSpec(
        theme_id="classic_professional",
        density="balanced",
        body_font="Calibri",
        body_size_pt=11.0,
        body_color=(0, 0, 0),
        heading_font="Calibri",
        heading_size_pt=13.0,
        heading_color=(79, 129, 189),
        name_size_pt=23.0,
        title_size_pt=13.0,
        title_color=(90, 90, 90),
        top_margin_in=0.8,
        right_margin_in=1.0,
        bottom_margin_in=0.8,
        left_margin_in=1.0,
        line_spacing=1.02,
        paragraph_after_pt=4.0,
        section_before_pt=10.0,
        section_after_pt=4.0,
        bullet_indent_in=0.23,
        max_resume_experiences=3,
        max_bullets_per_experience=2,
        summary_target_chars=320,
        skills_target_chars=220,
    ),
    "technical_compact": ThemeSpec(
        theme_id="technical_compact",
        density="compact",
        body_font="Calibri",
        body_size_pt=10.5,
        body_color=(15, 15, 15),
        heading_font="Calibri",
        heading_size_pt=12.0,
        heading_color=(58, 110, 165),
        name_size_pt=22.0,
        title_size_pt=12.0,
        title_color=(85, 85, 85),
        top_margin_in=0.65,
        right_margin_in=0.9,
        bottom_margin_in=0.65,
        left_margin_in=0.9,
        line_spacing=1.0,
        paragraph_after_pt=2.0,
        section_before_pt=8.0,
        section_after_pt=3.0,
        bullet_indent_in=0.18,
        max_resume_experiences=4,
        max_bullets_per_experience=2,
        summary_target_chars=260,
        skills_target_chars=260,
    ),
}


def _clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _list_to_text(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    if value in (None, ""):
        return ""
    return str(value).strip()


def _trim_text(text: str, max_chars: int) -> str:
    cleaned = _clean_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned

    shortened = cleaned[:max_chars].rstrip()
    sentence_end = max(shortened.rfind(". "), shortened.rfind("! "), shortened.rfind("? "))
    if sentence_end > max_chars // 2:
        return shortened[:sentence_end + 1].strip()

    shortened = shortened.rsplit(" ", 1)[0].rstrip(",;: ")
    if shortened and shortened[-1] not in ".!?":
        shortened += "."
    return shortened


def _compact_cover_letter_paragraph(text: str, *, max_sentences: int, max_chars: int) -> str:
    cleaned = _clean_whitespace(text)
    if not cleaned:
        return ""

    sentences = SENTENCE_BOUNDARY_RE.split(cleaned)
    if len(sentences) > max_sentences:
        cleaned = " ".join(sentences[:max_sentences]).strip()

    return _trim_text(cleaned, max_chars)


def _normalize_cover_letter_paragraphs(paragraphs) -> list[str]:
    if isinstance(paragraphs, str):
        items = [paragraphs]
    elif isinstance(paragraphs, list):
        items = [str(paragraph) for paragraph in paragraphs]
    else:
        paragraph_text = _list_to_text(paragraphs)
        items = [paragraph_text] if paragraph_text else []

    compacted = [
        _clean_whitespace(paragraph)
        for paragraph in items
        if _clean_whitespace(paragraph)
    ][:COVER_LETTER_MAX_PARAGRAPHS]

    if not compacted:
        return []

    normalized = []
    for index, paragraph in enumerate(compacted):
        is_closing_paragraph = index == len(compacted) - 1 and any(
            token in paragraph.lower()
            for token in ("thank", "appreciate", "welcome the opportunity", "look forward")
        )
        normalized.append(
            _compact_cover_letter_paragraph(
                paragraph,
                max_sentences=2 if is_closing_paragraph else 3,
                max_chars=220 if is_closing_paragraph else 360,
            )
        )

    total_chars = sum(len(paragraph) for paragraph in normalized)
    while total_chars > COVER_LETTER_TARGET_TOTAL_CHARS:
        longest_index = max(range(len(normalized)), key=lambda idx: len(normalized[idx]))
        current = normalized[longest_index]
        tighter_limit = max(180, len(current) - 80)
        updated = _compact_cover_letter_paragraph(
            current,
            max_sentences=2,
            max_chars=tighter_limit,
        )
        if updated == current:
            break
        normalized[longest_index] = updated
        total_chars = sum(len(paragraph) for paragraph in normalized)

    return [paragraph for paragraph in normalized if paragraph]


def _format_resume_skills(skills) -> str:
    if isinstance(skills, str):
        return skills
    if isinstance(skills, list):
        return _list_to_text(skills)
    if isinstance(skills, dict):
        groups = []
        for label, value in skills.items():
            value_text = _list_to_text(value)
            if value_text:
                groups.append(f"{label}: {value_text}")
        return "; ".join(groups)
    return _list_to_text(skills)


def _format_education_entries(education) -> str:
    if isinstance(education, str):
        return education
    if isinstance(education, dict):
        education = [education]
    if isinstance(education, list):
        entries = []
        for item in education:
            if isinstance(item, dict):
                main_parts = [item.get("degree"), item.get("institution")]
                main_text = ", ".join(str(part).strip() for part in main_parts if part)
                detail_parts = [
                    item.get("location"),
                    item.get("dates"),
                    f"GPA {item['gpa']}" if item.get("gpa") else None,
                    f"Average {item['average']}" if item.get("average") else None,
                ]
                details = " | ".join(str(part).strip() for part in detail_parts if part)
                awards_text = _list_to_text(item.get("awards"))
                if awards_text:
                    details = f"{details} | Awards: {awards_text}" if details else f"Awards: {awards_text}"
                if details:
                    entries.append(f"{main_text} ({details})" if main_text else details)
                elif main_text:
                    entries.append(main_text)
            else:
                item_text = str(item).strip()
                if item_text:
                    entries.append(item_text)
        return "; ".join(entries)
    return _list_to_text(education)


def _normalize_resume_experiences(experiences) -> list[dict]:
    if not isinstance(experiences, list):
        return []

    normalized = []
    for item in experiences:
        if not isinstance(item, dict):
            continue

        bullets = item.get("bullets", [])
        if isinstance(bullets, str):
            bullet_list = [bullets]
        elif isinstance(bullets, list):
            bullet_list = [str(bullet).strip() for bullet in bullets if str(bullet).strip()]
        else:
            bullet_text = str(bullets).strip()
            bullet_list = [bullet_text] if bullet_text else []

        normalized.append(
            {
                "company": str(item.get("company", "")).strip(),
                "role": str(item.get("role", "")).strip(),
                "dates": str(item.get("dates", "")).strip(),
                "bullets": bullet_list,
            }
        )

    return normalized


def normalize_document_sections(doc_type: str, sections: dict) -> dict:
    normalized = dict(sections or {})

    if doc_type == "resume":
        normalized["name"] = _list_to_text(normalized.get("name"))
        normalized["title"] = _list_to_text(normalized.get("title"))
        normalized["summary"] = _list_to_text(normalized.get("summary"))
        normalized["skills"] = _format_resume_skills(normalized.get("skills"))
        normalized["education"] = _format_education_entries(normalized.get("education"))
        normalized["experiences"] = _normalize_resume_experiences(normalized.get("experiences"))
        normalized["theme_id"] = _list_to_text(normalized.get("theme_id") or normalized.get("theme"))
        return normalized

    if doc_type == "cover_letter":
        normalized["name"] = _list_to_text(normalized.get("name"))
        normalized["date"] = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
        normalized["hiring_manager"] = _list_to_text(normalized.get("hiring_manager")) or "Hiring Manager"
        normalized["company"] = _list_to_text(normalized.get("company"))
        normalized["role"] = _list_to_text(normalized.get("role"))
        normalized["paragraphs"] = _normalize_cover_letter_paragraphs(normalized.get("paragraphs"))
        normalized["theme_id"] = _list_to_text(normalized.get("theme_id") or normalized.get("theme"))
        return normalized

    return normalized


def _choose_theme(doc_type: str, normalized_sections: dict) -> ThemeSpec:
    requested = normalized_sections.get("theme_id")
    if requested in THEMES:
        return THEMES[requested]

    if doc_type == "cover_letter":
        total_chars = sum(len(paragraph) for paragraph in normalized_sections.get("paragraphs", []))
        return THEMES["technical_compact"] if total_chars > 780 else THEMES["classic_professional"]

    experiences = normalized_sections.get("experiences", [])
    bullet_count = sum(len(item.get("bullets", [])) for item in experiences if isinstance(item, dict))
    density_score = (
        len(normalized_sections.get("summary", "")) // 80
        + len(normalized_sections.get("skills", "")) // 70
        + len(experiences) * 2
        + bullet_count
    )
    if density_score >= 10:
        return THEMES["technical_compact"]
    return THEMES["classic_professional"]


def _plan_resume_sections(normalized_sections: dict, theme: ThemeSpec) -> dict:
    experiences = []
    for item in normalized_sections.get("experiences", [])[: theme.max_resume_experiences]:
        bullets = item.get("bullets", [])[: theme.max_bullets_per_experience]
        experiences.append(
            {
                "company": item.get("company", ""),
                "role": item.get("role", ""),
                "dates": item.get("dates", ""),
                "bullets": [_trim_text(bullet, 120) for bullet in bullets],
            }
        )

    return {
        **normalized_sections,
        "summary": _trim_text(normalized_sections.get("summary", ""), theme.summary_target_chars),
        "skills": _trim_text(normalized_sections.get("skills", ""), theme.skills_target_chars),
        "experiences": experiences,
    }


def _plan_cover_letter_sections(normalized_sections: dict, theme: ThemeSpec) -> dict:
    paragraphs = _normalize_cover_letter_paragraphs(normalized_sections.get("paragraphs"))
    if theme.density == "compact":
        paragraphs = [
            _compact_cover_letter_paragraph(
                paragraph,
                max_sentences=2 if index == len(paragraphs) - 1 else 3,
                max_chars=200 if index == len(paragraphs) - 1 else 320,
            )
            for index, paragraph in enumerate(paragraphs)
        ]

    return {
        **normalized_sections,
        "paragraphs": paragraphs,
    }


def build_document_plan(doc_type: str, sections: dict) -> DocumentPlan:
    normalized_sections = normalize_document_sections(doc_type, sections)
    theme = _choose_theme(doc_type, normalized_sections)

    if doc_type == "resume":
        planned_sections = _plan_resume_sections(normalized_sections, theme)
        layout_metrics = {
            "experience_count": len(planned_sections.get("experiences", [])),
            "bullet_count": sum(len(item.get("bullets", [])) for item in planned_sections.get("experiences", [])),
            "summary_chars": len(planned_sections.get("summary", "")),
            "skills_chars": len(planned_sections.get("skills", "")),
        }
        section_order = ["summary", "experience", "skills", "education"]
        page_budget = 1
    else:
        planned_sections = _plan_cover_letter_sections(normalized_sections, theme)
        layout_metrics = {
            "paragraph_count": len(planned_sections.get("paragraphs", [])),
            "body_chars": sum(len(paragraph) for paragraph in planned_sections.get("paragraphs", [])),
        }
        section_order = ["date", "recipient", "subject", "body", "signature"]
        page_budget = 1

    return DocumentPlan(
        doc_type=doc_type,
        page_budget=page_budget,
        theme_id=theme.theme_id,
        density=theme.density,
        normalized_sections=planned_sections,
        section_order=section_order,
        layout_metrics=layout_metrics,
    )


def serialize_document_plan(plan: DocumentPlan) -> dict[str, Any]:
    return asdict(plan)


def _apply_theme(document: Document, theme: ThemeSpec):
    section = document.sections[0]
    section.top_margin = Inches(theme.top_margin_in)
    section.right_margin = Inches(theme.right_margin_in)
    section.bottom_margin = Inches(theme.bottom_margin_in)
    section.left_margin = Inches(theme.left_margin_in)

    style = document.styles["Normal"]
    style.font.name = theme.body_font
    style.font.size = Pt(theme.body_size_pt)
    style.font.color.rgb = RGBColor(*theme.body_color)
    style.paragraph_format.line_spacing = theme.line_spacing
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(theme.paragraph_after_pt)


def _add_section_heading(document: Document, text: str, theme: ThemeSpec):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(theme.section_before_pt)
    paragraph.paragraph_format.space_after = Pt(theme.section_after_pt)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run(text)
    run.bold = True
    run.font.name = theme.heading_font
    run.font.size = Pt(theme.heading_size_pt)
    run.font.color.rgb = RGBColor(*theme.heading_color)


def _add_body_paragraph(document: Document, text: str, theme: ThemeSpec, *, indent_in: float = 0.0):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(theme.paragraph_after_pt)
    paragraph.paragraph_format.line_spacing = theme.line_spacing
    if indent_in:
        paragraph.paragraph_format.left_indent = Inches(indent_in)
    run = paragraph.add_run(text)
    run.font.name = theme.body_font
    run.font.size = Pt(theme.body_size_pt)
    run.font.color.rgb = RGBColor(*theme.body_color)
    return paragraph


def _render_resume(plan: DocumentPlan) -> bytes:
    theme = THEMES[plan.theme_id]
    sections = plan.normalized_sections

    document = Document()
    _apply_theme(document, theme)

    header = document.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header.paragraph_format.space_after = Pt(4)
    header.paragraph_format.keep_with_next = True
    name_run = header.add_run(sections.get("name", ""))
    name_run.bold = True
    name_run.font.name = theme.heading_font
    name_run.font.size = Pt(theme.name_size_pt)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(theme.section_before_pt)
    title_run = title.add_run(sections.get("title", ""))
    title_run.font.name = theme.body_font
    title_run.font.size = Pt(theme.title_size_pt)
    title_run.font.color.rgb = RGBColor(*theme.title_color)

    if sections.get("summary"):
        _add_section_heading(document, "Summary", theme)
        _add_body_paragraph(document, sections["summary"], theme)

    experiences = sections.get("experiences", [])
    if experiences:
        _add_section_heading(document, "Experience", theme)
        for experience in experiences:
            line = document.add_paragraph()
            line.paragraph_format.keep_with_next = True
            line.paragraph_format.space_before = Pt(0)
            line.paragraph_format.space_after = Pt(theme.paragraph_after_pt)
            line.paragraph_format.tab_stops.add_tab_stop(Inches(6.3), WD_TAB_ALIGNMENT.RIGHT)

            role_run = line.add_run(experience.get("role", ""))
            role_run.bold = True
            role_run.font.size = Pt(theme.body_size_pt)
            role_run.font.name = theme.body_font
            company = experience.get("company", "")
            if company:
                company_run = line.add_run(f" | {company}")
                company_run.font.size = Pt(theme.body_size_pt)
                company_run.font.name = theme.body_font
            dates = experience.get("dates", "")
            if dates:
                dates_run = line.add_run(f"\t{dates}")
                dates_run.font.size = Pt(theme.body_size_pt)
                dates_run.font.name = theme.body_font

            for bullet in experience.get("bullets", []):
                _add_body_paragraph(document, f"• {bullet}", theme, indent_in=theme.bullet_indent_in)

    if sections.get("skills"):
        _add_section_heading(document, "Skills", theme)
        _add_body_paragraph(document, sections["skills"], theme)

    if sections.get("education"):
        _add_section_heading(document, "Education", theme)
        _add_body_paragraph(document, sections["education"], theme)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _render_cover_letter(plan: DocumentPlan) -> bytes:
    theme = THEMES[plan.theme_id]
    sections = plan.normalized_sections

    document = Document()
    _apply_theme(document, theme)

    _add_body_paragraph(document, sections.get("date", ""), theme)

    recipient_lines = [line for line in [sections.get("hiring_manager", ""), sections.get("company", "")] if line]
    for index, line_text in enumerate(recipient_lines):
        recipient = document.add_paragraph()
        recipient.paragraph_format.space_before = Pt(theme.section_before_pt if index == 0 else 0)
        recipient.paragraph_format.space_after = Pt(theme.paragraph_after_pt if index == len(recipient_lines) - 1 else 0)
        recipient.paragraph_format.keep_with_next = True
        line = recipient.add_run(line_text)
        line.font.name = theme.body_font
        line.font.size = Pt(theme.body_size_pt)

    subject = document.add_paragraph()
    subject.paragraph_format.space_before = Pt(theme.section_before_pt)
    subject.paragraph_format.space_after = Pt(theme.section_before_pt)
    subject.paragraph_format.keep_with_next = True
    subject_run = subject.add_run(f"Re: {sections.get('role', '')}")
    subject_run.bold = True
    subject_run.font.name = theme.body_font
    subject_run.font.size = Pt(theme.body_size_pt)

    for paragraph_text in sections.get("paragraphs", []):
        _add_body_paragraph(document, paragraph_text, theme)

    signature = document.add_paragraph()
    signature.paragraph_format.space_before = Pt(theme.section_before_pt)
    signature.paragraph_format.space_after = Pt(0)
    signature.paragraph_format.keep_with_next = True
    sig_run = signature.add_run("Sincerely,")
    sig_run.font.name = theme.body_font
    sig_run.font.size = Pt(theme.body_size_pt)

    name = document.add_paragraph()
    name.paragraph_format.space_before = Pt(0)
    name.paragraph_format.space_after = Pt(0)
    name_run = name.add_run(sections.get("name", ""))
    name_run.font.name = theme.body_font
    name_run.font.size = Pt(theme.body_size_pt)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render_document(plan: DocumentPlan) -> bytes:
    if plan.doc_type == "resume":
        return _render_resume(plan)
    if plan.doc_type == "cover_letter":
        return _render_cover_letter(plan)
    raise ValueError(f"Unsupported doc_type: {plan.doc_type}")
