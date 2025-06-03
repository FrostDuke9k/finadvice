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

# The OFFICIAL_SOURCES_CONFIG dictionary has been removed as it's no longer used.
# database.py now reads sources directly from the UK_Government_Finance_and_Tax_Websites.csv file.