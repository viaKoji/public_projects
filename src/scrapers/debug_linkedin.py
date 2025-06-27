# debug_linkedin.py - Version 1.0
# Test LinkedIn scraping to see what we're actually getting

import requests
from bs4 import BeautifulSoup
import os

def debug_linkedin_search():
    """Debug what LinkedIn returns for job searches"""
    
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    # Test 1: Basic LinkedIn jobs page
    print("🔍 Testing basic LinkedIn jobs page...")
    try:
        response = session.get("https://www.linkedin.com/jobs", timeout=15)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            with open('logs/linkedin_basic.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("✅ Saved basic LinkedIn response to logs/linkedin_basic.html")
        else:
            print(f"❌ Failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: LinkedIn job search with query
    print("\n🔍 Testing LinkedIn job search with query...")
    try:
        search_url = "https://www.linkedin.com/jobs/search"
        params = {
            'keywords': 'Product Manager',
            'location': 'Seattle, WA'
        }
        
        response = session.get(search_url, params=params, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Final URL: {response.url}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save full response
            with open('logs/linkedin_search.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("✅ Saved search response to logs/linkedin_search.html")
            
            # Check page title
            title = soup.find('title')
            if title:
                print(f"Page title: {title.get_text()}")
            
            # Count different types of elements
            print(f"Total divs: {len(soup.find_all('div'))}")
            print(f"Total links: {len(soup.find_all('a'))}")
            
            # Look for job-related elements
            job_related = soup.find_all(['div', 'li', 'article'], class_=lambda x: x and 'job' in str(x).lower())
            print(f"Elements with 'job' in class: {len(job_related)}")
            
            # Look for any links with 'job' in href
            job_links = soup.find_all('a', href=lambda x: x and 'job' in str(x).lower())
            print(f"Links with 'job' in href: {len(job_links)}")
            
            if job_links:
                print("Sample job links:")
                for i, link in enumerate(job_links[:3]):
                    print(f"  {i+1}. {link.get('href')} - {link.get_text()[:50]}...")
        else:
            print(f"❌ Failed with status {response.status_code}")
            with open('logs/linkedin_error.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Try alternative LinkedIn URLs
    print("\n🔍 Testing alternative LinkedIn URLs...")
    
    alternative_urls = [
        "https://www.linkedin.com/jobs/search?keywords=Product%20Manager&location=Seattle%2C%20WA",
        "https://www.linkedin.com/jobs/collections/recommended",
        "https://careers.linkedin.com/", # LinkedIn's own careers page
    ]
    
    for i, url in enumerate(alternative_urls):
        try:
            response = session.get(url, timeout=15)
            print(f"URL {i+1}: Status {response.status_code} - {url}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_links = soup.find_all('a', href=lambda x: x and 'job' in str(x).lower())
                print(f"  Found {len(job_links)} job-related links")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n📊 Debug Summary:")
    print("Check the files in the 'logs/' directory to see what LinkedIn is actually returning.")
    print("This will help us understand if we need:")
    print("1. Different selectors")
    print("2. Authentication")
    print("3. A different approach entirely")

if __name__ == "__main__":
    debug_linkedin_search()