# main.py
# Version 5.1 - FIXED: Corrected import paths for multi-source scrapers
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
    """Main function to run job search with focus on quality sources"""
    logging.info("Starting optimized job search tool v5.1...")
    
    # Initialize database
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    db_manager = SimpleJobDatabaseManager(DATABASE_PATH)
    
    # Initialize scrapers (import only when needed to avoid dependency issues)
    gmail_scraper = None
    all_new_jobs = []
    
    # Try to import and initialize Gmail scraper (PRIMARY SOURCE)
    try:
        from scrapers.gmail_linkedin_scraper import GmailLinkedInScraper
        gmail_scraper = GmailLinkedInScraper()
        logging.info("Gmail scraper initialized successfully")
    except ImportError as e:
        logging.warning(f"Gmail scraper not available - missing dependencies: {e}")
    except Exception as e:
        logging.warning(f"Gmail scraper initialization failed: {e}")
        logging.warning("Continuing with other scrapers...")
    
    # Gmail LinkedIn emails (PRIMARY - BEST SOURCE)
    if gmail_scraper:
        try:
            logging.info("🔍 Searching LinkedIn emails from Gmail (primary source)...")
            gmail_jobs = gmail_scraper.scrape_jobs(max_emails=25, scrape_descriptions=True)
            
            # Add Gmail jobs to database WITH VALIDATION
            gmail_new_jobs = 0
            for job in gmail_jobs:
                # Only add jobs with URLs AND that pass validation
                if job.get('url'):
                    # FIXED: Validate job before adding to database
                    if gmail_scraper._is_valid_job(job):
                        if db_manager.add_job(job):
                            gmail_new_jobs += 1
                            all_new_jobs.append(job)
                    else:
                        logging.debug(f"Skipping invalid job: {job.get('title', 'Unknown')}")
                else:
                    logging.debug(f"Skipping job without URL: {job.get('title', 'Unknown')}")
            
            logging.info(f"✅ Added {gmail_new_jobs} new jobs from LinkedIn emails")
            
        except Exception as e:
            logging.error(f"Gmail scraper failed: {e}")
    
    # Try other high-quality scrapers
    scrapers_attempted = 0
    scrapers_successful = 0
    
    # SimplyHired scraper (SECONDARY SOURCE) - FIXED IMPORT PATH
    try:
        from src.scrapers.simplyhired_scraper import SimplyHiredScraper
        simplyhired_scraper = SimplyHiredScraper(delay=2)
        scrapers_attempted += 1
        logging.info("✅ SimplyHired scraper imported and initialized successfully")
        
        # Only use first 2 keywords to avoid overwhelming
        for keyword in JOB_KEYWORDS[:2]:
            logging.info(f"🔍 Searching SimplyHired for: {keyword}")
            try:
                simplyhired_jobs = simplyhired_scraper.search_jobs(
                    keywords=keyword,
                    location="Seattle, WA",
                    remote=REMOTE_JOBS,
                    max_jobs=8
                )
                
                new_jobs_count = 0
                for job in simplyhired_jobs:
                    # Only add jobs with valid URLs
                    if job.get('url') and job['url'].startswith('http'):
                        if db_manager.add_job(job):
                            new_jobs_count += 1
                            all_new_jobs.append(job)
                    else:
                        logging.debug(f"Skipping SimplyHired job without valid URL: {job.get('title', 'Unknown')}")
                
                if new_jobs_count > 0:
                    logging.info(f"✅ Added {new_jobs_count} new SimplyHired jobs for: {keyword}")
                    scrapers_successful += 1
                else:
                    logging.warning(f"⚠️ SimplyHired found 0 valid jobs for: {keyword} (found {len(simplyhired_jobs)} total)")
                
            except Exception as e:
                logging.error(f"SimplyHired search failed for {keyword}: {e}")
        
    except ImportError as e:
        logging.error(f"❌ SimplyHired scraper import failed: {e}")
        logging.error("Check if src/scrapers/simplyhired_scraper.py exists and has correct dependencies")
    except Exception as e:
        logging.error(f"❌ SimplyHired scraper failed: {e}")
    
    # Indeed scraper (TERTIARY SOURCE) - NEW: Added Indeed scraper
    try:
        from src.scrapers.indeed_scraper import IndeedScraper
        indeed_scraper = IndeedScraper(delay=3)
        scrapers_attempted += 1
        logging.info("✅ Indeed scraper imported and initialized successfully")
        
        # Only use first keyword for Indeed (it's more restrictive)
        for keyword in JOB_KEYWORDS[:1]:
            logging.info(f"🔍 Searching Indeed for: {keyword}")
            try:
                indeed_jobs = indeed_scraper.search_jobs(
                    keywords=keyword,
                    location="Seattle, WA",
                    remote=REMOTE_JOBS,
                    max_jobs=5  # Lower limit due to rate limiting
                )
                
                new_jobs_count = 0
                for job in indeed_jobs:
                    # Only add jobs with valid URLs
                    if job.get('url') and job['url'].startswith('http'):
                        if db_manager.add_job(job):
                            new_jobs_count += 1
                            all_new_jobs.append(job)
                    else:
                        logging.debug(f"Skipping Indeed job without valid URL: {job.get('title', 'Unknown')}")
                
                if new_jobs_count > 0:
                    logging.info(f"✅ Added {new_jobs_count} new Indeed jobs for: {keyword}")
                    scrapers_successful += 1
                else:
                    logging.warning(f"⚠️ Indeed found 0 valid jobs for: {keyword} (found {len(indeed_jobs)} total)")
                
            except Exception as e:
                logging.error(f"Indeed search failed for {keyword}: {e}")
        
    except ImportError as e:
        logging.warning(f"⚠️ Indeed scraper import failed: {e}")
        logging.warning("Indeed scraper dependencies may be missing")
    except Exception as e:
        logging.error(f"❌ Indeed scraper failed: {e}")
    
    # API scraper (QUATERNARY SOURCE - only if we don't have many jobs) - FIXED IMPORT PATH
    if len(all_new_jobs) < 15:  # Only use if we need more jobs
        try:
            from src.scrapers.jobs_api_scraper import JobsAPIScraper
            api_scraper = JobsAPIScraper(delay=1)
            scrapers_attempted += 1
            logging.info("✅ Jobs API scraper imported and initialized successfully")
            
            for keyword in JOB_KEYWORDS[:1]:  # Just first keyword
                logging.info(f"🔍 Searching API sources for: {keyword}")
                try:
                    api_jobs = api_scraper.search_jobs(
                        keywords=keyword,
                        location="Seattle, WA",
                        max_jobs=5
                    )
                    
                    new_jobs_count = 0
                    for job in api_jobs:
                        # Only add jobs with valid URLs
                        if job.get('url') and job['url'].startswith('http'):
                            if db_manager.add_job(job):
                                new_jobs_count += 1
                                all_new_jobs.append(job)
                        else:
                            logging.debug(f"Skipping API job without valid URL: {job.get('title', 'Unknown')}")
                    
                    if new_jobs_count > 0:
                        logging.info(f"✅ Added {new_jobs_count} new API jobs for: {keyword}")
                        scrapers_successful += 1
                    else:
                        logging.warning(f"⚠️ API sources found 0 valid jobs for: {keyword} (found {len(api_jobs)} total)")
                    
                except Exception as e:
                    logging.error(f"API search failed for {keyword}: {e}")
            
        except ImportError as e:
            logging.error(f"❌ Jobs API scraper import failed: {e}")
            logging.error("Check if src/scrapers/jobs_api_scraper.py exists and has correct dependencies")
        except Exception as e:
            logging.error(f"❌ Jobs API scraper failed: {e}")
    else:
        logging.info(f"⏭️ Skipping API scraper - already found {len(all_new_jobs)} jobs")
    
    # Print summary
    total_new_jobs = len(all_new_jobs)
    stats = db_manager.get_stats()
    total_jobs = stats.get('total_jobs', 0)
    
    print(f"\n{'='*60}")
    print(f"JOB SEARCH SUMMARY v5.1")
    print(f"{'='*60}")
    print(f"✅ New jobs found: {total_new_jobs}")
    print(f"📊 Total jobs in database: {total_jobs}")
    print(f"🔧 Scrapers attempted: {scrapers_attempted}")
    print(f"✅ Scrapers successful: {scrapers_successful}")
    
    # Show stats by source
    by_source = stats.get('by_source', {})
    if by_source:
        print(f"\n📋 Jobs by source:")
        for source, count in by_source.items():
            print(f"   {source}: {count}")
    
    # Show sample of new jobs
    if all_new_jobs:
        print(f"\n🎯 Sample of new jobs found:")
        for i, job in enumerate(all_new_jobs[:5], 1):
            salary_info = ""
            if job.get('salary_min') and job.get('salary_max'):
                salary_info = f" (${job['salary_min']:,} - ${job['salary_max']:,})"
            elif job.get('salary_min'):
                salary_info = f" (${job['salary_min']:,}+)"
            
            url_indicator = "🔗" if job.get('url') else "❌"
            print(f"{i}. {job['title']} at {job['company']}{salary_info} {url_indicator}")
            print(f"   📍 {job['location']} | 🔗 {job.get('source', 'unknown')}")
            print()
    
    print(f"\n💡 Next steps:")
    print(f"   1. Review jobs: python ui/job_reviewer.py")
    print(f"   2. Web interface: python api/web_api.py → http://localhost:5000")
    print(f"   3. Clean database: python cleanup_jobs.py")
    
    if total_new_jobs == 0:
        print(f"\n💭 No new jobs found. This could mean:")
        print(f"   • All recent jobs are already in your database")
        print(f"   • Scrapers encountered issues (check logs above)")
        print(f"   • No new jobs matching your criteria were posted")
        
        if scrapers_attempted == 0:
            print(f"   • ⚠️ NO SCRAPERS WERE ATTEMPTED - check import errors above")
        elif scrapers_successful == 0:
            print(f"   • ⚠️ ALL SCRAPERS FAILED - check error messages above")
    
    # Enhanced diagnostics
    print(f"\n🔧 Scraper Diagnostics:")
    print(f"   • Gmail LinkedIn: {'✅ Working' if gmail_scraper else '❌ Failed'}")
    print(f"   • SimplyHired: {'✅ Attempted' if scrapers_attempted > 0 else '❌ Import failed'}")
    print(f"   • Indeed: {'⚠️ Attempted' if scrapers_attempted > 1 else '❌ Import failed'}")
    print(f"   • API Sources: {'⚠️ Attempted' if scrapers_attempted > 2 else '❌ Import failed or skipped'}")
    
    logging.info("Optimized job search completed successfully")

def test_scrapers():
    """Test all scrapers individually to diagnose issues"""
    print("🧪 Testing all job scrapers...")
    
    # Test imports
    scrapers_to_test = [
        ("Gmail LinkedIn", "scrapers.gmail_linkedin_scraper", "GmailLinkedInScraper"),
        ("SimplyHired", "src.scrapers.simplyhired_scraper", "SimplyHiredScraper"),
        ("Indeed", "src.scrapers.indeed_scraper", "IndeedScraper"),
        ("Jobs API", "src.scrapers.jobs_api_scraper", "JobsAPIScraper"),
    ]
    
    for name, module_path, class_name in scrapers_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            scraper_class = getattr(module, class_name)
            scraper = scraper_class()
            print(f"✅ {name}: Import and initialization successful")
        except ImportError as e:
            print(f"❌ {name}: Import failed - {e}")
        except Exception as e:
            print(f"⚠️ {name}: Import OK but initialization failed - {e}")

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
    print("🧪 Testing simplified database manager...")
    db_manager = SimpleJobDatabaseManager(DATABASE_PATH)
    
    # Add a test job with URL
    test_job = {
        'job_id': 'test_quality_123',
        'title': 'Senior Product Manager',
        'company': 'Test Company',
        'location': 'Seattle, WA',
        'salary_min': 140000,
        'salary_max': 160000,
        'description': 'Test job description',
        'source': 'test',
        'url': 'https://example.com/job/123'  # Valid URL
    }
    
    if db_manager.add_job(test_job):
        print("✅ Successfully added test job with URL")
    else:
        print("ℹ️  Test job already exists (normal)")
    
    # Retrieve jobs
    jobs = db_manager.get_jobs(limit=5)
    print(f"✅ Retrieved {len(jobs)} jobs from database")
    
    if jobs:
        print("\nSample job data:")
        for job in jobs[:3]:
            url_status = "🔗" if job.get('url') else "❌"
            print(f"- {job['title']} at {job['company']} (Source: {job['source']}) {url_status}")
    
    # Show stats
    stats = db_manager.get_stats()
    print(f"\n📊 Database Statistics:")
    print(f"   Total jobs: {stats.get('total_jobs', 0)}")
    print(f"   Recent jobs: {stats.get('recent_jobs', 0)}")
    print(f"   AI analyzed: {stats.get('ai_analyzed', 0)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test":
            test_database()
        elif command == "gmail":
            test_gmail_only()
        elif command == "scrapers":
            test_scrapers()
        elif command == "setup":
            setup_gmail_api()
        elif command == "clean":
            print("To clean the database, run: python cleanup_jobs.py")
        else:
            print("Available commands:")
            print("  python main.py          - Run optimized job search")
            print("  python main.py test     - Test database")
            print("  python main.py gmail    - Test Gmail scraper only")
            print("  python main.py scrapers - Test all scrapers")
            print("  python main.py setup    - Gmail API setup guide")
            print("  python cleanup_jobs.py  - Clean database (remove test jobs, no URLs)")
    else:
        main()