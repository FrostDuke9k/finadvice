# main.py
import requests
from bs4 import BeautifulSoup # For basic HTML cleaning in fetch_web_content
import time
from datetime import datetime
import json

import database # Your database module (as updated in Turn 48)
import config   # For API keys and DB URL (as updated in Turn 45)

from openai import OpenAI # Import the OpenAI library

def fetch_web_content(url, source_name="identified_source"):
    """ 
    Fetches web content from the given URL and extracts clean text.
    Limits content length to manage token usage.
    """
    print(f"[{datetime.now()}] Fetching content from URL: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 FinAdviceBot/2.0'
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status() 
        
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or 'text/plain' in content_type or not content_type:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script_or_style in soup(["script", "style", "header", "footer", "nav", "aside"]): # Remove common non-content tags
                script_or_style.decompose()
            text = soup.get_text(separator=' ', strip=True)
            # Further clean up multiple newlines or excessive whitespace if needed
            text = ' '.join(text.split())
            print(f"[{datetime.now()}] Fetched and cleaned text from {url} (length: {len(text)})")
            return text[:15000] # Limit content length to manage token usage (approx 4000-5000 tokens)
        else:
            print(f"[{datetime.now()}] Warning: Content type for {url} is '{content_type}'. Returning None.")
            return None 
    except Exception as e: 
        print(f"[{datetime.now()}] Error fetching or processing content from {url}: {e}")
        return None

def get_urls_and_initial_info_from_ai(user_question):
    """
    Asks OpenAI to provide an initial answer/information and suggest relevant URLs
    based on the user's question, with a strong emphasis on UK sources and an explanation if no URLs are found.
    (Incorporates the reinforced prompt from Turn 54)
    """
    print(f"[{datetime.now()}] Asking OpenAI to find info and URLs for: '{user_question}'")
    if not config.OPENAI_API_KEY:
        print(f"[{datetime.now()}] Error: OPENAI_API_KEY not configured.")
        return {"answer": "OpenAI API key not configured.", "urls": [], "url_search_explanation": "Configuration error."}

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    system_prompt = """You are an AI assistant helping a user find financial information relevant to the UK.
Based on the user's question, you MUST provide a response as a single, valid JSON object.
This JSON object should contain the following keys:
1.  "answer": (String) A direct answer or summary of information related to the user's question if readily available from your knowledge.
2.  "urls": (Array of Strings) A list of up to 3 potentially relevant, high-authority URLs. These URLs MUST be specific to the United Kingdom and preferably from official government sources (.gov.uk), UK financial regulatory bodies (.org.uk like FCA, MoneyHelper), or highly trusted UK financial institutions (like NS&I). Avoid purely commercial sites unless they are highly reputable for general UK guidance.
3.  "url_search_explanation": (String) If, after thorough consideration, you cannot identify any suitable high-authority UK URLs directly relevant to the user's specific question, the "urls" array should be empty, AND you MUST provide a brief explanation in this field (e.g., "User's question is too general for specific official URLs", "No direct official UK government page found for this specific strategic query", "Information is commonly known and not tied to a single URL"). If you do provide URLs, this field can state "Relevant URLs provided."

Example of a response WITH URLs:
{"answer": "The current UK Personal Allowance is £12,570.", "urls": ["https://www.gov.uk/income-tax-rates"], "url_search_explanation": "Relevant URLs provided."}

Example of a response WITHOUT URLs:
{"answer": "Diversification is key for long-term investment strategy.", "urls": [], "url_search_explanation": "The question about investment strategy is broad; specific official URLs are less applicable than general principles."}
"""
    user_prompt = f"User question: \"{user_question}\"\n\nPlease provide your answer, relevant UK-specific URLs, and a URL search explanation in the specified JSON format."

    try:
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
        print(f"[{datetime.now()}] Received initial info, URLs, and explanation from OpenAI.")
        
        parsed_response = json.loads(ai_response_content)
        
        if 'answer' not in parsed_response: parsed_response['answer'] = "AI response structure was incomplete (missing answer)."
        if 'urls' not in parsed_response or not isinstance(parsed_response['urls'], list):
            parsed_response['urls'] = []
            if 'url_search_explanation' not in parsed_response: 
                 parsed_response['url_search_explanation'] = "AI response structure was incomplete (missing urls and explanation)."
        if 'url_search_explanation' not in parsed_response:
             parsed_response['url_search_explanation'] = "No explanation provided by AI for URL search."
             
        return parsed_response
        
    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] Error: Failed to decode JSON response from AI (get_urls_and_initial_info_from_ai). Error: {e}")
        ai_response_content_for_log = locals().get('ai_response_content', 'Not available')
        print(f"AI Response Content was: {ai_response_content_for_log}")
        return {"answer": "Sorry, I encountered an error parsing the AI's sourcing response.", "urls": [], "url_search_explanation": "JSON parsing error."}
    except Exception as e:
        print(f"[{datetime.now()}] Error getting initial info/URLs from OpenAI: {e}")
        return {"answer": "Sorry, I encountered an error trying to find initial information.", "urls": [], "url_search_explanation": f"API or other error: {str(e)}"}

def synthesize_final_answer_with_ai(user_question, initial_ai_answer, fetched_url_contents: list):
    """
    Synthesizes a final answer using initial AI info and content fetched from URLs.
    """
    print(f"[{datetime.now()}] Synthesizing final answer for: '{user_question}'")
    if not config.OPENAI_API_KEY:
        return "OpenAI API key not configured. Cannot synthesize final answer."

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    context_from_urls = "\n\n".join([f"Content from URL {i+1}:\n{content}" for i, content in enumerate(fetched_url_contents) if content])
    if not context_from_urls.strip() and not fetched_url_contents: # No URLs were provided or all fetches failed
        context_from_urls = "No additional content was successfully fetched from any identified URLs."
    elif not context_from_urls.strip() and fetched_url_contents: # URLs provided, but all fetches returned empty/None
        context_from_urls = "Content could not be fetched or was empty for the identified URLs."


    system_prompt = """You are 'FinanceAdvisor', a helpful AI assistant specializing in UK finance and tax matters.
Your goal is to provide a comprehensive and accurate answer to the user's question.
You have been provided with an initial AI-generated answer and content fetched from relevant URLs (if any).
Integrate all this information to formulate your final response.
If the fetched content from URLs provides more specific or up-to-date details, prioritize that.
If the initial answer was good and the URL content doesn't add much new relevant information, you can reiterate or slightly expand on the initial answer, referencing that no further details were found in the provided URLs.
If contradictions arise, try to highlight them or use your best judgment based on what seems most authoritative (e.g., content from .gov.uk URLs).
Always be polite and professional.
Crucially, end every response with the following disclaimer: 'Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation.'"""

    user_prompt = f"""User question: "{user_question}"

Initial AI-generated information/answer:
---
{initial_ai_answer}
---

Content fetched from potentially relevant URLs (Note: if this section says "No additional content was successfully fetched...", it means either no URLs were provided to fetch, or fetching failed, or fetched content was empty):
---
{context_from_urls}
---

Please synthesize a final, comprehensive answer to the user's question using all the provided information.
Ensure the answer includes the mandatory disclaimer at the end.
"""
    try:
        print(f"[{datetime.now()}] Sending question and context to OpenAI for final answer synthesis...")
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", # Using a more capable model for synthesis
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
        # Fallback to initial answer if synthesis fails, but still add disclaimer
        disclaimer = "Disclaimer: This information is for guidance only and not professional financial advice. Please consult with a qualified financial advisor for advice tailored to your specific situation."
        error_message = f"I apologize, but I encountered an error while trying to generate a detailed answer. Based on initial information: {initial_ai_answer}"
        if disclaimer not in error_message:
             error_message += f"\n\n{disclaimer}"
        return error_message

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

            cached_answer = None
            cached_enquiry_id = None
            if keywords:
                cached_enquiries = database.search_stored_enquiries(keywords, verified_only=True) # Prioritize verified
                if cached_enquiries:
                    cached_answer_record = cached_enquiries[0]
                    cached_answer = cached_answer_record['ai_generated_information']
                    cached_enquiry_id = cached_answer_record['id']
                    database.increment_enquiry_usage_count(cached_enquiry_id)
                    print(f"[{datetime.now()}] Found verified cached answer (ID: {cached_enquiry_id}).")
            
            final_response_to_user = None
            enquiry_id_for_this_session = None # ID for the current ask, even if cache is hit

            if cached_answer:
                final_response_to_user = cached_answer
                source_of_answer_log = f"cache_hit_verified_enquiry_id_{cached_enquiry_id}"
                # Log this specific instance of the question being answered from cache
                enquiry_id_for_this_session = database.add_or_update_user_enquiry(
                    question_text=user_question, keywords=keywords,
                    ai_generated_information=cached_answer, # Store the cached answer
                    ai_identified_urls=cached_enquiries[0].get('ai_identified_urls'), # Store URLs from cached entry if available
                    source_of_answer=source_of_answer_log
                )
            else:
                print(f"[{datetime.now()}] No suitable verified cached answer. Proceeding with live AI sourcing.")
                # Log initial enquiry before potentially lengthy AI calls
                enquiry_id_for_this_session = database.add_or_update_user_enquiry(question_text=user_question, keywords=keywords, source_of_answer="pending_ai_processing")
                if not enquiry_id_for_this_session:
                    print(f"[{datetime.now()}] Failed to log initial enquiry. Aborting Q&A for this question.")
                    continue

                ai_sourcing_result = get_urls_and_initial_info_from_ai(user_question)
                initial_ai_answer = ai_sourcing_result.get("answer", "AI could not provide initial information.")
                identified_urls = ai_sourcing_result.get("urls", [])
                url_search_explanation = ai_sourcing_result.get("url_search_explanation", "")
                
                print(f"[{datetime.now()}] Initial AI answer: {initial_ai_answer[:200]}...")
                print(f"[{datetime.now()}] AI identified URLs: {identified_urls}")
                if not identified_urls and url_search_explanation:
                    print(f"[{datetime.now()}] AI explanation for no URLs: {url_search_explanation}")

                fetched_contents = []
                if identified_urls:
                    print(f"[{datetime.now()}] Attempting to fetch content from up to 2 identified URLs...")
                    for url in identified_urls[:2]: 
                        content = fetch_web_content(url)
                        if content:
                            fetched_contents.append(content)
                        else:
                            print(f"[{datetime.now()}] Failed to fetch content or content unsuitable from {url}")
                
                fetched_content_summary_for_db = " ".join([c[:500]+"..." for c in fetched_contents]) if fetched_contents else None

                final_response_to_user = synthesize_final_answer_with_ai(user_question, initial_ai_answer, fetched_contents)
                
                source_of_answer_log = "live_ai_synthesis_with_url_content" if fetched_contents else "live_ai_synthesis_general_knowledge"
                if not identified_urls and url_search_explanation != "Relevant URLs provided.": # If AI couldn't find URLs
                    source_of_answer_log += "_no_urls_found_by_ai"

                database.add_or_update_user_enquiry(
                    enquiry_id=enquiry_id_for_this_session, # Update the existing record for this session
                    question_text=user_question, keywords=keywords, # Resend question and keywords for completeness if updating
                    ai_generated_information=final_response_to_user,
                    ai_identified_urls=identified_urls if identified_urls else None,
                    fetched_content_summary=fetched_content_summary_for_db,
                    source_of_answer=source_of_answer_log,
                    is_verified=False 
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
    database.execute_schema() # This will create UserEnquiries if it doesn't exist
    
    # No proactive monitoring agent or CSV source loading in this new approach

    try:
        handle_user_questions() # Directly go to Q&A mode
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
    finally:
        print("Exiting.")