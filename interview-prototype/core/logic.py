# core/logic.py
# Handles core processing: Gemini API, PDF extraction, content generation.

import os
import google.generativeai as genai
from PyPDF2 import PdfReader
from dotenv import load_dotenv
# REMOVED: from tkinter import messagebox
import sys # For potentially exiting on critical config error

# --- Default Configuration & Constants ---
DEFAULT_NUM_TOPICS = 5
DEFAULT_MAX_FOLLOW_UPS = 2
MIN_TOPICS = 1
MAX_TOPICS = 10
MIN_FOLLOW_UPS = 0
MAX_FOLLOW_UPS_LIMIT = 5

MODEL_NAME = "gemini-1.5-flash-latest"
ERROR_PREFIX = "Error: " # Standard prefix for returning errors

# --- Core Logic Functions ---

def configure_gemini():
    """
    Loads API key from .env and configures the Gemini client.
    Returns True on success, False on failure.
    Prints errors to console. Exits if API key is missing.
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # Critical error, print and exit is acceptable before UI starts
        print(f"{ERROR_PREFIX}GOOGLE_API_KEY not found in .env file.\nPlease create a .env file in the same directory with your API key:\nGOOGLE_API_KEY=YOUR_API_KEY")
        return False # Signal failure
    try:
        genai.configure(api_key=api_key)
        print("Gemini API configured successfully.")
        return True
    except Exception as e:
        print(f"{ERROR_PREFIX}Configuring Gemini API: {e}")
        return False

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a given PDF file path.
    Returns extracted text string on success, None on failure.
    Prints errors/warnings to console.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        print(f"{ERROR_PREFIX}Invalid or non-existent PDF path provided: {pdf_path}")
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
            print(f"Warning: No text could be extracted from '{os.path.basename(pdf_path)}'. The PDF might be image-based or empty.")
            return None # Return None to clearly signal potential issue.
        print("PDF text extracted successfully.")
        return text
    except Exception as e:
        print(f"{ERROR_PREFIX}Reading PDF '{os.path.basename(pdf_path)}': {e}")
        return None

def generate_initial_questions(resume_text, job_desc_text="", model_name=MODEL_NAME, num_questions=DEFAULT_NUM_TOPICS):
    """
    Generates initial interview questions based on resume and optional job description.
    Returns a list of questions on success, None on failure.
    Prints errors/warnings to console.
    """
    print(f"Generating {num_questions} initial questions using {model_name}...")
    if not resume_text:
        print(f"{ERROR_PREFIX}Cannot generate questions without resume text.")
        return None
    try:
        model = genai.GenerativeModel(model_name)
        prompt_sections = [
            "You are a hiring manager preparing for a first-round screening interview.",
            f"Generate exactly {num_questions} insightful and tailored interview questions based on the candidate's resume and the provided job description.",
            "Your questions should aim to:",
            "  1. Assess the candidate's fit for the role described in the job description (if provided).",
            "  2. Probe deeper into specific skills, experiences, or projects mentioned in the resume that seem relevant.",
            "  3. Identify potential gaps or areas needing clarification.",
            "Avoid generic questions. Phrase them clearly as conversation starters.",
            "Format the output ONLY as a numbered list, with each question on a new line (e.g., '1. Question text'). Do not include any introductory or concluding text, just the numbered questions.",
            "\nCandidate's Resume Text:", "---", resume_text, "---" ]
        if job_desc_text:
            prompt_sections.extend([ "\nJob Description Text:", "---", job_desc_text, "---" ])
        else:
            prompt_sections.append("\n(No job description provided - focus questions based on the resume alone, imagining a generally relevant professional role).")
        prompt_sections.append(f"\n{num_questions} Tailored Interview Questions (Numbered List Only):")
        prompt = "\n".join(prompt_sections)

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        # Handle potential blocks or empty responses
        if not response.parts:
             feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A"
             block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A" else "Unknown"
             safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A" else "N/A"
             error_message = f"Received empty or blocked response for initial questions.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
             print(f"{ERROR_PREFIX}Initial Questions Generation: {error_message}")
             return None # Signal failure

        # Process successful response
        generated_text = response.text.strip()
        lines = generated_text.split('\n')
        questions = []
        for line in lines:
            line_strip = line.strip()
            # Basic check for numbered list format
            if line_strip and line_strip[0].isdigit():
                # Simple parsing: find first non-digit, non-dot/space/paren char
                first_char_index = -1
                for i, char in enumerate(line_strip):
                    if not char.isdigit() and char not in ['.', ' ', ')']:
                        first_char_index = i
                        break
                if first_char_index != -1:
                     # Add the whole stripped line (cleaning happens in UI)
                     questions.append(line_strip)
                else: # Malformed line (e.g., just "1.")
                     print(f"Skipping malformed line during question parsing: {line_strip}")

        # Limit to requested number, even if model gave more
        questions = questions[:num_questions]

        if questions:
            print(f"Successfully generated {len(questions)} initial questions.")
            if len(questions) < num_questions:
                # This is just informational, not an error
                print(f"Note: Model generated {len(questions)} initial questions (requested {num_questions}). This might happen if input is short or model couldn't find enough distinct points.")
            return questions
        else:
            # Model responded but parsing failed or gave empty list
            print(f"Warning: Model response for initial questions was empty or not in the expected numbered list format after parsing:\n\n{generated_text}")
            return None # Signal potential issue

    except Exception as e:
        err_msg = f"Generating initial questions with Gemini: {e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n\n{ERROR_PREFIX}Error 400 or Resource Exhausted: The combined text (Resume + Job Description) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs or a model with a larger context window if available."
        print(f"{ERROR_PREFIX}{err_msg}")
        return None

def generate_follow_up_question(context_question, user_answer, conversation_history, model_name=MODEL_NAME):
    """
    Generates a follow-up question based on the last answer and context.
    Returns the follow-up question string, "[END TOPIC]", or None on error.
    Prints errors to console.
    """
    print(f"Generating follow-up question using {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        # Limit history context sent to model
        history_str = "\n".join([f"Q: {item['q'][:100]}...\nA: {item['a'][:150]}..." for item in conversation_history[-3:]]) # Send last 3 Q/A pairs (limited length)
        prompt = f"""
        You are an interviewer conducting a screening call.
        The original topic question was: "{context_question}"
        Recent conversation on this topic:
        ---
        {history_str}
        ---
        Candidate's most recent answer: "{user_answer}"

        Based ONLY on the candidate's *last answer* in the context of the *original topic question*, ask ONE concise and relevant follow-up question to probe deeper or clarify something specific from their answer.
        *   If the answer was comprehensive and clear, and no natural follow-up arises, respond with exactly: `[END TOPIC]`
        *   Do NOT ask generic questions.
        *   Do NOT summarize the answer.
        *   Generate ONLY the single follow-up question OR the text `[END TOPIC]`.
        *   Keep the follow-up question focused and brief.

        Follow-up Question or End Signal: """

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
            print(f"Warning: Follow-up Generation - Empty/blocked response. Reason: {block_reason}. Ending topic.")
            return "[END TOPIC]" # Treat block as end of topic

        follow_up = response.text.strip()
        print(f"Generated follow-up attempt: '{follow_up}'")

        if not follow_up:
            print("Warning: Received empty follow-up response, ending topic.")
            return "[END TOPIC]" # Treat empty as end

        if follow_up == "[END TOPIC]":
            print("End topic signal received.")
            return "[END TOPIC]"

        # Basic validation/warnings (optional)
        if '?' not in follow_up and len(follow_up.split()) > 5:
            print("Warning: Generated follow-up might not be a question. Using it anyway.")
        elif len(follow_up.split()) < 3:
             print("Warning: Generated follow-up is very short. Using it anyway.")

        return follow_up # Return the generated question

    except Exception as e:
        print(f"{ERROR_PREFIX}Generating follow-up question: {e}")
        # Return None to indicate an error occurred, distinct from "[END TOPIC]"
        return None

def generate_summary_review(full_history, model_name=MODEL_NAME):
    """
    Generates a performance summary and review based on the interview transcript.
    Returns the summary string (Markdown formatted), or an error string starting with ERROR_PREFIX.
    Prints errors to console.
    """
    print(f"Generating interview summary and review using {model_name}...")
    if not full_history:
        print("No interview history recorded for summary.")
        return "No interview history recorded."
    try:
        model = genai.GenerativeModel(model_name)

        # Prepare transcript, limiting length
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

        # --- UPDATED PROMPT ---
        prompt = f"""
        Act as an objective hiring manager critically reviewing a candidate's screening interview performance based ONLY on the transcript below. Your goal is to assess their communication, clarity, and the substance of their answers in this specific conversation.

        Transcript:
        ---
        {transcript}
        ---

        Provide the following analysis using simple Markdown for formatting (e.g., **bold** for headings, `-` for list items):

        **1. Overall Communication & Approach:**
            - Communication style: ...
            - Preparedness: ...
            - Answer Structure & Effectiveness: ...

        **2. Strengths in Responses:**
            - Strength 1: ... (Evidence: ...)
            - Strength 2: ... (Evidence: ...)
            - Strength 3: ... (Evidence: ...)

        **3. Areas for Improvement in Responses:**
            - Area 1: ... (Evidence: ...)
            - Area 2: ... (Evidence: ...)
            - Area 3: ... (Evidence: ...)

        **4. Overall Impression (from this interview only):**
            - Impression: ...

        Ensure the analysis is balanced and constructive based ONLY on the transcript.
        """
        # --- END UPDATED PROMPT ---

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
            safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A" else "N/A"
            error_message = f"Empty or blocked response for Summary/Review.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
            print(f"{ERROR_PREFIX}Summary/Review Generation: {error_message}")
            return f"{ERROR_PREFIX}Could not generate summary/review. Reason: {block_reason}"

        print("Summary/review generated.")
        return response.text.strip() # Return the Markdown formatted text

    except Exception as e:
        error_message = f"Generating summary/review: {e}"
        print(f"{ERROR_PREFIX}{error_message}")
        return f"{ERROR_PREFIX}Could not generate summary/review.\nDetails: {e}"


def generate_qualification_assessment(resume_text, job_desc_text, full_history, model_name=MODEL_NAME):
    """
    Generates an assessment of candidate qualifications against the job description.
    Returns the assessment string (Markdown formatted), or an error string starting with ERROR_PREFIX.
    Prints errors to console.
    """
    print(f"Generating qualification assessment using {model_name}...")
    if not job_desc_text:
        print("No job description provided, skipping qualification assessment.")
        return "No job description provided, cannot perform qualification assessment."
    if not resume_text:
        print("No resume text available, skipping qualification assessment.")
        return "No resume text available, cannot perform qualification assessment."

    try:
        model = genai.GenerativeModel(model_name)

        # Prepare transcript, limiting length
        transcript_parts = []
        total_len = 0
        max_len = 20000
        if full_history:
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
        else:
            transcript = "N/A (No interview conducted or history available)"

        # --- UPDATED PROMPT ---
        prompt = f"""
        Act as a meticulous recruiter evaluating a candidate's potential fit for a specific role. Your task is to synthesize information ONLY from the provided Job Description, Candidate's Resume, and Interview Transcript to assess alignment with the key requirements.

        Job Description (JD):
        ---
        {job_desc_text}
        ---
        Candidate's Resume (R):
        ---
        {resume_text}
        ---
        Interview Transcript (T):
        ---
        {transcript}
        ---

        Provide the following assessment using simple Markdown for formatting (e.g., **bold** for headings, `-` for list items):

        **1. Alignment with Key Requirements:**
            *   Identify 5-7 key requirements from the JD.
            *   For each requirement:
                - **Requirement:** [Requirement text from JD]
                - **Assessment:** [Strong Match | Potential Match | Weak Match/Gap | Insufficient Information]
                - **Evidence:** [Cite brief evidence from R and/or T, like "(R) Mentions X", "(T) Described Y"]

        **2. Overall Fit Assessment (Based on Provided Info):**
            *   Conclusion on potential fit for the role (e.g., Strong, Potential, Unlikely).
            *   Brief reasoning highlighting key strengths/gaps relative to JD requirements.

        Base your assessment ONLY on the provided text (JD, R, T).
        """
        # --- END UPDATED PROMPT ---

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
            safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A" else "N/A"
            error_message = f"Empty or blocked response for Qualification Assessment.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
            print(f"{ERROR_PREFIX}Qualification Assessment Generation: {error_message}")
            return f"{ERROR_PREFIX}Could not generate assessment. Reason: {block_reason}"

        print("Qualification assessment generated.")
        return response.text.strip() # Return the Markdown formatted text

    except Exception as e:
        err_msg = f"Generating qualification assessment: {e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n\n{ERROR_PREFIX}Error 400 or Resource Exhausted: The combined text (JD + Resume + Transcript) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs, fewer follow-ups, or a model with a larger context window if available."
        print(f"{ERROR_PREFIX}{err_msg}")
        return f"{ERROR_PREFIX}Could not generate assessment.\nDetails: {e}"