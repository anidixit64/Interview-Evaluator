# logic.py
# Handles core processing: Gemini API, PDF extraction, content generation.

import os
import google.generativeai as genai
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from tkinter import messagebox # Keep for error reporting within logic functions

# --- Default Configuration & Constants ---
DEFAULT_NUM_TOPICS = 5
DEFAULT_MAX_FOLLOW_UPS = 2
MIN_TOPICS = 1
MAX_TOPICS = 10
MIN_FOLLOW_UPS = 0
MAX_FOLLOW_UPS_LIMIT = 5

MODEL_NAME = "gemini-1.5-flash-latest"

# --- Core Logic Functions ---

def configure_gemini():
    """Loads API key from .env and configures the Gemini client."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        messagebox.showerror("API Key Error", "Error: GOOGLE_API_KEY not found in .env file.\nPlease create a .env file in the same directory with your API key:\nGOOGLE_API_KEY=YOUR_API_KEY")
        return False
    try:
        genai.configure(api_key=api_key)
        print("Gemini API configured successfully.")
        return True
    except Exception as e:
        messagebox.showerror("API Config Error", f"Error configuring Gemini API: {e}")
        return False

def extract_text_from_pdf(pdf_path):
    """Extracts text from a given PDF file path."""
    if not pdf_path or not os.path.exists(pdf_path):
        messagebox.showerror("File Error", "Invalid or non-existent PDF path provided.")
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
            messagebox.showwarning("Extraction Warning", f"Warning: No text could be extracted from '{os.path.basename(pdf_path)}'. The PDF might be image-based or empty.")
            return None # Return None if no text is found
        print("PDF text extracted successfully.")
        return text
    except Exception as e:
        messagebox.showerror("PDF Read Error", f"Error reading PDF '{os.path.basename(pdf_path)}':\n{e}")
        return None

def generate_initial_questions(resume_text, job_desc_text="", model_name=MODEL_NAME, num_questions=DEFAULT_NUM_TOPICS):
    """Generates initial interview questions based on resume and optional job description."""
    print(f"Generating {num_questions} initial questions using {model_name}...")
    if not resume_text:
        messagebox.showerror("Generation Error", "Cannot generate questions without resume text.")
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

        if response.parts:
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
                        elif char in ['.', ' ', ')']:
                            continue
                        else:
                            continue
                    if first_char_index != -1:
                        questions.append(line_strip)
                    else:
                        print(f"Skipping malformed line: {line_strip}")

            questions = questions[:num_questions]

            if questions:
                print(f"Successfully generated {len(questions)} initial questions.")
                if len(questions) < num_questions:
                    messagebox.showinfo("Generation Note", f"Model generated {len(questions)} initial questions (requested {num_questions}). This might happen if the input is short or the model couldn't find enough distinct points. Proceeding.")
                return questions
            else:
                messagebox.showwarning("Generation Warning", "Model response for initial questions was empty or not in the expected numbered list format after parsing:\n\n" + generated_text)
                return None
        else:
             feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
             block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
             safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A." else "N/A"
             error_message = f"Received empty or blocked response for initial questions.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
             messagebox.showerror("Generation Error", error_message)
             print(f"Initial Questions Prompt Feedback: {feedback}")
             return None
    except Exception as e:
        err_msg = f"Error generating initial questions with Gemini:\n{e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n\nError 400 or Resource Exhausted: The combined text (Resume + Job Description) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs or a model with a larger context window if available."
        messagebox.showerror("Generation Error", err_msg)
        print(f"Exception during initial question generation: {e}")
        return None

def generate_follow_up_question(context_question, user_answer, conversation_history, model_name=MODEL_NAME):
    """Generates a follow-up question based on the last answer and context."""
    print(f"Generating follow-up question using {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        history_str = "\n".join([f"Q: {item['q'][:100]}...\nA: {item['a'][:150]}..." for item in conversation_history[-3:]])
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

        if response.parts:
            follow_up = response.text.strip()
            print(f"Generated follow-up attempt: '{follow_up}'")
            if follow_up:
                 if follow_up == "[END TOPIC]":
                     print("End topic signal received.")
                     return None # Signal to end the topic
                 if '?' not in follow_up and len(follow_up.split()) > 5:
                     print("Warning: Generated follow-up might not be a question. Using it anyway.")
                 elif len(follow_up.split()) < 3:
                      print("Warning: Generated follow-up is very short. Using it anyway.")
                 return follow_up
            else:
                 print("Received empty follow-up response, ending topic.")
                 return None
        else:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
            print(f"Follow-up Generation Warning: Empty/blocked response. Reason: {block_reason}. Ending topic.")
            return None
    except Exception as e:
        messagebox.showerror("Generation Error", f"Error generating follow-up question:\n{e}")
        print(f"Exception during follow-up generation: {e}")
        return None # End topic on error

def generate_summary_review(full_history, model_name=MODEL_NAME):
    """Generates a performance summary and review based on the interview transcript."""
    print(f"Generating interview summary and review using {model_name}...")
    if not full_history:
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
                transcript_parts.append(a_part)
                transcript_parts.append(q_part)
                total_len += item_len
            else:
                transcript_parts.append("[... earlier parts truncated ...]\n\n")
                break
        transcript = "".join(reversed(transcript_parts))

        prompt = f"""
        Act as an objective hiring manager critically reviewing a candidate's screening interview performance based ONLY on the transcript below. Your goal is to assess their communication, clarity, and the substance of their answers in this specific conversation.

        Transcript:
        ---
        {transcript}
        ---

        Provide the following analysis:

        1.  **Overall Communication & Approach:**
            *   Briefly describe the candidate's communication style (e.g., clear, concise, verbose, hesitant, articulate, structured).
            *   Did they generally seem prepared? Did they appear to understand the questions?
            *   How did they structure their answers (e.g., used STAR method, provided specific examples, gave high-level responses, anecdotal)? Assess the effectiveness.

        2.  **Strengths in Responses:**
            *   List 2-3 specific strengths observed *in their answers or communication*.
            *   Focus on aspects like clarity, relevance, depth of explanation, demonstrating specific skills/experiences with concrete examples, enthusiasm, or professionalism *evident in the text*.
            *   Cite brief evidence/examples directly from the transcript. (e.g., "Clear explanation of [Specific Task] using STAR in response to Q about X.", "Showed enthusiasm when discussing [Technology Y].")

        3.  **Areas for Improvement in Responses:**
            *   List 2-3 specific areas where responses could have been stronger *in this conversation*.
            *   Focus on aspects like vagueness, lack of specific examples, difficulty answering, rambling, not directly addressing the question, potential inconsistencies, or missed opportunities to showcase skills.
            *   Cite brief evidence/examples. (e.g., "Vague answer regarding [Topic Z], lacked specific metrics.", "Struggled to recall details for the question about [Project Q].", "Did not fully answer the part about [Specific Challenge] in Q about Y.")

        4.  **Overall Impression (from this interview only):**
            *   Based *only on this transcript*, what is your overall impression of the candidate's performance *in this specific interview setting*? (e.g., Strong performance, clear communicator; Showed potential but needs further probing on X; Some concerning gaps in communication/examples related to Y; Performance inconsistent).

        Format the output clearly using the specified headings (including the numbers). Do not invent information not present in the transcript. Ensure the analysis is balanced and constructive.
        """

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if response.parts:
            print("Summary/review generated.")
            return response.text.strip()
        else:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
            safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A." else "N/A"
            error_message = f"Empty or blocked response for Summary/Review.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
            messagebox.showerror("Review Generation Error", error_message)
            print(f"Summary/Review Feedback: {feedback}")
            return f"Error: Could not generate summary/review. {block_reason}"
    except Exception as e:
        error_message = f"Error generating summary/review:\n{e}"
        messagebox.showerror("Review Generation Error", error_message)
        print(f"Exception during summary/review: {e}")
        return f"Error: Could not generate summary/review.\n{e}"

def generate_qualification_assessment(resume_text, job_desc_text, full_history, model_name=MODEL_NAME):
    """Generates an assessment of candidate qualifications against the job description, using resume and transcript."""
    print(f"Generating qualification assessment using {model_name}...")
    if not job_desc_text:
        print("No job description provided, skipping qualification assessment.")
        return "No job description provided, cannot perform qualification assessment."
    if not resume_text:
        print("No resume text available, skipping qualification assessment.")
        return "No resume text available, cannot perform qualification assessment."

    try:
        model = genai.GenerativeModel(model_name)
        transcript_parts = []
        total_len = 0
        max_len = 20000
        if full_history:
            for item in reversed(full_history):
                q_part = f"Interviewer Q: {item['q']}\n"
                a_part = f"Candidate A: {item['a']}\n\n"
                item_len = len(q_part) + len(a_part)
                if total_len + item_len < max_len:
                    transcript_parts.append(a_part)
                    transcript_parts.append(q_part)
                    total_len += item_len
                else:
                    transcript_parts.append("[... earlier parts truncated ...]\n\n")
                    break
            transcript = "".join(reversed(transcript_parts))
        else:
            transcript = "N/A (No interview conducted or history available)"

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

        Provide the following assessment:

        1.  **Alignment with Key Requirements:**
            *   Carefully read the **Job Description** and identify the most critical skills, experiences, qualifications, and responsibilities (e.g., specific technologies, years of experience, educational requirements, key duties). List 5-7 of the most important ones.
            *   For each *key* requirement identified, assess the candidate's apparent level of alignment based *only* on the Resume and Transcript evidence. Use one of the following assessment terms:
                *   **Strong Match:** Clear evidence in both R and T (or strong evidence in one if applicable, like a degree on R).
                *   **Potential Match:** Some evidence in R or T, but needs further clarification or lacks depth/specific examples.
                *   **Weak Match/Gap:** Little to no evidence in R or T, or evidence suggests lack of experience/skill.
                *   **Insufficient Information:** Requirement not sufficiently addressed in either R or T to make a judgment.
            *   **Crucially, justify EACH assessment** by citing specific, brief evidence (or clear lack thereof) from the Resume (indicate with 'R') and/or Transcript (indicate with 'T'). Be precise about what supports the assessment.
            *   Example Format:
                *   `- Requirement (from JD): 3+ years Python development for web applications`
                *   `  Assessment: Strong Match`
                *   `  Evidence: Resume lists 5 years Python experience including Django framework (R); Candidate discussed deploying a specific Django application in detail (T).`
                *   `- Requirement (from JD): Experience with AWS services (S3, Lambda, EC2)`
                *   `  Assessment: Potential Match`
                *   `  Evidence: Resume mentions AWS certification (R); Candidate mentioned using S3 but seemed less familiar with Lambda specifics during the interview (T). Further probing needed.`
                *   `- Requirement (from JD): Leading small project teams`
                *   `  Assessment: Weak Match/Gap`
                *   `  Evidence: No mention of team lead experience on Resume (R); Candidate described only individual contributor roles when asked about projects (T).`
                *   `- Requirement (from JD): Excellent written communication skills`
                *   `  Assessment: Insufficient Information`
                *   `  Evidence: Resume appears well-written (R), but written skills not directly assessed in the verbal interview (T).`

        2.  **Overall Fit Assessment (Based on Provided Info):**
            *   Based *solely* on the requirement alignment analysis above (JD vs. Resume & Transcript), provide a summary conclusion about the candidate's potential fit for *this specific role*.
            *   Is the candidate likely a strong fit, a potential fit needing significant further exploration (e.g., technical assessment, second interview focusing on gaps), or likely not a suitable fit for *this role* based *only* on the requirements and the available text evidence?
            *   Briefly explain your reasoning, highlighting the most significant strengths and potential gaps identified in section 1 *relative to the key job requirements*.

        Be objective and analytical. Your entire assessment MUST be based ONLY on the text provided in the Job Description, Resume, and Transcript. Do not make assumptions or use external knowledge. Use the specified headings and formatting clearly.
        """

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if response.parts:
            print("Qualification assessment generated.")
            return response.text.strip()
        else:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
            safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A." else "N/A"
            error_message = f"Empty or blocked response for Qualification Assessment.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
            messagebox.showerror("Assessment Error", error_message)
            print(f"Assessment Feedback: {feedback}")
            return f"Error: Could not generate assessment. {block_reason}"
    except Exception as e:
        err_msg = f"Error generating qualification assessment:\n{e}"
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n\nError 400 or Resource Exhausted: The combined text (JD + Resume + Transcript) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs, fewer follow-ups, or a model with a larger context window if available."
        messagebox.showerror("Assessment Error", err_msg)
        print(f"Exception during qualification assessment: {e}")
        return f"Error: Could not generate assessment.\n{e}"
