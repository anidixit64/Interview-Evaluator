import React, { useState } from 'react';
import './App.css';

function App() {
  const [resumeText, setResumeText] = useState('');
  const [jobText, setJobText] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (resumeText.trim() && jobText.trim()) {
      console.log('Resume:', resumeText);
      console.log('Job Description:', jobText);
      setSubmitted(true);
    } else {
      alert('Please fill out both fields before submitting.');
    }
  };

  return (
    <div className="container">
      <h1>Interview Evaluator</h1>
      <div className="textbox-wrapper">
        <div className="textbox">
          <h2>Resume</h2>
          <textarea
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder="Paste your resume here..."
          />
        </div>
        <div className="textbox">
          <h2>Job Description</h2>
          <textarea
            value={jobText}
            onChange={(e) => setJobText(e.target.value)}
            placeholder="Paste job description here..."
          />
        </div>
      </div>
      <button onClick={handleSubmit}>Submit</button>
      {submitted && <p>Text submitted successfully. Ready for analysis!</p>}
    </div>
  );
}

export default App;
