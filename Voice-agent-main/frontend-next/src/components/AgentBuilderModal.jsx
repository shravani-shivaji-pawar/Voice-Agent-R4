"use client";

import React, { useState } from "react";

export default function AgentBuilderModal({ isOpen, onClose, onAgentGenerated }) {
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setGenerating(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/agents/generate-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });

      if (!res.ok) {
        throw new Error(`Failed to generate agent (${res.status})`);
      }

      const data = await res.json();
      if (data.agent) {
        onAgentGenerated && onAgentGenerated(data.agent);
        onClose();
      } else {
        throw new Error("Invalid response from agent builder API");
      }
    } catch (err) {
      console.error("Agent generation error:", err);
      setError(err.message || "Failed to generate agent config");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0, 0, 0, 0.8)", backdropFilter: "blur(6px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 9999, padding: "20px"
    }}>
      <div style={{
        background: "#141414", borderRadius: "16px", border: "1px solid #262626", width: "100%", maxWidth: "600px",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)", overflow: "hidden"
      }}>
        {/* Header */}
        <div style={{ padding: "24px 28px", borderBottom: "1px solid #262626", background: "#1A1A1A" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: "11px", fontWeight: "800", textTransform: "uppercase", letterSpacing: "1px", color: "#60a5fa" }}>
                Prompt-First Agent Builder
              </span>
              <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#FFFFFF", margin: "4px 0 0 0" }}>
                Create AI Voice Agent
              </h2>
            </div>
            <button onClick={onClose} style={{ border: "none", background: "none", fontSize: "24px", color: "#A3A3A3", cursor: "pointer" }}>
              &times;
            </button>
          </div>
          <p style={{ fontSize: "13px", color: "#A3A3A3", margin: "8px 0 0 0", lineHeight: "1.4" }}>
            Describe your voice agent's identity, role, behavior, and goals in plain language. Our AI will build the canonical configuration.
          </p>
        </div>

        {/* Body Form */}
        <form onSubmit={handleGenerate} style={{ padding: "28px" }}>
          {error && (
            <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "8px", color: "#fca5a5", fontSize: "13px", marginBottom: "16px" }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "8px" }}>
              What should this voice agent do?
            </label>
            <textarea
              rows={5}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Create an education counselling agent named Aarohi for a university. It should answer questions about MCA, MBA, fees, entrance exams, and transfer difficult cases to a human counsellor."
              style={{
                width: "100%", padding: "14px", borderRadius: "10px", background: "#1E1E1E", border: "1px solid #3D3D3D",
                color: "#FFFFFF", fontSize: "14px", fontFamily: "inherit", resize: "vertical", outline: "none"
              }}
            />
          </div>

          {/* Preset Chips */}
          <div style={{ marginBottom: "24px" }}>
            <span style={{ fontSize: "12px", fontWeight: "600", color: "#A3A3A3", display: "block", marginBottom: "8px" }}>
              Or try a sample prompt:
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {[
                "Education & Career Counsellor",
                "Real Estate Sales Specialist",
                "Electronics Customer Support",
                "Insurance Advisory Voice Assistant"
              ].map((sample) => (
                <button
                  key={sample}
                  type="button"
                  onClick={() => setPrompt(`Create a professional ${sample} voice agent. It should answer questions, collect lead details, and transfer complex calls.`)}
                  style={{
                    padding: "6px 12px", borderRadius: "20px", border: "1px solid #3D3D3D",
                    background: "#1E1E1E", color: "#E5E5E5", fontSize: "12px", fontWeight: "500", cursor: "pointer"
                  }}
                >
                  + {sample}
                </button>
              ))}
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
            <button
              type="button"
              onClick={onClose}
              disabled={generating}
              style={{ padding: "10px 18px", borderRadius: "8px", border: "1px solid #3D3D3D", background: "#1E1E1E", color: "#FFFFFF", fontWeight: "600", fontSize: "14px", cursor: "pointer" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={generating || !prompt.trim()}
              style={{
                padding: "10px 24px", borderRadius: "8px", border: "none",
                background: generating ? "#2563eb" : "#3b82f6", color: "#fff",
                fontWeight: "700", fontSize: "14px", cursor: generating ? "not-allowed" : "pointer"
              }}
            >
              {generating ? "✨ Generating Agent..." : "✨ Generate Agent Configuration"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
