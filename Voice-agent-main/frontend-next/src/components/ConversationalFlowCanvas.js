"use client";

import React, { useState, useEffect } from "react";
import { 
  Play, 
  MessageSquare, 
  Target, 
  HelpCircle, 
  BookOpen, 
  CheckCircle2, 
  ArrowRight, 
  Edit3, 
  Plus, 
  Save, 
  X, 
  Sparkles, 
  Zap,
  Check,
  AlertCircle,
  Database
} from "lucide-react";

export default function ConversationalFlowCanvas({ 
  agent, 
  activeNodeId = null, 
  onFlowUpdated = null,
  API_BASE = "http://localhost:8000"
}) {
  const [flowData, setFlowData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Node editor state
  const [editingNode, setEditingNode] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState("");

  // Canvas zoom & view state
  const [zoomLevel, setZoomLevel] = useState(100);

  const fetchFlow = async () => {
    if (!agent?.id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.id}/flow`);
      if (res.ok) {
        const data = await res.json();
        setFlowData(data);
      } else {
        setError("Could not load agent flow preview.");
      }
    } catch (err) {
      console.warn("Error loading flow:", err);
      setError("Failed to fetch flow graph.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFlow();
  }, [agent?.id, API_BASE]);

  const handleSaveNodeEdit = async () => {
    if (!editingNode || !agent?.id) return;
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);

    try {
      const currentNodes = flowData?.editable_flow?.nodes || [];
      const updatedNodes = currentNodes.map((n) => 
        n.id === editingNode.id ? editingNode : n
      );

      const res = await fetch(`${API_BASE}/api/agents/${agent.id}/flow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nodes: updatedNodes }),
      });

      if (res.ok) {
        const updatedFlow = await res.json();
        setFlowData(updatedFlow);
        setSaveSuccess(true);
        setTimeout(() => {
          setSaveSuccess(false);
          setEditingNode(null);
        }, 1200);
        if (onFlowUpdated) onFlowUpdated(updatedFlow);
      } else {
        const errData = await res.json().catch(() => ({}));
        setSaveError(errData.detail || "Failed to update node configuration.");
      }
    } catch (err) {
      setSaveError(err.message || "Network error while saving node.");
    } finally {
      setSaving(false);
    }
  };

  const getNodeIcon = (type) => {
    switch (type) {
      case "start":
      case "message":
        return <MessageSquare size={16} className="text-blue-400" />;
      case "slot_collection":
        return <Target size={16} className="text-emerald-400" />;
      case "fallback":
        return <HelpCircle size={16} className="text-amber-400" />;
      case "knowledge":
      case "website_knowledge":
        return <BookOpen size={16} className="text-purple-400" />;
      case "end":
        return <CheckCircle2 size={16} className="text-gray-400" />;
      default:
        return <Sparkles size={16} className="text-indigo-400" />;
    }
  };

  const getNodeTypeLabel = (type) => {
    switch (type) {
      case "start": return "Greeting Step";
      case "message": return "Spoken Question";
      case "slot_collection": return "Slot Qualification";
      case "fallback": return "Clarification / Fallback";
      case "knowledge": return "Website Knowledge";
      case "end": return "Conversation End";
      default: return type ? type.toUpperCase() : "FLOW NODE";
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "60px", textAlign: "center", color: "#A3A3A3" }}>
        <div className="scrape-loading-dot" style={{ marginRight: "6px" }} />
        <div className="scrape-loading-dot" style={{ marginRight: "6px" }} />
        <div className="scrape-loading-dot" />
        <p style={{ marginTop: "16px", fontSize: "14px", fontWeight: "600" }}>
          Generating Conversational Flow Canvas...
        </p>
      </div>
    );
  }

  if (error || !flowData) {
    return (
      <div style={{ padding: "40px", textAlign: "center", color: "#A3A3A3", background: "#141414", borderRadius: "12px", border: "1px solid #262626" }}>
        <AlertCircle size={28} style={{ color: "#FACC15", marginBottom: "12px" }} />
        <h4 style={{ color: "#FFFFFF", fontSize: "16px", marginBottom: "6px" }}>No Flow Available</h4>
        <p style={{ fontSize: "13px", marginBottom: "16px" }}>
          {error || "Create or configure the agent to generate its conversational flow."}
        </p>
        <button
          onClick={fetchFlow}
          style={{
            padding: "8px 16px", borderRadius: "6px", background: "#3b82f6", color: "#fff",
            border: "none", fontSize: "13px", fontWeight: "700", cursor: "pointer"
          }}
        >
          🔄 Refresh Flow
        </button>
      </div>
    );
  }

  const nodes = flowData?.graph?.nodes || [];
  const editableNodes = flowData?.editable_flow?.nodes || [];
  const hasAppliedKnowledge = agent?.has_applied_website_knowledge || agent?.summary_markdown || agent?.website_knowledge;

  return (
    <div style={{ position: "relative", height: "100%", display: "flex", flexDirection: "column", background: "#0B0B0C", borderRadius: "16px", border: "1px solid #262626", overflow: "hidden" }}>
      {/* Canvas Top Bar */}
      <div style={{ padding: "14px 20px", background: "#141416", borderBottom: "1px solid #262626", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: "800", textTransform: "uppercase", letterSpacing: "0.5px", color: "#60A5FA", background: "rgba(59, 130, 246, 0.12)", padding: "4px 10px", borderRadius: "6px", border: "1px solid rgba(59, 130, 246, 0.25)" }}>
            <Zap size={14} /> Conversational Flow Engine
          </span>
          <span style={{ fontSize: "13px", color: "#A3A3A3" }}>
            {nodes.length} Nodes • {flowData?.stats?.edge_count || 0} Dynamic Transitions
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {hasAppliedKnowledge && (
            <span style={{ fontSize: "11px", fontWeight: "700", color: "#A78BFA", background: "rgba(167, 139, 250, 0.15)", padding: "4px 10px", borderRadius: "6px", border: "1px solid rgba(167, 139, 250, 0.3)", display: "flex", alignItems: "center", gap: "4px" }}>
              <Database size={12} /> Applied Summary Knowledge Active
            </span>
          )}

          <div style={{ display: "flex", gap: "4px", background: "#1E1E22", borderRadius: "6px", padding: "2px", border: "1px solid #262626" }}>
            <button onClick={() => setZoomLevel(Math.max(70, zoomLevel - 10))} style={{ padding: "4px 8px", background: "none", border: "none", color: "#A3A3A3", cursor: "pointer", fontSize: "12px", fontWeight: "700" }}>-</button>
            <span style={{ padding: "4px 6px", fontSize: "11px", color: "#FFFFFF", fontWeight: "700" }}>{zoomLevel}%</span>
            <button onClick={() => setZoomLevel(Math.min(130, zoomLevel + 10))} style={{ padding: "4px 8px", background: "none", border: "none", color: "#A3A3A3", cursor: "pointer", fontSize: "12px", fontWeight: "700" }}>+</button>
          </div>
        </div>
      </div>

      {/* Main Flow Canvas Viewport */}
      <div style={{ flex: 1, padding: "32px", overflowY: "auto", background: "radial-gradient(circle at 50% 50%, #151518 0%, #0B0B0C 100%)", transform: `scale(${zoomLevel / 100})`, transformOrigin: "top center", transition: "transform 0.15s ease-out" }}>
        <div style={{ maxWidth: "840px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "24px", position: "relative" }}>

          {/* Start Indicator */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{ padding: "6px 16px", borderRadius: "20px", background: "linear-gradient(135deg, #2563EB, #1D4ED8)", color: "#FFFFFF", fontSize: "12px", fontWeight: "800", letterSpacing: "1px", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px", boxShadow: "0 0 15px rgba(37, 99, 235, 0.4)" }}>
              <Play size={12} fill="#FFF" /> START CONVERSATION
            </div>
          </div>

          {nodes.map((node, index) => {
            const isLast = index === nodes.length - 1;
            const isActive = activeNodeId === node.id || (activeNodeId === null && index === 0);
            const isCompleted = activeNodeId && index < nodes.findIndex(n => n.id === activeNodeId);
            const editableNode = editableNodes.find(en => en.id === node.id) || {
              id: node.id,
              type: node.type,
              label: node.label,
              response_en: node.agent_says,
              collects: node.collects || [],
              transitions: []
            };

            return (
              <React.Fragment key={node.id}>
                {/* Node Card Container */}
                <div
                  style={{
                    background: isActive ? "linear-gradient(180deg, #1E1B4B 0%, #141416 100%)" : "#141416",
                    border: isActive ? "2px solid #6366F1" : isCompleted ? "1px solid #10B981" : "1px solid #262626",
                    borderRadius: "14px",
                    padding: "20px",
                    position: "relative",
                    transition: "all 0.2s ease-out",
                    boxShadow: isActive ? "0 0 24px rgba(99, 102, 241, 0.3)" : "none"
                  }}
                >
                  {/* Node Status Badge */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div style={{ padding: "6px", borderRadius: "8px", background: "rgba(255, 255, 255, 0.05)" }}>
                        {getNodeIcon(node.type)}
                      </div>
                      <div>
                        <div style={{ fontSize: "11px", fontWeight: "700", color: "#6366F1", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                          {getNodeTypeLabel(node.type)}
                        </div>
                        <h4 style={{ fontSize: "16px", fontWeight: "800", color: "#FFFFFF", margin: 0 }}>
                          {node.label}
                        </h4>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      {isActive && (
                        <span style={{ fontSize: "11px", fontWeight: "800", background: "rgba(99, 102, 241, 0.2)", color: "#818CF8", padding: "4px 10px", borderRadius: "12px", border: "1px solid rgba(99, 102, 241, 0.4)", display: "flex", alignItems: "center", gap: "4px" }}>
                          <span className="scrape-loading-dot" style={{ background: "#818CF8", width: "6px", height: "6px" }} /> ACTIVE RUNTIME NODE
                        </span>
                      )}

                      {isCompleted && (
                        <span style={{ fontSize: "11px", fontWeight: "700", background: "rgba(16, 185, 129, 0.15)", color: "#10B981", padding: "4px 10px", borderRadius: "12px", border: "1px solid rgba(16, 185, 129, 0.3)", display: "flex", alignItems: "center", gap: "4px" }}>
                          <Check size={12} /> COMPLETED
                        </span>
                      )}

                      <button
                        onClick={() => setEditingNode(editableNode)}
                        style={{
                          padding: "6px 12px", borderRadius: "6px", background: "#1E1E22",
                          border: "1px solid #3D3D3D", color: "#FFFFFF", fontSize: "12px",
                          fontWeight: "600", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px"
                        }}
                      >
                        <Edit3 size={13} /> Edit Node
                      </button>
                    </div>
                  </div>

                  {/* Agent Response Prompt Summary */}
                  <div style={{ background: "#09090B", borderRadius: "10px", padding: "14px", border: "1px solid #1E1E22", marginBottom: "14px" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", color: "#A3A3A3", marginBottom: "4px", textTransform: "uppercase" }}>
                      Spoken Response / Prompt Logic:
                    </div>
                    <p style={{ fontSize: "14px", color: "#E5E5E5", margin: 0, lineHeight: "1.5" }}>
                      "{node.agent_says || "Dynamically generated by LLM based on user intent & agent system prompt."}"
                    </p>
                  </div>

                  {/* Collected Slots / Knowledge Tags */}
                  {(node.collects?.length > 0 || (index === 1 && hasAppliedKnowledge)) && (
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center", marginBottom: "14px" }}>
                      <span style={{ fontSize: "11px", color: "#A3A3A3", fontWeight: "700" }}>Captures:</span>
                      {node.collects?.map((slot) => (
                        <span key={slot} style={{ fontSize: "11px", fontWeight: "700", background: "rgba(16, 185, 129, 0.15)", color: "#34D399", padding: "3px 8px", borderRadius: "4px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                          {slot}
                        </span>
                      ))}

                      {index === 1 && hasAppliedKnowledge && (
                        <span style={{ fontSize: "11px", fontWeight: "700", background: "rgba(167, 139, 250, 0.15)", color: "#C4B5FD", padding: "3px 8px", borderRadius: "4px", border: "1px solid rgba(167, 139, 250, 0.3)" }}>
                          📚 Applied Website Knowledge Context
                        </span>
                      )}
                    </div>
                  )}

                  {/* Transition Next Step Badges */}
                  {node.expected_user_responses?.length > 0 && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingTop: "10px", borderTop: "1px solid #1E1E22" }}>
                      <span style={{ fontSize: "11px", color: "#A3A3A3", fontWeight: "700" }}>Transitions:</span>
                      {node.expected_user_responses.map((resp) => (
                        <span key={resp} style={{ fontSize: "11px", fontWeight: "600", background: "#1E1E22", color: "#D4D4D4", padding: "2px 8px", borderRadius: "4px", border: "1px solid #3D3D3D", display: "flex", alignItems: "center", gap: "4px" }}>
                          {resp} <ArrowRight size={10} className="text-gray-400" />
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Vertical Connector Arrow */}
                {!isLast && (
                  <div style={{ display: "flex", justifyContent: "center", margin: "-8px 0" }}>
                    <div style={{ width: "2px", height: "24px", background: isActive ? "#6366F1" : "#262626", position: "relative" }}>
                      <div style={{ position: "absolute", bottom: "-4px", left: "-3px", width: "8px", height: "8px", borderRight: `2px solid ${isActive ? "#6366F1" : "#262626"}`, borderBottom: `2px solid ${isActive ? "#6366F1" : "#262626"}`, transform: "rotate(45deg)" }} />
                    </div>
                  </div>
                )}
              </React.Fragment>
            );
          })}

          {/* End Conversation Tag */}
          <div style={{ display: "flex", justifyContent: "center", marginTop: "12px" }}>
            <div style={{ padding: "6px 16px", borderRadius: "20px", background: "#1E1E22", color: "#A3A3A3", border: "1px solid #262626", fontSize: "12px", fontWeight: "700", display: "flex", alignItems: "center", gap: "6px" }}>
              <CheckCircle2 size={14} /> CONVERSATION COMPLETION NODE
            </div>
          </div>

        </div>
      </div>

      {/* NODE EDITING MODAL */}
      {editingNode && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
          <div style={{ background: "#141416", borderRadius: "16px", border: "1px solid #3D3D3D", width: "600px", maxWidth: "90vw", padding: "24px", color: "#FFF" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", pb: "12px", borderBottom: "1px solid #262626" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Edit3 size={18} className="text-blue-400" />
                <h3 style={{ fontSize: "18px", fontWeight: "800", margin: 0 }}>
                  Edit Node: {editingNode.label}
                </h3>
              </div>
              <button onClick={() => setEditingNode(null)} style={{ background: "none", border: "none", color: "#A3A3A3", cursor: "pointer" }}>
                <X size={20} />
              </button>
            </div>

            {saveError && (
              <div style={{ padding: "10px 14px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#F87171", fontSize: "13px", marginBottom: "16px" }}>
                ⚠️ {saveError}
              </div>
            )}

            {saveSuccess && (
              <div style={{ padding: "10px 14px", borderRadius: "8px", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", color: "#34D399", fontSize: "13px", marginBottom: "16px" }}>
                ✓ Node configuration saved & persisted cleanly!
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                  Node Label
                </label>
                <input
                  type="text"
                  value={editingNode.label || ""}
                  onChange={(e) => setEditingNode({ ...editingNode, label: e.target.value })}
                  style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "14px", outline: "none" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                  Agent Spoken Response
                </label>
                <textarea
                  rows={4}
                  value={editingNode.response_en || ""}
                  onChange={(e) => setEditingNode({ ...editingNode, response_en: e.target.value })}
                  style={{ width: "100%", padding: "12px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px", outline: "none", lineHeight: "1.4" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                  Collected Slots (Comma-separated)
                </label>
                <input
                  type="text"
                  value={(editingNode.collects || []).join(", ")}
                  onChange={(e) => setEditingNode({ ...editingNode, collects: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}
                  placeholder="e.g. budget, location, qualification"
                  style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px", outline: "none" }}
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #262626" }}>
              <button
                onClick={() => setEditingNode(null)}
                style={{ padding: "10px 18px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveNodeEdit}
                disabled={saving}
                style={{ padding: "10px 22px", borderRadius: "8px", background: "#3b82f6", border: "none", color: "#FFF", fontWeight: "700", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
              >
                <Save size={14} /> {saving ? "Saving..." : "Save Node"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
