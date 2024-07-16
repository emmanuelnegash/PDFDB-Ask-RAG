import psycopg2
from psycopg2 import OperationalError, pool
import logging
import json
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool
db_pool = None

# File path for storing credentials
CREDENTIALS_FILE = "db_credentials.json"

def load_credentials():
    """Load database credentials from a JSON file."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_credentials(databases):
    """Save database credentials to a JSON file."""
    with open(CREDENTIALS_FILE, 'w') as file:
        json.dump(databases, file)
    logger.info("Database credentials saved.")

def create_connection_pool(db_config, minconn=1, maxconn=10):
    """Create a connection pool."""
    global db_pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn,
            maxconn,
            dbname=db_config["name"],
            user=db_config["username"],
            password=db_config["password"],
            host=db_config["host"],
            port=db_config["port"]
        )
        if db_pool:
            logger.info("Connection pool created successfully")
        else:
            logger.error("Connection pool creation failed")
    except OperationalError as e:
        logger.error(f"Error creating connection pool: {e}")
        db_pool = None

def get_connection():
    """Get a connection from the pool."""
    global db_pool
    if db_pool is not None:
        try:
            connection = db_pool.getconn()
            if connection:
                logger.info("Successfully retrieved connection from pool")
                return connection
        except OperationalError as e:
            logger.error(f"Error getting connection from pool: {e}")
    else:
        logger.error("Connection pool is not initialized")
    return None

def release_connection(connection):
    """Release the connection back to the pool."""
    global db_pool
    if db_pool is not None:
        try:
            db_pool.putconn(connection)
            logger.info("Connection released back to pool")
        except OperationalError as e:
            logger.error(f"Error releasing connection back to pool: {e}")
    else:
        logger.error("Connection pool is not initialized")

def execute_query(query, params=None, batch_size=None):
    """Execute a single query with optional batching."""
    connection = get_connection()
    if connection is None:
        logger.error("Failed to obtain a database connection")
        return None
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        while True:
            results = cursor.fetchmany(batch_size)
            if not results:
                break
            yield results
    except OperationalError as e:
        logger.error(f"The error '{e}' occurred")
    finally:
        cursor.close()
        release_connection(connection)

def get_table_names():
    """Retrieve table names from the database."""
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    result = list(execute_query(query))
    # Ensure we are returning a list of strings
    return [row[0] for batch in result for row in batch] if result else []

def add_database(db_form_data):
    """Store the database configuration."""
    db_name = db_form_data["name"]
    db_config = {
        "name": db_name,
        "host": db_form_data["host"],
        "port": db_form_data["port"],
        "username": db_form_data["username"],
        "password": db_form_data["password"]
    }
    create_connection_pool(db_config)  # Initialize connection pool for the new database
    return db_name, db_config

def edit_database(db_name, db_form_data, databases):
    """Edit an existing database configuration."""
    db_config = databases.get(db_name, {})
    db_config.update({
        "host": db_form_data["host"],
        "port": db_form_data["port"],
        "username": db_form_data["username"],
        "password": db_form_data["password"]
    })
    create_connection_pool(db_config)  # Re-initialize connection pool for the updated database
    return db_name, db_config

def close_connection_pool():
    """Close the database connection pool."""
    global db_pool
    if db_pool:
        db_pool.closeall()
        logger.info("Connection pool closed.")
