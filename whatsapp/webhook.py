from fastapi import Response
from twilio.twiml.messaging_response import MessagingResponse
import logging
import os
import requests
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_whatsapp_webhook(form_data: Dict[str, str], sql_agent: Any) -> Response:
    """
    Process incoming WhatsApp webhook requests
    
    Args:
        form_data: The form data from the webhook request
        sql_agent: The SQL agent to process queries
        
    Returns:
        A Twilio response
    """
    try:
        # Get the message from the request
        incoming_msg = form_data.get('Body', '').strip()
        sender = form_data.get('From', '')
        
        logger.info(f"Received message from {sender}: {incoming_msg}")
        
        # Process the query with our SQL agent
        result = process_query_for_whatsapp(sql_agent, incoming_msg)
        
        # Create a Twilio response
        twilio_resp = MessagingResponse()
        twilio_resp.message(result)
        
        return Response(content=str(twilio_resp), media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        twilio_resp = MessagingResponse()
        twilio_resp.message("Sorry, something went wrong. Please try again later.")
        return Response(content=str(twilio_resp), media_type="application/xml")

def process_query_for_whatsapp(agent: Any, question: str) -> str:
    """
    Process a query and format the response for WhatsApp
    
    Args:
        agent: The SQL agent
        question: The natural language question
        
    Returns:
        Formatted response for WhatsApp
    """
    try:
        # Log the events for debugging
        events = []
        for event in agent.stream({"messages": [("user", question)]}):
            events.append(event)
            logger.info(f"Event: {event}")
        
        # Get the final result
        messages = agent.invoke({"messages": [("user", question)]})
        
        # Extract the final answer
        for message in reversed(messages["messages"]):
            if hasattr(message, "tool_calls"):
                for tool_call in message.tool_calls:
                    if tool_call.get("name") == "SubmitFinalAnswer":
                        # Format the response for WhatsApp
                        reply_text = f"📊 *Results*\n\n{tool_call['args']['final_answer']}"
                        return reply_text
        
        # If no final answer found
        return "❌ Sorry, I couldn't find an answer to your question."
    except Exception as e:
        logger.error(f"Error in process_query_for_whatsapp: {str(e)}")
        return f"❌ Error processing your query: {str(e)}" 