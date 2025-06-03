# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (for local development)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

# Example for an AI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # You'll set this in Railway's environment variables

# Define your official sources here or manage them in the DB
# For simplicity, we'll define them here and ensure they are in the DB via initialization logic
OFFICIAL_SOURCES_CONFIG = {
    "HMRC_Tax_Updates": "https://www.gov.uk/government/organisations/hm-revenue-customs/announcements",
    "FCA_Regulations": "https://www.fca.org.uk/news",
    "UK_Treasury_News": "https://www.gov.uk/government/organisations/hm-treasury/announcements"
}