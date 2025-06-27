# src/utils/db_integrity_checker.py
import sqlite3
import logging
import json
from typing import List, Dict, Tuple
from datetime import datetime

class DatabaseIntegrityChecker:
    """
    Utility class for checking and fixing database integrity issues
    """
    
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def find_duplicate_jobs(self) -> List[Dict]:
        """
        Find potential duplicate jobs based on similar job IDs or content
        
        Returns:
            List of duplicate job groups
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Find jobs with similar job_ids (like the 4251767049 case)
                cursor.execute("""
                    SELECT job_id, title, company, url 
                    FROM jobs 
                    ORDER BY job_id
                """)
                
                all_jobs = cursor.fetchall()
                duplicates = []
                processed_ids = set()
                
                for job in all_jobs:
                    job_id = job['job_id']
                    
                    if job_id in processed_ids:
                        continue
                    
                    # Look for similar job IDs
                    similar_jobs = []
                    base_id = job_id
                    
                    # Extract numeric ID if it's embedded (like linkedin_email_4251767049)
                    import re
                    numeric_match = re.search(r'\d{10,}', job_id)
                    if numeric_match:
                        numeric_id = numeric_match.group()
                        
                        # Find all jobs with this numeric ID
                        for other_job in all_jobs:
                            other_id = other_job['job_id']
                            if numeric_id in other_id and other_id != job_id:
                                similar_jobs.append(dict(other_job))
                                processed_ids.add(other_id)
                    
                    if similar_jobs:
                        duplicate_group = {
                            'base_job': dict(job),
                            'similar_jobs': similar_jobs,
                            'total_count': len(similar_jobs) + 1,
                            'suggested_action': 'merge_or_remove_duplicates'
                        }
                        duplicates.append(duplicate_group)
                        processed_ids.add(job_id)
                
                return duplicates
                
        except Exception as e:
            self.logger.error(f"Error finding duplicate jobs: {e}")
            return []
    
    def find_orphaned_references(self) -> Dict:
        """
        Find orphaned references that might cause loading issues
        
        Returns:
            Dictionary with orphaned reference information
        """
        try:
            orphaned_refs = {
                'missing_job_ids': [],
                'invalid_job_ids': [],
                'feedback_orphans': []
            }
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for jobs with null or empty job_ids
                cursor.execute("SELECT id, title, company FROM jobs WHERE job_id IS NULL OR job_id = ''")
                invalid_jobs = cursor.fetchall()
                for job in invalid_jobs:
                    orphaned_refs['invalid_job_ids'].append({
                        'db_id': job[0],
                        'title': job[1],
                        'company': job[2]
                    })
                
                # Check job_feedback.json for references to non-existent jobs
                import os
                if os.path.exists('data/job_feedback.json'):
                    try:
                        with open('data/job_feedback.json', 'r') as f:
                            feedback_data = json.load(f)
                        
                        for feedback in feedback_data:
                            job_id = feedback.get('job_id')
                            if job_id:
                                cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,))
                                if not cursor.fetchone():
                                    orphaned_refs['feedback_orphans'].append({
                                        'job_id': job_id,
                                        'feedback': feedback
                                    })
                                    
                    except Exception as e:
                        self.logger.warning(f"Could not check feedback file: {e}")
            
            return orphaned_refs
            
        except Exception as e:
            self.logger.error(f"Error finding orphaned references: {e}")
            return {}
    
    def clean_duplicate_jobs(self, duplicate_groups: List[Dict], auto_resolve: bool = False) -> Dict:
        """
        Clean up duplicate jobs by merging or removing them
        
        Args:
            duplicate_groups: List of duplicate groups from find_duplicate_jobs()
            auto_resolve: If True, automatically resolve simple cases
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            cleanup_results = {
                'groups_processed': 0,
                'jobs_merged': 0,
                'jobs_removed': 0,
                'manual_review_needed': []
            }
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for group in duplicate_groups:
                    base_job = group['base_job']
                    similar_jobs = group['similar_jobs']
                    
                    if auto_resolve and len(similar_jobs) == 1:
                        # Simple case: merge two similar jobs
                        similar_job = similar_jobs[0]
                        
                        # Keep the job with more complete data
                        if self._job_has_more_data(base_job, similar_job):
                            keeper = base_job
                            to_remove = similar_job
                        else:
                            keeper = similar_job
                            to_remove = base_job
                        
                        # Remove the duplicate
                        cursor.execute("DELETE FROM jobs WHERE job_id = ?", (to_remove['job_id'],))
                        
                        cleanup_results['jobs_removed'] += 1
                        self.logger.info(f"Removed duplicate job: {to_remove['job_id']}")
                        
                    else:
                        # Complex case: needs manual review
                        cleanup_results['manual_review_needed'].append(group)
                    
                    cleanup_results['groups_processed'] += 1
                
                conn.commit()
            
            return cleanup_results
            
        except Exception as e:
            self.logger.error(f"Error cleaning duplicate jobs: {e}")
            return {}
    
    def _job_has_more_data(self, job1: Dict, job2: Dict) -> bool:
        """
        Compare two jobs and return True if job1 has more complete data
        """
        job1_score = 0
        job2_score = 0
        
        # Score based on data completeness
        fields_to_check = ['description', 'salary_min', 'salary_max', 'location', 'ai_analysis']
        
        for field in fields_to_check:
            if job1.get(field) and str(job1[field]).strip():
                job1_score += 1
            if job2.get(field) and str(job2[field]).strip():
                job2_score += 1
        
        # Prefer jobs with AI analysis
        if job1.get('ai_analyzed'):
            job1_score += 2
        if job2.get('ai_analyzed'):
            job2_score += 2
        
        return job1_score >= job2_score
    
    def validate_database_integrity(self) -> Dict:
        """
        Run comprehensive database integrity checks
        
        Returns:
            Dictionary with validation results
        """
        try:
            validation_results = {
                'total_jobs': 0,
                'duplicate_groups': [],
                'orphaned_references': {},
                'integrity_score': 100,
                'issues_found': [],
                'recommendations': []
            }
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total jobs
                cursor.execute("SELECT COUNT(*) FROM jobs")
                validation_results['total_jobs'] = cursor.fetchone()[0]
            
            # Find duplicates
            duplicates = self.find_duplicate_jobs()
            validation_results['duplicate_groups'] = duplicates
            
            if duplicates:
                validation_results['issues_found'].append(f"Found {len(duplicates)} duplicate job groups")
                validation_results['integrity_score'] -= len(duplicates) * 5
                validation_results['recommendations'].append("Run duplicate cleanup")
            
            # Find orphaned references
            orphaned = self.find_orphaned_references()
            validation_results['orphaned_references'] = orphaned
            
            if orphaned.get('invalid_job_ids'):
                validation_results['issues_found'].append(f"Found {len(orphaned['invalid_job_ids'])} jobs with invalid IDs")
                validation_results['integrity_score'] -= len(orphaned['invalid_job_ids']) * 10
            
            if orphaned.get('feedback_orphans'):
                validation_results['issues_found'].append(f"Found {len(orphaned['feedback_orphans'])} orphaned feedback references")
                validation_results['integrity_score'] -= len(orphaned['feedback_orphans']) * 3
            
            # Overall health assessment
            if validation_results['integrity_score'] >= 95:
                validation_results['recommendations'].append("Database integrity is excellent")
            elif validation_results['integrity_score'] >= 85:
                validation_results['recommendations'].append("Database integrity is good, minor cleanup recommended")
            else:
                validation_results['recommendations'].append("Database integrity issues detected, cleanup strongly recommended")
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error validating database integrity: {e}")
            return {'error': str(e)}


def run_integrity_check():
    """
    Standalone function to run integrity check and display results
    """
    print("🔍 Running Database Integrity Check...")
    
    checker = DatabaseIntegrityChecker()
    results = checker.validate_database_integrity()
    
    print(f"\n📊 Integrity Check Results:")
    print(f"  Total jobs: {results.get('total_jobs', 0)}")
    print(f"  Integrity score: {results.get('integrity_score', 0)}/100")
    
    if results.get('issues_found'):
        print(f"\n⚠️ Issues Found:")
        for issue in results['issues_found']:
            print(f"  - {issue}")
    
    if results.get('duplicate_groups'):
        print(f"\n🔄 Duplicate Groups:")
        for i, group in enumerate(results['duplicate_groups']):
            print(f"  Group {i+1}: {group['total_count']} similar jobs")
            print(f"    Base: {group['base_job']['job_id']} - {group['base_job']['title']}")
            for similar in group['similar_jobs']:
                print(f"    Similar: {similar['job_id']} - {similar['title']}")
    
    if results.get('recommendations'):
        print(f"\n💡 Recommendations:")
        for rec in results['recommendations']:
            print(f"  - {rec}")
    
    return results


def clean_duplicates_interactive():
    """
    Interactive duplicate cleanup
    """
    print("🧹 Interactive Duplicate Cleanup...")
    
    checker = DatabaseIntegrityChecker()
    duplicates = checker.find_duplicate_jobs()
    
    if not duplicates:
        print("✅ No duplicates found!")
        return
    
    print(f"Found {len(duplicates)} duplicate groups:")
    
    for i, group in enumerate(duplicates):
        print(f"\n--- Group {i+1} ---")
        print(f"Base job: {group['base_job']['job_id']} - {group['base_job']['title']}")
        for j, similar in enumerate(group['similar_jobs']):
            print(f"Similar {j+1}: {similar['job_id']} - {similar['title']}")
        
        response = input(f"Auto-resolve this group? (y/n/skip): ").lower()
        
        if response == 'y':
            result = checker.clean_duplicate_jobs([group], auto_resolve=True)
            print(f"✅ Resolved: removed {result['jobs_removed']} duplicate(s)")
        elif response == 'skip':
            continue
        else:
            print("⏭️ Skipped - manual review needed")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'clean':
        clean_duplicates_interactive()
    else:
        run_integrity_check()