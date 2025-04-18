from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
import json

# Import our modules
from sql_agent.agent import create_sql_agent, process_query
from whatsapp.webhook import process_whatsapp_webhook

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="SQL Agent API",
    description="API for natural language querying of SQL databases with WhatsApp integration",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the SQL agent
sql_agent = create_sql_agent()

# Define request models
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    status: str
    question: str
    sql_query: Optional[str] = None
    results: Optional[str] = None
    error: Optional[str] = None

class StreamResponse(BaseModel):
    event: Dict[str, Any]

# API endpoints
@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """Process a natural language query against the database"""
    try:
        result = process_query(sql_agent, request.question)
        return result
    except Exception as e:
        return {
            "status": "error",
            "question": request.question,
            "error": str(e)
        }

@app.post("/stream")
async def stream_endpoint(request: QueryRequest):
    """Stream the processing of a query"""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        try:
            for event in sql_agent.stream({"messages": [("user", request.question)]}):
                yield f"data: {json.dumps({'event': event})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Webhook for WhatsApp integration"""
    form_data = await request.form()
    return process_whatsapp_webhook(form_data, sql_agent)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) 