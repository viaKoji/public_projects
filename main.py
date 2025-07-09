# main.py
# Version 6.0 - Simplified Gmail LinkedIn only version
import logging
import os
from datetime import datetime
import sys
import time

# Add src to path so we can import our modules
sys.path.append('src')

from database.simple_db_manager import SimpleJobDatabaseManager
from config.settings import *

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('logs/job_search.log'),
        logging.StreamHandler()
    ]
)

def main():
    """Main function to run Gmail LinkedIn job search"""
    logging.info("Starting Gmail LinkedIn job search tool v6.0...")
    
    # Initialize database
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    db_manager = SimpleJobDatabaseManager(DATABASE_PATH)
    
    # Initialize Gmail LinkedIn scraper
    try:
        from scrapers.gmail_linkedin_scraper import GmailLinkedInScraper
        gmail_scraper = GmailLinkedInScraper()
        logging.info("✅ Gmail scraper initialized successfully")
    except ImportError as e:
        logging.error(f"❌ Gmail scraper import failed - missing dependencies: {e}")
        print("Please install required packages:")
        print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return
    except Exception as e:
        logging.error(f"❌ Gmail scraper initialization failed: {e}")
        print("Check your Gmail API setup (credentials.json and token.pickle)")
        return
    
    # Scrape LinkedIn jobs from Gmail
    try:
        logging.info("🔍 Searching LinkedIn emails from Gmail...")
        gmail_jobs = gmail_scraper.scrape_jobs(max_emails=25, scrape_descriptions=True)
        
        # Add Gmail jobs to database WITH VALIDATION
        new_jobs_count = 0
        for job in gmail_jobs:
            # Only add jobs with URLs AND that pass validation
            if job.get('url'):
                # Validate job before adding to database
                if gmail_scraper._is_valid_job(job):
                    if db_manager.add_job(job):
                        new_jobs_count += 1
                else:
                    logging.debug(f"Skipping invalid job: {job.get('title', 'Unknown')}")
            else:
                logging.debug(f"Skipping job without URL: {job.get('title', 'Unknown')}")
        
        logging.info(f"✅ Added {new_jobs_count} new jobs from LinkedIn emails")
        
    except Exception as e:
        logging.error(f"❌ Gmail scraper failed: {e}")
        print(f"Error during job search: {e}")
        return
    
    # Print summary
    stats = db_manager.get_stats()
    total_jobs = stats.get('total_jobs', 0)
    
    print(f"\n{'='*60}")
    print(f"JOB SEARCH SUMMARY v6.0 - Gmail LinkedIn Only")
    print(f"{'='*60}")
    print(f"✅ New jobs found: {new_jobs_count}")
    print(f"📊 Total jobs in database: {total_jobs}")
    
    # Show stats by status
    by_status = stats.get('by_status', {})
    if by_status:
        print(f"\n📋 Jobs by status:")
        for status, count in by_status.items():
            print(f"   {status}: {count}")
    
    # Show sample of new jobs
    if new_jobs_count > 0:
        print(f"\n🎯 Sample of new jobs found:")
        # Get the most recent jobs
        recent_jobs = db_manager.get_jobs(limit=5)
        for i, job in enumerate(recent_jobs[:5], 1):
            salary_info = ""
            if job.get('salary_min') and job.get('salary_max'):
                salary_info = f" (${job['salary_min']:,} - ${job['salary_max']:,})"
            elif job.get('salary_min'):
                salary_info = f" (${job['salary_min']:,}+)"
            
            print(f"{i}. {job['title']} at {job['company']}{salary_info}")
            print(f"   📍 {job['location']} | Status: {job.get('status', 'new')}")
            print()
    
    print(f"\n💡 Next steps:")
    print(f"   1. Web interface: python api/web_api.py → http://localhost:5000")
    print(f"   2. Check for new emails periodically")
    
    if new_jobs_count == 0:
        print(f"\n💭 No new jobs found. This could mean:")
        print(f"   • All recent jobs are already in your database")
        print(f"   • No new LinkedIn job emails received")
        print(f"   • Gmail token needs refresh (check error messages above)")

def test_gmail_only():
    """Test only the Gmail scraper functionality"""
    print("🧪 Testing Gmail LinkedIn scraper...")
    
    try:
        from scrapers.gmail_linkedin_scraper import GmailLinkedInScraper
        gmail_scraper = GmailLinkedInScraper()
        jobs = gmail_scraper.scrape_jobs(max_emails=10, scrape_descriptions=True)
        
        print(f"✅ Found {len(jobs)} jobs from LinkedIn emails")
        
        jobs_with_urls = [job for job in jobs if job.get('url')]
        jobs_without_urls = [job for job in jobs if not job.get('url')]
        
        print(f"🔗 Jobs with URLs: {len(jobs_with_urls)}")
        print(f"❌ Jobs without URLs: {len(jobs_without_urls)}")
        
        if jobs_with_urls:
            print(f"\n📋 Sample jobs with URLs:")
            for i, job in enumerate(jobs_with_urls[:3], 1):
                print(f"{i}. {job['title']} at {job['company']}")
                print(f"   📍 {job['location']}")
                print(f"   🔗 {job.get('url', 'No URL')}")
                print()
        
        if jobs_without_urls:
            print(f"\n⚠️  Jobs without URLs (will be skipped):")
            for job in jobs_without_urls[:3]:
                print(f"• {job['title']} at {job['company']}")
            
    except FileNotFoundError:
        print("❌ Gmail credentials not found!")
        print("Please follow the Gmail API setup instructions:")
        print("1. Download credentials.json from Google Cloud Console")
        print("2. Place it in your project root directory")
        print("3. Run this test again")
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Install required packages:")
        print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        
    except Exception as e:
        print(f"❌ Error testing Gmail scraper: {e}")
        print("Check the Gmail API setup instructions for troubleshooting")

def setup_gmail_api():
    """Guide user through Gmail API setup"""
    print("="*60)
    print("GMAIL API SETUP GUIDE")
    print("="*60)
    print("Follow these steps to set up Gmail API access:")
    print()
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create or select a project")
    print("3. Enable the Gmail API")
    print("4. Create OAuth 2.0 credentials")
    print("5. Download credentials.json to this directory")
    print()
    print("For detailed instructions, see the Gmail API Setup documentation.")
    print()
    
    if os.path.exists('credentials.json'):
        print("✅ credentials.json found!")
        print("Testing Gmail connection...")
        test_gmail_only()
    else:
        print("❌ credentials.json not found")
        print("Please complete the setup steps above")

def test_database():
    """Test database functionality"""
    print("🧪 Testing database manager...")
    db_manager = SimpleJobDatabaseManager(DATABASE_PATH)
    
    # Show stats
    stats = db_manager.get_stats()
    print(f"\n📊 Database Statistics:")
    print(f"   Total jobs: {stats.get('total_jobs', 0)}")
    print(f"   Recent jobs: {stats.get('recent_jobs', 0)}")
    print(f"   AI analyzed: {stats.get('ai_analyzed', 0)}")
    print(f"   By status: {stats.get('by_status', {})}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test":
            test_database()
        elif command == "gmail":
            test_gmail_only()
        elif command == "setup":
            setup_gmail_api()
        else:
            print("Available commands:")
            print("  python main.py          - Run Gmail LinkedIn job search")
            print("  python main.py test     - Test database")
            print("  python main.py gmail    - Test Gmail scraper only")
            print("  python main.py setup    - Gmail API setup guide")
    else:
        main()