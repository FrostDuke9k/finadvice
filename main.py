# main.py
import requests
from bs4 import BeautifulSoup
import hashlib
import time
from datetime import datetime
import json

import database
import config

from openai import OpenAI # Import the OpenAI library

# --- Helper Functions ---
def get_content_hash(content_string):
    """Generates an MD5 hash for a string to detect changes."""
    if not content_string:
        content_string = ""
    return hashlib.md5(content_string.encode('utf-8')).hexdigest()

def fetch_web_content(url, source_name):
    """
    Fetches web content from the given URL.
    """
    print(f"[{datetime.now()}] Fetching from: {url} for {source_name}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 UKFinanceTaxMonitorBot/1.0'
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status() 
        
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or 'text/plain' in content_type or not content_type:
            return response.text
        else:
            print(f"[{datetime.now()}] Warning: Content type for {url} is '{content_type}', not plain text/HTML. Skipping full processing.")
            return None 
    except requests.exceptions.Timeout:
        print(f"[{datetime.now()}] Error: Timeout while fetching {url} for {source_name}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[{datetime.now()}] Error: HTTP error {e.response.status_code} while fetching {url} for {source_name}. This site may be blocking automated access.")
        return None
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error: Could not fetch {url} for {source_name}. Details: {e}")
        return None
    except Exception as e: 
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
            href = link_tag['href']
            link_url = href 

    extracted_summary = f"Title: {title} - Snippet: {paragraph[:200]}..."
    return extracted_summary, link_url

def analyze_content_for_changes_ai(previous_content_summary, current_content_summary, source_name, full_html_content=None):
    """
    Analyzes content changes using OpenAI API to extract structured financial/tax information.
    """
    print(f"[{datetime.now()}] AI Analyzing changes for {source_name} with OpenAI...")

    if not config.OPENAI_API_KEY:
        print(f"[{datetime.now()}] Error: OPENAI_API_KEY not configured. Skipping AI analysis.")
        return {
            "change_type": "Configuration Error",
            "significance_level": "High",
            "main_summary": "OpenAI API key not found. Unable to perform AI analysis.",
            "key_details": [],
            "affected_parties": []
        }

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    content_to_analyze = current_content_summary 

    if previous_content_summary == current_content_summary:
        print(f"[{datetime.now()}] AI Analysis: Content summaries are identical for {source_name}. Assuming no significant semantic change.")
        return {
            "change_type": "No Semantic Change Detected (Summary Identical)",
            "significance_level": "Low",
            "main_summary": "The textual summary of the content appears identical to the previous version.",
            "key_details": [],
            "affected_parties": []
        }

    system_prompt = """You are a specialized AI assistant expert in UK finance and tax law.
Your task is to analyze provided text content from UK government or financial regulatory websites.
The content represents a new page or an update to an existing page.
Extract structured information relevant to financial advice, tax regulations, and official schemes for UK individuals and businesses.
You MUST output a single, valid JSON object and nothing else. Do not include any explanatory text before or after the JSON object."""

    user_prompt = f"""The content from source '{source_name}' has been updated or is new.
Previous summary snippet (if available): "{previous_content_summary[:200]}..."
Current content snippet to analyze: "{content_to_analyze}"

Please analyze the "Current content snippet" and provide a structured JSON output with the following fields:
- "change_type": (String) Classify the type of information or change (e.g., "Tax Rate Update", "New Savings Scheme", "Regulatory Guidance Change", "Eligibility Criteria Update", "General Announcement", "Economic Outlook", "Minor Textual Correction").
- "significance_level": (String) Estimate the significance for an average UK individual or small business (e.g., "High", "Medium", "Low", "Informational").
- "main_summary": (String) A concise summary (2-3 sentences) of the core information or change.
- "key_details": (Array of Strings) List specific key details, such as new rates, important dates, specific figures, names of schemes, or key conditions.
- "affected_parties": (Array of Strings) List who is primarily affected (e.g., "Individuals", "Self-Employed", "Small Businesses", "Pensioners", "Investors", "Home Buyers", "Low-Income Earners").
- "actionable_insights": (Array of Strings) Brief, actionable points or considerations for the affected parties. What should they potentially do or look into?
- "referenced_regulation_or_law": (String, optional) If a specific regulation, law name, or document number is clearly mentioned as the basis for the information, state it.
- "source_trustworthiness": (String) Based on the source name ('{source_name}'), categorize as "Official Government/Regulatory" or "General Financial Guidance".

If the content seems trivial, a minor correction, or not substantially finance/tax-related, please reflect this in the "change_type" and "significance_level".
"""

    try:
        print(f"[{datetime.now()}] Sending content for '{source_name}' to OpenAI for analysis...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        
        ai_response_content = response.choices[0].message.content
        print(f"[{datetime.now()}] Received AI analysis for {source_name}.")
        
        analysis_result = json.loads(ai_response_content)
        return analysis_result
    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] Error: Failed to decode JSON response from AI for {source_name}. Error: {e}")
        print(f"AI Response Content was: {ai_response_content}")
        return {
            "change_type": "AI Response Error", "significance_level": "Unknown",
            "main_summary": "Failed to parse structured data from AI response.",
            "key_details": [f"Raw AI output: {ai_response_content[:200]}..."],
            "affected_parties": []
        }
    except Exception as e:
        print(f"[{datetime.now()}] Error: An unexpected error occurred during AI analysis for {source_name}: {e}")
        return {
            "change_type": "AI Processing Error", "significance_level": "Unknown",
            "main_summary": f"An error occurred while communicating with or processing AI response: {str(e)}",
            "key_details": [],
            "affected_parties": []
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
                    print(f"[{datetime.now()}] AI Analysis Result for {source_name}: {ai_analysis_result.get('change_type', 'N/A')} - {ai_analysis_result.get('main_summary', 'N/A')[:60]}...")
                    
                    database.add_detected_change(
                        source_id=source_id,
                        previous_hash=previous_hash,
                        new_hash=current_hash,
                        change_summary=ai_analysis_result.get('main_summary', current_summary), 
                        ai_analysis=ai_analysis_result, 
                        full_text_snippet_from_change=current_summary, 
                        url_of_change=specific_url_of_change if specific_url_of_change else url
                    )
                    detected_changes_summary.append({
                        "source": source_name,
                        "timestamp": datetime.now().isoformat(),
                        "url": specific_url_of_change if specific_url_of_change else url,
                        "analysis_summary": ai_analysis_result.get('main_summary', 'N/A')
                    })
                else:
                    print(f"[{datetime.now()}] AI Analysis: No significant semantic change identified for {source_name}, or AI analysis returned no result, or an error occurred in AI processing that returned None/empty.")

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

def synthesize_answer_with_ai(user_question, context_from_db):
    """
    Uses OpenAI to synthesize a helpful answer to a user's question based on
    context retrieved from the internal knowledge base.
    """
    print(f"[{datetime.now()}] Synthesizing answer for: '{user_question}' using provided context.")

    if not config.OPENAI_API_KEY:
        print(f"[{datetime.now()}] Error: OPENAI_API_KEY not configured. Cannot synthesize answer.")
        return "I am unable to process your request at this time due to a configuration issue. Please contact support."

    if not context_from_db or context_from_db.strip() == "No specific information found in the local knowledge base for the given keywords." or context_from_db.strip() == "Placeholder: Internal search not yet implemented. Context from DB would go here.":
        context_from_db = "No specific information was retrieved from the local knowledge base regarding this query."

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    system_prompt = """You are 'FinanceAdvisor', a helpful AI assistant specializing in UK finance and tax matters.
Your goal is to provide clear, accurate, and concise answers based *primarily* on the context provided from an internal knowledge base.
If the provided context is insufficient to answer the question confidently, clearly state that the information is not available in the current knowledge base rather than speculating.
Always be polite and professional.
Crucially, end every response with the following disclaimer: 'Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation.'"""

    user_prompt = f"""User question: "{user_question}"

Provided context from internal knowledge base:
---
{context_from_db}
---

Based primarily on the provided context, please answer the user's question.
If the context directly answers the question, summarize it clearly.
If the context is related but doesn't directly answer, explain what information the context provides and why it might not fully answer the question.
If the context is "No specific information was retrieved from the local knowledge base regarding this query." or similar, then state that you don't have specific information on that topic in your current knowledge base.
Do not make up information beyond the provided context.
Ensure the answer includes the mandatory disclaimer at the end.
"""

    try:
        print(f"[{datetime.now()}] Sending question and context to OpenAI for answer synthesis...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5 
        )
        
        ai_answer = response.choices[0].message.content
        print(f"[{datetime.now()}] Received synthesized answer from OpenAI.")
        
        disclaimer = "Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation."
        if disclaimer not in ai_answer:
            ai_answer += f"\n\n{disclaimer}"
            
        return ai_answer

    except Exception as e:
        print(f"[{datetime.now()}] Error: An unexpected error occurred during AI answer synthesis: {e}")
        return f"I apologize, but I encountered an error while trying to generate an answer. Please try again later.\n\n{disclaimer}"

def handle_user_questions():
    """Handles user questions by logging, searching DB, and synthesizing AI answers."""
    print("\n--- Fiscal Advisor Q&A ---")
    print("Type 'quit' to exit Q&A mode.")
    while True:
        try:
            user_question = input("Ask your finance question: ")
            if user_question.lower() == 'quit':
                break
            if not user_question.strip():
                continue

            print(f"Received question: '{user_question}'")
            
            enquiry_id = database.add_user_enquiry(question_text=user_question, processing_status="processing_search")
            if not enquiry_id:
                print("Could not log your question to the database. Please try again.")
                continue

            keywords = [kw.lower() for kw in user_question.split() if len(kw) > 2]
            print(f"Searching database with keywords: {keywords}")

            search_results = database.search_knowledge_base(keywords) 
            
            retrieved_context_summary = ""
            if search_results:
                print(f"Found {len(search_results)} potentially relevant item(s) in the knowledge base:")
                context_parts = []
                for i, result in enumerate(search_results[:3]): 
                    print(f"  Result {i+1} Title/Summary: {result.get('change_summary_from_agent', 'N/A')}")
                    if result.get('raw_ai_analysis_result'):
                        ai_summary = result['raw_ai_analysis_result'].get('main_summary', '')
                        key_details = result['raw_ai_analysis_result'].get('key_details', [])
                        context_parts.append(f"Found information: {ai_summary} Key details: {', '.join(key_details if isinstance(key_details, list) else [str(key_details)])}")
                    elif result.get('change_summary_from_agent'):
                         context_parts.append(f"Found information: {result.get('change_summary_from_agent')}")

                retrieved_context_summary = " ".join(context_parts)
                if not retrieved_context_summary.strip():
                     retrieved_context_summary = "Found some database entries but could not form a concise text summary from them."
                print(f"Context for AI: {retrieved_context_summary[:500]}...") 
            else:
                print("No directly relevant information found in the current knowledge base for your keywords.")
                retrieved_context_summary = "No specific information found in the local knowledge base for the given keywords."

            generated_answer_text = synthesize_answer_with_ai(user_question, retrieved_context_summary)
            
            processing_status = "answered" if "I could not find specific information" not in generated_answer_text and "encountered an error" not in generated_answer_text else "no_info_found"
            database.update_user_enquiry_answer(enquiry_id, retrieved_context_summary[:2000], generated_answer_text, processing_status=processing_status) 
            
            print(f"\nFinanceAdvisor says:\n{generated_answer_text}\n")

        except Exception as e:
            print(f"An error occurred in the Q&A loop: {e}")

# --- Main execution / Example Usage ---
if __name__ == "__main__":
    print("Initializing UK Finance & Tax Law Monitor Agent...")
    
    print("Executing database schema (if needed)...")
    database.execute_schema() 
    
    print("Initializing/Verifying sources in database from CSV...")
    database.initialize_sources()

    agent = LawMonitorAgent()

    try:
        print("\nRunning an initial check for website updates...")
        agent.check_for_updates() 
        print("\nInitial website update check complete.")

        handle_user_questions()

    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
    finally:
        print("Exiting.")