# src/scrapers/indeed_scraper.py
import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
import hashlib

class IndeedScraper:
    def __init__(self, delay: int = 3):
        self.base_url = "https://www.indeed.com"
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
    def search_jobs(self, keywords: str, location: str = "Seattle, WA", 
                   remote: bool = True, max_jobs: int = 50) -> List[Dict]:
        """Search for jobs on Indeed"""
        jobs = []
        
        try:
            # Build search URL - try the viewjobs endpoint which is sometimes less restricted
            search_params = {
                'q': keywords,
                'l': location,
                'radius': '25',
                'sort': 'date',
                'limit': '50'
            }
            
            if remote:
                search_params['rbl'] = 'Remote'  # Alternative parameter for remote
            
            # Try the mobile version first (often less restricted)
            mobile_url = "https://indeed.com/jobs"  # Fixed: removed 'm.' subdomain
            
            logging.info(f"Searching Indeed for: {keywords} in {location}")
            
            # Add some randomization to appear more human
            import random
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(mobile_url, params=search_params, timeout=10)
            
            # If first attempt fails, try with different user agent
            if response.status_code == 403:
                logging.info("First attempt blocked, trying with different headers...")
                self.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0'
                })
                time.sleep(random.uniform(2, 4))
                response = self.session.get(mobile_url, params=search_params, timeout=10)
            
            # If still blocked, try without some parameters
            if response.status_code == 403:
                logging.info("Still blocked, trying simplified search...")
                simple_params = {'q': keywords, 'l': location}
                time.sleep(random.uniform(3, 5))
                response = self.session.get(mobile_url, params=simple_params, timeout=10)
            
            if response.status_code == 403:
                logging.warning(f"All attempts blocked for {keywords}. Trying RSS feed approach...")
                return self._try_rss_feed(keywords, location)
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try different selectors for job cards
            job_cards = (soup.find_all('div', class_='job_seen_beacon') or 
                        soup.find_all('div', class_='jobsearch-SerpJobCard') or
                        soup.find_all('div', class_='slider_container') or
                        soup.find_all('a', href=lambda x: x and '/viewjob' in x if x else False))
            
            if not job_cards:
                logging.info("No job cards found with standard selectors")
                return jobs
            
            for card in job_cards[:max_jobs]:
                job_data = self._parse_job_card(card)
                if job_data and self._meets_salary_criteria(job_data):
                    jobs.append(job_data)
                
                time.sleep(random.uniform(0.5, 1.5))  # Random delay between parsing
                    
        except Exception as e:
            logging.error(f"Error searching Indeed: {e}")
            
        logging.info(f"Found {len(jobs)} jobs matching criteria")
        return jobs
    
    def _try_rss_feed(self, keywords: str, location: str) -> List[Dict]:
        """Try Indeed's RSS feed as backup"""
        try:
            rss_url = f"https://rss.indeed.com/rss?q={quote(keywords)}&l={quote(location)}&sort=date"
            
            response = self.session.get(rss_url, timeout=10)
            if response.status_code == 200:
                # Parse RSS feed
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')
                
                jobs = []
                for item in items[:10]:  # Limit to 10 from RSS
                    try:
                        title = item.title.text if item.title else "Unknown Title"
                        link = item.link.text if item.link else ""
                        description = item.description.text if item.description else ""
                        
                        # Extract company and location from description
                        company = "Unknown Company"
                        job_location = location
                        
                        job_id = hashlib.md5(link.encode()).hexdigest()
                        
                        job_data = {
                            'job_id': job_id,
                            'title': title,
                            'company': company,
                            'location': job_location,
                            'salary_min': None,
                            'salary_max': None,
                            'description': description,
                            'requirements': '',
                            'job_type': 'full-time',
                            'remote_type': 'unknown',
                            'source': 'indeed_rss',
                            'url': link,
                            'posted_date': ''
                        }
                        jobs.append(job_data)
                        
                    except Exception as e:
                        logging.error(f"Error parsing RSS item: {e}")
                        continue
                
                logging.info(f"Found {len(jobs)} jobs from RSS feed")
                return jobs
                
        except Exception as e:
            logging.error(f"RSS feed also failed: {e}")
            
        return []

    def _parse_job_card(self, card) -> Optional[Dict]:
        """Parse individual job card - improved to handle different formats"""
        try:
            # Handle if card is an 'a' tag (link)
            if card.name == 'a':
                title = card.get_text(strip=True)
                job_url = urljoin(self.base_url, card['href'])
                company = "Unknown Company"
                location = "Unknown Location"
                description = ""
            else:
                # Get job title and link
                title_elem = (card.find('h2', class_='jobTitle') or 
                             card.find('a', class_='jobTitle-color-purple') or
                             card.find('span', attrs={'title': True}))
                
                if not title_elem:
                    return None
                    
                if title_elem.name == 'a':
                    title_link = title_elem
                else:
                    title_link = title_elem.find('a')
                    
                if not title_link:
                    return None
                    
                title = title_link.get_text(strip=True)
                job_url = urljoin(self.base_url, title_link['href'])
                
                # Company name
                company_elem = (card.find('span', class_='companyName') or
                               card.find('a', class_='companyName') or
                               card.find('div', class_='companyName'))
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                
                # Location
                location_elem = (card.find('div', class_='companyLocation') or
                                card.find('span', class_='companyLocation'))
                location = location_elem.get_text(strip=True) if location_elem else "Unknown Location"
                
                # Job snippet/description
                snippet_elem = (card.find('div', class_='job-snippet') or
                               card.find('span', class_='job-snippet'))
                description = snippet_elem.get_text(strip=True) if snippet_elem else ""
            
            # Generate unique job ID
            job_id = hashlib.md5(job_url.encode()).hexdigest()
            
            # Salary (if available)
            salary_elem = card.find('span', class_='estimated-salary')
            salary_min, salary_max = self._parse_salary(salary_elem.get_text() if salary_elem else "")
            
            # Check if remote
            remote_type = "unknown"
            if location:
                location_text = location.lower()
                if "remote" in location_text:
                    remote_type = "remote"
                elif "hybrid" in location_text:
                    remote_type = "hybrid"
                else:
                    remote_type = "onsite"
            
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
                'source': 'indeed',
                'url': job_url,
                'posted_date': self._extract_posted_date(card)
            }
            
        except Exception as e:
            logging.error(f"Error parsing job card: {e}")
            return None
    
    def _parse_salary(self, salary_text: str) -> tuple:
        """Extract salary range from text"""
        if not salary_text:
            return None, None
            
        # Remove common formatting
        salary_text = salary_text.replace(',', '').replace('$', '')
        
        # Look for salary ranges like "120000 - 150000"
        range_match = re.search(r'(\d+)\s*-\s*(\d+)', salary_text)
        if range_match:
            return int(range_match.group(1)), int(range_match.group(2))
        
        # Look for single salary like "130000"
        single_match = re.search(r'(\d+)', salary_text)
        if single_match:
            salary = int(single_match.group(1))
            return salary, salary
            
        return None, None
    
    def _extract_posted_date(self, card) -> str:
        """Extract when the job was posted"""
        date_elem = card.find('span', class_='date')
        if date_elem:
            return date_elem.get_text(strip=True)
        return ""
    
    def _meets_salary_criteria(self, job_data: Dict, min_salary: int = 120000) -> bool:
        """Check if job meets minimum salary requirement"""
        if job_data.get('salary_min'):
            return job_data['salary_min'] >= min_salary
        elif job_data.get('salary_max'):
            return job_data['salary_max'] >= min_salary
        else:
            # If no salary info, include it for manual review
            return True
    
    def get_job_details(self, job_url: str) -> Dict:
        """Get detailed job information from job page"""
        try:
            response = self.session.get(job_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get full job description
            description_elem = soup.find('div', class_='jobsearch-jobDescriptionText')
            description = description_elem.get_text(strip=True) if description_elem else ""
            
            # Try to extract requirements/qualifications section
            requirements = ""
            req_headers = soup.find_all(['h3', 'h4', 'strong'], 
                                      text=re.compile(r'(requirements|qualifications|skills)', re.I))
            
            for header in req_headers:
                # Get the next sibling elements that contain requirements
                next_elem = header.find_next_sibling()
                if next_elem:
                    requirements += next_elem.get_text(strip=True) + "\n"
            
            time.sleep(self.delay)  # Be respectful
            
            return {
                'description': description,
                'requirements': requirements
            }
            
        except Exception as e:
            logging.error(f"Error getting job details for {job_url}: {e}")
            return {'description': '', 'requirements': ''}