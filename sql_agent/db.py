import os
from langchain_community.utilities import SQLDatabase

def create_db_connection():
    try:
        # Get credentials from environment variables
        server = os.environ.get('DB_SERVER', 'data-chat.database.windows.net')
        database = os.environ.get('DB_NAME', 'supermart_sales')
        username = os.environ.get('DB_USER', 'veer')
        password = os.environ.get('DB_PASSWORD', 'welcome2azuredb!')
        
        connection_string = (
            f"mssql+pyodbc://{username}:{password}"
            f"@{server}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
        )
        print(connection_string )
        db = SQLDatabase.from_uri(connection_string)
        return db
    except Exception as e:
        print(f"Error connecting to Azure SQL Database: {e}")
        return None
