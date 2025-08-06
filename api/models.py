from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    thoughts: str
    status: str = "success"
    timestamp: datetime

class StreamMessage(BaseModel):
    type: str  # "thought_token", "action_token", "response_token", "thought_start", "action_start", "observation", "response_complete", "token", "done", "error"
    content: str

class ErrorResponse(BaseModel):
    error: str
    message: str
    status: str = "error"
    timestamp: datetime

class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
