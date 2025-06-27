# ai/simple_job_matcher.py - CLEAN FIXED VERSION
import json
import logging
import os
import time  # Add this import
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from openai import OpenAI  # Updated import for OpenAI 1.88.0+
import re

class SimpleAIJobMatcher:
    """
    Simplified AI-powered job matching system that learns from user feedback
    without requiring heavy ML dependencies like scikit-learn
    """
    
    def __init__(self, openai_api_key: str, user_profile_path: str = "data/user_profile.json"):
        """
        Initialize the simple AI job matcher
        
        Args:
            openai_api_key: OpenAI API key for GPT analysis
            user_profile_path: Path to store user profile and preferences
        """
        self.openai_api_key = openai_api_key
        self.client = OpenAI(api_key=openai_api_key)  # New client initialization
        
        self.user_profile_path = user_profile_path
        self.feedback_path = "data/job_feedback.json"
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize user profile and feedback storage
        self.user_profile = self._load_user_profile()
        self.job_feedback = self._load_feedback()
    
    def _load_user_profile(self) -> Dict:
        """Load user profile from file or create default"""
        if os.path.exists(self.user_profile_path):
            try:
                with open(self.user_profile_path, 'r') as f:
                    profile = json.load(f)
                    # Ensure last_updated field exists
                    if 'last_updated' not in profile:
                        profile['last_updated'] = datetime.now().isoformat()
                        self._save_user_profile_data(profile)
                    return profile
            except Exception as e:
                self.logger.error(f"Error loading user profile: {e}")
        
        # Default profile - customize this for your background
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
            ],
            "last_updated": datetime.now().isoformat()
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
    
    def _save_user_profile_data(self, profile_data: Dict):
        """Save profile data to file"""
        os.makedirs(os.path.dirname(self.user_profile_path), exist_ok=True)
        with open(self.user_profile_path, 'w') as f:
            json.dump(profile_data, f, indent=2)
    
    def _save_user_profile(self):
        """Save user profile to file with updated timestamp"""
        self.user_profile['last_updated'] = datetime.now().isoformat()
        self._save_user_profile_data(self.user_profile)
    
    def _save_feedback(self):
        """Save feedback to file"""
        os.makedirs(os.path.dirname(self.feedback_path), exist_ok=True)
        with open(self.feedback_path, 'w') as f:
            json.dump(self.job_feedback, f, indent=2)
    
    def update_user_profile(self, **kwargs):
        """Update user profile with new information"""
        self.user_profile.update(kwargs)
        self._save_user_profile()
        self.logger.info("User profile updated")

    def analyze_job_with_ai(self, job: Dict) -> Dict:
        """
        Use OpenAI to analyze a job posting and extract relevant information
        FIXED VERSION - resolves 'NoneType' object is not subscriptable error
        """
        try:
            # Create enhanced prompt that incorporates user feedback
            user_context = self._build_user_context_from_feedback()
            
            prompt = f"""
            Analyze this job posting for compatibility with user preferences:
            
            JOB DETAILS:
            Title: {job.get('title', '')}
            Company: {job.get('company', '')}
            Location: {job.get('location', '')}
            Description: {job.get('description', '')[:1000]}
            
            {user_context[:800]}
            
            Please provide a JSON response with:
            1. experience_level: junior/mid/senior/principal/director
            2. required_skills: list of 3-5 key skills mentioned
            3. company_size: startup/small/medium/large/enterprise
            4. industry: primary industry
            5. remote_type: onsite/hybrid/remote
            6. compatibility_score: 0-100 score based on user feedback patterns
            7. key_highlights: 2-3 most attractive aspects
            8. potential_concerns: any red flags based on user dislikes
            
            IMPORTANT: Consider the user's feedback that they frequently mention "not a software developer" 
            and dislike React/NodeJS/AWS developer roles. Score software engineering roles LOW (15-30).
            Score product management roles HIGH (60-85).
            
            Return only valid JSON with a numeric compatibility_score between 0-100.
            """
            
            # Rate limiting for Tier 1
            time.sleep(0.5)
            
            # Make API call with better error handling
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI job matching assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            # FIXED: Better response validation
            if not response:
                raise Exception("No response from OpenAI API")
                
            if not hasattr(response, 'choices') or not response.choices:
                raise Exception("Response missing choices")
                
            if not hasattr(response.choices[0], 'message') or not response.choices[0].message:
                raise Exception("Response missing message")
                
            response_text = response.choices[0].message.content
            if not response_text:
                raise Exception("Empty response content")
                
            response_text = response_text.strip()
            
            # Debug logging
            print(f"🔍 AI Response for '{job.get('title', 'Unknown')[:30]}': {response_text[:100]}...")
            
            # Initialize ai_analysis with a default score
            ai_analysis = {"compatibility_score": 50}  # Default fallback
            
            try:
                # Try to parse JSON
                parsed_analysis = json.loads(response_text)
                
                # Validate that we got a score
                if isinstance(parsed_analysis, dict) and 'compatibility_score' in parsed_analysis:
                    score = parsed_analysis['compatibility_score']
                    if isinstance(score, (int, float)) and 0 <= score <= 100:
                        ai_analysis = parsed_analysis
                        print(f"✅ JSON parsed successfully with score: {score}%")
                    else:
                        print(f"⚠️ Invalid score in JSON: {score}, using fallback")
                        ai_analysis['compatibility_score'] = self._generate_fallback_score(job)
                else:
                    print(f"⚠️ No valid compatibility_score in JSON, using fallback")
                    ai_analysis['compatibility_score'] = self._generate_fallback_score(job)
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                # Try to extract score from text
                import re
                score_match = re.search(r'"compatibility_score":\s*(\d+)', response_text)
                if score_match:
                    score = int(score_match.group(1))
                    ai_analysis = {"compatibility_score": score}
                    print(f"✅ Extracted score from text: {score}%")
                else:
                    # Generate intelligent fallback
                    ai_analysis['compatibility_score'] = self._generate_fallback_score(job)
                    print(f"✅ Generated intelligent fallback score: {ai_analysis['compatibility_score']}%")
            
            # CRITICAL: Ensure we always have a valid score
            final_score = ai_analysis.get('compatibility_score', 50)
            if not isinstance(final_score, (int, float)) or not (0 <= final_score <= 100):
                final_score = self._generate_fallback_score(job)
                ai_analysis['compatibility_score'] = final_score
            
            # Add AI analysis to job data
            job['ai_analysis'] = ai_analysis
            job['ai_analyzed'] = True
            job['ai_analysis_date'] = datetime.now().isoformat()
            job['compatibility_score'] = final_score
            job['score_source'] = 'AI_ANALYSIS'
            
            print(f"✅ AI Analysis successful for '{job.get('title', 'Unknown')[:30]}': {final_score}% (AI)")
            return job
            
        except Exception as e:
            self.logger.error(f"Error in AI job analysis for '{job.get('title', 'Unknown')}': {e}")
            print(f"❌ AI Analysis failed for '{job.get('title', 'Unknown')}': {e}")
            
            # Generate intelligent fallback score
            fallback_score = self._generate_fallback_score(job)
            
            job['ai_analysis'] = {"compatibility_score": fallback_score, "error": str(e)}
            job['ai_analyzed'] = False
            job['compatibility_score'] = fallback_score
            job['score_source'] = 'FALLBACK'
            
            print(f"✅ Fallback score for '{job.get('title', 'Unknown')[:30]}': {fallback_score}% (FALLBACK)")
            return job

    def _generate_fallback_score(self, job: Dict) -> float:
        """Generate intelligent fallback score - BULLETPROOF version that handles None values"""
        
        # SAFE: Handle None values in job data
        def safe_text_field(field_value):
            """Safely convert field to lowercase string"""
            if field_value is None:
                return ''
            return str(field_value).lower()
        
        # Safe field extraction
        title = safe_text_field(job.get('title'))
        company = safe_text_field(job.get('company'))
        description = safe_text_field(job.get('description'))
        
        # Start with neutral score
        score = 50.0
        
        print(f"  🔍 Analyzing fallback for: '{title[:30]}'")
        
        # MAJOR NEGATIVE SIGNALS (based on user feedback)
        if any(term in title for term in ['software engineer', 'developer', 'frontend', 'backend', 'full stack']):
            score = 20  # Very low for engineering roles
            print(f"  📉 Software engineering role detected: {score}%")
        elif any(term in title for term in ['engineering manager', 'engineering director']):
            score = 35  # Moderate for engineering management
            print(f"  📊 Engineering management role detected: {score}%")
        
        # Technical stack penalties
        full_text = title + ' ' + description
        if any(term in full_text for term in ['react', 'nodejs', 'aws engineer', 'javascript']):
            score -= 15
            print(f"  📉 Technical stack penalty applied")
        
        # Industry penalties
        company_desc = company + ' ' + description
        if any(term in company_desc for term in ['fintech', 'crypto', 'blockchain']):
            score -= 10
            print(f"  📉 FinTech/Crypto penalty applied")
        
        # MAJOR POSITIVE SIGNALS
        if any(term in title for term in ['product manager', 'product', 'strategic', 'strategy']):
            score = 75  # High for product roles
            print(f"  📈 Product/strategy role detected: {score}%")
        
        if any(term in title for term in ['operations', 'ops', 'business']):
            score += 15
            print(f"  📈 Operations/business boost applied")
        
        # Leadership boost
        if any(term in title for term in ['director', 'vp', 'vice president', 'chief', 'head of']):
            score += 10
            print(f"  📈 Leadership role boost applied")
        
        # Company preferences
        if 'amazon' in company:
            score += 15
            print(f"  📈 Amazon preference boost applied")
        elif any(term in company for term in ['google', 'microsoft', 'meta']):
            score += 10
            print(f"  📈 Top-tier company boost applied")
        
        # Clamp to valid range
        score = max(5, min(95, score))
        print(f"  ✅ Final fallback score: {score}%")
        return score

    def _build_user_context_from_feedback(self) -> str:
        """Build user context string from feedback data."""
        if not self.job_feedback:
            return "No user feedback available."
        
        # Analyze feedback patterns
        positive_patterns = []
        negative_patterns = []
        
        for feedback in self.job_feedback:
            rating = feedback.get('rating', 0)
            notes = feedback.get('notes', '').lower()
            job_title = feedback.get('title', '').lower()
            
            if rating >= 4:
                positive_patterns.append(f"Liked: {job_title} - {notes}")
            elif rating <= 2:
                negative_patterns.append(f"Disliked: {job_title} - {notes}")
        
        context = "USER PREFERENCES (based on feedback):\n"
        
        if positive_patterns:
            context += "\nPOSITIVE FEEDBACK:\n" + "\n".join(positive_patterns[:5])
        
        if negative_patterns:
            context += "\nNEGATIVE FEEDBACK:\n" + "\n".join(negative_patterns[:10])
        
        # Add key insights from the feedback analysis
        context += "\n\nKEY INSIGHTS FROM FEEDBACK:"
        context += "\n- User frequently mentions 'not a software developer'"
        context += "\n- Dislikes React/NodeJS/AWS developer roles"
        context += "\n- Prefers product management and strategic roles"
        context += "\n- FinTech/Crypto roles are poor fits"
        
        return context

    def calculate_compatibility_score(self, job: Dict) -> float:
        """
        Calculate compatibility score using simple matching algorithms
        
        Args:
            job: Job dictionary
            
        Returns:
            Compatibility score (0-100)
        """
        score = 0
        
        # Base scoring factors
        factors = {
            'title_match': 20,
            'skills_match': 15,
            'location_match': 10,
            'salary_match': 15,
            'company_match': 10,
            'keywords_positive': 15,
            'keywords_negative': -20,
            'ai_score': 15
        }
        
        # Title matching
        title = job.get('title', '').lower()
        title_score = 0
        for keyword in self.user_profile['keywords_positive']:
            if keyword.lower() in title:
                title_score += 1
        
        # Normalize title score
        if self.user_profile['keywords_positive']:
            title_score = (title_score / len(self.user_profile['keywords_positive'])) * factors['title_match']
            score += min(title_score, factors['title_match'])
        
        # Check for negative keywords
        negative_score = 0
        for neg_keyword in self.user_profile['keywords_negative']:
            if neg_keyword.lower() in title:
                negative_score += factors['keywords_negative'] / len(self.user_profile['keywords_negative'])
        score += negative_score
        
        # Skills matching (if available from AI analysis)
        if job.get('ai_analysis', {}).get('required_skills'):
            job_skills = [skill.lower() for skill in job['ai_analysis']['required_skills']]
            user_skills = [skill.lower() for skill in self.user_profile['skills']]
            
            # Simple overlap calculation
            skills_overlap = len(set(job_skills) & set(user_skills))
            if user_skills:
                skills_score = (skills_overlap / len(user_skills)) * factors['skills_match']
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
        if job.get('ai_analysis', {}).get('compatibility_score'):
            ai_score = (job['ai_analysis']['compatibility_score'] / 100) * factors['ai_score']
            score += ai_score
        
        # Learn from feedback
        if self.job_feedback:
            feedback_adjustment = self._calculate_feedback_adjustment(job)
            score += feedback_adjustment
        
        return min(max(score, 0), 100)  # Clamp between 0-100

    def _calculate_feedback_adjustment(self, job: Dict) -> float:
        """Calculate score adjustment based on past feedback using simple pattern matching"""
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
        
        # Title patterns - simple word overlap
        job_title = job.get('title', '').lower()
        job_words = set(re.findall(r'\b\w+\b', job_title))
        
        for liked in liked_jobs:
            liked_title = liked.get('title', '').lower()
            liked_words = set(re.findall(r'\b\w+\b', liked_title))
            common_words = job_words & liked_words
            if len(common_words) >= 2:
                adjustment += 3
        
        for disliked in disliked_jobs:
            disliked_title = disliked.get('title', '').lower()
            disliked_words = set(re.findall(r'\b\w+\b', disliked_title))
            common_words = job_words & disliked_words
            if len(common_words) >= 2:
                adjustment -= 5
        
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
            
            # Ensure compatibility score exists
            if 'compatibility_score' not in job:
                job['compatibility_score'] = self.calculate_compatibility_score(job)
            
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
        
        # Update preferences based on feedback
        self._update_preferences_from_feedback()
        
        self.logger.info(f"Recorded feedback: {rating}/5 for {job.get('title')}")
    
    def _update_preferences_from_feedback(self):
        """Update user preferences based on feedback patterns (FIXED VERSION)"""
        liked_jobs = [fb for fb in self.job_feedback if fb['rating'] >= 4]
        disliked_jobs = [fb for fb in self.job_feedback if fb['rating'] <= 2]
        
        # Update preferred companies from liked jobs
        liked_companies = [job.get('company') for job in liked_jobs if job.get('company')]
        for company in liked_companies:
            if company and company not in self.user_profile['preferred_companies']:
                self.user_profile['preferred_companies'].append(company)
        
        # FIXED: Only add negative keywords from DISLIKED jobs and be more selective
        # Words that should NEVER be negative keywords (whitelist)
        protected_words = {
            'remote', 'product', 'manager', 'senior', 'director', 'lead', 'principal',
            'vice', 'president', 'chief', 'strategy', 'platform', 'growth', 'data',
            'user', 'experience', 'engineering', 'technical', 'startup', 'amazon',
            'google', 'microsoft', 'meta', 'apple', 'seattle',
            'year', 'years', 'united', 'states', 'hour', 'hours', 'learning',
            'development', 'innovation', 'team', 'cross', 'functional'
        }
        
        # Words that are actually bad signals (expand this list)
        truly_negative_signals = {
            'junior', 'entry', 'level', 'intern', 'temporary', 'contract', 'part-time',
            'marketing', 'sales', 'service', 'call', 'center',
            'retail', 'cashier', 'clerk', 'assistant', 'receptionist', 'admin',
            'secretarial', 'entry', 'manual', 'labor'
        }
        
        # Only add negative keywords if they appear frequently in disliked jobs
        # AND are not in the protected words list
        # AND are actually negative signal words
        word_counts = {}
        for job in disliked_jobs:
            title_words = re.findall(r'\b\w+\b', job.get('title', '').lower())
            for word in title_words:
                if len(word) > 2:  # Only consider words longer than 2 characters
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Add to negative keywords only if:
        # 1. Word appears in 3+ disliked jobs (frequent pattern)
        # 2. Word is not in protected list
        # 3. Word is in truly negative signals OR appears in 4+ disliked jobs
        for word, count in word_counts.items():
            if (count >= 3 and 
                word not in protected_words and 
                word not in self.user_profile['keywords_negative']):
                
                # Extra strict: only add if it's a known bad signal OR appears very frequently
                if word in truly_negative_signals or count >= 4:
                    self.user_profile['keywords_negative'].append(word)
                    self.logger.info(f"Added negative keyword: '{word}' (appeared {count} times in disliked jobs)")
        
        # BONUS: Extract positive keywords from liked jobs
        if liked_jobs:
            positive_word_counts = {}
            for job in liked_jobs:
                title_words = re.findall(r'\b\w+\b', job.get('title', '').lower())
                for word in title_words:
                    if len(word) > 3:
                        positive_word_counts[word] = positive_word_counts.get(word, 0) + 1
            
            # Add frequently appearing words from liked jobs to positive keywords
            for word, count in positive_word_counts.items():
                if (count >= 2 and  # Appears in 2+ liked jobs
                    word not in self.user_profile['keywords_positive']):
                    self.user_profile['keywords_positive'].append(word)
                    self.logger.info(f"Added positive keyword: '{word}' (appeared {count} times in liked jobs)")
        
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
def test_simple_ai_matcher():
    """Test the simple AI job matcher"""
    from config.settings import OPENAI_API_KEY
    
    if not OPENAI_API_KEY:
        print("OpenAI API key not found in settings")
        return
    
    matcher = SimpleAIJobMatcher(OPENAI_API_KEY)
    
    # Test job
    test_job = {
        'job_id': 'test_simple_123',
        'title': 'Senior Product Manager - Platform',
        'company': 'Microsoft',
        'location': 'Seattle, WA',
        'description': 'We are looking for a Senior Product Manager to lead our platform initiatives...',
        'salary_min': 150000,
        'salary_max': 180000
    }
    
    # Analyze job
    analyzed_job = matcher.analyze_job_with_ai(test_job)
    score = analyzed_job.get('compatibility_score', 0)
    
    print(f"Job: {analyzed_job['title']}")
    print(f"Compatibility Score: {score}")
    print(f"AI Analysis: {analyzed_job.get('ai_analysis', {})}")

if __name__ == "__main__":
    test_simple_ai_matcher()