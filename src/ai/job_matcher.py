# ai/job_matcher.py
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pickle
import openai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd

class AIJobMatcher:
    """
    AI-powered job matching system that learns from user feedback
    to improve job recommendations over time
    """
    
    def __init__(self, openai_api_key: str, user_profile_path: str = "data/user_profile.json"):
        """
        Initialize the AI job matcher
        
        Args:
            openai_api_key: OpenAI API key for GPT analysis
            user_profile_path: Path to store user profile and preferences
        """
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key
        
        self.user_profile_path = user_profile_path
        self.feedback_path = "data/job_feedback.json"
        self.model_path = "data/job_matcher_model.pkl"
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize user profile and feedback storage
        self.user_profile = self._load_user_profile()
        self.job_feedback = self._load_feedback()
        
        # Initialize TF-IDF vectorizer for job matching
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Load or initialize the matching model
        self._load_or_initialize_model()
    
    def _load_user_profile(self) -> Dict:
        """Load user profile from file or create default"""
        if os.path.exists(self.user_profile_path):
            try:
                with open(self.user_profile_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading user profile: {e}")
        
        # Default profile - you should customize this
        return {
            "name": "Product Manager",
            "current_role": "Senior Product Manager",
            "experience_years": 8,
            "skills": [
                "Product Management", "Product Strategy", "User Research",
                "Data Analysis", "A/B Testing", "Roadmap Planning",
                "Cross-functional Leadership", "Agile/Scrum", "SQL",
                "Product Analytics", "Market Research", "Stakeholder Management"
            ],
            "industries": ["Technology", "SaaS", "E-commerce", "Fintech"],
            "preferred_companies": ["Microsoft", "Amazon", "Google", "Meta", "Apple"],
            "location_preferences": ["Seattle, WA", "Remote", "San Francisco, CA"],
            "salary_min": 140000,
            "salary_max": 200000,
            "company_size_preference": ["Large", "Medium"],
            "remote_preference": "Hybrid or Remote",
            "keywords_positive": [
                "product manager", "senior product", "principal product",
                "product lead", "product director", "product strategy",
                "user experience", "data-driven", "growth", "platform"
            ],
            "keywords_negative": [
                "junior", "entry level", "marketing", "sales",
                "customer service", "support", "temporary", "contract"
            ]
        }
    
    def _load_feedback(self) -> List[Dict]:
        """Load previous job feedback"""
        if os.path.exists(self.feedback_path):
            try:
                with open(self.feedback_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading feedback: {e}")
        return []
    
    def _save_user_profile(self):
        """Save user profile to file"""
        os.makedirs(os.path.dirname(self.user_profile_path), exist_ok=True)
        with open(self.user_profile_path, 'w') as f:
            json.dump(self.user_profile, f, indent=2)
    
    def _save_feedback(self):
        """Save feedback to file"""
        os.makedirs(os.path.dirname(self.feedback_path), exist_ok=True)
        with open(self.feedback_path, 'w') as f:
            json.dump(self.job_feedback, f, indent=2)
    
    def _load_or_initialize_model(self):
        """Load existing model or initialize new one"""
        if os.path.exists(self.model_path) and self.job_feedback:
            try:
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.vectorizer = model_data['vectorizer']
                    self.job_vectors = model_data.get('job_vectors')
                self.logger.info("Loaded existing job matcher model")
            except Exception as e:
                self.logger.error(f"Error loading model: {e}")
                self.job_vectors = None
        else:
            self.job_vectors = None
    
    def _save_model(self):
        """Save the current model"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        model_data = {
            'vectorizer': self.vectorizer,
            'job_vectors': self.job_vectors
        }
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
    
    def update_user_profile(self, **kwargs):
        """Update user profile with new information"""
        self.user_profile.update(kwargs)
        self._save_user_profile()
        self.logger.info("User profile updated")
    
    def analyze_job_with_ai(self, job: Dict) -> Dict:
        """
        Use OpenAI to analyze a job posting and extract relevant information
        
        Args:
            job: Job dictionary
            
        Returns:
            Enhanced job data with AI analysis
        """
        try:
            # Create prompt for job analysis
            prompt = f"""
            Analyze this job posting for a product manager and extract key information:
            
            Title: {job.get('title', '')}
            Company: {job.get('company', '')}
            Location: {job.get('location', '')}
            Description: {job.get('description', '')[:1000]}
            
            Please provide a JSON response with:
            1. experience_level: junior/mid/senior/principal/director
            2. required_skills: list of key skills mentioned
            3. company_size: startup/small/medium/large/enterprise
            4. industry: primary industry
            5. remote_type: onsite/hybrid/remote
            6. match_score: 0-100 score for a senior product manager with 8+ years experience
            7. key_highlights: 3-5 most attractive aspects of the role
            8. potential_concerns: any red flags or concerns
            
            Return only valid JSON.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            
            ai_analysis = json.loads(response.choices[0].message.content)
            
            # Add AI analysis to job data
            job['ai_analysis'] = ai_analysis
            job['ai_analyzed'] = True
            job['ai_analysis_date'] = datetime.now().isoformat()
            
            return job
            
        except Exception as e:
            self.logger.error(f"Error in AI job analysis: {e}")
            job['ai_analysis'] = {}
            job['ai_analyzed'] = False
            return job
    
    def calculate_compatibility_score(self, job: Dict) -> float:
        """
        Calculate compatibility score based on user profile and past feedback
        
        Args:
            job: Job dictionary
            
        Returns:
            Compatibility score (0-100)
        """
        score = 0
        weights = {}
        
        # Base scoring factors
        factors = {
            'title_match': 15,
            'skills_match': 20,
            'location_match': 10,
            'salary_match': 15,
            'company_match': 10,
            'experience_match': 10,
            'keywords_positive': 10,
            'keywords_negative': -15,
            'ai_score': 15
        }
        
        # Title matching
        title = job.get('title', '').lower()
        title_score = 0
        for keyword in self.user_profile['keywords_positive']:
            if keyword.lower() in title:
                title_score += 1
        score += min(title_score / len(self.user_profile['keywords_positive']) * factors['title_match'], factors['title_match'])
        
        # Skills matching (if available from AI analysis)
        if job.get('ai_analysis', {}).get('required_skills'):
            job_skills = [skill.lower() for skill in job['ai_analysis']['required_skills']]
            user_skills = [skill.lower() for skill in self.user_profile['skills']]
            skills_overlap = len(set(job_skills) & set(user_skills))
            skills_score = skills_overlap / max(len(user_skills), 1) * factors['skills_match']
            score += min(skills_score, factors['skills_match'])
        
        # Location matching
        job_location = job.get('location', '').lower()
        location_score = 0
        for pref_loc in self.user_profile['location_preferences']:
            if pref_loc.lower() in job_location or 'remote' in job_location:
                location_score = factors['location_match']
                break
        score += location_score
        
        # Salary matching
        if job.get('salary_min') or job.get('salary_max'):
            job_salary_min = job.get('salary_min', 0)
            job_salary_max = job.get('salary_max', 999999)
            user_min = self.user_profile['salary_min']
            user_max = self.user_profile['salary_max']
            
            if job_salary_max >= user_min and job_salary_min <= user_max:
                score += factors['salary_match']
            elif job_salary_min >= user_min * 0.8:  # Within 20% of minimum
                score += factors['salary_match'] * 0.7
        
        # Company matching
        company = job.get('company', '').lower()
        for pref_company in self.user_profile['preferred_companies']:
            if pref_company.lower() in company:
                score += factors['company_match']
                break
        
        # AI analysis score
        if job.get('ai_analysis', {}).get('match_score'):
            ai_score = job['ai_analysis']['match_score'] / 100 * factors['ai_score']
            score += ai_score
        
        # Learn from feedback
        if self.job_feedback:
            feedback_adjustment = self._calculate_feedback_adjustment(job)
            score += feedback_adjustment
        
        return min(max(score, 0), 100)  # Clamp between 0-100
    
    def _calculate_feedback_adjustment(self, job: Dict) -> float:
        """Calculate score adjustment based on past feedback"""
        adjustment = 0
        
        # Analyze patterns in liked/disliked jobs
        liked_jobs = [fb for fb in self.job_feedback if fb['rating'] >= 4]
        disliked_jobs = [fb for fb in self.job_feedback if fb['rating'] <= 2]
        
        # Company patterns
        job_company = job.get('company', '').lower()
        for liked in liked_jobs:
            if liked.get('company', '').lower() == job_company:
                adjustment += 5
        
        for disliked in disliked_jobs:
            if disliked.get('company', '').lower() == job_company:
                adjustment -= 10
        
        # Title patterns
        job_title = job.get('title', '').lower()
        for liked in liked_jobs:
            liked_title = liked.get('title', '').lower()
            common_words = set(job_title.split()) & set(liked_title.split())
            if len(common_words) >= 2:
                adjustment += 3
        
        return adjustment
    
    def score_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """
        Score a list of jobs and sort by compatibility
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Sorted list of jobs with compatibility scores
        """
        scored_jobs = []
        
        for job in jobs:
            # Analyze with AI if not already done
            if not job.get('ai_analyzed', False):
                job = self.analyze_job_with_ai(job)
            
            # Calculate compatibility score
            compatibility_score = self.calculate_compatibility_score(job)
            job['compatibility_score'] = compatibility_score
            
            scored_jobs.append(job)
        
        # Sort by compatibility score (highest first)
        scored_jobs.sort(key=lambda x: x.get('compatibility_score', 0), reverse=True)
        
        return scored_jobs
    
    def record_feedback(self, job: Dict, rating: int, notes: str = ""):
        """
        Record user feedback on a job recommendation
        
        Args:
            job: Job dictionary
            rating: 1-5 rating (1=poor match, 5=excellent match)
            notes: Optional notes about the rating
        """
        feedback = {
            'job_id': job.get('job_id'),
            'title': job.get('title'),
            'company': job.get('company'),
            'rating': rating,
            'notes': notes,
            'feedback_date': datetime.now().isoformat(),
            'compatibility_score': job.get('compatibility_score'),
            'ai_analysis': job.get('ai_analysis', {})
        }
        
        self.job_feedback.append(feedback)
        self._save_feedback()
        
        # Update model with new feedback
        self._retrain_model()
        
        self.logger.info(f"Recorded feedback: {rating}/5 for {job.get('title')}")
    
    def _retrain_model(self):
        """Retrain the model based on accumulated feedback"""
        if len(self.job_feedback) < 5:  # Need minimum feedback
            return
        
        # Update user preferences based on feedback patterns
        self._update_preferences_from_feedback()
        
        # Save updated model
        self._save_model()
        self.logger.info("Model retrained with new feedback")
    
    def _update_preferences_from_feedback(self):
        """Update user preferences based on feedback patterns"""
        liked_jobs = [fb for fb in self.job_feedback if fb['rating'] >= 4]
        disliked_jobs = [fb for fb in self.job_feedback if fb['rating'] <= 2]
        
        # Update preferred companies
        liked_companies = [job.get('company') for job in liked_jobs if job.get('company')]
        for company in liked_companies:
            if company not in self.user_profile['preferred_companies']:
                self.user_profile['preferred_companies'].append(company)
        
        # Update negative keywords from disliked jobs
        for job in disliked_jobs:
            title_words = job.get('title', '').lower().split()
            for word in title_words:
                if len(word) > 3 and word not in self.user_profile['keywords_negative']:
                    # Add frequently appearing words in disliked jobs to negative keywords
                    disliked_count = sum(1 for dj in disliked_jobs if word in dj.get('title', '').lower())
                    if disliked_count >= 2:  # Appears in 2+ disliked jobs
                        self.user_profile['keywords_negative'].append(word)
        
        self._save_user_profile()
    
    def get_recommendations(self, jobs: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        Get top job recommendations
        
        Args:
            jobs: List of job dictionaries
            top_n: Number of top recommendations to return
            
        Returns:
            Top N recommended jobs
        """
        scored_jobs = self.score_jobs(jobs)
        return scored_jobs[:top_n]
    
    def get_feedback_summary(self) -> Dict:
        """Get summary of feedback and learning progress"""
        if not self.job_feedback:
            return {"message": "No feedback recorded yet"}
        
        total_feedback = len(self.job_feedback)
        avg_rating = sum(fb['rating'] for fb in self.job_feedback) / total_feedback
        
        liked_jobs = len([fb for fb in self.job_feedback if fb['rating'] >= 4])
        disliked_jobs = len([fb for fb in self.job_feedback if fb['rating'] <= 2])
        
        return {
            "total_feedback": total_feedback,
            "average_rating": round(avg_rating, 2),
            "liked_jobs": liked_jobs,
            "disliked_jobs": disliked_jobs,
            "learning_progress": "Good" if total_feedback >= 10 else "Getting started",
            "preferred_companies": self.user_profile['preferred_companies'][-5:],  # Last 5
            "negative_keywords": self.user_profile['keywords_negative'][-5:]  # Last 5
        }


# Test function
def test_ai_matcher():
    """Test the AI job matcher"""
    from config.settings import OPENAI_API_KEY
    
    if not OPENAI_API_KEY:
        print("OpenAI API key not found in settings")
        return
    
    matcher = AIJobMatcher(OPENAI_API_KEY)
    
    # Test job
    test_job = {
        'job_id': 'test_ai_123',
        'title': 'Senior Product Manager - Platform',
        'company': 'Microsoft',
        'location': 'Seattle, WA',
        'description': 'We are looking for a Senior Product Manager to lead our platform initiatives...',
        'salary_min': 150000,
        'salary_max': 180000
    }
    
    # Analyze job
    analyzed_job = matcher.analyze_job_with_ai(test_job)
    score = matcher.calculate_compatibility_score(analyzed_job)
    
    print(f"Job: {analyzed_job['title']}")
    print(f"Compatibility Score: {score}")
    print(f"AI Analysis: {analyzed_job.get('ai_analysis', {})}")

if __name__ == "__main__":
    test_ai_matcher()