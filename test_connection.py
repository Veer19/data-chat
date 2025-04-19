import os
import sys
import pyodbc
import urllib.parse
import logging
from sqlalchemy import create_engine, text, event
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('connection_test.log')
    ]
)
logger = logging.getLogger("test_connection")

def test_direct_pyodbc_connection():
    """Test direct connection using pyodbc"""
    logger.info("=== Testing Direct PYODBC Connection ===")
    
    try:
        # Get credentials from environment variables
        server = os.environ.get('DB_SERVER', 'data-chat.database.windows.net')
        database = os.environ.get('DB_NAME', 'supermart_sales')
        username = os.environ.get('DB_USER', 'veer')
        password = os.environ.get('DB_PASSWORD', 'welcome2azuredb!')
        
        # List available drivers
        logger.info("Available ODBC drivers:")
        for driver in pyodbc.drivers():
            logger.info(f"  - {driver}")
        
        # Try different drivers
        driver_options = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server"
        ]
        
        for driver in driver_options:
            if driver not in pyodbc.drivers():
                logger.info(f"Driver {driver} not available, skipping...")
                continue
                
            logger.info(f"Trying connection with driver: {driver}")
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )
            
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                
                # Test basic connectivity
                logger.info("Testing SQL Server version...")
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                logger.info(f"Connected to: {version}")
                
                # Test listing tables
                logger.info("Testing table listing...")
                cursor.execute("""
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
                    ORDER BY TABLE_NAME
                """)
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Tables found: {tables}")
                
                # Test a simple query if tables exist
                if tables:
                    first_table = tables[0]
                    logger.info(f"Testing simple query on table: {first_table}")
                    cursor.execute(f"SELECT TOP 5 * FROM [{first_table}]")
                    columns = [column[0] for column in cursor.description]
                    logger.info(f"Columns: {columns}")
                    rows = cursor.fetchall()
                    logger.info(f"Retrieved {len(rows)} rows")
                
                cursor.close()
                conn.close()
                logger.info(f"[SUCCESS] Connection with {driver} successful!")
                return driver  # Return the first working driver
                
            except Exception as e:
                logger.error(f"[FAILED] Connection with {driver} failed: {str(e)}")
        
        logger.error("All drivers failed to connect")
        return None
        
    except Exception as e:
        logger.error(f"Error in direct connection test: {str(e)}")
        return None

def test_sqlalchemy_connection(driver_name=None):
    """Test connection using SQLAlchemy"""
    logger.info("=== Testing SQLAlchemy Connection ===")
    
    try:
        # Get credentials from environment variables
        server = os.environ.get('DB_SERVER', 'data-chat.database.windows.net')
        database = os.environ.get('DB_NAME', 'supermart_sales')
        username = os.environ.get('DB_USER', 'veer')
        password = os.environ.get('DB_PASSWORD', 'welcome2azuredb!')
        
        # If no driver specified, try to find one
        if not driver_name:
            driver_options = [
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "SQL Server Native Client 11.0",
                "SQL Server"
            ]
            
            for option in driver_options:
                if option in pyodbc.drivers():
                    driver_name = option
                    break
            
            if not driver_name:
                driver_name = "SQL Server"  # Fallback
        
        logger.info(f"Using driver: {driver_name}")
        
        # Build connection string
        conn_str = (
            f"DRIVER={{{driver_name}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )
        
        # Create SQLAlchemy engine
        quoted_conn_str = urllib.parse.quote_plus(conn_str)
        db_url = f"mssql+pyodbc:///?odbc_connect={quoted_conn_str}"
        logger.info(f"SQLAlchemy URL: {db_url}")
        
        # Create engine with specific configurations for Azure SQL
        engine = create_engine(
            db_url,
            connect_args={
                "timeout": 30,
                "use_setinputsizes": False
            },
            echo=True  # Show SQL queries for debugging
        )
        
        # Add event listeners
        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            dbapi_connection.autocommit = False
            cursor = dbapi_connection.cursor()
            cursor.execute("SET LOCK_TIMEOUT 30000")
            cursor.close()
        
        # Test connection
        with engine.connect() as connection:
            # Test version
            result = connection.execute(text("SELECT @@VERSION"))
            version = result.scalar()
            logger.info(f"Connected to: {version}")
            
            # Test listing tables
            result = connection.execute(text("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
                ORDER BY TABLE_NAME
            """))
            tables = [row[0] for row in result]
            logger.info(f"Tables found: {tables}")
            
            # Test a simple query if tables exist
            if tables:
                first_table = tables[0]
                logger.info(f"Testing simple query on table: {first_table}")
                result = connection.execute(text(f"SELECT TOP 5 * FROM [{first_table}]"))
                rows = result.fetchall()
                logger.info(f"Retrieved {len(rows)} rows")
        
        logger.info("[SUCCESS] SQLAlchemy connection successful!")
        return True
        
    except Exception as e:
        logger.error(f"[FAILED] SQLAlchemy connection failed: {str(e)}")
        return False

def test_langchain_with_direct_sql():
    """Test LangChain SQLDatabase with direct SQL approach"""
    logger.info("=== Testing LangChain with Direct SQL Approach ===")
    
    try:
        from langchain_community.utilities import SQLDatabase
        
        # Get credentials from environment variables
        server = os.environ.get('DB_SERVER', 'data-chat.database.windows.net')
        database = os.environ.get('DB_NAME', 'supermart_sales')
        username = os.environ.get('DB_USER', 'veer')
        password = os.environ.get('DB_PASSWORD', 'welcome2azuredb!')
        
        # Use SQL Server driver
        driver_name = "SQL Server"
        logger.info(f"Using driver: {driver_name}")
        
        # Build connection string
        conn_str = (
            f"DRIVER={{{driver_name}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )
        
        # Create SQLAlchemy engine
        quoted_conn_str = urllib.parse.quote_plus(conn_str)
        db_url = f"mssql+pyodbc:///?odbc_connect={quoted_conn_str}"
        
        # Create engine with specific configurations
        engine = create_engine(
            db_url,
            connect_args={
                "timeout": 30,
                "use_setinputsizes": False
            }
        )
        
        # Add event listeners
        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            dbapi_connection.autocommit = False
            cursor = dbapi_connection.cursor()
            cursor.execute("SET LOCK_TIMEOUT 30000")
            cursor.close()
        
        # Create a subclass of SQLDatabase to override problematic methods
        class DirectSQLDatabase(SQLDatabase):
            def get_table_names(self):
                """Get table names using direct SQL instead of SQLAlchemy's introspection"""
                with self._engine.connect() as connection:
                    result = connection.execute(text("""
                        SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
                        ORDER BY TABLE_NAME
                    """))
                    return [row[0] for row in result]
        
        # Create our custom database
        db = DirectSQLDatabase(engine)
        
        # Test getting table names
        logger.info("Testing get_table_names()...")
        tables = db.get_table_names()
        logger.info(f"Tables found: {tables}")
        
        # Test getting table info
        if tables:
            first_table = tables[0]
            logger.info(f"Testing get_table_info() for table: {first_table}")
            table_info = db.get_table_info(table_names=[first_table])
            logger.info(f"Table info: {table_info}")
            
            # Test running a query
            logger.info(f"Testing run() with a simple query...")
            result = db.run(f"SELECT TOP 5 * FROM [{first_table}]")
            logger.info(f"Query result: {result}")
        
        logger.info("[SUCCESS] LangChain with Direct SQL approach successful!")
        return True
        
    except Exception as e:
        logger.error(f"[FAILED] LangChain with Direct SQL approach failed: {str(e)}")
        return False

def main():
    """Run all tests"""
    logger.info("Starting Azure SQL Database connection tests")
    
    # Load environment variables
    load_dotenv()
    
    # Test SQLAlchemy connection
    sqlalchemy_success = test_sqlalchemy_connection('SQL Server')
    
    # Test LangChain with direct SQL approach
    if sqlalchemy_success:
        test_langchain_with_direct_sql()
    
    logger.info("All tests completed")

if __name__ == "__main__":
    main()
