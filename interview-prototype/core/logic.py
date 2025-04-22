# core/logic.py
# Handles core processing: Gemini API, PDF extraction, content generation.

import os
import re
import keyring
import google.generativeai as genai
from PyPDF2 import PdfReader
import sys
from . import prompts

# --- Default Configuration & Constants ---
DEFAULT_NUM_TOPICS = 1
DEFAULT_MAX_FOLLOW_UPS = 0
MIN_TOPICS = 1
MAX_TOPICS = 10
MIN_FOLLOW_UPS = 0
MAX_FOLLOW_UPS_LIMIT = 5

MODEL_NAME = "gemini-1.5-flash-latest"
ERROR_PREFIX = "Error: "

# --- Keyring Constants for Gemini ---
KEYRING_SERVICE_NAME_GEMINI = "InterviewBotPro_Gemini"
KEYRING_USERNAME_GEMINI = "gemini_api_key"

# --- Core Logic Functions ---

def configure_gemini():
    """
    Loads Google API key from keyring and configures the Gemini client.
    Returns True on success, False on failure.
    """
    api_key = None
    try:
        print(f"Attempting to retrieve Gemini API key from keyring (Service: '{KEYRING_SERVICE_NAME_GEMINI}')...")
        api_key = keyring.get_password(KEYRING_SERVICE_NAME_GEMINI, KEYRING_USERNAME_GEMINI)
        if not api_key:
            print(f"{ERROR_PREFIX}Gemini API key not found in keyring for service '{KEYRING_SERVICE_NAME_GEMINI}'.")
            print("Please store your key using your system's keyring.")
            return False
        print("Gemini API key retrieved from keyring.")

    except Exception as e:
        print(f"{ERROR_PREFIX}Accessing keyring failed: {e}")
        return False

    try:
        genai.configure(api_key=api_key)
        print("Gemini API configured successfully.")
        return True
    except Exception as e:
        print(f"{ERROR_PREFIX}Configuring Gemini API with retrieved key: {e}")
        return False

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a given PDF file path.
    Returns extracted text string on success, None on failure.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        print(f"{ERROR_PREFIX}Invalid or non-existent PDF path: {pdf_path}")
        return None
    print(f"Reading PDF: {pdf_path}...")
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            print(f"Warning: No text extracted from '{os.path.basename(pdf_path)}'.")
            return None
        print("PDF text extracted successfully.")
        return text
    except Exception as e:
        print(f"{ERROR_PREFIX}Reading PDF '{os.path.basename(pdf_path)}': {e}")
        return None

def generate_initial_questions(resume_text, job_desc_text="", model_name=MODEL_NAME, num_questions=DEFAULT_NUM_TOPICS):
    """
    Generates initial interview questions based on resume and optional job description.
    Returns a list of questions on success, None on failure.
    """
    print(f"Generating {num_questions} initial questions using {model_name}...")
    if not resume_text:
        print(f"{ERROR_PREFIX}Cannot generate questions without resume text.")
        return None
    try:
        model = genai.GenerativeModel(model_name)

        if job_desc_text:
            job_desc_section = prompts.JOB_DESC_SECTION_TEMPLATE.format(job_desc_text=job_desc_text)
        else:
            job_desc_section = prompts.NO_JOB_DESC_SECTION

        prompt = prompts.INITIAL_QUESTIONS_PROMPT_TEMPLATE.format(
            num_questions=num_questions,
            resume_text=resume_text,
            job_desc_section=job_desc_section
        )

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if not response.parts:
             feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
             block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
             print(f"{ERROR_PREFIX}Initial Questions Gen: Empty/blocked response. Reason: {block_reason}")
             return None

        generated_text = response.text.strip()
        lines = generated_text.split('\n')
        questions = []
        for line in lines:
            line_strip = line.strip()
            if line_strip and line_strip[0].isdigit():
                first_char_index = -1
                for i, char in enumerate(line_strip):
                    if not char.isdigit() and char not in ['.', ' ', ')']:
                        first_char_index = i
                        break
                if first_char_index != -1:
                     questions.append(line_strip)
                else:
                     print(f"Skipping malformed question line: {line_strip}")

        questions = questions[:num_questions]

        if questions:
            print(f"Successfully generated {len(questions)} initial questions.")
            if len(questions) < num_questions:
                print(f"Note: Model generated {len(questions)} questions (requested {num_questions}).")
            return questions
        else:
            print(f"Warning: Model response empty or not parsed correctly:\n{generated_text}")
            return None

    except Exception as e:
        err_msg = f"Generating initial questions: {e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n{ERROR_PREFIX}Inputs might be too large for model ('{MODEL_NAME}')."
        print(f"{ERROR_PREFIX}{err_msg}")
        return None

def generate_follow_up_question(context_question, user_answer, conversation_history, model_name=MODEL_NAME):
    """
    Generates a follow-up question based on the last answer and context.
    Returns the follow-up question string, "[END TOPIC]", or None on error.
    """
    print(f"Generating follow-up question using {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        history_str = "\n".join([f"Q: {item['q'][:100]}...\nA: {item['a'][:150]}..." for item in conversation_history[-3:]])

        prompt = prompts.FOLLOW_UP_PROMPT_TEMPLATE.format(
            context_question=context_question,
            history_str=history_str,
            user_answer=user_answer
        )

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if not response.parts:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
            print(f"Warning: Follow-up Gen - Empty/blocked. Reason: {block_reason}. Ending topic.")
            return "[END TOPIC]"

        follow_up = response.text.strip()
        print(f"Generated follow-up attempt: '{follow_up}'")

        if not follow_up:
            print("Warning: Received empty follow-up response, ending topic.")
            return "[END TOPIC]"

        return follow_up

    except Exception as e:
        print(f"{ERROR_PREFIX}Generating follow-up question: {e}")
        return None

def generate_summary_review(full_history, model_name=MODEL_NAME):
    """
    Generates a performance summary and review based on the interview transcript.
    Returns the summary string (Markdown formatted), or an error string.
    """
    print(f"Generating interview summary and review using {model_name}...")
    if not full_history:
        print("No history for summary.")
        return "No interview history recorded."
    try:
        model = genai.GenerativeModel(model_name)

        transcript_parts = []
        total_len = 0
        max_len = 15000
        for item in reversed(full_history):
            q_part = f"Interviewer Q: {item['q']}\n"
            a_part = f"Candidate A: {item['a']}\n\n"
            item_len = len(q_part) + len(a_part)
            if total_len + item_len < max_len:
                transcript_parts.insert(0, a_part)
                transcript_parts.insert(0, q_part)
                total_len += item_len
            else:
                transcript_parts.insert(0, "[... earlier parts truncated ...]\n\n")
                break
        transcript = "".join(transcript_parts)

        prompt = prompts.SUMMARY_REVIEW_PROMPT_TEMPLATE.format(transcript=transcript)

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if not response.parts:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
            print(f"{ERROR_PREFIX}Summary/Review Gen: Empty/blocked. Reason: {block_reason}")
            return f"{ERROR_PREFIX}Could not generate summary/review. Reason: {block_reason}"

        print("Summary/review generated.")
        return response.text.strip()

    except Exception as e:
        error_message = f"Generating summary/review: {e}"
        print(f"{ERROR_PREFIX}{error_message}")
        return f"{ERROR_PREFIX}Could not generate summary/review.\nDetails: {e}"

def generate_content_score_analysis(full_history, model_name=MODEL_NAME):
    """
    Generates a score (1-100) and analysis based on answer structure and relevance.
    Returns a dictionary: {'score': int, 'analysis_text': str, 'error': str | None}.
    """
    print(f"Generating content score and analysis using {model_name}...")
    result = {'score': 0, 'analysis_text': None, 'error': None} # Default result

    if not full_history:
        result['error'] = "No interview history recorded for content scoring."
        print(result['error'])
        return result

    try:
        model = genai.GenerativeModel(model_name)

        transcript_parts = []
        total_len = 0
        max_len = 15000 
        for item in reversed(full_history):
            q_part = f"Interviewer Q: {item['q']}\n"
            a_part = f"Candidate A: {item['a']}\n\n"
            item_len = len(q_part) + len(a_part)
            if total_len + item_len < max_len:
                transcript_parts.insert(0, a_part)
                transcript_parts.insert(0, q_part)
                total_len += item_len
            else:
                transcript_parts.insert(0, "[... earlier parts truncated ...]\n\n")
                break
        transcript = "".join(transcript_parts)

        prompt = prompts.CONTENT_SCORE_PROMPT_TEMPLATE.format(transcript=transcript)

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if not response.parts:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
            error_message = f"Content Score Gen: Empty/blocked. Reason: {block_reason}"
            print(f"{ERROR_PREFIX}{error_message}")
            result['error'] = f"Could not generate content score. Reason: {block_reason}"
            return result

        generated_text = response.text.strip()
        score = 0 
        analysis_text = "Could not parse analysis from response."

        score_match = re.search(r"Score:\s*(\d+)", generated_text, re.IGNORECASE)
        if score_match:
            try:
                score = int(score_match.group(1))
                score = max(0, min(100, score)) # Clamp score between 0-100
            except ValueError:
                print("Warning: Could not parse score number, using 0.")
                score = 0

        reasoning_match = re.search(r"Reasoning:?\s*(.*)", generated_text, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            analysis_text = reasoning_match.group(1).strip()
        elif not score_match:
             analysis_text = generated_text if generated_text else analysis_text


        result['score'] = score
        result['analysis_text'] = analysis_text
        print(f"Content score generated: {score}")
        return result

    except Exception as e:
        error_message = f"Generating content score/analysis: {e}"
        print(f"{ERROR_PREFIX}{error_message}")
        result['error'] = f"Could not generate content score.\nDetails: {e}"
        return result
    

    
def generate_qualification_assessment(resume_text, job_desc_text, full_history, model_name=MODEL_NAME):
    """
    Generates an assessment of candidate qualifications against the job description.
    Returns a dictionary containing:
        'requirements': A list of requirement detail dictionaries (incl. evidence).
        'overall_fit': A string with the overall fit assessment.
        'error': An error message string if generation failed, otherwise None.
    """
    print(f"Generating qualification assessment (with evidence) using {model_name}...")
    result_data = { "requirements": [], "overall_fit": None, "error": None }

    if not job_desc_text:
        result_data["error"] = "No job description provided, cannot perform assessment."
        print(result_data["error"])
        return result_data
    if not resume_text:
        result_data["error"] = "No resume text available, cannot perform assessment."
        print(result_data["error"])
        return result_data

    try:
        model = genai.GenerativeModel(model_name)
        transcript = "N/A"
        if full_history:
            transcript_parts = []
            total_len = 0
            max_len = 10000
            for item in reversed(full_history):
                q_part = f"Interviewer Q: {item['q']}\n"; a_part = f"Candidate A: {item['a']}\n\n"
                item_len = len(q_part) + len(a_part)
                if total_len + item_len < max_len:
                    transcript_parts.insert(0, a_part); transcript_parts.insert(0, q_part)
                    total_len += item_len
                else:
                    transcript_parts.insert(0, "[... earlier parts truncated ...]\n\n"); break
            transcript = "".join(transcript_parts)

        prompt = prompts.QUALIFICATION_ASSESSMENT_PROMPT_TEMPLATE.format(
            job_desc_text=job_desc_text,
            resume_text=resume_text,
            transcript=transcript
        )

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if not response.parts:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
            error_message = f"Qualification Assessment Gen: Empty/blocked. Reason: {block_reason}"
            print(f"{ERROR_PREFIX}{error_message}")
            result_data["error"] = f"Could not generate assessment. Reason: {block_reason}"
            return result_data

        print("Qualification assessment generated. Parsing response...")
        full_assessment_text = response.text.strip()
        requirements_list = []
        overall_fit = "Overall fit assessment not found in response."

        req_pattern = re.compile(
            r"^[ \t]*[\*-][ \t]+\*\*Requirement[:]*\*\*[ \t]*(.*?)\n"
            r"\s*[\*-][ \t]+\*\*Assessment[:]*\*\*[ \t]*(.*?)\n"
            r"\s*[\*-][ \t]+\*\*Evidence[:]*\*\*[ \t]*(.*?)" # Capture evidence text
            r"(?=\n[ \t]*[\*-][ \t]+\*\*Requirement|\n\s*\*\*2\. Overall Fit|\Z)",
            re.DOTALL | re.IGNORECASE | re.MULTILINE
        )

        matches = list(req_pattern.finditer(full_assessment_text))
        print(f"Found {len(matches)} potential requirement matches using regex (with evidence).")

        for match in matches:
            req_text = match.group(1).strip() if match.group(1) else "N/A"
            assessment_level = match.group(2).strip() if match.group(2) else "N/A"
            evidence_text = match.group(3).strip() if match.group(3) else "N/A" # Get evidence group

            resume_evidence = "N/A"
            transcript_evidence = "N/A"
            r_match = re.search(r'\(R\)\s*(.*?)(?=\(T\)|$)', evidence_text, re.IGNORECASE | re.DOTALL)
            t_match = re.search(r'\(T\)\s*(.*?)(?=\(R\)|$)', evidence_text, re.IGNORECASE | re.DOTALL)

            if r_match: resume_evidence = r_match.group(1).strip()
            if t_match: transcript_evidence = t_match.group(1).strip()

            if resume_evidence == "N/A" and transcript_evidence == "N/A" and evidence_text != "N/A":
                print(f"Warning: Could not parse specific (R)/(T) evidence for: '{req_text}'. Using full text.")
                resume_evidence = evidence_text
                transcript_evidence = "N/A"

            requirements_list.append({
                "requirement": req_text,
                "assessment": assessment_level,
                "resume_evidence": resume_evidence, 
                "transcript_evidence": transcript_evidence 
            })

        overall_match = re.search(r'\*\*2\.?\s*Overall Fit Assessment.*?\*\*:?\s*(.*?)$', full_assessment_text, re.DOTALL | re.IGNORECASE)
        if overall_match:
            overall_fit = overall_match.group(1).strip()
            print("Found Overall Fit section.")
        else:
             print("Warning: Could not find Overall Fit section using regex.")

        if not requirements_list and not overall_match:
             print(f"Warning: Could not parse requirements or overall fit from assessment text:\n{full_assessment_text}")
             result_data["error"] = "Could not parse assessment structure from the generated text."

        result_data["requirements"] = requirements_list
        result_data["overall_fit"] = overall_fit

        print(f"Parsed {len(requirements_list)} requirements successfully (with evidence).")
        return result_data

    except Exception as e:
        err_msg = f"Generating/parsing qualification assessment: {e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n{ERROR_PREFIX}Inputs might be too large for model ('{MODEL_NAME}')."
        print(f"{ERROR_PREFIX}{err_msg}")
        result_data["error"] = f"Could not generate or parse assessment.\nDetails: {e}"
        return result_data