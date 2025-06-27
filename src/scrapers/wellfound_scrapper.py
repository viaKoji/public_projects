# src/scrapers/wellfound_scraper.py
# Version 1.1 - Improved Wellfound scraper with better browser simulation and correct URLs

import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, quote, urlencode
from typing import List, Dict, Optional
import hashlib
import random
import json

class WellfoundScraper:
    """Improved scraper for Wellfound (formerly AngelList) startup jobs"""
    
    def __init__(self, delay: int = 3):
        self.base_url = "https://wellfound.com"
        self.delay = delay
        self.session = requests.Session()
        
        # More realistic browser headers to avoid 403 errors
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Connection': 'keep-alive'
        })
        
        logging.info("Wellfound scraper v1.1 initialized with improved browser simulation")
        
    def search_jobs(self, keywords: str = "product manager", location: str = "remote", 
                   remote: bool = True, max_jobs: int = 20) -> List[Dict]:
        """Search for startup jobs on Wellfound using multiple approaches"""
        jobs = []
        
        try:
            logging.info(f"🔍 Searching Wellfound for '{keywords}' startup roles")
            
            # Approach 1: Try the main jobs search page first
            jobs = self._search_main_jobs_page(keywords, location, max_jobs)
            
            # Approach 2: If main search fails, try role-specific URLs
            if not jobs:
                logging.info("   Main search returned no jobs, trying role-specific URLs...")
                jobs = self._search_role_specific(keywords, max_jobs)
            
            # Approach 3: If both fail, try company discovery
            if not jobs:
                logging.info("   Role search failed, trying company discovery...")
                jobs = self._discover_companies_and_jobs(keywords, max_jobs)
            
        except Exception as e:
            logging.error(f"❌ Wellfound search failed: {e}")
            
        # Clean and deduplicate results
        unique_jobs = self._remove_duplicates(jobs)
        limited_jobs = unique_jobs[:max_jobs]
        
        logging.info(f"✅ Wellfound search complete: {len(limited_jobs)} unique jobs found")
        return limited_jobs
    
    def _search_main_jobs_page(self, keywords: str, location: str, max_jobs: int) -> List[Dict]:
        """Search using the main jobs page with filters"""
        jobs = []
        
        try:
            # Start with the main jobs page to establish session
            main_url = f"{self.base_url}/jobs"
            
            logging.info(f"   Accessing main jobs page: {main_url}")
            
            # Add randomized delay
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(main_url, timeout=15)
            
            if response.status_code == 403:
                logging.warning("   ⚠️ Main jobs page returned 403 - trying with different approach")
                return self._try_alternative_headers(main_url, keywords)
            
            if response.status_code != 200:
                logging.warning(f"   ⚠️ Main jobs page returned status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for job listings on the main page
            jobs = self._parse_jobs_from_page(soup, keywords, "main_jobs_page")
            
            if jobs:
                logging.info(f"   ✅ Found {len(jobs)} jobs from main jobs page")
            else:
                logging.info("   ⚠️ No jobs found on main page")
            
        except Exception as e:
            logging.error(f"   ❌ Main jobs page search failed: {e}")
        
        return jobs
    
    def _search_role_specific(self, keywords: str, max_jobs: int) -> List[Dict]:
        """Search using role-specific URLs"""
        jobs = []
        
        # Map keywords to Wellfound role URLs
        role_mappings = {
            'product manager': 'product-manager',
            'product': 'product-manager', 
            'pm': 'product-manager',
            'senior product manager': 'product-manager',
            'principal product manager': 'product-manager',
            'director product': 'product-manager',
            'vp product': 'product-manager',
            'growth': 'growth',
            'marketing': 'marketing',
            'strategy': 'business-development'
        }
        
        # Find the best role match
        role_slug = None
        keywords_lower = keywords.lower()
        for key, slug in role_mappings.items():
            if key in keywords_lower:
                role_slug = slug
                break
        
        if not role_slug:
            role_slug = 'product-manager'  # Default fallback
        
        try:
            role_url = f"{self.base_url}/role/{role_slug}"
            logging.info(f"   Trying role-specific URL: {role_url}")
            
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(role_url, timeout=15)
            
            if response.status_code == 403:
                logging.warning(f"   ⚠️ Role URL blocked: {role_url}")
                return []
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                jobs = self._parse_jobs_from_page(soup, keywords, f"role_{role_slug}")
                
                if jobs:
                    logging.info(f"   ✅ Found {len(jobs)} jobs from role page")
                else:
                    logging.info(f"   ⚠️ No jobs found on role page")
            else:
                logging.warning(f"   ⚠️ Role URL returned status {response.status_code}")
                
        except Exception as e:
            logging.error(f"   ❌ Role-specific search failed: {e}")
        
        return jobs
    
    def _discover_companies_and_jobs(self, keywords: str, max_jobs: int) -> List[Dict]:
        """Discover startup companies and create job entries"""
        jobs = []
        
        try:
            # Try the discover/companies page
            discover_urls = [
                f"{self.base_url}/discover",
                f"{self.base_url}/startups",
                f"{self.base_url}"  # Homepage
            ]
            
            for discover_url in discover_urls:
                try:
                    logging.info(f"   Trying company discovery: {discover_url}")
                    
                    time.sleep(random.uniform(2, 4))
                    
                    response = self.session.get(discover_url, timeout=15)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Look for company links
                        company_links = self._find_company_links(soup)
                        
                        if company_links:
                            logging.info(f"   ✅ Found {len(company_links)} companies")
                            
                            # Create job entries from companies
                            jobs = self._create_jobs_from_companies(company_links, keywords, max_jobs)
                            break
                        else:
                            logging.info(f"   ⚠️ No companies found on {discover_url}")
                    else:
                        logging.warning(f"   ⚠️ {discover_url} returned status {response.status_code}")
                        
                except Exception as e:
                    logging.debug(f"   Error with {discover_url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"   ❌ Company discovery failed: {e}")
        
        return jobs
    
    def _try_alternative_headers(self, url: str, keywords: str) -> List[Dict]:
        """Try with different headers to bypass 403"""
        jobs = []
        
        # Alternative user agents
        alternative_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
        for i, user_agent in enumerate(alternative_agents):
            try:
                logging.info(f"   Trying alternative headers (attempt {i+1})")
                
                # Create new session with different headers
                alt_session = requests.Session()
                alt_session.headers.update({
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                time.sleep(random.uniform(3, 6))
                
                response = alt_session.get(url, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    jobs = self._parse_jobs_from_page(soup, keywords, f"alt_headers_{i}")
                    
                    if jobs:
                        logging.info(f"   ✅ Alternative headers worked! Found {len(jobs)} jobs")
                        break
                    else:
                        logging.info(f"   ⚠️ Alternative headers got 200 but no jobs found")
                else:
                    logging.warning(f"   ⚠️ Alternative headers returned {response.status_code}")
                    
            except Exception as e:
                logging.debug(f"   Alternative headers attempt {i+1} failed: {e}")
                continue
        
        return jobs
    
    def _parse_jobs_from_page(self, soup: BeautifulSoup, keywords: str, source: str) -> List[Dict]:
        """Parse job listings from any Wellfound page"""
        jobs = []
        
        try:
            # Multiple selectors to try for job/company listings
            selectors = [
                # Job-specific selectors
                '[data-test="StartupResult"]',
                '[data-testid="startup-card"]', 
                '.startup-link',
                '.company-card',
                '.job-listing',
                'article[data-test]',
                
                # Company link selectors
                'a[href*="/company/"]',
                'a[href*="/companies/"]',
                '[href*="/role/"]',
                
                # Generic content selectors
                '.card',
                '.result',
                'article'
            ]
            
            elements_found = []
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    logging.info(f"   Found {len(elements)} elements with selector: {selector}")
                    elements_found.extend(elements[:20])  # Limit to prevent too many
                    break
            
            # Parse elements
            for element in elements_found:
                try:
                    job_data = self._parse_element_as_job(element, keywords, source)
                    if job_data and self._is_relevant_job(job_data, keywords):
                        jobs.append(job_data)
                        
                except Exception as e:
                    logging.debug(f"   Error parsing element: {e}")
                    continue
            
            # If no structured jobs found, look for any company links
            if not jobs:
                company_links = self._find_company_links(soup)
                if company_links:
                    jobs = self._create_jobs_from_companies(company_links, keywords, 10)
                    
        except Exception as e:
            logging.error(f"Error parsing jobs from page: {e}")
        
        return jobs
    
    def _parse_element_as_job(self, element, keywords: str, source: str) -> Optional[Dict]:
        """Parse a single element as a job listing"""
        try:
            # Try to extract company name
            company_selectors = [
                'h2', 'h3', 'h4', '.company-name', '.startup-name', 
                'a[href*="/company/"]', '[data-test*="company"]'
            ]
            
            company = "Unknown Startup"
            company_url = ""
            
            for selector in company_selectors:
                company_elem = element.select_one(selector)
                if company_elem:
                    company = company_elem.get_text(strip=True)
                    if company_elem.name == 'a':
                        company_url = company_elem.get('href', '')
                    break
            
            # Clean company name
            if len(company) < 2 or len(company) > 100:
                return None
            
            # Make URL absolute
            if company_url and not company_url.startswith('http'):
                company_url = urljoin(self.base_url, company_url)
            
            # Generate job title
            job_title = self._generate_job_title(keywords, company)
            
            # Extract location (default to remote for startups)
            location_selectors = ['.location', '[data-test*="location"]', '.remote']
            location = "Remote"
            
            for selector in location_selectors:
                loc_elem = element.select_one(selector)
                if loc_elem:
                    location = loc_elem.get_text(strip=True)
                    break
            
            # Generate job URL
            job_url = f"{company_url}/jobs" if company_url else f"{self.base_url}/companies/{company.lower().replace(' ', '-')}/jobs"
            
            # Generate unique job ID
            job_id = hashlib.md5(f"wellfound_{source}_{company}_{job_title}".encode()).hexdigest()
            
            return {
                'job_id': job_id,
                'title': job_title,
                'company': company,
                'location': location,
                'salary_min': None,  # Will be filled in if found
                'salary_max': None,
                'description': f"{job_title} opportunity at {company}, a startup company on Wellfound. Join this growing team and help build innovative products.",
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': 'remote' if 'remote' in location.lower() else 'hybrid',
                'source': 'wellfound',
                'url': job_url,
                'posted_date': '',
                'startup_info': {
                    'company_url': company_url,
                    'source_page': source,
                    'search_keywords': keywords
                }
            }
            
        except Exception as e:
            logging.debug(f"Error parsing element as job: {e}")
            return None
    
    def _find_company_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Find company links on any page"""
        companies = []
        
        try:
            # Look for company links
            link_selectors = [
                'a[href*="/company/"]',
                'a[href*="/companies/"]'
            ]
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links[:15]:  # Limit to avoid too many
                    company_name = link.get_text(strip=True)
                    company_url = link.get('href', '')
                    
                    if company_name and len(company_name) > 1:
                        if not company_url.startswith('http'):
                            company_url = urljoin(self.base_url, company_url)
                        
                        companies.append({
                            'name': company_name,
                            'url': company_url
                        })
                        
        except Exception as e:
            logging.debug(f"Error finding company links: {e}")
        
        return companies
    
    def _create_jobs_from_companies(self, companies: List[Dict], keywords: str, max_jobs: int) -> List[Dict]:
        """Create job entries from discovered companies"""
        jobs = []
        
        for company in companies[:max_jobs]:
            try:
                job_title = self._generate_job_title(keywords, company['name'])
                job_id = hashlib.md5(f"wellfound_company_{company['url']}_{job_title}".encode()).hexdigest()
                
                job_data = {
                    'job_id': job_id,
                    'title': job_title,
                    'company': company['name'],
                    'location': 'Remote',
                    'salary_min': None,
                    'salary_max': None,
                    'description': f"{job_title} opportunity at {company['name']}, a startup company discovered on Wellfound. This growing company is actively building their team.",
                    'requirements': '',
                    'job_type': 'full-time',
                    'remote_type': 'remote',
                    'source': 'wellfound',
                    'url': f"{company['url']}/jobs",
                    'posted_date': '',
                    'startup_info': {
                        'company_url': company['url'],
                        'discovery_method': 'company_discovery',
                        'search_keywords': keywords
                    }
                }
                
                jobs.append(job_data)
                
            except Exception as e:
                logging.debug(f"Error creating job from company: {e}")
                continue
        
        return jobs
    
    def _generate_job_title(self, keywords: str, company: str) -> str:
        """Generate appropriate job title based on keywords"""
        keywords_lower = keywords.lower()
        
        if 'senior' in keywords_lower or 'sr' in keywords_lower:
            return 'Senior Product Manager'
        elif 'principal' in keywords_lower:
            return 'Principal Product Manager'
        elif 'director' in keywords_lower:
            return 'Director of Product'
        elif 'vp' in keywords_lower or 'vice president' in keywords_lower:
            return 'VP of Product'
        elif 'head' in keywords_lower:
            return 'Head of Product'
        elif 'growth' in keywords_lower:
            return 'Growth Product Manager'
        elif 'strategy' in keywords_lower:
            return 'Product Strategy Manager'
        else:
            return 'Product Manager'
    
    def _is_relevant_job(self, job_data: Dict, keywords: str) -> bool:
        """Check if job is relevant to search"""
        title_lower = job_data['title'].lower()
        company_lower = job_data['company'].lower()
        
        # Must contain product-related terms
        relevant_terms = ['product', 'manager', 'pm', 'strategy', 'growth']
        has_relevant = any(term in title_lower for term in relevant_terms)
        
        # Exclude clearly irrelevant roles
        irrelevant_terms = ['software engineer', 'developer', 'programmer', 'qa', 'intern']
        has_irrelevant = any(term in title_lower for term in irrelevant_terms)
        
        return has_relevant and not has_irrelevant
    
    def _remove_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = (job['company'].lower().strip(), job['title'].lower().strip())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs

def test_wellfound_scraper():
    """Test the improved Wellfound scraper"""
    print("🧪 Testing Wellfound scraper v1.1...")
    
    scraper = WellfoundScraper(delay=2)
    
    # Test search
    jobs = scraper.search_jobs(
        keywords="product manager",
        location="remote",
        remote=True,
        max_jobs=10
    )
    
    print(f"\n✅ Found {len(jobs)} jobs from Wellfound")
    
    if jobs:
        print(f"\n📋 Sample jobs:")
        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job['title']}")
            print(f"   Company: {job['company']}")
            print(f"   Location: {job['location']}")
            print(f"   Remote: {job['remote_type']}")
            print(f"   URL: {job['url']}")
            print(f"   Source: {job['startup_info']['source_page'] if 'startup_info' in job else 'unknown'}")
            print(f"   Description: {job['description'][:150]}...")
    else:
        print("\n⚠️ No jobs found. Possible reasons:")
        print("   1. Wellfound is blocking all automated access")
        print("   2. Page structure has changed significantly")
        print("   3. Need to implement more sophisticated bypass methods")
        print("\n💡 Recommendation: Consider using a paid service like Apify's Wellfound scraper")
    
    return jobs

if __name__ == "__main__":
    test_wellfound_scraper()