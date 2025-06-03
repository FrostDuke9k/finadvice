-- schema.sql

-- Table to store the sources you are monitoring
CREATE TABLE IF NOT EXISTS MonitoredSources (
    id SERIAL PRIMARY KEY,                      -- Unique identifier for each source
    name VARCHAR(255) UNIQUE NOT NULL,          -- Name of the source (e.g., "HMRC_Tax_Updates")
    url TEXT NOT NULL,                          -- URL of the source
    last_checked_at TIMESTAMP WITH TIME ZONE,   -- When this source was last checked
    last_content_hash VARCHAR(32),              -- MD5 hash of the last known relevant content/summary
    last_summary TEXT,                          -- The actual summary/content that was hashed
    is_active BOOLEAN DEFAULT TRUE              -- Flag to easily enable/disable monitoring for a source
);

-- Table to store detected changes and their AI analysis
CREATE TABLE IF NOT EXISTS DetectedChanges (
    id SERIAL PRIMARY KEY,                                  -- Unique identifier for each detected change
    source_id INTEGER REFERENCES MonitoredSources(id) ON DELETE CASCADE, -- Links to the MonitoredSources table
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- When the change was detected and recorded
    previous_content_hash VARCHAR(32),                      -- Hash of the content before this change (for context)
    new_content_hash VARCHAR(32) NOT NULL,                  -- Hash of the new content that triggered this record
    change_summary_from_agent TEXT,                         -- Brief summary of the change (could be from your extract_relevant_info or a high-level AI summary)
    raw_ai_analysis_result JSONB,                           -- Store structured AI output (e.g., from OpenAI). JSONB is efficient for querying.
    full_text_snippet_from_change TEXT,                     -- The relevant snippet of text identified as changed
    url_of_change TEXT                                      -- Specific URL of the article/page if different from the main source URL (e.g., a direct link to a new announcement)
);

-- You might want to add indexes later for performance on frequently queried columns, e.g.:
-- CREATE INDEX IF NOT EXISTS idx_source_id_detected_at ON DetectedChanges(source_id, detected_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_monitoredsources_is_active ON MonitoredSources(is_active);

-- Add this to your schema.sql file

CREATE TABLE IF NOT EXISTS UserEnquiries (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    timestamp_asked TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Fields to store the information found and answer given:
    -- This is a simplified version; we can expand it later.
    -- For now, let's assume we'll store a summary of what was found and the AI's answer.
    retrieved_context TEXT, -- Summary of relevant info found in your 'DetectedChanges' table
    generated_answer TEXT,  -- The answer provided to the user
    -- Optionally, link to specific rows in DetectedChanges if an answer is based on them
    -- relevant_detected_change_ids INTEGER[], 
    processing_status VARCHAR(50) DEFAULT 'pending' -- e.g., pending, answered, no_info_found
);