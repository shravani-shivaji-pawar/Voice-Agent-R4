"use client";

import React, { useState, useEffect } from "react";

const SUPPORTED_MODELS = [
  { id: "lightning_v3.1", name: "Lightning v3.1", description: "Ultra-low latency model for real-time voice agents" },
  { id: "lightning_v3.1_pro", name: "Lightning v3.1 Pro", description: "High-prosody premium model for expressive human-like delivery" },
];

const ALL_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "hi", "name": "Hindi" },
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
    gender: "female",
    accent: "Indian",
    description: "Sales & Conversational — Natural, warm female voice",
    models: ["lightning_v3.1", "lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "devansh",
    name: "Devansh",
    gender: "male",
    accent: "Indian",
    description: "Sales & Professional — Clear, confident male voice",
    models: ["lightning_v3.1", "lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "divya",
    name: "Divya",
    gender: "female",
    accent: "Indian",
    description: "Customer Support — Friendly, clear tone",
    models: ["lightning_v3.1"],
    languages: ["en", "hi", "mr", "gu", "bn"],
  },
  {
    voice_id: "meher",
    name: "Meher",
    gender: "female",
    accent: "Indian",
    description: "Pro Expressive — Premium warm conversational female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "arav",
    name: "Arav",
    gender: "male",
    accent: "Indian",
    description: "Pro Executive — Rich, articulate male voice for sales & counseling",
    models: ["lightning_v3.1_pro"],
    languages: ["en", "hi", "mr", "ta", "te", "kn", "ml", "gu", "pa", "bn"],
  },
  {
    voice_id: "emily",
    name: "Emily",
    gender: "female",
    accent: "British",
    description: "Pro Professional — Elegant UK accent female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en"],
  },
  {
    voice_id: "rachel",
    name: "Rachel",
    gender: "female",
    accent: "American",
    description: "Pro Natural — Clear US accent female voice",
    models: ["lightning_v3.1_pro"],
    languages: ["en"],
  },
];

export default function SmallestVoiceSelector({
  selectedModel = "lightning_v3.1",
  selectedLanguage = "en",
  selectedVoice = "anika",
  onChange,
}) {
  const [model, setModel] = useState(selectedModel);
  const [language, setLanguage] = useState(selectedLanguage);
  const [voice, setVoice] = useState(selectedVoice);
  const [voices, setVoices] = useState(FALLBACK_VOICES);
  const [loading, setLoading] = useState(false);
  const [playingVoiceId, setPlayingVoiceId] = useState(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    async function loadVoices() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/voices/smallest?model=${model}&language=${language}`);
        if (res.ok) {
          const data = await res.json();
          if (data.voices && data.voices.length > 0) {
            setVoices(data.voices);
          } else {
            setVoices(FALLBACK_VOICES.filter(v => v.models.includes(model)));
          }
        }
      } catch (err) {
        console.warn("Could not fetch Smallest voices API:", err);
        setVoices(FALLBACK_VOICES.filter(v => v.models.includes(model)));
      } finally {
        setLoading(false);
      }
    }
    loadVoices();
  }, [model, language, API_BASE]);

  const handleModelChange = (newModel) => {
    setModel(newModel);
    onChange && onChange({ model: newModel, language, voice });
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    onChange && onChange({ model, language: newLang, voice });
  };

  const handleVoiceSelect = (vId) => {
    setVoice(vId);
    onChange && onChange({ model, language, voice: vId });
  };

  const handlePreviewAudio = (vId) => {
    if (playingVoiceId === vId) {
      setPlayingVoiceId(null);
      return;
    }
    setPlayingVoiceId(vId);
    // Simulate audio preview playback pulse
    setTimeout(() => {
      setPlayingVoiceId(null);
    }, 2500);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Provider Badge */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "#f8fafc", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
        <span style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.5px", background: "#3b82f6", color: "#fff", padding: "4px 8px", borderRadius: "6px" }}>
          Canonical Voice Engine
        </span>
        <span style={{ fontSize: "14px", fontWeight: "600", color: "#1e293b" }}>Smallest AI Waves (Lightning)</span>
      </div>

      {/* Model & Language Controls */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: "600", color: "#475569", marginBottom: "6px" }}>
            TTS Model
          </label>
          <select
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "14px", background: "#fff" }}
          >
            {SUPPORTED_MODELS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} — {m.description}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: "600", color: "#475569", marginBottom: "6px" }}>
            Target Spoken Language
          </label>
          <select
            value={language}
            onChange={(e) => handleLanguageChange(e.target.value)}
            style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "14px", background: "#fff" }}
          >
            {ALL_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Voice Cards Catalog */}
      <div>
        <label style={{ display: "block", fontSize: "13px", fontWeight: "600", color: "#475569", marginBottom: "10px" }}>
          Compatible Smallest Voices ({voices.length} available)
        </label>

        {loading ? (
          <div style={{ padding: "20px", textAlign: "center", color: "#64748b" }}>Loading Smallest AI voices...</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "12px" }}>
            {voices.map((v) => {
              const isSelected = voice.toLowerCase() === v.voice_id.toLowerCase();
              const isPlaying = playingVoiceId === v.voice_id;

              return (
                <div
                  key={v.voice_id}
                  onClick={() => handleVoiceSelect(v.voice_id)}
                  style={{
                    padding: "14px",
                    borderRadius: "10px",
                    border: isSelected ? "2px solid #3b82f6" : "1px solid #e2e8f0",
                    background: isSelected ? "#eff6ff" : "#ffffff",
                    cursor: "pointer",
                    transition: "all 0.15s ease-in-out",
                    display: "flex",
                    flexDirection: "column",
                    justify: "space-between",
                    position: "relative",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
                    <div>
                      <div style={{ fontWeight: "700", fontSize: "15px", color: "#0f172a" }}>{v.name}</div>
                      <div style={{ fontSize: "12px", color: "#64748b" }}>
                        {v.gender} • {v.accent} Accent
                      </div>
                    </div>
                    {isSelected && (
                      <span style={{ fontSize: "11px", fontWeight: "700", background: "#3b82f6", color: "#fff", padding: "2px 6px", borderRadius: "4px" }}>
                        Selected
                      </span>
                    )}
                  </div>

                  <p style={{ fontSize: "12px", color: "#475569", margin: "8px 0 12px 0", lineHeight: "1.4" }}>
                    {v.description}
                  </p>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePreviewAudio(v.voice_id);
                    }}
                    style={{
                      width: "100%",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      background: isPlaying ? "#dbeafe" : "#f8fafc",
                      color: "#1e293b",
                      fontSize: "12px",
                      fontWeight: "600",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "6px",
                    }}
                  >
                    {isPlaying ? "🔊 Playing Preview..." : "▶ Preview Voice"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
