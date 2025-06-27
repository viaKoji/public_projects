# Version 2.5 - Salary Parser Utility
# src/utils/salary_parser.py
import re
import logging

class SalaryParser:
    """
    Utility to extract salary information from job titles, descriptions, and other text
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common salary patterns
        self.salary_patterns = [
            # $174K-$235K, $174k-$235k
            r'\$(\d+)k?\s*-\s*\$(\d+)k?',
            # $174,000-$235,000
            r'\$(\d{1,3}(?:,\d{3})*)\s*-\s*\$(\d{1,3}(?:,\d{3})*)',
            # 174K-235K (without $)
            r'(\d+)k?\s*-\s*(\d+)k?(?:\s*(?:per year|/year|annually|salary))?',
            # $174K - $235K (with spaces)
            r'\$(\d+)k?\s*[-–]\s*\$(\d+)k?',
            # Salary: $174,000 - $235,000
            r'salary:?\s*\$(\d{1,3}(?:,\d{3})*)\s*-\s*\$(\d{1,3}(?:,\d{3})*)',
            # Up to $200K, Up to $200,000
            r'up to \$(\d{1,3}(?:,\d{3})*||\d+k?)',
            # Starting at $150K
            r'starting at \$(\d{1,3}(?:,\d{3})*||\d+k?)',
            # $150K+, $150,000+
            r'\$(\d{1,3}(?:,\d{3})*|\d+k?)\+',
        ]
    
    def parse_salary_from_text(self, text: str) -> dict:
        """
        Extract salary information from any text
        
        Args:
            text: Text to search for salary information
            
        Returns:
            Dict with salary_min, salary_max, and original_text
        """
        if not text:
            return {}
        
        # Clean the text
        text = text.replace('$', '$').replace('–', '-').replace('—', '-')
        text_lower = text.lower()
        
        result = {}
        
        # Try each pattern
        for pattern in self.salary_patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            
            for match in matches:
                groups = match.groups()
                
                if len(groups) == 2:  # Range pattern
                    min_sal, max_sal = groups
                    result['salary_min'] = self._parse_salary_number(min_sal)
                    result['salary_max'] = self._parse_salary_number(max_sal)
                    result['original_text'] = match.group(0)
                    break
                    
                elif len(groups) == 1:  # Single salary (up to, starting at, etc.)
                    salary = self._parse_salary_number(groups[0])
                    if 'up to' in text_lower:
                        result['salary_max'] = salary
                    elif 'starting' in text_lower or '+' in match.group(0):
                        result['salary_min'] = salary
                    else:
                        result['salary_min'] = salary
                    result['original_text'] = match.group(0)
                    break
            
            if result:  # Found a match, stop trying other patterns
                break
        
        return result
    
    def _parse_salary_number(self, salary_str: str) -> int:
        """Convert salary string to integer"""
        if not salary_str:
            return 0
        
        # Remove common characters
        clean_salary = re.sub(r'[,$\s]', '', salary_str.lower())
        
        # Handle K suffix
        if clean_salary.endswith('k'):
            try:
                return int(float(clean_salary[:-1]) * 1000)
            except ValueError:
                return 0
        
        # Handle regular numbers
        try:
            return int(clean_salary)
        except ValueError:
            return 0
    
    def parse_job_salary(self, job: dict) -> dict:
        """
        Parse salary from a complete job dictionary (BULLETPROOF VERSION)
        
        Args:
            job: Job dictionary
            
        Returns:
            Updated job dictionary with parsed salary info
        """
        # Safety check: ensure job is a dictionary
        if not isinstance(job, dict):
            self.logger.warning(f"parse_job_salary received non-dict: {type(job)}")
            return {}
        
        # If salary is already properly parsed, return as-is
        existing_min = job.get('salary_min')
        existing_max = job.get('salary_max')
        if existing_min and existing_max:
            return job
        
        # SAFE: Convert None values to empty strings and handle slicing safely
        def safe_text_field(field_value, max_length=None):
            """Safely convert field to string and optionally limit length"""
            if field_value is None:
                return ''
            text = str(field_value)
            if max_length and len(text) > max_length:
                return text[:max_length]
            return text
        
        # Combine text sources to search (ALL NONE-SAFE)
        search_text = " ".join([
            safe_text_field(job.get('title')),
            safe_text_field(job.get('description'), 500),  # FIXED: Safe slice
            safe_text_field(job.get('location')),
            safe_text_field(job.get('company'))
        ])
        
        # Parse salary
        try:
            salary_info = self.parse_salary_from_text(search_text)
            
            if salary_info:
                # Update job with parsed salary info
                if 'salary_min' in salary_info and salary_info['salary_min'] > 0:
                    job['salary_min'] = salary_info['salary_min']
                if 'salary_max' in salary_info and salary_info['salary_max'] > 0:
                    job['salary_max'] = salary_info['salary_max']
                
                # Log what we found
                job_title = safe_text_field(job.get('title'), 50) or 'Unknown'
                self.logger.info(f"Parsed salary for {job_title}: "
                            f"${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}")
        
        except Exception as e:
            job_title = safe_text_field(job.get('title'), 50) or 'Unknown'
            self.logger.error(f"Error parsing salary for {job_title}: {e}")
        
        return job
    
    def clean_job_title(self, title: str) -> str:
        """
        Remove salary information from job title to clean it up
        
        Args:
            title: Original job title
            
        Returns:
            Cleaned job title
        """
        if not title:
            return title
        
        # Remove salary patterns from title
        cleaned = title
        
        for pattern in self.salary_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra spaces and separators
        cleaned = re.sub(r'\s*[·•|]\s*', ' · ', cleaned)  # Normalize separators
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
        cleaned = cleaned.strip(' ·•|')  # Remove leading/trailing separators
        
        return cleaned


# Helper function to process existing jobs in database
def update_jobs_with_salary_parsing():
    """
    Utility function to update existing jobs in database with parsed salary info
    """
    import sys
    sys.path.append('src')
    
    from database.simple_db_manager import SimpleJobDatabaseManager
    from config.settings import DATABASE_PATH
    
    db_manager = SimpleJobDatabaseManager(DATABASE_PATH)
    salary_parser = SalaryParser()
    
    # Get all jobs
    jobs = db_manager.get_jobs(limit=1000)
    updated_count = 0
    
    print(f"Processing {len(jobs)} jobs for salary parsing...")
    
    for job in jobs:
        original_job = job.copy()
        
        # Parse salary
        updated_job = salary_parser.parse_job_salary(job)
        
        # Check if anything changed
        if (updated_job.get('salary_min') != original_job.get('salary_min') or 
            updated_job.get('salary_max') != original_job.get('salary_max')):
            
            # Update in database (you might need to add an update method)
            print(f"Updated: {updated_job['title'][:50]}... "
                  f"Salary: ${updated_job.get('salary_min', 0):,} - ${updated_job.get('salary_max', 0):,}")
            updated_count += 1
    
    print(f"Updated {updated_count} jobs with salary information")


# Test function
def test_salary_parser():
    """Test the salary parser with various examples"""
    parser = SalaryParser()
    
    test_cases = [
        "Senior Engineering ManagerTrust & Will · United States (Remote)$174K-$235K / year",
        "Product Manager at Google $150,000 - $200,000 annually",
        "Software Engineer up to $180K",
        "Data Scientist starting at $120,000",
        "VP Engineering $250K+",
        "Marketing Manager Salary: $80,000 - $100,000",
        "Remote Developer 100k-150k per year"
    ]
    
    print("Testing Salary Parser:")
    print("="*60)
    
    for text in test_cases:
        result = parser.parse_salary_from_text(text)
        cleaned_title = parser.clean_job_title(text)
        
        print(f"Original: {text}")
        print(f"Salary: ${result.get('salary_min', 0):,} - ${result.get('salary_max', 0):,}")
        print(f"Cleaned Title: {cleaned_title}")
        print("-" * 40)


if __name__ == "__main__":
    test_salary_parser()