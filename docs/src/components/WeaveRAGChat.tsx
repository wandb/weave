import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

const BACKEND_URL = (window as any).DOCS_AGENT_BACKEND_URL || "http://localhost:8018/docs-agent";

export default function WeaveRAGChat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    setLoading(true);
    setAnswer(null);

    try {
      const res = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          input_items: [],
          conversation_id: "weave-rag-ui", // optional static ID
        }),
      });
      const data = await res.json();
      setAnswer(data.answer || "No response.");
    } catch (err) {
      console.error("Error:", err);
      setAnswer("Error: Could not fetch from backend.");
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
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
