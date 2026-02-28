# AI Resume & Cover Letter Automation

Automatically generate tailored resumes and cover letters for any job posting — paste a URL or just describe the role.

---

## How It Works

1. Paste a job URL **or** search by job title/keywords
2. **Tavily** finds the job posting URL → **Firecrawl** extracts the full description
3. **Gemini 2.5 Flash** tailors your master resume and writes a cover letter
4. Download a polished `.docx` file

---

## Tech Stack

### Frontend
- **Next.js** — UI for inputting job URLs, managing your master resume, and downloading generated documents
- **Vercel** — deploys the Next.js app

### Backend
- **Python + FastAPI** — API that orchestrates scraping, AI calls, and document generation
- **Google Cloud Run** — serverless container hosting for the FastAPI app
- **Supabase** — user authentication (Auth) and storing resume data / generation history (Postgres)

### Document Generation
- **docxtpl** (python-docx-template) — fills Jinja2-templated `.docx` files with AI-generated content; design your resume layout in Word once, reuse forever

### Job Research / Scraping
Two-stage pipeline:
1. **Tavily** — when no URL is provided, searches the web and returns ranked job posting URLs
2. **Firecrawl** — takes the URL and extracts the full job description as clean Markdown; handles JS rendering and anti-blocking on sites like LinkedIn, Indeed, and Greenhouse

### AI
- **Gemini 2.5 Flash** (Google AI) — generates tailored resume bullet points and cover letter copy; ~25× cheaper on output tokens than comparable models ($0.40/1M output tokens)

---

## Architecture

```
User (Next.js on Vercel)
        |
        v
FastAPI (Google Cloud Run)
        |
   +----+----+----------+
   |         |          |
Tavily   Firecrawl   Gemini 2.5 Flash
(find     (scrape     (generate
 URLs)      JD)        content)
                |
            docxtpl
        (fill .docx template)
                |
          Supabase (store history)
```

---

## Project Structure (planned)

```
/
├── frontend/           # Next.js app
│   └── ...
├── backend/            # FastAPI app
│   ├── main.py
│   ├── scraper.py      # Tavily + Firecrawl integration
│   ├── generator.py    # Gemini API calls
│   ├── docx_builder.py # docxtpl rendering
│   └── templates/      # .docx resume/cover letter templates
└── README.md
```

---

## Key Dependencies

| Layer | Package |
|---|---|
| Backend framework | `fastapi`, `uvicorn` |
| Document generation | `docxtpl` |
| Job discovery | `tavily-python` |
| Job scraping | `firecrawl-py` |
| AI | `google-genai` |
| Database / Auth | `supabase` |
| Frontend | `next`, `react` |
