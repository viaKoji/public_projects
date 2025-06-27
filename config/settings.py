# config/settings.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Job Search Parameters
JOB_KEYWORDS = [
    "Principal Product Manager",
    "product engineer", 
    "senior product engineer",
    "Product Manager, Hardware",
    "Senior Product Manager",
    "Director, Product Design",
    "Senior Product Manager"
]

# Location Settings
SEATTLE_ZIP = "98146"  # Downtown Seattle
SEARCH_RADIUS_MILES = 25  # 25 mile radius from Seattle
REMOTE_JOBS = True  # Include fully remote positions

# Experience Level
EXPERIENCE_LEVELS = ["senior", "lead", "director", "principal"]

# Salary Filter
MIN_SALARY = 120000  # Minimum salary in USD (adjust as needed)

# Database Settings
DATABASE_PATH = "data/jobs.db"

# API Keys (store these in a .env file, not here!)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Optional - can add later

# Email Settings (for notifications)
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USER = os.getenv("EMAIL_USER")  # Your Gmail address
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")  # Gmail app password
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")  # Where to send job alerts

# Scraping Settings
SCRAPING_DELAY = 2  # Seconds between requests (be respectful!)
MAX_JOBS_PER_SEARCH = 50
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"