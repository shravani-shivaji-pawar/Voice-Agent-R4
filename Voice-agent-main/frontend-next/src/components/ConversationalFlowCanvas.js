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
  Database,
  Trash2
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
  
  // Node editor states
  const [editingNode, setEditingNode] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newNodeData, setNewNodeData] = useState(null);

  // Deletion states
  const [deletingNode, setDeletingNode] = useState(null);
  const [reconnectTarget, setReconnectTarget] = useState("");

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

  // Helper to get current list of editable nodes
  const getEditableNodes = () => {
    if (flowData?.editable_flow?.nodes?.length) {
      return flowData.editable_flow.nodes;
    }
    const graphNodes = flowData?.graph?.nodes || [];
    const graphEdges = flowData?.graph?.edges || [];
    return graphNodes.map((node) => ({
      id: node.id,
      type: node.type || "message",
      label: node.label || node.id,
      response_en: node.agent_says || "",
      collects: node.collects || [],
      transitions: graphEdges
        .filter((edge) => edge.from === node.id)
        .map((edge) => ({
          intent: edge.intent || "confirm",
          label: edge.label || edge.intent || "Continue",
          target: edge.to || ""
        }))
    }));
  };

  const getUniqueIntent = (transitions) => {
    const existing = new Set((transitions || []).map(t => (t.intent || "").trim().toLowerCase()));
    const defaults = ["confirm", "deny", "unclear", "provide_info", "custom_intent_1", "custom_intent_2", "custom_intent_3"];
    for (const intent of defaults) {
      if (!existing.has(intent)) return intent;
    }
    let count = 1;
    while (existing.has(`intent_${count}`)) count++;
    return `intent_${count}`;
  };

  const saveNodesToBackend = async (nodesToSave) => {
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);

    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.id}/flow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nodes: nodesToSave }),
      });

      if (res.ok) {
        const updatedFlow = await res.json();
        setFlowData(updatedFlow);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 1500);
        if (onFlowUpdated) onFlowUpdated(updatedFlow);
        return true;
      } else {
        const errData = await res.json().catch(() => ({}));
        setSaveError(errData.detail || "Failed to update node configuration.");
        return false;
      }
    } catch (err) {
      setSaveError(err.message || "Network error while saving node.");
      return false;
    } finally {
      setSaving(false);
    }
  };

  // ----------------------------------------------------
  // FEATURE 1: EDIT NODE
  // ----------------------------------------------------
  const handleSaveNodeEdit = async () => {
    if (!editingNode || !agent?.id) return;
    
    // Validate duplicate transition intents
    if (editingNode.type !== "end" && editingNode.transitions?.length > 0) {
      const seenIntents = new Set();
      for (const t of editingNode.transitions) {
        const intent = (t.intent || "").trim().toLowerCase();
        if (!intent) {
          setSaveError("Every transition must specify an intent.");
          return;
        }
        if (seenIntents.has(intent)) {
          setSaveError(`Duplicate transition intent "${t.intent}". Each transition intent on a node must be unique.`);
          return;
        }
        seenIntents.add(intent);
      }
    }

    const currentNodes = getEditableNodes();
    const updatedNodes = currentNodes.map((n) => 
      n.id === editingNode.id ? editingNode : n
    );

    const success = await saveNodesToBackend(updatedNodes);
    if (success) {
      setEditingNode(null);
    }
  };

  // ----------------------------------------------------
  // FEATURE 2: ADD NODE
  // ----------------------------------------------------
  // Add node modal & placement states
  const [placementMode, setPlacementMode] = useState("end"); // "beginning" | "before" | "after" | "between" | "end"
  const [targetNodeId, setTargetNodeId] = useState("");
  const [fromNodeId, setFromNodeId] = useState("");
  const [toNodeId, setToNodeId] = useState("");

  const handleOpenAddModal = () => {
    const currentNodes = getEditableNodes();
    const defaultTarget = currentNodes.find(n => n.type === "end")?.id || currentNodes[0]?.id || "";
    const startNodeId = flowData?.graph?.start_node_id || currentNodes[0]?.id || "start";

    setNewNodeData({
      id: `node_${Date.now().toString(36)}`,
      label: "New Step",
      type: "message",
      response_en: "How can I assist you with this requirement?",
      collects: [],
      transitions: [
        { intent: "confirm", label: "User Confirms", target: defaultTarget }
      ]
    });

    setPlacementMode("after");
    setTargetNodeId(currentNodes.find(n => n.id !== startNodeId)?.id || currentNodes[0]?.id || "");
    setFromNodeId(startNodeId);
    setToNodeId(defaultTarget);
    setSaveError("");
    setShowAddModal(true);
  };

  const handleSaveNewNode = async () => {
    if (!newNodeData || !agent?.id) return;
    if (!newNodeData.label.trim()) {
      setSaveError("Node label is required.");
      return;
    }
    if (!newNodeData.response_en.trim()) {
      setSaveError("Spoken response instructions are required.");
      return;
    }

    const currentNodes = getEditableNodes();
    if (currentNodes.some(n => n.id === newNodeData.id)) {
      setSaveError(`Node ID '${newNodeData.id}' already exists. Please use a unique label.`);
      return;
    }

    const startNodeId = flowData?.graph?.start_node_id || currentNodes[0]?.id || "start";
    let finalNewNode = { ...newNodeData };
    let updatedNodes = [...currentNodes];

    // Compute transition graph rewiring based on placement mode
    if (placementMode === "beginning") {
      const startNode = currentNodes.find(n => n.id === startNodeId);
      const originalNextTarget = startNode?.transitions?.[0]?.target || currentNodes.find(n => n.id !== startNodeId)?.id || "";

      // New node transitions to start node's previous target
      if (finalNewNode.type !== "end" && originalNextTarget) {
        const intent = getUniqueIntent(finalNewNode.transitions);
        finalNewNode.transitions = [{ intent, label: "Continue", target: originalNextTarget }];
      }

      // Update start node to point to new node
      updatedNodes = updatedNodes.map(n => {
        if (n.id === startNodeId) {
          const transitions = n.transitions?.length > 0
            ? n.transitions.map((t, idx) => idx === 0 ? { ...t, target: finalNewNode.id } : t)
            : [{ intent: "confirm", label: "Start", target: finalNewNode.id }];
          return { ...n, transitions };
        }
        return n;
      });
    } else if (placementMode === "before") {
      if (!targetNodeId) {
        setSaveError("Please select a target node to insert before.");
        return;
      }
      const targetNode = currentNodes.find(n => n.id === targetNodeId);

      // New node transitions to target node
      if (finalNewNode.type !== "end") {
        const intent = getUniqueIntent(finalNewNode.transitions);
        finalNewNode.transitions = [{ intent, label: `To ${targetNode?.label || targetNodeId}`, target: targetNodeId }];
      }

      // Nodes pointing to target node now point to new node
      let rewiredAny = false;
      updatedNodes = updatedNodes.map(n => {
        const hasMatchingTransition = (n.transitions || []).some(t => t.target === targetNodeId);
        if (hasMatchingTransition) {
          rewiredAny = true;
          const updatedTransitions = n.transitions.map(t =>
            t.target === targetNodeId ? { ...t, target: finalNewNode.id } : t
          );
          return { ...n, transitions: updatedTransitions };
        }
        return n;
      });

      if (!rewiredAny) {
        updatedNodes = updatedNodes.map(n => {
          if (n.id === startNodeId) {
            const transitions = n.transitions?.length > 0
              ? n.transitions.map((t, idx) => idx === 0 ? { ...t, target: finalNewNode.id } : t)
              : [{ intent: "confirm", label: "Start", target: finalNewNode.id }];
            return { ...n, transitions };
          }
          return n;
        });
      }
    } else if (placementMode === "after") {
      if (!targetNodeId) {
        setSaveError("Please select a target node to insert after.");
        return;
      }
      const targetNode = currentNodes.find(n => n.id === targetNodeId);
      const originalTarget = targetNode?.transitions?.[0]?.target || currentNodes.find(n => n.type === "end")?.id || "";

      // New node transitions to target node's former next target
      if (finalNewNode.type !== "end" && originalTarget) {
        const intent = getUniqueIntent(finalNewNode.transitions);
        finalNewNode.transitions = [{ intent, label: "Continue", target: originalTarget }];
      }

      // Target node now transitions to new node
      updatedNodes = updatedNodes.map(n => {
        if (n.id === targetNodeId) {
          const updatedTransitions = n.transitions?.length > 0
            ? n.transitions.map((t, idx) => idx === 0 ? { ...t, target: finalNewNode.id } : t)
            : [{ intent: "confirm", label: "Next", target: finalNewNode.id }];
          return { ...n, transitions: updatedTransitions };
        }
        return n;
      });
    } else if (placementMode === "between") {
      if (!fromNodeId || !toNodeId) {
        setSaveError("Please select both From Node and To Node.");
        return;
      }
      if (fromNodeId === toNodeId) {
        setSaveError("From Node and To Node must be different.");
        return;
      }

      // New node transitions to toNode
      if (finalNewNode.type !== "end") {
        const intent = getUniqueIntent(finalNewNode.transitions);
        finalNewNode.transitions = [{ intent, label: "Continue", target: toNodeId }];
      }

      // Update fromNode's transition to target new node
      updatedNodes = updatedNodes.map(n => {
        if (n.id === fromNodeId) {
          const transitions = n.transitions || [];
          const hasMatchingTo = transitions.some(t => t.target === toNodeId);
          let updatedTransitions;
          if (hasMatchingTo) {
            updatedTransitions = transitions.map(t =>
              t.target === toNodeId ? { ...t, target: finalNewNode.id } : t
            );
          } else if (transitions.length > 0) {
            updatedTransitions = transitions.map((t, idx) =>
              idx === 0 ? { ...t, target: finalNewNode.id } : t
            );
          } else {
            const intent = getUniqueIntent([]);
            updatedTransitions = [{ intent, label: "Continue", target: finalNewNode.id }];
          }
          return { ...n, transitions: updatedTransitions };
        }
        return n;
      });
    }

    // Ensure non-terminal nodes have transitions
    if (finalNewNode.type !== "end" && (!finalNewNode.transitions || finalNewNode.transitions.length === 0)) {
      setSaveError("Non-terminal nodes require at least one outgoing transition.");
      return;
    }

    // Validate duplicate transition intents
    if (finalNewNode.type !== "end" && finalNewNode.transitions?.length > 0) {
      const seenIntents = new Set();
      for (const t of finalNewNode.transitions) {
        const intent = (t.intent || "").trim().toLowerCase();
        if (!intent) {
          setSaveError("Every transition must specify an intent.");
          return;
        }
        if (seenIntents.has(intent)) {
          setSaveError(`Duplicate transition intent "${t.intent}". Each transition intent on a node must be unique.`);
          return;
        }
        seenIntents.add(intent);
      }
    }

    // Insert finalNewNode at the exact requested position in the node list
    let insertIndex = updatedNodes.length;
    if (placementMode === "beginning") {
      const startIndex = updatedNodes.findIndex(n => n.id === startNodeId);
      insertIndex = startIndex >= 0 ? startIndex + 1 : 0;
    } else if (placementMode === "before") {
      const targetIndex = updatedNodes.findIndex(n => n.id === targetNodeId);
      insertIndex = targetIndex >= 0 ? targetIndex : updatedNodes.length;
    } else if (placementMode === "after") {
      const targetIndex = updatedNodes.findIndex(n => n.id === targetNodeId);
      insertIndex = targetIndex >= 0 ? targetIndex + 1 : updatedNodes.length;
    } else if (placementMode === "between") {
      const fromIndex = updatedNodes.findIndex(n => n.id === fromNodeId);
      insertIndex = fromIndex >= 0 ? fromIndex + 1 : updatedNodes.length;
    }
    updatedNodes.splice(insertIndex, 0, finalNewNode);

    const success = await saveNodesToBackend(updatedNodes);
    if (success) {
      setShowAddModal(false);
      setNewNodeData(null);
    }
  };

  // ----------------------------------------------------
  // FEATURE 3: DELETE NODE
  // ----------------------------------------------------
  const handleOpenDeleteConfirm = (node) => {
    const currentNodes = getEditableNodes();
    const startNodeId = flowData?.graph?.start_node_id || currentNodes[0]?.id || "start";
    
    // Protection rule 1: Start node
    if (node.id === startNodeId) {
      alert("Cannot delete the mandatory Start / Greeting node.");
      return;
    }

    // Protection rule 2: End node requirement
    const endNodes = currentNodes.filter(n => n.type === "end");
    if (node.type === "end" && endNodes.length <= 1) {
      alert("Cannot delete the last remaining End node. Flow requires at least one End node.");
      return;
    }

    // Find fallback reconnect target among remaining nodes
    const remainingNodes = currentNodes.filter(n => n.id !== node.id);
    const defaultReconnect = remainingNodes.find(n => n.type === "end")?.id || remainingNodes[0]?.id || "";
    
    setDeletingNode(node);
    setReconnectTarget(defaultReconnect);
    setSaveError("");
  };

  const handleConfirmDeleteNode = async () => {
    if (!deletingNode || !agent?.id) return;
    const currentNodes = getEditableNodes();
    
    // Remove the target node and update any incoming transitions
    const updatedNodes = currentNodes
      .filter(n => n.id !== deletingNode.id)
      .map(n => {
        const updatedTransitions = (n.transitions || [])
          .map(t => {
            if (t.target === deletingNode.id) {
              return reconnectTarget ? { ...t, target: reconnectTarget } : null;
            }
            return t;
          })
          .filter(Boolean);

        return {
          ...n,
          transitions: updatedTransitions
        };
      });

    const success = await saveNodesToBackend(updatedNodes);
    if (success) {
      setDeletingNode(null);
      setReconnectTarget("");
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
  const editableNodes = getEditableNodes();
  const startNodeId = flowData?.graph?.start_node_id || nodes[0]?.id || "start";
  const hasAppliedKnowledge = agent?.has_applied_website_knowledge || agent?.summary_markdown || agent?.website_knowledge;

  return (
    <div style={{ position: "relative", height: "100%", display: "flex", flexDirection: "column", background: "#0B0B0C", borderRadius: "16px", border: "1px solid #262626", overflow: "hidden" }}>
      {/* Canvas Top Bar */}
      <div style={{ padding: "14px 20px", background: "#141416", borderBottom: "1px solid #262626", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
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

          {/* + ADD NODE BUTTON */}
          <button
            onClick={handleOpenAddModal}
            style={{
              padding: "7px 14px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #10B981, #059669)",
              color: "#FFFFFF",
              border: "none",
              fontSize: "13px",
              fontWeight: "700",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 0 12px rgba(16, 185, 129, 0.3)"
            }}
          >
            <Plus size={15} /> Add Node
          </button>

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
            const isStartNode = node.id === startNodeId;
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

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                        <Edit3 size={13} /> Edit
                      </button>

                      <button
                        onClick={() => handleOpenDeleteConfirm(editableNode)}
                        disabled={isStartNode}
                        title={isStartNode ? "Start node cannot be deleted" : "Delete node"}
                        style={{
                          padding: "6px 10px", borderRadius: "6px",
                          background: isStartNode ? "#1A1A1D" : "rgba(239, 68, 68, 0.15)",
                          border: isStartNode ? "1px solid #262626" : "1px solid rgba(239, 68, 68, 0.3)",
                          color: isStartNode ? "#525252" : "#F87171",
                          fontSize: "12px", fontWeight: "600",
                          cursor: isStartNode ? "not-allowed" : "pointer",
                          display: "flex", alignItems: "center", gap: "4px"
                        }}
                      >
                        <Trash2 size={13} />
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
                  {(editableNode.transitions?.length > 0 || node.expected_user_responses?.length > 0) && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", paddingTop: "10px", borderTop: "1px solid #1E1E22" }}>
                      <span style={{ fontSize: "11px", color: "#A3A3A3", fontWeight: "700" }}>Transitions:</span>
                      {editableNode.transitions?.map((t, idx) => {
                        const targetNodeObj = editableNodes.find(n => n.id === t.target);
                        const targetLabel = targetNodeObj ? targetNodeObj.label : t.target;
                        return (
                          <span key={idx} style={{ fontSize: "11px", fontWeight: "600", background: "#1E1E22", color: "#D4D4D4", padding: "3px 8px", borderRadius: "4px", border: "1px solid #3D3D3D", display: "flex", alignItems: "center", gap: "4px" }}>
                            {t.label || t.intent} <ArrowRight size={10} className="text-blue-400" /> <span style={{ color: "#60A5FA", fontWeight: "700" }}>{targetLabel}</span>
                          </span>
                        );
                      })}
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

      {/* ---------------------------------------------------- */}
      {/* FEATURE 1: ADD NODE MODAL                             */}
      {/* ---------------------------------------------------- */}
      {showAddModal && newNodeData && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
          <div style={{ background: "#141416", borderRadius: "16px", border: "1px solid #3D3D3D", width: "640px", maxWidth: "92vw", maxHeight: "90vh", overflowY: "auto", padding: "24px", color: "#FFF" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", paddingBottom: "12px", borderBottom: "1px solid #262626" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Plus size={20} className="text-emerald-400" />
                <h3 style={{ fontSize: "18px", fontWeight: "800", margin: 0 }}>
                  Add Conversation Node
                </h3>
              </div>
              <button onClick={() => setShowAddModal(false)} style={{ background: "none", border: "none", color: "#A3A3A3", cursor: "pointer" }}>
                <X size={20} />
              </button>
            </div>

            {saveError && (
              <div style={{ padding: "10px 14px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#F87171", fontSize: "13px", marginBottom: "16px" }}>
                ⚠️ {saveError}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                    Node Label / Name *
                  </label>
                  <input
                    type="text"
                    value={newNodeData.label || ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      const slug = val.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
                      setNewNodeData({ 
                        ...newNodeData, 
                        label: val,
                        id: slug ? `node_${slug}` : `node_${Date.now().toString(36)}`
                      });
                    }}
                    placeholder="e.g. Technical Support"
                    style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "14px", outline: "none" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                    Node Type
                  </label>
                  <select
                    value={newNodeData.type || "message"}
                    onChange={(e) => setNewNodeData({ ...newNodeData, type: e.target.value })}
                    style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "14px", outline: "none" }}
                  >
                    <option value="message">Message (Spoken Response)</option>
                    <option value="slot_collection">Slot Qualification</option>
                    <option value="fallback">Clarification / Fallback</option>
                    <option value="end">Conversation End</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                  Spoken Response / Instructions *
                </label>
                <textarea
                  rows={3}
                  value={newNodeData.response_en || ""}
                  onChange={(e) => setNewNodeData({ ...newNodeData, response_en: e.target.value })}
                  placeholder="Instructions or spoken response text for this node..."
                  style={{ width: "100%", padding: "12px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px", outline: "none", lineHeight: "1.4" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                  Information to Collect (Slots, comma-separated)
                </label>
                <input
                  type="text"
                  value={(newNodeData.collects || []).join(", ")}
                  onChange={(e) => setNewNodeData({ ...newNodeData, collects: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}
                  placeholder="e.g. invoice_number, issue_type"
                  style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px", outline: "none" }}
                />
              </div>

              {/* Insertion Location Section */}
              <div style={{ background: "#19191C", borderRadius: "10px", padding: "14px", border: "1px solid #2D2D32" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#60A5FA", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  🎯 Insertion Location
                </label>
                
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "12px" }}>
                  <button
                    type="button"
                    onClick={() => setPlacementMode("beginning")}
                    style={{
                      padding: "8px 12px", borderRadius: "6px",
                      background: placementMode === "beginning" ? "#2563EB" : "#141416",
                      border: placementMode === "beginning" ? "1px solid #60A5FA" : "1px solid #3D3D3D",
                      color: "#FFF", fontSize: "12px", fontWeight: "700", cursor: "pointer", textAlign: "left"
                    }}
                  >
                    Option 1: At Beginning
                  </button>

                  <button
                    type="button"
                    onClick={() => setPlacementMode("before")}
                    style={{
                      padding: "8px 12px", borderRadius: "6px",
                      background: placementMode === "before" ? "#2563EB" : "#141416",
                      border: placementMode === "before" ? "1px solid #60A5FA" : "1px solid #3D3D3D",
                      color: "#FFF", fontSize: "12px", fontWeight: "700", cursor: "pointer", textAlign: "left"
                    }}
                  >
                    Option 2: Before Existing Node
                  </button>

                  <button
                    type="button"
                    onClick={() => setPlacementMode("after")}
                    style={{
                      padding: "8px 12px", borderRadius: "6px",
                      background: placementMode === "after" ? "#2563EB" : "#141416",
                      border: placementMode === "after" ? "1px solid #60A5FA" : "1px solid #3D3D3D",
                      color: "#FFF", fontSize: "12px", fontWeight: "700", cursor: "pointer", textAlign: "left"
                    }}
                  >
                    Option 3: After Existing Node
                  </button>

                  <button
                    type="button"
                    onClick={() => setPlacementMode("between")}
                    style={{
                      padding: "8px 12px", borderRadius: "6px",
                      background: placementMode === "between" ? "#2563EB" : "#141416",
                      border: placementMode === "between" ? "1px solid #60A5FA" : "1px solid #3D3D3D",
                      color: "#FFF", fontSize: "12px", fontWeight: "700", cursor: "pointer", textAlign: "left"
                    }}
                  >
                    Option 4: Between Two Nodes
                  </button>
                </div>

                {/* Controls for Before / After */}
                {(placementMode === "before" || placementMode === "after") && (
                  <div style={{ marginBottom: "10px" }}>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: "700", color: "#A3A3A3", marginBottom: "4px" }}>
                      {placementMode === "before" ? "Before node:" : "After node:"}
                    </label>
                    <select
                      value={targetNodeId}
                      onChange={(e) => setTargetNodeId(e.target.value)}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", background: "#141416", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px" }}
                    >
                      {editableNodes.map(n => (
                        <option key={n.id} value={n.id}>{n.label} ({n.id})</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Controls for Between */}
                {placementMode === "between" && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", color: "#A3A3A3", marginBottom: "4px" }}>
                        From node:
                      </label>
                      <select
                        value={fromNodeId}
                        onChange={(e) => setFromNodeId(e.target.value)}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", background: "#141416", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px" }}
                      >
                        {editableNodes.map(n => (
                          <option key={n.id} value={n.id}>{n.label} ({n.id})</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", color: "#A3A3A3", marginBottom: "4px" }}>
                        To node:
                      </label>
                      <select
                        value={toNodeId}
                        onChange={(e) => setToNodeId(e.target.value)}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", background: "#141416", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px" }}
                      >
                        {editableNodes.map(n => (
                          <option key={n.id} value={n.id}>{n.label} ({n.id})</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* Live Insertion Preview */}
                <div style={{ padding: "10px", borderRadius: "6px", background: "#09090B", border: "1px dashed #3B82F6", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", flexWrap: "wrap", fontSize: "12px" }}>
                  <span style={{ color: "#A3A3A3", fontWeight: "600" }}>Live Preview:</span>
                  {placementMode === "beginning" && (
                    <>
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>Start</span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#34D399", fontWeight: "800", background: "rgba(16, 185, 129, 0.2)", padding: "2px 8px", borderRadius: "4px" }}>
                        ✨ [ {newNodeData.label || "New Node"} ]
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>
                        {editableNodes.find(n => n.id !== startNodeId)?.label || "First Step"}
                      </span>
                    </>
                  )}

                  {placementMode === "before" && (
                    <>
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>Prior Node</span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#34D399", fontWeight: "800", background: "rgba(16, 185, 129, 0.2)", padding: "2px 8px", borderRadius: "4px" }}>
                        ✨ [ {newNodeData.label || "New Node"} ]
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>
                        {editableNodes.find(n => n.id === targetNodeId)?.label || targetNodeId || "Target Node"}
                      </span>
                    </>
                  )}

                  {placementMode === "after" && (
                    <>
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>
                        {editableNodes.find(n => n.id === targetNodeId)?.label || targetNodeId || "Prior Node"}
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#34D399", fontWeight: "800", background: "rgba(16, 185, 129, 0.2)", padding: "2px 8px", borderRadius: "4px" }}>
                        ✨ [ {newNodeData.label || "New Node"} ]
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>Next Node</span>
                    </>
                  )}

                  {placementMode === "between" && (
                    <>
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>
                        {editableNodes.find(n => n.id === fromNodeId)?.label || fromNodeId || "From Node"}
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#34D399", fontWeight: "800", background: "rgba(16, 185, 129, 0.2)", padding: "2px 8px", borderRadius: "4px" }}>
                        ✨ [ {newNodeData.label || "New Node"} ]
                      </span>
                      <ArrowRight size={12} className="text-blue-400" />
                      <span style={{ color: "#93C5FD", fontWeight: "700" }}>
                        {editableNodes.find(n => n.id === toNodeId)?.label || toNodeId || "To Node"}
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Transitions list */}
              {newNodeData.type !== "end" && (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "700", color: "#A3A3A3" }}>
                      Outgoing Transitions
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const target = editableNodes.find(n => n.type === "end")?.id || editableNodes[0]?.id || "";
                        const intent = getUniqueIntent(newNodeData.transitions);
                        const label = intent.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                        setNewNodeData({
                          ...newNodeData,
                          transitions: [...(newNodeData.transitions || []), { intent, label, target }]
                        });
                      }}
                      style={{ padding: "3px 8px", borderRadius: "4px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#60A5FA", fontSize: "11px", fontWeight: "700", cursor: "pointer" }}
                    >
                      + Add Transition
                    </button>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {(newNodeData.transitions || []).map((t, idx) => (
                      <div key={idx} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 30px", gap: "8px", alignItems: "center" }}>
                        <input
                          type="text"
                          value={t.intent || ""}
                          placeholder="Intent (e.g. confirm)"
                          onChange={(e) => {
                            const updated = [...newNodeData.transitions];
                            updated[idx] = { ...updated[idx], intent: e.target.value };
                            setNewNodeData({ ...newNodeData, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        />
                        <input
                          type="text"
                          value={t.label || ""}
                          placeholder="Label (e.g. Yes)"
                          onChange={(e) => {
                            const updated = [...newNodeData.transitions];
                            updated[idx] = { ...updated[idx], label: e.target.value };
                            setNewNodeData({ ...newNodeData, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        />
                        <select
                          value={t.target || ""}
                          onChange={(e) => {
                            const updated = [...newNodeData.transitions];
                            updated[idx] = { ...updated[idx], target: e.target.value };
                            setNewNodeData({ ...newNodeData, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        >
                          <option value="">-- Target Node --</option>
                          {editableNodes.map(n => (
                            <option key={n.id} value={n.id}>{n.label} ({n.id})</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => {
                            const updated = newNodeData.transitions.filter((_, i) => i !== idx);
                            setNewNodeData({ ...newNodeData, transitions: updated });
                          }}
                          style={{ background: "none", border: "none", color: "#F87171", cursor: "pointer", padding: 0 }}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #262626" }}>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ padding: "10px 18px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveNewNode}
                disabled={saving}
                style={{ padding: "10px 22px", borderRadius: "8px", background: "#10B981", border: "none", color: "#FFF", fontWeight: "700", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
              >
                <Save size={14} /> {saving ? "Saving..." : "Add & Save Node"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- */}
      {/* FEATURE 2: DELETE NODE CONFIRMATION MODAL            */}
      {/* ---------------------------------------------------- */}
      {deletingNode && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
          <div style={{ background: "#141416", borderRadius: "16px", border: "1px solid #3D3D3D", width: "520px", maxWidth: "90vw", padding: "24px", color: "#FFF" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
              <div style={{ padding: "8px", borderRadius: "10px", background: "rgba(239, 68, 68, 0.15)" }}>
                <Trash2 size={22} className="text-red-400" />
              </div>
              <h3 style={{ fontSize: "18px", fontWeight: "800", margin: 0, color: "#FFFFFF" }}>
                Delete Node: {deletingNode.label}?
              </h3>
            </div>

            <p style={{ fontSize: "14px", color: "#D4D4D4", lineHeight: "1.5", marginBottom: "16px" }}>
              Are you sure you want to permanently delete node <strong>"{deletingNode.label}"</strong>? This action will remove the node from the saved flow configuration and runtime.
            </p>

            {/* Reconnect incoming transitions */}
            {(() => {
              const incoming = editableNodes.filter(n => 
                n.id !== deletingNode.id && (n.transitions || []).some(t => t.target === deletingNode.id)
              );

              if (incoming.length > 0) {
                const remaining = editableNodes.filter(n => n.id !== deletingNode.id);
                return (
                  <div style={{ background: "#1E1E22", borderRadius: "10px", padding: "14px", border: "1px solid #3D3D3D", marginBottom: "16px" }}>
                    <div style={{ fontSize: "12px", fontWeight: "700", color: "#FBBF24", marginBottom: "8px" }}>
                      ⚠️ {incoming.length} node(s) currently transition to this node:
                    </div>
                    <ul style={{ fontSize: "12px", color: "#A3A3A3", paddingLeft: "20px", margin: "0 0 12px 0" }}>
                      {incoming.map(inc => (
                        <li key={inc.id}>{inc.label} ({inc.id})</li>
                      ))}
                    </ul>

                    <label style={{ display: "block", fontSize: "12px", fontWeight: "700", color: "#A3A3A3", marginBottom: "6px" }}>
                      Reconnect incoming transitions to:
                    </label>
                    <select
                      value={reconnectTarget}
                      onChange={(e) => setReconnectTarget(e.target.value)}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", background: "#141416", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "13px", outline: "none" }}
                    >
                      <option value="">Remove Incoming Transitions</option>
                      {remaining.map(r => (
                        <option key={r.id} value={r.id}>{r.label} ({r.id})</option>
                      ))}
                    </select>
                  </div>
                );
              }
              return null;
            })()}

            {saveError && (
              <div style={{ padding: "10px 14px", borderRadius: "8px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#F87171", fontSize: "13px", marginBottom: "16px" }}>
                ⚠️ {saveError}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "20px" }}>
              <button
                onClick={() => {
                  setDeletingNode(null);
                  setReconnectTarget("");
                }}
                style={{ padding: "10px 18px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontWeight: "600", fontSize: "13px", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeleteNode}
                disabled={saving}
                style={{ padding: "10px 22px", borderRadius: "8px", background: "#EF4444", border: "none", color: "#FFF", fontWeight: "700", fontSize: "13px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
              >
                <Trash2 size={14} /> {saving ? "Deleting..." : "Permanently Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------- */}
      {/* FEATURE 1: EDIT NODE MODAL WITH TRANSITIONS          */}
      {/* ---------------------------------------------------- */}
      {editingNode && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
          <div style={{ background: "#141416", borderRadius: "16px", border: "1px solid #3D3D3D", width: "640px", maxWidth: "92vw", maxHeight: "90vh", overflowY: "auto", padding: "24px", color: "#FFF" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", paddingBottom: "12px", borderBottom: "1px solid #262626" }}>
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
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
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
                    Node Type
                  </label>
                  <select
                    value={editingNode.type || "message"}
                    onChange={(e) => setEditingNode({ ...editingNode, type: e.target.value })}
                    style={{ width: "100%", padding: "10px 14px", borderRadius: "8px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "14px", outline: "none" }}
                  >
                    <option value="message">Message (Spoken Response)</option>
                    <option value="slot_collection">Slot Qualification</option>
                    <option value="fallback">Clarification / Fallback</option>
                    <option value="end">Conversation End</option>
                  </select>
                </div>
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

              {/* Edit Transitions list */}
              {editingNode.type !== "end" && (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <label style={{ fontSize: "12px", fontWeight: "700", color: "#A3A3A3" }}>
                      Outgoing Transitions
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const target = editableNodes.find(n => n.type === "end")?.id || editableNodes[0]?.id || "";
                        const intent = getUniqueIntent(editingNode.transitions);
                        const label = intent.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                        setEditingNode({
                          ...editingNode,
                          transitions: [...(editingNode.transitions || []), { intent, label, target }]
                        });
                      }}
                      style={{ padding: "3px 8px", borderRadius: "4px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#60A5FA", fontSize: "11px", fontWeight: "700", cursor: "pointer" }}
                    >
                      + Add Transition
                    </button>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {(editingNode.transitions || []).map((t, idx) => (
                      <div key={idx} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 30px", gap: "8px", alignItems: "center" }}>
                        <input
                          type="text"
                          value={t.intent || ""}
                          placeholder="Intent (e.g. confirm)"
                          onChange={(e) => {
                            const updated = [...editingNode.transitions];
                            updated[idx] = { ...updated[idx], intent: e.target.value };
                            setEditingNode({ ...editingNode, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        />
                        <input
                          type="text"
                          value={t.label || ""}
                          placeholder="Label (e.g. Yes)"
                          onChange={(e) => {
                            const updated = [...editingNode.transitions];
                            updated[idx] = { ...updated[idx], label: e.target.value };
                            setEditingNode({ ...editingNode, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        />
                        <select
                          value={t.target || ""}
                          onChange={(e) => {
                            const updated = [...editingNode.transitions];
                            updated[idx] = { ...updated[idx], target: e.target.value };
                            setEditingNode({ ...editingNode, transitions: updated });
                          }}
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "#1E1E22", border: "1px solid #3D3D3D", color: "#FFF", fontSize: "12px" }}
                        >
                          <option value="">-- Target Node --</option>
                          {editableNodes.map(n => (
                            <option key={n.id} value={n.id}>{n.label} ({n.id})</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => {
                            const updated = editingNode.transitions.filter((_, i) => i !== idx);
                            setEditingNode({ ...editingNode, transitions: updated });
                          }}
                          style={{ background: "none", border: "none", color: "#F87171", cursor: "pointer", padding: 0 }}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
