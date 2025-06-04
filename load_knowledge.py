# load_knowledge.py (Revised to load from finbase.json)
import json
import database # Your existing database module
# from datetime import datetime # Already in database.py, but good practice if used here directly

def main():
    json_filepath = 'finbase.json' # Assuming it's in the same directory
    
    print(f"Attempting to load knowledge from: {json_filepath}")
    
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f) # json.load() reads directly from a file object
        print("JSON data loaded and parsed successfully from finbase.json")
    except FileNotFoundError:
        print(f"Error: The JSON file '{json_filepath}' was not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse the content of '{json_filepath}' as JSON.")
        print(f"JSONDecodeError: {e}")
        print("Please ensure the file contains valid JSON.")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading or parsing '{json_filepath}': {e}")
        return

    # Now 'data' holds your Python dictionary/list parsed from finbase.json
    # The following part still depends on the *internal structure* of your finbase.json
    # You will need to customize the looping and data extraction based on that structure.

    entries_processed = 0
    # --- THIS PART IS HIGHLY DEPENDENT ON YOUR finbase.json STRUCTURE ---
    # Example: If your top-level JSON is a dictionary with a key like 'knowledge_points'
    # which holds a list of entries:
    # knowledge_points = data.get('knowledge_points', [])
    #
    # Or, if 'data' itself is a list of knowledge entries:
    # knowledge_points = data

    # Based on the previous snippets from fiscalbase.docx, let's re-use that HYPOTHETICAL structure
    # You MUST adjust this to match the actual structure of finbase.json
    if isinstance(data, dict) and 'knowledgeBase' in data:
        kb = data['knowledgeBase']
        for category_name, category_content in kb.items():
            for sub_category_name, items in category_content.items():
                if isinstance(items, list):
                    for item_detail in items:
                        knowledge_title = item_detail.get('serviceName', item_detail.get('schemeName', 'Untitled Entry'))
                        topic = category_name
                        sub_topic_val = sub_category_name
                        structured_data = item_detail # The item itself is the structured data
                        source_url = item_detail.get('sourceURL')
                        if isinstance(source_url, list): # Handle if sourceURL can be a list
                            source_url = ", ".join(source_url) if source_url else None
                        
                        source_description = f"From '{knowledge_title}' entry in {json_filepath}"

                        # Assuming you have the add_knowledge_entry function in database.py
                        # as discussed previously, accepting these parameters.
                        entry_id = database.add_knowledge_entry(
                            topic=topic,
                            sub_topic=sub_topic_val,
                            knowledge_title=knowledge_title,
                            structured_data_json=structured_data, # Pass the dict directly
                            source_url=source_url,
                            source_description=source_description
                            # manual_notes could be added if you have a field for it
                        )
                        if entry_id:
                            entries_processed += 1
    elif isinstance(data, list): # If finbase.json is directly a list of entries
        for item_detail in data:
            # You'd need to define how to get topic, sub_topic, title from item_detail
            knowledge_title = item_detail.get('serviceName', item_detail.get('schemeName', item_detail.get('knowledge_title', 'Untitled Entry')))
            topic = item_detail.get('topic', 'General') # Default topic if not specified
            sub_topic_val = item_detail.get('sub_topic')
            structured_data = item_detail
            source_url = item_detail.get('sourceURL')
            if isinstance(source_url, list):
                source_url = ", ".join(source_url) if source_url else None
            source_description = f"From '{knowledge_title}' entry in {json_filepath}"

            entry_id = database.add_knowledge_entry(
                topic=topic,
                sub_topic=sub_topic_val,
                knowledge_title=knowledge_title,
                structured_data_json=structured_data,
                source_url=source_url,
                source_description=source_description
            )
            if entry_id:
                entries_processed += 1
    else:
        print("Could not determine the primary structure of the JSON data (expected a top-level list or a dict with 'knowledgeBase').")
        print("Please check the structure of your finbase.json and adapt the parsing logic in this script.")

    if entries_processed > 0:
        print(f"Successfully processed and attempted to add {entries_processed} knowledge entries from {json_filepath}.")
    else:
        print(f"No knowledge entries were processed from {json_filepath}. Please check the JSON structure and the parsing logic.")

if __name__ == "__main__":
    # Ensure your .env file is accessible for DATABASE_URL for database.py
    # Run main.py once if you've updated schema.sql with KnowledgeEntries table to create it.
    main()