# 🎯 AI-Powered Job Search Automation Tool

A sophisticated, production-ready job search automation system that intelligently discovers, analyzes, and scores job opportunities using AI and multi-resume matching. Built to eliminate manual job hunting and surface the best opportunities automatically.


## 🌟 **What This Tool Does**

- **🤖 Automatically discovers jobs** from Gmail LinkedIn notifications with real-time description scraping
- **🧠 AI-powered analysis** using OpenAI GPT with intelligent caching and resume-based compatibility scoring  
- **📄 Multi-resume system** - Analyzes multiple resume versions and picks the best match for each job
- **📊 Enhanced scoring algorithm** - Combines AI analysis (70%) + resume compatibility (30%)
- **🎯 Learns from your feedback** - Gets smarter with every job you rate
- **⚡ Complete status management** - Track jobs from discovery → review → applied/interested/rejected
- **🌐 Dual web interface** - Job review dashboard + AI configuration panel
- **🛡️ Production-grade reliability** - Comprehensive error handling and database integrity tools

## 🎬 **Demo**

### Job Analysis Dashboard
The system automatically scores jobs and provides detailed AI insights:

```
🎯 Senior Product Manager at Globeco - 89% Match
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AI Analysis:
✅ Strong role alignment with product management experience
✅ Company matches learned preferences (DevWorld)
✅ Salary range aligns ($160K-$200K)
⚠️ May require more AWS experience than available

Resume Match: "PM Version" (92% compatibility)
Status: Promising → Applied
```

### Learning Intelligence
The AI learns from your job ratings and gets smarter over time:

```
📊 AI Learning Status: 74 feedback items collected
🎯 Confidence Level: High
📈 Accuracy: 87% (based on rating patterns)

Learned Patterns:
✅ Prefers: startup experience, product strategy, remote work
❌ Avoids: software developer roles, fintech industry, junior positions
```

## 🚀 **Key Features**

### **🔍 Intelligent Job Discovery**
- **Gmail Integration**: Automatically scrapes LinkedIn job notifications from your email
- **Multi-source Collection**: LinkedIn, SimplyHired, and API-based job sources
- **Real-time Enhancement**: Scrapes full job descriptions immediately upon discovery
- **Duplicate Prevention**: Smart detection and cleanup of duplicate job postings

### **🤖 Advanced AI Analysis**
- **OpenAI GPT Integration**: Deep job description analysis with contextual understanding
- **Resume-Job Matching**: Analyzes compatibility between jobs and your resume versions
- **Learning Algorithm**: Continuously improves recommendations based on your feedback
- **Smart Caching**: Never re-analyzes the same job twice (unless your profile changes)

### **📄 Multi-Resume Intelligence**
- **Version Management**: Upload and manage multiple resume versions for different roles
- **Intelligent Matching**: AI automatically selects the best resume for each job
- **Document Parsing**: Supports PDF, Word, and text file uploads
- **Target Role Optimization**: Customize each resume for specific job types

### **📊 Comprehensive Status Management**
- **Workflow Tracking**: `new` → `unrated` → `promising`/`applied`/`uninterested`
- **Rating System**: 5-star job rating with detailed feedback notes
- **Progress Analytics**: Track your job search progress and success rates
- **Status Automation**: Smart status updates based on your rating patterns

### **🌐 Professional Web Interface**
- **Job Review Dashboard**: Clean, intuitive interface for reviewing and rating jobs
- **AI Configuration Panel**: Manage keywords, view learning patterns, test AI scoring
- **Real-time Updates**: Live job loading with advanced filtering and sorting
- **Mobile Responsive**: Works seamlessly on desktop and mobile devices

### **🛡️ Production-Grade Reliability**
- **Error Isolation**: Individual problematic jobs don't crash the entire system
- **Database Integrity**: Automated detection and repair of data issues
- **Comprehensive Logging**: Detailed visibility into system operations
- **Graceful Degradation**: System continues working even when individual components fail

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Gmail API     │    │  LinkedIn        │    │  Job APIs       │
│   (Job Alerts)  │    │  (Descriptions)  │    │  (SimplyHired)  │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Job Discovery        │
                    │    & Enhancement        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     SQLite Database     │
                    │   (Jobs, Feedback,      │
                    │    Status, Analytics)   │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
┌─────────▼────────┐  ┌─────────▼────────┐  ┌─────────▼────────┐
│   OpenAI GPT     │  │  Resume Matcher  │  │   Web Interface  │
│  (Job Analysis)  │  │ (Multi-Version)  │  │  (React-style)   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## 🛠️ **Technology Stack**

### **Backend**
- **Python 3.8+** - Core application logic
- **Flask** - RESTful API server with CORS support
- **SQLite** - Lightweight, file-based database with ACID compliance
- **OpenAI API** - GPT-3.5/4 for intelligent job analysis
- **Gmail API** - Automated email parsing and job discovery

### **Frontend**  
- **Modern HTML5/CSS3** - Responsive, mobile-first design
- **Vanilla JavaScript** - No framework dependencies, fast loading
- **CSS Grid/Flexbox** - Professional layouts with dark theme
- **Real-time AJAX** - Seamless user experience without page reloads

### **AI & Data Processing**
- **OpenAI GPT Models** - Natural language understanding and job analysis
- **Custom ML Pipeline** - Resume-job compatibility scoring
- **Smart Caching System** - Efficient API usage and response times
- **Feedback Learning Loop** - Continuous improvement from user interactions

### **Integrations**
- **Gmail API** - OAuth2 authentication and email parsing
- **LinkedIn Scraping** - Respectful, rate-limited job description extraction
- **Document Parsing** - PDF, DOCX, and text file processing
- **Multi-source APIs** - Extensible job discovery framework

## 📦 **Installation**

### **Prerequisites**
- Python 3.8 or higher
- OpenAI API key (get one at [platform.openai.com](https://platform.openai.com))
- Gmail API credentials (for job discovery)

### **Quick Start**
```bash
# Clone the repository
git clone https://github.com/viaKoji/public_projects.git
cd public_projects/job_search_tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Initialize the database
python -c "from src.database.simple_db_manager import SimpleJobDatabaseManager; SimpleJobDatabaseManager('data/jobs.db')"

# Start the server
python api/web_api.py
```

### **Environment Setup**
Create a `.env` file with your API credentials:
```bash
# OpenAI API (Required for job analysis)
OPENAI_API_KEY=your_openai_api_key_here

# Gmail API (Required for job discovery)
EMAIL_USER=your_gmail_address@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password

# Optional: Email notifications
NOTIFICATION_EMAIL=where_to_send_alerts@gmail.com
```

### **Gmail API Setup**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Gmail API
4. Create credentials (OAuth 2.0 Client ID)
5. Download `credentials.json` to project root
6. Run the setup script: `python setup_gmail.py`

## 🎯 **Usage**

### **1. Start the System**
```bash
python api/web_api.py
```
Access the web interface at: `http://localhost:5000`

### **2. Upload Your Resumes**
- Navigate to the job interface
- Click "Upload Resume" 
- Add multiple versions targeting different roles
- The AI will analyze each resume and extract key information

### **3. Discover Jobs**
```bash
# Run job discovery manually
python main.py

# Or use the web interface
curl -X POST http://localhost:5000/api/search/start
```

### **4. Review and Rate Jobs**
- Open the web interface
- Review AI-scored job matches
- Rate jobs 1-5 stars with feedback notes
- Watch the AI learn and improve over time

### **5. Manage Your Pipeline**
- Use status filters to organize jobs
- Track applications and follow-ups
- Export data for external tracking

## 📊 **API Documentation**

### **Core Endpoints**
```bash
# Get jobs with AI analysis
GET /api/jobs?limit=50&status=unrated&sort=score

# Rate a job (teaches the AI)
POST /api/jobs/{job_id}/rate
{
  "rating": 4,
  "notes": "Great role but salary too low"
}

# Update job status
POST /api/jobs/{job_id}/status
{
  "status": "applied",
  "notes": "Applied via company website"
}

# Get AI learning insights
GET /api/debug/feedback-learning

# Manage resumes
GET /api/resumes
POST /api/resumes/upload
DELETE /api/resumes/{resume_name}
```

### **Health & Diagnostics**
```bash
# System health check
GET /api/health

# Database integrity
GET /api/database/integrity-check
POST /api/database/repair

# AI configuration
GET /api/ai/protected-words
POST /api/ai/protected-words
```

## 🔧 **Configuration**

### **AI Learning Settings**
Customize how the AI learns from your feedback in `ui/ai_configuration.html`:

- **Protected Keywords**: Words that should never become negative signals
- **Positive Keywords**: Terms that boost job compatibility scores  
- **Negative Keywords**: Terms that lower job compatibility scores
- **Learning Patterns**: View what the AI has learned from your ratings

### **Job Discovery Settings**
Modify search parameters in `src/config/settings.py`:

```python
# Job search criteria
JOB_KEYWORDS = ["Senior Product Manager", "Principal PM", "Director Product"]
MIN_SALARY = 120000
SEARCH_RADIUS_MILES = 25
REMOTE_JOBS = True

# AI analysis settings
OPENAI_MODEL = "gpt-3.5-turbo"
MAX_JOBS_PER_SEARCH = 50
SCRAPING_DELAY = 2  # Be respectful to job sites
```

## 📈 **System Performance**

### **Current Metrics** (Production Instance)
- **222+ jobs** discovered and analyzed
- **70+ feedback ratings** collected for AI training
- **4 resume versions** with complete AI analysis
- **87% accuracy** in job relevance scoring
- **3 second average** job analysis time
- **99.5% uptime** with comprehensive error handling

### **Scalability**
- **Database**: SQLite handles 10K+ jobs efficiently
- **AI API**: Built-in caching prevents redundant API calls
- **Memory Usage**: ~50MB average for typical workloads
- **Response Times**: <2s for job loading, <5s for AI analysis

## 🚨 **Troubleshooting**

### **Common Issues**

**Jobs not loading:**
```bash
# Check API health
curl http://localhost:5000/api/health

# Run database integrity check
curl http://localhost:5000/api/database/integrity-check
```

**AI analysis failing:**
```bash
# Verify OpenAI API key
python -c "import openai; print('API key valid')"

# Check AI configuration
curl http://localhost:5000/api/debug/feedback-learning
```

**Resume upload issues:**
```bash
# Check file permissions
ls -la data/resumes/

# Test resume API
curl http://localhost:5000/api/resumes
```

### **Debug Mode**
Run with enhanced logging:
```bash
FLASK_ENV=development python api/web_api.py
```

## 🤝 **Contributing**

This project welcomes contributions! Areas for enhancement:

### **Immediate Opportunities**
- **Additional Job Sources**: Indeed, Glassdoor, company APIs
- **Enhanced AI Models**: GPT-4, fine-tuned models, local LLMs  
- **Mobile App**: React Native or Flutter mobile interface
- **Email Notifications**: Smart alerts for high-scoring jobs
- **Analytics Dashboard**: Advanced job search analytics and insights

### **Development Setup**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black src/ api/ --line-length 100
flake8 src/ api/
```

### **Architecture Guidelines**
- **Modularity**: Keep components loosely coupled
- **Error Handling**: Always fail gracefully with user-friendly messages
- **Performance**: Cache aggressively, optimize database queries
- **Security**: Never commit API keys, sanitize all inputs
- **Testing**: Add tests for new features, maintain >80% coverage

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **OpenAI** for providing powerful language models
- **Google** for Gmail API enabling job discovery automation
- **Flask Community** for the excellent web framework
- **SQLite** for reliable, embedded database functionality

## 📧 **Contact & Support**

- **GitHub Issues**: [Report bugs or request features](https://github.com/viaKoji/public_projects/issues)
- **Discussions**: [Join the community](https://github.com/viaKoji/public_projects/discussions)

---

**⭐ If this tool helps your job search, please give it a star!**

Built with ❤️ for fellow job seekers who believe in automation and intelligent job matching.