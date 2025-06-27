# src/scrapers/fixed_linkedin_scraper.py
# Version 3.0 - Extract maximum data from LinkedIn's limited public results

import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
import hashlib
import random

class FixedLinkedInScraper:
    def __init__(self, delay: int = 3):
        self.base_url = "https://www.linkedin.com"
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
    def search_jobs(self, keywords: str, location: str = "Seattle, WA", 
                   remote: bool = True, max_jobs: int = 10) -> List[Dict]:
        """Search for jobs on LinkedIn (extracts maximum from public results)"""
        jobs = []
        
        try:
            # Use direct LinkedIn job search URL
            search_url = "https://www.linkedin.com/jobs/search"
            
            search_params = {
                'keywords': keywords,
                'location': location,
                'position': 1,
                'pageNum': 0
            }
            
            if remote:
                search_params['f_WT'] = '2'  # Remote work type
            
            logging.info(f"Searching LinkedIn for: {keywords} in {location}")
            
            # Add random delay
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(search_url, params=search_params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for the main job results list
                job_list = soup.find('ul', class_='jobs-search__results-list')
                if not job_list:
                    logging.info("No job results list found")
                    return jobs
                
                # Find all job cards in the main visible section (before sign-in wall)
                job_cards = job_list.find_all('li')
                
                # Only process the first few jobs (before the sign-in wall)
                visible_jobs = []
                for card in job_cards:
                    # Skip cards that are part of the blurred overlay
                    if 'blurred-overlay' in card.get('class', []):
                        break
                    if card.find('div', class_='job-search-card') or card.find('div', class_='base-search-card'):
                        visible_jobs.append(card)
                
                logging.info(f"Found {len(visible_jobs)} visible job cards")
                
                for card in visible_jobs[:max_jobs]:
                    job_data = self._parse_linkedin_job_card(card)
                    if job_data and self._meets_criteria(job_data, keywords):
                        jobs.append(job_data)
                        logging.info(f"Parsed job: {job_data['title']} at {job_data['company']}")
                    
                    time.sleep(random.uniform(0.5, 1.0))
                    
            else:
                logging.warning(f"LinkedIn returned status {response.status_code}")
                
        except Exception as e:
            logging.error(f"Error searching LinkedIn: {e}")
            
        logging.info(f"Successfully extracted {len(jobs)} jobs from LinkedIn")
        return jobs
    
    def _parse_linkedin_job_card(self, card) -> Optional[Dict]:
        """Parse LinkedIn job card with improved selectors"""
        try:
            # Try multiple selectors for the job container
            job_container = (
                card.find('div', class_='job-search-card') or
                card.find('div', class_='base-search-card') or
                card.find('div', class_='base-card')
            )
            
            if not job_container:
                return None
            
            # Extract job title
            title_elem = (
                job_container.find('h3', class_='base-search-card__title') or
                job_container.find('h3', class_='job-search-card__title') or
                job_container.find('a', class_='base-card__full-link')
            )
            
            if not title_elem:
                return None
            
            # Get title text and URL
            if title_elem.name == 'a':
                title = title_elem.get_text(strip=True)
                job_url = title_elem.get('href', '')
            else:
                title_link = title_elem.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    job_url = title_link.get('href', '')
                else:
                    title = title_elem.get_text(strip=True)
                    job_url = ""
            
            # Extract company
            company_elem = (
                job_container.find('h4', class_='base-search-card__subtitle') or
                job_container.find('h4', class_='job-search-card__company') or
                job_container.find('a', class_='hidden-nested-link')
            )
            
            if company_elem:
                # Company might be in a nested link
                company_link = company_elem.find('a')
                company = company_link.get_text(strip=True) if company_link else company_elem.get_text(strip=True)
            else:
                company = "Unknown Company"
            
            # Extract location
            location_elem = (
                job_container.find('span', class_='job-search-card__location') or
                job_container.find('div', class_='base-search-card__metadata')
            )
            
            location = "Unknown Location"
            if location_elem:
                # Location might be in the metadata div
                if location_elem.name == 'div':
                    location_span = location_elem.find('span', class_='job-search-card__location')
                    location = location_span.get_text(strip=True) if location_span else location_elem.get_text(strip=True)
                else:
                    location = location_elem.get_text(strip=True)
            
            # Extract posting date
            posted_date = ""
            time_elem = job_container.find('time')
            if time_elem:
                posted_date = time_elem.get('datetime', '') or time_elem.get_text(strip=True)
            
            # Generate job ID
            if job_url:
                job_id_match = re.search(r'jobs/view/(\d+)', job_url)
                if job_id_match:
                    job_id = f"linkedin_{job_id_match.group(1)}"
                else:
                    job_id = hashlib.md5(job_url.encode()).hexdigest()
            else:
                job_id = hashlib.md5(f"{title}_{company}".encode()).hexdigest()
            
            # Determine remote type
            remote_type = "onsite"
            location_lower = location.lower()
            if "remote" in location_lower:
                remote_type = "remote"
            elif "hybrid" in location_lower:
                remote_type = "hybrid"
            
            # Clean up URL
            if job_url and not job_url.startswith('http'):
                job_url = f"https://www.linkedin.com{job_url}"
            
            return {
                'job_id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'salary_min': None,  # LinkedIn doesn't show salaries in search results
                'salary_max': None,
                'description': f"LinkedIn job posting: {title} at {company}",
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': remote_type,
                'source': 'linkedin',
                'url': job_url,
                'posted_date': posted_date
            }
            
        except Exception as e:
            logging.error(f"Error parsing LinkedIn job card: {e}")
            return None
    
    def _meets_criteria(self, job_data: Dict, keywords: str) -> bool:
        """Check if job meets our search criteria"""
        title_lower = job_data['title'].lower()
        keywords_lower = keywords.lower()
        
        # Simple keyword matching
        keyword_parts = keywords_lower.split()
        return any(part in title_lower for part in keyword_parts if len(part) > 2)