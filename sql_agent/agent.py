from typing import Any, Dict, List, Optional
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from typing import Annotated, Literal
import os
import pyodbc
import urllib.parse
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import our tools
from sql_agent.tools import get_db_tools

# Load environment variables
load_dotenv()

# Define the state type
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

def handle_tool_error(state) -> dict:
    """Handle tool errors and format them for the agent"""
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    """Initial tool call to list tables"""
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }

def create_sql_agent():
    """Create and configure the SQL agent graph"""
    # Initialize database with SQL Server connection
    try:
        # Get available ODBC drivers
        print("Available ODBC drivers:")
        for driver in pyodbc.drivers():
            print(driver)
        
        # Use the SQL Server driver
        driver_name = "SQL Server"  # Update this if you have a different driver
        
        # Build connection string
        conn_str = (
            f"DRIVER={{{driver_name}}};"
            f"SERVER={os.environ.get('DB_SERVER')};"
            f"DATABASE={os.environ.get('DB_NAME')};"
            f"UID={os.environ.get('DB_USER')};"
            f"PWD={os.environ.get('DB_PASSWORD')};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=60;"
        )
        
        # Format for LangChain's SQLDatabase
        db_path = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
        
        # Create SQLDatabase instance
        db = SQLDatabase.from_uri(db_path)
        print("SQL Server connection successful!")
    except Exception as e:
        print(f"Error connecting to SQL Server: {e}")
        # Fallback to SQLite if SQL Server connection fails
        db_path = os.environ.get("DB_PATH", "sqlite:///Chinook.db")
        db = SQLDatabase.from_uri(db_path)
        print(f"Falling back to SQLite database: {db_path}")
    
    # Get tools
    list_tables_tool, get_schema_tool, query_tool, query_checker_tool = get_db_tools(db)
    print("Tables: ", list_tables_tool.invoke(""))
    
    # Create the workflow graph
    workflow = StateGraph(State)
    
    # Add nodes
    workflow.add_node("first_tool_call", first_tool_call)
    workflow.add_node(
        "list_tables_tool", create_tool_node_with_fallback([list_tables_tool])
    )
    workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))
    workflow.add_node("query_tool", create_tool_node_with_fallback([query_tool]))
    workflow.add_node("query_checker_tool", create_tool_node_with_fallback([query_checker_tool]))
    
    # Add model nodes
    model_get_schema = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
        [get_schema_tool]
    )
    
    workflow.add_node(
        "model_get_schema",
        lambda state: {
            "messages": [model_get_schema.invoke(state["messages"])],
        },
    )
    
    # Add query generation node
    class SubmitFinalAnswer(BaseModel):
        final_answer: str = Field(description="The final answer to the user's question")
    
    query_gen = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
        [SubmitFinalAnswer, query_tool, query_checker_tool]
    )
    
    workflow.add_node(
        "query_gen",
        lambda state: {
            "messages": [query_gen.invoke(state["messages"])],
        },
    )
    
    # Define edges
    workflow.add_edge(START, "first_tool_call")
    workflow.add_edge("first_tool_call", "list_tables_tool")
    workflow.add_edge("list_tables_tool", "model_get_schema")
    workflow.add_edge("model_get_schema", "get_schema_tool")
    workflow.add_edge("get_schema_tool", "query_gen")
    workflow.add_edge("query_tool", "query_gen")
    workflow.add_edge("query_checker_tool", "query_gen")
    
    # Add conditional edge to end
    def should_end(state):
        """Check if we should end the workflow"""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls"):
            for tool_call in last_message.tool_calls:
                if tool_call.get("name") == "SubmitFinalAnswer":
                    return END
                elif tool_call.get("name") == "sql_db_query":
                    return "query_tool"
                elif tool_call.get("name") == "sql_db_query_checker":
                    return "query_checker_tool"
        return "model_get_schema"
    
    # Use conditional edges
    workflow.add_conditional_edges("query_gen", should_end)
    
    # Compile the graph
    app = workflow.compile()
    return app

def process_query(agent, question: str) -> Dict[str, Any]:
    """Process a natural language query using the SQL agent"""
    try:
        # Invoke the agent with the question
        messages = agent.invoke(
            {"messages": [("user", question)]}
        )
        
        # Extract the final answer
        for message in reversed(messages["messages"]):
            if hasattr(message, "tool_calls"):
                for tool_call in message.tool_calls:
                    if tool_call.get("name") == "SubmitFinalAnswer":
                        return {
                            "status": "success",
                            "question": question,
                            "results": tool_call["args"]["final_answer"]
                        }
        
        # If no final answer found
        return {
            "status": "error",
            "question": question,
            "error": "No final answer generated"
        }
    except Exception as e:
        return {
            "status": "error",
            "question": question,
            "error": str(e)
        } 