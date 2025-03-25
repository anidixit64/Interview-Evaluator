import os
import sys
import google.generativeai as genai
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import customtkinter as ctk # Import customtkinter
from tkinter import messagebox, filedialog # Keep these standard dialogs
from PIL import Image # Import Pillow for icons

# --- Default Configuration ---
DEFAULT_NUM_TOPICS = 5
DEFAULT_MAX_FOLLOW_UPS = 2
MIN_TOPICS = 1
MAX_TOPICS = 10
MIN_FOLLOW_UPS = 0
MAX_FOLLOW_UPS_LIMIT = 5

MODEL_NAME = "gemini-1.5-flash-latest"
ICON_PATH = "icons" # Path to your icons folder (Create this folder and add 'folder.png', 'play.png', 'send.png', 'plus.png', 'minus.png')

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

        # Configure generation safety settings (optional, adjust as needed)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        if response.parts:
            generated_text = response.text.strip()
            # More robust parsing: find lines starting with digits and a dot/space
            lines = generated_text.split('\n')
            questions = []
            for line in lines:
                line_strip = line.strip()
                if line_strip and line_strip[0].isdigit():
                    # Find the first non-digit character after the number
                    first_char_index = -1
                    for i, char in enumerate(line_strip):
                        if not char.isdigit() and char not in ['.', ' ', ')']:
                            first_char_index = i
                            break
                        elif char in ['.', ' ', ')']: # Allow separators
                            continue
                        else: # Still a digit
                            continue

                    if first_char_index != -1:
                        questions.append(line_strip) # Keep the number for context if needed, or trim later
                    else: # Line starts with digits but has no text? Skip.
                        print(f"Skipping malformed line: {line_strip}")
                # Consider if the model might *not* number them - less ideal but possible fallback
                # elif line_strip and len(questions) < num_questions:
                #    questions.append(f"{len(questions)+1}. {line_strip}") # Add numbering if missing

            questions = questions[:num_questions] # Ensure we don't exceed requested number

            if questions:
                print(f"Successfully generated {len(questions)} initial questions.")
                if len(questions) < num_questions:
                    messagebox.showinfo("Generation Note", f"Model generated {len(questions)} initial questions (requested {num_questions}). This might happen if the input is short or the model couldn't find enough distinct points. Proceeding.")
                return questions
            else:
                messagebox.showwarning("Generation Warning", "Model response for initial questions was empty or not in the expected numbered list format after parsing:\n\n" + generated_text)
                return None
        else:
             # Handle blocked responses
             feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
             block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
             safety_ratings_str = "\n".join([f"  - {rating.category}: {rating.probability}" for rating in getattr(feedback, 'safety_ratings', [])]) if feedback != "N/A." else "N/A"
             error_message = f"Received empty or blocked response for initial questions.\nReason: {block_reason}\nSafety Ratings:\n{safety_ratings_str}"
             messagebox.showerror("Generation Error", error_message)
             print(f"Initial Questions Prompt Feedback: {feedback}")
             return None
    except Exception as e:
        err_msg = f"Error generating initial questions with Gemini:\n{e}"
        # Check specifically for prompt size issues
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += "\n\nError 400 or Resource Exhausted: The combined text (Resume + Job Description) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs or a model with a larger context window if available."
        messagebox.showerror("Generation Error", err_msg)
        print(f"Exception during initial question generation: {e}")
        return None

def generate_follow_up_question(context_question, user_answer, conversation_history, model_name=MODEL_NAME):
    """Generates a follow-up question based on the last answer and context."""
    print(f"Generating follow-up question using {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        # Format history concisely
        history_str = "\n".join([f"Q: {item['q'][:100]}...\nA: {item['a'][:150]}..." for item in conversation_history[-3:]]) # Limit history length shown in prompt
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

        # Configure generation safety settings
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
                 # Basic check: Does it look like a question?
                 if '?' not in follow_up and len(follow_up.split()) > 5: # Simple heuristic
                     print("Warning: Generated follow-up might not be a question. Using it anyway.")
                 elif len(follow_up.split()) < 3: # Too short?
                      print("Warning: Generated follow-up is very short. Using it anyway.")

                 return follow_up # Return the generated question
            else:
                 print("Received empty follow-up response, ending topic.")
                 return None # Treat empty response as end signal
        else:
            feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "N/A."
            block_reason = getattr(feedback, 'block_reason', 'Unknown') if feedback != "N/A." else "Unknown"
            print(f"Follow-up Generation Warning: Empty/blocked response. Reason: {block_reason}. Ending topic.")
            return None # Treat blocked response as end signal
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
        # Ensure transcript isn't excessively long for the prompt context
        transcript_parts = []
        total_len = 0
        max_len = 15000 # Adjust based on model limits and typical transcript size
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


        # --- MODIFIED PROMPT ---
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
        # --- END MODIFIED PROMPT ---

        # Configure generation safety settings
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
        return "No job description provided, cannot perform qualification assessment."
    if not resume_text:
        return "No resume text available, cannot perform qualification assessment."

    try:
        model = genai.GenerativeModel(model_name)
        # Ensure transcript isn't excessively long for the prompt context
        transcript_parts = []
        total_len = 0
        # Allow more context here as it's crucial for assessment
        max_len = 20000 # Adjust based on model limits and typical transcript size
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


        # --- MODIFIED PROMPT ---
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
        # --- END MODIFIED PROMPT ---

        # Configure generation safety settings
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
        # Check specifically for prompt size issues
        if "400" in str(e) and ("prompt" in str(e).lower() or "request payload" in str(e).lower() or "resource exhausted" in str(e).lower()):
             err_msg += f"\n\nError 400 or Resource Exhausted: The combined text (JD + Resume + Transcript) might be too large for the model's input limit ('{MODEL_NAME}'). Try with shorter inputs, fewer follow-ups, or a model with a larger context window if available."
        messagebox.showerror("Assessment Error", err_msg)
        print(f"Exception during qualification assessment: {e}")
        return f"Error: Could not generate assessment.\n{e}"

# --- GUI Class ---
class InterviewApp(ctk.CTk): # Inherit from ctk.CTk
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Interview Bot Pro")
        # Increased height slightly to better accommodate all sections
        self.geometry("850x950")

        # --- Appearance ---
        # Provide options during development, but set a default
        # ctk.set_appearance_mode("System") # Options: "System", "Dark", "Light"
        # ctk.set_default_color_theme("blue") # Options: "blue", "dark-blue", "green"
        # For consistency, let's pick one for the example:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- Load Icons ---
        self.icon_size = (20, 20) # Adjust as needed
        self.small_icon_size = (16, 16)
        self.select_icon = self._load_icon("folder.png", self.icon_size)
        self.start_icon = self._load_icon("play.png", self.icon_size)
        self.submit_icon = self._load_icon("send.png", self.icon_size)
        self.plus_icon = self._load_icon("plus.png", self.small_icon_size)
        self.minus_icon = self._load_icon("minus.png", self.small_icon_size)

        # --- Fonts ---
        self.font_default = ctk.CTkFont(size=12)
        self.font_bold = ctk.CTkFont(size=12, weight="bold")
        self.font_small = ctk.CTkFont(size=11) # Slightly larger small font
        self.font_large_bold = ctk.CTkFont(size=15, weight="bold") # Larger section titles
        self.font_history = ctk.CTkFont(size=10) # Specific smaller font for history

        # --- State Variables ---
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        self.num_topics_var = ctk.IntVar(value=DEFAULT_NUM_TOPICS)
        self.max_follow_ups_var = ctk.IntVar(value=DEFAULT_MAX_FOLLOW_UPS)
        self.num_topics = DEFAULT_NUM_TOPICS # Store actual value too
        self.max_follow_ups = DEFAULT_MAX_FOLLOW_UPS
        self.initial_questions = []
        self.current_initial_q_index = -1
        self.current_topic_question = ""    # The original question for the current topic
        self.current_topic_history = []     # History for the current topic only (Q/A pairs)
        self.follow_up_count = 0            # Follow-ups asked for the current topic
        self.current_full_interview_history = [] # All Q/A pairs for the entire interview
        self.review_window = None           # Reference to the Toplevel review window

        # --- Main Layout using Grid ---
        self.grid_columnconfigure(0, weight=1) # Make column 0 expandable
        self.grid_rowconfigure(0, weight=0) # Setup frame - fixed size
        self.grid_rowconfigure(1, weight=3) # Interview section - more weight
        self.grid_rowconfigure(2, weight=2) # History section - reasonable weight

        # --- Section 1: Setup ---
        setup_frame = ctk.CTkFrame(self, corner_radius=10)
        setup_frame.grid(row=0, column=0, padx=10, pady=10, sticky="new") # Anchor to top, expand horizontally
        setup_frame.grid_columnconfigure(1, weight=1) # Allow JD input/file label to expand

        ctk.CTkLabel(setup_frame, text="Setup", font=self.font_large_bold).grid(row=0, column=0, columnspan=4, pady=(5, 10), padx=10, sticky="w")

        # Row 1: Resume Selection
        self.select_btn = ctk.CTkButton(
            setup_frame, text="Select Resume PDF", command=self.select_resume_file,
            image=self.select_icon, compound="left", corner_radius=8, font=self.font_default,
            fg_color="white", text_color="black", hover_color="gray90" # White background
        )
        self.select_btn.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
        # Using an Entry-like label for better alignment and appearance
        self.file_label = ctk.CTkEntry(setup_frame, placeholder_text="No resume selected.", state="disabled", font=self.font_small)
        self.file_label.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        # Row 2: Job Description
        ctk.CTkLabel(setup_frame, text="Job Description (Optional):", font=self.font_default).grid(row=2, column=0, padx=(10, 5), pady=(10,5), sticky="nw")
        self.job_desc_input = ctk.CTkTextbox(
            setup_frame, height=120, corner_radius=8, # Increased height slightly
            wrap="word", state="disabled", font=self.font_small
        )
        self.job_desc_input.grid(row=2, column=1, columnspan=3, padx=5, pady=(10,5), sticky="ew")

        # Row 3: Configuration & Start Button
        config_inner_frame = ctk.CTkFrame(setup_frame, fg_color="transparent") # Use inner frame for layout
        config_inner_frame.grid(row=3, column=0, columnspan=4, pady=(10, 10), sticky="w", padx=5)

        # Topics Spinbox Replacement
        ctk.CTkLabel(config_inner_frame, text="Topics:", font=self.font_default).pack(side="left", padx=(5, 2))
        self.topic_minus_btn = ctk.CTkButton(
            config_inner_frame, text="", image=self.minus_icon, width=28, height=28,
            command=lambda: self.adjust_value(self.num_topics_var, -1, MIN_TOPICS, MAX_TOPICS), state="disabled",
            fg_color="white", text_color="black", hover_color="gray90" # White background
            )
        self.topic_minus_btn.pack(side="left", padx=(0, 0))
        self.num_topics_label = ctk.CTkLabel(config_inner_frame, textvariable=self.num_topics_var, width=25, justify="center", font=self.font_default)
        self.num_topics_label.pack(side="left", padx=(2, 2))
        self.topic_plus_btn = ctk.CTkButton(
            config_inner_frame, text="", image=self.plus_icon, width=28, height=28,
            command=lambda: self.adjust_value(self.num_topics_var, 1, MIN_TOPICS, MAX_TOPICS), state="disabled",
            fg_color="white", text_color="black", hover_color="gray90" # White background
            )
        self.topic_plus_btn.pack(side="left", padx=(0, 15))

        # Follow-ups Spinbox Replacement
        ctk.CTkLabel(config_inner_frame, text="Max Follow-ups:", font=self.font_default).pack(side="left", padx=(5, 2))
        self.followup_minus_btn = ctk.CTkButton(
            config_inner_frame, text="", image=self.minus_icon, width=28, height=28,
            command=lambda: self.adjust_value(self.max_follow_ups_var, -1, MIN_FOLLOW_UPS, MAX_FOLLOW_UPS_LIMIT), state="disabled",
            fg_color="white", text_color="black", hover_color="gray90" # White background
            )
        self.followup_minus_btn.pack(side="left", padx=(0, 0))
        self.max_follow_ups_label = ctk.CTkLabel(config_inner_frame, textvariable=self.max_follow_ups_var, width=25, justify="center", font=self.font_default)
        self.max_follow_ups_label.pack(side="left", padx=(2, 2))
        self.followup_plus_btn = ctk.CTkButton(
            config_inner_frame, text="", image=self.plus_icon, width=28, height=28,
            command=lambda: self.adjust_value(self.max_follow_ups_var, 1, MIN_FOLLOW_UPS, MAX_FOLLOW_UPS_LIMIT), state="disabled",
            fg_color="white", text_color="black", hover_color="gray90" # White background
            )
        self.followup_plus_btn.pack(side="left", padx=(0, 20))

        self.start_interview_btn = ctk.CTkButton(
            config_inner_frame, text="Start Interview", command=self.start_interview_process,
            state="disabled", image=self.start_icon, compound="left", corner_radius=8, font=self.font_bold,
            fg_color="white", text_color="black", hover_color="gray90" # White background
        )
        self.start_interview_btn.pack(side="left", padx=(10, 0))


        # --- Section 2: Interview Interaction ---
        interview_frame = ctk.CTkFrame(self, corner_radius=10)
        interview_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew") # Expandable
        interview_frame.grid_columnconfigure(0, weight=1) # Allow question/answer widgets to expand
        interview_frame.grid_rowconfigure(4, weight=1) # Allow answer box to expand vertically

        ctk.CTkLabel(interview_frame, text="Interview", font=self.font_large_bold).grid(row=0, column=0, pady=(5, 10), padx=10, sticky="w")

        # Interview Status/Question
        self.current_q_label = ctk.CTkLabel(interview_frame, text="Interviewer:", font=self.font_bold)
        self.current_q_label.grid(row=1, column=0, padx=10, sticky="w")
        self.current_q_text = ctk.CTkTextbox(
            interview_frame, height=80, wrap="word", state="disabled", # Start disabled
            font=self.font_default, activate_scrollbars=True, # Show scrollbars if needed
            # Use frame background color for a label-like look when disabled
            # fg_color=("gray90", "gray19") # Slightly different bg when disabled
            fg_color="transparent"
        )
        self.current_q_text.grid(row=2, column=0, padx=10, pady=(2, 10), sticky="ew")
        self.current_q_text.insert("1.0", "[Select Resume PDF above to enable setup]")
        self.current_q_text.configure(state="disabled") # Ensure it's disabled after inserting

        # Answer Input
        self.answer_label = ctk.CTkLabel(interview_frame, text="Your Answer:", font=self.font_bold)
        self.answer_label.grid(row=3, column=0, padx=10, pady=(5,0), sticky="w")
        self.answer_input = ctk.CTkTextbox(
            interview_frame, height=150, wrap="word", state="disabled", corner_radius=8, font=self.font_default
        )
        self.answer_input.grid(row=4, column=0, padx=10, pady=(2, 10), sticky="nsew") # Expandable

        # Submit Button Frame (to center the button)
        submit_frame = ctk.CTkFrame(interview_frame, fg_color="transparent")
        submit_frame.grid(row=5, column=0, pady=(5, 10))
        submit_frame.grid_columnconfigure(0, weight=1) # Center button

        self.submit_button = ctk.CTkButton(
            submit_frame, text="Submit Answer", command=self.submit_answer, state="disabled",
            image=self.submit_icon, compound="left", corner_radius=8, font=self.font_bold,
            fg_color="white", text_color="black", hover_color="gray90" # White background
        )
        self.submit_button.grid(row=0, column=0) # Centered by frame's grid config

        # Bind Enter key to submit answer (customtkinter handles this similarly)
        self.answer_input.bind("<Return>", self._submit_answer_event)
        self.answer_input.bind("<Shift-Return>", self._insert_newline_event) # Allow Shift+Enter


        # --- Section 3: History ---
        history_frame = ctk.CTkFrame(self, corner_radius=10)
        history_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew") # Expandable
        history_frame.grid_columnconfigure(0, weight=1)
        history_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(history_frame, text="History", font=self.font_large_bold).grid(row=0, column=0, pady=(5, 5), padx=10, sticky="w")

        self.history_text = ctk.CTkTextbox(
            history_frame, wrap="word", state="disabled", corner_radius=8, font=self.font_history
        )
        self.history_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew") # Expandable

        # Configure styles for history using CTkTextbox tags
        # Adjust colors based on your theme (examples for default 'blue' theme)
        # You might need CTk > 5.2.0 for reliable foreground color tags
        q_color = self._get_theme_color("button") # Example: Use button color for Q
        topic_color = self._get_theme_color("text_disabled") # Example: Dim color for marker
        answer_color = self._get_theme_color("text") # Default text color

        self.history_text.tag_config("question_style", foreground=q_color)
        self.history_text.tag_config("answer_style", foreground=answer_color)
        self.history_text.tag_config("topic_marker", foreground=topic_color)


        # --- Initial Setup ---
        if not configure_gemini():
            # Critical error, quit application
            messagebox.showerror("Fatal Error", "Gemini API could not be configured. Exiting.")
            self.after(100, self.quit) # Schedule quit after showing message box
        else:
            # Reset to initial state (disables most controls until PDF selected)
            self.reset_interview_state(clear_config=True)


    # --- Helper Methods ---

    def _load_icon(self, filename, size):
        """Loads a CTkImage icon, handles errors."""
        try:
            path = os.path.join(ICON_PATH, filename)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Icon file not found at {path}")
            return ctk.CTkImage(Image.open(path), size=size)
        except FileNotFoundError as e:
            print(f"Warning: Icon not found - {e}. Using text button.")
            # Optionally show a warning messagebox once, maybe using a flag
            # messagebox.showwarning("Icon Warning", f"Could not load icon: {filename}.\nPlease ensure '{ICON_PATH}' folder exists and contains the icon files.")
            return None
        except Exception as e:
            print(f"Error loading icon {filename}: {e}")
            messagebox.showerror("Icon Error", f"Error loading icon {filename}: {e}")
            return None

    def _get_theme_color(self, color_name):
        """ Safely gets a color from the current theme. """
        try:
            # Access theme data (this might change in future CTk versions)
            theme_data = ctk.ThemeManager.theme
            # Try getting from CTkButton first, then CTkLabel, then fallback
            # Adjusted logic to handle the new white buttons better for history Q color
            if color_name == "button": # Let's pick a different color for Q in history now
                # Try the default theme's primary button color instead of our white override
                default_blue = "#1F6AA5" # Fallback if theme retrieval fails
                return theme_data.get("CTkButton", {}).get("fg_color", default_blue) if isinstance(theme_data.get("CTkButton", {}).get("fg_color"), str) else default_blue # Get original theme button color if possible
            elif color_name in theme_data.get("CTkLabel", {}):
                 return theme_data["CTkLabel"][color_name]
            elif color_name in theme_data.get("CTkFrame", {}):
                 return theme_data["CTkFrame"][color_name]
            else: # Fallback colors (adjust as needed)
                if color_name == "text": return "#DCE4EE" # Default dark mode text
                if color_name == "text_disabled": return "gray60"
                # button color fallback handled above
                return "white" # Absolute fallback
        except Exception as e:
            print(f"Warning: Could not get theme color '{color_name}': {e}")
            # Return reasonable fallbacks
            if color_name == "text": return "#DCE4EE"
            if color_name == "text_disabled": return "gray60"
            if color_name == "button": return "#1F6AA5" # Default blue button color
            return "white"

    def adjust_value(self, var, amount, min_val, max_val):
        """Helper to adjust IntVars for spinbox replacements."""
        current_val = var.get()
        new_val = current_val + amount
        if min_val <= new_val <= max_val:
            var.set(new_val)
            # Update internal state directly
            if var == self.num_topics_var:
                self.num_topics = new_val
                print(f"Number of topics set to: {self.num_topics}")
            if var == self.max_follow_ups_var:
                self.max_follow_ups = new_val
                print(f"Max follow-ups set to: {self.max_follow_ups}")

    def update_status(self, message, busy=False):
        """Update the main status/question display and optionally set busy cursor."""
        # Update Textbox
        self.current_q_text.configure(state="normal") # Enable to modify
        self.current_q_text.delete("1.0", "end")
        self.current_q_text.insert("1.0", message)
        self.current_q_text.configure(state="disabled") # Disable again

        # Update Cursor
        if busy:
            self.configure(cursor="watch")
        else:
            self.configure(cursor="")
        self.update_idletasks() # Ensure UI updates immediately

    def display_question(self, question_text):
        """Update the current question label and enable input."""
        self.update_status(question_text, busy=False) # Updates text and resets cursor
        self.enable_interview_controls()
        self.answer_input.focus()

    def add_to_history(self, text, tag=None):
        """Appends text to the history display with optional styling."""
        try:
            self.history_text.configure(state="normal") # Enable to modify
            if tag:
                self.history_text.insert("end", text, (tag,)) # Pass tag as a tuple
            else:
                self.history_text.insert("end", text)
            self.history_text.configure(state="disabled") # Disable again
            self.history_text.see("end") # Scroll to bottom
        except Exception as e:
            print(f"Error adding to history: {e}")
            # Attempt to add without tag if tagging failed
            try:
                self.history_text.insert("end", text)
                self.history_text.configure(state="disabled")
                self.history_text.see("end")
            except: pass # Ignore if adding fails completely

    def set_setup_controls_state(self, state):
        """Enable/Disable setup controls EXCEPT the Select PDF button."""
        # state should be "normal" or "disabled"
        self.job_desc_input.configure(state=state)
        self.set_spinbox_state(state)
        self.start_interview_btn.configure(state=state)
        # The select_btn state is managed separately in select_resume_file and reset

    def set_spinbox_state(self, state):
        """Enable/Disable the custom spinbox buttons."""
        self.topic_minus_btn.configure(state=state)
        self.topic_plus_btn.configure(state=state)
        self.followup_minus_btn.configure(state=state)
        self.followup_plus_btn.configure(state=state)
        # Also enable/disable labels visually if desired (optional)
        label_state = "normal" if state == "normal" else "disabled"
        # Note: CTkLabel doesn't have a 'state' like buttons/entries.
        # You might change text color to indicate disabled state if needed.
        # text_color = self._get_theme_color("text") if state == "normal" else self._get_theme_color("text_disabled")
        # self.num_topics_label.configure(text_color=text_color)
        # self.max_follow_ups_label.configure(text_color=text_color)


    def enable_interview_controls(self):
        """Enable answer input and submit button."""
        self.answer_input.configure(state="normal")
        self.submit_button.configure(state="normal")

    def disable_interview_controls(self):
        """Disable answer input and submit button."""
        self.answer_input.configure(state="disabled")
        self.submit_button.configure(state="disabled")

    def reset_interview_state(self, clear_config=True):
        """Clears UI elements and data, resetting to initial or post-config state."""
        print(f"Resetting interview state (clear_config={clear_config})...")
        # Clear conversational state
        self.initial_questions = []
        self.current_initial_q_index = -1
        self.current_topic_question = ""
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []

        # Clear/disable interview section
        self.disable_interview_controls()
        self.answer_input.delete("1.0", "end")

        # Clear history display
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        self.history_text.configure(state="disabled")

        if clear_config:
            # Full reset to initial application state
            self.pdf_filepath = None
            self.resume_content = ""
            self.job_description_text = ""

            # Reset file label using the Entry widget's methods
            self.file_label.configure(state="normal")
            self.file_label.delete(0, "end")
            self.file_label.insert(0, "No resume selected.")
            self.file_label.configure(state="disabled")

            self.select_btn.configure(state="normal") # Enable file selection

            # Clear and disable JD
            self.job_desc_input.configure(state="normal")
            self.job_desc_input.delete("1.0", "end")
            self.job_desc_input.configure(state="disabled")

            # Disable config and start button
            self.set_spinbox_state("disabled")
            self.start_interview_btn.configure(state="disabled")

            self.update_status("[Select Resume PDF above to enable setup]", busy=False)

            # Reset config values to defaults
            self.num_topics_var.set(DEFAULT_NUM_TOPICS)
            self.max_follow_ups_var.set(DEFAULT_MAX_FOLLOW_UPS)
            self.num_topics = DEFAULT_NUM_TOPICS
            self.max_follow_ups = DEFAULT_MAX_FOLLOW_UPS
        else:
             # Resetting after config, before interview starts (keep setup values/state)
             # Ensure setup controls remain disabled during interview generation/run
             self.set_setup_controls_state("disabled")
             # Select button should also remain disabled during interview
             self.select_btn.configure(state="disabled")
             self.update_status("[Ready to Start Interview]", busy=False)

        # Close review window if open (safe regardless of clear_config)
        if self.review_window and self.review_window.winfo_exists():
            print("Destroying existing review window during reset.")
            self.review_window.destroy()
        self.review_window = None # Important to reset the variable

        self.configure(cursor="") # Ensure cursor is reset
        print("Interview state reset complete.")


    # --- GUI Logic Methods ---

    def select_resume_file(self):
        """Handles resume selection, enables JD input and config."""
        filepath = filedialog.askopenfilename(
            title="Select Resume PDF",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not filepath:
            # User cancelled selection
            if not self.pdf_filepath: # Only update if no file was previously selected
                self.file_label.configure(state="normal")
                self.file_label.delete(0, "end")
                self.file_label.insert(0, "Selection cancelled.")
                self.file_label.configure(state="disabled")
            return

        self.pdf_filepath = filepath
        filename = os.path.basename(filepath)

        # Update the file label (Entry widget)
        self.file_label.configure(state="normal")
        self.file_label.delete(0, "end")
        self.file_label.insert(0, filename)
        self.file_label.configure(state="disabled")

        # Enable next steps
        self.job_desc_input.configure(state="normal")
        self.set_spinbox_state("normal")
        self.start_interview_btn.configure(state="normal")
        self.select_btn.configure(state="disabled") # Disable select btn after successful selection

        self.update_status("[Optional: Paste Job Description, adjust settings, then Start Interview]", busy=False)
        self.job_desc_input.focus() # Move focus to JD input

    def start_interview_process(self):
        """Reads JD, config, extracts text, generates questions, starts interview."""
        if not self.pdf_filepath:
            messagebox.showerror("Input Missing", "Please select a resume PDF file first.")
            return

        # --- Read Config and Inputs ---
        self.job_description_text = self.job_desc_input.get("1.0", "end-1c").strip() # Use -1c to exclude trailing newline
        # Values are already updated in self.num_topics / self.max_follow_ups by adjust_value
        # Re-read from IntVars just to be absolutely sure (though should be redundant)
        self.num_topics = self.num_topics_var.get()
        self.max_follow_ups = self.max_follow_ups_var.get()

        # Validation (redundant if adjust_value works, but good safety check)
        if not (MIN_TOPICS <= self.num_topics <= MAX_TOPICS):
            messagebox.showerror("Invalid Settings", f"Number of Topics must be between {MIN_TOPICS} and {MAX_TOPICS}.")
            return
        if not (MIN_FOLLOW_UPS <= self.max_follow_ups <= MAX_FOLLOW_UPS_LIMIT):
             messagebox.showerror("Invalid Settings", f"Maximum Follow-ups must be between {MIN_FOLLOW_UPS} and {MAX_FOLLOW_UPS_LIMIT}.")
             return

        print(f"Starting Interview Process: Topics={self.num_topics}, MaxFollowUps={self.max_follow_ups}")

        # --- Disable Setup & Start Processing ---
        self.set_setup_controls_state("disabled")
        self.select_btn.configure(state="disabled") # Ensure select is disabled
        # Reset only the interview part, keep config values
        self.reset_interview_state(clear_config=False)
        self.update_status("Extracting text from PDF...", busy=True)

        # --- Extract PDF Text ---
        self.resume_content = extract_text_from_pdf(self.pdf_filepath)
        if not self.resume_content:
            self.update_status("[Failed to extract text. Please select a valid PDF.]", busy=False)
            # Re-enable setup controls (except JD which might have content)
            self.select_btn.configure(state="normal") # Allow re-selection
            self.set_spinbox_state("normal")
            self.start_interview_btn.configure(state="normal")
            # Keep JD enabled if it had content, otherwise disable
            self.job_desc_input.configure(state="normal" if self.job_description_text else "disabled")
            return

        # --- Generate Initial Questions ---
        self.update_status(f"Generating {self.num_topics} initial interview questions...", busy=True)
        # Run generation in a separate thread or use async if it blocks GUI significantly
        # For simplicity here, we run it directly, but 'busy=True' helps visually
        self.initial_questions = generate_initial_questions(
            self.resume_content,
            job_desc_text=self.job_description_text,
            num_questions=self.num_topics
        )
        self.configure(cursor="") # Reset cursor after generation attempt

        if not self.initial_questions:
            self.update_status("[Failed to generate initial questions. Check logs/API key/Input Size.]", busy=False)
            # Re-enable setup controls fully for another attempt
            self.select_btn.configure(state="normal")
            self.job_desc_input.configure(state="normal")
            self.set_spinbox_state("normal")
            self.start_interview_btn.configure(state="normal")
            return

        # --- Start the Interview Flow ---
        self.current_initial_q_index = 0
        self.start_next_topic() # Display the first question


    def start_next_topic(self):
        """Displays the next initial question OR triggers the final review."""
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0
            self.current_topic_history = [] # Reset history for the new topic

            # Get the raw question string (might have number prefix)
            raw_q_text = self.initial_questions[self.current_initial_q_index]

            # Attempt to clean the question number prefix
            cleaned_q = raw_q_text.strip()
            if cleaned_q and cleaned_q[0].isdigit():
                parts = cleaned_q.split('.', 1)
                if len(parts) > 1:
                    self.current_topic_question = parts[1].strip()
                else: # Maybe just "1 Question text" without dot
                    parts = cleaned_q.split(' ', 1)
                    if len(parts) > 1 and parts[0].isdigit():
                         self.current_topic_question = parts[1].strip()
                    else: # Fallback: use raw text if parsing fails
                        self.current_topic_question = cleaned_q
            else: # No number prefix found
                 self.current_topic_question = cleaned_q

            topic_marker_text = f"\n--- Starting Topic {self.current_initial_q_index + 1} of {len(self.initial_questions)} ---\n"
            print(topic_marker_text.strip()) # Log to console
            self.add_to_history(topic_marker_text, tag="topic_marker") # Add marker to GUI history

            print(f"Asking Initial Question: {self.current_topic_question}")
            self.display_question(self.current_topic_question) # Display the cleaned question text
        else:
            # --- End of Interview ---
            print("\n--- Interview Finished ---")
            self.update_status("Interview finished. Generating final review & assessment...", busy=True)
            self.disable_interview_controls()

            # Generate review and assessment
            summary_review = generate_summary_review(self.current_full_interview_history)
            qual_assessment = generate_qualification_assessment(
                self.resume_content,
                self.job_description_text,
                self.current_full_interview_history
            )
            self.configure(cursor="") # Reset cursor after generation

            # Show review window (reset is handled when window is closed)
            self.show_final_review_window(summary_review, qual_assessment)
            self.update_status("[Interview Complete. Review window opened. Close it to reset for a new interview.]", busy=False)
            # DO NOT reset state here - wait for review window close command


    def _submit_answer_event(self, event=None):
        """Handles the Enter key press in the answer box."""
        # Check if submit button is active to prevent submission when disabled
        if self.submit_button.cget('state') == "normal":
             print("Enter pressed, submitting answer...")
             self.submit_answer()
             return "break" # Prevents the default newline insertion from Enter
        print("Enter pressed, but submit button is disabled.")
        return None # Allow default behavior if disabled

    def _insert_newline_event(self, event=None):
        """Handles Shift+Enter to allow newline insertion."""
        print("Shift+Enter pressed, allowing newline.")
        # Let CTkTextbox handle the newline insertion by not returning "break"
        pass

    def submit_answer(self):
        """Handles answer submission, generates follow-ups or moves to the next topic."""
        user_answer = self.answer_input.get("1.0", "end-1c").strip()
        if not user_answer:
            messagebox.showwarning("Input Required", "Please enter an answer before submitting.")
            return

        # Get last question asked (which is currently displayed)
        # Use self.current_topic_question for follow-up context, but log the displayed one
        last_question_asked_display = self.current_q_text.get("1.0", "end-1c").strip()

        print(f"User Answer: {user_answer}")

        # Store Q/A pair
        q_data = {"q": last_question_asked_display, "a": user_answer}
        self.current_topic_history.append(q_data)      # For follow-up context within topic
        self.current_full_interview_history.append(q_data) # For final review

        # Update GUI History
        self.add_to_history(f"Q: {last_question_asked_display}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        # Clear input field & disable controls while thinking
        self.answer_input.delete("1.0", "end")
        self.disable_interview_controls()
        self.update_status("Thinking of next question...", busy=True)

        # --- Decide next step: Follow-up or Next Topic ---
        if self.follow_up_count < self.max_follow_ups:
            # Try to generate a follow-up
            follow_up_q = generate_follow_up_question(
                self.current_topic_question, # Use the original topic question as context
                user_answer,
                self.current_topic_history   # Pass history *for this topic*
            )

            if follow_up_q:
                # Follow-up question generated
                self.follow_up_count += 1
                print(f"Asking Follow-up {self.follow_up_count}/{self.max_follow_ups}: {follow_up_q}")
                self.display_question(follow_up_q) # Display the follow-up
            else:
                # No follow-up generated (or [END TOPIC] signal)
                print("Ending topic (no more follow-ups generated or signal received).")
                self.current_initial_q_index += 1
                self.start_next_topic() # Move to the next initial question
        else:
            # Reached max follow-ups for this topic
            print(f"Reached max follow-ups ({self.max_follow_ups}) for this topic.")
            self.current_initial_q_index += 1
            self.start_next_topic() # Move to the next initial question

        # Ensure cursor is reset if generation was fast (might already be done by display_question)
        if self.cget('cursor') == "watch":
            self.configure(cursor="")


    def _close_review_and_reset(self):
        """Destroys the review window and resets the main app state."""
        print("Close review window requested.")
        if self.review_window and self.review_window.winfo_exists():
            self.review_window.destroy()
        self.review_window = None # Clear the reference

        # Now reset the main application after closing the review
        print("Triggering main app reset after closing review.")
        self.reset_interview_state(clear_config=True)


    def show_final_review_window(self, summary_review_text, qualification_assessment_text):
        """Creates and displays a Toplevel window with the final review using customtkinter."""
        if self.review_window is not None and self.review_window.winfo_exists():
             print("Review window already exists, bringing to front.")
             self.review_window.lift()
             self.review_window.focus_set()
             return # Don't create a new one

        print("Creating review window...")
        self.review_window = ctk.CTkToplevel(self)
        self.review_window.title("Interview Review & Assessment")
        self.review_window.geometry("800x750") # Adjusted size
        self.review_window.transient(self) # Keep on top of main window
        self.review_window.grab_set()      # Modal behavior

        # Configure grid
        self.review_window.grid_columnconfigure(0, weight=1)
        self.review_window.grid_rowconfigure(0, weight=1) # Summary frame row
        self.review_window.grid_rowconfigure(1, weight=1) # Assessment frame row
        self.review_window.grid_rowconfigure(2, weight=0) # Button row

        # --- Frame for Summary/Review ---
        review_frame = ctk.CTkFrame(self.review_window, corner_radius=10)
        review_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        review_frame.grid_columnconfigure(0, weight=1); review_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(review_frame, text="Interview Performance Summary & Feedback", font=self.font_bold).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        review_text_widget = ctk.CTkTextbox(review_frame, wrap="word", font=self.font_small, corner_radius=8)
        review_text_widget.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        review_text_widget.insert("1.0", summary_review_text if summary_review_text else "Could not generate summary/review.")
        review_text_widget.configure(state="disabled")

        # --- Frame for Qualification Assessment ---
        qual_frame = ctk.CTkFrame(self.review_window, corner_radius=10)
        qual_frame.grid(row=1, column=0, padx=10, pady=(5, 5), sticky="nsew")
        qual_frame.grid_columnconfigure(0, weight=1); qual_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(qual_frame, text="Qualification Assessment vs. Job Description", font=self.font_bold).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        qual_text_widget = ctk.CTkTextbox(qual_frame, wrap="word", font=self.font_small, corner_radius=8)
        qual_text_widget.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        qual_text_widget.insert("1.0", qualification_assessment_text if qualification_assessment_text else "Could not generate qualification assessment (e.g., no JD provided).")
        qual_text_widget.configure(state="disabled")

        # --- Close Button ---
        # Use the combined close and reset command
        close_button = ctk.CTkButton(
            self.review_window,
            text="Close and Reset",
            command=self._close_review_and_reset, # Use the new method
            width=150,
            corner_radius=8,
            font = self.font_bold,
            fg_color="white", text_color="black", hover_color="gray90" # White background
            )
        close_button.grid(row=2, column=0, pady=(10, 10))

        # Ensure the window appears on top and gets focus
        self.review_window.after(150, self.review_window.lift) # Slightly longer delay
        self.review_window.after(200, self.review_window.focus_set)

        # Make closing the window via 'X' also trigger the reset
        self.review_window.protocol("WM_DELETE_WINDOW", self._close_review_and_reset)


# --- Main Execution ---
if __name__ == "__main__":
    # Ensure icons folder exists (optional: create if missing)
    if not os.path.exists(ICON_PATH):
        print(f"Warning: Icon folder '{ICON_PATH}' not found. Icons will be missing.")
        # try:
        #     os.makedirs(ICON_PATH)
        #     print(f"Created missing icon folder '{ICON_PATH}'. Please add icon files.")
        # except OSError as e:
        #     print(f"Error: Could not create icon folder '{ICON_PATH}': {e}")

    # Check for .env file before starting GUI
    if not os.path.exists(".env"):
         messagebox.showwarning("Configuration Warning", "'.env' file not found.\nPlease create a file named '.env' in the application directory and add your Google API key like this:\n\nGOOGLE_API_KEY=YOUR_ACTUAL_API_KEY")
         # Decide if you want to exit or proceed (Gemini config will fail later)
         # sys.exit("Exiting due to missing .env file.")

    app = InterviewApp()
    # Initial state is set at the end of __init__ after checking API key config
    app.mainloop()
    print("\n--- Program End ---")