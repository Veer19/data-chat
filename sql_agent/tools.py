from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from typing import Tuple, Any

def get_db_tools(db: SQLDatabase) -> Tuple[Any, Any, Any, Any]:
    """
    Get the database tools from the SQLDatabaseToolkit
    
    Args:
        db: SQLDatabase instance
        
    Returns:
        Tuple of tools: list_tables_tool, get_schema_tool, query_tool, query_checker_tool
    """
    # Create toolkit with the database
    toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o"))
    
    # Get all tools
    tools = toolkit.get_tools()
    
    # Extract specific tools
    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")
    query_tool = next(tool for tool in tools if tool.name == "sql_db_query")
    query_checker_tool = next(tool for tool in tools if tool.name == "sql_db_query_checker")
    
    return list_tables_tool, get_schema_tool, query_tool, query_checker_tool 