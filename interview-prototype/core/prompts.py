# core/prompts.py
"""
Stores prompt templates used for interacting with the generative AI model.
Uses f-string syntax for parameterization.
"""

# --- Initial Questions Generation ---
INITIAL_QUESTIONS_PROMPT_TEMPLATE = """
You are a hiring manager preparing for a first-round screening interview.
Generate exactly {num_questions} insightful and tailored interview questions based on the candidate's resume and the provided job description.
Your questions should aim to:
  1. Assess the candidate's fit for the role described in the job description (if provided).
  2. Probe deeper into specific skills, experiences, or projects mentioned in the resume that seem relevant.
  3. Identify potential gaps or areas needing clarification.
Avoid generic questions. Phrase them clearly as conversation starters.
Format the output ONLY as a numbered list, with each question on a new line (e.g., '1. Question text'). Do not include any introductory or concluding text, just the numbered questions.

Candidate's Resume Text:
---
{resume_text}
---
{job_desc_section}

{num_questions} Tailored Interview Questions (Numbered List Only):
"""

JOB_DESC_SECTION_TEMPLATE = """
Job Description Text:
---
{job_desc_text}
---
"""

NO_JOB_DESC_SECTION = """
(No job description provided - focus questions based on the resume alone, imagining a generally relevant professional role).
"""


# --- Follow-up Question Generation ---
FOLLOW_UP_PROMPT_TEMPLATE = """
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

Follow-up Question or End Signal:
"""

# --- Summary Review Generation ---
SUMMARY_REVIEW_PROMPT_TEMPLATE = """
Act as an objective hiring manager critically reviewing a candidate's screening interview performance based ONLY on the transcript below. Your goal is to assess their communication, clarity, and the substance of their answers in this specific conversation. Ignore misspellings or minor gramatical errors in their responses.

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


# --- Content Score Generation ---
CONTENT_SCORE_PROMPT_TEMPLATE = """
Analyze the structure, clarity, and relevance of the candidate's answers based ONLY on the provided interview transcript. Do not evaluate the *correctness* of the answers, only how well they were presented and if they addressed the questions asked.

Transcript:
---
{transcript}
---

Provide the following:
1.  A score from 1 to 100 evaluating the overall effectiveness of the candidate's responses in terms of structure, clarity, and directness in answering the questions. Higher scores mean clearer, well-structured answers directly addressing the questions. Lower scores indicate rambling, unclear, or off-topic responses.
2.  A brief reasoning section explaining the score, highlighting specific examples from the transcript related to answer format and relevance. Use simple Markdown for formatting the reasoning (e.g., **bold**, `-` lists).

Output Format (Exactly as follows):
Score: [Your Score from 1-100]

Reasoning:
[Your reasoning text here using Markdown]
"""


# --- Qualification Assessment Generation ---
QUALIFICATION_ASSESSMENT_PROMPT_TEMPLATE = """
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

Provide the following assessment using simple Markdown for formatting (e.g., **bold** for headings, `-` or `*` for list items):

**1. Alignment with Key Requirements:**
    *   Identify key requirements from the JD.
    *   For each requirement:
        - **Requirement:** [Requirement text from JD]
        - **Assessment:** [Strong Match | Potential Match | Weak Match/Gap | Insufficient Information]
        - **Evidence:** [Cite brief evidence from R and/or T, like "(R) Mentions X", "(T) Described Y"]

**2. Overall Fit Assessment (Based on Provided Info):**
    - **Conclusion:** [Provide ONE concise rating ONLY from: Strong Fit | Potential Fit | Weak Fit/Gap | Insufficient Information | Unlikely Fit]
    - **Reasoning:** [Provide brief reasoning here, highlighting key strengths/gaps relative to JD requirements based on the evidence above.]

Base your assessment ONLY on the provided text (JD, R, T). Ensure the 'Conclusion' line contains ONLY the rating phrase.
"""