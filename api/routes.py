import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from api.models import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from api.agent_service import AgentService

# Initialize router
router = APIRouter()

# Initialize agent service (singleton)
agent_service = AgentService()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(timestamp=datetime.now())

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events"""
    try:
        async def generate():
            async for message in agent_service.chat_stream(request.message):
                # Format as plain JSON without SSE prefix
                data = message.dict()
                yield f"{json.dumps(data, ensure_ascii=False)}\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint"""
    try:
        result = agent_service.chat_sync(request.message)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["response"])
        
        return ChatResponse(
            response=result["response"],
            thoughts=result["thoughts"],
            timestamp=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_conversation():
    """Reset conversation history"""
    try:
        result = agent_service.reset_conversation()
        return {"status": "success", "message": "Conversation history cleared", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
