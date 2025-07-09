# Fixed debug version with authentication
# debug_gmail_test.py
import sys
sys.path.append('src')

def check_gmail_connection():
    """Basic Gmail API connection test"""
    try:
        print("🔌 TESTING GMAIL API CONNECTION")
        print("=" * 40)
        
        from scrapers.gmail_linkedin_scraper import GmailLinkedInScraper
        
        scraper = GmailLinkedInScraper()
        
        # FIX: Call authenticate() before using service
        print("🔐 Authenticating with Gmail API...")
        scraper.authenticate()
        
        # Test basic API call
        print("📧 Testing basic Gmail API access...")
        
        profile = scraper.service.users().getProfile(userId='me').execute()
        print(f"✅ Connected to Gmail: {profile.get('emailAddress', 'Unknown')}")
        
        # Test search
        print("🔍 Testing email search...")
        results = scraper.service.users().messages().list(
            userId='me',
            q='from:linkedin.com',
            maxResults=5
        ).execute()
        
        messages = results.get('messages', [])
        print(f"✅ Found {len(messages)} LinkedIn emails (basic search)")
        
        # Test specific LinkedIn senders
        print("\n🔍 Testing specific LinkedIn senders...")
        for sender in ['jobalerts-noreply@linkedin.com', 'jobs-noreply@linkedin.com', 'jobs-listings@linkedin.com']:
            try:
                results = scraper.service.users().messages().list(
                    userId='me',
                    q=f'from:{sender}',
                    maxResults=3
                ).execute()
                count = len(results.get('messages', []))
                print(f"   {sender}: {count} emails")
            except Exception as e:
                print(f"   {sender}: Error - {e}")
        
        return True, scraper
        
    except Exception as e:
        print(f"❌ Gmail connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_email_content(scraper):
    """Test actual email content parsing"""
    try:
        print("\n📧 TESTING EMAIL CONTENT EXTRACTION")
        print("=" * 40)
        
        # Get one email to examine
        results = scraper.service.users().messages().list(
            userId='me',
            q='from:jobalerts-noreply@linkedin.com OR from:jobs-noreply@linkedin.com',
            maxResults=1
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            print("❌ No LinkedIn emails found")
            return False
        
        # Get the full email
        email_data = scraper.service.users().messages().get(
            userId='me',
            id=messages[0]['id'],
            format='full'
        ).execute()
        
        # Extract content
        subject, sender, body_text = scraper.extract_email_content(email_data)
        
        print(f"📬 Subject: {subject}")
        print(f"👤 Sender: {sender}")
        print(f"📝 Body length: {len(body_text)} characters")
        
        # Look for job URLs
        import re
        job_urls = re.findall(r'https://www\.linkedin\.com/comm/jobs/view/\d+', body_text)
        print(f"🔗 Found {len(job_urls)} job URLs")
        
        # Show sample content
        print(f"\n📄 First 500 characters of email body:")
        print("-" * 50)
        print(body_text[:500])
        print("-" * 50)
        
        # Test job parsing
        print(f"\n🔍 Testing job parsing...")
        jobs = scraper.parse_jobs_from_email(body_text, subject)
        print(f"✅ Parsed {len(jobs)} jobs from email")
        
        for i, job in enumerate(jobs[:3], 1):
            print(f"{i}. {job['title']} at {job['company']}")
            print(f"   Location: {job['location']}")
            print(f"   URL: {job['url']}")
            if job.get('salary'):
                print(f"   Salary: {job['salary']}")
        
        return len(jobs) > 0
        
    except Exception as e:
        print(f"❌ Email content test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_scraping(scraper):
    """Test the full scraping process"""
    try:
        print("\n🚀 TESTING FULL SCRAPING PROCESS")
        print("=" * 40)
        
        # Use the existing scrape_jobs method but limit emails
        print("🔍 Running scrape_jobs with limit of 5 emails...")
        jobs = scraper.scrape_jobs(max_emails=5)
        
        print(f"✅ Full scraping completed: {len(jobs)} jobs found")
        
        if jobs:
            print("\n📋 Sample results:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"{i}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                print(f"   Source: {job['source']}")
                if job.get('salary'):
                    print(f"   Salary: {job['salary']}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Full scraping test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 GMAIL SCRAPER DEBUGGING")
    print("=" * 50)
    
    # Test 1: Basic connection
    success, scraper = check_gmail_connection()
    if not success:
        print("❌ Basic Gmail connection failed. Check credentials.")
        exit(1)
    
    # Test 2: Email content extraction
    if not test_email_content(scraper):
        print("❌ Email content extraction failed.")
        # Don't exit - continue to test full scraping
    
    # Test 3: Full scraping process
    if test_full_scraping(scraper):
        print("\n🎉 Gmail scraper testing completed!")
    else:
        print("\n❌ Gmail scraper has issues.")