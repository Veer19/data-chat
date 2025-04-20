from fastapi import Response, Request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
import logging
import os
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Add Twilio request validation
async def validate_twilio_request(request: Request) -> bool:
    validator = RequestValidator(os.environ.get('TWILIO_AUTH_TOKEN'))
    
    # Get the request URL
    url = str(request.url)
    
    # Get form data - must await it
    form_data = await request.form()
    post_data = dict(form_data)
    
    # Get the X-Twilio-Signature header
    signature = request.headers.get('X-TWILIO-SIGNATURE', '')
    
    return validator.validate(url, post_data, signature)

async def process_whatsapp_webhook(request: Request, sql_agent: Any) -> Response:
    """Process incoming WhatsApp webhook requests"""
    try:
        # Validate the request is from Twilio
        if not await validate_twilio_request(request):
            logger.warning("Invalid Twilio signature")
            return Response(status_code=403)
        
        # Get form data
        form_data = await request.form()
        
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
        # Just use invoke, no need for stream
        messages = agent.invoke({"messages": [("user", question)]})
        logger.info(f"Agent response: {messages}")
        
        # Get the last message which should have the final answer
        last_message = messages["messages"][-1]
        
        # Check if we have a final answer
        if hasattr(last_message, "tool_calls"):
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "SubmitFinalAnswer":
                    answer = tool_call["args"]["final_answer"]
                    # Format nicely for WhatsApp
                    formatted_answer = (
                        f"{answer}\n\n"
                    )
                    return formatted_answer
        
        # If we didn't get a final answer
        return (
            "❌ I couldn't process that query.\n\n"
            "Try rephrasing your question or ask something else! 🤔"
        )
        
    except Exception as e:
        logger.error(f"Error in process_query_for_whatsapp: {str(e)}")
        return (
            "❌ Oops! Something went wrong.\n\n"
            "Please try asking your question again in a different way."
        ) 