
from typing import Any, Annotated
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from sql_agent.db import create_db_connection


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="The final answer to the user")

def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
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

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def handle_tool_error(state) -> dict:
    error = state.get("error")
    print("ERROR", error)
    tool_calls = state["messages"][-1].tool_calls
    print("TOOL CALLS", tool_calls)
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def query_gen_node(state: State):
    """Generate SQL query from natural language question"""
    query_gen_system = """You are a SQL expert with a strong attention to detail.

    Given an input question, output a syntactically correct SQL Server query to run.
    
    When generating the query:
    1. Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
    2. You can order the results by a relevant column to return the most interesting examples.
    3. Never query for all the columns from a specific table, only ask for the relevant columns given the question.
    4. Make sure to use SQL Server syntax.
    
    DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
    
    DO NOT output any other text or any formatting other than the query.
    DO NOT format the query with line breaks or ```sql```.
    Only return valid SQL query.
    """

    query_gen_prompt = ChatPromptTemplate.from_messages(
        [("system", query_gen_system), ("placeholder", "{messages}")]
    )
    query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4o", temperature=0)
    message = query_gen.invoke(state)
    return {"messages": [message]}

def format_answer_node(state: State):
    """Format the query results into a natural language response"""
    format_system = """You are a helpful business analyst assistant.
    
    Take the SQL query results and format them into a clear, natural language response.
    Consider the original question when formatting your response.
    
    You MUST use the SubmitFinalAnswer tool to provide your response.
    Make your response concise but informative."""

    format_prompt = ChatPromptTemplate.from_messages(
        [("system", format_system), ("placeholder", "{messages}")]
    )
    format_model = format_prompt | ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
        [SubmitFinalAnswer], tool_choice="required"
    )
    print("FORMAT STATE", state)
    return {"messages": [format_model.invoke(state)]}

def model_check_query(state: State) -> dict[str, list[AIMessage]]:
    """
    Use this tool to double-check if your query is correct before executing it.
    """
    query_check_system = """You are a SQL expert with a strong attention to detail.
    Double check the PostgreSQL query for common mistakes, including:
    - Using NOT IN with NULL values
    - Using UNION when UNION ALL should have been used
    - Using BETWEEN for exclusive ranges
    - Data type mismatch in predicates
    - Properly quoting identifiers
    - Using the correct number of arguments for functions
    - Casting to the correct data type
    - Using the proper columns for joins

    If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

    Only output the query, no other text.
    """

    query_check_prompt = ChatPromptTemplate.from_messages(
        [("system", query_check_system), ("placeholder", "{messages}")]
    )
    query_check = query_check_prompt | ChatOpenAI(model="gpt-4o", temperature=0)

    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

def create_sql_agent():
    db = create_db_connection()
    toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o"))
    tools = toolkit.get_tools()
    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")
    sql_db_query_tool = next(tool for tool in tools if tool.name == "sql_db_query")
    
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("first_tool_call", first_tool_call)
    workflow.add_node("list_tables_tool", create_tool_node_with_fallback([list_tables_tool]))
    workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))
    workflow.add_node("model_get_schema", lambda state: {
        "messages": [ChatOpenAI(model="gpt-4o").bind_tools([get_schema_tool]).invoke(state["messages"])],
    })
    workflow.add_node("query_gen", query_gen_node)
    workflow.add_node("correct_query", model_check_query)
    workflow.add_node("execute_query", create_tool_node_with_fallback([sql_db_query_tool]))
    workflow.add_node("format_answer", format_answer_node)

    # Add edges
    workflow.add_edge(START, "first_tool_call")
    workflow.add_edge("first_tool_call", "list_tables_tool")
    workflow.add_edge("list_tables_tool", "model_get_schema")
    workflow.add_edge("model_get_schema", "get_schema_tool")
    workflow.add_edge("get_schema_tool", "query_gen")
    workflow.add_edge("query_gen", "execute_query")
    workflow.add_edge("execute_query", "format_answer")
    workflow.add_edge("format_answer", END)

    return workflow.compile()