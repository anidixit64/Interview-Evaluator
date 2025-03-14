import React from "react";

function App() {
  return (
    <div style={styles.page}>
      <div style={styles.centeredText}>Interview Evaluator</div>
      <div style={styles.spacer}></div>
    </div>
  );
}

const styles = {
  page: {
    textAlign: "center",
    fontFamily: "Arial, sans-serif",
    height: "200vh", // Creates scrollable space
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  centeredText: {
    fontSize: "3rem",
    fontWeight: "bold",
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)", // Ensures perfect centering
  },
  spacer: {
    height: "100vh", // Extra scrollable space below
  },
};

export default App;
