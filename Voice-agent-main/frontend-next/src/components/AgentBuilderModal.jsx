"use client";

import React, { useState, useEffect } from "react";

const SUPPORTED_MODELS = [
  { id: "lightning_v3.1", name: "Smallest AI — Lightning v3.1", description: "Ultra-low latency model for real-time voice agents" },
  { id: "lightning_v3.1_pro", name: "Smallest AI — Lightning v3.1 Pro", description: "High-prosody premium model for expressive human-like delivery" },
];

const ALL_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "hi", name: "Hindi" },
  { code: "mr", name: "Marathi" },
  { code: "ta", name: "Tamil" },
  { code: "te", name: "Telugu" },
  { code: "kn", name: "Kannada" },
  { code: "ml", name: "Malayalam" },
  { code: "gu", name: "Gujarati" },
  { code: "pa", name: "Punjabi" },
  { code: "bn", name: "Bengali" },
];

const FALLBACK_VOICES = [
  {
    voice_id: "anika",
    name: "Anika",
    gender: "Female",
    accent: "Indian",
    description: "Sales & Conversational — Natural, warm female voice",
    models: ["lightning_v3.1", "lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "devansh",
    name: "Devansh",
    gender: "Male",
    accent: "Indian",
    description: "Sales & Professional — Clear, confident male voice",
    models: ["lightning_v3.1", "lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "divya",
    name: "Divya",
    gender: "Female",
    accent: "Indian",
    description: "Customer Support — Friendly, clear tone",
    models: ["lightning_v3.1"],
    languages: ["en", "hi", "mr", "gu", "bn"],
  },
  {
    voice_id: "meher",
    name: "Meher",
    gender: "Female",
    accent: "Indian",
    description: "Pro Expressive — Premium warm conversational female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "arav",
    name: "Arav",
    gender: "Male",
    accent: "Indian",
    description: "Pro Executive — Rich, articulate male voice for sales & counseling",
    models: ["lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "emily",
    name: "Emily",
    gender: "Female",
    accent: "British",
    description: "Pro Professional — Elegant UK accent female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en"],
  },
  {
    voice_id: "rachel",
    name: "Rachel",
    gender: "Female",
    accent: "American",
    description: "Pro Natural — Clear US accent female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en"],
  },
];

export default function AgentBuilderModal({ isOpen, onClose, onAgentGenerated }) {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("lightning_v3.1");
  const [language, setLanguage] = useState("en");
  const [voice, setVoice] = useState("anika");
  const [availableVoices, setAvailableVoices] = useState(FALLBACK_VOICES);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Filter compatible voices based on Model & Language
  useEffect(() => {
    async function updateVoices() {
      try {
        const res = await fetch(`${API_BASE}/api/voices/smallest?model=${model}&language=${language}`);
        if (res.ok) {
          const data = await res.json();
          if (data.voices && data.voices.length > 0) {
            setAvailableVoices(data.voices);
            if (!data.voices.some((v) => (v.voice_id || v.id) === voice)) {
              setVoice(data.voices[0].voice_id || data.voices[0].id || "anika");
            }
            return;
          }
        }
      } catch (err) {
        console.warn("Using local voice catalog for Smallest AI:", err);
      }

      // Local fallback filtering
      const filtered = FALLBACK_VOICES.filter(
        (v) => v.models.includes(model) && v.languages.includes(language)
      );
      const fallbackList = filtered.length > 0 ? filtered : FALLBACK_VOICES.filter((v) => v.models.includes(model));
      setAvailableVoices(fallbackList);
      if (!fallbackList.some((v) => v.voice_id === voice)) {
        setVoice(fallbackList[0]?.voice_id || "anika");
      }
    }

    if (isOpen) {
      updateVoices();
    }
  }, [model, language, isOpen, API_BASE]);

  if (!isOpen) return null;

  const selectedVoiceObj = availableVoices.find((v) => (v.voice_id || v.id) === voice) || availableVoices[0];

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setGenerating(true);
    setError(null);

    try {
      const fullPrompt = `${prompt.trim()}\n\n[Agent Voice Configuration: Provider=Smallest AI, Model=${model}, Language=${language}, Voice=${voice}]`;
      const res = await fetch(`${API_BASE}/api/agents/generate-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: fullPrompt }),
      });

      if (!res.ok) {
        throw new Error(`Failed to generate agent (${res.status})`);
      }

      const data = await res.json();
      if (data.agent) {
        // Apply user selected voice, model, and language directly to generated agent
        const updatedAgent = {
          ...data.agent,
          language: language,
          tts: {
            provider: "smallest",
            model: model,
            voice: voice,
          },
        };

        // Persist voice selection update to agent
        try {
          await fetch(`${API_BASE}/api/agents/${updatedAgent.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updatedAgent),
          });
        } catch (saveErr) {
          console.warn("Agent voice settings update error:", saveErr);
        }

        onAgentGenerated && onAgentGenerated(updatedAgent);
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
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "rgba(0, 0, 0, 0.8)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 9999, padding: "20px"
      }}
    >
      <div
        style={{
          background: "#141414", borderRadius: "16px", border: "1px solid #262626", width: "100%", maxWidth: "650px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)", overflow: "hidden", maxHeight: "90vh", display: "flex", flexDirection: "column"
        }}
      >
        {/* Header */}
        <div style={{ padding: "22px 28px", borderBottom: "1px solid #262626", background: "#1A1A1A" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: "11px", fontWeight: "800", textTransform: "uppercase", letterSpacing: "1px", color: "#60a5fa" }}>
                Prompt-First Agent Builder
              </span>
              <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#FFFFFF", margin: "4px 0 0 0" }}>
                Create Voice Agent
              </h2>
            </div>
            <button onClick={onClose} style={{ border: "none", background: "none", fontSize: "24px", color: "#A3A3A3", cursor: "pointer" }}>
              &times;
            </button>
          </div>
          <p style={{ fontSize: "13px", color: "#A3A3A3", margin: "6px 0 0 0", lineHeight: "1.4" }}>
            Describe your voice agent prompt, select model, language, and voice persona to generate a production AI agent.
          </p>
        </div>

        {/* Body Form */}
        <form onSubmit={handleGenerate} style={{ padding: "24px 28px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "20px" }}>
          {error && (
            <div style={{ padding: "12px 16px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "8px", color: "#fca5a5", fontSize: "13px" }}>
              {error}
            </div>
          )}

          {/* 1. Agent Prompt Box */}
          <div>
            <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "8px" }}>
              Agent Prompt
            </label>
            <textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Create an LIC insurance advisor that helps customers understand life insurance policies."
              style={{
                width: "100%", padding: "14px", borderRadius: "10px", background: "#1E1E1E", border: "1px solid #3D3D3D",
                color: "#FFFFFF", fontSize: "14px", fontFamily: "inherit", resize: "vertical", outline: "none"
              }}
            />
            {/* Sample Prompts */}
            <div style={{ marginTop: "10px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {[
                "LIC Insurance Advisor",
                "Education & Career Counsellor",
                "Real Estate Sales Specialist",
                "Customer Support Agent"
              ].map((sample) => (
                <button
                  key={sample}
                  type="button"
                  onClick={() => setPrompt(`Create an ${sample} that assists callers, answers questions naturally, and gathers customer details.`)}
                  style={{
                    padding: "4px 10px", borderRadius: "16px", border: "1px solid #3D3D3D",
                    background: "#1E1E1E", color: "#A3A3A3", fontSize: "11px", fontWeight: "500", cursor: "pointer"
                  }}
                >
                  + {sample}
                </button>
              ))}
            </div>
          </div>

          {/* Configuration Section Header */}
          <div style={{ borderTop: "1px solid #262626", paddingTop: "16px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.5px", color: "#60a5fa" }}>
              Voice Engine & Persona Configuration
            </span>
          </div>

          {/* 2. Model & 3. Language Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            {/* Model Selection */}
            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                Model
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: "8px", background: "#1E1E1E",
                  border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "13px", outline: "none"
                }}
              >
                {SUPPORTED_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Language Selection */}
            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: "8px", background: "#1E1E1E",
                  border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "13px", outline: "none"
                }}
              >
                {ALL_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name} ({l.code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 4. Voice Selection */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <label style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF" }}>
                Voice
              </label>
              <span style={{ fontSize: "11px", color: "#60a5fa", fontWeight: "600" }}>
                Filtered by Model ({model}) + Language ({language})
              </span>
            </div>
            <select
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              style={{
                width: "100%", padding: "10px 12px", borderRadius: "8px", background: "#1E1E1E",
                border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "13px", outline: "none", marginBottom: "8px"
              }}
            >
              {availableVoices.map((v) => {
                const vid = v.voice_id || v.id;
                const vName = v.name || vid;
                const vGender = v.gender ? ` (${v.gender}, ${v.accent || "Indian"})` : "";
                return (
                  <option key={vid} value={vid}>
                    🎙️ {vName} {vGender} — {v.description || "Smallest AI Voice"}
                  </option>
                );
              })}
            </select>

            {/* Selected Voice Badge Preview */}
            {selectedVoiceObj && (
              <div
                style={{
                  padding: "10px 14px", background: "rgba(59, 130, 246, 0.1)", borderRadius: "8px",
                  border: "1px solid rgba(59, 130, 246, 0.3)", display: "flex", justifyContent: "space-between", alignItems: "center"
                }}
              >
                <div>
                  <span style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF" }}>
                    Selected Voice: {selectedVoiceObj.name || voice}
                  </span>
                  <span style={{ fontSize: "12px", color: "#A3A3A3", marginLeft: "8px" }}>
                    {selectedVoiceObj.gender} • {selectedVoiceObj.accent || "Indian"} Accent
                  </span>
                </div>
                <span style={{ fontSize: "11px", fontWeight: "700", background: "#3b82f6", color: "#fff", padding: "2px 8px", borderRadius: "4px" }}>
                  Smallest AI
                </span>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "12px", paddingTop: "16px", borderTop: "1px solid #262626" }}>
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
              {generating ? "✨ Generating Agent..." : "✨ Generate Agent"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

