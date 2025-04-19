import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
load_dotenv()

connection_string = (
    f"mssql+pyodbc://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    "@data-chat.database.windows.net/supermart_sales"
    "?driver=ODBC+Driver+18+for+SQL+Server"
)
print(connection_string )
db = SQLDatabase.from_uri(connection_string)
tables = db.get_table_names()
print(tables)
print(db.run(f"SELECT TOP 5 * FROM {tables[0]}"))