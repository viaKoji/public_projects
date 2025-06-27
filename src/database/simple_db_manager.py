# database/simple_db_manager.py - UPDATED with Status Management
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

class SimpleJobDatabaseManager:
    """
    Simplified database manager with job status management
    Uses pure SQLite with Python's built-in sqlite3 module
    """
    
    def __init__(self, db_path: str = "data/jobs.db"):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Create database and tables
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary database tables with status management"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if table exists and get its structure
            cursor.execute("PRAGMA table_info(jobs)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            if not existing_columns:
                # Create new table with status fields
                cursor.execute('''
                    CREATE TABLE jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        company TEXT,
                        location TEXT,
                        description TEXT,
                        salary_min INTEGER,
                        salary_max INTEGER,
                        remote_type TEXT,
                        source TEXT,
                        url TEXT,
                        found_date TEXT,
                        ai_analysis TEXT,
                        compatibility_score REAL,
                        ai_analyzed BOOLEAN DEFAULT FALSE,
                        ai_analysis_date TEXT,
                        status TEXT DEFAULT 'new',
                        status_updated_date TEXT,
                        application_date TEXT,
                        rating INTEGER,
                        rating_notes TEXT,
                        rating_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                self.logger.info("Created new jobs table with status management fields")
            else:
                # Add missing columns to existing table
                required_columns = {
                    'found_date': 'TEXT',
                    'ai_analysis': 'TEXT',
                    'compatibility_score': 'REAL',
                    'ai_analyzed': 'BOOLEAN DEFAULT FALSE',
                    'ai_analysis_date': 'TEXT',
                    'status': 'TEXT DEFAULT "unrated"',  # Default to unrated for existing jobs
                    'status_updated_date': 'TEXT',
                    'application_date': 'TEXT',
                    'rating': 'INTEGER',
                    'rating_notes': 'TEXT',
                    'rating_date': 'TEXT',
                    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
                }
                
                for column, column_type in required_columns.items():
                    if column not in existing_columns:
                        try:
                            cursor.execute(f'ALTER TABLE jobs ADD COLUMN {column} {column_type}')
                            self.logger.info(f"Added column: {column}")
                        except sqlite3.OperationalError as e:
                            self.logger.warning(f"Could not add column {column}: {e}")
                
                self.logger.info("Updated existing jobs table with status management fields")
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_id ON jobs(job_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_company ON jobs(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON jobs(source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_analyzed ON jobs(ai_analyzed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_found_date ON jobs(found_date)')
            
            conn.commit()
    
    def add_job(self, job_data: Dict) -> bool:
        """
        Add a job to the database with status management
        
        Args:
            job_data: Dictionary containing job information
            
        Returns:
            True if job was added, False if it already exists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if job already exists
                cursor.execute('SELECT id FROM jobs WHERE job_id = ?', (job_data.get('job_id'),))
                if cursor.fetchone():
                    self.logger.debug(f"Job {job_data.get('job_id')} already exists")
                    return False
                
                # Determine initial status
                found_date = job_data.get('found_date', datetime.now().isoformat())
                initial_status = self._determine_initial_status(found_date)
                
                # Insert new job
                ai_analysis_json = json.dumps(job_data.get('ai_analysis', {}))
                
                cursor.execute('''
                    INSERT INTO jobs (
                        job_id, title, company, location, description,
                        salary_min, salary_max, remote_type, source, url,
                        found_date, ai_analysis, compatibility_score,
                        ai_analyzed, ai_analysis_date, status, status_updated_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_data.get('job_id'),
                    job_data.get('title'),
                    job_data.get('company'),
                    job_data.get('location'),
                    job_data.get('description'),
                    job_data.get('salary_min'),
                    job_data.get('salary_max'),
                    job_data.get('remote_type', 'unknown'),
                    job_data.get('source'),
                    job_data.get('url'),
                    found_date,
                    ai_analysis_json,
                    job_data.get('compatibility_score'),
                    job_data.get('ai_analyzed', False),
                    job_data.get('ai_analysis_date'),
                    initial_status,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                self.logger.info(f"Added job with status '{initial_status}': {job_data.get('title')} at {job_data.get('company')}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error adding job: {e}")
            return False
    
    def _determine_initial_status(self, found_date: str) -> str:
        """
        Determine initial status for a job based on when it was found
        
        Args:
            found_date: ISO format date string
            
        Returns:
            Initial status ('new' or 'unrated')
        """
        try:
            found_dt = datetime.fromisoformat(found_date.replace('Z', '+00:00'))
            now = datetime.now()
            
            # If found within last 24 hours, mark as 'new'
            if (now - found_dt).total_seconds() < 86400:  # 24 hours
                return 'new'
            else:
                return 'unrated'
        except (ValueError, TypeError):
            # If date parsing fails, default to 'unrated'
            return 'unrated'
    
    def get_jobs(self, limit: int = 100, source: str = None, status: str = None) -> List[Dict]:
        """
        Get jobs from database with status filtering
        
        Args:
            limit: Maximum number of jobs to return
            source: Filter by source (optional)
            status: Filter by status (optional)
            
        Returns:
            List of job dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                # Check which columns exist
                cursor.execute("PRAGMA table_info(jobs)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # Build column list based on what exists
                select_columns = []
                all_columns = [
                    'id', 'job_id', 'title', 'company', 'location', 'description',
                    'salary_min', 'salary_max', 'remote_type', 'source', 'url',
                    'found_date', 'ai_analysis', 'compatibility_score', 
                    'ai_analyzed', 'ai_analysis_date', 'status', 'status_updated_date',
                    'application_date', 'rating', 'rating_notes', 'rating_date', 'created_at'
                ]
                
                for col in all_columns:
                    if col in existing_columns:
                        select_columns.append(col)
                
                columns_str = ', '.join(select_columns)
                
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if source and source.lower() != 'all':
                    where_conditions.append('source = ?')
                    params.append(source)
                
                if status and status.lower() != 'all':
                    where_conditions.append('status = ?')
                    params.append(status)
                
                where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'
                
                # Determine order by column
                order_column = 'created_at' if 'created_at' in existing_columns else 'id'
                
                query = f'''
                    SELECT {columns_str} FROM jobs 
                    WHERE {where_clause}
                    ORDER BY {order_column} DESC 
                    LIMIT ?
                '''
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries and parse JSON fields
                jobs = []
                for row in rows:
                    job_dict = dict(row)
                    
                    # Parse AI analysis JSON if it exists
                    if job_dict.get('ai_analysis'):
                        try:
                            job_dict['ai_analysis'] = json.loads(job_dict['ai_analysis'])
                        except (json.JSONDecodeError, TypeError):
                            job_dict['ai_analysis'] = {}
                    else:
                        job_dict['ai_analysis'] = {}
                    
                    # Ensure all expected fields exist with defaults
                    defaults = {
                        'found_date': datetime.now().isoformat(),
                        'compatibility_score': None,
                        'remote_type': 'unknown',
                        'ai_analyzed': False,
                        'ai_analysis_date': None,
                        'status': 'unrated',
                        'status_updated_date': None,
                        'application_date': None,
                        'rating': None,
                        'rating_notes': None,
                        'rating_date': None
                    }
                    
                    for field, default_value in defaults.items():
                        if field not in job_dict:
                            job_dict[field] = default_value
                    
                    jobs.append(job_dict)
                
                return jobs
                
        except Exception as e:
            self.logger.error(f"Error getting jobs: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: str, rating: int = None, 
                         rating_notes: str = None) -> bool:
        """
        Update job status and rating
        
        Args:
            job_id: Job identifier
            status: New status
            rating: Job rating (1-5) if provided
            rating_notes: Notes about the rating
            
        Returns:
            True if updated successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update fields
                update_fields = ['status = ?', 'status_updated_date = ?']
                params = [status, datetime.now().isoformat()]
                
                if rating is not None:
                    update_fields.extend(['rating = ?', 'rating_date = ?'])
                    params.extend([rating, datetime.now().isoformat()])
                
                if rating_notes is not None:
                    update_fields.append('rating_notes = ?')
                    params.append(rating_notes)
                
                if status == 'applied':
                    update_fields.append('application_date = ?')
                    params.append(datetime.now().isoformat())
                
                params.append(job_id)  # For WHERE clause
                
                query = f'''
                    UPDATE jobs 
                    SET {', '.join(update_fields)}
                    WHERE job_id = ?
                '''
                
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Updated job {job_id} status to '{status}'")
                    return True
                else:
                    self.logger.warning(f"Job {job_id} not found for status update")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error updating job status: {e}")
            return False
    
    def update_job_analysis(self, job_id: str, ai_analysis: Dict, compatibility_score: float = None, 
                           ai_analyzed: bool = None, ai_analysis_date: str = None):
        """
        Update job with AI analysis and compatibility score
        
        Args:
            job_id: Job identifier
            ai_analysis: AI analysis dictionary
            compatibility_score: Compatibility score (optional)
            ai_analyzed: Whether the job has been analyzed by AI (optional)
            ai_analysis_date: When the AI analysis was performed (optional)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                ai_analysis_json = json.dumps(ai_analysis)
                
                # Build dynamic update query based on provided parameters
                update_fields = ['ai_analysis = ?']
                params = [ai_analysis_json]
                
                if compatibility_score is not None:
                    update_fields.append('compatibility_score = ?')
                    params.append(compatibility_score)
                
                if ai_analyzed is not None:
                    update_fields.append('ai_analyzed = ?')
                    params.append(ai_analyzed)
                
                if ai_analysis_date is not None:
                    update_fields.append('ai_analysis_date = ?')
                    params.append(ai_analysis_date)
                
                params.append(job_id)  # For WHERE clause
                
                query = f'''
                    UPDATE jobs 
                    SET {', '.join(update_fields)}
                    WHERE job_id = ?
                '''
                
                cursor.execute(query, params)
                conn.commit()
                self.logger.info(f"Updated analysis for job: {job_id}")
                
        except Exception as e:
            self.logger.error(f"Error updating job analysis: {e}")
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """
        Get a specific job by job_id
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job dictionary or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
                row = cursor.fetchone()
                
                if row:
                    job_dict = dict(row)
                    
                    # Parse AI analysis JSON
                    if job_dict.get('ai_analysis'):
                        try:
                            job_dict['ai_analysis'] = json.loads(job_dict['ai_analysis'])
                        except json.JSONDecodeError:
                            job_dict['ai_analysis'] = {}
                    
                    # Ensure status fields exist
                    if 'status' not in job_dict:
                        job_dict['status'] = 'unrated'
                    if 'ai_analyzed' not in job_dict:
                        job_dict['ai_analyzed'] = False
                    if 'ai_analysis_date' not in job_dict:
                        job_dict['ai_analysis_date'] = None
                    
                    return job_dict
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting job by ID: {e}")
            return None
    
    def auto_update_job_statuses(self):
        """
        Automatically update job statuses based on business rules
        - Move 'new' jobs older than 24h to 'unrated'
        - Move ANY rated job out of 'new' status to appropriate status
        - Set jobs with rating ≤3 to 'uninterested'
        - Set jobs with rating >3 to 'promising'
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update 'new' jobs older than 24 hours to 'unrated'
                twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
                
                cursor.execute('''
                    UPDATE jobs 
                    SET status = 'unrated', status_updated_date = ?
                    WHERE status = 'new' AND found_date < ?
                ''', (datetime.now().isoformat(), twenty_four_hours_ago))
                
                new_to_unrated = cursor.rowcount
                
                # NEW: Move ANY rated job out of 'new' status to appropriate status
                cursor.execute('''
                    UPDATE jobs 
                    SET status = CASE 
                        WHEN rating <= 3 THEN 'uninterested'
                        WHEN rating > 3 THEN 'promising'
                    END,
                    status_updated_date = ?
                    WHERE rating IS NOT NULL AND status = 'new'
                ''', (datetime.now().isoformat(),))
                
                rated_new_updated = cursor.rowcount
                
                # Update jobs with rating ≤3 to 'uninterested' (unless manually overridden recently)
                cursor.execute('''
                    UPDATE jobs 
                    SET status = 'uninterested', status_updated_date = ?
                    WHERE rating <= 3 AND status != 'uninterested'
                ''', (datetime.now().isoformat(),))
                
                rated_to_uninterested = cursor.rowcount
                
                # NEW: Update jobs with rating >3 to 'promising' (if not already applied)
                cursor.execute('''
                    UPDATE jobs 
                    SET status = 'promising', status_updated_date = ?
                    WHERE rating > 3 AND status NOT IN ('promising', 'applied')
                ''', (datetime.now().isoformat(),))
                
                rated_to_promising = cursor.rowcount
                
                conn.commit()
                
                total_updated = new_to_unrated + rated_new_updated + rated_to_uninterested + rated_to_promising
                if total_updated > 0:
                    self.logger.info(f"Auto-updated statuses: {new_to_unrated} new→unrated, {rated_new_updated} rated new→status, {rated_to_uninterested} rated→uninterested, {rated_to_promising} rated→promising")
                
                return total_updated
                
        except Exception as e:
            self.logger.error(f"Error auto-updating job statuses: {e}")
            return 0
    
    def get_stats(self) -> Dict:
        """
        Get database statistics including status breakdown
        
        Returns:
            Dictionary with database stats
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check which columns exist
                cursor.execute("PRAGMA table_info(jobs)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # Total jobs
                cursor.execute('SELECT COUNT(*) FROM jobs')
                total_jobs = cursor.fetchone()[0]
                
                # Jobs by source
                if 'source' in existing_columns:
                    cursor.execute('SELECT source, COUNT(*) FROM jobs GROUP BY source')
                    by_source = dict(cursor.fetchall())
                else:
                    by_source = {}
                
                # Jobs by status
                by_status = {}
                if 'status' in existing_columns:
                    cursor.execute('SELECT status, COUNT(*) FROM jobs GROUP BY status')
                    by_status = dict(cursor.fetchall())
                
                # Recent jobs (last 7 days)
                recent_jobs = 0
                if 'created_at' in existing_columns:
                    cursor.execute('''
                        SELECT COUNT(*) FROM jobs 
                        WHERE created_at >= date('now', '-7 days')
                    ''')
                    recent_jobs = cursor.fetchone()[0]
                
                # Jobs with AI analysis
                ai_analyzed = 0
                if 'ai_analyzed' in existing_columns:
                    cursor.execute('SELECT COUNT(*) FROM jobs WHERE ai_analyzed = 1')
                    ai_analyzed = cursor.fetchone()[0]
                elif 'ai_analysis' in existing_columns:
                    cursor.execute('''
                        SELECT COUNT(*) FROM jobs 
                        WHERE ai_analysis IS NOT NULL 
                        AND ai_analysis != '' 
                        AND ai_analysis != '{}'
                    ''')
                    ai_analyzed = cursor.fetchone()[0]
                
                # Jobs with ratings
                rated_jobs = 0
                if 'rating' in existing_columns:
                    cursor.execute('SELECT COUNT(*) FROM jobs WHERE rating IS NOT NULL')
                    rated_jobs = cursor.fetchone()[0]
                
                return {
                    'total_jobs': total_jobs,
                    'recent_jobs': recent_jobs,
                    'ai_analyzed': ai_analyzed,
                    'rated_jobs': rated_jobs,
                    'by_source': by_source,
                    'by_status': by_status
                }
                
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {
                'total_jobs': 0,
                'recent_jobs': 0,
                'ai_analyzed': 0,
                'rated_jobs': 0,
                'by_source': {},
                'by_status': {}
            }
    
    def search_jobs(self, keywords: List[str] = None, company: str = None, 
                   min_salary: int = None, status: str = None) -> List[Dict]:
        """
        Search jobs with filters including status
        
        Args:
            keywords: List of keywords to search in title/description
            company: Company name to filter by
            min_salary: Minimum salary filter
            status: Job status filter
            
        Returns:
            List of matching job dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Build query dynamically
                query = "SELECT * FROM jobs WHERE 1=1"
                params = []
                
                if keywords:
                    keyword_conditions = []
                    for keyword in keywords:
                        keyword_conditions.append("(title LIKE ? OR description LIKE ?)")
                        params.extend([f"%{keyword}%", f"%{keyword}%"])
                    query += " AND (" + " OR ".join(keyword_conditions) + ")"
                
                if company:
                    query += " AND company LIKE ?"
                    params.append(f"%{company}%")
                
                if min_salary:
                    query += " AND (salary_min >= ? OR salary_max >= ?)"
                    params.extend([min_salary, min_salary])
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY created_at DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                jobs = []
                for row in rows:
                    job_dict = dict(row)
                    
                    # Parse AI analysis JSON
                    if job_dict.get('ai_analysis'):
                        try:
                            job_dict['ai_analysis'] = json.loads(job_dict['ai_analysis'])
                        except json.JSONDecodeError:
                            job_dict['ai_analysis'] = {}
                    
                    jobs.append(job_dict)
                
                return jobs
                
        except Exception as e:
            self.logger.error(f"Error searching jobs: {e}")
            return []
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from database
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Deleted job: {job_id}")
                    return True
                else:
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error deleting job: {e}")
            return False


# Migration script for existing jobs
def migrate_existing_jobs_to_status_system():
    """
    Migration script to add status fields to existing jobs
    and import ratings from job_feedback.json
    """
    import os
    
    db_manager = SimpleJobDatabaseManager()
    
    # Step 1: Auto-update statuses (will handle new→unrated transitions)
    updated_count = db_manager.auto_update_job_statuses()
    print(f"✅ Auto-updated {updated_count} job statuses")
    
    # Step 2: Import ratings from job_feedback.json if it exists
    feedback_path = "data/job_feedback.json"
    if os.path.exists(feedback_path):
        try:
            with open(feedback_path, 'r') as f:
                feedback_data = json.load(f)
            
            imported_count = 0
            for feedback in feedback_data:
                job_id = feedback.get('job_id')
                rating = feedback.get('rating')
                notes = feedback.get('notes', '')
                
                if job_id and rating:
                    # Determine status based on rating
                    if rating <= 3:
                        status = 'uninterested'
                    else:
                        status = 'promising'
                    
                    success = db_manager.update_job_status(
                        job_id=job_id,
                        status=status,
                        rating=rating,
                        rating_notes=notes
                    )
                    
                    if success:
                        imported_count += 1
            
            print(f"✅ Imported {imported_count} ratings from job_feedback.json")
            
        except Exception as e:
            print(f"❌ Error importing feedback: {e}")
    
    # Step 3: Show final statistics
    stats = db_manager.get_stats()
    print(f"\n📊 Final Statistics:")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  By status: {stats['by_status']}")
    print(f"  Rated jobs: {stats['rated_jobs']}")


# Test function
def test_status_management():
    """Test the status management functionality"""
    import os
    
    # Use test database
    test_db_path = "data/test_status_jobs.db"
    
    # Remove test database if exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # Create database manager
    db_manager = SimpleJobDatabaseManager(test_db_path)
    
    # Test jobs with different dates
    test_jobs = [
        {
            'job_id': 'test_new_123',
            'title': 'Senior Product Manager',
            'company': 'Test Company',
            'location': 'Seattle, WA',
            'description': 'Test job description',
            'source': 'test',
            'url': 'https://example.com/job/123',
            'found_date': datetime.now().isoformat()  # New job
        },
        {
            'job_id': 'test_old_456',
            'title': 'Engineering Manager',
            'company': 'Old Company',
            'location': 'Remote',
            'description': 'Old job description',
            'source': 'test',
            'url': 'https://example.com/job/456',
            'found_date': (datetime.now() - timedelta(days=2)).isoformat()  # Old job
        }
    ]
    
    # Add test jobs
    for job in test_jobs:
        success = db_manager.add_job(job)
        print(f"Added job {job['job_id']}: {success}")
    
    # Test getting jobs by status
    new_jobs = db_manager.get_jobs(status='new')
    unrated_jobs = db_manager.get_jobs(status='unrated')
    
    print(f"New jobs: {len(new_jobs)}")
    print(f"Unrated jobs: {len(unrated_jobs)}")
    
    # Test rating a job
    if new_jobs:
        job_id = new_jobs[0]['job_id']
        success = db_manager.update_job_status(job_id, 'reviewed', rating=4, rating_notes='Good fit!')
        print(f"Rated job {job_id}: {success}")
    
    # Test auto-update
    updated = db_manager.auto_update_job_statuses()
    print(f"Auto-updated {updated} jobs")
    
    # Test stats
    stats = db_manager.get_stats()
    print(f"Stats: {stats}")
    
    # Clean up
    os.remove(test_db_path)
    print("✅ Test completed successfully")

if __name__ == "__main__":
    # Run migration script
    print("🔄 Running migration to add status management...")
    migrate_existing_jobs_to_status_system()
    
    # Run test
    print("\n🧪 Running status management test...")
    test_status_management()