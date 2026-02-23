"""
ATS (Applicant Tracking System) with BM25
Supports flexible field definitions for organizations to customize matching criteria
"""

import os
import json
import pickle
import hashlib
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
import numpy as np
from collections import defaultdict

# Core libraries
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import string
import re

# BM25 implementation
try:
    from rank_bm25 import BM25Okapi, BM25L, BM25Plus
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'rank_bm25'])
    from rank_bm25 import BM25Okapi, BM25L, BM25Plus

# Document processing
try:
    import PyPDF2
except ImportError:
    subprocess.check_call(['pip', 'install', 'PyPDF2'])
    import PyPDF2

try:
    import docx
except ImportError:
    subprocess.check_call(['pip', 'install', 'python-docx'])
    import docx

# For UI
try:
    from tabulate import tabulate
except ImportError:
    subprocess.check_call(['pip', 'install', 'tabulate'])
    from tabulate import tabulate

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')

@dataclass
class FieldDefinition:
    """Define a field that organizations can use for matching"""
    name: str
    description: str
    weight: float = 1.0  # Importance weight for scoring
    required: bool = False  # Is this field required?
    keywords: List[str] = field(default_factory=list)  # Default keywords to look for
    min_experience: Optional[int] = None  # For experience fields
    education_levels: List[str] = field(default_factory=list)  # For education fields

@dataclass
class OrganizationProfile:
    """Organization profile with custom matching preferences"""
    id: str
    name: str
    industry: str
    field_definitions: List[FieldDefinition]
    matching_threshold: float = 0.3  # Minimum score to consider
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Candidate:
    """Candidate profile"""
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    resume_path: Optional[str] = None
    resume_text: str = ""
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    applied_jobs: List[str] = field(default_factory=list)
    upload_date: datetime = field(default_factory=datetime.now)

@dataclass
class JobDescription:
    """Job description created by organization"""
    id: str
    organization_id: str
    title: str
    description: str
    required_fields: Dict[str, Any]  # Field requirements
    custom_weights: Dict[str, float]  # Override default field weights
    posted_date: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active, closed, draft

@dataclass
class MatchResult:
    """Match result with explanation"""
    candidate_id: str
    job_id: str
    overall_score: float
    field_scores: Dict[str, float]
    explanations: List[str]
    matched_keywords: Dict[str, List[str]]
    missing_requirements: List[str]
    rank: Optional[int] = None

class TextProcessor:
    """Advanced text preprocessing"""
    
    def __init__(self, use_lemmatization=True, remove_stopwords=True):
        self.use_lemmatization = use_lemmatization
        self.remove_stopwords = remove_stopwords
        self.lemmatizer = WordNetLemmatizer() if use_lemmatization else None
        self.stop_words = set(stopwords.words('english')) if remove_stopwords else set()
        self.punctuation = set(string.punctuation)
        
        # Common resume sections
        self.section_patterns = {
            'skills': r'(?i)(technical skills?|skills?|competencies|expertise)',
            'experience': r'(?i)(work experience|professional experience|employment|work history)',
            'education': r'(?i)(education|academic background|qualifications)',
            'projects': r'(?i)(projects|personal projects|key projects)',
            'certifications': r'(?i)(certifications?|licenses?|credentials)'
        }
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^\w\s\.\-@]', ' ', text)
        
        return text.strip()
    
    def extract_sections(self, text: str) -> Dict[str, str]:
        """Extract different sections from resume"""
        sections = {}
        lines = text.split('\n')
        current_section = 'other'
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line is a section header
            found_section = False
            for section_name, pattern in self.section_patterns.items():
                if re.match(pattern, line, re.IGNORECASE):
                    if section_content:
                        sections[current_section] = ' '.join(section_content)
                    current_section = section_name
                    section_content = []
                    found_section = True
                    break
            
            if not found_section:
                section_content.append(line)
        
        # Add last section
        if section_content:
            sections[current_section] = ' '.join(section_content)
        
        return sections
    
    def extract_years_experience(self, text: str) -> Optional[float]:
        """Extract years of experience from text"""
        patterns = [
            r'(\d+)\+?\s*years?',
            r'(\d+)\s*years?\s*of\s*experience',
            r'experience\s*of\s*(\d+)\s*years?',
            r'(\d+)\s*yr?s?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return float(matches[0])
                except ValueError:
                    pass
        return None
    
    def extract_education_level(self, text: str) -> List[str]:
        """Extract education level from text"""
        education_keywords = {
            'phd': ['phd', 'doctorate', 'doctoral'],
            'masters': ['master', 'mba', 'msc', 'ma', 'm.s.', 'm.a.'],
            'bachelors': ['bachelor', 'bsc', 'ba', 'b.s.', 'b.a.', 'undergraduate'],
            'associate': ['associate', 'a.a.', 'a.s.'],
            'diploma': ['diploma', 'certificate']
        }
        
        found_levels = []
        text_lower = text.lower()
        
        for level, keywords in education_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found_levels.append(level)
                    break
        
        return found_levels
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize and preprocess text"""
        if not text:
            return []
        
        # Clean text
        text = self.clean_text(text)
        
        # Tokenize
        tokens = word_tokenize(text.lower())
        
        # Process tokens
        processed_tokens = []
        for token in tokens:
            # Remove punctuation
            if token in self.punctuation:
                continue
            
            # Remove stopwords
            if self.remove_stopwords and token in self.stop_words:
                continue
            
            # Lemmatize
            if self.use_lemmatization and self.lemmatizer:
                token = self.lemmatizer.lemmatize(token)
            
            if len(token) > 1:  # Remove single characters
                processed_tokens.append(token)
        
        return processed_tokens

class DocumentProcessor:
    """Handle document loading and processing"""
    
    def __init__(self, text_processor: TextProcessor):
        self.text_processor = text_processor
        self.supported_formats = {'.pdf', '.docx', '.doc', '.txt'}
    
    def load_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
        return text
    
    def load_docx(self, file_path: str) -> str:
        """Extract text from DOCX"""
        text = ""
        try:
            doc = docx.Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error reading DOCX {file_path}: {e}")
        return text
    
    def load_text(self, file_path: str) -> str:
        """Load text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""
    
    def process_resume(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Process resume file and extract information"""
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            text = self.load_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            text = self.load_docx(file_path)
        elif ext == '.txt':
            text = self.load_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
        
        # Extract sections and information
        sections = self.text_processor.extract_sections(text)
        years_exp = self.text_processor.extract_years_experience(text)
        education = self.text_processor.extract_education_level(text)
        
        extracted_info = {
            'sections': sections,
            'years_experience': years_exp,
            'education_levels': education,
            'full_text': text
        }
        
        return text, extracted_info

class ATS_BM25:
    """
    Main ATS system with BM25 and customizable field matching
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.text_processor = TextProcessor()
        self.document_processor = DocumentProcessor(self.text_processor)
        
        # Data storage
        self.organizations: Dict[str, OrganizationProfile] = {}
        self.candidates: Dict[str, Candidate] = {}
        self.jobs: Dict[str, JobDescription] = {}
        self.matches: Dict[str, List[MatchResult]] = defaultdict(list)
        
        # BM25 models (one per organization/job type)
        self.bm25_models: Dict[str, Any] = {}
        self.corpus: Dict[str, List] = {}
        
        if model_path and os.path.exists(model_path):
            self.load_system(model_path)
    
    def register_organization(self, org_profile: OrganizationProfile) -> str:
        """Register a new organization"""
        self.organizations[org_profile.id] = org_profile
        self.bm25_models[org_profile.id] = None
        self.corpus[org_profile.id] = []
        print(f"Organization '{org_profile.name}' registered successfully!")
        return org_profile.id
    
    def create_job(self, job: JobDescription) -> str:
        """Create a new job posting"""
        self.jobs[job.id] = job
        
        # Add to organization's corpus for matching
        org_id = job.organization_id
        if org_id not in self.corpus:
            self.corpus[org_id] = []
        
        # Tokenize job description
        tokens = self.text_processor.tokenize(job.description)
        self.corpus[org_id].append({
            'job_id': job.id,
            'tokens': tokens,
            'requirements': job.required_fields
        })
        
        # Rebuild BM25 model for this organization
        self._rebuild_org_model(org_id)
        
        print(f"Job '{job.title}' created successfully!")
        return job.id
    
    def add_candidate(self, candidate: Candidate, resume_file: Optional[str] = None) -> str:
        """Add a new candidate with resume"""
        if resume_file and os.path.exists(resume_file):
            text, extracted_info = self.document_processor.process_resume(resume_file)
            candidate.resume_text = text
            candidate.extracted_fields = extracted_info
            candidate.resume_path = resume_file
        
        self.candidates[candidate.id] = candidate
        print(f"Candidate '{candidate.name}' added successfully!")
        return candidate.id
    
    def _rebuild_org_model(self, org_id: str):
        """Rebuild BM25 model for an organization"""
        if org_id not in self.corpus or not self.corpus[org_id]:
            return
        
        # Extract tokens for BM25
        corpus_tokens = [item['tokens'] for item in self.corpus[org_id]]
        self.bm25_models[org_id] = BM25Okapi(corpus_tokens)
    
    def match_candidate_to_jobs(self, candidate_id: str, org_id: str, top_k: int = 10) -> List[MatchResult]:
        """Match a candidate to all jobs in an organization"""
        if candidate_id not in self.candidates:
            raise ValueError(f"Candidate {candidate_id} not found")
        
        if org_id not in self.organizations:
            raise ValueError(f"Organization {org_id} not found")
        
        if org_id not in self.bm25_models or self.bm25_models[org_id] is None:
            raise ValueError(f"No jobs found for organization {org_id}")
        
        candidate = self.candidates[candidate_id]
        org = self.organizations[org_id]
        
        # Get candidate tokens
        candidate_tokens = self.text_processor.tokenize(candidate.resume_text)
        
        # Get BM25 scores for all jobs
        scores = self.bm25_models[org_id].get_scores(candidate_tokens)
        
        # Calculate detailed matches for each job
        results = []
        for idx, (job_data, bm25_score) in enumerate(zip(self.corpus[org_id], scores)):
            job = self.jobs[job_data['job_id']]
            
            # Calculate field-based scores
            field_scores, explanations, matched_keywords, missing = self._calculate_field_scores(
                candidate, job, org.field_definitions
            )
            
            # Combine BM25 score with field scores
            overall_score = self._calculate_overall_score(
                bm25_score, field_scores, job.custom_weights
            )
            
            # Only include if above threshold
            if overall_score >= org.matching_threshold:
                result = MatchResult(
                    candidate_id=candidate_id,
                    job_id=job.id,
                    overall_score=overall_score,
                    field_scores=field_scores,
                    explanations=explanations,
                    matched_keywords=matched_keywords,
                    missing_requirements=missing
                )
                results.append(result)
        
        # Sort by overall score and assign ranks
        results.sort(key=lambda x: x.overall_score, reverse=True)
        for i, result in enumerate(results[:top_k], 1):
            result.rank = i
        
        # Store matches
        self.matches[candidate_id].extend(results)
        
        return results[:top_k]
    
    def match_job_to_candidates(self, job_id: str, top_k: int = 10) -> List[MatchResult]:
        """Match a job to all candidates"""
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        org = self.organizations[job.organization_id]
        
        results = []
        job_tokens = self.text_processor.tokenize(job.description)
        
        for candidate_id, candidate in self.candidates.items():
            # Get candidate tokens
            candidate_tokens = self.text_processor.tokenize(candidate.resume_text)
            
            # Calculate similarity (simplified version)
            # In production, you'd want to use a proper BM25 model for candidates
            common_tokens = set(job_tokens) & set(candidate_tokens)
            similarity = len(common_tokens) / max(len(set(job_tokens)), 1)
            
            # Calculate field scores
            field_scores, explanations, matched_keywords, missing = self._calculate_field_scores(
                candidate, job, org.field_definitions
            )
            
            overall_score = (similarity + sum(field_scores.values())) / 2
            
            if overall_score >= org.matching_threshold:
                result = MatchResult(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    overall_score=overall_score,
                    field_scores=field_scores,
                    explanations=explanations,
                    matched_keywords=matched_keywords,
                    missing_requirements=missing
                )
                results.append(result)
        
        results.sort(key=lambda x: x.overall_score, reverse=True)
        for i, result in enumerate(results[:top_k], 1):
            result.rank = i
        
        return results[:top_k]
    
    def _calculate_field_scores(self, candidate: Candidate, job: JobDescription, 
                               field_defs: List[FieldDefinition]) -> Tuple[Dict, List, Dict, List]:
        """Calculate scores for each field with explanations"""
        field_scores = {}
        explanations = []
        matched_keywords = defaultdict(list)
        missing_requirements = []
        
        candidate_text = candidate.resume_text.lower()
        
        for field_def in field_defs:
            field_name = field_def.name
            required_value = job.required_fields.get(field_name)
            
            if not required_value:
                field_scores[field_name] = 0
                continue
            
            score = 0
            explanation_parts = []
            
            # Check for keywords
            if field_def.keywords:
                found_keywords = []
                for keyword in field_def.keywords:
                    if keyword.lower() in candidate_text:
                        found_keywords.append(keyword)
                        matched_keywords[field_name].append(keyword)
                
                if found_keywords:
                    keyword_score = len(found_keywords) / len(field_def.keywords)
                    score += keyword_score * 0.5
                    explanation_parts.append(f"Found keywords: {', '.join(found_keywords[:3])}")
            
            # Check experience requirement
            if field_def.min_experience and candidate.extracted_fields.get('years_experience'):
                candidate_exp = candidate.extracted_fields['years_experience']
                if candidate_exp >= field_def.min_experience:
                    score += 0.3
                    explanation_parts.append(f"Experience: {candidate_exp}+ years")
                else:
                    missing_requirements.append(f"Need {field_def.min_experience}+ years experience")
            
            # Check education requirement
            if field_def.education_levels and candidate.extracted_fields.get('education_levels'):
                candidate_edu = candidate.extracted_fields['education_levels']
                matching_levels = set(candidate_edu) & set(field_def.education_levels)
                if matching_levels:
                    score += 0.2
                    explanation_parts.append(f"Education: {', '.join(matching_levels)}")
                else:
                    missing_requirements.append(f"Missing education: {', '.join(field_def.education_levels)}")
            
            # Apply field weight
            weight = job.custom_weights.get(field_name, field_def.weight)
            field_scores[field_name] = score * weight
            
            if explanation_parts:
                explanations.append(f"{field_name}: {', '.join(explanation_parts)}")
        
        return field_scores, explanations, dict(matched_keywords), missing_requirements
    
    def _calculate_overall_score(self, bm25_score: float, field_scores: Dict, 
                                custom_weights: Dict) -> float:
        """Calculate overall score combining BM25 and field scores"""
        # Normalize BM25 score to 0-1 range (simple min-max for now)
        bm25_norm = min(bm25_score / 10, 1.0)  # Adjust based on your BM25 scores
        
        # Average field scores
        field_avg = sum(field_scores.values()) / max(len(field_scores), 1)
        
        # Weighted combination (adjust weights as needed)
        overall = (0.4 * bm25_norm) + (0.6 * field_avg)
        
        return round(overall, 3)
    
    def get_match_explanation(self, match_result: MatchResult) -> str:
        """Get detailed explanation for a match"""
        explanation = []
        explanation.append("=" * 50)
        explanation.append(f"MATCH ANALYSIS (Rank #{match_result.rank})")
        explanation.append("=" * 50)
        explanation.append(f"Overall Score: {match_result.overall_score:.3f}")
        
        explanation.append("\n📊 FIELD SCORES:")
        for field, score in match_result.field_scores.items():
            explanation.append(f"  • {field}: {score:.3f}")
        
        if match_result.explanations:
            explanation.append("\n✅ STRENGTHS:")
            for exp in match_result.explanations[:5]:
                explanation.append(f"  • {exp}")
        
        if match_result.matched_keywords:
            explanation.append("\n🔑 MATCHED KEYWORDS:")
            for field, keywords in match_result.matched_keywords.items():
                explanation.append(f"  • {field}: {', '.join(keywords[:5])}")
        
        if match_result.missing_requirements:
            explanation.append("\n⚠️ MISSING REQUIREMENTS:")
            for req in match_result.missing_requirements[:5]:
                explanation.append(f"  • {req}")
        
        return "\n".join(explanation)
    
    def display_matches(self, matches: List[MatchResult]):
        """Display matches in a formatted table"""
        if not matches:
            print("No matches found")
            return
        
        table_data = []
        for match in matches:
            candidate = self.candidates.get(match.candidate_id, None)
            job = self.jobs.get(match.job_id, None)
            
            if candidate and job:
                table_data.append([
                    match.rank,
                    candidate.name[:20],
                    job.title[:25],
                    f"{match.overall_score:.3f}",
                    len(match.explanations),
                    len(match.matched_keywords)
                ])
        
        headers = ["Rank", "Candidate", "Job Title", "Score", "Strengths", "Keywords"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def save_system(self, path: str):
        """Save entire system state"""
        os.makedirs(path, exist_ok=True)
        
        state = {
            'organizations': self.organizations,
            'candidates': self.candidates,
            'jobs': self.jobs,
            'matches': self.matches,
            'corpus': self.corpus
        }
        
        with open(os.path.join(path, 'system_state.pkl'), 'wb') as f:
            pickle.dump(state, f)
        
        print(f"System saved to {path}")
    
    def load_system(self, path: str):
        """Load system state"""
        with open(os.path.join(path, 'system_state.pkl'), 'rb') as f:
            state = pickle.load(f)
        
        self.organizations = state['organizations']
        self.candidates = state['candidates']
        self.jobs = state['jobs']
        self.matches = state['matches']
        self.corpus = state['corpus']
        
        # Rebuild BM25 models
        for org_id in self.organizations:
            self._rebuild_org_model(org_id)
        
        print(f"System loaded from {path}")

class ATSInterface:
    """Command-line interface for the ATS system"""
    
    def __init__(self):
        self.ats = ATS_BM25()
        self.current_org = None
    
    def run(self):
        """Main interface loop"""
        while True:
            self._clear_screen()
            print("\n" + "="*60)
            print("           ATS - Applicant Tracking System")
            print("="*60)
            print("\n1. Register New Organization")
            print("2. Login as Organization")
            print("3. Add Candidate (Upload Resume)")
            print("4. Match Candidate to Jobs")
            print("5. Match Job to Candidates")
            print("6. View Match Details")
            print("7. Save System State")
            print("8. Load System State")
            print("9. Exit")
            
            choice = input("\nEnter your choice (1-9): ").strip()
            
            if choice == '1':
                self._register_organization()
            elif choice == '2':
                self._login_organization()
            elif choice == '3':
                self._add_candidate()
            elif choice == '4':
                self._match_candidate_to_jobs()
            elif choice == '5':
                self._match_job_to_candidates()
            elif choice == '6':
                self._view_match_details()
            elif choice == '7':
                self._save_system()
            elif choice == '8':
                self._load_system()
            elif choice == '9':
                print("\nThank you for using ATS!")
                break
    
    def _clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _register_organization(self):
        """Register a new organization"""
        print("\n--- Register New Organization ---")
        
        org_id = input("Organization ID: ").strip()
        name = input("Organization Name: ").strip()
        industry = input("Industry: ").strip()
        
        # Define custom fields for matching
        print("\nDefine matching fields (press Enter with empty name to finish):")
        field_defs = []
        
        while True:
            print("\nField Definition:")
            field_name = input("  Field name (e.g., 'skills', 'experience'): ").strip()
            if not field_name:
                break
            
            description = input("  Description: ").strip()
            weight = float(input("  Weight (0.1-2.0, default=1.0): ").strip() or "1.0")
            required = input("  Required? (y/n): ").strip().lower() == 'y'
            
            keywords = input("  Keywords (comma-separated): ").strip().split(',')
            keywords = [k.strip() for k in keywords if k.strip()]
            
            field_def = FieldDefinition(
                name=field_name,
                description=description,
                weight=weight,
                required=required,
                keywords=keywords
            )
            field_defs.append(field_def)
        
        org_profile = OrganizationProfile(
            id=org_id,
            name=name,
            industry=industry,
            field_definitions=field_defs
        )
        
        self.ats.register_organization(org_profile)
        input("\nPress Enter to continue...")
    
    def _login_organization(self):
        """Login as an organization"""
        print("\n--- Login as Organization ---")
        
        org_id = input("Organization ID: ").strip()
        
        if org_id in self.ats.organizations:
            self.current_org = org_id
            org = self.ats.organizations[org_id]
            print(f"\nLogged in as: {org.name}")
            
            # Show organization dashboard
            self._org_dashboard()
        else:
            print("\nOrganization not found!")
        
        input("\nPress Enter to continue...")
    
    def _org_dashboard(self):
        """Organization dashboard"""
        org = self.ats.organizations[self.current_org]
        
        print(f"\n--- {org.name} Dashboard ---")
        print(f"Industry: {org.industry}")
        print(f"Matching Fields: {len(org.field_definitions)}")
        
        # Count jobs
        org_jobs = [j for j in self.ats.jobs.values() if j.organization_id == self.current_org]
        print(f"Active Jobs: {len(org_jobs)}")
        
        print("\nOptions:")
        print("1. Create New Job")
        print("2. View Jobs")
        print("3. Match Job to Candidates")
        print("4. Logout")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == '1':
            self._create_job()
        elif choice == '2':
            self._view_jobs()
        elif choice == '3':
            self._match_job_to_candidates()
        elif choice == '4':
            self.current_org = None
    
    def _create_job(self):
        """Create a new job posting"""
        print("\n--- Create New Job ---")
        
        job_id = f"JOB_{len(self.ats.jobs) + 1}"
        title = input("Job Title: ").strip()
        description = input("Job Description: ").strip()
        
        # Get field requirements
        org = self.ats.organizations[self.current_org]
        required_fields = {}
        custom_weights = {}
        
        print("\nSet requirements for each field:")
        for field_def in org.field_definitions:
            print(f"\n{field_def.name} - {field_def.description}")
            value = input(f"  Required value (or press Enter to skip): ").strip()
            if value:
                required_fields[field_def.name] = value
            
            weight = input(f"  Custom weight (default={field_def.weight}): ").strip()
            if weight:
                custom_weights[field_def.name] = float(weight)
        
        job = JobDescription(
            id=job_id,
            organization_id=self.current_org,
            title=title,
            description=description,
            required_fields=required_fields,
            custom_weights=custom_weights
        )
        
        self.ats.create_job(job)
        input("\nJob created! Press Enter to continue...")
    
    def _add_candidate(self):
        """Add a new candidate with resume"""
        print("\n--- Add New Candidate ---")
        
        candidate_id = input("Candidate ID: ").strip()
        name = input("Full Name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone (optional): ").strip()
        
        # Upload resume
        resume_path = input("Resume file path (PDF/DOCX/TXT): ").strip()
        
        candidate = Candidate(
            id=candidate_id,
            name=name,
            email=email,
            phone=phone if phone else None
        )
        
        self.ats.add_candidate(candidate, resume_path if resume_path else None)
        input("\nCandidate added! Press Enter to continue...")
    
    def _match_candidate_to_jobs(self):
        """Match a candidate to jobs"""
        print("\n--- Match Candidate to Jobs ---")
        
        candidate_id = input("Candidate ID: ").strip()
        
        if candidate_id not in self.ats.candidates:
            print("Candidate not found!")
            input("\nPress Enter to continue...")
            return
        
        org_id = input("Organization ID: ").strip()
        
        if org_id not in self.ats.organizations:
            print("Organization not found!")
            input("\nPress Enter to continue...")
            return
        
        try:
            matches = self.ats.match_candidate_to_jobs(candidate_id, org_id, top_k=5)
            
            if matches:
                print(f"\nTop {len(matches)} matches found:")
                self.ats.display_matches(matches)
                
                # Ask if user wants to see details
                view_details = input("\nView match details? (y/n): ").strip().lower()
                if view_details == 'y':
                    rank = int(input("Enter rank number to view details: ").strip())
                    if 1 <= rank <= len(matches):
                        match = matches[rank-1]
                        print(self.ats.get_match_explanation(match))
            else:
                print("\nNo matches found above threshold")
        
        except Exception as e:
            print(f"Error during matching: {e}")
        
        input("\nPress Enter to continue...")
    
    def _match_job_to_candidates(self):
        """Match a job to candidates"""
        print("\n--- Match Job to Candidates ---")
        
        job_id = input("Job ID: ").strip()
        
        if job_id not in self.ats.jobs:
            print("Job not found!")
            input("\nPress Enter to continue...")
            return
        
        try:
            matches = self.ats.match_job_to_candidates(job_id, top_k=5)
            
            if matches:
                print(f"\nTop {len(matches)} candidates found:")
                self.ats.display_matches(matches)
                
                # Ask if user wants to see details
                view_details = input("\nView match details? (y/n): ").strip().lower()
                if view_details == 'y':
                    rank = int(input("Enter rank number to view details: ").strip())
                    if 1 <= rank <= len(matches):
                        match = matches[rank-1]
                        print(self.ats.get_match_explanation(match))
            else:
                print("\nNo matches found above threshold")
        
        except Exception as e:
            print(f"Error during matching: {e}")
        
        input("\nPress Enter to continue...")
    
    def _view_jobs(self):
        """View jobs for current organization"""
        print("\n--- Organization Jobs ---")
        
        org_jobs = [j for j in self.ats.jobs.values() 
                   if j.organization_id == self.current_org]
        
        if not org_jobs:
            print("No jobs found")
        else:
            for job in org_jobs:
                print(f"\nID: {job.id}")
                print(f"Title: {job.title}")
                print(f"Status: {job.status}")
                print(f"Posted: {job.posted_date.strftime('%Y-%m-%d')}")
        
        input("\nPress Enter to continue...")
    
    def _view_match_details(self):
        """View detailed match explanation"""
        print("\n--- Match Details ---")
        
        candidate_id = input("Candidate ID: ").strip()
        
        if candidate_id not in self.ats.matches:
            print("No matches found for this candidate")
        else:
            matches = self.ats.matches[candidate_id]
            self.ats.display_matches(matches)
            
            rank = input("\nEnter rank to view details (or Enter to skip): ").strip()
            if rank and rank.isdigit():
                rank = int(rank)
                if 1 <= rank <= len(matches):
                    print(self.ats.get_match_explanation(matches[rank-1]))
        
        input("\nPress Enter to continue...")
    
    def _save_system(self):
        """Save system state"""
        path = input("Save path: ").strip()
        self.ats.save_system(path)
        input("\nPress Enter to continue...")
    
    def _load_system(self):
        """Load system state"""
        path = input("Load path: ").strip()
        if os.path.exists(path):
            self.ats.load_system(path)
        else:
            print("Path not found!")
        input("\nPress Enter to continue...")

def main():
    """Main entry point"""
    interface = ATSInterface()
    interface.run()

if __name__ == "__main__":
    main()