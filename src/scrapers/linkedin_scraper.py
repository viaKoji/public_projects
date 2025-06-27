# src/scrapers/linkedin_scraper.py
# Version: 2.0 - Focus on public LinkedIn job search with better parsing

import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
import hashlib
import random

class LinkedInJobsScraper:
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
                   remote: bool = True, max_jobs: int = 50) -> List[Dict]:
        """Search for jobs on LinkedIn (public job search)"""
        jobs = []
        
        try:
            # Use LinkedIn's public job search URL
            search_url = "https://www.linkedin.com/jobs/search"
            
            search_params = {
                'keywords': keywords,
                'location': location,
                'f_TPR': 'r86400',  # Posted in last 24 hours - try removing this
                'position': 1,
                'pageNum': 0
            }
            
            # Remove time filter - might be too restrictive
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
            
            # Debug: Log response details
            logging.info(f"LinkedIn response status: {response.status_code}")
            logging.info(f"LinkedIn response URL: {response.url}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Debug: Save HTML to see what we're getting
                with open('logs/linkedin_response.html', 'w', encoding='utf-8') as f:
                    f.write(soup.prettify())
                
                # Try multiple selectors for job cards
                selectors_to_try = [
                    'div.base-card',
                    'div.job-search-card',
                    'li.result-card',
                    'div[data-entity-urn*="job"]',
                    'article',
                    'div.jobs-search__results-list li',
                    'div.job-result-card'
                ]
                
                job_cards = []
                for selector in selectors_to_try:
                    job_cards = soup.select(selector)
                    if job_cards:
                        logging.info(f"Found {len(job_cards)} job cards with selector: {selector}")
                        break
                    else:
                        logging.info(f"No cards found with selector: {selector}")
                
                if not job_cards:
                    # Check if we're getting a login page or different content
                    page_title = soup.find('title')
                    if page_title:
                        logging.warning(f"LinkedIn page title: {page_title.get_text()}")
                    
                    # Look for any links that might be job links
                    all_links = soup.find_all('a', href=True)
                    job_links = [link for link in all_links if '/jobs/' in link.get('href', '')]
                    logging.info(f"Found {len(job_links)} potential job links")
                    
                    if len(job_links) > 0:
                        # Try parsing these as job cards
                        for link in job_links[:max_jobs]:
                            job_data = self._parse_job_link(link)
                            if job_data and self._meets_criteria(job_data, keywords):
                                jobs.append(job_data)
                else:
                    for card in job_cards[:max_jobs]:
                        job_data = self._parse_linkedin_job_card(card)
                        if job_data and self._meets_criteria(job_data, keywords):
                            jobs.append(job_data)
                        
                        time.sleep(random.uniform(0.5, 1.5))
                    
            elif response.status_code == 999:
                logging.warning("LinkedIn returned 999 - likely rate limited")
            else:
                logging.warning(f"LinkedIn returned status {response.status_code}")
                # Save error response for debugging
                with open('logs/linkedin_error.html', 'w', encoding='utf-8') as f:
                    f.write(response.text[:2000])
                
        except Exception as e:
            logging.error(f"Error searching LinkedIn: {e}")
            
        logging.info(f"Found {len(jobs)} jobs from LinkedIn")
        return jobs
    
    def _parse_job_link(self, link) -> Optional[Dict]:
        """Parse a job link element"""
        try:
            href = link.get('href', '')
            if not href:
                return None
            
            # Extract job title from link text or nearby elements
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                # Try to find title in parent or sibling elements
                parent = link.parent
                if parent:
                    title = parent.get_text(strip=True)
            
            if not title or len(title) < 3:
                return None
            
            # Generate job ID from URL
            job_id = hashlib.md5(f"linkedin_{href}".encode()).hexdigest()
            
            # Clean up the URL
            if href.startswith('/'):
                job_url = f"https://www.linkedin.com{href}"
            else:
                job_url = href
            
            return {
                'job_id': job_id,
                'title': title,
                'company': "LinkedIn Company",  # We'll get this from detailed page later
                'location': "Location TBD",
                'salary_min': None,
                'salary_max': None,
                'description': "LinkedIn job posting",
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': 'unknown',
                'source': 'linkedin',
                'url': job_url,
                'posted_date': ''
            }
            
        except Exception as e:
            logging.error(f"Error parsing LinkedIn job link: {e}")
            return None
        """Parse LinkedIn job card"""
        try:
            # Job title and link
            title_elem = (card.find('h3', class_='base-search-card__title') or
                         card.find('a', class_='result-card__full-card-link'))
            
            if not title_elem:
                return None
            
            if title_elem.name == 'a':
                title = title_elem.get_text(strip=True)
                job_url = title_elem.get('href', '')
            else:
                title_link = title_elem.find('a')
                if not title_link:
                    return None
                title = title_link.get_text(strip=True)
                job_url = title_link.get('href', '')
            
            # Company
            company_elem = (card.find('h4', class_='base-search-card__subtitle') or
                          card.find('a', class_='result-card__subtitle-link'))
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location
            location_elem = (card.find('span', class_='job-search-card__location') or
                           card.find('span', class_='result-card__location'))
            location = location_elem.get_text(strip=True) if location_elem else "Unknown Location"
            
            # Generate job ID
            job_id = hashlib.md5(f"linkedin_{job_url}".encode()).hexdigest()
            
            # Description (limited in search results)
            description = ""
            snippet_elem = card.find('p', class_='job-search-card__snippet')
            if snippet_elem:
                description = snippet_elem.get_text(strip=True)
            
            # Determine remote type
            remote_type = "onsite"
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
                'salary_min': None,  # Not usually shown in search results
                'salary_max': None,
                'description': description,
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': remote_type,
                'source': 'linkedin',
                'url': job_url if job_url.startswith('http') else f"https://www.linkedin.com{job_url}",
                'posted_date': self._extract_posted_date(card)
            }
            
        except Exception as e:
            logging.error(f"Error parsing LinkedIn job card: {e}")
            return None
    
    def _extract_posted_date(self, card) -> str:
        """Extract posting date from LinkedIn card"""
        try:
            date_elem = card.find('time', class_='job-search-card__listdate')
            if date_elem:
                return date_elem.get('datetime', '')
            
            # Alternative selector
            date_elem = card.find('span', class_='result-card__listdate')
            if date_elem:
                return date_elem.get_text(strip=True)
                
        except Exception:
            pass
        
        return ""
    
    def _meets_criteria(self, job_data: Dict, keywords: str) -> bool:
        """Check if job meets our search criteria"""
        title_lower = job_data['title'].lower()
        keywords_lower = keywords.lower()
        
        # Check if any keyword appears in title
        keyword_parts = keywords_lower.split()
        return any(part in title_lower for part in keyword_parts)