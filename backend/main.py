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

    # Load generated documents for this conversation's jobs
    jobs = (
        supabase.table("jobs")
        .select("id")
        .eq("conversation_id", conversation_id)
        .execute()
    )
    docs = []
    if jobs.data:
        job_ids = [j["id"] for j in jobs.data]
        for job_id in job_ids:
            doc_results = (
                supabase.table("generated_documents")
                .select("id, doc_type, file_url")
                .eq("job_id", job_id)
                .execute()
            )
            for doc in doc_results.data:
                signed = supabase.storage.from_("documents").create_signed_url(
                    doc["file_url"], 3600
                )
                docs.append({
                    "document_id": doc["id"],
                    "doc_type": doc["doc_type"],
                    "download_url": signed.get("signedURL", ""),
                })

    return {**conv.data, "messages": messages.data, "documents": docs}


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
    return {"download_url": signed.get("signedURL", "")}
