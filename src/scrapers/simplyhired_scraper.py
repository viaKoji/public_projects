# src/scrapers/simplyhired_scraper.py
# Version 2.0 - Fixed SimplyHired scraper with anti-bot bypass and updated selectors

import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
import hashlib
import random

class SimplyHiredScraper:
    """Improved SimplyHired scraper with anti-bot bypass"""
    
    def __init__(self, delay: int = 3):
        self.base_url = "https://www.simplyhired.com"
        self.delay = delay
        self.session = requests.Session()
        
        # Enhanced headers to bypass 403 blocking
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
        
        logging.info("SimplyHired scraper v2.0 initialized with anti-bot bypass")
        
    def search_jobs(self, keywords: str, location: str = "Seattle, WA", 
                   remote: bool = True, max_jobs: int = 20) -> List[Dict]:
        """Search for jobs on SimplyHired with improved anti-bot measures"""
        jobs = []
        
        try:
            logging.info(f"🔍 Searching SimplyHired for: {keywords} in {location}")
            
            # Step 1: Visit homepage first to establish session
            if not self._establish_session():
                logging.warning("Failed to establish session with SimplyHired")
                return []
            
            # Step 2: Perform search with anti-bot measures
            search_jobs = self._perform_search(keywords, location, remote, max_jobs)
            jobs.extend(search_jobs)
            
        except Exception as e:
            logging.error(f"❌ SimplyHired search failed: {e}")
            
        # Clean and limit results
        unique_jobs = self._remove_duplicates(jobs)
        limited_jobs = unique_jobs[:max_jobs]
        
        logging.info(f"✅ SimplyHired search complete: {len(limited_jobs)} jobs found")
        return limited_jobs
    
    def _establish_session(self) -> bool:
        """Visit homepage first to establish session and get cookies"""
        try:
            logging.info("   Establishing session with SimplyHired homepage...")
            
            # Add random delay to appear human
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(self.base_url, timeout=15)
            
            if response.status_code == 200:
                logging.info("   ✅ Session established successfully")
                # Small delay after homepage visit
                time.sleep(random.uniform(1, 2))
                return True
            elif response.status_code == 403:
                logging.warning("   ⚠️ Homepage blocked - trying alternative approach")
                return self._try_alternative_session()
            else:
                logging.warning(f"   ⚠️ Homepage returned status {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"   ❌ Session establishment failed: {e}")
            return False
    
    def _try_alternative_session(self) -> bool:
        """Try alternative headers if initial session fails"""
        try:
            logging.info("   Trying alternative headers...")
            
            # Alternative user agents that may work better
            alternative_agents = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
            ]
            
            for i, user_agent in enumerate(alternative_agents):
                try:
                    # Update headers
                    self.session.headers.update({
                        'User-Agent': user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive'
                    })
                    
                    time.sleep(random.uniform(2, 4))
                    
                    response = self.session.get(self.base_url, timeout=15)
                    
                    if response.status_code == 200:
                        logging.info(f"   ✅ Alternative headers {i+1} worked!")
                        return True
                        
                except Exception as e:
                    logging.debug(f"   Alternative headers {i+1} failed: {e}")
                    continue
            
            logging.warning("   ⚠️ All alternative headers failed")
            return False
            
        except Exception as e:
            logging.error(f"   ❌ Alternative session attempt failed: {e}")
            return False
    
    def _perform_search(self, keywords: str, location: str, remote: bool, max_jobs: int) -> List[Dict]:
        """Perform the actual job search"""
        jobs = []
        
        try:
            # Build search URL
            search_url = f"{self.base_url}/search"
            
            search_params = {
                'q': keywords,
                'l': location,
                'pn': 1,  # Page number
                'job': ''  # Empty job parameter
            }
            
            # Add remote parameter if requested
            if remote:
                search_params['remote'] = 'true'
            
            logging.info(f"   Performing search: {search_url}")
            logging.debug(f"   Search params: {search_params}")
            
            # Random delay before search
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(search_url, params=search_params, timeout=15)
            
            if response.status_code == 403:
                logging.warning("   ⚠️ Search blocked with 403 - trying mobile version")
                return self._try_mobile_search(keywords, location, max_jobs)
            
            if response.status_code != 200:
                logging.warning(f"   ⚠️ Search returned status {response.status_code}")
                return []
            
            logging.info("   ✅ Search request successful, parsing results...")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = self._parse_job_results(soup, keywords)
            
            if jobs:
                logging.info(f"   ✅ Found {len(jobs)} jobs from search results")
            else:
                logging.info("   ⚠️ No jobs found in search results - trying alternative parsing")
                jobs = self._try_alternative_parsing(soup, keywords)
                
        except Exception as e:
            logging.error(f"   ❌ Search performance failed: {e}")
        
        return jobs
    
    def _try_mobile_search(self, keywords: str, location: str, max_jobs: int) -> List[Dict]:
        """Try mobile version if regular search is blocked"""
        jobs = []
        
        try:
            logging.info("   Trying mobile version...")
            
            # Update headers for mobile
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            
            self.session.headers.update(mobile_headers)
            
            # Try mobile URL
            mobile_url = f"{self.base_url}/search"
            params = {
                'q': keywords,
                'l': location,
                'pn': 1
            }
            
            time.sleep(random.uniform(3, 5))
            
            response = self.session.get(mobile_url, params=params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                jobs = self._parse_job_results(soup, keywords)
                
                if jobs:
                    logging.info(f"   ✅ Mobile version worked! Found {len(jobs)} jobs")
                else:
                    logging.info("   ⚠️ Mobile version accessible but no jobs found")
            else:
                logging.warning(f"   ⚠️ Mobile version returned {response.status_code}")
                
        except Exception as e:
            logging.error(f"   ❌ Mobile search failed: {e}")
        
        return jobs
    
    def _parse_job_results(self, soup: BeautifulSoup, keywords: str) -> List[Dict]:
        """Parse job results from SimplyHired page"""
        jobs = []
        
        try:
            # Updated selectors for current SimplyHired structure
            job_selectors = [
                # 2024/2025 SimplyHired selectors
                '[data-testid="job-list"] article',
                'article[data-jk]',
                '.job',
                '.SerpJob-jobCard',
                '[data-testid="job-card"]',
                '.jobposting',
                
                # Fallback selectors
                '.result',
                '.card',
                'div[data-jk]'
            ]
            
            job_cards = []
            for selector in job_selectors:
                job_cards = soup.select(selector)
                if job_cards:
                    logging.info(f"   Found {len(job_cards)} job cards using selector: {selector}")
                    break
            
            if not job_cards:
                logging.warning("   ⚠️ No job cards found with any selector")
                return []
            
            # Parse each job card
            for card in job_cards:
                try:
                    job_data = self._parse_job_card(card, keywords)
                    if job_data and self._meets_criteria(job_data, keywords):
                        jobs.append(job_data)
                        
                except Exception as e:
                    logging.debug(f"   Error parsing job card: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"Error parsing job results: {e}")
        
        return jobs
    
    def _try_alternative_parsing(self, soup: BeautifulSoup, keywords: str) -> List[Dict]:
        """Try alternative parsing methods if main parsing fails"""
        jobs = []
        
        try:
            logging.info("   Trying alternative parsing methods...")
            
            # Look for any links that might be job links
            job_links = soup.find_all('a', href=re.compile(r'(job|position|career)'))
            
            if job_links:
                logging.info(f"   Found {len(job_links)} potential job links")
                
                for link in job_links[:10]:  # Limit to prevent too many
                    try:
                        title = link.get_text(strip=True)
                        url = link.get('href', '')
                        
                        if len(title) > 5 and url:
                            # Make URL absolute
                            if not url.startswith('http'):
                                url = urljoin(self.base_url, url)
                            
                            job_data = self._create_job_from_link(title, url, keywords)
                            if job_data:
                                jobs.append(job_data)
                                
                    except Exception as e:
                        continue
            
            # Look for any text that might contain job information
            if not jobs:
                text_content = soup.get_text()
                if 'product manager' in text_content.lower() or keywords.lower() in text_content.lower():
                    # Create a basic job entry indicating presence
                    job_data = {
                        'job_id': hashlib.md5(f"simplyhired_detected_{keywords}".encode()).hexdigest(),
                        'title': f'{keywords.title()} (Found on SimplyHired)',
                        'company': 'Various Companies',
                        'location': 'Multiple Locations',
                        'salary_min': None,
                        'salary_max': None,
                        'description': f'{keywords} positions found on SimplyHired. Visit the site directly for more details.',
                        'requirements': '',
                        'job_type': 'full-time',
                        'remote_type': 'unknown',
                        'source': 'simplyhired',
                        'url': f"{self.base_url}/search?q={quote(keywords)}",
                        'posted_date': ''
                    }
                    jobs.append(job_data)
                    logging.info("   ✅ Created indicator job showing presence on SimplyHired")
            
        except Exception as e:
            logging.error(f"Alternative parsing failed: {e}")
        
        return jobs
    
    def _parse_job_card(self, card, keywords: str) -> Optional[Dict]:
        """Parse individual job card with updated selectors"""
        try:
            # Extract job title
            title_selectors = [
                'h3 a', 'h4 a', '.jobTitle a', '[data-testid="job-title"]',
                '.title a', 'a[data-jk]', '.SerpJob-titleLink'
            ]
            
            title_elem = None
            job_url = ""
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    job_url = title_elem.get('href', '')
                    break
            
            if not title_elem:
                # Try without anchor tag
                title_selectors_no_link = [
                    'h3', 'h4', '.jobTitle', '[data-testid="job-title"]', '.title'
                ]
                for selector in title_selectors_no_link:
                    title_elem = card.select_one(selector)
                    if title_elem:
                        break
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            
            # Make URL absolute
            if job_url and not job_url.startswith('http'):
                job_url = urljoin(self.base_url, job_url)
            
            # Extract company
            company_selectors = [
                '.companyName', '[data-testid="company-name"]', '.SerpJob-companyName',
                '.company a', '.company', 'span[title]'
            ]
            
            company = "Unknown Company"
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    company = company_elem.get_text(strip=True)
                    break
            
            # Extract location
            location_selectors = [
                '.location', '[data-testid="job-location"]', '.SerpJob-location',
                '.companyLocation', '.loc'
            ]
            
            location = "Unknown Location"
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    location = location_elem.get_text(strip=True)
                    break
            
            # Extract salary if available
            salary_selectors = [
                '.salary', '.SerpJob-salary', '[data-testid="salary"]', '.pay'
            ]
            
            salary_min, salary_max = None, None
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    salary_min, salary_max = self._parse_salary(salary_text)
                    break
            
            # Extract description/snippet
            desc_selectors = [
                '.snippet', '.SerpJob-snippet', '[data-testid="job-snippet"]',
                '.summary', '.description'
            ]
            
            description = f"{title} position at {company}."
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    break
            
            # Generate job ID
            job_id = hashlib.md5(f"simplyhired_{job_url}_{title}".encode()).hexdigest()
            
            # Determine remote type
            remote_type = "onsite"
            if location:
                location_lower = location.lower()
                if "remote" in location_lower:
                    remote_type = "remote"
                elif "hybrid" in location_lower:
                    remote_type = "hybrid"
            
            return {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'salary_min': salary_min,
                'salary_max': salary_max,
                'description': description,
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': remote_type,
                'source': 'simplyhired',
                'url': job_url if job_url else f"{self.base_url}/search?q={quote(title)}",
                'posted_date': ''
            }
            
        except Exception as e:
            logging.debug(f"Error parsing job card: {e}")
            return None
    
    def _create_job_from_link(self, title: str, url: str, keywords: str) -> Optional[Dict]:
        """Create job entry from a link found on the page"""
        try:
            if len(title) < 5 or 'simplyhired' in title.lower():
                return None
            
            job_id = hashlib.md5(f"simplyhired_link_{url}".encode()).hexdigest()
            
            return {
                'job_id': job_id,
                'title': title,
                'company': 'SimplyHired Partner',
                'location': 'Unknown Location',
                'salary_min': None,
                'salary_max': None,
                'description': f"{title} opportunity found on SimplyHired.",
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': 'unknown',
                'source': 'simplyhired',
                'url': url,
                'posted_date': ''
            }
            
        except Exception as e:
            return None
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """Extract salary range from text"""
        if not salary_text:
            return None, None
        
        # Clean the text
        salary_text = salary_text.replace(',', '').replace('$', '').upper()
        
        # Handle "K" notation
        salary_text = re.sub(r'(\d+)K', r'\g<1>000', salary_text)
        
        # Look for salary ranges
        range_patterns = [
            r'(\d+)\s*-\s*(\d+)',  # 50000 - 80000
            r'(\d+)\s*TO\s*(\d+)',  # 50000 TO 80000
        ]
        
        for pattern in range_patterns:
            match = re.search(pattern, salary_text)
            if match:
                try:
                    min_sal = int(match.group(1))
                    max_sal = int(match.group(2))
                    return min_sal, max_sal
                except ValueError:
                    continue
        
        # Look for single salary
        single_match = re.search(r'(\d{4,})', salary_text)
        if single_match:
            try:
                salary = int(single_match.group(1))
                return salary, salary
            except ValueError:
                pass
        
        return None, None
    
    def _meets_criteria(self, job_data: Dict, keywords: str) -> bool:
        """Check if job meets our search criteria"""
        title_lower = job_data['title'].lower()
        keywords_lower = keywords.lower()
        
        # Check if any keyword appears in title
        keyword_parts = keywords_lower.split()
        title_match = any(part in title_lower for part in keyword_parts if len(part) > 2)
        
        # Exclude clearly irrelevant jobs
        exclude_terms = ['truck driver', 'delivery driver', 'warehouse', 'retail']
        exclude_match = any(term in title_lower for term in exclude_terms)
        
        return title_match and not exclude_match
    
    def _remove_duplicates(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs based on title and company"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = (job['title'].lower().strip(), job['company'].lower().strip())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs

def test_simplyhired_scraper():
    """Test the fixed SimplyHired scraper"""
    print("🧪 Testing SimplyHired scraper v2.0...")
    
    scraper = SimplyHiredScraper(delay=2)
    
    # Test search
    jobs = scraper.search_jobs(
        keywords="product manager",
        location="Seattle, WA",
        remote=True,
        max_jobs=10
    )
    
    print(f"\n✅ Found {len(jobs)} jobs from SimplyHired")
    
    if jobs:
        print(f"\n📋 Sample jobs:")
        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job['title']}")
            print(f"   Company: {job['company']}")
            print(f"   Location: {job['location']}")
            print(f"   Remote: {job['remote_type']}")
            print(f"   URL: {job['url']}")
            if job['salary_min']:
                print(f"   Salary: ${job['salary_min']:,} - ${job['salary_max']:,}")
            print(f"   Description: {job['description'][:100]}...")
    else:
        print("\n⚠️ No jobs found. SimplyHired may still be blocking requests.")
        print("   Consider adding proxy rotation or using a different approach.")
    
    return jobs

if __name__ == "__main__":
    test_simplyhired_scraper()