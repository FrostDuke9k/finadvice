# database.py
import psycopg2
import psycopg2.extras 
from psycopg2 import sql
import config # For DATABASE_URL
from datetime import datetime
import json # For potential JSONB operations if any were kept (not in this simplified schema)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        raise

def execute_schema():
    """Executes the schema.sql file to create tables/apply alterations."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        with open('schema.sql', 'r') as f:
            sql_script = f.read()
            cur.execute(sql_script) 
        conn.commit()
        print("Database schema executed successfully.")
    except FileNotFoundError:
        print("schema.sql not found. Please ensure it's in the correct location.")
    except psycopg2.Error as e:
        print(f"Error executing schema: {e}")
    finally:
        if conn:
            if 'cur' in locals() and not cur.closed: cur.close()
            conn.close()

def add_or_update_user_enquiry(question_text, keywords=None, ai_generated_information=None, 
                               ai_identified_urls=None, fetched_content_summary=None, 
                               source_of_answer=None, is_verified=False, enquiry_id=None):
    """Adds a new user enquiry or updates an existing one. Returns the enquiry ID."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if enquiry_id: # Update existing
            # For simplicity, this example just updates all fields.
            # You might want more granular updates.
            cur.execute("""
                UPDATE UserEnquiries 
                SET question_text = %s, keywords = %s, ai_generated_information = %s, 
                    ai_identified_urls = %s, fetched_content_summary = %s, 
                    source_of_answer = %s, is_verified = %s 
                WHERE id = %s
            """, (question_text, keywords, ai_generated_information, ai_identified_urls, 
                  fetched_content_summary, source_of_answer, is_verified, enquiry_id))
            print(f"User enquiry ID {enquiry_id} updated.")
        else: # Insert new
            cur.execute("""
                INSERT INTO UserEnquiries (question_text, keywords, ai_generated_information, 
                                           ai_identified_urls, fetched_content_summary, 
                                           source_of_answer, is_verified, timestamp_asked, usage_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0) RETURNING id;
            """, (question_text, keywords, ai_generated_information, ai_identified_urls, 
                  fetched_content_summary, source_of_answer, is_verified, datetime.now()))
            enquiry_id = cur.fetchone()[0]
            print(f"New user enquiry added with ID: {enquiry_id}")
        
        conn.commit()
        return enquiry_id
    except psycopg2.Error as e:
        print(f"Error adding/updating user enquiry for question '{question_text[:50]}...': {e}")
        if conn: conn.rollback()
        return None
    finally:
        if conn:
            if 'cur' in locals() and not cur.closed: cur.close()
            conn.close()

def search_stored_enquiries(keywords: list, verified_only=True):
    """
    Searches the UserEnquiries table for verified answers matching keywords.
    Returns a list of matching (id, question_text, ai_generated_information, ai_identified_urls) dicts.
    """
    if not keywords:
        return []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Search based on keywords array overlap (&&) or question_text ILIKE
        # This query can be refined for better relevance.
        conditions = []
        params = []

        # Condition for keywords array overlap
        # Ensure keywords are stored consistently (e.g., all lowercase)
        # This expects keywords in the DB to be an array of text.
        conditions.append(sql.SQL("keywords && %s")) 
        params.append(keywords)

        # Optionally add ILIKE conditions for question_text
        # for kw_pattern in [f"%{kw}%" for kw in keywords]:
        #     conditions.append(sql.SQL("question_text ILIKE %s"))
        #     params.append(kw_pattern)

        base_query_select = sql.SQL("SELECT id, question_text, ai_generated_information, ai_identified_urls, usage_count FROM UserEnquiries WHERE ")
        if verified_only:
            base_query_where = sql.SQL("is_verified = TRUE AND (")
        else:
            base_query_where = sql.SQL("(") # Or remove is_verified from WHERE if not needed for unverified search

        if not conditions: # Should not happen if keywords are present
             return []

        query_sql = base_query_select + base_query_where + sql.SQL(" OR ").join(conditions) + sql.SQL(") ORDER BY usage_count DESC, timestamp_asked DESC LIMIT 5;")
        
        cur.execute(query_sql, params)
        results = cur.fetchall()
        return [dict(row) for row in results]
    except psycopg2.Error as e:
        print(f"Error searching stored enquiries: {e}")
        return []
    finally:
        if conn:
            if 'cur' in locals() and not cur.closed: cur.close()
            conn.close()

def increment_enquiry_usage_count(enquiry_id):
    """Increments the usage_count for a specific stored enquiry."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE UserEnquiries SET usage_count = usage_count + 1 WHERE id = %s;", (enquiry_id,))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error incrementing usage count for enquiry ID {enquiry_id}: {e}")
        if conn: conn.rollback()
    finally:
        if conn:
            if 'cur' in locals() and not cur.closed: cur.close()
            conn.close()