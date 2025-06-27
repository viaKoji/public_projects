# src/database/db_manager.py
import sqlite3
import pandas as pd
from datetime import datetime
import logging
from typing import List, Dict, Optional

class JobDatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    description TEXT,
                    requirements TEXT,
                    job_type TEXT,  -- full-time, part-time, contract
                    remote_type TEXT,  -- remote, hybrid, onsite
                    source TEXT,  -- indeed, linkedin, etc.
                    url TEXT,
                    posted_date TEXT,
                    scraped_date TEXT,
                    ai_score REAL,  -- AI matching score (0-1)
                    user_feedback INTEGER,  -- User rating (1-5)
                    applied BOOLEAN DEFAULT FALSE,
                    status TEXT DEFAULT 'new'  -- new, reviewed, applied, rejected
                )
            ''')
            
            # Search history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_date TEXT,
                    keywords TEXT,
                    location TEXT,
                    jobs_found INTEGER,
                    new_jobs INTEGER
                )
            ''')
            
            # User feedback table for AI learning
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    feedback_score INTEGER,  -- 1-5 rating
                    feedback_notes TEXT,
                    feedback_date TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            ''')
            
            conn.commit()
            logging.info("Database initialized successfully")
    
    def add_job(self, job_data: Dict) -> bool:
        """Add a new job to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if job already exists
                cursor.execute("SELECT id FROM jobs WHERE job_id = ?", (job_data['job_id'],))
                if cursor.fetchone():
                    logging.info(f"Job {job_data['job_id']} already exists")
                    return False
                
                cursor.execute('''
                    INSERT INTO jobs (
                        job_id, title, company, location, salary_min, salary_max,
                        description, requirements, job_type, remote_type, source,
                        url, posted_date, scraped_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_data['job_id'],
                    job_data['title'],
                    job_data['company'],
                    job_data['location'],
                    job_data.get('salary_min'),
                    job_data.get('salary_max'),
                    job_data['description'],
                    job_data.get('requirements', ''),
                    job_data.get('job_type', ''),
                    job_data.get('remote_type', ''),
                    job_data['source'],
                    job_data['url'],
                    job_data.get('posted_date', ''),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                logging.info(f"Added new job: {job_data['title']} at {job_data['company']}")
                return True
                
        except Exception as e:
            logging.error(f"Error adding job: {e}")
            return False
    
    def get_jobs(self, limit: int = None, status: str = None) -> pd.DataFrame:
        """Retrieve jobs from database"""
        query = "SELECT * FROM jobs"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
            
        query += " ORDER BY scraped_date DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(query, conn, params=params)
    
    def update_job_score(self, job_id: str, ai_score: float):
        """Update AI matching score for a job"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET ai_score = ? WHERE job_id = ?",
                (ai_score, job_id)
            )
            conn.commit()
    
    def add_feedback(self, job_id: str, score: int, notes: str = ""):
        """Add user feedback for a job"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (job_id, feedback_score, feedback_notes, feedback_date)
                VALUES (?, ?, ?, ?)
            ''', (job_id, score, notes, datetime.now().isoformat()))
            
            # Also update the main jobs table
            cursor.execute(
                "UPDATE jobs SET user_feedback = ? WHERE job_id = ?",
                (score, job_id)
            )
            conn.commit()
    
    def get_new_jobs_count(self) -> int:
        """Get count of new jobs since last check"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'")
            return cursor.fetchone()[0]
    
    def mark_jobs_as_reviewed(self, job_ids: List[str]):
        """Mark jobs as reviewed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in job_ids])
            cursor.execute(
                f"UPDATE jobs SET status = 'reviewed' WHERE job_id IN ({placeholders})",
                job_ids
            )
            conn.commit()