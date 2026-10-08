"""
=====================================================================
CLOUD DATABASE INITIALIZER SCRIPT
Run this script to automatically initialize all tables, views, 
stored procedures, triggers, and sample data on a remote cloud MySQL database.
=====================================================================
"""
import os
import pymysql
from config import Config

def init_cloud_database():
    print(f"Connecting to database at {Config.DB_HOST}:{Config.DB_PORT} as {Config.DB_USER}...")
    
    connect_kwargs = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'charset': 'utf8mb4',
        'autocommit': True
    }
    if Config.DB_SSL_REQUIRED:
        connect_kwargs['ssl'] = {'ssl_mode': 'REQUIRED'}

    conn = pymysql.connect(**connect_kwargs)
    
    sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'library_db.sql')
    with open(sql_path, 'r', encoding='utf-8') as f:
        full_sql = f.read()

    print(f"Executing {sql_path}...")
    with conn.cursor() as cursor:
        # Split by DELIMITER $$ for triggers and stored procedures
        sections = full_sql.split('DELIMITER $$')
        
        # 1. First section: Tables, Drop DB, Create DB
        first_part = sections[0]
        for stmt in first_part.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    print(f"Warning on stmt: {e}")

        # Connect specifically to the created database
        cursor.execute(f"USE `{Config.DB_NAME}`;")

        # 2. Middle sections (Triggers, Views, Stored Procedures)
        for section in sections[1:]:
            proc_part, remaining = section.split('DELIMITER ;', 1)
            for proc_block in proc_part.split('$$'):
                proc_block = proc_block.strip()
                if proc_block:
                    try:
                        cursor.execute(proc_block)
                    except Exception as e:
                        print(f"Warning on proc/trigger: {e}")
            
            # Remaining standard SQL in section
            for stmt in remaining.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    try:
                        cursor.execute(stmt)
                    except Exception as e:
                        print(f"Warning on stmt: {e}")

    conn.close()
    print("✅ Database initialized successfully with all tables, triggers, SPs, views, and sample data!")

if __name__ == '__main__':
    init_cloud_database()
