"""
db.py
The "Key" that opens the door to LiyanaArachchi's Neon Database.
It reads the secret password from the .env file and creates a connection.
"""
import os
import psycopg

def get_conn():
    """
    Reads the ANOMALY_DB_URL from the .env file and returns a live 
    connection to the Postgres database.
    """
    # 1. Find the .env file (it lives one folder up from this file)
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    
    # 2. Read the .env file manually (so we don't need to install extra packages)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    # 3. Get the secret URL
    db_url = os.environ.get("ANOMALY_DB_URL")
    
    if not db_url:
        raise ValueError("❌ ERROR: ANOMALY_DB_URL not found in your .env file! Please check it.")
    
    # 4. Return the connection
    return psycopg.connect(db_url)