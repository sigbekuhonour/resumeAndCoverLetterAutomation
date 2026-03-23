from types import SimpleNamespace

import document_filenames
import tools
from document_engine import DocumentPlan
from tools import _merge_context_content, _normalize_document_sections


def test_merge_context_content_merges_nested_dicts():
    existing = {
        "summary": "Backend engineer",
        "location": "Remote",
        "preferences": {
            "remote": True,
            "industries": ["healthcare"],
        },
    }
    incoming = {
        "summary": "Senior backend engineer",
        "preferences": {
            "industries": ["fintech"],
            "salary": "150k+",
        },
    }

    merged = _merge_context_content(existing, incoming)

    assert merged == {
        "summary": "Senior backend engineer",
        "location": "Remote",
        "preferences": {
            "remote": True,
            "industries": ["healthcare", "fintech"],
            "salary": "150k+",
        },
    }


def test_merge_context_content_appends_unique_list_entries():
    existing = [
        {"company": "Acme", "role": "Engineer"},
        {"company": "Globex", "role": "Lead Engineer"},
    ]
    incoming = [
        {"company": "Acme", "role": "Engineer"},
        {"company": "Initech", "role": "Staff Engineer"},
    ]

    merged = _merge_context_content(existing, incoming)

    assert merged == [
        {"company": "Acme", "role": "Engineer"},
        {"company": "Globex", "role": "Lead Engineer"},
        {"company": "Initech", "role": "Staff Engineer"},
    ]


def test_normalize_document_sections_formats_resume_fields_for_template():
    normalized = _normalize_document_sections(
        "resume",
        {
            "summary": "Backend engineer",
            "skills": {
                "Languages": ["Python", "SQL"],
                "Cloud": ["GCP"],
            },
            "education": [
                {
                    "degree": "B.Sc. Computer Science",
                    "institution": "Memorial University",
                    "dates": "2021-2025",
                    "gpa": "3.8",
                }
            ],
            "experiences": [
                {
                    "company": "Acme",
                    "role": "Engineer",
                    "dates": "2022-2024",
                    "bullets": ["Built APIs", "Improved performance"],
                }
            ],
        },
    )

    assert normalized["skills"] == "Languages: Python, SQL; Cloud: GCP"
    assert normalized["education"] == "B.Sc. Computer Science, Memorial University (2021-2025 | GPA 3.8)"
    assert normalized["experiences"] == [
        {
            "company": "Acme",
            "role": "Engineer",
            "dates": "2022-2024",
            "bullets": ["Built APIs", "Improved performance"],
        }
    ]


def test_normalize_document_sections_sets_cover_letter_defaults():
    normalized = _normalize_document_sections(
        "cover_letter",
        {
            "company": "Boam AI",
            "role": "Backend Engineer",
            "paragraphs": ["Paragraph one", "Paragraph two"],
        },
    )

    assert normalized["company"] == "Boam AI"
    assert normalized["role"] == "Backend Engineer"
    assert normalized["hiring_manager"] == "Hiring Manager"
    assert normalized["paragraphs"] == ["Paragraph one", "Paragraph two"]
    assert isinstance(normalized["date"], str)
    assert normalized["date"]


def test_normalize_document_sections_compacts_cover_letter_paragraphs():
    normalized = _normalize_document_sections(
        "cover_letter",
        {
            "company": "Boam AI",
            "role": "Backend Engineer",
            "paragraphs": [
                "Sentence one. Sentence two. Sentence three. Sentence four.",
                "This paragraph is intentionally very long so that the normalizer has to trim it down to a safer size for the cover letter template while keeping it readable and reasonably complete for the final exported document.",
                "Third paragraph stays in place.",
                "Thank you for your time. I appreciate your consideration. I look forward to speaking with you soon.",
                "This paragraph should be dropped.",
            ],
        },
    )

    assert len(normalized["paragraphs"]) == 4
    assert normalized["paragraphs"][0] == "Sentence one. Sentence two. Sentence three."
    assert len(normalized["paragraphs"][1]) <= 360
    assert normalized["paragraphs"][-1] == "Thank you for your time. I appreciate your consideration."


def test_semantic_generated_document_filename_uses_name_role_company():
    filename = document_filenames.semantic_generated_document_filename(
        "resume",
        {
            "name": "Aham Sel",
            "title": "Backend Engineer",
            "company": "Fresha",
        },
    )

    assert filename == "Aham-Sel-Backend-Engineer-Fresha-Resume.docx"


def test_semantic_generated_document_filename_appends_variant_suffix():
    filename = document_filenames.semantic_generated_document_filename(
        "resume",
        {
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
        },
        variant_key="creative_safe",
    )

    assert filename == "Jordan-Vale-Product-Designer-North-Coast-Resume-Creative.docx"


def test_next_versioned_filename_increments_existing_versions():
    filename = document_filenames.next_versioned_filename(
        "Aham-Sel-Backend-Engineer-Fresha-Resume.docx",
        [
            "Aham-Sel-Backend-Engineer-Fresha-Resume.docx",
            "Aham-Sel-Backend-Engineer-Fresha-Resume-v2.docx",
        ],
    )

    assert filename == "Aham-Sel-Backend-Engineer-Fresha-Resume-v3.docx"


class _DummyStorageBucket:
    def __init__(self, sink: list[tuple[str, dict]]):
        self.sink = sink

    def upload(self, path: str, file: bytes, file_options: dict | None = None):
        self.sink.append(("upload", {"path": path, "file": file, "file_options": file_options}))
        return {"path": path}

    def create_signed_url(self, path: str, _expires_in: int):
        return {"signedURL": f"https://example.com/{path}"}


class _DummyStorage:
    def __init__(self, sink: list[tuple[str, dict]]):
        self.sink = sink

    def from_(self, bucket_name: str):
        self.sink.append(("bucket", {"name": bucket_name}))
        return _DummyStorageBucket(self.sink)


class _DummyTable:
    def __init__(self, name: str, sink: list[tuple[str, dict]], generated_documents: list[dict]):
        self.name = name
        self.sink = sink
        self.generated_documents = generated_documents
        self.payload = None
        self.filters: dict[str, str] = {}

    def select(self, _columns: str):
        return self

    def eq(self, key: str, value: str):
        self.filters[key] = value
        return self

    def insert(self, payload: dict):
        self.payload = payload
        self.sink.append((self.name, payload))
        if self.name == "generated_documents":
            self.generated_documents.append(payload)
        return self

    def execute(self):
        if self.name == "generated_documents" and self.payload is None:
            data = [
                row for row in self.generated_documents
                if all(row.get(key) == value for key, value in self.filters.items())
            ]
            return SimpleNamespace(data=data)
        return SimpleNamespace(data=[self.payload] if self.payload else [])


class _DummySupabase:
    def __init__(self, generated_documents: list[dict] | None = None):
        self.events: list[tuple[str, dict]] = []
        self.generated_documents = list(generated_documents or [])
        self.storage = _DummyStorage(self.events)

    def table(self, name: str):
        return _DummyTable(name, self.events, self.generated_documents)


def test_generate_document_sync_emits_progress_events(monkeypatch):
    dummy_supabase = _DummySupabase([
        {
            "user_id": "user-1",
            "filename": "Avery-Carter-Backend-Engineer-Boam-AI-Resume.docx",
        }
    ])
    plan = DocumentPlan(
        doc_type="resume",
        page_budget=1,
        theme_id="technical_compact",
        density="compact",
        normalized_sections={"name": "Avery Carter"},
        section_order=["summary", "experience"],
        layout_metrics={"bullet_count": 4},
        verification={"status": "passed", "issues": []},
        repair_history=[{"action": "reduce_bullets"}],
        attempt_count=2,
    )
    progress_events: list[dict] = []

    monkeypatch.setattr(tools, "supabase", dummy_supabase)
    monkeypatch.setattr(tools, "build_document_plan", lambda doc_type, sections: plan)
    monkeypatch.setattr(tools, "render_document", lambda built_plan: b"fake-docx")
    monkeypatch.setattr(
        tools,
        "serialize_document_plan",
        lambda built_plan: {
            "theme_id": built_plan.theme_id,
            "repair_history": built_plan.repair_history,
            "verification": built_plan.verification,
        },
    )

    result = tools._generate_document_sync(
        "resume",
        {
            "name": "Avery Carter",
            "title": "Backend Engineer",
            "company": "Boam AI",
        },
        "user-1",
        "job-1",
        progress_callback=progress_events.append,
    )

    assert [(event["phase"], event["state"]) for event in progress_events] == [
        ("plan", "running"),
        ("plan", "done"),
        ("repair", "done"),
        ("verify", "done"),
        ("render", "running"),
        ("render", "done"),
        ("save", "running"),
        ("save", "done"),
    ]
    assert result["variant_count"] == 1
    assert result["theme_id"] == "technical_compact"
    assert result["page_budget"] == 1
    assert result["filename"] == "Avery-Carter-Backend-Engineer-Boam-AI-Resume-v2.docx"
    assert any(
        event_name == "generated_documents"
        and payload["doc_type"] == "resume"
        and payload["filename"] == "Avery-Carter-Backend-Engineer-Boam-AI-Resume-v2.docx"
        and payload["source_sections"]["title"] == "Backend Engineer"
        and payload["source_conversation_id"] is None
        for event_name, payload in dummy_supabase.events
    )


def test_generate_document_sync_emits_dual_resume_variants_for_design_roles(monkeypatch):
    dummy_supabase = _DummySupabase()
    progress_events: list[dict] = []
    creative_plan = DocumentPlan(
        doc_type="resume",
        page_budget=1,
        theme_id="modern_minimal",
        density="balanced",
        normalized_sections={
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
            "summary": "Product designer focused on systems and interaction design.",
            "skills": "Design: Figma, Systems",
            "experiences": [],
            "education": "BDes Interaction Design",
        },
        section_order=["summary", "experience", "skills", "education"],
        layout_metrics={"bullet_count": 0},
        verification={"status": "passed", "issues": []},
        repair_history=[],
        attempt_count=1,
    )
    ats_plan = DocumentPlan(
        doc_type="resume",
        page_budget=1,
        theme_id="ats_minimal",
        density="balanced",
        normalized_sections={
            **creative_plan.normalized_sections,
            "layout_strategy": "ats_safe",
        },
        section_order=["summary", "experience", "skills", "education"],
        layout_metrics={"bullet_count": 0},
        verification={"status": "passed", "issues": []},
        repair_history=[],
        attempt_count=1,
    )

    def _build_plan(doc_type, sections):
        if sections.get("layout_strategy") == "ats_safe":
            return ats_plan
        return creative_plan

    monkeypatch.setattr(tools, "supabase", dummy_supabase)
    monkeypatch.setattr(tools, "build_document_plan", _build_plan)
    monkeypatch.setattr(
        tools,
        "render_document",
        lambda built_plan: f"docx-{built_plan.theme_id}".encode(),
    )
    monkeypatch.setattr(
        tools,
        "serialize_document_plan",
        lambda built_plan: {
            "theme_id": built_plan.theme_id,
            "verification": built_plan.verification,
        },
    )

    result = tools._generate_document_sync(
        "resume",
        {
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
        },
        "user-1",
        "job-1",
        progress_callback=progress_events.append,
    )

    assert result["variant_count"] == 2
    assert [doc["variant_label"] for doc in result["documents"]] == [
        "Creative-safe",
        "ATS-safe",
    ]
    assert [doc["theme_id"] for doc in result["documents"]] == [
        "modern_minimal",
        "ats_minimal",
    ]
    assert [doc["filename"] for doc in result["documents"]] == [
        "Jordan-Vale-Product-Designer-North-Coast-Resume-Creative.docx",
        "Jordan-Vale-Product-Designer-North-Coast-Resume-ATS.docx",
    ]
    assert result["variant_group_id"] == result["documents"][0]["variant_group_id"]
    assert result["variant_group_id"] == result["documents"][1]["variant_group_id"]
    assert progress_events[1]["detail"] == "Prepared Creative-safe and ATS-safe variants."
    assert progress_events[-1]["detail"] == "Stored both variants and generated download links."


def test_generate_document_sync_can_regenerate_single_variant(monkeypatch):
    dummy_supabase = _DummySupabase()
    creative_plan = DocumentPlan(
        doc_type="resume",
        page_budget=1,
        theme_id="modern_minimal",
        density="balanced",
        normalized_sections={
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
        },
        section_order=["summary"],
        layout_metrics={"bullet_count": 0},
        verification={"status": "passed", "issues": []},
        repair_history=[],
        attempt_count=1,
    )
    ats_plan = DocumentPlan(
        doc_type="resume",
        page_budget=1,
        theme_id="ats_minimal",
        density="balanced",
        normalized_sections={
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
            "layout_strategy": "ats_safe",
        },
        section_order=["summary"],
        layout_metrics={"bullet_count": 0},
        verification={"status": "passed", "issues": []},
        repair_history=[],
        attempt_count=1,
    )

    def _build_plan(doc_type, sections):
        if sections.get("layout_strategy") == "ats_safe":
            return ats_plan
        return creative_plan

    monkeypatch.setattr(tools, "supabase", dummy_supabase)
    monkeypatch.setattr(tools, "build_document_plan", _build_plan)
    monkeypatch.setattr(
        tools,
        "render_document",
        lambda built_plan: f"docx-{built_plan.theme_id}".encode(),
    )
    monkeypatch.setattr(
        tools,
        "serialize_document_plan",
        lambda built_plan: {"theme_id": built_plan.theme_id},
    )

    result = tools._generate_document_sync(
        "resume",
        {
            "name": "Jordan Vale",
            "title": "Product Designer",
            "company": "North Coast",
        },
        "user-1",
        "job-1",
        conversation_id="conv-1",
        force_variant_key="ats_safe",
        variant_group_id="bundle-1",
    )

    assert result["variant_count"] == 1
    assert result["variant_group_id"] == "bundle-1"
    assert result["variant_key"] == "ats_safe"
    assert result["variant_label"] == "ATS-safe"
    assert result["theme_id"] == "ats_minimal"
    assert result["can_regenerate"] is True
    assert result["filename"] == "Jordan-Vale-Product-Designer-North-Coast-Resume-ATS.docx"
    generated_rows = [
        payload
        for event_name, payload in dummy_supabase.events
        if event_name == "generated_documents"
    ]
    assert len(generated_rows) == 1
    assert generated_rows[0]["variant_group_id"] == "bundle-1"
    assert generated_rows[0]["source_conversation_id"] == "conv-1"
    assert generated_rows[0]["source_sections"]["company"] == "North Coast"


def test_generate_document_sync_marks_render_failures(monkeypatch):
    dummy_supabase = _DummySupabase()
    plan = DocumentPlan(
        doc_type="cover_letter",
        page_budget=1,
        theme_id="classic_professional",
        density="balanced",
        normalized_sections={"name": "Avery Carter"},
        section_order=["body"],
        layout_metrics={"paragraph_count": 3},
        verification={"status": "passed", "issues": []},
        repair_history=[],
        attempt_count=1,
    )
    progress_events: list[dict] = []

    monkeypatch.setattr(tools, "supabase", dummy_supabase)
    monkeypatch.setattr(tools, "build_document_plan", lambda doc_type, sections: plan)
    monkeypatch.setattr(
        tools,
        "render_document",
        lambda built_plan: (_ for _ in ()).throw(RuntimeError("render exploded")),
    )

    result = tools._generate_document_sync(
        "cover_letter",
        {"name": "Avery Carter"},
        "user-1",
        "job-1",
        progress_callback=progress_events.append,
    )

    assert result == {"error": "Document generation failed: render exploded"}
    assert progress_events[-1] == {
        "phase": "render",
        "state": "failed",
        "detail": "render exploded",
    }
