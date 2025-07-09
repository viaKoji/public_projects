#!/usr/bin/env python3
"""
Gmail LinkedIn Job Scraper v4.0 - FIXED PARSING
Properly handles all LinkedIn email formats
"""

import os
import sys
import pickle
import base64
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.path.append('src')
from utils.linkedin_job_scraper import LinkedInJobScraper

class GmailLinkedInScraper:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        self.service = None
        
        # LinkedIn job email senders we want to scrape
        self.LINKEDIN_SENDERS = [
            'jobs-noreply@linkedin.com',
            'jobs-listings@linkedin.com',
            'jobalerts-noreply@linkedin.com'
        ]
        
        print("🔧 Gmail LinkedIn Scraper v4.0 - Fixed Parsing")
        
    def authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        print("✅ Gmail authentication successful")
    
    def get_linkedin_emails(self, max_results: int = 50) -> List[Dict]:
        """Get recent LinkedIn job emails"""
        try:
            all_emails = []
            
            for sender in self.LINKEDIN_SENDERS:
                print(f"🔍 Searching emails from: {sender}")
                
                # Search for emails from this LinkedIn sender
                query = f'from:{sender}'
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_results // len(self.LINKEDIN_SENDERS)
                ).execute()
                
                messages = results.get('messages', [])
                print(f"   Found {len(messages)} emails")
                
                # Get full email content for each message
                for message in messages:
                    try:
                        email_data = self.service.users().messages().get(
                            userId='me',
                            id=message['id'],
                            format='full'
                        ).execute()
                        
                        all_emails.append(email_data)
                        
                    except Exception as e:
                        print(f"   ⚠️ Error getting email {message['id']}: {e}")
                        continue
            
            print(f"📧 Retrieved {len(all_emails)} total emails for parsing")
            return all_emails
            
        except Exception as e:
            print(f"❌ Error getting emails: {e}")
            return []
    
    def extract_email_content(self, email_data: Dict) -> tuple:
        """Extract subject, sender, and body text from email"""
        try:
            headers = email_data['payload'].get('headers', [])
            
            # Extract headers
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            
            # Extract email body text
            body_text = self._get_email_body(email_data['payload'])
            
            return subject, sender, body_text
            
        except Exception as e:
            print(f"   ⚠️ Error extracting email content: {e}")
            return "No Subject", "Unknown Sender", ""
    
    def _get_email_body(self, payload: Dict) -> str:
        """Recursively extract plain text body from email payload"""
        body_text = ""
        
        # Check if this part has body data
        if 'body' in payload and 'data' in payload['body']:
            try:
                decoded = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                body_text += decoded
            except:
                pass
        
        # Check multipart content
        if 'parts' in payload:
            for part in payload['parts']:
                # Look for text/plain parts
                if part.get('mimeType') == 'text/plain' and 'body' in part and 'data' in part['body']:
                    try:
                        decoded = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        body_text += decoded
                    except:
                        pass
                # Recursively check nested parts
                elif 'parts' in part:
                    body_text += self._get_email_body(part)
        
        return body_text
    
    def parse_jobs_from_email(self, email_text: str, subject: str) -> List[Dict]:
        """Parse job listings from LinkedIn email text with improved logic"""
        jobs = []
        
        try:
            # Find all job URLs first
            job_url_pattern = r'View job:\s*(https://www\.linkedin\.com/comm/jobs/view/(\d+)[^\s]*)'
            url_matches = list(re.finditer(job_url_pattern, email_text))
            
            if not url_matches:
                print("   No job URLs found in email")
                return []
            
            # Process each job URL and its preceding content
            for i, match in enumerate(url_matches):
                job_url = match.group(1).split('?')[0]  # Clean URL
                job_id = match.group(2)
                
                # Determine the content boundaries for this job
                # Start: either beginning of email or end of previous job URL
                if i == 0:
                    start_pos = 0
                else:
                    # Start after the previous job's URL line
                    prev_match = url_matches[i-1]
                    start_pos = email_text.find('\n', prev_match.end()) + 1
                
                # End: current URL match position
                end_pos = match.start()
                
                # Extract the job content
                job_content = email_text[start_pos:end_pos].strip()
                
                # Parse this job
                job_info = self._parse_job_content_smart(job_content, job_url, job_id)
                
                if job_info and self._is_valid_job(job_info):
                    jobs.append(job_info)
                    
        except Exception as e:
            print(f"   ⚠️ Error parsing jobs from email: {e}")
        
        return jobs

    def _parse_job_content_smart(self, content: str, job_url: str, job_id: str) -> Optional[Dict]:
        """Smart parsing that handles various LinkedIn email formats"""
        try:
            # Clean and split content into lines
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Remove email artifacts and headers
            lines = self._filter_email_artifacts(lines)
            
            if len(lines) < 1:
                return None
            
            # Identify job components using pattern matching
            job_title = None
            company = None
            location = None
            metadata = []
            
            # Pattern-based line classification
            for i, line in enumerate(lines):
                line_type = self._classify_line(line)
                
                if line_type == 'job_title' and not job_title:
                    job_title = line
                elif line_type == 'company' and not company:
                    company = line
                elif line_type == 'location' and not location:
                    location = line
                elif line_type == 'metadata':
                    metadata.append(line)
                elif not job_title and line_type == 'unknown':
                    # First substantive line is usually the job title
                    job_title = line
                elif not company and line_type == 'unknown' and job_title:
                    # Second substantive line is usually the company
                    company = line
                elif not location and line_type == 'unknown' and company:
                    # Third substantive line might be location
                    location = line
            
            # Handle special case: only 2 lines (title + location)
            if len(lines) == 2 and job_title and not company and location:
                # This is likely a job with no company listed
                pass  # Keep as is
            
            # Validate and fix common parsing errors
            job_title, company, location = self._validate_and_fix_parsing(
                job_title, company, location, lines
            )
            
            # Extract salary if present
            salary = self._extract_salary(content)
            
            return {
                'job_id': job_id,
                'title': job_title or "Unknown Position",
                'company': company or "Unknown Company",
                'location': location or "Location Not Specified",
                'url': job_url,
                'salary': salary,
                'additional_info': metadata,
                'source': 'gmail_linkedin',
                'scraped_at': datetime.now().isoformat(),
                'found_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   ⚠️ Error in smart parsing: {e}")
            return None
    
    def _filter_email_artifacts(self, lines: List[str]) -> List[str]:
        """Remove email headers, footers, and navigation elements"""
        filtered = []
        
        skip_patterns = [
            # Email headers and navigation
            'your job alert', 'new jobs match', 'job picks', 'similar jobs',
            'preferences', 'match your', 'jobs for you', 'see all jobs',
            'linkedin', 'unsubscribe', 'manage preferences', 'manage your',
            'help center', 'you are receiving', 'intended for', 'why we included',
            'results from the new ai-powered job search',
            
            # Separators
            '------', '=====', '-----',
            
            # Job count headers (e.g., "217 jobs in United States")
            r'^\d+\+?\s+.*\s+jobs\s+in\s+'
        ]
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if line should be skipped
            skip = False
            for pattern in skip_patterns:
                if pattern.startswith('^'):
                    # Regex pattern
                    if re.search(pattern, line, re.IGNORECASE):
                        skip = True
                        break
                elif pattern in line_lower:
                    skip = True
                    break
            
            if not skip and len(line) >= 2:
                filtered.append(line)
        
        return filtered
    
    def _classify_line(self, line: str) -> str:
        """Classify what type of content a line represents"""
        line_lower = line.lower()
        
        # Job title patterns
        job_title_keywords = [
            'manager', 'director', 'engineer', 'developer', 'analyst',
            'specialist', 'coordinator', 'administrator', 'assistant',
            'executive', 'officer', 'lead', 'senior', 'principal',
            'architect', 'consultant', 'designer', 'scientist',
            'ceo', 'cto', 'cfo', 'coo', 'vp', 'president',
            'co-founder', 'founder', 'partner', 'head'
        ]
        
        # Company patterns
        company_suffixes = [
            'inc', 'llc', 'corp', 'corporation', 'company', 'co',
            'ltd', 'limited', 'group', 'partners', 'solutions',
            'technologies', 'systems', 'services', 'labs', 'studio',
            'digital', 'global', 'international'
        ]
        
        # Location patterns
        location_patterns = [
            r'^[A-Za-z\s]+,\s*[A-Z]{2}$',  # City, ST
            r'^[A-Z]{2}$',  # Just state
            r'\b(remote|hybrid|onsite|on-site)\b',
            r'\b(area|region|metro|greater)\b'
        ]
        
        countries = [
            'united states', 'usa', 'canada', 'uk', 'united kingdom',
            'australia', 'germany', 'france', 'netherlands', 'singapore'
        ]
        
        # Metadata patterns
        metadata_patterns = [
            'alumni', 'connection', 'actively hiring', 'skills match',
            'experience match', 'apply with', 'this company'
        ]
        
        # PRIORITY CHECK: C-level and founder titles
        if re.search(r'\b(c[a-z]o|ceo|cto|cfo|coo|co-founder|founder)\b', line_lower):
            return 'job_title'
        
        # Check for pattern like "Role - Description" where Role contains job keywords
        if ' - ' in line:
            first_part = line.split(' - ')[0].lower()
            if any(keyword in first_part for keyword in job_title_keywords):
                return 'job_title'
        
        # Check for job title keywords
        if any(keyword in line_lower for keyword in job_title_keywords):
            return 'job_title'
        
        # Check for company
        if any(suffix in line_lower for suffix in company_suffixes):
            return 'company'
        
        # Check for location
        for pattern in location_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return 'location'
        
        if any(country in line_lower for country in countries):
            return 'location'
        
        # Check for metadata
        if any(pattern in line_lower for pattern in metadata_patterns):
            return 'metadata'
        
        # Check if it's a number-based metadata (e.g., "62 school alumni")
        if re.match(r'^\d+\s+\w+', line):
            return 'metadata'
        
        return 'unknown'
    
    def _validate_and_fix_parsing(self, job_title: str, company: str, 
                                   location: str, all_lines: List[str]) -> Tuple[str, str, str]:
        """Validate and fix common parsing errors"""
        
        # Fix: Country name parsed as company
        countries = ['united states', 'usa', 'canada', 'uk', 'united kingdom']
        if company and company.lower() in countries:
            # Company is actually a location
            if not location:
                location = company
                company = None
            
            # Try to find the real company in remaining lines
            if not company:
                for line in all_lines:
                    if (line != job_title and 
                        line != location and 
                        self._classify_line(line) in ['company', 'unknown'] and
                        line.lower() not in countries):
                        company = line
                        break
        
        # Fix: Location parsed as company
        if company and self._classify_line(company) == 'location':
            if not location:
                location = company
                company = None
        
        # Fix: Job title looks like metadata
        if job_title and self._classify_line(job_title) == 'metadata':
            # Shift everything down
            if company and not location:
                location = company
            company = job_title
            job_title = None
            
            # Find the real job title
            for line in all_lines:
                if self._classify_line(line) == 'job_title':
                    job_title = line
                    break
        
        return job_title, company, location
    
    def _extract_salary(self, content: str) -> Optional[str]:
        """Extract salary information from content"""
        salary_pattern = r'\$[\d,]+(?:K)?(?:\s*-\s*\$[\d,]+(?:K)?)?\s*(?:/\s*(?:year|yr))?'
        match = re.search(salary_pattern, content, re.IGNORECASE)
        return match.group(0).strip() if match else None
    
    def _is_valid_job(self, job_info: Dict) -> bool:
        """Validate that extracted job info is actually a job"""
        title = job_info.get('title', '').lower()
        company = job_info.get('company', '').lower()
        
        # Filter out email headers and summaries
        invalid_indicators = [
            'your job alert', 'new jobs match', 'jobs match your preferences',
            'job picks for you', 'similar jobs', 'preferences', 'match your',
            'jobs in united states', 'jobs in usa', 'jobs in us'
        ]
        
        # Filter out job search summaries
        if re.search(r'\b\d[\d,]*\+?\s+.*\s+jobs\s+in\s+', title, re.IGNORECASE):
            return False
        
        for indicator in invalid_indicators:
            if indicator in title or indicator in company:
                return False
        
        # Must have reasonable title
        if len(job_info.get('title', '')) < 3:
            return False
        
        return True
    
    def debug_email_content(self, max_emails: int = 3):
        """Debug method to examine raw email content"""
        print("🔍 DEBUG: Examining email content...")
        
        if not self.service:
            self.authenticate()
        
        emails = self.get_linkedin_emails(max_emails)
        
        for i, email_data in enumerate(emails):
            print(f"\n{'='*60}")
            print(f"EMAIL {i+1}")
            print(f"{'='*60}")
            
            # Extract email content
            subject, sender, body_text = self.extract_email_content(email_data)
            
            print(f"Subject: {subject}")
            print(f"Sender: {sender}")
            print(f"Body length: {len(body_text)} characters")
            
            # Test improved job parsing
            print(f"\n🔍 Testing improved job parsing...")
            jobs = self.parse_jobs_from_email(body_text, subject)
            print(f"✅ Parsed {len(jobs)} jobs from email")
            
            for j, job in enumerate(jobs[:5], 1):
                print(f"\n{j}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                if job.get('salary'):
                    print(f"   Salary: {job['salary']}")
                if job.get('additional_info'):
                    print(f"   Info: {', '.join(job['additional_info'])}")
    
    def scrape_jobs(self, max_emails: int = 50, scrape_descriptions: bool = True) -> List[Dict]:
        """Main method to scrape jobs from Gmail LinkedIn emails"""
        print("🚀 Starting Gmail LinkedIn job scraping...")
        if scrape_descriptions:
            print("🔗 Will scrape LinkedIn descriptions immediately")
        
        if not self.service:
            self.authenticate()
        
        # Initialize LinkedIn content scraper if needed
        linkedin_scraper = LinkedInJobScraper() if scrape_descriptions else None
        
        # Get LinkedIn emails
        emails = self.get_linkedin_emails(max_emails)
        if not emails:
            print("❌ No LinkedIn emails found")
            return []
        
        all_jobs = []
        
        for i, email_data in enumerate(emails):
            try:
                print(f"📧 Processing email {i+1}/{len(emails)}")
                
                # Extract email content
                subject, sender, body_text = self.extract_email_content(email_data)
                print(f"   Subject: {subject[:60]}...")
                
                # Parse jobs from this email
                jobs = self.parse_jobs_from_email(body_text, subject)
                
                if jobs:
                    print(f"   ✅ Found {len(jobs)} valid jobs")
                    
                    # Enhance with LinkedIn descriptions if requested
                    if scrape_descriptions and linkedin_scraper:
                        enhanced_jobs = []
                        for j, job in enumerate(jobs, 1):
                            try:
                                print(f"   🔗 [{j}/{len(jobs)}] Scraping: {job['title'][:40]}...")
                                
                                # Enhance job with LinkedIn content
                                enhanced_job = linkedin_scraper.enhance_job_with_linkedin_content(job)
                                
                                if enhanced_job.get('scraped_successfully'):
                                    desc_len = len(enhanced_job.get('description', ''))
                                    print(f"   ✅ [{j}/{len(jobs)}] Description: {desc_len} chars")
                                else:
                                    error = enhanced_job.get('scraping_error', 'Unknown error')
                                    print(f"   ⚠️ [{j}/{len(jobs)}] Failed: {error}")
                                
                                enhanced_jobs.append(enhanced_job)
                                
                                # Add delay to be respectful to LinkedIn
                                if j < len(jobs):
                                    import time
                                    time.sleep(2)
                                
                            except Exception as scrape_error:
                                print(f"   ❌ [{j}/{len(jobs)}] Error: {scrape_error}")
                                enhanced_jobs.append(job)
                        
                        all_jobs.extend(enhanced_jobs)
                    else:
                        all_jobs.extend(jobs)
                else:
                    print(f"   ⚠️ No jobs found in this email")
                
            except Exception as e:
                print(f"   ❌ Error processing email: {e}")
                continue
        
        # Remove duplicates based on job_id
        unique_jobs = []
        seen_ids = set()
        
        for job in all_jobs:
            if job['job_id'] not in seen_ids:
                unique_jobs.append(job)
                seen_ids.add(job['job_id'])
        
        print(f"🎯 Final result: {len(unique_jobs)} unique jobs from {len(emails)} emails")
        
        if scrape_descriptions:
            with_descriptions = len([j for j in unique_jobs if j.get('description')])
            print(f"📄 Jobs with descriptions: {with_descriptions}/{len(unique_jobs)}")
        
        return unique_jobs

def main():
    """Test the fixed Gmail LinkedIn scraper"""
    scraper = GmailLinkedInScraper()
    
    try:
        # Test with debug output first
        scraper.debug_email_content(max_emails=2)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()