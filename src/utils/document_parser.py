# Version 3.2 - Resume Document Parser
# src/utils/document_parser.py
import os
import logging
from typing import Dict, Optional
import tempfile

class ResumeDocumentParser:
    """
    Parse resume documents (PDF, DOCX, DOC, TXT) into clean text
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt']
    
    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.supported_formats
    
    def parse_document(self, file_path: str) -> Dict[str, str]:
        """
        Parse a resume document and extract text
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary with 'text', 'filename', 'format', and 'status'
        """
        try:
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename.lower())[1]
            
            if not self.is_supported_format(filename):
                return {
                    'text': '',
                    'filename': filename,
                    'format': file_ext,
                    'status': 'unsupported_format',
                    'error': f'Unsupported format: {file_ext}. Supported: {self.supported_formats}'
                }
            
            # Parse based on file type
            if file_ext == '.pdf':
                text = self._parse_pdf(file_path)
            elif file_ext in ['.docx', '.doc']:
                text = self._parse_word(file_path)
            elif file_ext == '.txt':
                text = self._parse_text(file_path)
            else:
                raise ValueError(f"Unsupported format: {file_ext}")
            
            # Clean and validate text
            cleaned_text = self._clean_text(text)
            
            if len(cleaned_text.strip()) < 100:
                return {
                    'text': cleaned_text,
                    'filename': filename,
                    'format': file_ext,
                    'status': 'too_short',
                    'error': 'Extracted text is too short (less than 100 characters). Document may be poorly formatted or corrupted.'
                }
            
            return {
                'text': cleaned_text,
                'filename': filename,
                'format': file_ext,
                'status': 'success',
                'word_count': len(cleaned_text.split()),
                'char_count': len(cleaned_text)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing document {file_path}: {e}")
            return {
                'text': '',
                'filename': os.path.basename(file_path) if file_path else 'unknown',
                'format': file_ext if 'file_ext' in locals() else 'unknown',
                'status': 'parse_error',
                'error': str(e)
            }
    
    def _parse_pdf(self, file_path: str) -> str:
        """Parse PDF file"""
        try:
            import PyPDF2
            
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
            
            return text
            
        except ImportError:
            # Fallback to pdfplumber if PyPDF2 not available
            try:
                import pdfplumber
                
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                
                return text
                
            except ImportError:
                raise ImportError("PDF parsing requires PyPDF2 or pdfplumber. Install with: pip install PyPDF2 pdfplumber")
    
    def _parse_word(self, file_path: str) -> str:
        """Parse Word document (.docx, .doc)"""
        try:
            from docx import Document
            
            # For .docx files
            if file_path.lower().endswith('.docx'):
                doc = Document(file_path)
                text = ""
                
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                
                # Also extract text from tables
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            text += cell.text + " "
                        text += "\n"
                
                return text
            
            # For .doc files (older format)
            else:
                try:
                    import mammoth
                    
                    with open(file_path, 'rb') as docx_file:
                        result = mammoth.extract_raw_text(docx_file)
                        return result.value
                        
                except ImportError:
                    raise ImportError("DOC file parsing requires mammoth. Install with: pip install mammoth")
                    
        except ImportError:
            raise ImportError("Word document parsing requires python-docx and mammoth. Install with: pip install python-docx mammoth")
    
    def _parse_text(self, file_path: str) -> str:
        """Parse plain text file"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        return file.read()
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, read as binary and decode with errors='ignore'
            with open(file_path, 'rb') as file:
                return file.read().decode('utf-8', errors='ignore')
                
        except Exception as e:
            raise Exception(f"Error reading text file: {e}")
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        lines = []
        for line in text.split('\n'):
            cleaned_line = ' '.join(line.split())  # Normalize whitespace
            if cleaned_line:  # Skip empty lines
                lines.append(cleaned_line)
        
        # Join with single newlines
        cleaned = '\n'.join(lines)
        
        # Remove excessive newlines (more than 2)
        import re
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def get_requirements_info(self) -> Dict:
        """Get information about required dependencies"""
        requirements = {
            'pdf_parsing': {
                'packages': ['PyPDF2', 'pdfplumber'],
                'install_command': 'pip install PyPDF2 pdfplumber',
                'description': 'Required for PDF resume parsing'
            },
            'word_parsing': {
                'packages': ['python-docx', 'mammoth'],
                'install_command': 'pip install python-docx mammoth',
                'description': 'Required for Word document (.docx, .doc) parsing'
            }
        }
        
        # Check which packages are available
        available_packages = []
        missing_packages = []
        
        try:
            import PyPDF2
            available_packages.append('PyPDF2')
        except ImportError:
            missing_packages.append('PyPDF2')
        
        try:
            import pdfplumber
            available_packages.append('pdfplumber')
        except ImportError:
            missing_packages.append('pdfplumber')
        
        try:
            import docx
            available_packages.append('python-docx')
        except ImportError:
            missing_packages.append('python-docx')
        
        try:
            import mammoth
            available_packages.append('mammoth')
        except ImportError:
            missing_packages.append('mammoth')
        
        return {
            'requirements': requirements,
            'available_packages': available_packages,
            'missing_packages': missing_packages,
            'pdf_support': any(pkg in available_packages for pkg in ['PyPDF2', 'pdfplumber']),
            'word_support': any(pkg in available_packages for pkg in ['python-docx', 'mammoth'])
        }


# Helper function to check if document parsing is available
def check_document_parsing_support():
    """Check what document parsing features are available"""
    parser = ResumeDocumentParser()
    info = parser.get_requirements_info()
    
    print("📄 DOCUMENT PARSING SUPPORT CHECK")
    print("=" * 50)
    
    print(f"📋 Available packages: {', '.join(info['available_packages']) if info['available_packages'] else 'None'}")
    print(f"❌ Missing packages: {', '.join(info['missing_packages']) if info['missing_packages'] else 'None'}")
    print()
    
    print(f"PDF Support: {'✅ Available' if info['pdf_support'] else '❌ Missing'}")
    print(f"Word Support: {'✅ Available' if info['word_support'] else '❌ Missing'}")
    print()
    
    if info['missing_packages']:
        print("To install missing packages:")
        if any(pkg in info['missing_packages'] for pkg in ['PyPDF2', 'pdfplumber']):
            print("  pip install PyPDF2 pdfplumber")
        if any(pkg in info['missing_packages'] for pkg in ['python-docx', 'mammoth']):
            print("  pip install python-docx mammoth")
    
    return info


# Test function
def test_document_parser():
    """Test the document parser with sample files"""
    parser = ResumeDocumentParser()
    
    print("🧪 TESTING DOCUMENT PARSER")
    print("=" * 40)
    
    # Test with sample text
    test_text = """
    John Smith
    Senior Product Manager
    
    Experience:
    • 8 years of product management experience
    • Led cross-functional teams of 15+ people
    • Launched 5 major product features
    
    Skills:
    • Product Strategy & Roadmapping
    • Data Analysis (SQL, Python)
    • User Experience Design
    """
    
    # Create temporary text file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_text)
        temp_file = f.name
    
    try:
        result = parser.parse_document(temp_file)
        
        print(f"✅ Test Results:")
        print(f"   Status: {result['status']}")
        print(f"   Format: {result['format']}")
        print(f"   Word Count: {result.get('word_count', 0)}")
        print(f"   Text Preview: {result['text'][:100]}...")
        
    finally:
        # Clean up
        os.unlink(temp_file)
    
    # Check parsing support
    info = parser.get_requirements_info()
    print(f"\n📦 Parsing Support:")
    print(f"   PDF: {'✅' if info['pdf_support'] else '❌'}")
    print(f"   Word: {'✅' if info['word_support'] else '❌'}")


if __name__ == "__main__":
    check_document_parsing_support()
    print()
    test_document_parser()