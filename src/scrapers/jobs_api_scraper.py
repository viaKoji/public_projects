# src/scrapers/jobs_api_scraper.py
import requests
import logging
import hashlib
from typing import List, Dict
import time

class JobsAPIScraper:
    """Scraper for various job APIs as backup to Indeed"""
    
    def __init__(self, delay: int = 1):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Job Search Tool v1.0',
            'Accept': 'application/json'
        })
    
    def search_jobs(self, keywords: str, location: str = "Seattle, WA", max_jobs: int = 50) -> List[Dict]:
        """Search multiple job APIs"""
        all_jobs = []
        
        # Try multiple sources
        sources = [
            self._search_adzuna,
            self._search_themuse,
            self._search_usajobs  # For government positions
        ]
        
        for source_func in sources:
            try:
                jobs = source_func(keywords, location, max_jobs // len(sources))
                all_jobs.extend(jobs)
                time.sleep(self.delay)
            except Exception as e:
                logging.error(f"Error with {source_func.__name__}: {e}")
                continue
        
        return all_jobs[:max_jobs]
    
    def _search_adzuna(self, keywords: str, location: str, max_jobs: int) -> List[Dict]:
        """Search Adzuna API (free tier available)"""
        try:
            # Adzuna API endpoint (you'd need to register for free API key)
            # For now, this is a placeholder that demonstrates the structure
            url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
            
            params = {
                'app_id': 'your_app_id',  # Would need actual API key
                'app_key': 'your_app_key',
                'what': keywords,
                'where': location,
                'results_per_page': min(max_jobs, 20),
                'sort_by': 'date'
            }
            
            # For now, return empty since we don't have API keys
            # In a real implementation, you'd make the API call here
            logging.info("Adzuna API would be called here (need API key)")
            return []
            
        except Exception as e:
            logging.error(f"Adzuna API error: {e}")
            return []
    
    def _search_themuse(self, keywords: str, location: str, max_jobs: int) -> List[Dict]:
        """Search The Muse API (no key required for basic usage)"""
        try:
            url = "https://www.themuse.com/api/public/jobs"
            
            # Map keywords to categories
            category = "Engineering"  # Default
            if "product manager" in keywords.lower():
                category = "Product"
            elif "design" in keywords.lower():
                category = "Design"
            elif "engineer" in keywords.lower():
                category = "Engineering"
            
            params = {
                'category': category,
                'location': 'Seattle%2C%20WA',
                'page': 1,
                'descending': True
            }
            
            # Add more specific headers
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://www.themuse.com/jobs',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                jobs = []
                
                for job in data.get('results', [])[:max_jobs]:
                    # Check if job title matches our keywords
                    job_title = job.get('name', '').lower()
                    if any(word in job_title for word in keywords.lower().split()):
                        job_data = self._parse_muse_job(job, keywords)
                        if job_data:
                            jobs.append(job_data)
                
                logging.info(f"Found {len(jobs)} matching jobs from The Muse")
                return jobs
            else:
                logging.warning(f"The Muse API returned status {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"The Muse API error: {e}")
            return []
    
    def _search_usajobs(self, keywords: str, location: str, max_jobs: int) -> List[Dict]:
        """Search USAJobs API for government positions"""
        try:
            url = "https://data.usajobs.gov/api/search"
            
            # USAJobs requires specific headers
            headers = {
                'Host': 'data.usajobs.gov',
                'User-Agent': 'jobsearch-bot@example.com',  # Replace with your email
                'Authorization-Key': 'your-usajobs-api-key-here'  # Optional: get free key from usajobs.gov
            }
            
            params = {
                'Keyword': keywords,
                'LocationName': 'Seattle, Washington',
                'ResultsPerPage': min(max_jobs, 25),
                'SortField': 'ApplicationCloseDate',
                'SortDirection': 'DESC'
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                jobs = []
                
                search_result = data.get('SearchResult', {})
                items = search_result.get('SearchResultItems', [])
                
                for item in items[:max_jobs]:
                    job_data = self._parse_usajobs_job(item['MatchedObjectDescriptor'])
                    if job_data:
                        jobs.append(job_data)
                
                logging.info(f"Found {len(jobs)} jobs from USAJobs")
                return jobs
            else:
                logging.warning(f"USAJobs API returned status {response.status_code}: {response.text[:200]}")
                return []
                
        except Exception as e:
            logging.error(f"USAJobs API error: {e}")
            return []
    
    def _parse_muse_job(self, job_data: dict, keywords: str) -> Dict:
        """Parse job data from The Muse"""
        try:
            job_id = f"muse_{job_data.get('id', '')}"
            
            return {
                'job_id': job_id,
                'title': job_data.get('name', ''),
                'company': job_data.get('company', {}).get('name', 'Unknown Company'),
                'location': ', '.join([loc.get('name', '') for loc in job_data.get('locations', [])]),
                'salary_min': None,
                'salary_max': None,
                'description': job_data.get('contents', ''),
                'requirements': '',
                'job_type': 'full-time',
                'remote_type': 'unknown',
                'source': 'themuse',
                'url': job_data.get('refs', {}).get('landing_page', ''),
                'posted_date': job_data.get('publication_date', '')
            }
        except Exception as e:
            logging.error(f"Error parsing Muse job: {e}")
            return None
    
    def _parse_usajobs_job(self, job_data: dict) -> Dict:
        """Parse job data from USAJobs"""
        try:
            job_id = f"usajobs_{job_data.get('PositionID', '')}"
            
            # Extract salary information
            salary_min = None
            salary_max = None
            
            position_remuneration = job_data.get('PositionRemuneration', [])
            if position_remuneration:
                salary_min = position_remuneration[0].get('MinimumRange')
                salary_max = position_remuneration[0].get('MaximumRange')
            
            return {
                'job_id': job_id,
                'title': job_data.get('PositionTitle', ''),
                'company': job_data.get('OrganizationName', 'U.S. Government'),
                'location': ', '.join([loc.get('LocationName', '') for loc in job_data.get('PositionLocation', [])]),
                'salary_min': int(salary_min) if salary_min else None,
                'salary_max': int(salary_max) if salary_max else None,
                'description': job_data.get('UserArea', {}).get('Details', {}).get('MajorDuties', [''])[0],
                'requirements': job_data.get('QualificationSummary', ''),
                'job_type': 'full-time',
                'remote_type': 'onsite',  # Government jobs typically onsite
                'source': 'usajobs',
                'url': job_data.get('ApplyURI', [''])[0],
                'posted_date': job_data.get('PublicationStartDate', '')
            }
        except Exception as e:
            logging.error(f"Error parsing USAJobs job: {e}")
            return None