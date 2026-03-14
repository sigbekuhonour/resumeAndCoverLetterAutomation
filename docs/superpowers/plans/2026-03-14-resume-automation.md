# AI Resume & Cover Letter Automation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conversational AI app that generates tailored resumes and cover letters by researching job postings and progressively learning about the user.

**Architecture:** Backend-driven chat — FastAPI orchestrates Gemini 2.5 Flash with function calling (Tavily, Firecrawl, docxtpl). Frontend is a Next.js chat UI that streams responses via SSE directly from Cloud Run. Supabase handles auth, database, and file storage.

**Tech Stack:** Python/FastAPI, Next.js/React, Supabase, Gemini 2.5 Flash, Tavily, Firecrawl, docxtpl, Tailwind CSS

---

## Chunk 1: Project Scaffolding & Database Schema

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/Dockerfile`
- Create: `backend/templates/.gitkeep`
- Create: `frontend/.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Node
node_modules/
.next/
out/

# Environment
.env
.env.local
.env.*.local
backend/.env

# IDE
.vscode/
.idea/

# OS
.DS_Store

# Logs
*.log
firebase-debug.log

# Generated docs
backend/output/
```

- [ ] **Step 2: Create `backend/requirements.txt`**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
python-dotenv==1.1.0
pydantic==2.11.3
pydantic-settings==2.9.1
google-genai==1.14.0
tavily-python==0.5.0
firecrawl-py==1.16.0
docxtpl==0.19.0
supabase==2.15.2
python-jose[cryptography]==3.4.0
sse-starlette==2.3.3
httpx==0.28.1
```

- [ ] **Step 3: Create `backend/.env.example`**

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
GEMINI_API_KEY=your-gemini-api-key
TAVILY_API_KEY=your-tavily-api-key
FIRECRAWL_API_KEY=your-firecrawl-api-key
FRONTEND_URL=http://localhost:3000
```

- [ ] **Step 4: Create `frontend/.env.example`**

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 5: Create `backend/templates/.gitkeep`**

Empty file — placeholder for `.docx` templates added later.

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/requirements.txt backend/.env.example frontend/.env.example backend/templates/.gitkeep
git commit -m "scaffold project structure with backend deps and env examples"
```

---

### Task 2: Supabase Database Schema

**Files:**
- Create: `supabase/migrations/001_initial_schema.sql`

Uses Supabase MCP `apply_migration` to run the SQL.

- [ ] **Step 1: Write the migration SQL**

```sql
-- Create profiles table (extends auth.users)
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  email text,
  created_at timestamptz default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    new.email
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- User context (progressive profile)
create table public.user_context (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  category text not null,
  content jsonb not null default '{}',
  source_conversation_id uuid,
  updated_at timestamptz default now()
);

-- Conversations
create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  mode text not null check (mode in ('job_to_resume', 'find_jobs')),
  title text default 'New conversation',
  status text default 'active' check (status in ('active', 'completed')),
  created_at timestamptz default now()
);

-- Messages
create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

-- Jobs
create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  company text,
  url text,
  description_md text,
  created_at timestamptz default now()
);

-- Generated documents
create table public.generated_documents (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  doc_type text not null check (doc_type in ('resume', 'cover_letter')),
  file_url text not null,
  created_at timestamptz default now()
);

-- Add FK from user_context to conversations (after conversations table exists)
alter table public.user_context
  add constraint fk_user_context_conversation
  foreign key (source_conversation_id)
  references public.conversations(id) on delete set null;

-- Indexes for common queries
create index idx_user_context_user on public.user_context(user_id);
create index idx_conversations_user on public.conversations(user_id);
create index idx_messages_conversation on public.messages(conversation_id);
create index idx_jobs_conversation on public.jobs(conversation_id);
create index idx_generated_documents_job on public.generated_documents(job_id);
create index idx_generated_documents_user on public.generated_documents(user_id);

-- Enable RLS on all tables (backend uses service key so bypasses, but good practice)
alter table public.profiles enable row level security;
alter table public.user_context enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.jobs enable row level security;
alter table public.generated_documents enable row level security;

-- RLS policies: users can only access their own data
create policy "Users can view own profile" on public.profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on public.profiles for update using (auth.uid() = id);

create policy "Users can manage own context" on public.user_context for all using (auth.uid() = user_id);
create policy "Users can manage own conversations" on public.conversations for all using (auth.uid() = user_id);
create policy "Users can manage own messages" on public.messages for all using (
  auth.uid() = (select user_id from public.conversations where id = conversation_id)
);
create policy "Users can manage own jobs" on public.jobs for all using (auth.uid() = user_id);
create policy "Users can manage own documents" on public.generated_documents for all using (auth.uid() = user_id);
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Run: `mcp__plugin_supabase_supabase__apply_migration` with project ID `hwzptzrjqcniukwrjnrb` and the SQL above.

- [ ] **Step 3: Create Supabase Storage bucket**

Run: `mcp__plugin_supabase_supabase__execute_sql` to create the `documents` storage bucket:
```sql
insert into storage.buckets (id, name, public) values ('documents', 'documents', false);

create policy "Users can upload own documents"
  on storage.objects for insert
  with check (bucket_id = 'documents' and auth.uid()::text = (storage.foldername(name))[1]);

create policy "Users can read own documents"
  on storage.objects for select
  using (bucket_id = 'documents' and auth.uid()::text = (storage.foldername(name))[1]);
```

- [ ] **Step 4: Save migration file locally and commit**

Save the SQL to `supabase/migrations/001_initial_schema.sql` for version control.

```bash
git add supabase/
git commit -m "add initial database schema and storage bucket"
```

---

## Chunk 2: Backend Foundation

### Task 3: Config & Database Client

**Files:**
- Create: `backend/config.py`
- Create: `backend/db.py`

- [ ] **Step 1: Write `backend/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str
    gemini_api_key: str
    tavily_api_key: str
    firecrawl_api_key: str
    frontend_url: str = "http://localhost:3000"


settings = Settings()
```

- [ ] **Step 2: Write `backend/db.py`**

```python
from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)
```

- [ ] **Step 3: Verify config loads**

Create `backend/.env` from `backend/.env.example` with real values (user provides keys).

Run: `cd backend && python -c "from config import settings; print(settings.supabase_url)"`
Expected: prints the Supabase URL.

- [ ] **Step 4: Commit**

```bash
git add backend/config.py backend/db.py
git commit -m "add backend config and supabase client"
```

---

### Task 4: Pydantic Models

**Files:**
- Create: `backend/models.py`

- [ ] **Step 1: Write `backend/models.py`**

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ConversationMode(str, Enum):
    job_to_resume = "job_to_resume"
    find_jobs = "find_jobs"


class ConversationStatus(str, Enum):
    active = "active"
    completed = "completed"


class DocType(str, Enum):
    resume = "resume"
    cover_letter = "cover_letter"


class CreateConversationRequest(BaseModel):
    mode: ConversationMode


class SendMessageRequest(BaseModel):
    content: str


class ConversationResponse(BaseModel):
    id: str
    mode: ConversationMode
    title: str
    status: ConversationStatus
    created_at: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: dict = {}
    created_at: str


class DocumentResponse(BaseModel):
    id: str
    job_id: str
    doc_type: DocType
    file_url: str
    created_at: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/models.py
git commit -m "add pydantic request/response models"
```

---

### Task 5: JWT Auth Middleware

**Files:**
- Create: `backend/auth.py`

- [ ] **Step 1: Write `backend/auth.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Decode Supabase JWT and return user ID."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no subject",
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

- [ ] **Step 2: Write test for auth**

Create `backend/tests/test_auth.py`:

```python
import pytest
from jose import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch
from config import settings


def make_token(user_id: str, secret: str = None) -> str:
    """Create a test JWT."""
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated"},
        secret or settings.supabase_jwt_secret,
        algorithm="HS256",
    )


def test_valid_token_returns_user_id():
    from auth import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    import asyncio

    token = make_token("test-user-123")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    result = asyncio.run(get_current_user(creds))
    assert result == "test-user-123"


def test_invalid_token_raises_401():
    from auth import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import HTTPException
    import asyncio

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(creds))
    assert exc_info.value.status_code == 401
```

- [ ] **Step 3: Run tests**

Run: `cd backend && pip install -e . 2>/dev/null; python -m pytest tests/test_auth.py -v`
Expected: 2 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "add JWT auth middleware with tests"
```

---

## Chunk 3: Backend Tools

### Task 6: Tavily Search Tool

**Files:**
- Create: `backend/tools.py`

- [ ] **Step 1: Write Tavily search in `backend/tools.py`**

```python
import os
import uuid
import io
from datetime import datetime, timezone
from tavily import TavilyClient
from firecrawl import FirecrawlApp
from docxtpl import DocxTemplate
from config import settings
from db import supabase


tavily_client = TavilyClient(api_key=settings.tavily_api_key)
firecrawl_client = FirecrawlApp(api_key=settings.firecrawl_api_key)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


async def search_jobs(query: str, location: str | None = None) -> list[dict]:
    """Search for job postings using Tavily."""
    search_query = f"{query} job posting"
    if location:
        search_query += f" {location}"
    try:
        results = tavily_client.search(
            query=search_query,
            max_results=5,
            search_depth="basic",
        )
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:200],
            }
            for r in results.get("results", [])
        ]
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]


async def scrape_job(url: str) -> dict:
    """Scrape a job posting URL using Firecrawl."""
    try:
        result = firecrawl_client.scrape_url(url, params={"formats": ["markdown"]})
        markdown = getattr(result, "markdown", "") or ""
        return {
            "description_md": markdown,
            "url": url,
        }
    except Exception as e:
        return {"error": f"Scraping failed: {str(e)}"}


async def generate_document(
    doc_type: str,
    sections: dict,
    user_id: str,
    job_id: str,
) -> dict:
    """Generate a .docx document from template and upload to Supabase Storage."""
    template_path = os.path.join(TEMPLATE_DIR, f"{doc_type}.docx")
    try:
        doc = DocxTemplate(template_path)
        doc.render(sections)

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        doc_id = str(uuid.uuid4())
        storage_path = f"{user_id}/{doc_id}.docx"

        supabase.storage.from_("documents").upload(
            path=storage_path,
            file=buffer.getvalue(),
            file_options={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        )

        signed_url = supabase.storage.from_("documents").create_signed_url(
            storage_path, 3600
        )

        # Save document record
        supabase.table("generated_documents").insert({
            "id": doc_id,
            "job_id": job_id,
            "user_id": user_id,
            "doc_type": doc_type,
            "file_url": storage_path,
        }).execute()

        return {
            "document_id": doc_id,
            "download_url": signed_url.get("signedURL", ""),
        }
    except Exception as e:
        return {"error": f"Document generation failed: {str(e)}"}


async def save_user_context(
    user_id: str,
    category: str,
    content: dict,
    conversation_id: str | None = None,
) -> dict:
    """Save or update user context in Supabase."""
    try:
        existing = (
            supabase.table("user_context")
            .select("id")
            .eq("user_id", user_id)
            .eq("category", category)
            .execute()
        )

        if existing.data:
            supabase.table("user_context").update({
                "content": content,
                "source_conversation_id": conversation_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase.table("user_context").insert({
                "user_id": user_id,
                "category": category,
                "content": content,
                "source_conversation_id": conversation_id,
            }).execute()

        return {"status": "saved", "category": category}
    except Exception as e:
        return {"error": f"Context save failed: {str(e)}"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/tools.py
git commit -m "add tool implementations for Tavily, Firecrawl, docxtpl, and context"
```

---

### Task 7: Chat Orchestration (Gemini + SSE)

**Files:**
- Create: `backend/chat.py`

This is the core of the application — manages the Gemini conversation with function calling and streams responses via SSE.

- [ ] **Step 1: Write `backend/chat.py`**

```python
import json
from typing import AsyncGenerator
from google import genai
from google.genai import types
from sse_starlette.sse import ServerSentEvent
from config import settings
from db import supabase
import tools

gemini_client = genai.Client(api_key=settings.gemini_api_key)

MODEL = "gemini-2.5-flash"

# Gemini function declarations
TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_jobs",
            description="Search the web for job postings matching a query. Use when the user describes a role they want or asks to find jobs.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="Job search query, e.g. 'Senior Python Developer'"),
                    "location": types.Schema(type=types.Type.STRING, description="Job location, e.g. 'New York' or 'remote'"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="scrape_job",
            description="Extract the full job description from a URL. Use after finding a job URL or when the user provides one.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "url": types.Schema(type=types.Type.STRING, description="URL of the job posting"),
                },
                required=["url"],
            ),
        ),
        types.FunctionDeclaration(
            name="generate_document",
            description="Generate a resume or cover letter as a .docx file. Use only after you have gathered enough information about the user and the job.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "doc_type": types.Schema(type=types.Type.STRING, description="'resume' or 'cover_letter'"),
                    "sections": types.Schema(
                        type=types.Type.OBJECT,
                        description="Template variables. Resume: {name, title, summary, experiences: [{company, role, dates, bullets}], skills, education}. Cover letter: {name, date, company, hiring_manager, role, paragraphs: [str]}",
                    ),
                },
                required=["doc_type", "sections"],
            ),
        ),
        types.FunctionDeclaration(
            name="save_user_context",
            description="Save information you've learned about the user for future conversations. Use when the user shares their work experience, skills, education, or other profile info.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category": types.Schema(type=types.Type.STRING, description="Category: 'work_experience', 'skills', 'education', 'certifications', 'personal_info', or 'preferences'"),
                    "content": types.Schema(type=types.Type.OBJECT, description="Structured data about this category"),
                },
                required=["category", "content"],
            ),
        ),
    ]
)

SYSTEM_PROMPTS = {
    "job_to_resume": """You are a career assistant helping the user create a tailored resume and cover letter for a specific job.

Your workflow:
1. Ask the user what position they're interested in, or accept a job URL
2. Use search_jobs to find the posting, or scrape_job if they give a URL
3. Analyze the job requirements
4. Ask the user targeted questions about their relevant experience, skills, and education — one or two questions at a time, not everything at once
5. When you learn something important about the user, use save_user_context to remember it
6. Once you have enough info, use generate_document to create the resume and cover letter

Be conversational and helpful. Ask specific questions based on what the job requires. Don't ask for information you already have from the user's context.""",

    "find_jobs": """You are a career assistant helping the user find jobs that match their profile.

Your workflow:
1. Review the user's existing context to understand their background
2. Ask what kind of roles they're looking for (or suggest based on their profile)
3. Use search_jobs to find matching positions
4. Present the results and let the user pick which ones interest them
5. For selected jobs, use scrape_job to get full details
6. Generate tailored documents using generate_document

Be proactive in suggesting roles based on the user's skills and experience.""",
}


def _build_context_prompt(user_id: str) -> str:
    """Load user context from Supabase and format as a prompt section."""
    result = supabase.table("user_context").select("category, content").eq("user_id", user_id).execute()
    if not result.data:
        return "No prior information about this user."
    parts = ["Here is what you already know about this user:"]
    for ctx in result.data:
        parts.append(f"\n**{ctx['category']}:** {json.dumps(ctx['content'])}")
    return "\n".join(parts)


def _build_history(conversation_id: str) -> list[types.Content]:
    """Load conversation history from Supabase and format for Gemini."""
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    contents = []
    for msg in result.data:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    return contents


async def _execute_tool(
    function_call: types.FunctionCall,
    user_id: str,
    conversation_id: str,
    job_id: str | None,
) -> tuple[dict, str | None]:
    """Execute a Gemini function call and return result + optional updated job_id."""
    name = function_call.name
    args = dict(function_call.args) if function_call.args else {}

    if name == "search_jobs":
        result = await tools.search_jobs(**args)
    elif name == "scrape_job":
        result = await tools.scrape_job(**args)
        # Save the scraped job
        if "error" not in result:
            job_data = supabase.table("jobs").insert({
                "conversation_id": conversation_id,
                "user_id": user_id,
                "title": args.get("url", ""),
                "url": args.get("url", ""),
                "description_md": result.get("description_md", ""),
            }).execute()
            if job_data.data:
                job_id = job_data.data[0]["id"]
    elif name == "generate_document":
        if not job_id:
            result = {"error": "No job has been scraped yet in this conversation."}
        else:
            result = await tools.generate_document(
                doc_type=args.get("doc_type", "resume"),
                sections=args.get("sections", {}),
                user_id=user_id,
                job_id=job_id,
            )
    elif name == "save_user_context":
        result = await tools.save_user_context(
            user_id=user_id,
            category=args.get("category", ""),
            content=args.get("content", {}),
            conversation_id=conversation_id,
        )
    else:
        result = {"error": f"Unknown tool: {name}"}

    return result, job_id


async def stream_chat(
    conversation_id: str,
    user_id: str,
    user_message: str,
    mode: str,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Stream a chat response with function calling via SSE."""

    # Save user message
    supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": user_message,
    }).execute()

    # Build prompt
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["job_to_resume"])
    context_prompt = _build_context_prompt(user_id)
    full_system = f"{system_prompt}\n\n{context_prompt}"

    # Build history
    history = _build_history(conversation_id)

    # Track job_id for document generation
    existing_jobs = supabase.table("jobs").select("id").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(1).execute()
    job_id = existing_jobs.data[0]["id"] if existing_jobs.data else None

    # Create chat contents
    contents = history

    full_response = ""
    max_tool_rounds = 5  # prevent infinite tool loops

    for tool_round in range(max_tool_rounds):
        # Use streaming to send text chunks to the client in real-time
        has_function_call = False
        function_call_content = None

        response_stream = gemini_client.models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=full_system,
                tools=[TOOL_DECLARATIONS],
                temperature=0.7,
            ),
        )

        for chunk in response_stream:
            if not chunk.candidates or not chunk.candidates[0].content.parts:
                continue

            for part in chunk.candidates[0].content.parts:
                if part.function_call:
                    has_function_call = True
                    fc = part.function_call
                    function_call_content = chunk.candidates[0].content

                    # Emit status event
                    yield ServerSentEvent(
                        data=json.dumps({"tool": fc.name, "state": "running"}),
                        event="status",
                    )

                    # Execute tool
                    result, job_id = await _execute_tool(fc, user_id, conversation_id, job_id)

                    # Emit status done
                    yield ServerSentEvent(
                        data=json.dumps({"tool": fc.name, "state": "done"}),
                        event="status",
                    )

                    # Emit document event if a document was generated
                    if fc.name == "generate_document" and "document_id" in result:
                        yield ServerSentEvent(
                            data=json.dumps(result),
                            event="document",
                        )

                    # Add function call and result to contents for next round
                    contents.append(function_call_content)
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response=result,
                        )],
                    ))
                    break  # Process one function call at a time

                elif part.text:
                    full_response += part.text
                    yield ServerSentEvent(
                        data=json.dumps({"content": part.text}),
                        event="message",
                    )

            if has_function_call:
                break  # Break out of chunk loop to start next tool round

        if not has_function_call:
            break

    # Save assistant response
    if full_response:
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": full_response,
        }).execute()
```

- [ ] **Step 2: Commit**

```bash
git add backend/chat.py
git commit -m "add Gemini chat orchestration with function calling and SSE streaming"
```

---

## Chunk 4: Backend API & Deployment

### Task 8: FastAPI Routes

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Write `backend/main.py`**

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from config import settings
from auth import get_current_user
from db import supabase
from models import (
    CreateConversationRequest,
    SendMessageRequest,
    ConversationResponse,
    MessageResponse,
)
from chat import stream_chat

app = FastAPI(title="Resume & Cover Letter AI", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    body: CreateConversationRequest,
    user_id: str = Depends(get_current_user),
):
    result = supabase.table("conversations").insert({
        "user_id": user_id,
        "mode": body.mode,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    row = result.data[0]
    return ConversationResponse(
        id=row["id"],
        mode=row["mode"],
        title=row["title"],
        status=row["status"],
        created_at=row["created_at"],
    )


@app.get("/conversations")
async def list_conversations(user_id: str = Depends(get_current_user)):
    result = (
        supabase.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@app.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
):
    conv = (
        supabase.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )

    return {**conv.data, "messages": messages.data}


@app.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user),
):
    # Verify conversation belongs to user
    conv = (
        supabase.table("conversations")
        .select("mode")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        async for event in stream_chat(
            conversation_id=conversation_id,
            user_id=user_id,
            user_message=body.content,
            mode=conv.data["mode"],
        ):
            yield event

    return EventSourceResponse(event_generator())


@app.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    user_id: str = Depends(get_current_user),
):
    doc = (
        supabase.table("generated_documents")
        .select("*")
        .eq("id", document_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    signed = supabase.storage.from_("documents").create_signed_url(
        doc.data["file_url"], 3600
    )
    return {"download_url": signed.get("signedURL", signed.get("signedUrl", ""))}
```

- [ ] **Step 2: Test the server starts**

Run: `cd backend && uvicorn main:app --reload --port 8000`
Expected: Server starts, `GET /health` returns `{"status": "ok"}`.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "add FastAPI routes for conversations, messages, and documents"
```

---

### Task 9: Dockerfile

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Verify Docker build**

Run: `cd backend && docker build -t resume-api .`
Expected: Image builds successfully.

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "add Dockerfile for backend"
```

---

## Chunk 5: Document Templates

### Task 10: Create .docx Templates

**Files:**
- Create: `backend/templates/resume.docx`
- Create: `backend/templates/cover_letter.docx`

These need to be created programmatically using `python-docx` since we can't hand-craft binary .docx files. We'll create a script that generates the initial templates with Jinja2 placeholders.

- [ ] **Step 1: Create template generator script**

Create `backend/create_templates.py`:

```python
"""Generate initial .docx templates with Jinja2 placeholders for docxtpl."""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os


def create_resume_template():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Name header
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("{{ name }}")
    run.bold = True
    run.font.size = Pt(24)

    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("{{ title }}")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph()

    # Summary
    doc.add_heading("Summary", level=2)
    doc.add_paragraph("{{ summary }}")

    # Experience — use Jinja2 for loop with paragraph-level tags
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("{% for exp in experiences %}")
    p = doc.add_paragraph()
    run = p.add_run("{{ exp.role }}")
    run.bold = True
    p.add_run(" | {{ exp.company }} | {{ exp.dates }}")
    doc.add_paragraph("{% for bullet in exp.bullets %}")
    doc.add_paragraph("• {{ bullet }}")
    doc.add_paragraph("{% endfor %}")
    doc.add_paragraph("{% endfor %}")

    # Skills
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("{{ skills }}")

    # Education
    doc.add_heading("Education", level=2)
    doc.add_paragraph("{{ education }}")

    os.makedirs("templates", exist_ok=True)
    doc.save("templates/resume.docx")
    print("Created templates/resume.docx")


def create_cover_letter_template():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Date and header
    doc.add_paragraph("{{ date }}")
    doc.add_paragraph()
    doc.add_paragraph("{{ hiring_manager }}")
    doc.add_paragraph("{{ company }}")
    doc.add_paragraph()
    doc.add_paragraph("Re: {{ role }}")
    doc.add_paragraph()

    # Body paragraphs
    doc.add_paragraph("{% for para in paragraphs %}")
    doc.add_paragraph("{{ para }}")
    doc.add_paragraph("{% endfor %}")

    doc.add_paragraph()
    doc.add_paragraph("Sincerely,")
    doc.add_paragraph("{{ name }}")

    os.makedirs("templates", exist_ok=True)
    doc.save("templates/cover_letter.docx")
    print("Created templates/cover_letter.docx")


if __name__ == "__main__":
    create_resume_template()
    create_cover_letter_template()
```

- [ ] **Step 2: Run the script to generate templates**

Run: `cd backend && pip install python-docx && python create_templates.py`
Expected: `templates/resume.docx` and `templates/cover_letter.docx` created.

- [ ] **Step 3: Verify templates work with docxtpl**

Run a quick test:
```bash
cd backend && python -c "
from docxtpl import DocxTemplate
doc = DocxTemplate('templates/resume.docx')
doc.render({
    'name': 'Jane Doe',
    'title': 'Software Engineer',
    'summary': 'Experienced developer.',
    'experiences': [{'role': 'Engineer', 'company': 'Acme', 'dates': '2020-2024', 'bullets': ['Built APIs', 'Led team']}],
    'skills': 'Python, JavaScript',
    'education': 'BS Computer Science',
})
doc.save('templates/test_output.docx')
print('Template renders OK')
"
```
Expected: prints "Template renders OK", creates `templates/test_output.docx`.
Clean up: `rm backend/templates/test_output.docx`

- [ ] **Step 4: Commit**

```bash
git add backend/create_templates.py backend/templates/resume.docx backend/templates/cover_letter.docx
git commit -m "add docx templates for resume and cover letter"
```

---

## Chunk 6: Frontend Setup & Auth

### Task 11: Next.js Project Scaffolding

**Files:**
- Create: `frontend/` (via `create-next-app`)

- [ ] **Step 1: Create Next.js app**

Run:
```bash
cd /Users/aham/projects/dev/resumeAndCoverLetterAutomation
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
```

Accept defaults. This creates the full Next.js project in `frontend/`.

- [ ] **Step 2: Install Supabase dependencies**

Run:
```bash
cd frontend && npm install @supabase/supabase-js @supabase/ssr
```

- [ ] **Step 3: Set up `frontend/.env.local`**

Copy from `.env.example` and fill in real values.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "scaffold Next.js frontend with Tailwind and Supabase deps"
```

---

### Task 12: Supabase Auth Integration

**Files:**
- Create: `frontend/src/lib/supabase/client.ts`
- Create: `frontend/src/lib/supabase/server.ts`
- Create: `frontend/src/lib/supabase/middleware.ts`
- Modify: `frontend/src/middleware.ts`
- Create: `frontend/src/app/login/page.tsx`

- [ ] **Step 1: Create browser client**

`frontend/src/lib/supabase/client.ts`:

```typescript
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

- [ ] **Step 2: Create server client**

`frontend/src/lib/supabase/server.ts`:

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet) => {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // setAll called from Server Component — ignored
          }
        },
      },
    }
  );
}
```

- [ ] **Step 3: Create middleware helper**

`frontend/src/lib/supabase/middleware.ts`:

```typescript
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user && !request.nextUrl.pathname.startsWith("/login")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (user && request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/chat", request.url));
  }

  return response;
}
```

- [ ] **Step 4: Create middleware**

`frontend/src/middleware.ts`:

```typescript
import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
```

- [ ] **Step 5: Create login page**

`frontend/src/app/login/page.tsx`:

```tsx
"use client";

import { createClient } from "@/lib/supabase/client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const supabase = createClient();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const { error } = isSignUp
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    router.push("/chat");
  };

  const handleGoogleAuth = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Resume AI</h1>
          <p className="mt-2 text-gray-600">
            Generate tailored resumes and cover letters
          </p>
        </div>

        <button
          onClick={handleGoogleAuth}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </button>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">or</span>
          </div>
        </div>

        <form onSubmit={handleEmailAuth} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
          />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? "..." : isSignUp ? "Sign up" : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
          <button
            onClick={() => setIsSignUp(!isSignUp)}
            className="text-blue-600 hover:underline"
          >
            {isSignUp ? "Sign in" : "Sign up"}
          </button>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create auth callback route**

`frontend/src/app/auth/callback/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);
  }

  return NextResponse.redirect(`${origin}/chat`);
}
```

- [ ] **Step 7: Test login page renders**

Run: `cd frontend && npm run dev`
Visit `http://localhost:3000` — should redirect to `/login` and show the login form.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/ frontend/src/middleware.ts frontend/src/app/login/ frontend/src/app/auth/
git commit -m "add Supabase auth with Google and email/password login"
```

---

## Chunk 7: Frontend Chat UI

### Task 13: App Layout with Sidebar

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create API helper**

`frontend/src/lib/api.ts`:

```typescript
import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session?.access_token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res;
}

export async function apiJson<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await apiFetch(path, options);
  return res.json();
}
```

- [ ] **Step 2: Create Sidebar component**

`frontend/src/components/Sidebar.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { apiJson } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

interface Conversation {
  id: string;
  title: string;
  mode: string;
  created_at: string;
}

export default function Sidebar() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [mode, setMode] = useState<"job_to_resume" | "find_jobs">(
    "job_to_resume"
  );
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    apiJson<Conversation[]>("/conversations").then(setConversations).catch(console.error);
  }, [pathname]);

  const handleNew = async () => {
    const conv = await apiJson<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    router.push(`/chat/${conv.id}`);
  };

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  };

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold">Resume AI</h1>
      </div>

      <div className="p-3">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
          className="w-full p-2 bg-gray-800 rounded text-sm"
        >
          <option value="job_to_resume">Job → Resume</option>
          <option value="find_jobs">Find Jobs</option>
        </select>
        <button
          onClick={handleNew}
          className="w-full mt-2 p-2 bg-blue-600 rounded hover:bg-blue-700 transition text-sm"
        >
          + New Chat
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => router.push(`/chat/${c.id}`)}
            className={`w-full text-left p-2 rounded text-sm truncate hover:bg-gray-800 transition ${
              pathname === `/chat/${c.id}` ? "bg-gray-800" : ""
            }`}
          >
            {c.title}
          </button>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-700">
        <button
          onClick={() => router.push("/history")}
          className="w-full p-2 text-sm text-gray-400 hover:text-white transition"
        >
          History
        </button>
        <button
          onClick={handleSignOut}
          className="w-full p-2 text-sm text-gray-400 hover:text-white transition"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Update layout**

Replace `frontend/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Resume AI",
  description: "Generate tailored resumes and cover letters with AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Create chat layout with sidebar**

`frontend/src/app/(app)/layout.tsx`:

```tsx
import Sidebar from "@/components/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 flex flex-col">{children}</main>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/Sidebar.tsx frontend/src/app/layout.tsx frontend/src/app/\(app\)/
git commit -m "add app layout with sidebar and API helper"
```

---

### Task 14: Chat Page with SSE Streaming

**Files:**
- Create: `frontend/src/app/(app)/chat/[id]/page.tsx`
- Create: `frontend/src/components/ChatMessage.tsx`
- Create: `frontend/src/components/StatusPill.tsx`
- Create: `frontend/src/components/DownloadCard.tsx`
- Create: `frontend/src/app/(app)/chat/page.tsx`

- [ ] **Step 1: Create ChatMessage component**

`frontend/src/components/ChatMessage.tsx`:

```tsx
interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  return (
    <div
      className={`flex ${role === "user" ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[70%] px-4 py-3 rounded-2xl ${
          role === "user"
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        <p className="whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create StatusPill component**

`frontend/src/components/StatusPill.tsx`:

```tsx
interface StatusPillProps {
  tool: string;
  state: "running" | "done";
}

const TOOL_LABELS: Record<string, string> = {
  search_jobs: "Searching for jobs",
  scrape_job: "Reading job posting",
  generate_document: "Generating document",
  save_user_context: "Saving your info",
};

export default function StatusPill({ tool, state }: StatusPillProps) {
  const label = TOOL_LABELS[tool] || tool;
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
      {state === "running" ? (
        <span className="inline-block w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
      ) : (
        <span className="inline-block w-2 h-2 bg-green-400 rounded-full" />
      )}
      {label}
      {state === "running" ? "..." : " — done"}
    </div>
  );
}
```

- [ ] **Step 3: Create DownloadCard component**

`frontend/src/components/DownloadCard.tsx`:

```tsx
interface DownloadCardProps {
  docType: string;
  downloadUrl: string;
}

export default function DownloadCard({ docType, downloadUrl }: DownloadCardProps) {
  const label = docType === "resume" ? "Resume" : "Cover Letter";
  return (
    <div className="inline-flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg mb-4">
      <svg
        className="w-8 h-8 text-green-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <div>
        <p className="font-medium text-green-800">{label} ready</p>
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-green-600 hover:underline"
        >
          Download .docx
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create chat page**

`frontend/src/app/(app)/chat/[id]/page.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, apiJson } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import ChatMessage from "@/components/ChatMessage";
import StatusPill from "@/components/StatusPill";
import DownloadCard from "@/components/DownloadCard";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface StatusEvent {
  tool: string;
  state: "running" | "done";
}

interface DocumentEvent {
  document_id: string;
  doc_type: string;
  download_url: string;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [statuses, setStatuses] = useState<StatusEvent[]>([]);
  const [documents, setDocuments] = useState<DocumentEvent[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load existing messages
  useEffect(() => {
    apiJson<{ messages: Message[] }>(`/conversations/${id}`)
      .then((data) => setMessages(data.messages || []))
      .catch(console.error);
  }, [id]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statuses]);

  const sendMessage = async () => {
    if (!input.trim() || streaming) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setStreaming(true);
    setStatuses([]);

    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${API_URL}/conversations/${id}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.access_token}`,
          },
          body: JSON.stringify({ content: userMsg }),
        }
      );

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantContent = "";
      let buffer = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let eventType = "message";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const data = JSON.parse(line.slice(6));

              if (eventType === "message") {
                assistantContent += data.content;
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      content: assistantContent,
                    };
                  } else {
                    updated.push({ role: "assistant", content: assistantContent });
                  }
                  return updated;
                });
              } else if (eventType === "status") {
                setStatuses((prev) => {
                  const existing = prev.findIndex((s) => s.tool === data.tool);
                  if (existing >= 0) {
                    const updated = [...prev];
                    updated[existing] = data;
                    return updated;
                  }
                  return [...prev, data];
                });
              } else if (eventType === "document") {
                setDocuments((prev) => [...prev, data]);
              } else if (eventType === "error") {
                setMessages((prev) => [
                  ...prev,
                  { role: "assistant", content: `Error: ${data.message}` },
                ]);
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Stream error:", err);
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-xl font-medium">Start a conversation</p>
            <p className="text-sm mt-2">
              Describe the job you want to apply for, or paste a job URL.
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} />
        ))}
        {statuses.map((s, i) => (
          <StatusPill key={`${s.tool}-${i}`} tool={s.tool} state={s.state} />
        ))}
        {documents.map((d, i) => (
          <DownloadCard
            key={d.document_id}
            docType={d.doc_type}
            downloadUrl={d.download_url}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
          className="flex gap-3 max-w-4xl mx-auto"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={streaming}
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create /chat redirect page**

`frontend/src/app/(app)/chat/page.tsx`:

```tsx
export default function ChatIndex() {
  return (
    <div className="flex items-center justify-center h-full text-gray-400">
      <div className="text-center">
        <p className="text-xl font-medium">Resume AI</p>
        <p className="text-sm mt-2">
          Select a conversation or start a new one.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ frontend/src/app/\(app\)/chat/
git commit -m "add chat UI with SSE streaming, status pills, and download cards"
```

---

### Task 15: History Page

**Files:**
- Create: `frontend/src/app/(app)/history/page.tsx`

- [ ] **Step 1: Create history page**

`frontend/src/app/(app)/history/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiJson } from "@/lib/api";

interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  created_at: string;
}

export default function HistoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const router = useRouter();

  useEffect(() => {
    apiJson<Conversation[]>("/conversations")
      .then(setConversations)
      .catch(console.error);
  }, []);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Conversation History</h1>
      {conversations.length === 0 ? (
        <p className="text-gray-400">No conversations yet.</p>
      ) : (
        <div className="space-y-3">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/chat/${c.id}`)}
              className="w-full text-left p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition"
            >
              <div className="flex justify-between items-center">
                <div>
                  <p className="font-medium">{c.title}</p>
                  <p className="text-sm text-gray-500">
                    {c.mode === "job_to_resume" ? "Job → Resume" : "Find Jobs"}{" "}
                    · {new Date(c.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    c.status === "active"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {c.status}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/\(app\)/history/
git commit -m "add conversation history page"
```

---

## Chunk 8: Manual Setup & Deployment

### Task 16: Manual Setup Checklist (User)

These steps must be done by the user manually before the app can run end-to-end.

- [ ] **Step 1: Get API keys**

1. **Gemini API key** — https://aistudio.google.com/apikey
2. **Tavily API key** — https://app.tavily.com
3. **Firecrawl API key** — https://www.firecrawl.dev

- [ ] **Step 2: Enable Supabase Auth providers**

In Supabase Dashboard → Authentication → Providers:
1. Enable **Email** (should be enabled by default)
2. Enable **Google** — requires creating OAuth credentials in Google Cloud Console:
   - Go to GCP Console → APIs & Services → Credentials
   - Create OAuth 2.0 Client ID (Web application)
   - Authorized redirect URI: `https://hwzptzrjqcniukwrjnrb.supabase.co/auth/v1/callback`
   - Copy Client ID and Secret into Supabase Google provider settings

- [ ] **Step 3: Get Supabase keys**

From Supabase Dashboard → Settings → API:
1. Copy **Project URL** → `SUPABASE_URL`
2. Copy **anon public key** → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
3. Copy **service_role key** → `SUPABASE_SERVICE_KEY`
4. Copy **JWT Secret** → `SUPABASE_JWT_SECRET`

- [ ] **Step 4: Fill in `.env` files**

Copy examples to real env files and fill in all values:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

- [ ] **Step 5: Test locally**

Terminal 1: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000`
Terminal 2: `cd frontend && npm install && npm run dev`

Visit `http://localhost:3000`, sign in, create a conversation, and test the chat.

---

### Task 17: Deploy Backend to Cloud Run

- [ ] **Step 1: Set GCloud project**

```bash
gcloud config set project resumeandcoverletterautomation
```

- [ ] **Step 2: Build and push Docker image**

```bash
cd backend
gcloud builds submit --tag gcr.io/resumeandcoverletterautomation/resume-api
```

- [ ] **Step 3: Deploy to Cloud Run**

```bash
gcloud run deploy resume-api \
  --image gcr.io/resumeandcoverletterautomation/resume-api \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=<url>,SUPABASE_SERVICE_KEY=<key>,SUPABASE_JWT_SECRET=<secret>,GEMINI_API_KEY=<key>,TAVILY_API_KEY=<key>,FIRECRAWL_API_KEY=<key>,FRONTEND_URL=<vercel-url>"
```

- [ ] **Step 4: Update frontend `.env.local` with Cloud Run URL**

Set `NEXT_PUBLIC_API_URL` to the Cloud Run service URL.

- [ ] **Step 5: Deploy frontend to Vercel**

Connect the GitHub repo to Vercel, set root directory to `frontend/`, add environment variables, and deploy.

- [ ] **Step 6: Update backend CORS with Vercel URL**

Redeploy Cloud Run with the Vercel production URL in `FRONTEND_URL`.

- [ ] **Step 7: End-to-end test on production**

Sign in → create conversation → send a message → verify AI responds with job search → answer questions → generate document → download.
