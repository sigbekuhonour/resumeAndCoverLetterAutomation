# Find Jobs Mode Redesign — Design Spec

## Overview

Redesign the "Find Jobs" mode to accept resume uploads, present structured job results, and differentiate the two modes (Job → Resume vs Find Jobs) as distinct product experiences within the same app. Update the landing page to surface both modes to new visitors.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| User input method | File upload + text fallback | Fastest path for users with a resume, doesn't block those without |
| Mode differentiation | Entry + results presentation | Distinct entry UX and structured JobCards make Find Jobs feel like a discovery tool, not a chatbot |
| Landing page | Tab switcher | Both modes equally discoverable, one active at a time, no clutter. Default tab is "I have a job posting" |
| Find Jobs entry (in-app) | Upload zone above chat | Prominent drag/drop area signals "this mode is different." Disappears after upload, attachment button persists in chat input |
| Job results display | Inline job cards in chat | Builds on existing card component pattern (DownloadCard), keeps architecture simple, match score + action buttons are structured enough |
| Post-upload behavior | Show extracted summary → confirm → search | Builds trust without the overhead of an editable profile card. Corrections happen naturally in chat |

> **Note — Landing page override:** The UI redesign spec (2026-03-15) intentionally chose a single-CTA landing page because both modes had similar text-based entry points. This spec overrides that decision because Find Jobs now has a visually distinct entry experience (file upload vs URL input). The two tabs communicate "this tool does two specific things" — which is the core product positioning goal to differentiate from generic chatbot SaaS.

## Landing Page: Tab Switcher

### Current State
Single hero with URL input, hardcoded to `job_to_resume` mode.

### New Design
Same hero headline and branding. Below the headline, a pill toggle switches between two tabs:

**"I have a job posting" tab (default):**
- URL input + "Generate" button (same as current)
- On submit: checks auth, creates conversation with `mode: "job_to_resume"`, redirects to `/chat/{id}?initial=<message>`

**"Find jobs for me" tab:**
- File upload zone: drag/drop area with "Choose file" button
- Supported formats: PDF, DOCX, PNG, JPG
- Below the upload zone: text link "or describe your experience →" that navigates to `/chat` in find_jobs mode (no file)
- **Auth gating:** Interacting with the upload zone (click or drag) checks auth first. If unauthenticated, redirect to `/login?returnTo=/chat&mode=find_jobs`. After login, the user lands on the `/chat` page in Find Jobs mode where they can upload. This avoids the problem of losing a selected file during the auth redirect flow.
- For authenticated users: on file submit, create conversation with `mode: "find_jobs"`, upload file to `/conversations/{id}/upload`, redirect to `/chat/{id}?initial=I've uploaded my resume. Please analyze it and help me find matching jobs.`

**"How it works" section:** Update to reflect both flows or use a combined 3-step flow.

## File Upload Infrastructure

### New Endpoint: `POST /conversations/{id}/upload`

- Accepts: `multipart/form-data` with a single file field
- Validates: file type (PDF, DOCX, PNG, JPG), max size 10MB
- Auth: requires Bearer token (same as other endpoints)
- Flow:
  1. Upload file to Supabase Storage at `{user_id}/{conversation_id}/{filename}`
  2. Upload file to Gemini Files API via `client.files.upload(file=<bytes>)` to get a multimodal-ready reference
  3. Store metadata in `conversation_files` table (storage path, Gemini file URI, mime type, file size)
  4. Return `{ file_id, filename, gemini_file_uri }`
- Error responses:
  - 400: unsupported file type or exceeds 10MB
  - 401: not authenticated
  - 500: Supabase Storage or Gemini Files API failure (return which step failed)

### Frontend `FileUpload` Component

- Drag-and-drop zone with click fallback
- Shows upload progress indicator during upload
- Shows filename + checkmark after successful upload
- Accepts `.pdf`, `.docx`, `.png`, `.jpg`
- **Error states:**
  - File too large: inline error "File must be under 10MB" below the upload zone, zone border turns red
  - Unsupported format: inline error "Supported formats: PDF, DOCX, PNG, JPG"
  - Server error: inline error "Upload failed — please try again" with a retry button
  - All error states are dismissible and allow re-selection
- Emits file to parent; parent handles the API call
- Used in: `/chat` page (Find Jobs empty state), `/chat/[id]` page (attachment button in Find Jobs mode)

### Frontend Upload Helper

New `apiUpload` function in `lib/api.ts` — uses `fetch` directly (NOT `apiFetch`) because `apiFetch` hardcodes `Content-Type: application/json`. The browser must set `Content-Type: multipart/form-data` with the boundary automatically. The helper constructs a `FormData` object and sends it with only the `Authorization` header.

```typescript
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session?.access_token}` },
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

### File Processing in `stream_chat()`

When a conversation has an uploaded file and it's the first message exchange:

```python
# Check for uploaded file
file_record = get_conversation_file(conversation_id)
contents = []
if file_record and not has_prior_messages:
    contents.append(types.Part.from_uri(
        file_uri=file_record.gemini_file_uri,
        mime_type=file_record.mime_type
    ))
contents.append(types.Part.from_text(user_message))
```

The file is included in the Gemini `contents` array alongside the user's text message. Gemini processes both multimodally.

> **Gemini file URI expiry:** Gemini Files API URIs expire after 48 hours. Since the file is only included in the `contents` array on the first message exchange (when `not has_prior_messages`), this is acceptable — the first exchange happens immediately after upload. For mid-conversation uploads via the attachment button, the same pattern applies: include the file in the very next message's contents. The `gemini_file_uri` stored in the database is for reference only and is not reused after the initial processing.

### DOCX Support

Gemini's Files API accepts DOCX files (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`) and can extract text content from them for multimodal processing. No server-side conversion needed. If Gemini's DOCX handling proves unreliable during implementation, fall back to server-side extraction via `python-docx` before sending as plain text — but start with native Gemini support.

## Mode-Specific Chat Experiences

### `/chat` Page (New Conversation Entry)

Has mode selector pills at top. Selected mode changes the empty state:

**Job → Resume (default):**
- Empty state: chat icon + "Start a conversation" + "Paste a job posting URL or describe the role you're targeting."
- Input bar at bottom with text input (same as current)

**Find Jobs:**
- Empty state: upload zone centered — drag/drop area with upload icon, "Upload your resume" heading, "PDF, DOCX, or image — we'll extract everything" subtext, "Choose file" button
- "Or" divider below upload zone
- "Type your experience in the chat below" text pointing to input bar
- Input bar placeholder changes to: "Describe your experience and what roles you're looking for..."

**On submit (either mode):**
1. Create conversation via `POST /conversations` with selected mode
2. If file was selected (Find Jobs): upload via `POST /conversations/{id}/upload`
3. Redirect to `/chat/{id}?initial=<message>`

### `/chat/[id]` Page (Active Conversation)

**Job → Resume conversations:** No changes. Works exactly as today.

**Find Jobs conversations:** Two additions:

1. **Attachment button (📎)** in the chat input bar — opens file picker for uploading additional files mid-conversation. Only visible when the conversation mode is `find_jobs`. On file select: upload via `POST /conversations/{id}/upload`, then auto-send a message "I've uploaded an additional document. Please review it."

2. **JobCard component** — rendered inline in chat flow when `job_result` SSE events arrive. Displays:
   - Job title (bold)
   - Company + location (both optional — may not be available from all search results)
   - Match score badge: green (≥80%), amber (≥60%), red (<60%)
   - Snippet (2 lines, truncated)
   - URL (linked, truncated display)
   - Two action buttons:
     - "Generate Resume" → sends a chat message asking the AI to generate docs for this specific job
     - "View Details" → sends a chat message asking the AI to scrape and show the full JD

### `job_result` SSE Rendering Order

`job_result` events accumulate in a `jobResults` state array (same pattern as `documents` state). They render inline in the message area, after the current batch of assistant messages and status pills, before the `documents` section. When new `job_result` events arrive during streaming, they appear immediately (not buffered until stream ends).

```
[ChatMessage - assistant text]
[StatusPill - scraping status]
[JobCard - result 1]
[JobCard - result 2]
[JobCard - result 3]
[DownloadCard - if any documents generated]
```

The SSE handler in `/chat/[id]/page.tsx` adds a new `else if (eventType === "job_result")` branch that appends to the `jobResults` array, following the exact same pattern as `document` event handling.

## New SSE Event Type: `job_result`

```
event: job_result
data: {"title": "Senior Frontend Engineer", "company": "Stripe", "location": "Remote", "match_score": 92, "snippet": "Build and scale...", "url": "https://..."}
```

Fields:
- `title` (required): Job title
- `url` (required): Job posting URL
- `snippet` (required): Short description
- `match_score` (required): 0-100 match percentage calculated by AI
- `company` (optional): Company name, parsed by AI from title/snippet
- `location` (optional): Location/remote status, parsed by AI

## Backend AI Changes

### Updated Find Jobs System Prompt

**When file uploaded:**
```
You are a career assistant helping the user find jobs that match their profile.

The user has uploaded their resume. Analyze it thoroughly — extract work experience,
skills, education, certifications, and any other relevant details. Respond with a
concise summary of what you found and ask if anything needs correction.

Use save_user_context to persist each category you extract (work_experience, skills,
education, certifications, personal_info).

Once the user confirms their profile, ask what kind of roles they're looking for
(or suggest based on their profile). Then use search_jobs to find matching positions.

For each promising result, use scrape_job to get the full description, then assess
how well it matches the user's profile (0-100%). Once you have assessed the results,
use present_job_results to show them to the user as structured cards.

IMPORTANT: When you generate a document, do NOT paste the download URL in your
response. The UI will automatically show a download card.
```

**When no file (text fallback):**
```
You are a career assistant helping the user find jobs that match their profile.

Ask focused questions to understand the user's background — experience, skills,
education, what they're looking for. Use save_user_context as you learn things.

Once you have enough context, ask what roles they want and use search_jobs to find
matching positions. For each promising result, use scrape_job to get the full
description, then assess how well it matches the user's profile (0-100%). Once you
have assessed the results, use present_job_results to show them as structured cards.

IMPORTANT: When you generate a document, do NOT paste the download URL in your
response. The UI will automatically show a download card.
```

### New Tool: `present_job_results`

Replaces the approach of emitting events from `_execute_tool()` directly. The AI calls this tool after it has searched, scraped, and assessed jobs — so all fields including `match_score`, `company`, and `location` are populated from the AI's reasoning.

**Tool declaration:**
```python
types.FunctionDeclaration(
    name="present_job_results",
    description="Present job search results to the user as structured cards. Call this after you have assessed match scores for each result.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "results": types.Schema(
                type="ARRAY",
                items=types.Schema(
                    type="OBJECT",
                    properties={
                        "title": types.Schema(type="STRING", description="Job title"),
                        "url": types.Schema(type="STRING", description="Job posting URL"),
                        "snippet": types.Schema(type="STRING", description="Brief description"),
                        "match_score": types.Schema(type="INTEGER", description="0-100 match percentage"),
                        "company": types.Schema(type="STRING", description="Company name"),
                        "location": types.Schema(type="STRING", description="Location or remote status"),
                    },
                    required=["title", "url", "snippet", "match_score"],
                ),
            ),
        },
        required=["results"],
    ),
)
```

**Execution in `_execute_tool()` → `stream_chat()`:**

`_execute_tool()` returns the results array as its response data. `stream_chat()` then emits a `job_result` SSE event for each item in the array — same pattern as `document` event emission after `generate_document`. The tool returns `{"status": "presented", "count": N}` to Gemini so it knows the cards were shown.

```python
# In stream_chat(), after _execute_tool() returns for present_job_results:
if tool_name == "present_job_results":
    for job in tool_result.get("results", []):
        yield ServerSentEvent(data=json.dumps(job), event="job_result")
    tool_response = {"status": "presented", "count": len(tool_result.get("results", []))}
```

### Match Score Calculation

No separate tool or API call. The AI calculates match scores via its reasoning: after getting search results from `search_jobs` and scraping top results with `scrape_job`, it compares each JD against the user's known profile to assign a match percentage. It then calls `present_job_results` with the enriched data.

**Flow:**
1. AI calls `search_jobs(query, location)` → gets raw results (title, url, snippet)
2. AI calls `scrape_job(url)` for each promising result → gets full JD
3. AI compares each JD against user profile → calculates match scores in its reasoning
4. AI calls `present_job_results([{title, url, snippet, match_score, company, location}, ...])` → frontend renders JobCards
5. AI composes a text response summarizing the results

## Data Model Changes

### New Table: `conversation_files`

```sql
create table conversation_files (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  storage_path text not null,
  gemini_file_uri text not null,
  mime_type text not null,
  file_size bigint not null,
  created_at timestamptz not null default now()
);

-- RLS
alter table conversation_files enable row level security;

create policy "Users can read own files"
  on conversation_files for select
  using (user_id = auth.uid());

create policy "Users can insert own files"
  on conversation_files for insert
  with check (user_id = auth.uid());
```

### Existing Tables — No Changes

- `conversations` — `mode` field already supports `find_jobs`
- `messages` — no changes
- `jobs` — still used when AI scrapes a job from Find Jobs results
- `generated_documents` — still used when user clicks "Generate Resume" on a JobCard
- `user_context` — still used to persist extracted profile data via `save_user_context`

## What's NOT in Scope

- **Editable profile page** (IMPROVEMENTS.md #6) — separate feature. Resume upload bootstraps profile via `save_user_context` through chat.
- **Side panel for results** — decided against in favor of inline JobCards
- **Multiple file uploads in a single drop** — one file at a time for v1

## Component Inventory

**New components (3):**
- `FileUpload` — drag/drop + click upload zone with error states
- `JobCard` — inline job result card with match score and action buttons
- `apiUpload` helper in `lib/api.ts` — multipart upload using `fetch` directly (not `apiFetch`)

**Modified frontend files (3):**
- `app/page.tsx` — landing page tab switcher
- `app/(app)/chat/page.tsx` — mode-specific empty states (upload zone for Find Jobs)
- `app/(app)/chat/[id]/page.tsx` — attachment button, JobCard rendering, `job_result` SSE handling

**Modified backend files (4):**
- `main.py` — new upload endpoint
- `chat.py` — file-aware streaming, `present_job_results` tool + `job_result` SSE events, updated system prompts
- `tools.py` — `present_job_results` tool declaration
- `models.py` — new request/response types for upload

**New migration (1):**
- `conversation_files` table + RLS policies (follows existing migration pattern in `supabase/migrations/`)
