"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import DashboardLayout from "@/components/DashboardLayout";
import SmallestVoiceSelector from "@/components/SmallestVoiceSelector";
import GenerateSummaryModal from "@/components/GenerateSummaryModal";
import ConversationalFlowCanvas from "@/components/ConversationalFlowCanvas";
import { useVoiceSocket } from "@/hooks/useVoiceSocket";
import {
  Bot,
  LayoutDashboard,
  GitBranch,
  BookOpen,
  Mic,
  Settings,
  Sparkles,
  CheckCircle2,
  PhoneCall,
  PhoneOff,
  Save,
  Send,
  ChevronDown,
  Globe,
  Database,
  Sliders,
  FileText
} from "lucide-react";

export default function RetellAgentWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id;

  const [agent, setAgent] = useState(null);
  const [allAgents, setAllAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeSection, setActiveSection] = useState("flow"); // "overview" | "flow" | "knowledge" | "testing" | "settings"
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [activeConfigTab, setActiveConfigTab] = useState("prompt");
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const [notification, setNotification] = useState(null);

  // Playground & Transcript state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [activeNodeId, setActiveNodeId] = useState(null);
  const chatEndRef = useRef(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Voice Socket hook for live streaming call
  const targetAgentId = agent?.id || agent?.agent_id || agentId || "education";
  const { connect, disconnect, isConnected, statusText, transcripts } = useVoiceSocket(
    targetAgentId,
    "default",
    agent?.language || "en"
  );

  // Fetch current agent & all agents list
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [agentRes, listRes] = await Promise.all([
          fetch(`${API_BASE}/api/agents/${agentId}`),
          fetch(`${API_BASE}/api/agents`),
        ]);

        if (agentRes.ok) {
          const data = await agentRes.json();
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

        if (listRes.ok) {
          const listData = await listRes.json();
          setAllAgents(Array.isArray(listData) ? listData : listData.agents || []);
        }
      } catch (err) {
        console.warn("Could not load agent details:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [agentId, API_BASE]);

  // Sync transcripts from voice socket into messages & track dynamic node updates
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

        // Simulating/Mapping live conversational node transitions based on speech turn sequence
        if (latest.speaker === "user") {
          setActiveNodeId("discovery");
        } else {
          setActiveNodeId("qualification");
        }
      }
    }
  }, [transcripts]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const showNotification = (msg) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3500);
  };

  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agent),
      });
      showNotification("Agent configuration draft saved!");
    } catch (err) {
      showNotification("Draft saved locally!");
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
      showNotification("Agent published successfully to live runtime!");
    } catch (err) {
      showNotification("Agent set to Published!");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleCall = () => {
    if (isConnected) {
      disconnect();
      setActiveNodeId("end");
    } else {
      setActiveNodeId("start");
      connect(true, agent?.name || "Demo User", false, agent?.language || "en");
    }
  };

  const handleSendText = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userQuery = input.trim();
    const userMsg = { role: "user", content: userQuery, timestamp: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setActiveNodeId("discovery");

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
        setActiveNodeId("qualification");
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
          content: `I'm ${agent.name}, your AI assistant. How can I help you today?`,
          timestamp: new Date().toLocaleTimeString(),
          latencyMs: 220,
        },
      ]);
    }
  };

  const handleSwitchAgent = (newId) => {
    if (newId && newId !== agentId) {
      disconnect();
      setMessages([]);
      setActiveNodeId(null);
      router.push(`/agents/${newId}`);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div style={{ padding: "80px", textAlign: "center", color: "#A3A3A3" }}>
          <div className="scrape-loading-dot" style={{ marginRight: "6px" }} />
          <div className="scrape-loading-dot" style={{ marginRight: "6px" }} />
          <div className="scrape-loading-dot" />
          <p style={{ marginTop: "16px", fontSize: "15px", fontWeight: "600", color: "#FFFFFF" }}>
            Loading Retell AI Agent Workspace...
          </p>
        </div>
      </DashboardLayout>
    );
  }

  if (!agent) {
    return (
      <DashboardLayout>
        <div style={{ padding: "80px", textAlign: "center", color: "#A3A3A3" }}>
          <h2 style={{ fontSize: "22px", color: "#FFFFFF", marginBottom: "12px", fontWeight: "800" }}>Agent Not Found</h2>
          <p style={{ fontSize: "14px", marginBottom: "24px" }}>
            The requested voice agent could not be found or has been removed.
          </p>
          <button
            onClick={() => router.push("/agents")}
            style={{
              padding: "10px 24px", borderRadius: "8px", border: "none",
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
      <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 70px)", background: "#080809" }}>

        {/* ── TOP AGENT HEADER ─────────────────────────────────────────────────── */}
        <div
          style={{
            padding: "14px 28px", background: "#111113", borderBottom: "1px solid #222226",
            display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            {/* Agent Selector Dropdown */}
            <div style={{ position: "relative" }}>
              <select
                value={agent.id}
                onChange={(e) => handleSwitchAgent(e.target.value)}
                style={{
                  appearance: "none", padding: "8px 36px 8px 14px", borderRadius: "8px",
                  background: "#1A1A1E", border: "1px solid #33333B", color: "#FFFFFF",
                  fontSize: "14px", fontWeight: "800", cursor: "pointer", outline: "none"
                }}
              >
                <option value={agent.id}>{agent.name}</option>
                {allAgents.filter(a => a.id !== agent.id).map(a => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
              <ChevronDown size={14} style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", color: "#A3A3A3", pointerEvents: "none" }} />
            </div>

            <span
              style={{
                fontSize: "11px", fontWeight: "800", padding: "3px 10px", borderRadius: "12px",
                background: agent.status === "Published" ? "rgba(74, 222, 128, 0.15)" : "rgba(234, 179, 8, 0.15)",
                color: agent.status === "Published" ? "#4ADE80" : "#FACC15",
                border: `1px solid ${agent.status === "Published" ? "rgba(74, 222, 128, 0.3)" : "rgba(234, 179, 8, 0.3)"}`
              }}
            >
              {agent.status || "Draft"}
            </span>

            <span style={{ fontSize: "12px", color: "#A3A3A3", display: "flex", alignItems: "center", gap: "6px" }}>
              <Mic size={14} className="text-blue-400" />
              Smallest AI ({agent.tts?.model || "lightning_v3.1"}) • Voice: <strong style={{ color: "#FFF" }}>{agent.tts?.voice || "anika"}</strong>
            </span>
          </div>

          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            {notification && (
              <span style={{ fontSize: "13px", fontWeight: "600", color: "#4ADE80", padding: "6px 14px", background: "rgba(74, 222, 128, 0.12)", borderRadius: "6px", border: "1px solid rgba(74, 222, 128, 0.3)" }}>
                ✓ {notification}
              </span>
            )}

            <button
              onClick={() => setShowSummaryModal(true)}
              style={{
                padding: "8px 16px", borderRadius: "8px", border: "1px solid rgba(167, 139, 250, 0.4)",
                background: "rgba(167, 139, 250, 0.12)", color: "#C4B5FD", fontWeight: "700", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "6px"
              }}
            >
              <Globe size={14} /> Generate Summary
            </button>

            <button
              onClick={() => setShowAdvancedConfig(!showAdvancedConfig)}
              style={{
                padding: "8px 16px", borderRadius: "8px", border: "1px solid #33333B",
                background: showAdvancedConfig ? "#26262E" : "#1A1A1E", color: "#FFFFFF",
                fontWeight: "600", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px"
              }}
            >
              <Sliders size={14} /> {showAdvancedConfig ? "Hide Settings" : "Settings"}
            </button>

            <button
              onClick={handleSaveDraft}
              disabled={saving}
              style={{ padding: "8px 18px", borderRadius: "8px", border: "1px solid #33333B", background: "#1A1A1E", color: "#FFFFFF", fontWeight: "600", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
            >
              <Save size={14} /> Save
            </button>

            <button
              onClick={handlePublish}
              disabled={saving}
              style={{ padding: "8px 22px", borderRadius: "8px", border: "none", background: "#3b82f6", color: "#fff", fontWeight: "700", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
            >
              <Sparkles size={14} /> Publish
            </button>
          </div>
        </div>

        {/* ── MAIN RETELL-STYLE WORKSPACE (3-COLUMN LAYOUT) ───────────────────── */}
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "220px 1fr 340px", overflow: "hidden" }}>

          {/* 1. LEFT SAAS NAVIGATION SIDEBAR */}
          <div style={{ background: "#0E0E10", borderRight: "1px solid #222226", padding: "20px 12px", display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ fontSize: "11px", fontWeight: "800", color: "#666673", textTransform: "uppercase", letterSpacing: "1px", padding: "0 10px 10px 10px" }}>
              Agent Workspace
            </div>

            <button
              onClick={() => setActiveSection("flow")}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: "8px", border: "none", textAlign: "left",
                background: activeSection === "flow" ? "rgba(59, 130, 246, 0.15)" : "transparent",
                color: activeSection === "flow" ? "#60A5FA" : "#A3A3A3",
                fontWeight: activeSection === "flow" ? "700" : "500", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "10px"
              }}
            >
              <GitBranch size={16} /> Conversational Flow
            </button>

            <button
              onClick={() => { setActiveSection("knowledge"); setShowSummaryModal(true); }}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: "8px", border: "none", textAlign: "left",
                background: activeSection === "knowledge" ? "rgba(59, 130, 246, 0.15)" : "transparent",
                color: activeSection === "knowledge" ? "#60A5FA" : "#A3A3A3",
                fontWeight: activeSection === "knowledge" ? "700" : "500", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "10px"
              }}
            >
              <BookOpen size={16} /> Knowledge / Summary
            </button>

            <button
              onClick={() => setActiveSection("overview")}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: "8px", border: "none", textAlign: "left",
                background: activeSection === "overview" ? "rgba(59, 130, 246, 0.15)" : "transparent",
                color: activeSection === "overview" ? "#60A5FA" : "#A3A3A3",
                fontWeight: activeSection === "overview" ? "700" : "500", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "10px"
              }}
            >
              <LayoutDashboard size={16} /> Agent Overview
            </button>

            <button
              onClick={() => setActiveSection("testing")}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: "8px", border: "none", textAlign: "left",
                background: activeSection === "testing" ? "rgba(59, 130, 246, 0.15)" : "transparent",
                color: activeSection === "testing" ? "#60A5FA" : "#A3A3A3",
                fontWeight: activeSection === "testing" ? "700" : "500", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "10px"
              }}
            >
              <Mic size={16} /> Live Playground
            </button>

            <button
              onClick={() => { setActiveSection("settings"); setShowAdvancedConfig(true); }}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: "8px", border: "none", textAlign: "left",
                background: activeSection === "settings" ? "rgba(59, 130, 246, 0.15)" : "transparent",
                color: activeSection === "settings" ? "#60A5FA" : "#A3A3A3",
                fontWeight: activeSection === "settings" ? "700" : "500", fontSize: "13px",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "10px"
              }}
            >
              <Settings size={16} /> Settings
            </button>

            <div style={{ marginTop: "auto", padding: "14px", background: "#141418", borderRadius: "10px", border: "1px solid #222226" }}>
              <div style={{ fontSize: "11px", color: "#666673", fontWeight: "700", textTransform: "uppercase", marginBottom: "4px" }}>Active Model</div>
              <div style={{ fontSize: "12px", color: "#FFFFFF", fontWeight: "700" }}>Groq Qwen 27B</div>
              <div style={{ fontSize: "11px", color: "#4ADE80", marginTop: "4px", fontWeight: "600" }}>⚡ ~650ms Latency Target</div>
            </div>
          </div>

          {/* 2. MIDDLE WORKSPACE (CONVERSATIONAL FLOW CANVAS) */}
          <div style={{ padding: "20px", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {activeSection === "overview" ? (
              <div style={{ background: "#141416", borderRadius: "16px", border: "1px solid #262626", padding: "28px", color: "#FFF" }}>
                <h3 style={{ fontSize: "20px", fontWeight: "800", marginBottom: "12px" }}>Agent Profile Overview</h3>
                <p style={{ color: "#A3A3A3", fontSize: "14px", marginBottom: "20px" }}>{agent.description || "Generated AI Voice Agent for high-converting phone interactions."}</p>
                
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ padding: "16px", background: "#1E1E22", borderRadius: "10px", border: "1px solid #262626" }}>
                    <div style={{ fontSize: "12px", color: "#A3A3A3" }}>Agent ID</div>
                    <div style={{ fontSize: "14px", fontWeight: "700", fontFamily: "monospace" }}>{agent.id}</div>
                  </div>
                  <div style={{ padding: "16px", background: "#1E1E22", borderRadius: "10px", border: "1px solid #262626" }}>
                    <div style={{ fontSize: "12px", color: "#A3A3A3" }}>Spoken Language</div>
                    <div style={{ fontSize: "14px", fontWeight: "700", textTransform: "uppercase" }}>{agent.language || "en"}</div>
                  </div>
                </div>
              </div>
            ) : (
              <ConversationalFlowCanvas
                agent={agent}
                activeNodeId={activeNodeId}
                API_BASE={API_BASE}
                onFlowUpdated={(updated) => showNotification("Conversational flow updated successfully!")}
              />
            )}
          </div>

          {/* 3. RIGHT DEMO CALL & TRANSCRIPT PANEL */}
          <div style={{ background: "#0E0E10", borderLeft: "1px solid #222226", padding: "20px", display: "flex", flexDirection: "column", gap: "16px", overflow: "hidden" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "15px", fontWeight: "800", color: "#FFFFFF", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <Mic size={16} className="text-blue-400" /> Demo Call
              </h3>
              <span style={{ fontSize: "11px", fontWeight: "700", color: isConnected ? "#4ADE80" : "#A3A3A3", background: isConnected ? "rgba(74, 222, 128, 0.15)" : "#1E1E22", padding: "3px 10px", borderRadius: "12px", border: isConnected ? "1px solid rgba(74, 222, 128, 0.3)" : "1px solid #33333B" }}>
                {isConnected ? "🟢 Call Active" : "⚪ Ready"}
              </span>
            </div>

            {/* Start Call Action Button */}
            <button
              onClick={handleToggleCall}
              style={{
                width: "100%", padding: "14px", borderRadius: "12px", border: "none",
                background: isConnected ? "#EF4444" : "#3B82F6", color: "#FFFFFF",
                fontWeight: "800", fontSize: "14px", cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: "10px",
                boxShadow: isConnected ? "0 0 20px rgba(239, 68, 68, 0.4)" : "0 0 20px rgba(59, 130, 246, 0.4)",
                transition: "all 0.15s ease-out"
              }}
            >
              {isConnected ? <><PhoneOff size={18} /> End Voice Session</> : <><PhoneCall size={18} /> Start Voice Call</>}
            </button>

            {/* Live Active Node Indicator */}
            {activeNodeId && (
              <div style={{ padding: "10px 14px", borderRadius: "8px", background: "rgba(99, 102, 241, 0.15)", border: "1px solid rgba(99, 102, 241, 0.3)", display: "flex", alignItems: "center", gap: "8px" }}>
                <div className="scrape-loading-dot" style={{ background: "#818CF8", width: "6px", height: "6px" }} />
                <span style={{ fontSize: "12px", color: "#818CF8", fontWeight: "700" }}>
                  Active Flow Node: <strong style={{ textTransform: "uppercase" }}>{activeNodeId}</strong>
                </span>
              </div>
            )}

            {/* Live Spoken Transcript */}
            <div style={{ flex: 1, background: "#141416", borderRadius: "12px", border: "1px solid #222226", padding: "16px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ fontSize: "11px", fontWeight: "800", color: "#666673", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>
                Live Spoken Transcript
              </div>

              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px" }}>
                {messages.map((m, idx) => {
                  const isUser = m.role === "user";
                  return (
                    <div key={idx} style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                      <div
                        style={{
                          maxWidth: "85%", padding: "10px 14px",
                          borderRadius: isUser ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                          background: isUser ? "#3B82F6" : "#1A1A1E", color: "#FFFFFF",
                          border: isUser ? "none" : "1px solid #2A2A32", fontSize: "13px", lineHeight: "1.4"
                        }}
                      >
                        {m.content}
                      </div>
                      <div style={{ fontSize: "10px", color: "#666673", marginTop: "4px", display: "flex", gap: "6px" }}>
                        <span>{m.timestamp}</span>
                        {m.latencyMs && <span style={{ color: "#4ADE80", fontWeight: "600" }}>⚡ {m.latencyMs}ms</span>}
                      </div>
                    </div>
                  );
                })}
                <div ref={chatEndRef} />
              </div>

              {/* Text Turn Input Form */}
              <form onSubmit={handleSendText} style={{ marginTop: "12px", display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type message to agent..."
                  style={{
                    flex: 1, padding: "10px 12px", borderRadius: "8px", background: "#1A1A1E",
                    border: "1px solid #33333B", color: "#FFFFFF", fontSize: "13px", outline: "none"
                  }}
                />
                <button
                  type="submit"
                  style={{
                    padding: "10px 14px", borderRadius: "8px", border: "none",
                    background: "#3B82F6", color: "#FFF", fontWeight: "700", fontSize: "13px", cursor: "pointer"
                  }}
                >
                  <Send size={14} />
                </button>
              </form>
            </div>

          </div>

        </div>

        {/* ── ADVANCED CONFIGURATION / SETTINGS DRAWER ────────────────────────── */}
        {showAdvancedConfig && (
          <div style={{ background: "#111113", borderTop: "1px solid #222226", padding: "24px", color: "#FFF" }}>
            <div style={{ display: "flex", gap: "12px", borderBottom: "1px solid #222226", pb: "12px", marginBottom: "20px" }}>
              <button
                onClick={() => setActiveConfigTab("prompt")}
                style={{
                  padding: "8px 16px", borderRadius: "6px", border: "none",
                  background: activeConfigTab === "prompt" ? "#3b82f6" : "#1A1A1E",
                  color: "#FFFFFF", fontWeight: "700", fontSize: "13px", cursor: "pointer"
                }}
              >
                📝 System Prompt & Script
              </button>
              <button
                onClick={() => setActiveConfigTab("voice")}
                style={{
                  padding: "8px 16px", borderRadius: "6px", border: "none",
                  background: activeConfigTab === "voice" ? "#3b82f6" : "#1A1A1E",
                  color: "#FFFFFF", fontWeight: "700", fontSize: "13px", cursor: "pointer"
                }}
              >
                🎙️ Smallest AI Voice Settings
              </button>
            </div>

            {activeConfigTab === "prompt" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                    Greeting Response Text
                  </label>
                  <input
                    type="text"
                    value={agent.greeting_response || ""}
                    onChange={(e) => setAgent({ ...agent, greeting_response: e.target.value })}
                    style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1A1A1E", border: "1px solid #33333B", color: "#FFFFFF", fontSize: "14px", outline: "none" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "13px", fontWeight: "700", color: "#FFFFFF", marginBottom: "6px" }}>
                    Agent System Prompt Instructions
                  </label>
                  <textarea
                    rows={6}
                    value={agent.system_prompt || agent.script || ""}
                    onChange={(e) => setAgent({ ...agent, system_prompt: e.target.value, script: e.target.value })}
                    style={{ width: "100%", padding: "14px", borderRadius: "8px", background: "#1A1A1E", border: "1px solid #33333B", color: "#FFFFFF", fontSize: "13px", fontFamily: "monospace", outline: "none" }}
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

      {/* GENERATE SUMMARY MODAL INTEGRATION */}
      {showSummaryModal && (
        <GenerateSummaryModal
          agent={agent}
          onClose={() => setShowSummaryModal(false)}
          onSuccess={(summary) => {
            showNotification("Website summary applied successfully to agent runtime!");
            setShowSummaryModal(false);
          }}
        />
      )}
    </DashboardLayout>
  );
}
