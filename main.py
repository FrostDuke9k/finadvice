# main.py
import requests # Ensure requests is imported
from bs4 import BeautifulSoup
import hashlib
import time
from datetime import datetime
import json

import database
import config

# --- Helper Functions ---
def get_content_hash(content_string):
    """Generates an MD5 hash for a string to detect changes."""
    if not content_string:
        content_string = ""
    return hashlib.md5(content_string.encode('utf-8')).hexdigest()

# Updated function: Renamed from mock_fetch_web_content
def fetch_web_content(url, source_name):
    """
    Fetches web content from the given URL.
    """
    print(f"[{datetime.now()}] Fetching from: {url} for {source_name}")
    try:
        # Using a common User-Agent. Some websites might block default Python/requests User-Agents.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 UKFinanceTaxMonitorBot/1.0'
        }
        response = requests.get(url, timeout=15, headers=headers) # Increased timeout slightly
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        # Check if content type is likely to be HTML or text based.
        # Some sites might return PDF, images, etc., which BeautifulSoup might not handle well.
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or 'text/plain' in content_type or not content_type: # If no content-type, assume it might be text
            return response.text
        else:
            print(f"[{datetime.now()}] Warning: Content type for {url} is '{content_type}', not plain text/HTML. Skipping full processing of this content type for now.")
            return None # Or handle differently, e.g., download PDF if it's a PDF.

    except requests.exceptions.Timeout:
        print(f"[{datetime.now()}] Error: Timeout while fetching {url} for {source_name}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now()}] Error: HTTP error {e.response.status_code} while fetching {url} for {source_name}")
        return None
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error: Could not fetch {url} for {source_name}. Details: {e}")
        return None
    except Exception as e: # Catch any other unexpected error during fetch
        print(f"[{datetime.now()}] An unexpected error occurred while fetching {url} for {source_name}: {e}")
        return None

def extract_relevant_info(html_content, source_name):
    """
    Placeholder for extracting relevant information using BeautifulSoup.
    This would need to be tailored to the structure of each specific source website.
    """
    if not html_content:
        return "No content", None
    soup = BeautifulSoup(html_content, 'html.parser')
    title_tag = soup.find('h1')
    first_p_tag = soup.find('p')
    title = title_tag.get_text(strip=True) if title_tag else "No title found"
    paragraph = first_p_tag.get_text(strip=True) if first_p_tag else "No paragraph found"
    
    link_url = None
    if first_p_tag:
        link_tag = first_p_tag.find('a')
        if link_tag and 'href' in link_tag.attrs:
            # Ensure the URL is absolute
            href = link_tag['href']
            if href.startswith('/'): # Relative URL
                # This needs the base URL of the source to be truly absolute.
                # For now, just noting it. Proper handling requires parsing the original URL.
                # from urllib.parse import urljoin
                # link_url = urljoin(base_url_of_source, href) # base_url_of_source would need to be passed or derived
                pass # For now, we'll let it be relative or require full URLs in content
            link_url = href


    extracted_summary = f"Title: {title} - Snippet: {paragraph[:200]}..."
    return extracted_summary, link_url

# --- (analyze_content_for_changes_ai function remains the same as previously provided) ---
def analyze_content_for_changes_ai(previous_content_summary, current_content_summary, source_name, full_html_content=None):
    """
    CONCEPTUAL AI/NLP analysis function.
    THIS IS WHERE YOU'LL INTEGRATE WITH AN AI API LIKE OPENAI.
    """
    print(f"[{datetime.now()}] AI Analyzing changes for {source_name}...")
    if previous_content_summary == current_content_summary: 
        return None

    change_description = f"Content changed for {source_name}. Current snippet: '{current_content_summary[:70]}...'"
    if "tax code changes" in current_content_summary.lower():
        return {
            "change_type": "Tax Code Adjustment (Mock)", "impact_level": "High",
            "affected_entities": ["Individuals", "Businesses"],
            "summary_of_change": "Potential changes to income tax bands identified.",
            "key_points": ["Income tax bands may have been adjusted.", "Review official HMRC documents."],
            "actionable_insights": "Check if this affects your tax planning."
        }
    elif "consumer credit" in current_content_summary.lower():
         return {
            "change_type": "Regulatory Guidance (Mock)", "impact_level": "Medium",
            "affected_entities": ["Financial Institutions", "Consumers"],
            "summary_of_change": "New guidance on consumer credit practices.",
            "key_points": ["New rules for consumer credit.", "Effective next quarter."],
            "actionable_insights": "Financial institutions should review compliance."
        }
    return {
        "change_type": "Generic Update (Mock)", "impact_level": "Unknown",
        "summary_of_change": change_description,
        "key_points": ["Content has been updated."],
    }

class LawMonitorAgent:
    def __init__(self):
        print(f"[{datetime.now()}] LawMonitorAgent initialized. Will fetch sources from database.")

    def check_for_updates(self):
        """
        Checks all configured active sources from the database for updates.
        """
        print(f"\n[{datetime.now()}] --- Starting Law Monitor Update Check ---")
        
        active_sources = database.get_active_sources()
        if not active_sources:
            print(f"[{datetime.now()}] No active sources found in the database. Ending check.")
            return []

        detected_changes_summary = []

        for source_data in active_sources:
            source_id = source_data['id']
            source_name = source_data['name']
            url = source_data['url']
            previous_hash = source_data['last_content_hash']
            previous_summary = source_data['last_summary'] if source_data['last_summary'] else "N/A (first check)"

            print(f"[{datetime.now()}] Checking source: {source_name} (ID: {source_id}) from {url}")
            
            # MODIFIED: Call the renamed function
            html_content = fetch_web_content(url, source_name) 

            if not html_content:
                print(f"[{datetime.now()}] Failed to fetch content for {source_name} or content type not suitable. Skipping.")
                continue

            current_summary, specific_url_of_change = extract_relevant_info(html_content, source_name)
            current_hash = get_content_hash(current_summary)

            if current_hash != previous_hash:
                print(f"[{datetime.now()}] Change DETECTED for {source_name}!")
                print(f"  Previous Hash: {previous_hash}, Current Hash: {current_hash}")

                ai_analysis_result = analyze_content_for_changes_ai(previous_summary, current_summary, source_name, full_html_content=html_content)

                if ai_analysis_result:
                    print(f"[{datetime.now()}] AI Analysis Result for {source_name}: {ai_analysis_result.get('change_type', 'N/A')} - {ai_analysis_result.get('summary_of_change', 'N/A')[:60]}...")
                    
                    database.add_detected_change(
                        source_id=source_id,
                        previous_hash=previous_hash,
                        new_hash=current_hash,
                        change_summary=ai_analysis_result.get('summary_of_change', current_summary),
                        ai_analysis=ai_analysis_result,
                        full_text_snippet_from_change=current_summary,
                        url_of_change=specific_url_of_change if specific_url_of_change else url
                    )
                    detected_changes_summary.append({
                        "source": source_name,
                        "timestamp": datetime.now().isoformat(),
                        "url": specific_url_of_change if specific_url_of_change else url,
                        "analysis_summary": ai_analysis_result.get('summary_of_change', 'N/A')
                    })
                else:
                    print(f"[{datetime.now()}] AI Analysis: No significant semantic change identified for {source_name}, or AI analysis returned None.")

                database.update_source_state(source_id, current_hash, current_summary)
            else:
                print(f"[{datetime.now()}] No change detected for {source_name} (Hash: {current_hash}).")

        if detected_changes_summary:
            print(f"\n[{datetime.now()}] --- Summary of Detected Changes This Cycle ---")
            for change in detected_changes_summary:
                print(f"  Source: {change['source']}, Summary: {change['analysis_summary'][:100]}...")
        else:
            print(f"\n[{datetime.now()}] --- No new law/regulation changes detected in this cycle. ---")
        
        return detected_changes_summary

# --- Main execution / Example Usage ---
if __name__ == "__main__":
    print("Initializing UK Finance & Tax Law Monitor Agent...")
    
    print("Executing database schema (if needed)...")
    database.execute_schema() 
    
    print("Initializing/Verifying sources in database from CSV...")
    database.initialize_sources()

    agent = LawMonitorAgent()

    try:
        while True:
            agent.check_for_updates()
            sleep_duration = 60 
            print(f"\n[{datetime.now()}] Next check in {sleep_duration} seconds...")
            time.sleep(sleep_duration) 
    except KeyboardInterrupt:
        print("\nMonitor agent stopped by user.")
    finally:
        print("Exiting.")