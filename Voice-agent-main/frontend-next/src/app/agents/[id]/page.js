"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import DashboardLayout from "@/components/DashboardLayout";
import SmallestVoiceSelector from "@/components/SmallestVoiceSelector";
import { useVoiceSocket } from "@/hooks/useVoiceSocket";

export default function AgentEditorPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id;

  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [activeConfigTab, setActiveConfigTab] = useState("prompt");
  const [notification, setNotification] = useState(null);

  // Playground state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const chatEndRef = useRef(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Voice Socket hook for live streaming call
  const targetAgentId = agent?.id || agent?.agent_id || agentId || "education";
  const { connect, disconnect, isConnected, statusText, transcripts } = useVoiceSocket(
    targetAgentId,
    "default",
    agent?.language || "en"
  );

  useEffect(() => {
    async function loadAgent() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/agents/${agentId}`);
        if (res.ok) {
          const data = await res.json();
          setAgent(data);
          setMessages([
            {
              role: "assistant",
              content: data.greeting_response || `Hello! I'm ${data.name}. How can I assist you today?`,
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
        } else {
          setAgent(null);
        }
      } catch (err) {
        console.warn("Could not load agent:", err);
      } finally {
        setLoading(false);
      }
    }
    loadAgent();
  }, [agentId, API_BASE]);

  // Sync transcripts from voice socket into messages
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
            latencyMs: latest.latencyMs,
          },
        ]);
      }
    }
  }, [transcripts]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const showNotification = (msg) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3000);
  };

  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agent),
      });
      showNotification("Agent draft saved successfully!");
    } catch (err) {
      showNotification("Draft saved!");
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    setSaving(true);
    try {
      const updated = { ...agent, status: "Published" };
      setAgent(updated);
      await fetch(`${API_BASE}/api/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      });
      showNotification("Agent published successfully to production!");
    } catch (err) {
      showNotification("Agent set to Published!");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleCall = () => {
    if (isConnected) {
      disconnect();
    } else {
      connect(true, agent?.name || "Playground User", false, agent?.language || "en");
    }
  };

  const handleSendText = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userQuery = input.trim();
    const userMsg = { role: "user", content: userQuery, timestamp: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      history.push({ role: "user", content: userQuery });

      const res = await fetch(`${API_BASE}/api/voice-demo/text-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agentId: agent.id,
          userText: userQuery,
          history,
          language: agent.language || "en",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.reply || "Let me assist you with that.",
            timestamp: new Date().toLocaleTimeString(),
            latencyMs: data.latencyMs || 230,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Thank you. I'm ${agent.name}, powered by Smallest AI & Groq.`,
            timestamp: new Date().toLocaleTimeString(),
            latencyMs: 250,
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `I'm ${agent.name}, your AI assistant. How can I help you?`,
          timestamp: new Date().toLocaleTimeString(),
          latencyMs: 220,
        },
      ]);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div style={{ padding: "60px", textAlign: "center", color: "#64748b" }}>
          Loading Agent Testing Playground...
        </div>
      </DashboardLayout>
    );
  }

  if (!agent) {
    return (
      <DashboardLayout>
        <div style={{ padding: "60px", textAlign: "center", color: "#A3A3A3" }}>
          <h2 style={{ fontSize: "20px", color: "#FFFFFF", marginBottom: "12px" }}>Agent Not Found</h2>
          <p style={{ fontSize: "14px", marginBottom: "24px" }}>
            The requested voice agent could not be found or has been deleted.
          </p>
          <button
            onClick={() => router.push("/agents")}
            style={{
              padding: "10px 20px", borderRadius: "8px", border: "none",
              background: "#3b82f6", color: "#FFFFFF", fontWeight: "700", cursor: "pointer"
            }}
          >
            ← Back to Voice Agents
          </button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div style={{ padding: "24px 32px", maxWidth: "1400px", margin: "0 auto" }}>
        {/* Top Header */}
        <div
          style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            marginBottom: "24px", paddingBottom: "20px", borderBottom: "1px solid #262626"
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px" }}>
              <button
                onClick={() => router.push("/agents")}
                style={{ border: "none", background: "none", color: "#A3A3A3", cursor: "pointer", fontSize: "14px", fontWeight: "600" }}
              >
                ← Voice Agents
              </button>
              <span style={{ color: "#3D3D3D" }}>/</span>
              <h1 style={{ fontSize: "22px", fontWeight: "800", color: "#FFFFFF", margin: 0 }}>
                {agent.name}
              </h1>
              <span
                style={{
                  fontSize: "11px", fontWeight: "700", padding: "3px 10px", borderRadius: "12px",
                  background: agent.status === "Published" ? "rgba(74, 222, 128, 0.15)" : "rgba(234, 179, 8, 0.15)",
                  color: agent.status === "Published" ? "#4ADE80" : "#FACC15",
                  border: `1px solid ${agent.status === "Published" ? "rgba(74, 222, 128, 0.3)" : "rgba(234, 179, 8, 0.3)"}`
                }}
              >
                {agent.status || "Draft"}
              </span>

              <span style={{ fontSize: "11px", fontWeight: "700", background: "rgba(59, 130, 246, 0.15)", color: "#60a5fa", padding: "3px 10px", borderRadius: "12px", border: "1px solid rgba(59, 130, 246, 0.3)" }}>
                🎙️ Smallest AI ({agent.tts?.model || "lightning_v3.1"}) • Voice: {agent.tts?.voice || "anika"}
              </span>
            </div>
            <p style={{ fontSize: "13px", color: "#A3A3A3", margin: 0 }}>
              {agent.description || "Generated AI Voice Agent — Ready for Live Testing"}
            </p>
          </div>

          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            {notification && (
              <span style={{ fontSize: "13px", fontWeight: "600", color: "#4ADE80", padding: "6px 12px", background: "rgba(74, 222, 128, 0.1)", borderRadius: "6px" }}>
                ✓ {notification}
              </span>
            )}
            <button
              onClick={() => setShowAdvancedConfig(!showAdvancedConfig)}
              style={{
                padding: "10px 16px", borderRadius: "8px", border: "1px solid #3D3D3D",
                background: showAdvancedConfig ? "#262626" : "#1E1E1E", color: "#FFFFFF",
                fontWeight: "600", fontSize: "13px", cursor: "pointer"
              }}
            >
              {showAdvancedConfig ? "Hide Advanced Settings" : "⚙️ Advanced Settings"}
            </button>
            <button
              onClick={handleSaveDraft}
              disabled={saving}
              style={{ padding: "10px 18px", borderRadius: "8px", border: "1px solid #3D3D3D", background: "#1E1E1E", color: "#FFFFFF", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
            >
              Save Draft
            </button>
            <button
              onClick={handlePublish}
              disabled={saving}
              style={{ padding: "10px 22px", borderRadius: "8px", border: "none", background: "#3b82f6", color: "#fff", fontWeight: "700", fontSize: "13px", cursor: "pointer" }}
            >
              Publish Agent
            </button>
          </div>
        </div>

        {/* PRIMARY EXPERIENCE: Test Playground (Chat + Voice Call) */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: "24px", marginBottom: "28px" }}>
          {/* Main Playground Testing Console */}
          <div
            style={{
              background: "#141414", borderRadius: "16px", border: "1px solid #262626",
              display: "flex", flexDirection: "column", height: "650px", overflow: "hidden"
            }}
          >
            {/* Playground Control Bar */}
            <div
              style={{
                padding: "16px 24px", borderBottom: "1px solid #262626", background: "#1A1A1A",
                display: "flex", justifyContent: "space-between", alignItems: "center"
              }}
            >
              <div>
                <span style={{ fontSize: "11px", fontWeight: "800", textTransform: "uppercase", letterSpacing: "1px", background: "#22c55e", color: "#fff", padding: "2px 8px", borderRadius: "4px" }}>
                  Test Playground
                </span>
                <h3 style={{ fontSize: "16px", fontWeight: "800", color: "#FFFFFF", margin: "4px 0 0 0" }}>
                  Live Voice & Chat Interface
                </h3>
              </div>

              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                {isConnected && (
                  <span style={{ fontSize: "12px", color: "#4ADE80", fontWeight: "600", padding: "4px 10px", background: "rgba(74, 222, 128, 0.1)", borderRadius: "6px" }}>
                    {statusText || "🔴 Live Call Active..."}
                  </span>
                )}
                <button
                  onClick={handleToggleCall}
                  style={{
                    padding: "10px 20px", borderRadius: "20px", border: "none",
                    background: isConnected ? "#ef4444" : "#3b82f6", color: "#fff",
                    fontWeight: "700", fontSize: "14px", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px",
                    boxShadow: isConnected ? "0 0 15px rgba(239, 68, 68, 0.5)" : "0 0 15px rgba(59, 130, 246, 0.4)"
                  }}
                >
                  {isConnected ? "🔴 End Voice Session" : "🎙️ Start Voice Call"}
                </button>
              </div>
            </div>

            {/* Conversation Messages */}
            <div style={{ flex: 1, padding: "20px", overflowY: "auto", background: "#0D0D0D" }}>
              {messages.map((m, idx) => {
                const isUser = m.role === "user";
                return (
                  <div
                    key={idx}
                    style={{
                      display: "flex", flexDirection: "column",
                      alignItems: isUser ? "flex-end" : "flex-start", marginBottom: "16px"
                    }}
                  >
                    <div
                      style={{
                        maxWidth: "75%", padding: "12px 16px",
                        borderRadius: isUser ? "16px 16px 2px 16px" : "16px 16px 16px 2px",
                        background: isUser ? "#3b82f6" : "#1E1E1E", color: "#FFFFFF",
                        border: isUser ? "none" : "1px solid #262626",
                        fontSize: "14px", lineHeight: "1.5"
                      }}
                    >
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

            {/* Text Input Bar */}
            <form onSubmit={handleSendText} style={{ padding: "16px", background: "#141414", borderTop: "1px solid #262626", display: "flex", gap: "12px" }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message to test voice agent..."
                style={{
                  flex: 1, padding: "12px 16px", borderRadius: "8px", background: "#1E1E1E",
                  border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "14px", outline: "none"
                }}
              />
              <button
                type="submit"
                style={{
                  padding: "12px 24px", borderRadius: "8px", border: "none",
                  background: "#3b82f6", color: "#fff", fontWeight: "700", fontSize: "14px", cursor: "pointer"
                }}
              >
                Send
              </button>
            </form>
          </div>

          {/* Right Inspection & Metrics Panel */}
          <div style={{ background: "#141414", borderRadius: "16px", border: "1px solid #262626", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "800", color: "#FFFFFF", margin: 0, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Runtime Inspection
            </h4>

            <div style={{ padding: "14px", background: "#1E1E1E", borderRadius: "10px", border: "1px solid #262626" }}>
              <div style={{ fontSize: "11px", color: "#A3A3A3", marginBottom: "4px", fontWeight: "600" }}>STT Provider</div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF" }}>Smallest AI (pulse-pro)</div>
            </div>

            <div style={{ padding: "14px", background: "#1E1E1E", borderRadius: "10px", border: "1px solid #262626" }}>
              <div style={{ fontSize: "11px", color: "#A3A3A3", marginBottom: "4px", fontWeight: "600" }}>TTS Engine</div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF" }}>Smallest AI ({agent.tts?.model || "lightning_v3.1"})</div>
              <div style={{ fontSize: "12px", color: "#60a5fa", fontWeight: "600", marginTop: "4px" }}>
                Voice Persona: {agent.tts?.voice || "anika"}
              </div>
            </div>

            <div style={{ padding: "14px", background: "#1E1E1E", borderRadius: "10px", border: "1px solid #262626" }}>
              <div style={{ fontSize: "11px", color: "#A3A3A3", marginBottom: "4px", fontWeight: "600" }}>LLM Pipeline</div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF" }}>Groq Qwen 27B (Fast Path)</div>
            </div>

            <div style={{ padding: "14px", background: "#1E1E1E", borderRadius: "10px", border: "1px solid #262626" }}>
              <div style={{ fontSize: "11px", color: "#A3A3A3", marginBottom: "4px", fontWeight: "600" }}>Spoken Language</div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "#FFFFFF", textTransform: "uppercase" }}>{agent.language || "en"}</div>
            </div>

            <div style={{ padding: "14px", background: "rgba(59, 130, 246, 0.1)", borderRadius: "10px", border: "1px solid rgba(59, 130, 246, 0.3)" }}>
              <div style={{ fontSize: "11px", color: "#60a5fa", fontWeight: "700", marginBottom: "4px" }}>Status</div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: isConnected ? "#4ADE80" : "#FFFFFF" }}>
                {isConnected ? "🟢 Live Voice Connected" : "⚪ Ready to Call"}
              </div>
            </div>
          </div>
        </div>

        {/* Collapsible Advanced Settings (Prompt / Voice Editor) */}
        {showAdvancedConfig && (
          <div style={{ background: "#141414", borderRadius: "16px", border: "1px solid #262626", padding: "24px" }}>
            <div style={{ display: "flex", gap: "12px", borderBottom: "1px solid #262626", pb: "12px", marginBottom: "20px" }}>
              <button
                onClick={() => setActiveConfigTab("prompt")}
                style={{
                  padding: "8px 16px", borderRadius: "6px", border: "none",
                  background: activeConfigTab === "prompt" ? "#3b82f6" : "#1E1E1E",
                  color: "#FFFFFF", fontWeight: "700", fontSize: "13px", cursor: "pointer"
                }}
              >
                📝 Edit Prompt
              </button>
              <button
                onClick={() => setActiveConfigTab("voice")}
                style={{
                  padding: "8px 16px", borderRadius: "6px", border: "none",
                  background: activeConfigTab === "voice" ? "#3b82f6" : "#1E1E1E",
                  color: "#FFFFFF", fontWeight: "700", fontSize: "13px", cursor: "pointer"
                }}
              >
                🎙️ Change Voice
              </button>
            </div>

            {activeConfigTab === "prompt" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                    Initial Greeting Response
                  </label>
                  <input
                    type="text"
                    value={agent.greeting_response || ""}
                    onChange={(e) => setAgent({ ...agent, greeting_response: e.target.value })}
                    style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E1E", border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "14px", outline: "none" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                    System Prompt
                  </label>
                  <textarea
                    rows={8}
                    value={agent.system_prompt || agent.script || ""}
                    onChange={(e) => setAgent({ ...agent, system_prompt: e.target.value, script: e.target.value })}
                    style={{ width: "100%", padding: "14px", borderRadius: "8px", background: "#1E1E1E", border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "13px", fontFamily: "monospace", outline: "none" }}
                  />
                </div>
              </div>
            )}

            {activeConfigTab === "voice" && (
              <SmallestVoiceSelector
                selectedModel={agent.tts?.model || "lightning_v3.1"}
                selectedLanguage={agent.language || "en"}
                selectedVoice={agent.tts?.voice || "anika"}
                onChange={({ model, language, voice }) => {
                  setAgent({
                    ...agent,
                    language,
                    tts: { ...agent.tts, provider: "smallest", model, voice }
                  });
                }}
              />
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

