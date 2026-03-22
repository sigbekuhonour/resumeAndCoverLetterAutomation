import io

from docx import Document

import document_engine


def test_build_document_plan_respects_requested_theme():
    plan = document_engine.build_document_plan(
        "resume",
        {
            "name": "Avery Carter",
            "title": "Backend Engineer",
            "summary": "Experienced backend engineer.",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "education": "BSc Computer Science",
            "experiences": [],
            "theme_id": "technical_compact",
        },
    )

    assert plan.theme_id == "technical_compact"
    assert plan.density == "compact"
    assert plan.page_budget == 1


def test_build_document_plan_chooses_compact_theme_for_dense_resume():
    plan = document_engine.build_document_plan(
        "resume",
        {
            "name": "Avery Carter",
            "title": "Backend Engineer",
            "summary": " ".join(["Built APIs and distributed systems."] * 12),
            "skills": {
                "Languages": ["Python", "TypeScript", "SQL", "JavaScript"],
                "Cloud": ["AWS", "GCP", "Azure"],
                "Data": ["PostgreSQL", "MongoDB", "Redis"],
            },
            "education": "BSc Computer Science",
            "experiences": [
                {"company": "A", "role": "One", "dates": "2020-2021", "bullets": ["A", "B", "C"]},
                {"company": "B", "role": "Two", "dates": "2021-2022", "bullets": ["A", "B", "C"]},
                {"company": "C", "role": "Three", "dates": "2022-2023", "bullets": ["A", "B", "C"]},
                {"company": "D", "role": "Four", "dates": "2023-2024", "bullets": ["A", "B", "C"]},
            ],
        },
    )

    assert plan.theme_id == "technical_compact"
    assert plan.layout_metrics["experience_count"] == 4
    assert plan.layout_metrics["bullet_count"] == 8


def test_build_document_plan_compacts_cover_letter():
    plan = document_engine.build_document_plan(
        "cover_letter",
        {
            "name": "Avery Carter",
            "company": "Boam AI",
            "role": "Backend Engineer",
            "paragraphs": [
                "Sentence one. Sentence two. Sentence three. Sentence four.",
                "This paragraph is intentionally very long so that the engine must trim it while still keeping the cover letter useful, direct, and aligned with the one-page target that the planner is enforcing for the final render.",
                "Third paragraph stays in place.",
                "Thank you for your time. I appreciate your consideration. I look forward to speaking with you soon.",
                "This one should be dropped completely.",
            ],
        },
    )

    assert plan.page_budget == 1
    assert plan.layout_metrics["paragraph_count"] == 4
    assert plan.normalized_sections["paragraphs"][0] == "Sentence one. Sentence two. Sentence three."
    assert plan.normalized_sections["paragraphs"][-1] == "Thank you for your time. I appreciate your consideration."


def test_render_document_outputs_expected_cover_letter_structure():
    plan = document_engine.build_document_plan(
        "cover_letter",
        {
            "name": "Avery Carter",
            "company": "Boam AI",
            "role": "Backend Engineer",
            "paragraphs": [
                "I am excited to apply.",
                "I have built backend systems with FastAPI and PostgreSQL.",
                "I would bring strong API and distributed-systems experience to the role.",
                "Thank you for your time and consideration.",
            ],
        },
    )

    rendered = document_engine.render_document(plan)
    document = Document(io.BytesIO(rendered))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    assert paragraphs[0]
    assert paragraphs[1] == "Hiring Manager"
    assert paragraphs[2] == "Boam AI"
    assert paragraphs[3] == "Re: Backend Engineer"
    assert paragraphs[-2] == "Sincerely,"
    assert paragraphs[-1] == "Avery Carter"
