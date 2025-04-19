from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
import json
import logging

# Import our modules
from sql_agent.agent import create_sql_agent
from whatsapp.webhook import process_whatsapp_webhook

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('app.log')  # Log to file
    ]
)

logger = logging.getLogger(__name__)

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

# SQL agent will be initialized on first use
sql_agent = None

# Dependency to get the SQL agent
async def get_sql_agent():
    global sql_agent
    if sql_agent is None:
        logger.info("Initializing SQL agent")
        sql_agent = create_sql_agent()
    return sql_agent

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
async def query_endpoint(request: QueryRequest, agent=Depends(get_sql_agent)):
    """Process a natural language query against the database"""
    # try:
    print("QUESTION", request.question)
    
    messages = agent.invoke(
        {"messages": [("user", request.question)]}
    )
    for message in messages["messages"]:
        print("MESSAGE", message)
        print("____________________")
    json_str = messages["messages"][-1].tool_calls[0]["args"]["final_answer"]
    # for event in agent.stream(
    #     {"messages": [("user", request.question)]}
    # ):
    #     print(event)
    return {
        "status": "success",
        "question": request.question,
        "results": json_str,
        "error": None
    }
    # except Exception as e:
    #     logger.error(f"Error processing query: {str(e)}")
    #     return {
    #         "status": "error",
    #         "question": request.question,
    #         "sql_query": None,
    #         "results": None,
    #         "error": str(e)
    #     }

@app.post("/stream")
async def stream_endpoint(request: QueryRequest, agent=Depends(get_sql_agent)):
    """Stream the processing of a query"""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        try:
            for event in agent.stream({"messages": [("user", request.question)]}):
                yield f"data: {json.dumps({'event': event})}\n\n"
        except Exception as e:
            logger.error(f"Error streaming query: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, agent=Depends(get_sql_agent)):
    """Webhook for WhatsApp integration"""
    form_data = await request.form()
    return process_whatsapp_webhook(form_data, agent)

@app.get("/")
def health():
    return {"status": "FastAPI is live on Azure 🎉"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) 