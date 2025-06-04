-- schema.sql

-- Table to store user questions, AI-sourced information, and identified URLs
CREATE TABLE IF NOT EXISTS UserEnquiries (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    keywords TEXT[],                         -- Keywords extracted from the question for searching
    timestamp_asked TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    ai_generated_information TEXT,           -- The primary answer or information synthesized by AI
    ai_identified_urls TEXT[],             -- URLs suggested by AI as relevant
    
    fetched_content_summary TEXT,            -- Optional: A summary of content fetched from AI-identified URLs
                                             -- (if your app fetches and processes them)

    is_verified BOOLEAN DEFAULT FALSE,       -- For potential future admin/manual verification of the answer's quality
    usage_count INTEGER DEFAULT 0,           -- How many times this stored answer was reused
    source_of_answer VARCHAR(255)            -- e.g., 'live_ai_search_and_synthesis', 'cached_verified_response'
);

-- Optional: Index on keywords for faster searching of past enquiries
CREATE INDEX IF NOT EXISTS idx_userenquiries_keywords ON UserEnquiries USING GIN (keywords);