from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from collections import Counter
import spacy
import re

app = FastAPI()
nlp = spacy.load("en_core_web_sm")

PROGRAMMING_LANGUAGES = {"python", "java", "c++", "javascript", "typescript", "sql", "go", "swift", "scala", "html", "css"}
SOFT_SKILLS = {"team", "communication", "adaptable", "fast learner", "leadership", "independent", "collaboration", "problem-solving", "initiative", "attention to detail"}
DEGREES = {"bachelor", "master", "phd", "mba", "associate", "ba", "bs", "ma", "ms", "b.sc", "m.sc", "b.eng", "m.eng"}

class InputText(BaseModel):
    resumeText: str
    jobText: str

@app.post("/analyze")
async def analyze_texts(data: InputText):
    resume_text = data.resumeText.lower()
    job_text = data.jobText.lower()
    resume_doc = nlp(resume_text)
    job_doc = nlp(job_text)

    # Extract companies (ORGs)
    resume_companies = [ent.text for ent in resume_doc.ents if ent.label_ == "ORG"]

    # Extract programming languages
    resume_skills = [token.text for token in resume_doc if token.text in PROGRAMMING_LANGUAGES]
    job_skills = [token.text for token in job_doc if token.text in PROGRAMMING_LANGUAGES]

    # Extract soft skills
    job_soft_skills = [token.text for token in job_doc if token.text in SOFT_SKILLS]

    # Extract years
    resume_years = re.findall(r"\b(19[5-9][0-9]|20[0-9]{2}|2100)\b", data.resumeText)

    # Extract degrees and education entities
    degree_mentions = [word for word in resume_text.split() if word in DEGREES]
    education_orgs = [ent.text for ent in resume_doc.ents if ent.label_ == "ORG" and any(
        deg in ent.sent.text for deg in DEGREES
    )]

    return {
        "resume_companies": Counter(resume_companies).most_common(),
        "resume_skills": Counter(resume_skills).most_common(),
        "resume_years": Counter(resume_years).most_common(),
        "resume_degrees": Counter(degree_mentions).most_common(),
        "resume_education_orgs": Counter(education_orgs).most_common(),
        "job_skills": Counter(job_skills).most_common(),
        "job_soft_skills": Counter(job_soft_skills).most_common()
    }
