import pymysql
from pymysql.cursors import DictCursor
from flask import g, current_app

def get_db():
    """
    Returns a MySQL connection stored in Flask's application context `g`.
    A single connection is reused for the entire lifecycle of an incoming request.
    """
    if 'db' not in g:
        connect_kwargs = {
            'host': current_app.config['DB_HOST'],
            'port': current_app.config['DB_PORT'],
            'user': current_app.config['DB_USER'],
            'password': current_app.config['DB_PASSWORD'],
            'database': current_app.config['DB_NAME'],
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': False
        }
        if current_app.config.get('DB_SSL_REQUIRED'):
            connect_kwargs['ssl'] = {'ssl_mode': 'REQUIRED'}

        g.db = pymysql.connect(**connect_kwargs)
    return g.db

def close_db(e=None):
    """Closes the active database connection when the request finishes."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_all(sql, params=None):
    """
    Executes a SELECT query and returns all matching rows as a list of dicts.
    Uses parameterized SQL to guarantee SQL Injection prevention.
    """
    db = get_db()
    with db.cursor() as cursor:
        if params is not None and len(params) > 0:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.fetchall()

def query_one(sql, params=None):
    """
    Executes a SELECT query and returns the first row as a dict, or None.
    Uses parameterized SQL to guarantee SQL Injection prevention.
    """
    db = get_db()
    with db.cursor() as cursor:
        if params is not None and len(params) > 0:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.fetchone()

def execute_db(sql, params=None, autocommit=True):
    """
    Executes an INSERT, UPDATE, or DELETE query.
    Returns the last inserted row ID or affected rows.
    """
    db = get_db()
    with db.cursor() as cursor:
        if params is not None and len(params) > 0:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        last_id = cursor.lastrowid
        affected = cursor.rowcount
    if autocommit:
        db.commit()
    return {'last_id': last_id, 'affected': affected}

def call_proc(proc_name, params=None):
    """
    Executes a MySQL Stored Procedure with parameters and returns all result sets.
    """
    db = get_db()
    results = []
    with db.cursor() as cursor:
        cursor.callproc(proc_name, params or ())
        # Fetch the first result set
        result = cursor.fetchall()
        if result:
            results.append(result)
        # Fetch any additional result sets if procedure produced multiple
        while cursor.nextset():
            more = cursor.fetchall()
            if more:
                results.append(more)
    db.commit()
    return results
