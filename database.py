# database.py
import psycopg2
import psycopg2.extras # For dictionary cursors
from psycopg2 import sql # For safe SQL query composition
import csv # Import the csv module
import config # Still needed for DATABASE_URL
from datetime import datetime

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

def add_detected_change(source_id, previous_hash, new_hash, change_summary, ai_analysis, full_text_snippet, url_of_change):
    """Adds a new detected change to the DetectedChanges table."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO DetectedChanges
            (source_id, previous_content_hash, new_content_hash, change_summary_from_agent, raw_ai_analysis_result, full_text_snippet_from_change, url_of_change, detected_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (source_id, previous_hash, new_hash, change_summary, psycopg2.extras.Json(ai_analysis) if ai_analysis else None, full_text_snippet, url_of_change, datetime.now()))
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