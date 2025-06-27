# src/utils/linkedin_job_scraper.py
import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import Dict, Optional
import re

class LinkedInJobScraper:
    """
    Scrapes LinkedIn job posting content from public URLs
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # Mimic a real browser to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def scrape_job_content(self, linkedin_url: str) -> Dict:
        """
        Scrape job content from LinkedIn URL
        
        Args:
            linkedin_url: LinkedIn job posting URL
            
        Returns:
            Dictionary with scraped job information
        """
        try:
            # Add small delay to be respectful
            time.sleep(1)
            
            self.logger.info(f"Scraping LinkedIn job: {linkedin_url}")
            
            response = self.session.get(linkedin_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract job information from LinkedIn's public job page
            job_data = {
                'url': linkedin_url,
                'title': self._extract_title(soup),
                'company': self._extract_company(soup),
                'location': self._extract_location(soup),
                'description': self._extract_description(soup),
                'employment_type': self._extract_employment_type(soup),
                'experience_level': self._extract_experience_level(soup),
                'industry': self._extract_industry(soup),
                'scraped_successfully': True,
                'scraped_timestamp': time.time()
            }
            
            # Clean up the description
            if job_data['description']:
                job_data['description'] = self._clean_description(job_data['description'])
                job_data['description_length'] = len(job_data['description'])
            
            self.logger.info(f"Successfully scraped job: {job_data['title']} at {job_data['company']}")
            return job_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error scraping {linkedin_url}: {e}")
            return self._error_response(linkedin_url, f"Network error: {e}")
            
        except Exception as e:
            self.logger.error(f"Error scraping {linkedin_url}: {e}")
            return self._error_response(linkedin_url, f"Parsing error: {e}")
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job title from page"""
        selectors = [
            'h1.t-24.t-bold.inline',
            'h1[data-test-id="job-title"]',
            'h1.topcard__title',
            'h1.job-title',
            'h1'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
        return None
    
    def _extract_company(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company name from page"""
        selectors = [
            'a.topcard__org-name-link',
            'span.topcard__flavor--black-link',
            'a[data-test-id="job-details-company-name"]',
            'span.job-details-jobs-unified-top-card__company-name'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
        return None
    
    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job location from page"""
        selectors = [
            'span.topcard__flavor--bullet',
            'span[data-test-id="job-details-location"]',
            'span.job-details-jobs-unified-top-card__bullet'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                # Filter out non-location bullets
                if any(word in text.lower() for word in ['remote', 'hybrid', 'on-site', 'city', 'state', 'country']):
                    return text
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job description from page"""
        selectors = [
            'div.description__text',
            'div[data-test-id="job-details-description"]',
            'div.jobs-description__content',
            'div.job-details-jobs-unified-top-card__job-description',
            'section.job-details',
            'div.jobs-box__html-content'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Get text content and preserve some structure
                text = element.get_text(separator='\n').strip()
                if len(text) > 100:  # Only return if substantial content
                    return text
        
        # Fallback: look for any large text blocks
        all_text = soup.get_text()
        if len(all_text) > 500:
            # Try to extract the main content area
            paragraphs = soup.find_all('p')
            if paragraphs:
                combined_text = '\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50])
                if len(combined_text) > 200:
                    return combined_text
        
        return None
    
    def _extract_employment_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract employment type (Full-time, Part-time, etc.)"""
        text = soup.get_text().lower()
        
        if 'full-time' in text or 'full time' in text:
            return 'Full-time'
        elif 'part-time' in text or 'part time' in text:
            return 'Part-time'
        elif 'contract' in text:
            return 'Contract'
        elif 'temporary' in text:
            return 'Temporary'
        elif 'internship' in text:
            return 'Internship'
        
        return None
    
    def _extract_experience_level(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract experience level from job content"""
        text = soup.get_text().lower()
        
        if any(word in text for word in ['senior', 'sr.', 'lead', 'principal']):
            return 'Senior'
        elif any(word in text for word in ['junior', 'jr.', 'entry level', 'entry-level']):
            return 'Junior'
        elif any(word in text for word in ['director', 'vp', 'vice president', 'head of']):
            return 'Executive'
        else:
            return 'Mid'
    
    def _extract_industry(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract industry information"""
        text = soup.get_text().lower()
        
        industries = {
            'technology': ['software', 'tech', 'saas', 'cloud', 'ai', 'machine learning'],
            'finance': ['financial', 'banking', 'fintech', 'investment'],
            'healthcare': ['health', 'medical', 'pharma', 'biotech'],
            'retail': ['retail', 'e-commerce', 'consumer'],
            'consulting': ['consulting', 'advisory', 'strategy']
        }
        
        for industry, keywords in industries.items():
            if any(keyword in text for keyword in keywords):
                return industry.title()
        
        return None
    
    def _clean_description(self, description: str) -> str:
        """Clean and normalize job description text"""
        # Remove excessive whitespace
        description = re.sub(r'\s+', ' ', description)
        
        # Remove common LinkedIn artifacts
        description = re.sub(r'Show more\s*Show less', '', description)
        description = re.sub(r'See more jobs like this.*$', '', description)
        
        # Clean up bullet points and formatting
        description = re.sub(r'\s*•\s*', '\n• ', description)
        description = re.sub(r'\s*-\s*', '\n- ', description)
        
        return description.strip()
    
    def _error_response(self, url: str, error_msg: str) -> Dict:
        """Return error response format"""
        return {
            'url': url,
            'title': None,
            'company': None,
            'location': None,
            'description': None,
            'employment_type': None,
            'experience_level': None,
            'industry': None,
            'scraped_successfully': False,
            'error_message': error_msg,
            'scraped_timestamp': time.time()
        }
    
    def enhance_job_with_linkedin_content(self, job: Dict) -> Dict:
        """
        Enhance a job dictionary with scraped LinkedIn content
        
        Args:
            job: Existing job dictionary with 'url' field
            
        Returns:
            Enhanced job dictionary with scraped content
        """
        linkedin_url = job.get('url')
        
        if not linkedin_url or not linkedin_url.startswith('http'):
            self.logger.warning(f"Invalid LinkedIn URL for job {job.get('job_id', 'unknown')}: {linkedin_url}")
            return job
        
        # Skip if already scraped recently (within last day)
        if job.get('scraped_timestamp') and (time.time() - job.get('scraped_timestamp', 0)) < 86400:
            self.logger.info(f"Job {job.get('job_id')} already scraped recently, skipping")
            return job
        
        scraped_data = self.scrape_job_content(linkedin_url)
        
        if scraped_data['scraped_successfully']:
            # Update job with scraped content, preserving existing data
            job.update({
                'description': scraped_data['description'],
                'employment_type': scraped_data.get('employment_type'),
                'scraped_experience_level': scraped_data.get('experience_level'),
                'scraped_industry': scraped_data.get('industry'),
                'scraped_successfully': True,
                'scraped_timestamp': scraped_data['scraped_timestamp'],
                'description_length': scraped_data.get('description_length', 0)
            })
            
            # Update title/company if scraping found better data
            if scraped_data.get('title') and len(scraped_data['title']) > len(job.get('title', '')):
                job['original_title'] = job.get('title')
                job['title'] = scraped_data['title']
            
            if scraped_data.get('company') and not job.get('company'):
                job['company'] = scraped_data['company']
                
        else:
            job.update({
                'scraped_successfully': False,
                'scraping_error': scraped_data.get('error_message'),
                'scraped_timestamp': scraped_data['scraped_timestamp']
            })
        
        return job


# Test function
def test_linkedin_scraper():
    """Test the LinkedIn job scraper"""
    scraper = LinkedInJobScraper()
    
    # Test with a real LinkedIn job URL
    test_url = "https://www.linkedin.com/jobs/view/4158986236/"
    
    result = scraper.scrape_job_content(test_url)
    
    print("Scraping Results:")
    print(f"Title: {result.get('title')}")
    print(f"Company: {result.get('company')}")
    print(f"Location: {result.get('location')}")
    print(f"Description Length: {len(result.get('description', ''))}")
    print(f"Successfully Scraped: {result.get('scraped_successfully')}")
    
    if result.get('description'):
        print(f"Description Preview: {result['description'][:200]}...")

if __name__ == "__main__":
    test_linkedin_scraper()