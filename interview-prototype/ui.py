# ui.py
# Handles the user interface using customtkinter. Calls logic from logic.py & audio_handler.py

import os
import sys
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image
import logic # Import the logic module
import audio_handler # Import the audio handler
from audio_handler import RECORDINGS_DIR # Import the constant
import queue # Import queue for STT results

# --- UI Constants ---
ICON_PATH = "icons"

class InterviewApp(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Interview Bot Pro")
        self.geometry("850x1000")

        # --- Appearance ---
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- Load Icons ---
        self.icon_size = (20, 20)
        self.small_icon_size = (16, 16)
        self.select_icon = self._load_icon("folder.png", self.icon_size)
        self.start_icon = self._load_icon("play.png", self.icon_size)
        self.submit_icon = self._load_icon("send.png", self.icon_size)
        self.plus_icon = self._load_icon("plus.png", self.small_icon_size)
        self.minus_icon = self._load_icon("minus.png", self.small_icon_size)
        self.record_icon = self._load_icon("send.png", self.icon_size)

        # --- Fonts ---
        self.font_default = ctk.CTkFont(size=12)
        self.font_bold = ctk.CTkFont(size=12, weight="bold")
        self.font_small = ctk.CTkFont(size=11)
        self.font_large_bold = ctk.CTkFont(size=15, weight="bold")
        self.font_history = ctk.CTkFont(size=10)

        # --- State Variables ---
        self.pdf_filepath = None
        self.resume_content = ""
        self.job_description_text = ""
        self.num_topics_var = ctk.IntVar(value=logic.DEFAULT_NUM_TOPICS)
        self.max_follow_ups_var = ctk.IntVar(value=logic.DEFAULT_MAX_FOLLOW_UPS)
        self.num_topics = logic.DEFAULT_NUM_TOPICS
        self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
        self.initial_questions = [] # Raw questions from generator
        self.cleaned_initial_questions = set() # Processed initial Qs for matching
        self.current_initial_q_index = -1
        self.current_topic_question = "" # The *cleaned* initial question for the current topic
        self.current_topic_history = []
        self.follow_up_count = 0
        self.current_full_interview_history = []
        self.review_window = None
        self.use_speech_input_var = ctk.BooleanVar(value=False)
        self.is_recording = False

        # --- Main Layout using Grid ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=2)

        # --- Section 1: Setup ---
        setup_frame = ctk.CTkFrame(self, corner_radius=10)
        setup_frame.grid(row=0, column=0, padx=10, pady=10, sticky="new")
        setup_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(setup_frame, text="Setup", font=self.font_large_bold).grid(row=0, column=0, columnspan=4, pady=(5, 10), padx=10, sticky="w")
        # Row 1: Resume
        self.select_btn = ctk.CTkButton( setup_frame, text="Select Resume PDF", command=self.select_resume_file, image=self.select_icon, compound="left", corner_radius=8, font=self.font_default, fg_color="white", text_color="black", hover_color="gray90")
        self.select_btn.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
        self.file_label = ctk.CTkEntry(setup_frame, placeholder_text="No resume selected.", state="disabled", font=self.font_small)
        self.file_label.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        # Row 2: Job Description
        ctk.CTkLabel(setup_frame, text="Job Description (Optional):", font=self.font_default).grid(row=2, column=0, padx=(10, 5), pady=(10,5), sticky="nw")
        self.job_desc_input = ctk.CTkTextbox( setup_frame, height=100, corner_radius=8, wrap="word", state="disabled", font=self.font_small)
        self.job_desc_input.grid(row=2, column=1, columnspan=3, padx=5, pady=(10,5), sticky="ew")
        # Row 3: Configuration (Topics, Followups)
        config_frame_row3 = ctk.CTkFrame(setup_frame, fg_color="transparent")
        config_frame_row3.grid(row=3, column=0, columnspan=4, pady=(5, 5), sticky="w", padx=5)
        ctk.CTkLabel(config_frame_row3, text="Topics:", font=self.font_default).pack(side="left", padx=(5, 2))
        self.topic_minus_btn = ctk.CTkButton( config_frame_row3, text="", image=self.minus_icon, width=28, height=28, command=lambda: self.adjust_value(self.num_topics_var, -1, logic.MIN_TOPICS, logic.MAX_TOPICS), state="disabled", fg_color="white", text_color="black", hover_color="gray90")
        self.topic_minus_btn.pack(side="left", padx=(0, 0))
        self.num_topics_label = ctk.CTkLabel(config_frame_row3, textvariable=self.num_topics_var, width=25, justify="center", font=self.font_default)
        self.num_topics_label.pack(side="left", padx=(2, 2))
        self.topic_plus_btn = ctk.CTkButton( config_frame_row3, text="", image=self.plus_icon, width=28, height=28, command=lambda: self.adjust_value(self.num_topics_var, 1, logic.MIN_TOPICS, logic.MAX_TOPICS), state="disabled", fg_color="white", text_color="black", hover_color="gray90")
        self.topic_plus_btn.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(config_frame_row3, text="Max Follow-ups:", font=self.font_default).pack(side="left", padx=(5, 2))
        self.followup_minus_btn = ctk.CTkButton( config_frame_row3, text="", image=self.minus_icon, width=28, height=28, command=lambda: self.adjust_value(self.max_follow_ups_var, -1, logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT), state="disabled", fg_color="white", text_color="black", hover_color="gray90")
        self.followup_minus_btn.pack(side="left", padx=(0, 0))
        self.max_follow_ups_label = ctk.CTkLabel(config_frame_row3, textvariable=self.max_follow_ups_var, width=25, justify="center", font=self.font_default)
        self.max_follow_ups_label.pack(side="left", padx=(2, 2))
        self.followup_plus_btn = ctk.CTkButton( config_frame_row3, text="", image=self.plus_icon, width=28, height=28, command=lambda: self.adjust_value(self.max_follow_ups_var, 1, logic.MIN_FOLLOW_UPS, logic.MAX_FOLLOW_UPS_LIMIT), state="disabled", fg_color="white", text_color="black", hover_color="gray90")
        self.followup_plus_btn.pack(side="left", padx=(0, 20))
        # Row 4: Input Mode Checkbox and Start Button
        config_frame_row4 = ctk.CTkFrame(setup_frame, fg_color="transparent")
        config_frame_row4.grid(row=4, column=0, columnspan=4, pady=(0, 10), sticky="w", padx=5)
        self.speech_checkbox = ctk.CTkCheckBox( config_frame_row4, text="Use Speech Input", variable=self.use_speech_input_var, onvalue=True, offvalue=False, command=self.update_submit_button_text, state="disabled", font=self.font_default)
        self.speech_checkbox.pack(side="left", padx=(5, 20))
        self.start_interview_btn = ctk.CTkButton( config_frame_row4, text="Start Interview", command=self.start_interview_process, state="disabled", image=self.start_icon, compound="left", corner_radius=8, font=self.font_bold, fg_color="white", text_color="black", hover_color="gray90")
        self.start_interview_btn.pack(side="left", padx=(10, 0))

        # --- Section 2: Interview Interaction ---
        interview_frame = ctk.CTkFrame(self, corner_radius=10)
        interview_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        interview_frame.grid_columnconfigure(0, weight=1)
        interview_frame.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(interview_frame, text="Interview", font=self.font_large_bold).grid(row=0, column=0, pady=(5, 10), padx=10, sticky="w")
        self.current_q_label = ctk.CTkLabel(interview_frame, text="Interviewer:", font=self.font_bold)
        self.current_q_label.grid(row=1, column=0, padx=10, sticky="w")
        self.current_q_text = ctk.CTkTextbox( interview_frame, height=80, wrap="word", state="disabled", font=self.font_default, activate_scrollbars=True, fg_color="transparent")
        self.current_q_text.grid(row=2, column=0, padx=10, pady=(2, 10), sticky="ew")
        self.answer_label = ctk.CTkLabel(interview_frame, text="Your Answer:", font=self.font_bold)
        self.answer_label.grid(row=3, column=0, padx=10, pady=(5,0), sticky="w")
        self.answer_input = ctk.CTkTextbox( interview_frame, height=150, wrap="word", state="disabled", corner_radius=8, font=self.font_default)
        self.answer_input.grid(row=4, column=0, padx=10, pady=(2, 10), sticky="nsew")
        submit_frame = ctk.CTkFrame(interview_frame, fg_color="transparent")
        submit_frame.grid(row=5, column=0, pady=(5, 10))
        submit_frame.grid_columnconfigure(0, weight=1)
        self.submit_button = ctk.CTkButton( submit_frame, text="Submit Answer", command=self.handle_answer_submission, state="disabled", image=self.submit_icon, compound="left", corner_radius=8, font=self.font_bold, fg_color="white", text_color="black", hover_color="gray90")
        self.submit_button.grid(row=0, column=0)
        self.answer_input.bind("<Return>", self._submit_answer_event)
        self.answer_input.bind("<Shift-Return>", self._insert_newline_event)

        # --- Section 3: History ---
        history_frame = ctk.CTkFrame(self, corner_radius=10)
        history_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        history_frame.grid_columnconfigure(0, weight=1)
        history_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(history_frame, text="History", font=self.font_large_bold).grid(row=0, column=0, pady=(5, 5), padx=10, sticky="w")
        self.history_text = ctk.CTkTextbox( history_frame, wrap="word", state="disabled", corner_radius=8, font=self.font_history)
        self.history_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        q_color = self._get_theme_color("button")
        topic_color = self._get_theme_color("text_disabled")
        answer_color = self._get_theme_color("text")
        self.history_text.tag_config("question_style", foreground=q_color)
        self.history_text.tag_config("answer_style", foreground=answer_color)
        self.history_text.tag_config("topic_marker", foreground=topic_color)

        # --- Initial Setup ---
        self.reset_interview_state(clear_config=True)
        self.check_stt_queue()

    # --- Helper Methods ---

    def _load_icon(self, filename, size):
        try:
            path = os.path.join(ICON_PATH, filename)
            if not os.path.exists(path): return None
            return ctk.CTkImage(Image.open(path), size=size)
        except Exception as e: print(f"Error loading icon {filename}: {e}"); return None

    def _get_theme_color(self, color_name):
        try:
            theme_data = ctk.ThemeManager.theme
            if color_name == "button":
                default_blue = "#1F6AA5"; return theme_data.get("CTkButton", {}).get("fg_color", default_blue) if isinstance(theme_data.get("CTkButton", {}).get("fg_color"), str) else default_blue
            elif color_name in theme_data.get("CTkLabel", {}): return theme_data["CTkLabel"][color_name]
            elif color_name in theme_data.get("CTkFrame", {}): return theme_data["CTkFrame"][color_name]
            else:
                if color_name == "text": return "#DCE4EE"
                if color_name == "text_disabled": return "gray60"
                return "white"
        except Exception as e:
            if color_name == "text": return "#DCE4EE"
            if color_name == "text_disabled": return "gray60"
            if color_name == "button": return "#1F6AA5"
            return "white"

    def adjust_value(self, var, amount, min_val, max_val):
        current_val = var.get(); new_val = current_val + amount
        if min_val <= new_val <= max_val:
            var.set(new_val)
            if var == self.num_topics_var: self.num_topics = new_val
            if var == self.max_follow_ups_var: self.max_follow_ups = new_val

    def update_status(self, message, busy=False):
        if not self.is_recording:
            self.current_q_text.configure(state="normal"); self.current_q_text.delete("1.0", "end"); self.current_q_text.insert("1.0", message); self.current_q_text.configure(state="disabled")
        if busy: self.configure(cursor="watch")
        else: self.configure(cursor="")
        self.update_idletasks()

    def display_question(self, question_text):
        self.update_status(question_text, busy=False)
        try: audio_handler.speak_text(question_text)
        except Exception as e: print(f"UI Error: Failed to initiate TTS: {e}")
        self.enable_interview_controls()
        if not self.use_speech_input_var.get(): self.answer_input.focus()

    def add_to_history(self, text, tag=None):
        try:
            self.history_text.configure(state="normal")
            if tag: self.history_text.insert("end", text, (tag,))
            else: self.history_text.insert("end", text)
            self.history_text.configure(state="disabled"); self.history_text.see("end")
        except Exception as e: print(f"Error adding to history: {e}")

    def set_setup_controls_state(self, state):
        self.job_desc_input.configure(state=state); self.set_spinbox_state(state); self.start_interview_btn.configure(state=state); self.speech_checkbox.configure(state=state)

    def set_spinbox_state(self, state):
        if hasattr(self, 'topic_minus_btn'): self.topic_minus_btn.configure(state=state)
        if hasattr(self, 'topic_plus_btn'): self.topic_plus_btn.configure(state=state)
        if hasattr(self, 'followup_minus_btn'): self.followup_minus_btn.configure(state=state)
        if hasattr(self, 'followup_plus_btn'): self.followup_plus_btn.configure(state=state)

    def enable_interview_controls(self):
        text_input_state = "disabled" if self.use_speech_input_var.get() else "normal"
        if hasattr(self, 'answer_input'): self.answer_input.configure(state=text_input_state)
        if hasattr(self, 'submit_button'): self.submit_button.configure(state="normal")
        self.is_recording = False; self.update_submit_button_text()

    def disable_interview_controls(self, is_recording_stt=False):
        if hasattr(self, 'answer_input'): self.answer_input.configure(state="disabled")
        if hasattr(self, 'submit_button'): self.submit_button.configure(state="disabled")
        self.is_recording = is_recording_stt

    def reset_interview_state(self, clear_config=True):
        print(f"Resetting interview state (clear_config={clear_config})...")
        self.initial_questions = []; self.cleaned_initial_questions = set() # <-- Reset set
        self.current_initial_q_index = -1; self.current_topic_question = ""
        self.current_topic_history = []; self.follow_up_count = 0
        self.current_full_interview_history = []; self.is_recording = False

        self.disable_interview_controls()
        if hasattr(self, 'answer_input') and self.answer_input.winfo_exists(): self.answer_input.delete("1.0", "end")
        if hasattr(self, 'history_text') and self.history_text.winfo_exists(): self.history_text.configure(state="normal"); self.history_text.delete("1.0", "end"); self.history_text.configure(state="disabled")

        if clear_config:
            self.pdf_filepath = None; self.resume_content = ""; self.job_description_text = ""
            if hasattr(self, 'file_label') and self.file_label.winfo_exists(): self.file_label.configure(state="normal"); self.file_label.delete(0, "end"); self.file_label.insert(0, "No resume selected."); self.file_label.configure(state="disabled")
            if hasattr(self, 'select_btn') and self.select_btn.winfo_exists(): self.select_btn.configure(state="normal")
            if hasattr(self, 'job_desc_input') and self.job_desc_input.winfo_exists(): self.job_desc_input.configure(state="normal"); self.job_desc_input.delete("1.0", "end"); self.job_desc_input.configure(state="disabled")
            self.set_setup_controls_state("disabled")
            if hasattr(self, 'current_q_text') and self.current_q_text.winfo_exists(): self.update_status("[Select Resume PDF above to enable setup]", busy=False)
            self.num_topics_var.set(logic.DEFAULT_NUM_TOPICS); self.max_follow_ups_var.set(logic.DEFAULT_MAX_FOLLOW_UPS)
            self.num_topics = logic.DEFAULT_NUM_TOPICS; self.max_follow_ups = logic.DEFAULT_MAX_FOLLOW_UPS
            self.use_speech_input_var.set(False); self.update_submit_button_text()
        else:
             self.set_setup_controls_state("disabled")
             if hasattr(self, 'select_btn') and self.select_btn.winfo_exists(): self.select_btn.configure(state="disabled")
             if hasattr(self, 'current_q_text') and self.current_q_text.winfo_exists(): self.update_status("[Ready to Start Interview]", busy=False)

        if self.review_window and self.review_window.winfo_exists(): self.review_window.destroy()
        self.review_window = None; self.configure(cursor="")
        print("Interview state reset complete.")

    # --- Helper to clean question prefix ---
    def _clean_question_text(self, raw_q_text):
        """Removes number prefixes like '1. ' or '1 ' from question text."""
        cleaned_q = raw_q_text.strip()
        if cleaned_q and cleaned_q[0].isdigit():
            parts = cleaned_q.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
            else:
                parts = cleaned_q.split(' ', 1)
                if len(parts) > 1 and parts[0].isdigit(): return parts[1].strip()
                else: return cleaned_q
        else: return cleaned_q

    # --- MODIFIED: Transcript Saving with Grouping ---
    def save_transcript_to_file(self):
        """Saves the full interview history to transcript.txt, grouping by topic."""
        if not self.current_full_interview_history:
            print("No interview history to save."); return

        if not self.cleaned_initial_questions:
             print("Warning: Cleaned initial questions set is empty. Cannot structure transcript correctly.")
             # Fallback: Save flat list if structure info is missing
             try:
                filepath = os.path.join(RECORDINGS_DIR, "transcript_flat.txt")
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    for i, qa in enumerate(self.current_full_interview_history):
                        f.write(f"{i+1}. Q: {qa.get('q', 'N/A')}\n   A: {qa.get('a', 'N/A')}\n\n")
                print(f"Saved flat transcript to {filepath}")
             except Exception as e: print(f"Error saving flat transcript: {e}")
             return

        transcript_lines = []
        current_topic_num = 0
        current_follow_up_num = 0

        try:
            for qa_pair in self.current_full_interview_history:
                q = qa_pair.get('q', 'MISSING QUESTION')
                a = qa_pair.get('a', 'MISSING ANSWER')

                # Check if this question matches one of the *cleaned* initial questions
                is_initial = q in self.cleaned_initial_questions

                if is_initial:
                    current_topic_num += 1
                    current_follow_up_num = 0 # Reset follow-up count for new topic
                    if current_topic_num > 1:
                         transcript_lines.append("-------------------------") # Separator
                    transcript_lines.append(f"Question {current_topic_num}: {q}")
                    transcript_lines.append(f"Answer: {a}")
                else: # It's a follow-up
                    current_follow_up_num += 1
                    # Add extra newline before follow-up for spacing
                    transcript_lines.append("")
                    transcript_lines.append(f"Follow Up {current_follow_up_num}: {q}")
                    transcript_lines.append(f"Answer: {a}")

                transcript_lines.append("") # Add blank line after each Answer

            # Ensure the recordings directory exists
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            filepath = os.path.join(RECORDINGS_DIR, "transcript.txt")
            print(f"Saving grouped transcript to {filepath}...")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(transcript_lines).strip()) # Write joined lines, remove trailing newline
            print("Grouped transcript saved successfully.")

        except Exception as e:
            print(f"Error saving grouped transcript: {e}")
            messagebox.showerror("File Save Error", f"Could not save transcript to {filepath}:\n{e}")


    # --- GUI Logic Methods ---

    def update_submit_button_text(self):
        if not hasattr(self, 'submit_button'): return
        if self.use_speech_input_var.get():
            self.submit_button.configure(text="Record Answer", image=self.record_icon)
            self.answer_input.configure(state="disabled"); self.answer_input.delete("1.0", "end")
        else:
            self.submit_button.configure(text="Submit Answer", image=self.submit_icon)
            if self.submit_button.cget('state') == 'normal': self.answer_input.configure(state="normal"); self.answer_input.focus()
            else: self.answer_input.configure(state="disabled")

    def select_resume_file(self):
        filepath = filedialog.askopenfilename(title="Select Resume PDF", filetypes=[("PDF Files", "*.pdf")])
        if not filepath:
            if not self.pdf_filepath: self.file_label.configure(state="normal"); self.file_label.delete(0, "end"); self.file_label.insert(0, "Selection cancelled."); self.file_label.configure(state="disabled")
            return
        self.pdf_filepath = filepath; filename = os.path.basename(filepath)
        self.file_label.configure(state="normal"); self.file_label.delete(0, "end"); self.file_label.insert(0, filename); self.file_label.configure(state="disabled")
        self.set_setup_controls_state("normal"); self.select_btn.configure(state="disabled")
        self.update_status("[Optional: Paste JD, adjust settings, then Start]", busy=False); self.job_desc_input.focus()

    def start_interview_process(self):
        if not self.pdf_filepath: messagebox.showerror("Input Missing", "Select resume PDF."); return
        self.job_description_text = self.job_desc_input.get("1.0", "end-1c").strip()
        self.num_topics = self.num_topics_var.get(); self.max_follow_ups = self.max_follow_ups_var.get()
        if not (logic.MIN_TOPICS <= self.num_topics <= logic.MAX_TOPICS): messagebox.showerror("Invalid Settings", f"Topics: {logic.MIN_TOPICS}-{logic.MAX_TOPICS}."); return
        if not (logic.MIN_FOLLOW_UPS <= self.max_follow_ups <= logic.MAX_FOLLOW_UPS_LIMIT): messagebox.showerror("Invalid Settings", f"Follow-ups: {logic.MIN_FOLLOW_UPS}-{logic.MAX_FOLLOW_UPS_LIMIT}."); return
        print(f"Starting: Topics={self.num_topics}, FollowUps={self.max_follow_ups}, Speech={self.use_speech_input_var.get()}")
        self.set_setup_controls_state("disabled"); self.select_btn.configure(state="disabled")
        self.reset_interview_state(clear_config=False)
        self.update_status("Extracting PDF...", busy=True)
        self.resume_content = logic.extract_text_from_pdf(self.pdf_filepath)
        if not self.resume_content: self.update_status("[PDF Error]", busy=False); self.select_btn.configure(state="normal"); self.set_setup_controls_state("normal"); return
        self.update_status(f"Generating {self.num_topics} questions...", busy=True)
        self.initial_questions = logic.generate_initial_questions( self.resume_content, job_desc_text=self.job_description_text, num_questions=self.num_topics)
        self.configure(cursor="")
        if not self.initial_questions: self.update_status("[Generation Error]", busy=False); self.select_btn.configure(state="normal"); self.set_setup_controls_state("normal"); return

        # --- Prepare cleaned initial questions set ---
        self.cleaned_initial_questions = {self._clean_question_text(q) for q in self.initial_questions}
        # -------------------------------------------

        self.current_initial_q_index = 0; self.start_next_topic()

    def start_next_topic(self):
        if 0 <= self.current_initial_q_index < len(self.initial_questions):
            self.follow_up_count = 0; self.current_topic_history = []
            raw_q_text = self.initial_questions[self.current_initial_q_index]
            self.current_topic_question = self._clean_question_text(raw_q_text) # Store cleaned version
            topic_marker = f"\n--- Topic {self.current_initial_q_index + 1}/{len(self.initial_questions)} ---\n"
            print(topic_marker.strip()); self.add_to_history(topic_marker, tag="topic_marker")
            print(f"Asking Initial: {self.current_topic_question}")
            self.display_question(self.current_topic_question)
        else: # End of interview
            print("\n--- Interview Finished ---")
            self.update_status("Saving transcript & generating review...", busy=True); self.disable_interview_controls()
            self.save_transcript_to_file() # <-- Save transcript
            summary = logic.generate_summary_review(self.current_full_interview_history)
            assessment = logic.generate_qualification_assessment( self.resume_content, self.job_description_text, self.current_full_interview_history)
            self.configure(cursor=""); self.show_final_review_window(summary, assessment)
            self.update_status("[Complete. Review window open...]", busy=False)

    def _submit_answer_event(self, event=None):
        if not self.use_speech_input_var.get() and self.submit_button.cget('state') == "normal": self.handle_answer_submission(); return "break"
        return None

    def _insert_newline_event(self, event=None):
        if not self.use_speech_input_var.get(): pass
        else: return "break"

    def handle_answer_submission(self):
        if self.is_recording: return
        if self.use_speech_input_var.get():
            print("Record button."); self.disable_interview_controls(is_recording_stt=True); self.update_status_stt("STT_Status: Starting Mic...")
            self.answer_input.configure(state="normal"); self.answer_input.delete("1.0", "end"); self.answer_input.configure(state="disabled")
            topic_idx = self.current_initial_q_index + 1; followup_idx = self.follow_up_count
            audio_handler.start_speech_recognition( topic_idx=topic_idx, follow_up_idx=followup_idx)
        else:
            print("Submit button."); user_answer = self.answer_input.get("1.0", "end-1c").strip()
            if not user_answer: messagebox.showwarning("Input Required", "Enter answer."); return
            self.process_answer(user_answer)

    def update_status_stt(self, message):
         display_message = message
         if message == "STT_Status: Adjusting...": display_message = "[Calibrating Mic...]"
         elif message == "STT_Status: Listening...": display_message = "[Listening... Speak Now]"
         elif message == "STT_Status: Processing...": display_message = "[Processing Speech...]"
         elif message.startswith("STT_Error:"): display_message = f"[Error: {message.split(':', 1)[1].strip()}]"
         elif message.startswith("STT_Success:"): display_message = "[Speech Recognized]"
         self.current_q_text.configure(state="normal"); self.current_q_text.delete("1.0", "end"); self.current_q_text.insert("1.0", display_message); self.current_q_text.configure(state="disabled")
         self.update_idletasks()

    def check_stt_queue(self):
        try:
            result = audio_handler.stt_result_queue.get_nowait()
            if result.startswith("STT_Status:"): self.update_status_stt(result)
            elif result.startswith("STT_Success:"):
                transcript = result.split(":", 1)[1].strip()
                self.update_status_stt(result)
                self.answer_input.configure(state="normal"); self.answer_input.delete("1.0", "end"); self.answer_input.insert("1.0", transcript); self.answer_input.configure(state="disabled")
                self.process_answer(transcript)
            elif result.startswith("STT_Error:"):
                self.update_status_stt(result)
                messagebox.showerror("STT Error", result.split(":", 1)[1].strip())
                self.enable_interview_controls()
        except queue.Empty: pass
        except Exception as e: print(f"STT queue error: {e}"); self.enable_interview_controls()
        self.after(100, self.check_stt_queue)

    def process_answer(self, user_answer):
        last_q_disp = self.current_q_text.get("1.0", "end-1c").strip()
        # Try to get actual last Q if status bar shows STT message
        last_q = self.current_topic_question # Default to current topic Q
        if last_q_disp.startswith("["):
            # More robust: Check if current_topic_history has entries
            if self.current_topic_history:
                last_q = self.current_topic_history[-1]['q'] # Use last question recorded for this topic
        else:
            last_q = last_q_disp # Use displayed text if not STT status


        print(f"Processing Answer: {user_answer}")
        q_data = {"q": last_q, "a": user_answer} # Use determined last_q
        self.current_topic_history.append(q_data)
        self.current_full_interview_history.append(q_data)

        self.add_to_history(f"Q: {last_q}\n", tag="question_style")
        self.add_to_history(f"A: {user_answer}\n\n", tag="answer_style")

        self.answer_input.configure(state="normal"); self.answer_input.delete("1.0", "end"); self.disable_interview_controls()
        self.update_status("Thinking...", busy=True)

        if self.follow_up_count < self.max_follow_ups:
            follow_up_q = logic.generate_follow_up_question( self.current_topic_question, user_answer, self.current_topic_history)
            if follow_up_q:
                self.follow_up_count += 1; print(f"Follow-up {self.follow_up_count}/{self.max_follow_ups}: {follow_up_q}")
                # self.last_asked_question_text = follow_up_q # Consider adding this state var
                self.display_question(follow_up_q)
            else: print("Ending topic."); self.current_initial_q_index += 1; self.start_next_topic()
        else: print(f"Max follow-ups."); self.current_initial_q_index += 1; self.start_next_topic()
        if self.cget('cursor') == "watch": self.configure(cursor="")

    # --- Review Window Methods ---
    def _close_review_and_reset(self):
        print("Close review.");
        if self.review_window and self.review_window.winfo_exists(): self.review_window.destroy()
        self.review_window = None; print("Resetting."); self.reset_interview_state(clear_config=True)

    def show_final_review_window(self, summary, assessment):
        if self.review_window is not None and self.review_window.winfo_exists(): self.review_window.lift(); self.review_window.focus_set(); return
        print("Creating review window..."); self.review_window = ctk.CTkToplevel(self); self.review_window.title("Review & Assessment"); self.review_window.geometry("800x750"); self.review_window.transient(self); self.review_window.grab_set()
        self.review_window.grid_columnconfigure(0, weight=1); self.review_window.grid_rowconfigure(0, weight=1); self.review_window.grid_rowconfigure(1, weight=1); self.review_window.grid_rowconfigure(2, weight=0)
        frame1 = ctk.CTkFrame(self.review_window, corner_radius=10); frame1.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew"); frame1.grid_columnconfigure(0, weight=1); frame1.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame1, text="Performance Summary", font=self.font_bold).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        text1 = ctk.CTkTextbox(frame1, wrap="word", font=self.font_small, corner_radius=8); text1.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew"); text1.insert("1.0", summary or "N/A"); text1.configure(state="disabled")
        frame2 = ctk.CTkFrame(self.review_window, corner_radius=10); frame2.grid(row=1, column=0, padx=10, pady=(5, 5), sticky="nsew"); frame2.grid_columnconfigure(0, weight=1); frame2.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame2, text="Qualification Assessment", font=self.font_bold).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        text2 = ctk.CTkTextbox(frame2, wrap="word", font=self.font_small, corner_radius=8); text2.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew"); text2.insert("1.0", assessment or "N/A"); text2.configure(state="disabled")
        btn = ctk.CTkButton( self.review_window, text="Close & Reset", command=self._close_review_and_reset, width=150, corner_radius=8, font = self.font_bold, fg_color="white", text_color="black", hover_color="gray90"); btn.grid(row=2, column=0, pady=(10, 10))
        self.review_window.after(150, self.review_window.lift); self.review_window.after(200, self.review_window.focus_set); self.review_window.protocol("WM_DELETE_WINDOW", self._close_review_and_reset)


# --- Main Execution ---
if __name__ == "__main__":
    if not os.path.exists(ICON_PATH): print(f"Warning: Icon folder '{ICON_PATH}' not found.")
    if not os.path.exists(".env"): messagebox.showwarning("Config Warning", "'.env' file not found.")
    if not logic.configure_gemini(): messagebox.showerror("Fatal Error", "Gemini API failed."); sys.exit(1)
    else:
        # Check microphone
        stt_backend_found = False; audio_lib = "None"
        try:
            import sounddevice as sd;
            if sd.query_devices(kind='input'): print("Input ok (sounddevice)."); stt_backend_found = True; audio_lib="sounddevice"
        except Exception: pass
        if not stt_backend_found:
            try:
                 import pyaudio; p = pyaudio.PyAudio(); input_devices_found = False
                 for i in range(p.get_host_api_count()):
                      host_api_info = p.get_host_api_info_by_index(i)
                      for j in range(host_api_info.get('deviceCount')):
                          if p.get_device_info_by_host_api_device_index(i, j).get('maxInputChannels') > 0: input_devices_found = True; break
                      if input_devices_found: break
                 p.terminate();
                 if input_devices_found: print("Input ok (PyAudio)."); stt_backend_found = True; audio_lib="PyAudio"
            except Exception: pass
        if not stt_backend_found: messagebox.showwarning("Audio Warning", f"No input device found via {audio_lib}. Install/config needed for speech.")

        app = InterviewApp()
        app.mainloop()
    print("\n--- Program End ---")