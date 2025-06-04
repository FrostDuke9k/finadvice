# main.py
import requests
from bs4 import BeautifulSoup # May still be needed if you fetch and parse URL content
import time
from datetime import datetime
import json

import database
import config # For API keys and DB URL

from openai import OpenAI

# --- fetch_web_content and extract_relevant_info might still be needed ---
# --- if your app fetches content from URLs OpenAI identifies. ---
def fetch_web_content(url, source_name="identified_source"): # source_name is less critical now
    """ Fetches web content from the given URL. """
    print(f"[{datetime.now()}] Fetching content from URL: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 FinAdviceBot/2.0'
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status() 
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or 'text/plain' in content_type or not content_type:
            # Basic cleaning of HTML before sending to AI (optional, can be more sophisticated)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Get text, remove script/style, limit length
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:15000] # Limit content length to manage token usage
        else:
            print(f"[{datetime.now()}] Warning: Content type for {url} is '{content_type}'. Returning None.")
            return None 
    except Exception as e: 
        print(f"[{datetime.now()}] Error fetching content from {url}: {e}")
        return None

def get_urls_and_initial_info_from_ai(user_question):
    """
    Asks OpenAI to provide an initial answer/information and suggest relevant URLs
    based on the user's question.
    """
    print(f"[{datetime.now()}] Asking OpenAI to find info and URLs for: '{user_question}'")
    if not config.OPENAI_API_KEY:
        print(f"[{datetime.now()}] Error: OPENAI_API_KEY not configured.")
        return {"answer": "OpenAI API key not configured.", "urls": []}

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    system_prompt = """You are an AI assistant helping a user find financial information relevant to the UK.
Based on the user's question, provide:
1. A direct answer or summary of information if readily available from your knowledge.
2. A list of up to 3 potentially relevant, high-authority UK government or financial regulatory URLs if applicable.
   Prioritize .gov.uk, .org.uk (official bodies like MoneyHelper, FCA). Avoid purely commercial sites unless they are highly reputable sources for general guidance (like NS&I).

Format your response as a single JSON object with two keys: "answer" (string) and "urls" (array of strings).
Example: {"answer": "The current UK Personal Allowance is X.", "urls": ["https://www.gov.uk/income-tax-rates"]}
If no specific URLs come to mind or are not appropriate for the question, provide an empty array for "urls".
"""
    user_prompt = f"User question: \"{user_question}\"\n\nPlease provide your answer and relevant URLs in the specified JSON format."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125", # Or gpt-4 for better URL suggestion and info
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        ai_response_content = response.choices[0].message.content
        print(f"[{datetime.now()}] Received initial info and URLs from OpenAI.")
        parsed_response = json.loads(ai_response_content)
        return parsed_response
    except Exception as e:
        print(f"[{datetime.now()}] Error getting initial info/URLs from OpenAI: {e}")
        return {"answer": "Sorry, I encountered an error trying to find initial information.", "urls": []}

def synthesize_final_answer_with_ai(user_question, initial_ai_answer, fetched_url_contents: list):
    """
    Synthesizes a final answer using initial AI info and content fetched from URLs.
    """
    print(f"[{datetime.now()}] Synthesizing final answer for: '{user_question}'")
    if not config.OPENAI_API_KEY:
        return "OpenAI API key not configured. Cannot synthesize final answer."

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    context_from_urls = "\n\n".join([f"Content from URL {i+1}:\n{content[:3000]}..." for i, content in enumerate(fetched_url_contents) if content])
    if not context_from_urls:
        context_from_urls = "No additional content was successfully fetched from the identified URLs."

    system_prompt = """You are 'FinanceAdvisor', a helpful AI assistant specializing in UK finance and tax matters.
Your goal is to provide a comprehensive and accurate answer to the user's question.
You have been provided with an initial AI-generated answer and content fetched from relevant URLs.
Integrate all this information to formulate your final response.
If the fetched content from URLs provides more specific or up-to-date details, prioritize that.
If the initial answer was good and the URL content doesn't add much, you can reiterate or slightly expand on the initial answer.
If contradictions arise, point them out or use your best judgment based on what seems most authoritative (e.g., .gov.uk content).
Always be polite and professional.
Crucially, end every response with the following disclaimer: 'Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation.'"""

    user_prompt = f"""User question: "{user_question}"

Initial AI-generated information/answer:
---
{initial_ai_answer}
---

Content fetched from potentially relevant URLs:
---
{context_from_urls}
---

Please synthesize a final, comprehensive answer to the user's question using all the provided information.
Ensure the answer includes the mandatory disclaimer at the end.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", # Use a more capable model for this synthesis task
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5
        )
        final_answer = response.choices[0].message.content
        disclaimer = "Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation."
        if disclaimer not in final_answer:
            final_answer += f"\n\n{disclaimer}"
        return final_answer
    except Exception as e:
        print(f"[{datetime.now()}] Error synthesizing final answer with OpenAI: {e}")
        return f"Sorry, I encountered an error refining the answer. The initial information was: {initial_ai_answer}\n\nDisclaimer: This information is for guidance only..."

def handle_user_questions():
    """Handles user questions using AI for sourcing and synthesis, with caching."""
    print("\n--- Fiscal Advisor Q&A ---")
    print("Type 'quit' to exit Q&A mode.")
    while True:
        try:
            user_question = input("Ask your finance question: ").strip()
            if user_question.lower() == 'quit':
                break
            if not user_question:
                continue

            print(f"[{datetime.now()}] Received question: '{user_question}'")
            keywords = [kw.lower().strip('?,.') for kw in user_question.split() if len(kw.strip('?,.')) > 2]
            print(f"[{datetime.now()}] Extracted keywords: {keywords}")

            # 1. Check cache for similar, verified questions
            cached_answer = None
            if keywords:
                cached_enquiries = database.search_stored_enquiries(keywords, verified_only=True)
                if cached_enquiries:
                    cached_answer_record = cached_enquiries[0] # Use the top one for simplicity
                    cached_answer = cached_answer_record['ai_generated_information']
                    database.increment_enquiry_usage_count(cached_answer_record['id'])
                    print(f"[{datetime.now()}] Found verified cached answer (ID: {cached_answer_record['id']}).")
                    database.add_or_update_user_enquiry( # Log this instance of asking
                        question_text=user_question, keywords=keywords,
                        ai_generated_information=cached_answer,
                        source_of_answer=f"cache_hit_verified_enquiry_id_{cached_answer_record['id']}"
                    )

            final_response_to_user = None
            if cached_answer:
                final_response_to_user = cached_answer
            else:
                print(f"[{datetime.now()}] No suitable cached answer. Proceeding with live AI sourcing.")
                # Log initial enquiry before potentially lengthy AI calls
                enquiry_id = database.add_or_update_user_enquiry(question_text=user_question, keywords=keywords, source_of_answer="pending_ai_processing")
                if not enquiry_id:
                    print("Failed to log initial enquiry. Aborting.")
                    continue

                # Step 1: Get initial info and URLs from AI
                ai_sourcing_result = get_urls_and_initial_info_from_ai(user_question)
                initial_ai_answer = ai_sourcing_result.get("answer", "AI could not provide initial information.")
                identified_urls = ai_sourcing_result.get("urls", [])
                
                print(f"[{datetime.now()}] Initial AI answer: {initial_ai_answer[:200]}...")
                print(f"[{datetime.now()}] AI identified URLs: {identified_urls}")

                # Step 2: Fetch content from identified URLs (if any)
                fetched_contents = []
                if identified_urls:
                    for url in identified_urls[:2]: # Limit to fetching, say, top 2 URLs to manage time/cost
                        content = fetch_web_content(url)
                        if content:
                            fetched_contents.append(content)
                
                fetched_content_summary_for_db = " ".join([c[:500]+"..." for c in fetched_contents]) if fetched_contents else None

                # Step 3: Synthesize final answer
                final_response_to_user = synthesize_final_answer_with_ai(user_question, initial_ai_answer, fetched_contents)
                
                # Step 4: Store the new Q&A pair
                database.add_or_update_user_enquiry(
                    enquiry_id=enquiry_id, # Update the existing record
                    question_text=user_question, keywords=keywords,
                    ai_generated_information=final_response_to_user,
                    ai_identified_urls=identified_urls if identified_urls else None,
                    fetched_content_summary=fetched_content_summary_for_db,
                    source_of_answer="live_ai_synthesis_with_url_content" if fetched_contents else "live_ai_synthesis_general_knowledge",
                    is_verified=False # New AI answers are not verified by default
                )

            print(f"\nFinanceAdvisor says:\n{final_response_to_user}\n")

        except Exception as e:
            print(f"[{datetime.now()}] An error occurred in the Q&A loop: {e}")
            import traceback
            traceback.print_exc()

# --- Main execution ---
if __name__ == "__main__":
    print("Initializing UK Finance & Tax Law Fiscal Advisor...")
    
    print("Executing database schema (if needed)...")
    database.execute_schema() 
    
    # No proactive monitoring agent in this new approach
    # No initial source loading from CSV in this new approach

    try:
        handle_user_questions() # Directly go to Q&A mode
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
    finally:
        print("Exiting.")