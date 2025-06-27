# Version 3.1 - AI Resume-Based Job Matching System (FIXED)
# src/ai/resume_job_matcher.py
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from openai import OpenAI  # Updated import for OpenAI 1.88.0+
import re

class ResumeBasedJobMatcher:
    """
    Advanced AI job matcher that uses multiple resumes to find best matching jobs
    """
    
    def __init__(self, openai_api_key: str, resumes_dir: str = "data/resumes"):
        self.openai_api_key = openai_api_key
        self.client = OpenAI(api_key=openai_api_key)  # New client initialization
        self.resumes_dir = resumes_dir
        self.logger = logging.getLogger(__name__)
        
        # Ensure resumes directory exists
        os.makedirs(resumes_dir, exist_ok=True)
        
        # Store parsed resumes
        self.resumes = {}
        self.resume_profiles = {}
        
        # Load existing resumes
        self._load_all_resumes()
    
    def add_resume(self, resume_name: str, resume_text: str, target_roles: List[str] = None):
        """
        Add a resume version with AI analysis - CLEAN VERSION that fails fast
        """
        try:
            self.logger.info(f"🔄 Starting resume analysis for: {resume_name}")
            
            # Validate inputs
            if not resume_name or not resume_name.strip():
                self.logger.error("❌ Resume name is required")
                return False
                
            if not resume_text or len(resume_text.strip()) < 100:
                self.logger.error(f"❌ Resume text too short: {len(resume_text)} characters")
                return False
            
            # Ensure target_roles is a list
            if target_roles is None:
                target_roles = []
            elif isinstance(target_roles, str):
                target_roles = [target_roles]
            
            self.logger.info(f"📝 Resume text length: {len(resume_text)} chars")
            self.logger.info(f"🎯 Target roles: {target_roles}")
            
            # AI ANALYSIS - This MUST succeed or we fail the whole operation
            self.logger.info("🤖 Calling OpenAI API for resume analysis...")
            
            resume_analysis = self._analyze_resume_with_ai(resume_text, target_roles)
            
            # Strict validation - no empty or invalid analysis allowed
            if not resume_analysis:
                raise ValueError("❌ AI analysis returned empty result")
                
            if not isinstance(resume_analysis, dict):
                raise ValueError(f"❌ AI analysis returned invalid type: {type(resume_analysis)}")
                
            if len(resume_analysis) == 0:
                raise ValueError("❌ AI analysis returned empty dictionary")
            
            # Validate critical fields are present
            required_fields = ['skills', 'experience_years', 'experience_level']
            missing_fields = [field for field in required_fields if field not in resume_analysis]
            
            if missing_fields:
                raise ValueError(f"❌ AI analysis missing critical fields: {missing_fields}")
            
            self.logger.info(f"✅ AI analysis successful with {len(resume_analysis)} fields")
            self.logger.info(f"   - Experience: {resume_analysis.get('experience_level')} ({resume_analysis.get('experience_years')} years)")
            self.logger.info(f"   - Skills: {len(resume_analysis.get('skills', []))} found")
            
            # Create resume data structure
            resume_data = {
                'name': resume_name,
                'text': resume_text,
                'target_roles': target_roles,
                'analysis': resume_analysis,
                'created_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
            # Save to file with verification
            resume_file = os.path.join(self.resumes_dir, f"{resume_name}.json")
            self.logger.info(f"💾 Saving to file: {resume_file}")
            
            os.makedirs(self.resumes_dir, exist_ok=True)
            
            with open(resume_file, 'w', encoding='utf-8') as f:
                json.dump(resume_data, f, indent=2, ensure_ascii=False)
            
            # Verify file was written correctly
            if not os.path.exists(resume_file):
                raise IOError(f"❌ Resume file was not created: {resume_file}")
            
            # Verify file contents
            with open(resume_file, 'r', encoding='utf-8') as f:
                verification_data = json.load(f)
                verification_analysis = verification_data.get('analysis', {})
                
                if len(verification_analysis) == 0:
                    raise ValueError(f"❌ File verification failed: analysis is empty in saved file")
                    
            file_size = os.path.getsize(resume_file)
            self.logger.info(f"✅ File saved and verified ({file_size} bytes)")
            
            # Store in memory
            self.resumes[resume_name] = resume_data
            self.resume_profiles[resume_name] = resume_analysis
            
            self.logger.info(f"✅ Resume '{resume_name}' added successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to add resume '{resume_name}': {e}")
            
            # Clean up any partial files
            try:
                resume_file = os.path.join(self.resumes_dir, f"{resume_name}.json")
                if os.path.exists(resume_file):
                    os.remove(resume_file)
            except:
                pass
            
            # Remove from memory if it was added
            if resume_name in self.resumes:
                del self.resumes[resume_name]
            if resume_name in self.resume_profiles:
                del self.resume_profiles[resume_name]
            
            # Re-raise the exception so the caller knows exactly what failed
            raise e

    def _analyze_resume_with_ai(self, resume_text: str, target_roles: List[str] = None) -> Dict:
        """Use OpenAI to analyze resume - CLEAN VERSION with clear error reporting"""
        try:
            target_roles_text = ", ".join(target_roles) if target_roles else "various roles"
            
            # Truncate resume text intelligently but log if we do
            max_chars = 2500
            original_length = len(resume_text)
            if len(resume_text) > max_chars:
                resume_text = resume_text[:max_chars]
                self.logger.warning(f"⚠️ Resume text truncated from {original_length} to {max_chars} chars")
            
            prompt = f"""
            Analyze this resume for someone targeting {target_roles_text} and extract key information:
            
            RESUME:
            {resume_text}
            
            Please provide a JSON response with exactly these fields:
            1. skills: Array of technical and soft skills (strings)
            2. experience_years: Number representing total years of experience
            3. experience_level: String (junior/mid/senior/principal/executive)
            4. industries: Array of industries they've worked in (strings)
            5. company_types: Array of company types (startup/small/medium/large/enterprise)
            6. key_achievements: Array of major accomplishments (strings)
            7. preferred_roles: Array of job titles they'd be good for (strings)
            8. keywords: Array of important keywords for job matching (strings)
            9. salary_range: String with estimated salary range
            10. strengths: Array of top 3-5 professional strengths (strings)
            11. work_style: String (remote/hybrid/onsite or "not specified")
            
            Return ONLY valid JSON. Do not include any other text.
            """
            
            self.logger.debug(f"🤖 Calling OpenAI API...")
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200,
                timeout=30
            )

            response_content = response.choices[0].message.content.strip()
            self.logger.debug(f"🤖 OpenAI response received ({len(response_content)} chars)")
            
            if not response_content:
                raise ValueError("OpenAI returned empty response")
            
            # Clean and extract JSON
            response_content = response_content.strip()
            
            # Remove any markdown formatting or extra text
            import re
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                response_content = json_match.group(0)
            else:
                raise ValueError(f"No valid JSON found in OpenAI response: {response_content[:200]}...")
            
            # Parse JSON
            try:
                analysis = json.loads(response_content)
            except json.JSONDecodeError as json_error:
                self.logger.error(f"❌ JSON parsing failed: {json_error}")
                self.logger.error(f"   Response: {response_content[:500]}...")
                raise ValueError(f"OpenAI returned invalid JSON: {json_error}")
            
            # Validate the analysis structure
            if not isinstance(analysis, dict):
                raise ValueError(f"OpenAI returned non-dict: {type(analysis)}")
            
            # Check for required fields
            required_fields = ['skills', 'experience_years', 'experience_level', 'industries']
            missing_fields = [field for field in required_fields if field not in analysis]
            
            if missing_fields:
                self.logger.error(f"❌ OpenAI response missing required fields: {missing_fields}")
                raise ValueError(f"OpenAI analysis missing required fields: {missing_fields}")
            
            # Validate field types
            if not isinstance(analysis.get('skills'), list):
                raise ValueError(f"Skills field must be a list, got: {type(analysis.get('skills'))}")
                
            if not isinstance(analysis.get('experience_years'), (int, float)):
                raise ValueError(f"Experience years must be a number, got: {type(analysis.get('experience_years'))}")
            
            self.logger.info(f"✅ AI analysis validated successfully")
            return analysis
        
        except Exception as e:
            self.logger.error(f"❌ AI resume analysis failed: {e}")
            raise e
    
    def _load_all_resumes(self):
        """Load all existing resume files"""
        if not os.path.exists(self.resumes_dir):
            return
        
        for filename in os.listdir(self.resumes_dir):
            if filename.endswith('.json'):
                resume_name = filename[:-5]  # Remove .json
                try:
                    resume_file = os.path.join(self.resumes_dir, filename)
                    with open(resume_file, 'r', encoding='utf-8') as f:
                        resume_data = json.load(f)
                    
                    self.resumes[resume_name] = resume_data
                    self.resume_profiles[resume_name] = resume_data.get('analysis', {})
                    
                except Exception as e:
                    self.logger.error(f"Error loading resume {filename}: {e}")
    
    def get_resume_names(self) -> List[str]:
        """Get list of available resume versions"""
        return list(self.resumes.keys())
    
    def find_best_resume_match(self, job_data: Dict, available_resumes: List[Dict] = None) -> Dict:
        """
        Find the best resume match for a given job.
        
        Args:
            job_data: Dictionary containing job information
            available_resumes: List of resume dictionaries (optional, uses loaded resumes if not provided)
            
        Returns:
            Dictionary with best resume match and score
        """
        # Use loaded resumes if none provided
        if available_resumes is None:
            available_resumes = list(self.resumes.values())
        
        if not available_resumes:
            return {
                'best_resume': None,
                'match_score': 0.0,
                'reasoning': 'No resumes available'
            }
        
        best_match = None
        best_score = 0.0
        best_reasoning = ""
        
        job_title = job_data.get('title', 'Unknown')
        
        for resume in available_resumes:
            try:
                # Calculate match score using rule-based approach
                analysis = self._calculate_resume_job_match(job_data, resume)
                
                score = analysis.get('match_score', 0.0)
                
                # Handle None values to fix the comparison error
                if score is not None and (best_score is None or score > best_score):
                    best_score = score
                    best_match = resume
                    best_reasoning = analysis.get('reasoning', '')
                
                print(f"📄 Resume '{resume.get('name', 'Unknown')}' vs '{job_title}': {score:.1f}%")
                
            except Exception as e:
                print(f"❌ Error analyzing resume '{resume.get('name', 'Unknown')}': {str(e)}")
                continue
        
        return {
            'best_resume': best_match,
            'match_score': best_score if best_score is not None else 0.0,
            'reasoning': best_reasoning
        }
    def match_job_to_resumes(self, job: Dict) -> Dict[str, float]:
        """
        Match a job against all resume versions and return compatibility scores
        
        Args:
            job: Job dictionary
            
        Returns:
            Dictionary with resume_name -> compatibility_score mapping
        """
        if not self.resumes:
            return {}
        
        scores = {}
        
        for resume_name, resume_data in self.resumes.items():
            analysis = self._calculate_resume_job_match(job, resume_data)
            score = analysis.get('match_score', 0.0)
            scores[resume_name] = score
        
        return scores
    
    def _calculate_resume_job_match(self, job: Dict, resume_data: Dict) -> Dict:
        """Calculate compatibility score between a job and specific resume - FIXED VERSION"""
        try:
            analysis = resume_data.get('analysis', {})
            if not analysis:
                return {'match_score': 0.0, 'reasoning': 'No resume analysis available'}
            
            score = 0
            reasons = []
            
            # Job title matching (25 points)
            job_title = job.get('title', '').lower()
            preferred_roles = [role.lower() for role in analysis.get('preferred_roles', [])]
            target_roles = [role.lower() for role in resume_data.get('target_roles', [])]
            
            all_target_roles = preferred_roles + target_roles
            title_match = False
            for role in all_target_roles:
                if any(word in job_title for word in role.split()):
                    score += 25
                    title_match = True
                    reasons.append(f"Title matches target role: {role}")
                    break
            
            if not title_match:
                reasons.append("No direct title match found")
            
            # Skills matching (20 points)
            job_description = job.get('description', '').lower()
            resume_skills = [skill.lower() for skill in analysis.get('skills', [])]
            
            skills_found = 0
            for skill in resume_skills:
                if skill in job_description:
                    skills_found += 1
            
            if resume_skills:
                skills_score = min((skills_found / len(resume_skills)) * 20, 20)
                score += skills_score
                reasons.append(f"Skills match: {skills_found}/{len(resume_skills)} skills found")
            
            # Experience level matching (15 points)
            resume_level = analysis.get('experience_level', '').lower()
            if resume_level in job_description:
                score += 15
                reasons.append(f"Experience level match: {resume_level}")
            elif 'senior' in resume_level and 'senior' in job_description:
                score += 15
                reasons.append("Senior level alignment")
            elif 'principal' in resume_level and ('principal' in job_description or 'lead' in job_description):
                score += 15
                reasons.append("Principal/Lead level alignment")
            
            # Industry matching (10 points)
            resume_industries = [ind.lower() for ind in analysis.get('industries', [])]
            industry_match = False
            for industry in resume_industries:
                if industry in job_description:
                    score += 10
                    industry_match = True
                    reasons.append(f"Industry match: {industry}")
                    break
            
            if not industry_match:
                reasons.append("No industry match found")
            
            # Keywords matching (15 points)
            resume_keywords = [kw.lower() for kw in analysis.get('keywords', [])]
            keywords_found = sum(1 for kw in resume_keywords if kw in job_description)
            
            if resume_keywords:
                keyword_score = min((keywords_found / len(resume_keywords)) * 15, 15)
                score += keyword_score
                reasons.append(f"Keywords match: {keywords_found}/{len(resume_keywords)} found")
            
            # Company size matching (10 points) - FIXED: Handle missing ai_analysis
            company_types = analysis.get('company_types', [])
            ai_analysis = job.get('ai_analysis', {})
            if isinstance(ai_analysis, dict):  # Make sure it's a dict, not string
                company_size = ai_analysis.get('company_size', '')
                if company_size and company_size in company_types:
                    score += 10
                    reasons.append("Company size preference match")
            
            # Salary alignment (5 points) - FIXED: Handle string salary_range
            salary_range = analysis.get('salary_range', '')
            job_salary_min = job.get('salary_min', 0)
            job_salary_max = job.get('salary_max', 999999)
            
            # Parse salary range if it's a string like "$120,000 - $180,000"
            if isinstance(salary_range, str) and salary_range and job_salary_min:
                try:
                    # Extract numbers from salary range string
                    import re
                    numbers = re.findall(r'[\d,]+', salary_range)
                    if len(numbers) >= 2:
                        resume_min = int(numbers[0].replace(',', ''))
                        resume_max = int(numbers[1].replace(',', ''))
                        
                        # Check if there's salary overlap
                        if job_salary_max >= resume_min and job_salary_min <= resume_max:
                            score += 5
                            reasons.append("Salary range alignment")
                            
                except (ValueError, IndexError, AttributeError):
                    # Skip salary matching if parsing fails
                    pass
            elif isinstance(salary_range, dict):
                # Handle dict format salary range
                resume_min = salary_range.get('min', 0)
                resume_max = salary_range.get('max', 999999)
                
                if job_salary_max >= resume_min and job_salary_min <= resume_max:
                    score += 5
                    reasons.append("Salary range alignment")
            
            final_score = min(score, 100)  # Cap at 100
            reasoning = "; ".join(reasons) if reasons else "Standard compatibility analysis"
            
            return {
                'match_score': final_score,
                'reasoning': reasoning
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating resume job match: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'match_score': 0.0,
                'reasoning': f"Error in analysis: {str(e)}"
            }
    
    def get_best_resume_for_job(self, job: Dict) -> Tuple[str, float]:
        """
        Find the best resume version for a specific job
        
        Returns:
            Tuple of (resume_name, compatibility_score)
        """
        scores = self.match_job_to_resumes(job)
        
        if not scores:
            return None, 0
        
        best_resume = max(scores.items(), key=lambda x: x[1])
        return best_resume
    
    def generate_job_search_keywords(self, resume_name: str = None) -> List[str]:
        """
        Generate smart job search keywords based on resume(s)
        
        Args:
            resume_name: Specific resume to use, or None for all resumes
            
        Returns:
            List of search keywords optimized for this person
        """
        if resume_name and resume_name in self.resume_profiles:
            profiles = [self.resume_profiles[resume_name]]
        else:
            profiles = list(self.resume_profiles.values())
        
        if not profiles:
            return ["Product Manager"]  # Fallback
        
        # Collect keywords from all relevant profiles
        all_keywords = set()
        
        for profile in profiles:
            # Add preferred roles
            all_keywords.update(profile.get('preferred_roles', []))
            
            # Add target roles from resume data
            resume_data = next((r for r in self.resumes.values() 
                              if r.get('analysis') == profile), {})
            all_keywords.update(resume_data.get('target_roles', []))
            
            # Add key skills as job titles
            skills = profile.get('skills', [])
            for skill in skills:
                if any(word in skill.lower() for word in ['manager', 'director', 'lead', 'engineer', 'analyst']):
                    all_keywords.add(skill)
        
        # Convert to list and prioritize
        keywords = list(all_keywords)
        
        # Sort by relevance (longer, more specific terms first)
        keywords.sort(key=lambda x: (len(x.split()), len(x)), reverse=True)
        
        return keywords[:10]  # Return top 10 keywords
    
    def get_resume_summary(self, resume_name: str) -> Dict:
        """Get a summary of a resume version"""
        if resume_name not in self.resumes:
            return {}
        
        resume_data = self.resumes[resume_name]
        analysis = resume_data.get('analysis', {})
        
        return {
            'name': resume_name,
            'target_roles': resume_data.get('target_roles', []),
            'experience_level': analysis.get('experience_level', 'Unknown'),
            'experience_years': analysis.get('experience_years', 0),
            'top_skills': analysis.get('skills', [])[:5],
            'industries': analysis.get('industries', []),
            'last_updated': resume_data.get('last_updated', 'Unknown')
        }
    
    def update_resume(self, resume_name: str, resume_text: str = None, target_roles: List[str] = None):
        """Update an existing resume"""
        if resume_name not in self.resumes:
            return False
        
        resume_data = self.resumes[resume_name]
        
        if resume_text:
            resume_data['text'] = resume_text
            # Re-analyze with AI
            resume_data['analysis'] = self._analyze_resume_with_ai(resume_text, target_roles)
        
        if target_roles:
            resume_data['target_roles'] = target_roles
        
        resume_data['last_updated'] = datetime.now().isoformat()
        
        # Save to file
        resume_file = os.path.join(self.resumes_dir, f"{resume_name}.json")
        with open(resume_file, 'w') as f:
            json.dump(resume_data, f, indent=2)
        
        # Update in memory
        self.resumes[resume_name] = resume_data
        self.resume_profiles[resume_name] = resume_data['analysis']
        
        return True


# Helper functions for easy integration
def setup_resume_system():
    """Initialize the resume-based matching system"""
    from config.settings import OPENAI_API_KEY
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key required for resume analysis")
        return None
    
    return ResumeBasedJobMatcher(OPENAI_API_KEY)

def add_resume_from_file(matcher: ResumeBasedJobMatcher, resume_path: str, resume_name: str, target_roles: List[str]):
    """Add a resume from a text file"""
    try:
        with open(resume_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
        
        return matcher.add_resume(resume_name, resume_text, target_roles)
    except Exception as e:
        print(f"Error reading resume file {resume_path}: {e}")
        return False

def match_job_to_resumes(self, job: Dict) -> Dict[str, float]:
    if not self.resumes:
        return {}
    
    scores = {}
    
    for resume_name, resume_data in self.resumes.items():
        analysis = self._calculate_resume_job_match(job, resume_data)
        score = analysis.get('match_score', 0.0)
        
        # DEBUG: Let's see what we're getting
        print(f"DEBUG: {resume_name} analysis: {analysis}")
        print(f"DEBUG: {resume_name} score type: {type(score)}, value: {score}")
        
        scores[resume_name] = score
    
    return scores

# Test function
def test_resume_matcher():
    """Test the resume matching system"""
    matcher = setup_resume_system()
    if not matcher:
        return
    
    # Example resume text
    sample_resume = """
    John Smith
    Senior Product Manager
    
    Experience:
    - 8 years of product management experience at tech companies
    - Led cross-functional teams of 15+ people
    - Launched 5 major product features with 2M+ users
    - Expert in data analysis, A/B testing, and user research
    - Experience with Agile/Scrum methodologies
    
    Skills:
    - Product Strategy & Roadmapping
    - Data Analysis (SQL, Python)
    - User Experience Design
    - Market Research
    - Team Leadership
    
    Companies: Microsoft, Amazon, startup experience
    """
    
    # Add sample resume
    matcher.add_resume(
        "senior_pm", 
        sample_resume, 
        ["Senior Product Manager", "Principal Product Manager", "Product Director"]
    )
    
    print("✅ Resume system test completed!")
    print(f"Available resumes: {matcher.get_resume_names()}")
    
    # Test keyword generation
    keywords = matcher.generate_job_search_keywords("senior_pm")
    print(f"Generated keywords: {keywords}")

if __name__ == "__main__":
    test_resume_matcher()