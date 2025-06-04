# database.py
import psycopg2
import psycopg2.extras # For dictionary cursors
from psycopg2 import sql # For safe SQL query composition
import csv # Import the csv module
import config # Still needed for DATABASE_URL
from datetime import datetime
import json # For handling JSON data in knowledge entries

# --- (get_db_connection, execute_schema, get_active_sources, update_source_state, add_detected_change functions remain the same as previously provided) ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        raise

def execute_schema():
    """Executes the schema.sql file to create tables if they don't exist."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Assuming schema.sql is in the same directory
        with open('schema.sql', 'r') as f:
            cur.execute(f.read())
        conn.commit()
        cur.close()
        conn.close()
        print("Database schema executed successfully.")
    except psycopg2.Error as e:
        print(f"Error executing schema: {e}")
    except FileNotFoundError:
        print("schema.sql not found. Please ensure it's in the correct location.")


def _read_sources_from_csv(csv_filepath="UK_Government_Finance_and_Tax_Websites.csv"):
    """Reads sources from the provided CSV file."""
    sources = []
    try:
        with open(csv_filepath, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            # Expected headers: "Website/Service", "URL", "Description"
            # The CSV reader will handle the first line as headers.
            for row in reader:
                name = row.get("Website/Service")
                url = row.get("URL")
                # Basic validation
                if name and url and url.startswith(('http://', 'https://')):
                    sources.append({"name": name.strip(), "url": url.strip()})
                elif name and url: # Attempt to fix common issue if http(s) is missing
                    print(f"Warning: URL for '{name}' in CSV is missing http(s) prefix. Assuming https.")
                    sources.append({"name": name.strip(), "url": "https://" + url.strip()})
                else:
                    print(f"Skipping invalid row in CSV: {row}")
        print(f"Read {len(sources)} sources from {csv_filepath}")
    except FileNotFoundError:
        print(f"Error: The CSV file '{csv_filepath}' was not found.")
    except Exception as e:
        print(f"Error reading CSV file '{csv_filepath}': {e}")
    return sources

def initialize_sources():
    """
    Initializes sources in the MonitoredSources table from the CSV file.
    It will insert new sources and will not update existing ones based on name.
    """
    sources_from_csv = _read_sources_from_csv()
    if not sources_from_csv:
        print("No sources found in CSV or CSV could not be read. Skipping source initialization.")
        return

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        inserted_count = 0
        for source_data in sources_from_csv:
            name = source_data["name"]
            url = source_data["url"]
            # Upsert logic: Insert if not exists (based on unique name), do nothing if it exists.
            # This prevents duplicate entries if the script is run multiple times
            # but also means it won't update URLs for existing names via CSV.
            # For URL updates, manual DB intervention or more complex logic would be needed.
            cur.execute("""
                INSERT INTO MonitoredSources (name, url, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING;
            """, (name, url, True))
            if cur.rowcount > 0: # Check if a row was actually inserted
                inserted_count += 1
        
        conn.commit()
        if inserted_count > 0:
            print(f"{inserted_count} new sources initialized in the database from CSV.")
        else:
            print("No new sources to add from CSV; existing sources remain.")

    except psycopg2.Error as e:
        print(f"Error initializing sources from CSV: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            if not cur.closed:
                 cur.close()
            conn.close()

def get_active_sources():
    """Retrieves all active sources from the MonitoredSources table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, name, url, last_content_hash, last_summary FROM MonitoredSources WHERE is_active = TRUE;")
        sources = cur.fetchall()
        # Convert RealDictRow objects to plain dicts for easier use outside this module if necessary
        return [dict(source) for source in sources]
    except psycopg2.Error as e:
        print(f"Error fetching active sources: {e}")
        return []
    finally:
        if conn:
            if not cur.closed:
                 cur.close()
            conn.close()

def update_source_state(source_id, new_hash, new_summary):
    """Updates the last_content_hash, last_summary, and last_checked_at for a source."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE MonitoredSources
            SET last_content_hash = %s, last_summary = %s, last_checked_at = %s
            WHERE id = %s;
        """, (new_hash, new_summary, datetime.now(), source_id))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error updating source state for ID {source_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            if not cur.closed:
                 cur.close()
            conn.close()

def add_detected_change(source_id, previous_hash, new_hash, change_summary, ai_analysis, full_text_snippet_from_change, url_of_change): # Parameter name updated
    """Adds a new detected change to the DetectedChanges table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO DetectedChanges
            (source_id, previous_content_hash, new_content_hash, change_summary_from_agent, raw_ai_analysis_result, full_text_snippet_from_change, url_of_change, detected_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (source_id, previous_hash, new_hash, change_summary, 
              psycopg2.extras.Json(ai_analysis) if ai_analysis else None, 
              full_text_snippet_from_change, # Variable updated to match parameter
              url_of_change, datetime.now()))
        conn.commit()
        print(f"Detected change for source ID {source_id} added to database.")
    except psycopg2.Error as e:
        print(f"Error adding detected change for source ID {source_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            if not cur.closed:
                 cur.close()
            conn.close()

def add_user_enquiry(question_text, retrieved_context=None, generated_answer=None, processing_status="pending"):
    """Adds a new user enquiry to the UserEnquiries table."""
    conn = None
    entry_id = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO UserEnquiries (question_text, retrieved_context, generated_answer, processing_status, timestamp_asked)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
        """, (question_text, retrieved_context, generated_answer, processing_status, datetime.now()))
        entry_id = cur.fetchone()[0] # Get the ID of the newly inserted row
        conn.commit()
        print(f"User enquiry added to database with ID: {entry_id}")
        return entry_id
    except psycopg2.Error as e:
        print(f"Error adding user enquiry: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            if not cur.closed:
                 cur.close()
            conn.close()

def update_user_enquiry_answer(enquiry_id, retrieved_context, generated_answer, processing_status="answered"):
    """Updates an existing user enquiry with the context found and the generated answer."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE UserEnquiries
            SET retrieved_context = %s, generated_answer = %s, processing_status = %s
            WHERE id = %s;
        """, (retrieved_context, generated_answer, processing_status, enquiry_id))
        conn.commit()
        print(f"User enquiry ID {enquiry_id} updated with answer.")
    except psycopg2.Error as e:
        print(f"Error updating user enquiry ID {enquiry_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            if not cur.closed:
                cur.close()
            conn.close()

def search_knowledge_base(keywords: list):
    """
    Searches the DetectedChanges table for entries matching the given keywords.
    Searches in 'change_summary_from_agent' and specific fields within 'raw_ai_analysis_result'.
    """
    if not keywords:
        return []

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Constructing the WHERE clause for searching
        # This is a basic example; more advanced text search (like full-text search)
        # could be implemented for better results.
        # We'll search for any of the keywords.

        # Search conditions for text fields
        text_search_conditions = []
        for keyword in keywords:
            # ILIKE for case-insensitive search
            text_search_conditions.append(sql.SQL("change_summary_from_agent ILIKE %s"))
            # Search within common JSONB text fields
            text_search_conditions.append(sql.SQL("raw_ai_analysis_result->>'main_summary' ILIKE %s"))
            text_search_conditions.append(sql.SQL("raw_ai_analysis_result->>'change_type' ILIKE %s"))
            # To search in an array within JSONB (e.g., 'key_details'):
            # text_search_conditions.append(sql.SQL("EXISTS (SELECT 1 FROM jsonb_array_elements_text(raw_ai_analysis_result->'key_details') AS elem WHERE elem ILIKE %s)"))


        # Parameters for the query, ensuring each keyword is wrapped for ILIKE
        query_params = []
        for _ in range(len(keywords)): # For each keyword, we have multiple fields to check
            for keyword in keywords: # This repetition is not ideal, let's refine
                # This needs to be structured so each keyword is tried against each condition group
                pass # Will restructure below

        # Let's refine the query construction for clarity and correctness
        # We want to find rows where ANY of the keywords match in ANY of the target fields.

        # Build individual LIKE conditions for each keyword
        keyword_like_patterns = [f"%{kw}%" for kw in keywords]

        # Build OR conditions for each field for all keywords
        # This can get complex quickly with many keywords and fields.
        # A simpler approach for now: search if any keyword appears in main_summary or change_summary_from_agent

        # Simpler query: Check if any keyword is in main_summary or change_summary_from_agent
        # This example uses OR logic: find if *any* keyword matches.
        conditions = []
        params = []
        for pattern in keyword_like_patterns:
            conditions.append(sql.SQL("change_summary_from_agent ILIKE %s"))
            params.append(pattern)
            conditions.append(sql.SQL("raw_ai_analysis_result->>'main_summary' ILIKE %s"))
            params.append(pattern)
            conditions.append(sql.SQL("raw_ai_analysis_result->>'change_type' ILIKE %s"))
            params.append(pattern)
            # Example for searching within a JSON array (like 'key_details' or 'affected_parties')
            # This requires ensuring 'key_details' exists and is an array.
            # conditions.append(sql.SQL("EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(raw_ai_analysis_result->'key_details', '[]'::jsonb)) AS elem WHERE elem ILIKE %s)"))
            # params.append(pattern)


        if not conditions:
            return []

        query_sql = sql.SQL("SELECT id, source_id, detected_at, change_summary_from_agent, raw_ai_analysis_result, url_of_change FROM DetectedChanges WHERE ") + sql.SQL(" OR ").join(conditions) + sql.SQL(" ORDER BY detected_at DESC LIMIT 10;")

        # print(f"Search query: {query_sql.as_string(conn)}") # For debugging
        # print(f"Search params: {params}") # For debugging

        cur.execute(query_sql, params)
        results = cur.fetchall()
        return [dict(row) for row in results]

    except psycopg2.Error as e:
        print(f"Error searching knowledge base: {e}")
        return []
    finally:
        if conn:
            if not cur.closed:
                cur.close()
            conn.close()

def add_knowledge_entry(topic, sub_topic, knowledge_title, structured_data_json, source_url=None, source_description=None, manual_notes=None):
    """Adds a new knowledge entry to the KnowledgeEntries table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Ensure structured_data_json is a valid JSON string for PostgreSQL's JSONB
        # If it's already a Python dict, psycopg2 can handle it with extras.Json
        if isinstance(structured_data_json, dict):
            db_json_data = psycopg2.extras.Json(structured_data_json)
        elif isinstance(structured_data_json, str):
            # Validate if it's a JSON string, then let DB handle it, or parse and pass as dict
            try:
                parsed_json = json.loads(structured_data_json)
                db_json_data = psycopg2.extras.Json(parsed_json)
            except json.JSONDecodeError:
                print(f"Warning: structured_data_json for '{knowledge_title}' is not a valid JSON string. Storing as plain text in notes or skipping.")
                # Handle error appropriately, e.g., skip or store differently
                # For this example, we'll try to insert what we have, but ideally, it should be valid JSON.
                # If your JSONB column is NOT NULL, this will fail if db_json_data isn't set.
                # Let's assume for now the input `structured_data_json` will be a Python dict.
                raise ValueError("structured_data_json must be a dictionary or valid JSON string for JSONB field")

        else:
            raise ValueError("structured_data_json must be a dictionary or valid JSON string for JSONB field")

        cur.execute("""
            INSERT INTO KnowledgeEntries 
            (topic, sub_topic, knowledge_title, structured_data, source_url, source_description, manual_notes, created_at, last_reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (topic, sub_topic, knowledge_title, db_json_data, source_url, 
              source_description, manual_notes, datetime.now(), datetime.now()))
        entry_id = cur.fetchone()[0]
        conn.commit()
        print(f"Knowledge entry '{knowledge_title}' added with ID: {entry_id}")
        return entry_id
    except psycopg2.Error as e:
        print(f"Error adding knowledge entry '{knowledge_title}': {e}")
        if conn:
            conn.rollback()
        return None
    except ValueError as ve:
        print(f"ValueError for knowledge entry '{knowledge_title}': {ve}")
        return None
    finally:
        if conn:
            if not cur.closed:
                cur.close()
            conn.close()