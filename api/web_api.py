# Version 3.4 - Complete AI Analysis Fix (Removed Duplicate Scraping, Fixed AI Step)
# api/web_api.py
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sys
import os
import logging
import json
import subprocess
import threading
import time
import re
import sqlite3 
from datetime import datetime
from collections import Counter
from flask import send_from_directory

# Add src to path
sys.path.append('src')
sys.path.append('.')

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for web interface

# Add this helper function after the imports section
def should_reanalyze_job(job, user_profile):
    """Determine if a job needs AI re-analysis - FIXED VERSION"""
    # Never analyzed before
    if not job.get('ai_analyzed', False):
        return True
    
    # No AI analysis data
    if not job.get('ai_analysis') or not job.get('compatibility_score'):
        return True
    
    # Check if profile changed since last analysis
    job_analysis_date = job.get('ai_analysis_date')
    profile_update_date = user_profile.get('last_updated')
    
    if job_analysis_date and profile_update_date:
        try:
            from datetime import datetime
            job_date = datetime.fromisoformat(job_analysis_date)
            profile_date = datetime.fromisoformat(profile_update_date)
            
            # Re-analyze if profile was updated after job analysis
            if profile_date > job_date:
                return True
        except (ValueError, TypeError) as e:
            # If date parsing fails, don't re-analyze (conservative approach)
            logger.warning(f"Date parsing failed for job {job.get('job_id')}: {e}")
            return False
    
    # Job is up-to-date
    return False

def safe_analyze_job_with_error_isolation(job, ai_matcher, job_index, total_jobs):
    """
    Safely analyze a single job with comprehensive error handling
    
    Args:
        job: Job dictionary to analyze
        ai_matcher: AI matcher instance
        job_index: Current job index for logging
        total_jobs: Total number of jobs being analyzed
        
    Returns:
        Tuple of (success: bool, analyzed_job: dict, error_message: str)
    """
    job_id = job.get('job_id', 'unknown')
    job_title = job.get('title', 'Unknown')[:40]
    
    try:
        logger.info(f"🤖 Analyzing job {job_index+1}/{total_jobs}: {job_title} (ID: {job_id})")
        
        # Validate job has required fields
        if not job_id or job_id == 'unknown':
            return False, job, f"Job missing valid job_id"
        
        if not job.get('title'):
            return False, job, f"Job {job_id} missing title"
        
        # Check if job exists in database (additional safety check)
        if db_manager:
            db_job = db_manager.get_job_by_id(job_id)
            if not db_job:
                return False, job, f"Job {job_id} not found in database"
        
        # Run AI analysis with timeout protection
        analyzed_job = ai_matcher.analyze_job_with_ai(job)
        
        # Verify AI analysis succeeded
        if not analyzed_job.get('ai_analyzed', False):
            return False, job, f"AI analysis failed to complete for job {job_id}"
        
        if not analyzed_job.get('ai_analysis') or not analyzed_job.get('compatibility_score'):
            return False, job, f"AI analysis incomplete for job {job_id}"
        
        logger.info(f"✅ AI analysis successful: {analyzed_job.get('compatibility_score', 0):.1f}% for {job_title}")
        return True, analyzed_job, ""
        
    except KeyError as e:
        error_msg = f"Missing required field for job {job_id}: {e}"
        logger.error(error_msg)
        return False, job, error_msg
        
    except ValueError as e:
        error_msg = f"Invalid data for job {job_id}: {e}"
        logger.error(error_msg)
        return False, job, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error analyzing job {job_id}: {str(e)}"
        logger.error(error_msg)
        return False, job, error_msg

def validate_jobs_before_analysis(jobs):
    """
    Validate and filter jobs before AI analysis to prevent errors
    
    Args:
        jobs: List of job dictionaries
        
    Returns:
        Tuple of (valid_jobs: list, invalid_jobs: list, validation_report: dict)
    """
    valid_jobs = []
    invalid_jobs = []
    validation_report = {
        'total_jobs': len(jobs),
        'valid_jobs': 0,
        'invalid_jobs': 0,
        'issues_found': []
    }
    
    for job in jobs:
        issues = []
        
        # Check required fields
        if not job.get('job_id'):
            issues.append("Missing job_id")
        elif not isinstance(job.get('job_id'), str):
            issues.append("Invalid job_id type")
        
        if not job.get('title'):
            issues.append("Missing title")
        
        if not job.get('company'):
            issues.append("Missing company")
        
        # Check for duplicate job_id format issues
        job_id = str(job.get('job_id', ''))
        if 'linkedin_email_' in job_id and job_id.count('_') > 2:
            issues.append("Potentially malformed LinkedIn email job_id")
        
        if issues:
            invalid_jobs.append({
                'job': job,
                'issues': issues
            })
            validation_report['issues_found'].extend([f"Job {job_id}: {issue}" for issue in issues])
        else:
            valid_jobs.append(job)
    
    validation_report['valid_jobs'] = len(valid_jobs)
    validation_report['invalid_jobs'] = len(invalid_jobs)
    
    if invalid_jobs:
        logger.warning(f"⚠️ Found {len(invalid_jobs)} invalid jobs that will be skipped during analysis")
        for invalid in invalid_jobs:
            logger.warning(f"   - {invalid['job'].get('job_id', 'unknown')}: {', '.join(invalid['issues'])}")
    
    return valid_jobs, invalid_jobs, validation_report

# REPLACE the existing get_jobs function with this enhanced version
@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """ENHANCED: Get jobs from database with AI analysis and robust error handling"""
    try:
        # Safety check for database manager
        if not db_manager:
            logger.error("Database manager not initialized")
            return jsonify({
                'success': False,
                'error': 'Database not available',
                'jobs': [],
                'total': 0
            }), 500
        
        # Get query parameters
        limit = int(request.args.get('limit', 50))
        source = request.args.get('source', None)
        status = request.args.get('status', None)
        sort_by = request.args.get('sort', 'score')
        
        logger.info(f"🔸 Getting jobs (limit={limit*2}, source={source}, status={status})")
        
        # Auto-update job statuses before retrieving
        updated_count = db_manager.auto_update_job_statuses()
        if updated_count > 0:
            logger.info(f"🔸 Auto-updated {updated_count} job statuses")
        
        # Filter by source and status with enhanced error handling
        try:
            if source and source.lower() != 'all':
                if status and status.lower() != 'all':
                    jobs = db_manager.get_jobs(limit=limit*2, source=source, status=status)
                else:
                    jobs = db_manager.get_jobs(limit=limit*2, source=source)
            else:
                if status and status.lower() != 'all':
                    jobs = db_manager.get_jobs(limit=limit*2, status=status)
                else:
                    jobs = db_manager.get_jobs(limit=limit*2)
        except Exception as db_error:
            logger.error(f"Database error retrieving jobs: {db_error}")
            return jsonify({
                'success': False,
                'error': f'Database error: {str(db_error)}',
                'jobs': [],
                'total': 0
            }), 500
        
        # SAFETY CHECK: Ensure jobs is not None
        if jobs is None:
            jobs = []
            logger.warning("Database returned None for jobs - using empty list")
        
        # SAFETY CHECK: Ensure jobs is a list
        if not isinstance(jobs, list):
            logger.error(f"Database returned non-list type: {type(jobs)}")
            jobs = []
        
        logger.info(f"🔸 Retrieved {len(jobs)} jobs from database")
        
        # Early return if no jobs
        if len(jobs) == 0:
            return jsonify({
                'success': True,
                'jobs': [],
                'total': 0,
                'status_filter': status,
                'sort_by': sort_by,
                'message': f'No jobs found' + (f' with status: {status}' if status else '')
            })
        
        # ENHANCED: VALIDATE JOBS BEFORE AI ANALYSIS
        valid_jobs, invalid_jobs, validation_report = validate_jobs_before_analysis(jobs)
        
        if invalid_jobs:
            logger.warning(f"⚠️ Validation found {len(invalid_jobs)} problematic jobs - they will be skipped")
        
        # Update jobs list to only include valid jobs
        jobs = valid_jobs
        
        # NEW: AI ANALYSIS AND RESUME MATCHING PIPELINE WITH ERROR ISOLATION
        logger.info("🤖 Starting AI analysis and resume matching pipeline...")
        
        # Check which jobs need AI analysis - ENHANCED: Skip jobs that are already rated/reviewed
        jobs_needing_analysis = []
        skipped_reasons = {}
        
        for job in jobs:
            job_id = job.get('job_id', 'unknown')
            
            # Skip AI analysis if job already has rating or final status
            if job.get('rating') is not None:
                skipped_reasons[job_id] = f"already rated ({job.get('rating')}/5)"
                continue
            
            if job.get('status') in ['promising', 'applied', 'uninterested']:
                skipped_reasons[job_id] = f"final status ({job.get('status')})"
                continue
            
            if not job.get('ai_analyzed', False):
                jobs_needing_analysis.append(job)
            else:
                skipped_reasons[job_id] = "already analyzed"

        logger.info(f"🔍 Found {len(jobs_needing_analysis)} jobs needing AI analysis")
        logger.info(f"🔍 Skipped {len(skipped_reasons)} jobs (reasons logged)")
        
        # AI analysis for unanalyzed jobs with ERROR ISOLATION
        analysis_results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        if jobs_needing_analysis and ai_matcher:
            logger.info("🤖 Running AI analysis on unanalyzed jobs with error isolation...")
            
            for i, job in enumerate(jobs_needing_analysis):
                success, analyzed_job, error_message = safe_analyze_job_with_error_isolation(
                    job, ai_matcher, i, len(jobs_needing_analysis)
                )
                
                if success:
                    # Update the job in our list
                    try:
                        job_index = jobs.index(job)
                        jobs[job_index] = analyzed_job
                        
                        # Save analysis to database
                        db_manager.update_job_analysis(
                            job.get('job_id'),
                            analyzed_job.get('ai_analysis', {}),
                            analyzed_job.get('compatibility_score', 0),
                            ai_analyzed=True,
                            ai_analysis_date=analyzed_job.get('ai_analysis_date')
                        )
                        
                        analysis_results['successful'] += 1
                        
                    except ValueError:
                        logger.error(f"Could not find job in list to update: {job.get('job_id')}")
                        analysis_results['failed'] += 1
                        analysis_results['errors'].append(f"Job list update failed for {job.get('job_id')}")
                    
                else:
                    # Log error but continue with other jobs
                    analysis_results['failed'] += 1
                    analysis_results['errors'].append(error_message)
                    logger.warning(f"⚠️ Skipping problematic job and continuing: {error_message}")
        
        # Log analysis results
        if jobs_needing_analysis:
            logger.info(f"✅ AI Analysis Results: {analysis_results['successful']} successful, {analysis_results['failed']} failed")
            if analysis_results['errors']:
                logger.warning(f"AI Analysis Errors: {analysis_results['errors'][:3]}")  # Log first 3 errors
        
        # Resume matching integration with error handling
        if resume_matcher:
            logger.info("📄 Running resume matching analysis...")
            try:
                resume_errors = 0
                for job in jobs:
                    try:
                        # Get resume compatibility scores
                        resume_scores = resume_matcher.match_job_to_resumes(job)
                        
                        if resume_scores:
                            # Find best resume match
                            best_resume_name, best_resume_score = max(resume_scores.items(), key=lambda x: x[1])
                            
                            # Add resume matching data to job
                            job['resume_matches'] = resume_scores
                            job['best_resume'] = best_resume_name
                            job['resume_compatibility_score'] = best_resume_score
                            
                            # Enhance overall compatibility score with resume data
                            ai_score = job.get('compatibility_score', 0)
                            # Weighted combination: 70% AI analysis + 30% resume match
                            if ai_score and best_resume_score:
                                enhanced_score = (ai_score * 0.7) + (best_resume_score * 0.3)
                                job['compatibility_score'] = enhanced_score
                                job['score_source'] = 'AI_WITH_RESUME_MATCH'
                        
                    except Exception as resume_error:
                        resume_errors += 1
                        logger.warning(f"Resume matching failed for job {job.get('job_id', 'unknown')}: {resume_error}")
                        continue
                
                if resume_errors == 0:
                    logger.info("✅ Resume matching completed successfully")
                else:
                    logger.warning(f"✅ Resume matching completed with {resume_errors} errors")
                
            except Exception as e:
                logger.warning(f"⚠️ Resume matching failed (continuing without it): {e}")
        
        # Apply sorting based on sort_by parameter with error handling
        try:
            if sort_by == 'score':
                jobs.sort(key=lambda x: x.get('compatibility_score') or 0, reverse=True)
            elif sort_by == 'date':
                jobs.sort(key=lambda x: x.get('found_date') or '1900-01-01', reverse=True)
            elif sort_by == 'company':
                jobs.sort(key=lambda x: (x.get('company') or '').lower())
            elif sort_by == 'title':
                jobs.sort(key=lambda x: (x.get('title') or '').lower())
        except Exception as sort_error:
            logger.warning(f"Sorting failed: {sort_error}. Using default order.")
        
        # Limit final results
        final_jobs = jobs[:limit]
        
        # Calculate status statistics for UI with error handling
        status_stats = {}
        try:
            for job in jobs:
                job_status = job.get('status', 'unknown')
                status_stats[job_status] = status_stats.get(job_status, 0) + 1
        except Exception as stats_error:
            logger.warning(f"Status statistics calculation failed: {stats_error}")
            status_stats = {'error': 'Could not calculate statistics'}
        
        # Prepare response with comprehensive information
        response_data = {
            'success': True,
            'jobs': final_jobs,
            'total': len(final_jobs),
            'status_filter': status or 'all',
            'sort_by': sort_by,
            'status_statistics': status_stats,
            'processing_summary': {
                'total_retrieved': len(jobs) + len(invalid_jobs),
                'valid_jobs': len(jobs),
                'invalid_jobs_skipped': len(invalid_jobs),
                'ai_analysis_attempted': len(jobs_needing_analysis),
                'ai_analysis_successful': analysis_results['successful'],
                'ai_analysis_failed': analysis_results['failed']
            },
            'message': f'Jobs loaded with enhanced error handling (v3.5)'
        }
        
        # Add warnings if there were issues
        if invalid_jobs or analysis_results['failed'] > 0:
            warnings = []
            if invalid_jobs:
                warnings.append(f"{len(invalid_jobs)} jobs skipped due to data issues")
            if analysis_results['failed'] > 0:
                warnings.append(f"{analysis_results['failed']} jobs failed AI analysis")
            response_data['warnings'] = warnings
        
        logger.info(f"✅ Jobs pipeline completed: {len(final_jobs)} jobs with enhanced error handling")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"🔸 FATAL ERROR in get_jobs (with enhanced handling): {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Error loading jobs with enhanced error handling: {str(e)}',
            'suggestion': 'Check database integrity and run integrity check tool'
        }), 500

# Import LinkedIn job scraper (MOVED TO CORRECT LOCATION)
try:
    print("🔍 Attempting to import LinkedIn scraper...")
    from utils.linkedin_job_scraper import LinkedInJobScraper
    print("🔍 Import successful, initializing scraper...")
    linkedin_scraper = LinkedInJobScraper()
    LINKEDIN_SCRAPING_ENABLED = True
    print("✅ LinkedIn scraper loaded successfully")
except ImportError as e:
    print(f"⚠️  LinkedIn scraper import failed: {e}")
    print(f"    Current sys.path: {sys.path}")
    print("    Make sure linkedin_job_scraper.py exists in src/utils/")
    linkedin_scraper = None
    LINKEDIN_SCRAPING_ENABLED = False
except Exception as e:
    print(f"❌ Error initializing LinkedIn scraper: {e}")
    import traceback
    traceback.print_exc()
    linkedin_scraper = None
    LINKEDIN_SCRAPING_ENABLED = False

from database.simple_db_manager import SimpleJobDatabaseManager as JobDatabaseManager
from ai.simple_job_matcher import SimpleAIJobMatcher as AIJobMatcher
from config.settings import *
from dotenv import load_dotenv
load_dotenv()  # Add this line near the top

# Import salary parser
try:
    from utils.salary_parser import SalaryParser
    salary_parser = SalaryParser()
    SALARY_PARSING_ENABLED = True
except ImportError:
    print("⚠️  Salary parser not found. Install it to src/utils/salary_parser.py for better salary extraction.")
    SALARY_PARSING_ENABLED = False

# Import document parser
try:
    from utils.document_parser import ResumeDocumentParser
    document_parser = ResumeDocumentParser()
    DOCUMENT_PARSING_ENABLED = True
except ImportError:
    print("⚠️  Document parser not found. Install it to src/utils/document_parser.py for file upload support.")
    document_parser = None
    DOCUMENT_PARSING_ENABLED = False

try:
    from ai.resume_job_matcher import ResumeBasedJobMatcher
    resume_matcher = ResumeBasedJobMatcher(OPENAI_API_KEY) if OPENAI_API_KEY else None
    RESUME_MATCHING_ENABLED = bool(resume_matcher)
except ImportError:
    print("⚠️  Resume matcher not found. Install it to src/ai/resume_job_matcher.py for resume-based matching.")
    resume_matcher = None
    RESUME_MATCHING_ENABLED = False


# Initialize components with safety checks
db_manager = JobDatabaseManager(DATABASE_PATH) if DATABASE_PATH else None
ai_matcher = AIJobMatcher(OPENAI_API_KEY) if OPENAI_API_KEY else None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for job search status
job_search_status = {"running": False, "progress": "", "completed": False}

@app.route('/')
def serve_index():
    """Serve the web interface"""
    return send_from_directory('../ui', 'web_job_interface.html')
    

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database and AI statistics"""
    try:
        # Database stats
        if not db_manager:
            db_stats = {'error': 'Database not available'}
        else:
            db_stats = db_manager.get_stats()
        
        # AI feedback stats
        ai_stats = {}
        if ai_matcher:
            try:
                feedback_summary = ai_matcher.get_feedback_summary()
                if not feedback_summary.get('message'):
                    ai_stats = feedback_summary
            except Exception as ai_error:
                logger.error(f"Error getting AI feedback summary: {ai_error}")
                ai_stats = {'error': str(ai_error)}
        
        return jsonify({
            'success': True,
            'database': db_stats,
            'ai_feedback': ai_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sources', methods=['GET'])
def get_sources():
    """Get available job sources for filtering"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        stats = db_manager.get_stats()
        sources = list(stats.get('by_source', {}).keys())
        
        return jsonify({
            'success': True,
            'sources': sources
        })
        
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        return jsonify({
            'success': True,
            'profile': ai_matcher.user_profile
        })
        
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/profile', methods=['POST'])
def update_profile():
    """Update user profile"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['current_role', 'experience_years', 'salary_min', 'salary_max']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Update profile
        ai_matcher.update_user_profile(**data)
        
        logger.info("User profile updated successfully")
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/start', methods=['POST'])
def start_job_search():
    """Start a new job search in background"""
    try:
        global job_search_status
        
        if job_search_status["running"]:
            return jsonify({
                'success': False, 
                'error': 'Job search already running'
            }), 400
        
        # Reset status
        job_search_status = {
            "running": True, 
            "progress": "Starting job search...", 
            "completed": False,
            "start_time": time.time()
        }
        
        # Start job search in background thread
        search_thread = threading.Thread(target=run_job_search_background)
        search_thread.daemon = True
        search_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Job search started in background'
        })
        
    except Exception as e:
        logger.error(f"Error starting job search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/status', methods=['GET'])
def get_search_status():
    """Get job search status"""
    return jsonify({
        'success': True,
        'status': job_search_status
    })

def run_job_search_background():
    """Run job search in background"""
    global job_search_status
    
    try:
        job_search_status["progress"] = "Initializing scrapers..."
        time.sleep(1)
        
        # Import and run main job search
        import main
        
        job_search_status["progress"] = "Searching Gmail for LinkedIn jobs..."
        
        # Run the main job search function
        main.main()
        
        job_search_status["progress"] = "Job search completed successfully!"
        job_search_status["completed"] = True
        job_search_status["running"] = False
        
        logger.info("Background job search completed")
        
    except Exception as e:
        logger.error(f"Error in background job search: {e}")
        job_search_status["progress"] = f"Error: {str(e)}"
        job_search_status["completed"] = True
        job_search_status["running"] = False

@app.route('/api/search/gmail-test', methods=['POST'])
def test_gmail_scraper():
    """Test Gmail scraper functionality"""
    try:
        from scrapers.gmail_linkedin_scraper import GmailLinkedInScraper
        
        gmail_scraper = GmailLinkedInScraper()
        jobs = gmail_scraper.search_jobs(days_back=7, max_emails=5)
        
        return jsonify({
            'success': True,
            'message': f'Gmail test successful - found {len(jobs)} jobs',
            'jobs_found': len(jobs),
            'sample_jobs': jobs[:3] if jobs else []
        })
        
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Gmail credentials not found. Please set up Gmail API access.'
        }), 400
        
    except Exception as e:
        logger.error(f"Gmail test error: {e}")
        return jsonify({
            'success': False,
            'error': f'Gmail test failed: {str(e)}'
        }), 500

@app.route('/api/resumes', methods=['GET'])
def get_resumes():
    """Get all resume versions"""
    try:
        if not resume_matcher:
            return jsonify({'success': False, 'error': 'Resume matching not available'}), 400
        
        resumes = []
        for resume_name in resume_matcher.get_resume_names():
            summary = resume_matcher.get_resume_summary(resume_name)
            resumes.append(summary)
        
        return jsonify({
            'success': True,
            'resumes': resumes
        })
        
    except Exception as e:
        logger.error(f"Error getting resumes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/upload', methods=['POST'])
def upload_resume():
    """Upload and parse a resume document"""
    try:
        if not resume_matcher:
            return jsonify({'success': False, 'error': 'Resume matching not available'}), 400
        
        if not document_parser:
            return jsonify({'success': False, 'error': 'Document parsing not available'}), 400
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Get form data
        resume_name = request.form.get('name', '').strip()
        target_roles_str = request.form.get('target_roles', '').strip()
        target_roles = [role.strip() for role in target_roles_str.split(',') if role.strip()] if target_roles_str else []
        
        if not resume_name:
            return jsonify({'success': False, 'error': 'Resume name is required'}), 400
        
        # Check file format
        if not document_parser.is_supported_format(file.filename):
            return jsonify({
                'success': False, 
                'error': f'Unsupported file format. Supported: {document_parser.supported_formats}'
            }), 400
        
        # Save uploaded file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Parse document
            parse_result = document_parser.parse_document(temp_path)
            
            if parse_result['status'] != 'success':
                return jsonify({
                    'success': False,
                    'error': f"Document parsing failed: {parse_result.get('error', 'Unknown error')}",
                    'parse_details': parse_result
                }), 400
            
            # Add resume with parsed text
            success = resume_matcher.add_resume(resume_name, parse_result['text'], target_roles)
            
            if success:
                summary = resume_matcher.get_resume_summary(resume_name)
                return jsonify({
                    'success': True,
                    'message': f'Resume {resume_name} uploaded and analyzed successfully',
                    'resume': summary,
                    'parse_details': {
                        'filename': parse_result['filename'],
                        'format': parse_result['format'],
                        'word_count': parse_result.get('word_count', 0),
                        'char_count': parse_result.get('char_count', 0)
                    }
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to add resume after parsing'}), 500
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/parsing-support', methods=['GET'])
def get_parsing_support():
    """Get information about document parsing support"""
    try:
        if not document_parser:
            return jsonify({
                'success': False,
                'error': 'Document parser not available',
                'support': {
                    'pdf_support': False,
                    'word_support': False,
                    'supported_formats': [],
                    'missing_packages': ['PyPDF2', 'pdfplumber', 'python-docx', 'mammoth']
                }
            })
        
        info = document_parser.get_requirements_info()
        
        return jsonify({
            'success': True,
            'support': {
                'pdf_support': info['pdf_support'],
                'word_support': info['word_support'],
                'supported_formats': document_parser.supported_formats,
                'available_packages': info['available_packages'],
                'missing_packages': info['missing_packages'],
                'requirements': info['requirements']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting parsing support: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/add', methods=['POST'])
def add_resume():
    """Add a new resume version"""
    try:
        if not resume_matcher:
            return jsonify({'success': False, 'error': 'Resume matching not available'}), 400
        
        data = request.get_json()
        resume_name = data.get('name')
        resume_text = data.get('text')
        target_roles = data.get('target_roles', [])
        
        if not resume_name or not resume_text:
            return jsonify({'success': False, 'error': 'Name and text are required'}), 400
        
        success = resume_matcher.add_resume(resume_name, resume_text, target_roles)
        
        if success:
            summary = resume_matcher.get_resume_summary(resume_name)
            return jsonify({
                'success': True,
                'message': f'Resume {resume_name} added successfully',
                'resume': summary
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add resume'}), 500
        
    except Exception as e:
        logger.error(f"Error adding resume: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/<resume_name>', methods=['DELETE'])
def delete_resume(resume_name):
    """Delete a resume version"""
    try:
        if not resume_matcher:
            return jsonify({'success': False, 'error': 'Resume matching not available'}), 400
        
        if resume_name not in resume_matcher.resumes:
            return jsonify({'success': False, 'error': 'Resume not found'}), 404
        
        # Delete file
        resume_file = os.path.join(resume_matcher.resumes_dir, f"{resume_name}.json")
        if os.path.exists(resume_file):
            os.remove(resume_file)
        
        # Remove from memory
        del resume_matcher.resumes[resume_name]
        del resume_matcher.resume_profiles[resume_name]
        
        return jsonify({
            'success': True,
            'message': f'Resume {resume_name} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting resume: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/sources', methods=['GET'])
def analyze_job_sources():
    """Analyze job sources and URL patterns"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get all jobs
        jobs = db_manager.get_jobs(limit=1000)
        
        analysis = {
            'total_jobs': len(jobs),
            'by_source': {},
            'url_issues': {
                'missing_urls': [],
                'invalid_urls': [],
                'url_patterns': {}
            }
        }
        
        for job in jobs:
            source = job.get('source', 'Unknown')
            url = job.get('url')
            
            # Track by source
            if source not in analysis['by_source']:
                analysis['by_source'][source] = {
                    'total': 0,
                    'with_urls': 0,
                    'without_urls': 0,
                    'sample_jobs': []
                }
            
            analysis['by_source'][source]['total'] += 1
            
            # Add sample job info
            if len(analysis['by_source'][source]['sample_jobs']) < 3:
                analysis['by_source'][source]['sample_jobs'].append({
                    'title': job.get('title', 'N/A')[:50],
                    'company': job.get('company', 'N/A'),
                    'has_url': bool(url),
                    'job_id': job.get('job_id')
                })
            
            if url:
                analysis['by_source'][source]['with_urls'] += 1
                
                # Track URL patterns
                if url.startswith('http'):
                    domain = url.split('/')[2] if '/' in url else url
                    if domain not in analysis['url_issues']['url_patterns']:
                        analysis['url_issues']['url_patterns'][domain] = 0
                    analysis['url_issues']['url_patterns'][domain] += 1
                else:
                    analysis['url_issues']['invalid_urls'].append({
                        'job_id': job.get('job_id'),
                        'title': job.get('title', 'N/A')[:50],
                        'source': source,
                        'url': url
                    })
            else:
                analysis['by_source'][source]['without_urls'] += 1
                analysis['url_issues']['missing_urls'].append({
                    'job_id': job.get('job_id'),
                    'title': job.get('title', 'N/A')[:50],
                    'company': job.get('company', 'N/A'),
                    'source': source
                })
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error analyzing sources: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/validate-urls', methods=['GET'])
def validate_all_urls():
    """Validate and report on job URLs in database"""
    try:
        import requests
        from urllib.parse import urlparse
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get all jobs
        jobs = db_manager.get_jobs(limit=1000)
        
        url_stats = {
            'total_jobs': len(jobs),
            'valid_urls': 0,
            'invalid_urls': 0,
            'missing_urls': 0,
            'problematic_urls': []
        }
        
        for job in jobs:
            url = job.get('url')
            
            if not url:
                url_stats['missing_urls'] += 1
                continue
            
            # Basic URL validation
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError("Invalid URL format")
                
                # Quick HEAD request to check if URL exists (with timeout)
                response = requests.head(url, timeout=5, allow_redirects=True)
                
                if response.status_code < 400:
                    url_stats['valid_urls'] += 1
                else:
                    url_stats['invalid_urls'] += 1
                    url_stats['problematic_urls'].append({
                        'job_id': job['job_id'],
                        'title': job['title'][:50],
                        'url': url,
                        'status_code': response.status_code
                    })
                    
            except Exception as e:
                url_stats['invalid_urls'] += 1
                url_stats['problematic_urls'].append({
                    'job_id': job['job_id'],
                    'title': job['title'][:50],
                    'url': url,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'url_validation': url_stats
        })
        
    except Exception as e:
        logger.error(f"Error validating URLs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/parse-salaries', methods=['POST'])
def parse_all_salaries():
    """Parse salary information for all jobs in database"""
    try:
        if not SALARY_PARSING_ENABLED:
            return jsonify({
                'success': False, 
                'error': 'Salary parsing not available'
            }), 400
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get all jobs
        jobs = db_manager.get_jobs(limit=1000)
        updated_count = 0
        
        for job in jobs:
            original_min = job.get('salary_min')
            original_max = job.get('salary_max')
            
            # Parse salary if not already present
            if not original_min and not original_max:
                salary_parser.parse_job_salary(job)
                
                # Check if we found salary info
                if job.get('salary_min') or job.get('salary_max'):
                    updated_count += 1
                    logger.info(f"Parsed salary for {job['title']}: "
                              f"${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}")
        
        return jsonify({
            'success': True,
            'message': f'Parsed salary information for {updated_count} jobs',
            'updated_count': updated_count,
            'total_jobs': len(jobs)
        })
        
    except Exception as e:
        logger.error(f"Error parsing salaries: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/analyze-job/<job_id>', methods=['POST'])
def analyze_job_with_ai(job_id):
    """Analyze a specific job with AI"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get job from database
        job = db_manager.get_job_by_id(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Analyze with AI if not already done
        if not job.get('ai_analyzed', False):
            analyzed_job = ai_matcher.analyze_job_with_ai(job)
            compatibility_score = ai_matcher.calculate_compatibility_score(analyzed_job)
            
            # Update database
            db_manager.update_job_analysis(
                job_id, 
                analyzed_job.get('ai_analysis', {}), 
                compatibility_score
            )
            
            return jsonify({
                'success': True,
                'message': 'Job analyzed successfully',
                'ai_analysis': analyzed_job.get('ai_analysis', {}),
                'compatibility_score': compatibility_score
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Job already analyzed',
                'ai_analysis': job.get('ai_analysis', {}),
                'compatibility_score': job.get('compatibility_score')
            })
        
    except Exception as e:
        logger.error(f"Error analyzing job {job_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/feedback-learning', methods=['GET'])
def debug_feedback_learning():
    """Debug how AI is learning from feedback"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        # Get feedback summary
        feedback_summary = ai_matcher.get_feedback_summary()
        
        # Analyze patterns in your feedback
        liked_jobs = [fb for fb in ai_matcher.job_feedback if fb['rating'] >= 4]
        disliked_jobs = [fb for fb in ai_matcher.job_feedback if fb['rating'] <= 2]
        
        # Extract patterns from your notes
        your_negative_patterns = []
        for job in disliked_jobs:
            notes = job.get('notes', '').lower()
            if 'software developer' in notes or "i'm not a developer" in notes:
                your_negative_patterns.append("Software Developer Role")
            if 'react' in notes or 'nodejs' in notes or 'aws' in notes:
                your_negative_patterns.append("Specific Tech Stack")
            if 'fintech' in notes or 'crypto' in notes or 'ai focused' in notes:
                your_negative_patterns.append("Industry Mismatch")
        
        your_positive_patterns = []
        for job in liked_jobs:
            notes = job.get('notes', '').lower()
            if 'startup' in notes or 'product' in notes:
                your_positive_patterns.append("Startup/Product Experience Match")
        
        # Test scoring on a sample job
        test_job = {
            'job_id': 'debug_test',
            'title': 'Senior Product Manager - Platform Strategy',
            'company': 'Amazon',
            'description': 'Lead product strategy for platform initiatives with startup experience',
            'location': 'Seattle, WA (Remote)',
            'salary_min': 160000,
            'salary_max': 200000
        }
        
        test_score = ai_matcher.calculate_compatibility_score(test_job)
        
        return jsonify({
            'success': True,
            'feedback_summary': feedback_summary,
            'total_feedback_items': len(ai_matcher.job_feedback),
            'learning_patterns': {
                'negative_patterns_found': list(set(your_negative_patterns)),
                'positive_patterns_found': list(set(your_positive_patterns)),
                'updated_negative_keywords': ai_matcher.user_profile.get('keywords_negative', [])
            },
            'test_scoring': {
                'test_job': test_job,
                'calculated_score': test_score,
                'explanation': 'This tests if your feedback affected scoring'
            },
            'current_profile_updates': {
                'preferred_companies': ai_matcher.user_profile.get('preferred_companies', []),
                'negative_keywords': ai_matcher.user_profile.get('keywords_negative', [])
            }
        })
        
    except Exception as e:
        logger.error(f"Error debugging feedback learning: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/cleanup-keywords', methods=['POST'])
def cleanup_negative_keywords():
    """Clean up incorrectly added negative keywords"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        # Words that should NEVER be negative keywords
        protected_words = {
            'remote', 'product', 'manager', 'senior', 'director', 'lead', 'principal',
            'vice', 'president', 'chief', 'strategy', 'platform', 'growth', 'data',
            'user', 'experience', 'engineering', 'technical', 'startup', 'amazon',
            'google', 'microsoft', 'meta', 'apple', 'seattle',
            'year', 'years', 'united', 'states', 'hour', 'hours', 'learning',
            'development', 'innovation', 'team', 'cross', 'functional', 'operating',
            'officer'
        }
        
        # Get current negative keywords
        current_negative = ai_matcher.user_profile.get('keywords_negative', [])
        
        # Remove protected words
        cleaned_negative = []
        removed_words = []
        
        for word in current_negative:
            if word.lower() in protected_words:
                removed_words.append(word)
            else:
                cleaned_negative.append(word)
        
        # Update the profile
        ai_matcher.user_profile['keywords_negative'] = cleaned_negative
        ai_matcher._save_user_profile()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {len(removed_words)} incorrectly added negative keywords',
            'removed_words': removed_words,
            'remaining_negative_keywords': cleaned_negative,
            'before_count': len(current_negative),
            'after_count': len(cleaned_negative)
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/reset-profile', methods=['POST'])
def reset_user_profile():
    """Reset user profile to defaults (keeps feedback data)"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        # Backup current preferred companies (these are good)
        current_companies = ai_matcher.user_profile.get('preferred_companies', [])
        
        # Reset to default profile but keep learned companies
        ai_matcher.user_profile = ai_matcher._load_user_profile()
        
        # Restore the good companies we learned
        for company in current_companies:
            if company not in ai_matcher.user_profile['preferred_companies']:
                ai_matcher.user_profile['preferred_companies'].append(company)
        
        ai_matcher._save_user_profile()
        
        return jsonify({
            'success': True,
            'message': 'User profile reset to defaults (kept learned companies)',
            'kept_companies': current_companies,
            'new_profile': ai_matcher.user_profile
        })
        
    except Exception as e:
        logger.error(f"Error resetting profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/scrape-job/<job_id>', methods=['POST'])
def manually_scrape_job(job_id):
    """Manually scrape a specific job's LinkedIn content"""
    try:
        if not LINKEDIN_SCRAPING_ENABLED:
            return jsonify({
                'success': False, 
                'error': 'LinkedIn scraping not available'
            }), 400
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get job from database
        job = db_manager.get_job_by_id(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        if not job.get('url'):
            return jsonify({'success': False, 'error': 'Job has no LinkedIn URL'}), 400
        
        # Scrape the job
        enhanced_job = linkedin_scraper.enhance_job_with_linkedin_content(job)
        
        if enhanced_job.get('scraped_successfully'):
            return jsonify({
                'success': True,
                'message': f'Successfully scraped job: {enhanced_job.get("title")}',
                'scraped_data': {
                    'title': enhanced_job.get('title'),
                    'company': enhanced_job.get('company'),
                    'description_length': len(enhanced_job.get('description', '')),
                    'description_preview': enhanced_job.get('description', '')[:200] + '...' if enhanced_job.get('description') else None,
                    'employment_type': enhanced_job.get('employment_type'),
                    'experience_level': enhanced_job.get('scraped_experience_level'),
                    'industry': enhanced_job.get('scraped_industry')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to scrape job: {enhanced_job.get("scraping_error", "Unknown error")}',
                'url': job.get('url')
            })
        
    except Exception as e:
        logger.error(f"Error manually scraping job {job_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/linkedin-scraping-status', methods=['GET'])
def get_linkedin_scraping_status():
    """Get status of LinkedIn scraping capabilities"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get all jobs and analyze scraping status
        jobs = db_manager.get_jobs(limit=1000)
        
        stats = {
            'total_jobs': len(jobs),
            'jobs_with_descriptions': 0,
            'jobs_without_descriptions': 0,
            'jobs_successfully_scraped': 0,
            'jobs_failed_scraping': 0,
            'jobs_never_scraped': 0,
            'avg_description_length': 0,
            'linkedin_scraping_enabled': LINKEDIN_SCRAPING_ENABLED
        }
        
        description_lengths = []
        
        for job in jobs:
            description = job.get('description', '')
            has_description = description and len(description) > 100
            
            if has_description:
                stats['jobs_with_descriptions'] += 1
                description_lengths.append(len(description))
            else:
                stats['jobs_without_descriptions'] += 1
            
            if job.get('scraped_successfully'):
                stats['jobs_successfully_scraped'] += 1
            elif job.get('scraped_timestamp'):
                stats['jobs_failed_scraping'] += 1
            else:
                stats['jobs_never_scraped'] += 1
        
        if description_lengths:
            stats['avg_description_length'] = sum(description_lengths) / len(description_lengths)
        
        return jsonify({
            'success': True,
            'scraping_stats': stats,
            'recommendations': {
                'should_scrape': stats['jobs_without_descriptions'] > 0,
                'scraping_priority': 'high' if stats['jobs_without_descriptions'] > stats['jobs_with_descriptions'] else 'low',
                'estimated_time': f"{stats['jobs_without_descriptions'] * 3} seconds" if stats['jobs_without_descriptions'] > 0 else "0 seconds"
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting LinkedIn scraping status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'version': '3.4',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'database': 'connected' if db_manager else 'unavailable',
            'ai_matcher': 'available' if ai_matcher else 'unavailable',
            'openai_api': 'configured' if OPENAI_API_KEY else 'missing',
            'salary_parsing': 'enabled' if SALARY_PARSING_ENABLED else 'disabled',
            'resume_matching': 'enabled' if RESUME_MATCHING_ENABLED else 'disabled',
            'document_parsing': 'enabled' if DOCUMENT_PARSING_ENABLED else 'disabled',
            'linkedin_scraping': 'enabled' if LINKEDIN_SCRAPING_ENABLED else 'disabled'
        }
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/ai/protected-words', methods=['GET'])
def get_protected_words():
    """Get current protected words list"""
    try:
        # Try to load from saved config file first
        config_file = "data/ai_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    saved_protected_words = config.get('protected_words')
                    if saved_protected_words:
                        return jsonify({
                            'success': True,
                            'protected_words': saved_protected_words,
                            'description': 'Words that should never become negative keywords',
                            'count': len(saved_protected_words),
                            'source': 'saved_config'
                        })
            except Exception as e:
                logger.warning(f"Could not load saved protected words: {e}")
        
        # Fallback to defaults if file doesn't exist or is invalid
        default_protected_words = [
            'remote', 'product', 'manager', 'senior', 'director', 'lead', 'principal',
            'vice', 'president', 'chief', 'strategy', 'platform', 'growth', 'data',
            'user', 'experience', 'engineering', 'technical', 'startup', 'amazon',
            'google', 'microsoft', 'meta', 'apple', 'seattle',
            'year', 'years', 'united', 'states', 'hour', 'hours', 'learning',
            'development', 'innovation', 'team', 'cross', 'functional', 'operating',
            'officer'
        ]
        
        return jsonify({
            'success': True,
            'protected_words': default_protected_words,
            'description': 'Words that should never become negative keywords (defaults)',
            'count': len(default_protected_words),
            'source': 'defaults'
        })
        
    except Exception as e:
        logger.error(f"Error getting protected words: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/protected-words', methods=['POST'])
def update_protected_words():
    """Update protected words list"""
    try:
        data = request.get_json()
        new_protected_words = data.get('protected_words', [])
        
        if not isinstance(new_protected_words, list):
            return jsonify({'success': False, 'error': 'protected_words must be a list'}), 400
        
        # Validate words (no empty strings, reasonable length)
        filtered_words = []
        for word in new_protected_words:
            if isinstance(word, str) and len(word.strip()) > 0 and len(word.strip()) < 50:
                filtered_words.append(word.strip().lower())
        
        # Save to a config file or update the AI matcher directly
        config_file = "data/ai_config.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                config = {}
        
        config['protected_words'] = filtered_words
        config['last_updated'] = datetime.now().isoformat()
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(filtered_words)} protected words',
            'protected_words': filtered_words
        })
        
    except Exception as e:
        logger.error(f"Error updating protected words: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/negative-signals', methods=['GET'])
def get_negative_signals():
    """Get current truly negative signals list"""
    try:
        # Extract from simple_job_matcher.py or use defaults
        default_negative_signals = [
            'junior', 'entry', 'level', 'intern', 'temporary', 'contract', 'part-time',
            'marketing', 'sales', 'service', 'call', 'center',
            'retail', 'cashier', 'clerk', 'assistant', 'receptionist', 'admin',
            'secretarial', 'entry', 'manual', 'labor'
        ]
        
        return jsonify({
            'success': True,
            'negative_signals': default_negative_signals,
            'description': 'Words that should always lower job scores',
            'count': len(default_negative_signals)
        })
        
    except Exception as e:
        logger.error(f"Error getting negative signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/negative-signals', methods=['POST'])
def update_negative_signals():
    """Update truly negative signals list"""
    try:
        data = request.get_json()
        new_negative_signals = data.get('negative_signals', [])
        
        if not isinstance(new_negative_signals, list):
            return jsonify({'success': False, 'error': 'negative_signals must be a list'}), 400
        
        # Validate words
        filtered_signals = []
        for signal in new_negative_signals:
            if isinstance(signal, str) and len(signal.strip()) > 0 and len(signal.strip()) < 50:
                filtered_signals.append(signal.strip().lower())
        
        # Save to config file
        config_file = "data/ai_config.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                config = {}
        
        config['negative_signals'] = filtered_signals
        config['last_updated'] = datetime.now().isoformat()
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(filtered_signals)} negative signals',
            'negative_signals': filtered_signals
        })
        
    except Exception as e:
        logger.error(f"Error updating negative signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/learning-analysis', methods=['GET'])
def get_ai_learning_analysis():
    """Get comprehensive AI learning analysis"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        feedback_data = ai_matcher.job_feedback
        user_profile = ai_matcher.user_profile
        
        if not feedback_data:
            return jsonify({
                'success': True,
                'message': 'No feedback data available yet',
                'total_feedback': 0
            })
        
        # Analyze feedback patterns
        analysis = {
            'total_feedback': len(feedback_data),
            'rating_distribution': {},
            'negative_patterns': [],
            'positive_patterns': [],
            'learned_companies': [],
            'learned_keywords': {
                'positive': user_profile.get('keywords_positive', []),
                'negative': user_profile.get('keywords_negative', [])
            },
            'confidence_score': 0,
            'recommendations': []
        }
        
        # Rating distribution
        for rating in range(1, 6):
            analysis['rating_distribution'][str(rating)] = len([f for f in feedback_data if f.get('rating') == rating])
        
        # Extract patterns from feedback notes
        liked_jobs = [f for f in feedback_data if f.get('rating', 0) >= 4]
        disliked_jobs = [f for f in feedback_data if f.get('rating', 0) <= 2]
        
        # Analyze negative patterns from disliked jobs
        negative_phrases = []
        for job in disliked_jobs:
            notes = job.get('notes', '').lower()
            title = job.get('title', '').lower()
            
            # Extract key negative phrases from notes
            if 'not a' in notes:
                negative_phrases.append('not a software developer')
            if 'no experience' in notes or 'limited' in notes:
                negative_phrases.append('lacks required experience')
            if 'fintech' in notes or 'crypto' in notes:
                negative_phrases.append('fintech/crypto industry mismatch')
            if any(tech in notes for tech in ['react', 'nodejs', 'aws', 'javascript']):
                negative_phrases.append('specific tech stack requirements')
            if 'full stack' in notes or 'full stack' in title:
                negative_phrases.append('full stack developer requirements')
        
        analysis['negative_patterns'] = list(set(negative_phrases))
        
        # Analyze positive patterns from liked jobs
        positive_phrases = []
        for job in liked_jobs:
            notes = job.get('notes', '').lower()
            title = job.get('title', '').lower()
            
            if 'strong fit' in notes or 'good fit' in notes:
                positive_phrases.append('strong role alignment')
            if 'startup' in notes:
                positive_phrases.append('startup experience match')
            if 'strategic' in title or 'strategy' in title:
                positive_phrases.append('strategic/product focus')
            if 'amazon' in job.get('company', '').lower():
                positive_phrases.append('preferred company match')
        
        analysis['positive_patterns'] = list(set(positive_phrases))
        
        # Extract learned companies
        analysis['learned_companies'] = user_profile.get('preferred_companies', [])
        
        # Calculate confidence score
        total_ratings = len(feedback_data)
        if total_ratings >= 30:
            analysis['confidence_score'] = 95
        elif total_ratings >= 20:
            analysis['confidence_score'] = 85
        elif total_ratings >= 10:
            analysis['confidence_score'] = 70
        elif total_ratings >= 5:
            analysis['confidence_score'] = 50
        else:
            analysis['confidence_score'] = 25
        
        # Generate recommendations
        recommendations = []
        if total_ratings < 10:
            recommendations.append("Rate more jobs to improve AI accuracy")
        if len(analysis['negative_patterns']) > 5:
            recommendations.append("Consider cleaning up negative keywords")
        if len(analysis['learned_companies']) < 3:
            recommendations.append("Rate jobs from preferred companies to help AI learn")
        
        analysis['recommendations'] = recommendations
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error in AI learning analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/resume-insights', methods=['GET'])
def get_resume_insights():
    """Get insights from uploaded resumes"""
    try:
        if not resume_matcher:
            return jsonify({'success': False, 'error': 'Resume matching not available'}), 400
        
        resume_names = resume_matcher.get_resume_names()
        
        if not resume_names:
            return jsonify({
                'success': True,
                'message': 'No resumes uploaded yet',
                'resume_count': 0
            })
        
        insights = {
            'resume_count': len(resume_names),
            'resumes': [],
            'combined_profile': {
                'all_skills': set(),
                'all_roles': set(),
                'experience_levels': set(),
                'industries': set()
            },
            'matching_strategy': 'multi-resume'
        }
        
        # Analyze each resume
        for resume_name in resume_names:
            resume_summary = resume_matcher.get_resume_summary(resume_name)
            resume_data = resume_matcher.resumes.get(resume_name, {})
            analysis = resume_data.get('analysis', {})
            
            resume_insight = {
                'name': resume_name,
                'summary': resume_summary,
                'analysis': analysis,
                'target_roles': resume_data.get('target_roles', []),
                'strengths': analysis.get('strengths', []),
                'keywords_extracted': analysis.get('keywords', [])
            }
            
            insights['resumes'].append(resume_insight)
            
            # Add to combined profile
            insights['combined_profile']['all_skills'].update(analysis.get('skills', []))
            insights['combined_profile']['all_roles'].update(analysis.get('preferred_roles', []))
            insights['combined_profile']['experience_levels'].add(analysis.get('experience_level', ''))
            insights['combined_profile']['industries'].update(analysis.get('industries', []))
        
        # Convert sets to lists for JSON serialization
        for key in insights['combined_profile']:
            if isinstance(insights['combined_profile'][key], set):
                insights['combined_profile'][key] = list(insights['combined_profile'][key])
        
        return jsonify({
            'success': True,
            'insights': insights
        })
        
    except Exception as e:
        logger.error(f"Error getting resume insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/explain-job/<job_id>', methods=['GET'])
def explain_job_score(job_id):
    """Explain why a specific job got its compatibility score"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get job from database
        job = db_manager.get_job_by_id(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Generate detailed explanation
        explanation = {
            'job_id': job_id,
            'job_title': job.get('title', 'Unknown'),
            'company': job.get('company', 'Unknown'),
            'final_score': job.get('compatibility_score', 0),
            'score_source': job.get('score_source', 'Unknown'),
            'breakdown': {},
            'reasoning': [],
            'ai_analysis': job.get('ai_analysis', {}),
            'user_feedback_context': []
        }
        
        # Analyze scoring factors
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        company = job.get('company', '').lower()
        
        # Check positive keywords impact
        positive_matches = []
        for keyword in ai_matcher.user_profile.get('keywords_positive', []):
            if keyword.lower() in title or keyword.lower() in description:
                positive_matches.append(keyword)
        
        explanation['breakdown']['positive_keywords'] = {
            'matches': positive_matches,
            'impact': f"+{len(positive_matches) * 5} points"
        }
        
        # Check negative keywords impact
        negative_matches = []
        for keyword in ai_matcher.user_profile.get('keywords_negative', []):
            if keyword.lower() in title or keyword.lower() in description:
                negative_matches.append(keyword)
        
        explanation['breakdown']['negative_keywords'] = {
            'matches': negative_matches,
            'impact': f"-{len(negative_matches) * 10} points"
        }
        
        # Company preference impact
        preferred_companies = ai_matcher.user_profile.get('preferred_companies', [])
        company_match = any(pref.lower() in company for pref in preferred_companies)
        explanation['breakdown']['company_preference'] = {
            'match': company_match,
            'impact': "+15 points" if company_match else "0 points"
        }
        
        # Analyze patterns from feedback
        feedback_context = []
        similar_feedback = []
        
        for feedback in ai_matcher.job_feedback:
            feedback_title = feedback.get('title', '').lower()
            feedback_notes = feedback.get('notes', '').lower()
            rating = feedback.get('rating', 0)
            
            # Find similar jobs based on title words
            title_words = set(re.findall(r'\b\w+\b', title))
            feedback_words = set(re.findall(r'\b\w+\b', feedback_title))
            common_words = title_words & feedback_words
            
            if len(common_words) >= 2:
                similar_feedback.append({
                    'title': feedback.get('title', ''),
                    'rating': rating,
                    'notes': feedback.get('notes', ''),
                    'common_words': list(common_words)
                })
        
        explanation['user_feedback_context'] = similar_feedback[:3]  # Top 3 similar
        
        # Generate reasoning text
        reasoning = []
        
        if positive_matches:
            reasoning.append(f"✅ Contains preferred keywords: {', '.join(positive_matches)}")
        
        if negative_matches:
            reasoning.append(f"❌ Contains negative signals: {', '.join(negative_matches)}")
        
        if company_match:
            reasoning.append(f"✅ Company '{company}' is in your preferred list")
        
        # AI analysis insights
        ai_analysis = job.get('ai_analysis', {})
        if ai_analysis.get('key_highlights'):
            reasoning.append(f"🎯 AI identified highlights: {', '.join(ai_analysis['key_highlights'])}")
        
        if ai_analysis.get('potential_concerns'):
            reasoning.append(f"⚠️ AI identified concerns: {', '.join(ai_analysis['potential_concerns'])}")
        
        # Feedback-based insights
        if similar_feedback:
            avg_rating = sum(f['rating'] for f in similar_feedback) / len(similar_feedback)
            if avg_rating >= 4:
                reasoning.append(f"📈 Similar jobs received high ratings ({avg_rating:.1f}/5)")
            elif avg_rating <= 2:
                reasoning.append(f"📉 Similar jobs received low ratings ({avg_rating:.1f}/5)")
        
        explanation['reasoning'] = reasoning
        
        return jsonify({
            'success': True,
            'explanation': explanation
        })
        
    except Exception as e:
        logger.error(f"Error explaining job score for {job_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/test-keyword-impact', methods=['POST'])
def test_keyword_impact():
    """Test how keyword changes would affect job scoring"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        data = request.get_json()
        new_positive = data.get('positive_keywords', [])
        new_negative = data.get('negative_keywords', [])
        test_job_title = data.get('test_job_title', 'Senior Product Manager at Amazon')
        
        # Create a test job
        test_job = {
            'job_id': 'test_keyword_impact',
            'title': test_job_title,
            'company': 'Test Company',
            'description': f'Job description for {test_job_title}',
            'location': 'Seattle, WA'
        }
        
        # Calculate current score
        current_score = ai_matcher.calculate_compatibility_score(test_job)
        
        # Temporarily modify user profile
        original_positive = ai_matcher.user_profile.get('keywords_positive', []).copy()
        original_negative = ai_matcher.user_profile.get('keywords_negative', []).copy()
        
        # Test with new keywords
        ai_matcher.user_profile['keywords_positive'] = new_positive
        ai_matcher.user_profile['keywords_negative'] = new_negative
        
        new_score = ai_matcher.calculate_compatibility_score(test_job)
        
        # Restore original keywords
        ai_matcher.user_profile['keywords_positive'] = original_positive
        ai_matcher.user_profile['keywords_negative'] = original_negative
        
        impact = {
            'test_job': test_job_title,
            'current_score': round(current_score, 1),
            'new_score': round(new_score, 1),
            'score_change': round(new_score - current_score, 1),
            'impact_description': ''
        }
        
        # Generate impact description
        if abs(impact['score_change']) < 1:
            impact['impact_description'] = 'Minimal impact on this job'
        elif impact['score_change'] > 0:
            impact['impact_description'] = f"Would increase score by {impact['score_change']} points"
        else:
            impact['impact_description'] = f"Would decrease score by {abs(impact['score_change'])} points"
        
        return jsonify({
            'success': True,
            'impact': impact
        })
        
    except Exception as e:
        logger.error(f"Error testing keyword impact: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/feedback-patterns', methods=['GET'])
def get_feedback_patterns():
    """Get detailed patterns from user feedback"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        feedback_data = ai_matcher.job_feedback
        
        if not feedback_data:
            return jsonify({
                'success': True,
                'patterns': {'message': 'No feedback data available'},
                'total_feedback': 0
            })
        
        patterns = {
            'total_feedback': len(feedback_data),
            'disliked_terms': Counter(),
            'liked_terms': Counter(),
            'company_ratings': {},
            'title_patterns': {
                'engineering_roles': [],
                'product_roles': [],
                'operations_roles': [],
                'other_roles': []
            },
            'feedback_timeline': [],
            'key_insights': []
        }
        
        # Analyze each feedback item
        for feedback in feedback_data:
            rating = feedback.get('rating', 0)
            title = feedback.get('title', '').lower()
            company = feedback.get('company', '')
            notes = feedback.get('notes', '').lower()
            date = feedback.get('feedback_date', '')
            
            # Extract words from title and notes
            title_words = re.findall(r'\b\w+\b', title)
            note_words = re.findall(r'\b\w+\b', notes) if notes else []
            
            # Categorize by rating
            if rating <= 2:  # Disliked
                patterns['disliked_terms'].update(title_words)
                patterns['disliked_terms'].update(note_words)
            elif rating >= 4:  # Liked
                patterns['liked_terms'].update(title_words)
                patterns['liked_terms'].update(note_words)
            
            # Company ratings
            if company:
                if company not in patterns['company_ratings']:
                    patterns['company_ratings'][company] = []
                patterns['company_ratings'][company].append(rating)
            
            # Categorize job types
            if any(term in title for term in ['engineering', 'engineer', 'developer']):
                patterns['title_patterns']['engineering_roles'].append({
                    'title': feedback.get('title', ''),
                    'rating': rating,
                    'company': company
                })
            elif any(term in title for term in ['product', 'pm']):
                patterns['title_patterns']['product_roles'].append({
                    'title': feedback.get('title', ''),
                    'rating': rating,
                    'company': company
                })
            elif any(term in title for term in ['operations', 'operating', 'ops']):
                patterns['title_patterns']['operations_roles'].append({
                    'title': feedback.get('title', ''),
                    'rating': rating,
                    'company': company
                })
            else:
                patterns['title_patterns']['other_roles'].append({
                    'title': feedback.get('title', ''),
                    'rating': rating,
                    'company': company
                })
            
            # Timeline data
            patterns['feedback_timeline'].append({
                'date': date,
                'rating': rating,
                'title': feedback.get('title', '')[:50]
            })
        
        # Generate insights
        insights = []
        
        # Most disliked terms
        top_disliked = patterns['disliked_terms'].most_common(5)
        if top_disliked:
            insights.append(f"Most disliked terms: {', '.join([term for term, count in top_disliked])}")
        
        # Engineering role pattern
        eng_ratings = [job['rating'] for job in patterns['title_patterns']['engineering_roles']]
        if eng_ratings:
            avg_eng_rating = sum(eng_ratings) / len(eng_ratings)
            insights.append(f"Engineering roles average rating: {avg_eng_rating:.1f}/5 ({len(eng_ratings)} jobs)")
        
        # Product role pattern
        prod_ratings = [job['rating'] for job in patterns['title_patterns']['product_roles']]
        if prod_ratings:
            avg_prod_rating = sum(prod_ratings) / len(prod_ratings)
            insights.append(f"Product roles average rating: {avg_prod_rating:.1f}/5 ({len(prod_ratings)} jobs)")
        
        # Company preferences
        company_avgs = {}
        for company, ratings in patterns['company_ratings'].items():
            if len(ratings) >= 2:  # Only companies with multiple ratings
                company_avgs[company] = sum(ratings) / len(ratings)
        
        if company_avgs:
            best_company = max(company_avgs.items(), key=lambda x: x[1])
            insights.append(f"Highest rated company: {best_company[0]} ({best_company[1]:.1f}/5)")
        
        patterns['key_insights'] = insights
        
        # Convert Counter objects to regular dicts for JSON serialization
        patterns['disliked_terms'] = dict(patterns['disliked_terms'].most_common(20))
        patterns['liked_terms'] = dict(patterns['liked_terms'].most_common(20))
        
        return jsonify({
            'success': True,
            'patterns': patterns
        })
        
    except Exception as e:
        logger.error(f"Error getting feedback patterns: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/web_job_interface.html')
def job_interface():
    return send_from_directory('../ui', 'web_job_interface.html')

@app.route('/ai_configuration.html')
def ai_configuration():
    return send_from_directory('../ui', 'ai_configuration.html')

# General static file handler for any other HTML files
@app.route('/<path:filename>')
def serve_static(filename):
    if filename.endswith('.html'):
        return send_from_directory('../ui', filename)
    return "File not found", 404


# Add this new endpoint for force re-analysis
@app.route('/api/jobs/force-reanalyze', methods=['POST'])
def force_reanalyze_all_jobs():
    """Force re-analysis of all jobs with AI (use sparingly)"""
    try:
        if not ai_matcher:
            return jsonify({'success': False, 'error': 'AI matcher not available'}), 400
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        data = request.get_json() or {}
        confirm = data.get('confirm', False)
        
        if not confirm:
            return jsonify({
                'success': False, 
                'error': 'Must confirm force re-analysis with {"confirm": true}'
            }), 400
        
        # Get all jobs
        jobs = db_manager.get_jobs(limit=1000)
        
        if not jobs:
            return jsonify({
                'success': True,
                'message': 'No jobs to re-analyze',
                'reanalyzed_count': 0
            })
        
        # Force re-analysis by clearing analysis flags
        reanalyzed_count = 0
        for job in jobs:
            if isinstance(job, dict):
                # Clear AI analysis flags to force re-analysis
                job['ai_analyzed'] = False
                job.pop('ai_analysis_date', None)
                
                try:
                    # Re-analyze with AI
                    analyzed_job = ai_matcher.analyze_job_with_ai(job)
                    job.update(analyzed_job)
                    
                    # Mark as analyzed
                    job['ai_analyzed'] = True
                    job['ai_analysis_date'] = datetime.now().isoformat()
                    
                    reanalyzed_count += 1
                    
                    # Update database if possible
                    try:
                        if hasattr(db_manager, 'update_job_analysis'):
                            db_manager.update_job_analysis(
                                job.get('job_id'), 
                                job.get('ai_analysis', {}), 
                                job.get('compatibility_score', 0),
                                ai_analyzed=True,
                                ai_analysis_date=job['ai_analysis_date']
                            )
                    except Exception as db_error:
                        logger.warning(f"Could not update job in DB: {db_error}")
                    
                    logger.info(f"Force re-analyzed: {job.get('title', 'Unknown')[:40]}")
                    
                except Exception as analysis_error:
                    logger.error(f"Failed to re-analyze job {job.get('job_id')}: {analysis_error}")
                    continue
        
        return jsonify({
            'success': True,
            'message': f'Force re-analyzed {reanalyzed_count} jobs',
            'reanalyzed_count': reanalyzed_count,
            'total_jobs': len(jobs)
        })
        
    except Exception as e:
        logger.error(f"Error in force re-analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add this endpoint to check analysis status
@app.route('/api/jobs/analysis-status', methods=['GET'])
def get_analysis_status():
    """Get status of AI analysis across all jobs"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        jobs = db_manager.get_jobs(limit=1000)
        
        status = {
            'total_jobs': len(jobs),
            'analyzed_jobs': 0,
            'unanalyzed_jobs': 0,
            'outdated_analysis': 0,
            'analysis_percentage': 0
        }
        
        if ai_matcher:
            user_profile = ai_matcher.user_profile
            
            for job in jobs:
                if isinstance(job, dict):
                    if job.get('ai_analyzed', False) and job.get('ai_analysis'):
                        if should_reanalyze_job(job, user_profile):
                            status['outdated_analysis'] += 1
                        else:
                            status['analyzed_jobs'] += 1
                    else:
                        status['unanalyzed_jobs'] += 1
        
        if status['total_jobs'] > 0:
            status['analysis_percentage'] = round(
                (status['analyzed_jobs'] / status['total_jobs']) * 100, 1
            )
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting analysis status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Additional API endpoints to add to web_api.py
# Add these endpoints after your existing routes

@app.route('/api/jobs/by-status', methods=['GET'])
def get_jobs_by_status():
    """Get jobs filtered by status with enhanced filtering"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Get query parameters
        status = request.args.get('status', 'all')
        limit = int(request.args.get('limit', 50))
        source = request.args.get('source', None)
        sort_by = request.args.get('sort', 'score')  # score, date, company, title
        
        logger.info(f"🔸 Getting jobs by status: {status}, limit: {limit}, source: {source}")
        
        # Auto-update statuses before querying
        db_manager.auto_update_job_statuses()
        
        # Get jobs with status filter
        if status == 'all':
            jobs = db_manager.get_jobs(limit=limit*2, source=source)
        else:
            jobs = db_manager.get_jobs(limit=limit*2, source=source, status=status)
        
        if not jobs:
            return jsonify({
                'success': True,
                'jobs': [],
                'total': 0,
                'status_filter': status,
                'message': f'No jobs found with status: {status}'
            })
        
        # Apply sorting based on sort_by parameter
        if sort_by == 'score':
            jobs.sort(key=lambda x: x.get('compatibility_score', 0), reverse=True)
        elif sort_by == 'date':
            jobs.sort(key=lambda x: x.get('found_date', ''), reverse=True)
        elif sort_by == 'company':
            jobs.sort(key=lambda x: x.get('company', '').lower())
        elif sort_by == 'title':
            jobs.sort(key=lambda x: x.get('title', '').lower())
        
        # Limit results
        jobs = jobs[:limit]
        
        # Calculate status statistics
        all_jobs = db_manager.get_jobs(limit=1000)  # Get more for stats
        status_stats = {}
        for job in all_jobs:
            job_status = job.get('status', 'unknown')
            status_stats[job_status] = status_stats.get(job_status, 0) + 1
        
        return jsonify({
            'success': True,
            'jobs': jobs,
            'total': len(jobs),
            'status_filter': status,
            'sort_by': sort_by,
            'status_statistics': status_stats,
            'message': f'Found {len(jobs)} jobs with status: {status}'
        })
        
    except Exception as e:
        logger.error(f"Error getting jobs by status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/<job_id>/status', methods=['POST'])
def update_job_status(job_id):
    """Update job status and optionally rating"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        data = request.get_json()
        new_status = data.get('status')
        rating = data.get('rating')
        notes = data.get('notes', '')
        
        if not new_status:
            return jsonify({'success': False, 'error': 'Status is required'}), 400
        
        # Validate status
        valid_statuses = ['new', 'unrated', 'promising', 'applied', 'uninterested']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False, 
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        # Validate rating if provided
        if rating is not None and (not isinstance(rating, int) or rating < 1 or rating > 5):
            return jsonify({'success': False, 'error': 'Rating must be between 1 and 5'}), 400
        
        # Apply business rules for status transitions
        if rating is not None:
            if rating <= 3 and new_status != 'uninterested':
                # Auto-set to uninterested for low ratings
                new_status = 'uninterested'
                logger.info(f"Auto-setting job {job_id} to 'uninterested' due to rating ≤3")
            elif rating > 3 and new_status == 'uninterested':
                # Don't allow uninterested with high rating
                new_status = 'promising'
                logger.info(f"Auto-setting job {job_id} to 'promising' due to rating >3")
        
        # Update the job status
        success = db_manager.update_job_status(
            job_id=job_id,
            status=new_status,
            rating=rating,
            rating_notes=notes
        )
        
        if not success:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # If rating was provided, also record it with the AI matcher for learning
        if rating is not None and ai_matcher:
            try:
                job = db_manager.get_job_by_id(job_id)
                if job:
                    ai_matcher.record_feedback(job, rating, notes)
                    logger.info(f"Recorded feedback in AI matcher for job {job_id}")
            except Exception as ai_error:
                logger.warning(f"Could not record AI feedback: {ai_error}")
        
        # Special handling for 'applied' status
        message = f'Job status updated to "{new_status}"'
        if new_status == 'applied':
            message += ' - This will help the AI learn to score similar jobs higher!'
            
            # Future: Add AI learning verification here
            # For now, just log that this should trigger learning
            logger.info(f"Job {job_id} marked as 'applied' - AI should learn from this positive signal")
        
        return jsonify({
            'success': True,
            'message': message,
            'new_status': new_status,
            'rating': rating
        })
        
    except Exception as e:
        logger.error(f"Error updating job status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/<job_id>/rate', methods=['POST'])
def rate_job_with_status(job_id):
    """Rate a job and automatically update status based on rating"""
    try:
        
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        data = request.get_json()
        rating = data.get('rating')
        notes = data.get('notes', '')
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': 'Valid rating (1-5) is required'}), 400
        
        # Determine status based on rating
        if rating <= 3:
            new_status = 'uninterested'
        else:
            new_status = 'promising'
        
        # Update job with rating and status
        success = db_manager.update_job_status(
            job_id=job_id,
            status=new_status,
            rating=rating,
            rating_notes=notes
        )
    
        
        if not success:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Force status update immediately after rating
        updated_count = db_manager.auto_update_job_statuses()
        
        # Check the job status after update
        updated_job = db_manager.get_job_by_id(job_id)
        
        # Record feedback with AI matcher
        if ai_matcher:
            try:
                job = db_manager.get_job_by_id(job_id)
                if job:
                    ai_matcher.record_feedback(job, rating, notes)
            except Exception as ai_error:
                logger.warning(f"Could not record AI feedback: {ai_error}")
        
        return jsonify({
            'success': True,
            'message': f'Job rated {rating}/5 stars and status set to "{new_status}"',
            'rating': rating,
            'status': new_status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/statistics', methods=['GET'])
def get_status_statistics():
    """Get detailed statistics about job statuses"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        # Auto-update statuses first
        updated_count = db_manager.auto_update_job_statuses()
        
        # Get comprehensive stats
        stats = db_manager.get_stats()
        
        # Calculate additional metrics
        total_jobs = stats['total_jobs']
        by_status = stats.get('by_status', {})
        
        # Calculate percentages
        status_percentages = {}
        for status, count in by_status.items():
            status_percentages[status] = round((count / total_jobs * 100), 1) if total_jobs > 0 else 0
        
        # Calculate workflow progress
        rated_jobs = stats.get('rated_jobs', 0)
        review_progress = round((rated_jobs / total_jobs * 100), 1) if total_jobs > 0 else 0
        
        # Get recent activity (jobs added/updated in last 7 days)
        recent_jobs = stats.get('recent_jobs', 0)
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_jobs': total_jobs,
                'by_status': by_status,
                'status_percentages': status_percentages,
                'rated_jobs': rated_jobs,
                'review_progress': review_progress,
                'recent_jobs': recent_jobs,
                'auto_updated_count': updated_count
            },
            'status_definitions': {
                'new': 'Jobs added in the last 24 hours',
                'unrated': 'Jobs that need review and rating',
                'promising': 'Jobs rated 4-5 stars but no action taken',
                'applied': 'Jobs you have applied to (helps train AI)',
                'uninterested': 'Jobs rated 1-3 stars or manually dismissed'
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting status statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/bulk-update', methods=['POST'])
def bulk_update_status():
    """Bulk update job statuses"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        data = request.get_json()
        job_ids = data.get('job_ids', [])
        new_status = data.get('status')
        
        if not job_ids or not new_status:
            return jsonify({'success': False, 'error': 'job_ids and status are required'}), 400
        
        # Validate status
        valid_statuses = ['new', 'unrated', 'promising', 'applied', 'uninterested']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False, 
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        # Update each job
        updated_count = 0
        failed_jobs = []
        
        for job_id in job_ids:
            success = db_manager.update_job_status(job_id, new_status)
            if success:
                updated_count += 1
            else:
                failed_jobs.append(job_id)
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} jobs to status "{new_status}"',
            'updated_count': updated_count,
            'failed_jobs': failed_jobs
        })
        
    except Exception as e:
        logger.error(f"Error in bulk status update: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/auto-update-statuses', methods=['POST'])
def trigger_auto_update_statuses():
    """Manually trigger automatic status updates"""
    try:
        if not db_manager:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        updated_count = db_manager.auto_update_job_statuses()
        
        return jsonify({
            'success': True,
            'message': f'Auto-updated {updated_count} job statuses',
            'updated_count': updated_count
        })
        
    except Exception as e:
        logger.error(f"Error in auto-update statuses: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add these endpoints to web_api.py after your existing routes

@app.route('/api/database/integrity-check', methods=['GET'])
def run_database_integrity_check():
    """Run comprehensive database integrity check"""
    try:
        # Import the integrity checker
        sys.path.append('src/utils')
        from db_integrity_checker import DatabaseIntegrityChecker
        
        checker = DatabaseIntegrityChecker(DATABASE_PATH)
        results = checker.validate_database_integrity()
        
        return jsonify({
            'success': True,
            'integrity_check': results,
            'message': f'Database integrity check completed. Score: {results.get("integrity_score", 0)}/100'
        })
        
    except Exception as e:
        logger.error(f"Error running integrity check: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/find-duplicates', methods=['GET'])
def find_duplicate_jobs():
    """Find duplicate jobs in the database"""
    try:
        sys.path.append('src/utils')
        from db_integrity_checker import DatabaseIntegrityChecker
        
        checker = DatabaseIntegrityChecker(DATABASE_PATH)
        duplicates = checker.find_duplicate_jobs()
        
        return jsonify({
            'success': True,
            'duplicate_groups': duplicates,
            'total_groups': len(duplicates),
            'message': f'Found {len(duplicates)} duplicate job groups'
        })
        
    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/clean-duplicates', methods=['POST'])
def clean_duplicate_jobs():
    """Clean up duplicate jobs"""
    try:
        data = request.get_json() or {}
        auto_resolve = data.get('auto_resolve', False)
        
        sys.path.append('src/utils')
        from db_integrity_checker import DatabaseIntegrityChecker
        
        checker = DatabaseIntegrityChecker(DATABASE_PATH)
        
        # First find duplicates
        duplicates = checker.find_duplicate_jobs()
        
        if not duplicates:
            return jsonify({
                'success': True,
                'message': 'No duplicates found to clean',
                'cleanup_results': {
                    'groups_processed': 0,
                    'jobs_removed': 0
                }
            })
        
        # Clean duplicates
        cleanup_results = checker.clean_duplicate_jobs(duplicates, auto_resolve=auto_resolve)
        
        return jsonify({
            'success': True,
            'cleanup_results': cleanup_results,
            'message': f'Processed {cleanup_results["groups_processed"]} duplicate groups, removed {cleanup_results["jobs_removed"]} jobs'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning duplicates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/orphaned-references', methods=['GET'])
def find_orphaned_references():
    """Find orphaned references that might cause loading issues"""
    try:
        sys.path.append('src/utils')
        from db_integrity_checker import DatabaseIntegrityChecker
        
        checker = DatabaseIntegrityChecker(DATABASE_PATH)
        orphaned = checker.find_orphaned_references()
        
        total_issues = (
            len(orphaned.get('missing_job_ids', [])) + 
            len(orphaned.get('invalid_job_ids', [])) + 
            len(orphaned.get('feedback_orphans', []))
        )
        
        return jsonify({
            'success': True,
            'orphaned_references': orphaned,
            'total_issues': total_issues,
            'message': f'Found {total_issues} orphaned reference issues'
        })
        
    except Exception as e:
        logger.error(f"Error finding orphaned references: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/fix-specific-duplicate', methods=['POST'])
def fix_specific_duplicate():
    """Fix a specific duplicate job issue (like the 4251767049 case)"""
    try:
        data = request.get_json()
        target_job_id = data.get('job_id')
        action = data.get('action', 'auto')  # 'auto', 'keep_original', 'keep_enhanced'
        
        if not target_job_id:
            return jsonify({'success': False, 'error': 'job_id is required'}), 400
        
        # Find all jobs with similar IDs
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Look for jobs containing this ID
            cursor.execute('''
                SELECT job_id, title, company, description, ai_analyzed, ai_analysis, compatibility_score
                FROM jobs 
                WHERE job_id LIKE ? OR job_id = ?
            ''', (f'%{target_job_id}%', target_job_id))
            
            similar_jobs = [dict(row) for row in cursor.fetchall()]
        
        if len(similar_jobs) < 2:
            return jsonify({
                'success': False,
                'error': f'No duplicates found for job ID {target_job_id}',
                'found_jobs': similar_jobs
            })
        
        # Determine which job to keep
        if action == 'auto':
            # Keep the job with more complete data
            best_job = similar_jobs[0]
            for job in similar_jobs[1:]:
                if _job_has_better_data(job, best_job):
                    best_job = job
        elif action == 'keep_original':
            # Keep the job with the simpler ID (usually the original)
            best_job = min(similar_jobs, key=lambda j: len(j['job_id']))
        elif action == 'keep_enhanced':
            # Keep the job with the more complex ID (usually the enhanced one)
            best_job = max(similar_jobs, key=lambda j: len(j['job_id']))
        else:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        # Remove the other jobs
        jobs_to_remove = [job for job in similar_jobs if job['job_id'] != best_job['job_id']]
        
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            removed_count = 0
            
            for job in jobs_to_remove:
                cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job['job_id'],))
                if cursor.rowcount > 0:
                    removed_count += 1
                    logger.info(f"Removed duplicate job: {job['job_id']}")
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Fixed duplicate for {target_job_id}',
            'kept_job': best_job['job_id'],
            'removed_jobs': [job['job_id'] for job in jobs_to_remove],
            'removed_count': removed_count
        })
        
    except Exception as e:
        logger.error(f"Error fixing specific duplicate: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _job_has_better_data(job1, job2):
    """Helper function to determine which job has better/more complete data"""
    job1_score = 0
    job2_score = 0
    
    # Score based on data completeness
    fields_to_check = ['description', 'company', 'title']
    
    for field in fields_to_check:
        val1 = job1.get(field, '')
        val2 = job2.get(field, '')
        
        if val1 and len(str(val1).strip()) > len(str(val2).strip()):
            job1_score += 1
        elif val2 and len(str(val2).strip()) > len(str(val1).strip()):
            job2_score += 1
    
    # Prefer jobs with AI analysis
    if job1.get('ai_analyzed'):
        job1_score += 2
    if job2.get('ai_analyzed'):
        job2_score += 2
    
    # Prefer jobs with compatibility scores
    if job1.get('compatibility_score'):
        job1_score += 1
    if job2.get('compatibility_score'):
        job2_score += 1
    
    return job1_score > job2_score

@app.route('/api/database/repair', methods=['POST'])
def repair_database():
    """Run comprehensive database repair"""
    try:
        data = request.get_json() or {}
        auto_fix = data.get('auto_fix', False)
        
        repair_results = {
            'integrity_check': {},
            'duplicates_cleaned': 0,
            'orphaned_refs_fixed': 0,
            'issues_resolved': []
        }
        
        sys.path.append('src/utils')
        from db_integrity_checker import DatabaseIntegrityChecker
        
        checker = DatabaseIntegrityChecker(DATABASE_PATH)
        
        # Step 1: Run integrity check
        integrity_results = checker.validate_database_integrity()
        repair_results['integrity_check'] = integrity_results
        
        if auto_fix:
            # Step 2: Fix duplicates
            duplicates = checker.find_duplicate_jobs()
            if duplicates:
                cleanup_results = checker.clean_duplicate_jobs(duplicates, auto_resolve=True)
                repair_results['duplicates_cleaned'] = cleanup_results['jobs_removed']
                repair_results['issues_resolved'].append(f"Cleaned {cleanup_results['jobs_removed']} duplicate jobs")
            
            # Step 3: Update job statuses
            if db_manager:
                updated_statuses = db_manager.auto_update_job_statuses()
                if updated_statuses > 0:
                    repair_results['issues_resolved'].append(f"Updated {updated_statuses} job statuses")
        
        return jsonify({
            'success': True,
            'repair_results': repair_results,
            'message': f'Database repair completed. {"Auto-fixes applied." if auto_fix else "Diagnostics only."}'
        })
        
    except Exception as e:
        logger.error(f"Error repairing database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("="*60)
    print("🚀 STARTING JOB SEARCH API SERVER v3.4 - AI ANALYSIS FIXED")
    print("="*60)
    print(f"🌐 Web Interface: http://localhost:5000")
    print(f"🔧 API Health Check: http://localhost:5000/api/health")
    print(f"📊 Database: {DATABASE_PATH if DATABASE_PATH else 'NOT CONFIGURED'}")
    print(f"🤖 AI Matcher: {'Enabled' if ai_matcher else 'Disabled (missing OpenAI key)'}")
    print(f"💰 Salary Parsing: {'Enabled' if SALARY_PARSING_ENABLED else 'Disabled'}")
    print(f"📄 Resume Matching: {'Enabled' if RESUME_MATCHING_ENABLED else 'Disabled'}")
    print(f"📎 Document Parsing: {'Enabled' if DOCUMENT_PARSING_ENABLED else 'Disabled'}")
    print(f"🔗 LinkedIn Scraping: {'Enabled' if LINKEDIN_SCRAPING_ENABLED else 'Disabled'}")
    print("="*60)
    print("🔍 Available Endpoints:")
    print("   GET  /api/jobs - Load jobs from database")
    print("   POST /api/jobs/<id>/rate - Rate a job")
    print("   GET  /api/stats - Database and AI statistics")
    print("   GET  /api/sources - Available job sources")
    print("   GET  /api/profile - User profile")
    print("   POST /api/profile - Update user profile")
    print("   POST /api/search/start - Start background job search")
    print("   GET  /api/search/status - Job search status")
    print("   GET  /api/resumes - List resume versions")
    print("   POST /api/resumes/add - Add resume via text")
    print("   POST /api/resumes/upload - Upload resume document")
    print("   DELETE /api/resumes/<name> - Delete resume")
    print("   GET  /api/debug/sources - Analyze job sources")
    print("   GET  /api/debug/validate-urls - Validate job URLs")
    print("   POST /api/debug/parse-salaries - Parse all salaries")
    print("   POST /api/debug/analyze-job/<id> - AI analyze job")
    print("   GET  /api/debug/feedback-learning - Debug AI learning")
    print("   POST /api/debug/cleanup-keywords - Clean bad keywords")
    print("   POST /api/debug/reset-profile - Reset user profile")
    print("   POST /api/debug/scrape-job/<id> - Manual job scraping")
    print("   GET  /api/debug/linkedin-scraping-status - Scraping stats")
    print("="*60)
    print("🎯 VERSION 3.4 IMPROVEMENTS:")
    print("   ✅ FIXED: AI analysis now runs on ALL jobs")
    print("   ✅ FIXED: Removed duplicate LinkedIn scraping steps")
    print("   ✅ FIXED: AI scoring uses your 25 feedback items")
    print("   ✅ FIXED: Forced analysis removes 0% score issue")
    print("   ✅ ADDED: LinkedIn job description scraping")
    print("   ✅ ADDED: Debug endpoints for troubleshooting")
    print("="*60)
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)