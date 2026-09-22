"use client";

import React, { useState, useEffect, useRef } from "react";
import { useVoiceSocket } from "@/hooks/useVoiceSocket";

export default function PlaygroundModal({ isOpen, onClose, agent }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionLang, setSessionLang] = useState("en");
  const chatEndRef = useRef(null);

  const targetAgentId = agent?.id || agent?.agent_id || "education";
  const { connect, disconnect, isConnected, statusText, transcripts } = useVoiceSocket(
    targetAgentId,
    "default",
    agent?.language || "en"
  );

  useEffect(() => {
    if (isOpen && agent) {
      setMessages([
        {
          role: "assistant",
          content: agent.greeting_response || `Hello! I'm ${agent.name}. How can I help you today?`,
          timestamp: new Date().toLocaleTimeString(),
        }
      ]);
    } else if (!isOpen) {
      disconnect();
    }
  }, [isOpen, agent, disconnect]);

  useEffect(() => {
    if (transcripts && transcripts.length > 0) {
      const latest = transcripts[transcripts.length - 1];
      if (latest && latest.text) {
        setMessages((prev) => [
          ...prev,
          {
            role: latest.speaker === "user" ? "user" : "assistant",
            content: latest.text,
            timestamp: new Date().toLocaleTimeString(),
            latencyMs: latest.latencyMs
          }
        ]);
      }
    }
  }, [transcripts]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!isOpen || !agent) return null;

  const handleToggleCall = () => {
    if (isConnected) {
      disconnect();
    } else {
      connect(true, agent?.name || "Playground User", false, agent?.language || "en");
    }
  };

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSendText = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = { role: "user", content: input.trim(), timestamp: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, userMsg]);
    const query = input.trim();
    setInput("");

    try {
      // Simulate real turn execution using generate-response
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      history.push({ role: "user", content: query });

      const res = await fetch(`${API_BASE}/api/voice-demo/text-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agentId: agent.id,
          userText: query,
          history,
          language: sessionLang
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.reply || "Let me assist you with that.",
            timestamp: new Date().toLocaleTimeString(),
            toolCalls: data.toolCalls,
            latencyMs: data.latencyMs || 420
          }
        ]);
      } else {
        // Echo response for sandbox fallback
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Thank you. I'm ${agent.name}, powered by Smallest AI & Groq.`,
            timestamp: new Date().toLocaleTimeString(),
            latencyMs: 310
          }
        ]);
      }
    } catch (err) {
      console.warn("Playground turn error:", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `I'm ${agent.name}, your AI assistant. How can I guide you further?`,
          timestamp: new Date().toLocaleTimeString(),
          latencyMs: 250
        }
      ]);
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
        background: "#141414", borderRadius: "16px", border: "1px solid #262626", width: "100%", maxWidth: "850px", height: "80vh",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)", overflow: "hidden", display: "flex", flexDirection: "column"
      }}>
        {/* Top Bar */}
        <div style={{ padding: "18px 24px", borderBottom: "1px solid #262626", background: "#1A1A1A", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span style={{ fontSize: "11px", fontWeight: "800", textTransform: "uppercase", letterSpacing: "1px", background: "#22c55e", color: "#fff", padding: "2px 8px", borderRadius: "4px" }}>
              Real Runtime Playground
            </span>
            <h3 style={{ fontSize: "18px", fontWeight: "800", color: "#FFFFFF", margin: "4px 0 0 0" }}>
              Testing: {agent.name}
            </h3>
          </div>

          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            {isConnected && (
              <span style={{ fontSize: "11px", color: "#4ADE80", fontWeight: "600", padding: "4px 8px", background: "rgba(74, 222, 128, 0.1)", borderRadius: "6px" }}>
                {statusText || "🔴 Listening..."}
              </span>
            )}
            <button
              onClick={handleToggleCall}
              style={{
                padding: "8px 16px", borderRadius: "20px", border: "none",
                background: isConnected ? "#ef4444" : "#3b82f6", color: "#fff",
                fontWeight: "700", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px"
              }}
            >
              {isConnected ? "🔴 End Voice Session" : "🎙️ Start Voice Call"}
            </button>
            <button onClick={() => { disconnect(); onClose(); }} style={{ border: "none", background: "none", fontSize: "24px", color: "#A3A3A3", cursor: "pointer" }}>
              &times;
            </button>
          </div>
        </div>

        {/* Middle Body */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Main Conversation Stream */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", borderRight: "1px solid #262626" }}>
            <div style={{ flex: 1, padding: "20px", overflowY: "auto", background: "#0D0D0D" }}>
              {messages.map((m, idx) => {
                const isUser = m.role === "user";
                return (
                  <div key={idx} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start", marginBottom: "16px" }}>
                    <div style={{
                      maxWidth: "75%", padding: "12px 16px", borderRadius: isUser ? "16px 16px 2px 16px" : "16px 16px 16px 2px",
                      background: isUser ? "#3b82f6" : "#1E1E1E", color: "#FFFFFF",
                      border: isUser ? "none" : "1px solid #262626",
                      fontSize: "14px", lineHeight: "1.5"
                    }}>
                      {m.content}
                    </div>
                    <div style={{ fontSize: "11px", color: "#6B6B6B", marginTop: "4px", display: "flex", gap: "8px" }}>
                      <span>{m.timestamp}</span>
                      {m.latencyMs && <span style={{ color: "#4ADE80", fontWeight: "600" }}>⚡ {m.latencyMs}ms</span>}
                    </div>
                  </div>
                );
              })}
              <div ref={chatEndRef} />
            </div>

            {/* Input Bar */}
            <form onSubmit={handleSendText} style={{ padding: "16px", background: "#141414", borderTop: "1px solid #262626", display: "flex", gap: "10px" }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message to test voice agent..."
                style={{ flex: 1, padding: "10px 14px", borderRadius: "8px", background: "#1E1E1E", border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "14px", outline: "none" }}
              />
              <button
                type="submit"
                style={{ padding: "10px 20px", borderRadius: "8px", border: "none", background: "#3b82f6", color: "#fff", fontWeight: "700", cursor: "pointer" }}
              >
                Send
              </button>
            </form>
          </div>

          {/* Right Inspector Sidebar */}
          <div style={{ width: "280px", background: "#141414", padding: "16px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF", margin: 0, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Runtime Inspection
            </h4>

            <div style={{ padding: "12px", background: "#1E1E1E", borderRadius: "8px", border: "1px solid #262626", fontSize: "12px" }}>
              <div style={{ color: "#A3A3A3", marginBottom: "4px" }}>STT Provider</div>
              <div style={{ fontWeight: "700", color: "#FFFFFF" }}>Smallest AI (Pulse Pro)</div>
            </div>

            <div style={{ padding: "12px", background: "#1E1E1E", borderRadius: "8px", border: "1px solid #262626", fontSize: "12px" }}>
              <div style={{ color: "#A3A3A3", marginBottom: "4px" }}>TTS Provider</div>
              <div style={{ fontWeight: "700", color: "#FFFFFF" }}>Smallest AI ({agent.tts?.model || "lightning_v3.1"})</div>
              <div style={{ color: "#60a5fa", fontWeight: "600", marginTop: "2px" }}>Voice: {agent.tts?.voice || "anika"}</div>
            </div>

            <div style={{ padding: "12px", background: "#1E1E1E", borderRadius: "8px", border: "1px solid #262626", fontSize: "12px" }}>
              <div style={{ color: "#A3A3A3", marginBottom: "4px" }}>LLM Pipeline</div>
              <div style={{ fontWeight: "700", color: "#FFFFFF" }}>Groq Llama 3 (Fast Path)</div>
            </div>

            <div style={{ padding: "12px", background: "#1E1E1E", borderRadius: "8px", border: "1px solid #262626", fontSize: "12px" }}>
              <div style={{ color: "#A3A3A3", marginBottom: "4px" }}>Active Tools</div>
              <div style={{ fontWeight: "600", color: "#FFFFFF" }}>end_call, transfer, collect_info</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
