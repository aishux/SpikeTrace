"""
FastAPI backend for SpikeTrace chat: exposes /api/chat and serves the frontend.
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from strands_spiketrace_agent import query_spiketrace_agent

app = FastAPI(title="SpikeTrace Chat API")

# Allow frontend (same-origin when served from here, or localhost from file/server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")


class ChatRequest(BaseModel):
    message: str
    context_id: str | None = None  # Continue same conversation so agent can use tools (e.g. Jira/Slack)


class ChatResponse(BaseModel):
    response: str
    context_id: str | None = None  # Send this back on the next message in this chat


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send user message to SpikeTrace agent and return the response. Pass context_id to keep conversation context (e.g. so 'yes' triggers create_incident_ticket)."""
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        response_text, context_id = await query_spiketrace_agent(
            message, context_id=request.context_id
        )
        return ChatResponse(response=response_text, context_id=context_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}",
        )


# Serve frontend (must be last so /api/* takes precedence)
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
