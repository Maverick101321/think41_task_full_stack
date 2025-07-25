import psycopg2
import psycopg2.extras
from flask import g, current_app

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db' not in g:
        g.db = psycopg2.connect(current_app.config['SQLALCHEMY_DATABASE_URI'], cursor_factory=psycopg2.extras.DictCursor)
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def execute_query(query, params=None, fetch=None):
    """
    Executes a database query with transaction handling.
    :param query: SQL query string with placeholders (%s).
    :param params: Tuple of parameters to substitute into the query.
    :param fetch: "one" to fetch a single result, "all" to fetch all results.
    :return: Query result or None.
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result = None
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            conn.commit()
            return result
    except psycopg2.Error:
        if conn:
            conn.rollback()
        raise

def init_app(app):
    """Register database functions with the Flask app."""
    app.teardown_appcontext(close_db)