import React, { useState } from "react";

export default function WeaveRAGChat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    setAnswer(null);

    try {
      const res = await fetch("http://localhost:8000/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      setAnswer(data);
    } catch (err) {
      console.error("Error:", err);
      setAnswer({ answer: "Request failed.", source: "N/A" });
    }

    setLoading(false);
  };

  return (
    <div style={{ marginTop: "2rem", maxWidth: 600 }}>
      <h3>Ask Weave Docs</h3>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          placeholder="Ask a docs question..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          style={{ flex: 1, padding: "0.5rem" }}
        />
        <button onClick={ask} disabled={loading || !question}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>
        {answer && (
        <div style={{ background: "#f6f8fa", padding: "1rem", borderRadius: 8 }}>
            <strong>Answer:</strong>
            <p>{answer.answer}</p>
            <small>
            <strong>Source:</strong> {answer.source}
            </small>

            {answer.retrieved && answer.retrieved.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
                <small><strong>Top 5 Retrieved Chunks:</strong></small>
                <ul style={{ paddingLeft: "1.2rem", marginTop: "0.25rem", fontSize: "0.85rem" }}>
                {answer.retrieved.map((chunk, idx) => (
                    <li key={idx}>[{chunk.score}] {chunk.source}</li>
                ))}
                </ul>
            </div>
            )}
        </div>
        )}
    </div>
  );
}
