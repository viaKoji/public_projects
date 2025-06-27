#!/usr/bin/env python3
"""
Gmail LinkedIn Job Scraper v3.5 - IMPROVED PARSING
Fixed parsing issues: header contamination, salary extraction, location cleanup
"""

import os
import sys
import pickle
import base64
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
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
        
        print("🔧 Gmail LinkedIn Scraper v3.5 - Improved Parsing")
        
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
        """Parse job listings from LinkedIn email text using improved patterns"""
        jobs = []
        
        try:
            # Method 1: Split by separators (handles most LinkedIn emails)
            separator_patterns = [
                r'-{50,}',  # Long dashes
                r'View job:',  # View job lines
            ]
            
            sections = []
            for pattern in separator_patterns:
                parts = re.split(pattern, email_text)
                if len(parts) > 1:
                    sections = parts
                    break
            
            if not sections:
                sections = [email_text]  # Fallback to whole email
            
            for section in sections:
                section = section.strip()
                if not section or len(section) < 50:  # Skip very short sections
                    continue
                
                # Look for LinkedIn job URLs in this section
                url_matches = re.finditer(r'https://www\.linkedin\.com/comm/jobs/view/(\d+)', section)
                
                for url_match in url_matches:
                    job_id = url_match.group(1)
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                    
                    # Parse job details from the text before the URL
                    job_info = self._parse_job_section_improved(section, job_url, job_id, url_match)
                    if job_info and self._is_valid_job(job_info):
                        jobs.append(job_info)
            
            # Method 2: Alternative parsing for different formats
            if not jobs:
                jobs = self._parse_jobs_alternative_method(email_text)
            
        except Exception as e:
            print(f"   ⚠️ Error parsing jobs from email: {e}")
        
        return jobs
    
    def _parse_job_section_improved(self, section: str, job_url: str, job_id: str, url_match) -> Optional[Dict]:
        """Improved job section parsing with better pattern recognition"""
        try:
            # Get text before the URL (this contains the job details)
            text_before_url = section[:url_match.start()].strip()
            lines = [line.strip() for line in text_before_url.split('\n') if line.strip()]
            
            # Remove lines that are clearly not job data
            filtered_lines = []
            for line in lines:
                # Skip email headers and navigation text
                if any(skip_phrase in line.lower() for skip_phrase in [
                    'your job alert', 'new jobs match', 'job picks', 'similar jobs',
                    'preferences', 'match your', 'jobs for you', 'see all jobs',
                    'linkedin', 'unsubscribe', 'manage', 'help center',
                    'you are receiving', 'intended for', 'why we included'
                ]):
                    continue
                
                # Skip very short lines (likely formatting)
                if len(line) < 3:
                    continue
                
                # Skip lines that are just numbers or symbols
                if re.match(r'^[\d\s\-\+\=\*]+$', line):
                    continue
                
                filtered_lines.append(line)
            
            if len(filtered_lines) < 2:
                return None
            
            # Extract job information from filtered lines
            job_title = None
            company = None
            location = None
            salary = None
            additional_info = []
            
            # Pattern recognition for LinkedIn job emails
            # Usually: Job Title, Company, Location, [optional extras]
            idx = 0
            
            # Find job title (first substantial line that looks like a job title)
            while idx < len(filtered_lines):
                line = filtered_lines[idx]
                if self._looks_like_job_title(line):
                    job_title = line
                    idx += 1
                    break
                idx += 1
            
            # Find company (next line after job title)
            if idx < len(filtered_lines):
                company = filtered_lines[idx]
                idx += 1
            
            # Find location (next line after company, if it looks like a location)
            if idx < len(filtered_lines):
                potential_location = filtered_lines[idx]
                if self._looks_like_location(potential_location):
                    location = self._clean_location(potential_location)
                    idx += 1
                else:
                    location = "United States"  # Default fallback
            
            # Process remaining lines for additional info and salary
            while idx < len(filtered_lines):
                line = filtered_lines[idx]
                
                # Check for salary information
                salary_match = re.search(r'\$[\d,]+(?:K)?(?:-\$[\d,]+(?:K)?)?\s*(?:/\s*year)?', line)
                if salary_match and not salary:
                    salary = salary_match.group().strip()
                
                # Check for additional useful info
                if any(info_indicator in line.lower() for info_indicator in [
                    'alumni', 'skills match', 'experience match', 'actively hiring',
                    'apply with', 'company is', 'high match', 'school alumni'
                ]):
                    additional_info.append(line)
                
                idx += 1
            
            # Validate and clean the extracted data
            if not job_title or not company:
                return None
            
            # Clean up the data
            job_title = self._clean_job_title(job_title)
            company = self._clean_company_name(company)
            
            return {
                'job_id': job_id,
                'title': job_title,
                'company': company,
                'location': location or "United States",
                'url': job_url,
                'salary': salary,
                'additional_info': additional_info,
                'source': 'gmail_linkedin',
                'scraped_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"   ⚠️ Error parsing improved job section: {e}")
            return None
    
    def _looks_like_job_title(self, line: str) -> bool:
        """Check if a line looks like a job title"""
        # Job titles typically contain these keywords and are substantial
        job_keywords = [
            'engineer', 'manager', 'director', 'officer', 'analyst', 'specialist',
            'lead', 'senior', 'principal', 'staff', 'head', 'chief', 'vice president',
            'vp', 'svp', 'architect', 'developer', 'consultant', 'coordinator'
        ]
        
        if len(line) < 5 or len(line) > 100:
            return False
        
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in job_keywords)
    
    def _looks_like_location(self, line: str) -> bool:
        """Check if a line looks like a location"""
        # Common location patterns
        location_indicators = [
            'united states', 'remote', 'ca', 'ny', 'tx', 'wa', 'area',
            'city', 'state', 'county', 'district', 'san francisco', 'new york',
            'seattle', 'boston', 'los angeles', 'chicago', 'austin', 'denver'
        ]
        
        # Check for zip codes
        if re.match(r'^\d{5}(-\d{4})?$', line.strip()):
            return True
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in location_indicators)
    
    def _clean_location(self, location: str) -> str:
        """Clean and standardize location data"""
        if not location:
            return "United States"
        
        # Handle location with separators
        if '·' in location:
            parts = location.split('·')
            location = parts[0].strip()
        
        if ',' in location and 'Remote' not in location:
            # Keep full "City, State" format
            return location.strip()
        
        # Handle zip codes - try to expand them (basic mapping)
        zip_to_city = {
            '98004': 'Bellevue, WA',
            '98007': 'Bellevue, WA', 
            '27703': 'Durham, NC',
            '18064': 'Nazareth, PA'
        }
        
        if location.strip() in zip_to_city:
            return zip_to_city[location.strip()]
        
        return location.strip()
    
    def _clean_job_title(self, title: str) -> str:
        """Clean job title formatting"""
        if not title:
            return "Unknown Position"
        
        # Remove common prefixes and formatting
        title = re.sub(r'^[•·\-\*]\s*', '', title)
        title = title.strip()
        
        # Capitalize properly if all caps or all lowercase
        if title.isupper() or title.islower():
            title = title.title()
        
        return title
    
    def _clean_company_name(self, company: str) -> str:
        """Clean company name formatting"""
        if not company:
            return "Unknown Company"
        
        # Remove common prefixes and formatting
        company = re.sub(r'^[•·\-\*]\s*', '', company)
        company = company.strip()
        
        # Remove trailing info like "(Remote)" or "- Remote"
        company = re.sub(r'\s*[\(\-]\s*(Remote|Hybrid).*$', '', company, flags=re.IGNORECASE)
        
        return company
    
    def _is_valid_job(self, job_info: Dict) -> bool:
        """Validate that extracted job info is actually a job (not email header)"""
        title = job_info.get('title', '').lower()
        company = job_info.get('company', '').lower()
        
        # Filter out email headers that got parsed as jobs
        invalid_indicators = [
            'your job alert', 'new jobs match', 'jobs match your preferences',
            'job picks for you', 'similar jobs', 'preferences', 'match your'
        ]
        
        for indicator in invalid_indicators:
            if indicator in title or indicator in company:
                return False
        
        # Must have reasonable title and company
        if len(job_info.get('title', '')) < 5 or len(job_info.get('company', '')) < 2:
            return False
        
        return True
    
    def _parse_jobs_alternative_method(self, email_text: str) -> List[Dict]:
        """Alternative parsing method for different email formats"""
        jobs = []
        
        try:
            # Look for all LinkedIn job URLs
            url_pattern = r'https://www\.linkedin\.com/comm/jobs/view/(\d+)[^\s]*'
            url_matches = re.finditer(url_pattern, email_text)
            
            for match in url_matches:
                job_id = match.group(1)
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                
                # Find text around this URL (500 chars before, 100 after)
                start_pos = max(0, match.start() - 500)
                end_pos = min(len(email_text), match.end() + 100)
                context = email_text[start_pos:end_pos]
                
                # Try to extract job info from context
                job_info = self._extract_job_from_context(context, job_url, job_id)
                if job_info and self._is_valid_job(job_info):
                    jobs.append(job_info)
        
        except Exception as e:
            print(f"   ⚠️ Error in alternative parsing: {e}")
        
        return jobs
    
    def _extract_job_from_context(self, context: str, job_url: str, job_id: str) -> Optional[Dict]:
        """Extract job info from text context around URL"""
        try:
            lines = [line.strip() for line in context.split('\n') if line.strip()]
            
            # Look for job title patterns
            job_title = "Position Not Found"
            company = "Company Not Found"
            location = "United States"
            
            for i, line in enumerate(lines):
                if self._looks_like_job_title(line):
                    job_title = self._clean_job_title(line)
                    
                    # Try to find company in next few lines
                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line = lines[j]
                        if len(next_line) > 2 and not self._looks_like_location(next_line):
                            company = self._clean_company_name(next_line)
                            break
                    
                    # Try to find location
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j]
                        if self._looks_like_location(next_line):
                            location = self._clean_location(next_line)
                            break
                    
                    break
            
            return {
                'job_id': job_id,
                'title': job_title,
                'company': company,
                'location': location,
                'url': job_url,
                'salary': None,
                'additional_info': [],
                'source': 'gmail_linkedin_alt',
                'scraped_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"   ⚠️ Error extracting from context: {e}")
            return None
    
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
            
            # Show first 1000 characters of body
            print(f"\nFirst 1000 characters of body:")
            print("-" * 40)
            print(body_text[:1000])
            print("-" * 40)
            
            # Look for LinkedIn job URLs
            job_urls = re.findall(r'https://www\.linkedin\.com/comm/jobs/view/\d+', body_text)
            print(f"\nFound {len(job_urls)} job URLs:")
            for url in job_urls[:5]:  # Show first 5
                print(f"  {url}")
            
            # Test improved job parsing
            print(f"\n🔍 Testing improved job parsing...")
            jobs = self.parse_jobs_from_email(body_text, subject)
            print(f"✅ Parsed {len(jobs)} jobs from email")
            
            for j, job in enumerate(jobs[:3], 1):
                print(f"{j}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                if job.get('salary'):
                    print(f"   Salary: {job['salary']}")
                if job.get('additional_info'):
                    print(f"   Info: {', '.join(job['additional_info'])}")
    
    def scrape_jobs(self, max_emails: int = 50, scrape_descriptions: bool = True) -> List[Dict]:
        """Main method to scrape jobs from Gmail LinkedIn emails WITH immediate description scraping"""
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
                    valid_jobs = [job for job in jobs if self._is_valid_job(job)]
                    print(f"   ✅ Found {len(valid_jobs)} valid jobs (filtered {len(jobs) - len(valid_jobs)} invalid)")
                    
                    # ENHANCEMENT: Immediately scrape LinkedIn descriptions
                    if scrape_descriptions and linkedin_scraper:
                        enhanced_jobs = []
                        for j, job in enumerate(valid_jobs, 1):
                            try:
                                print(f"   🔗 [{j}/{len(valid_jobs)}] Scraping: {job['title'][:40]}...")
                                
                                # Enhance job with LinkedIn content
                                enhanced_job = linkedin_scraper.enhance_job_with_linkedin_content(job)
                                
                                if enhanced_job.get('scraped_successfully'):
                                    desc_len = len(enhanced_job.get('description', ''))
                                    print(f"   ✅ [{j}/{len(valid_jobs)}] Description: {desc_len} chars")
                                else:
                                    error = enhanced_job.get('scraping_error', 'Unknown error')
                                    print(f"   ⚠️ [{j}/{len(valid_jobs)}] Failed: {error}")
                                
                                enhanced_jobs.append(enhanced_job)
                                
                                # Add delay to be respectful to LinkedIn
                                if j < len(valid_jobs):  # No delay after last job
                                    import time
                                    time.sleep(2)
                                
                            except Exception as scrape_error:
                                print(f"   ❌ [{j}/{len(valid_jobs)}] Error: {scrape_error}")
                                enhanced_jobs.append(job)  # Keep original job
                        
                        all_jobs.extend(enhanced_jobs)
                    else:
                        # No description scraping - just add the jobs
                        all_jobs.extend(valid_jobs)
                        
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
    """Test the improved Gmail LinkedIn scraper"""
    scraper = GmailLinkedInScraper()
    
    try:
        # Scrape jobs
        jobs = scraper.scrape_jobs(max_emails=20)
        
        if jobs:
            print(f"\n✅ Successfully scraped {len(jobs)} jobs!")
            
            # Display sample jobs
            print("\n📋 Sample jobs:")
            for i, job in enumerate(jobs[:5]):
                print(f"\n{i+1}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                print(f"   URL: {job['url']}")
                if job['salary']:
                    print(f"   Salary: {job['salary']}")
                if job['additional_info']:
                    print(f"   Info: {', '.join(job['additional_info'])}")
            
            # Save results
            with open('gmail_scraped_jobs_improved.json', 'w') as f:
                json.dump(jobs, f, indent=2)
            print(f"\n💾 Jobs saved to gmail_scraped_jobs_improved.json")
        
        else:
            print("\n❌ No jobs found. Check your email parsing patterns.")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()