"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  LayoutDashboard, 
  ShieldAlert, 
  Database, 
  GitBranch, 
  PlayCircle, 
  UserCheck, 
  TrendingUp, 
  Lock, 
  Settings, 
  FileText, 
  LogOut, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Search, 
  Filter, 
  RefreshCw, 
  ShieldCheck, 
  Info,
  Server,
  Activity,
  Layers
} from "lucide-react";
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, Legend
} from "recharts";
import { ReactFlow, Background, Controls, MiniMap } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const API_BASE = "http://localhost:8000";
const ML_API_BASE = "http://localhost:8001";

export default function SentraFlowApp() {
  // Auth state
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ email: string; role: string } | null>(null);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  
  // Navigation
  const [activeTab, setActiveTab] = useState("dashboard");
  
  // WebSocket state
  const [wsStatus, setWsStatus] = useState("DISCONNECTED");
  const [realtimeAlerts, setRealtimeAlerts] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  
  // Data states
  const [dashboardStats, setDashboardStats] = useState<any>({
    transactions: 0,
    openAlerts: 0,
    dqPassRate: 96.4,
    pipelineSuccess: 98.7,
    p95Latency: 24.1,
    driftPSI: 0.08,
    driftStatus: "stable",
    systemHealth: { api: "Healthy", db: "Healthy", ml: "Healthy", storage: "Healthy" }
  });
  const [transactions, setTransactions] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<any | null>(null);
  const [resolutionReason, setResolutionReason] = useState("");
  const [pipelines, setPipelines] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any | null>(null);
  const [replayReason, setReplayReason] = useState("");
  const [replayStatus, setReplayStatus] = useState<any | null>(null);
  
  // Data Catalog states
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<any | null>(null);
  const [columns, setColumns] = useState<any[]>([]);
  
  // PII Governance states
  const [piiRules, setPiiRules] = useState<any[]>([]);
  const [newRulePattern, setNewRulePattern] = useState("");
  const [newRuleType, setNewRuleType] = useState("regex");
  const [newRuleStrategy, setNewRuleStrategy] = useState("hash");
  
  // Model registry & drift states
  const [models, setModels] = useState<any[]>([]);
  const [driftMetrics, setDriftMetrics] = useState<any[]>([]);
  const [predictionPSI, setPredictionPSI] = useState(0.0);
  
  // Audit log states
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  
  // Admin states
  const [usersList, setUsersList] = useState<any[]>([]);
  const [newUsrEmail, setNewUsrEmail] = useState("");
  const [newUsrPassword, setNewUsrPassword] = useState("");
  const [newUsrRole, setNewUsrRole] = useState("analyst");
  
  // Lineage Graph state
  const [lineageTable, setLineageTable] = useState("fact_transactions");
  const [lineageColumn, setLineageColumn] = useState("transaction_id");
  const [lineageFlow, setLineageFlow] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });

  // Notifications
  const [toast, setToast] = useState<{ message: string; type: "success" | "warning" | "info" } | null>(null);

  // Sync token from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("sf_token");
    const savedUser = localStorage.getItem("sf_user");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
  }, []);

  // Show Toast helper
  const showToast = (message: string, type: "success" | "warning" | "info" = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  // Initialize WebSocket when authenticated
  useEffect(() => {
    if (!token) return;
    
    const connectWS = () => {
      const ws = new WebSocket(`ws://localhost:8000/ws/alerts?token=${token}`);
      wsRef.current = ws;
      setWsStatus("CONNECTING");

      ws.onopen = () => {
        setWsStatus("CONNECTED");
        showToast("Connected to real-time risk notification stream.", "success");
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "NEW_FRAUD_ALERT") {
          showToast(`REAL-TIME ALERT: Fraud risk flagged! Score: ${msg.data.risk_score.toFixed(2)} (${msg.data.risk_level})`, "warning");
          setRealtimeAlerts(prev => [msg.data, ...prev].slice(0, 10));
          // Refresh alerts list if on alerts tab
          fetchAlerts();
          fetchDashboardStats();
        } else if (msg.type === "MODEL_DRIFT_ALERT") {
          showToast(`ALERT: Prediction Drift Detected! PSI: ${msg.data.psi.toFixed(3)}`, "warning");
          fetchModelDrift();
        }
      };

      ws.onclose = () => {
        setWsStatus("DISCONNECTED");
        // Try reconnecting in 5 seconds
        setTimeout(connectWS, 5000);
      };
    };

    connectWS();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [token]);

  // Fetch initial data on auth
  useEffect(() => {
    if (!token) return;
    fetchDashboardStats();
    fetchTransactions();
    fetchAlerts();
    fetchPipelines();
    fetchCatalog();
    fetchPiiRules();
    fetchModelDrift();
    fetchAuditLogs();
    if (user?.role === "admin") {
      fetchUsers();
    }
  }, [token, activeTab]);

  // Fetch lineage when parameters change
  useEffect(() => {
    if (!token) return;
    fetchLineage();
  }, [token, lineageTable, lineageColumn]);

  // API Call helper
  const apiCall = async (endpoint: string, method = "GET", body: any = null) => {
    const headers: any = {
      "Authorization": `Bearer ${token}`
    };
    if (body) {
      headers["Content-Type"] = "application/json";
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null
      });

      if (response.status === 401) {
        handleLogout();
        throw new Error("Session expired.");
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "API call failed");
      }

      return await response.json();
    } catch (e: any) {
      console.error(e);
      showToast(e.message, "warning");
      return null;
    }
  };

  // Data fetching functions
  const fetchDashboardStats = async () => {
    try {
      const health = await fetch(`${API_BASE}/api/health`).then(r => r.json());
      const drift = await fetch(`${ML_API_BASE}/drift`).then(r => r.json());
      const txs = await apiCall("/api/transactions?limit=1");
      const alts = await apiCall("/api/alerts?status=open&limit=1");
      
      setDashboardStats({
        transactions: txs ? txs.total : 1284392,
        openAlerts: alts ? alts.total : 27,
        dqPassRate: health.dq_pass_rate || 96.4,
        pipelineSuccess: health.pipeline_success_rate || 98.7,
        p95Latency: health.p95_latency_ms || 24.1,
        driftPSI: drift ? drift.psi : 0.08,
        driftStatus: drift ? drift.drift_status : "stable",
        systemHealth: health.services || { api: "Healthy", db: "Healthy", ml: "Healthy", storage: "Healthy" }
      });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTransactions = async () => {
    const data = await apiCall("/api/transactions?limit=25");
    if (data) setTransactions(data.transactions);
  };

  const fetchAlerts = async () => {
    const data = await apiCall("/api/alerts?limit=25");
    if (data) setAlerts(data.alerts);
  };

  const fetchPipelines = async () => {
    const data = await apiCall("/api/pipelines/runs?limit=25");
    if (data) setPipelines(data.runs);
  };

  const fetchCatalog = async () => {
    const data = await apiCall("/api/catalog/datasets");
    if (data) {
      setDatasets(data);
      if (data.length > 0 && !selectedDataset) {
        setSelectedDataset(data[0]);
      }
    }
    const cols = await apiCall("/api/catalog/columns");
    if (cols) setColumns(cols);
  };

  const fetchPiiRules = async () => {
    if (user?.role !== "admin") return;
    const data = await apiCall("/api/admin/pii-rules");
    if (data) setPiiRules(data);
  };

  const fetchModelDrift = async () => {
    const data = await apiCall("/api/governance/models");
    if (data) setModels(data);
    
    // Get drift metrics for primary model
    if (data && data.length > 0) {
      const drift = await apiCall(`/api/governance/models/${data[0].model_version}/drift`);
      if (drift) setDriftMetrics(drift);
      
      const mlDrift = await fetch(`${ML_API_BASE}/drift`).then(r => r.json());
      if (mlDrift) setPredictionPSI(mlDrift.psi);
    }
  };

  const fetchAuditLogs = async () => {
    if (user?.role === "analyst") return; // Gated
    const data = await apiCall("/api/audit?limit=25");
    if (data) setAuditLogs(data.logs);
  };

  const fetchUsers = async () => {
    const data = await apiCall("/api/admin/users");
    if (data) setUsersList(data);
  };

  const fetchLineage = async () => {
    const data = await apiCall(`/api/lineage/${lineageTable}/${lineageColumn}`);
    if (data) {
      // Convert API node/edge format to React Flow format with absolute positions
      const flowNodes = data.nodes.map((n: any, idx: number) => ({
        id: n.id,
        data: { label: n.label },
        position: { x: 50 + idx * 250, y: 150 + (idx % 2) * 80 },
        style: { 
          background: n.type === 'column' ? '#1e293b' : '#0f172a',
          color: '#cbd5e1',
          border: n.id.includes(lineageColumn) ? '2px solid #ef4444' : '1px solid #475569',
          borderRadius: '8px',
          padding: '12px',
          fontWeight: '500',
          fontFamily: 'monospace'
        }
      }));
      setLineageFlow({ nodes: flowNodes, edges: data.edges });
    }
  };

  // Actions
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });

      if (!response.ok) {
        throw new Error("Invalid username or password");
      }

      const data = await response.json();
      localStorage.setItem("sf_token", data.access_token);
      
      // Fetch user profiles details
      const userRes = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { "Authorization": `Bearer ${data.access_token}` }
      }).then(r => r.json());

      localStorage.setItem("sf_user", JSON.stringify(userRes));
      
      setToken(data.access_token);
      setUser(userRes);
      showToast(`Welcome back, logged in as ${userRes.role}`, "success");
    } catch (e: any) {
      setLoginError(e.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("sf_token");
    localStorage.removeItem("sf_user");
    setToken(null);
    setUser(null);
    setActiveTab("dashboard");
    if (wsRef.current) wsRef.current.close();
  };

  const handleResolveAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAlert) return;
    
    const data = await apiCall(`/api/alerts/${selectedAlert.id}`, "PATCH", {
      status: "resolved",
      reason: resolutionReason
    });

    if (data) {
      showToast("Alert resolved and audited successfully", "success");
      setSelectedAlert(null);
      setResolutionReason("");
      fetchAlerts();
      fetchDashboardStats();
      fetchAuditLogs();
    }
  };

  const handleTriggerReplay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRun) return;

    setReplayStatus("Triggered...");
    const data = await apiCall(`/api/pipelines/runs/${selectedRun.run_id}/replay`, "POST", {
      reason: replayReason
    });

    if (data) {
      showToast("Pipeline Sandbox Replay initialized successfully", "success");
      setReplayReason("");
      
      // Follow the real-time background task updates
      const interval = setInterval(async () => {
        const check = await apiCall(`/api/pipelines/runs/${data.run_id}`);
        if (check) {
          setReplayStatus(check);
          if (check.status === "success" || check.status === "failed") {
            clearInterval(interval);
            fetchPipelines();
            fetchAuditLogs();
          }
        }
      }, 1500);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    const data = await apiCall("/api/admin/pii-rules", "POST", {
      column_pattern: newRulePattern,
      rule_type: newRuleType,
      masking_strategy: newRuleStrategy
    });

    if (data) {
      showToast("PII Masking rule created successfully", "success");
      setNewRulePattern("");
      fetchPiiRules();
      fetchAuditLogs();
    }
  };

  const handleToggleRule = async (ruleId: int) => {
    const data = await apiCall(`/api/admin/pii-rules/${ruleId}/toggle`, "PATCH");
    if (data) {
      showToast("Rule status toggled.", "success");
      fetchPiiRules();
      fetchAuditLogs();
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const data = await apiCall("/api/admin/users", "POST", {
      email: newUsrEmail,
      password: newUsrPassword,
      role: newUsrRole
    });

    if (data) {
      showToast(`User account created: ${newUsrEmail}`, "success");
      setNewUsrEmail("");
      setNewUsrPassword("");
      fetchUsers();
      fetchAuditLogs();
    }
  };

  // Mock data for graphs if Recharts loads empty
  const timeChartData = [
    { name: "08-08", value: 45000 },
    { name: "08-09", value: 48000 },
    { name: "08-10", value: 52000 },
    { name: "08-11", value: 49000 },
    { name: "08-12", value: 60000 },
    { name: "08-13", value: 55000 },
    { name: "08-14", value: 68000 }
  ];

  const riskDistribution = [
    { name: "LOW", count: 4880, color: "#10b981" },
    { name: "MEDIUM", count: 98, color: "#f59e0b" },
    { name: "HIGH", count: 18, color: "#ef4444" },
    { name: "CRITICAL", count: 4, color: "#7f1d1d" }
  ];

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090d16] text-[#cbd5e1] font-sans p-6">
        <div className="w-full max-w-md bg-[#111827] border border-[#1f2937] rounded-xl p-8 shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <div className="h-12 w-12 bg-red-600/10 border border-red-600/30 rounded-xl flex items-center justify-center text-red-500 mb-4">
              <Activity className="h-6 w-6 animate-pulse" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-wide">SENTRAFLOW</h1>
            <p className="text-sm text-gray-400 mt-1">Fraud Intelligence & Data Lakehouse</p>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-6">
            {loginError && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-sm flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                <span>{loginError}</span>
              </div>
            )}
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Email Address</label>
              <input 
                type="email" 
                required 
                className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500 transition-colors"
                value={loginEmail}
                onChange={e => setLoginEmail(e.target.value)}
                placeholder="analyst@sentraflow.com"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Password</label>
              <input 
                type="password" 
                required 
                className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3 text-white focus:outline-none focus:border-red-500 transition-colors"
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <button 
              type="submit" 
              className="w-full bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-bold py-3 px-4 rounded-lg shadow-lg shadow-red-600/20 transition-all uppercase tracking-wider text-xs"
            >
              Sign In
            </button>
          </form>
          
          <div className="mt-8 text-center text-xs text-gray-500 border-t border-gray-800 pt-6">
            <p className="font-semibold text-gray-400 mb-2">Demo Credentials:</p>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-[#1e293b] py-2 px-1 rounded border border-[#334155]">
                <p className="font-bold text-gray-300">Admin</p>
                <p className="text-[10px] text-gray-400">admin@sentraflow.com / admin</p>
              </div>
              <div className="bg-[#1e293b] py-2 px-1 rounded border border-[#334155]">
                <p className="font-bold text-gray-300">Analyst</p>
                <p className="text-[10px] text-gray-400">analyst@sentraflow.com / analyst</p>
              </div>
              <div className="bg-[#1e293b] py-2 px-1 rounded border border-[#334155]">
                <p className="font-bold text-gray-300">Auditor</p>
                <p className="text-[10px] text-gray-400">auditor@sentraflow.com / auditor</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#090d16] text-[#cbd5e1] font-sans overflow-hidden">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-5 py-4 rounded-xl border shadow-2xl transition-all max-w-md ${
          toast.type === "success" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" :
          toast.type === "warning" ? "bg-red-500/10 border-red-500/30 text-red-400" :
          "bg-blue-500/10 border-blue-500/30 text-blue-400"
        }`}>
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm font-medium">{toast.message}</p>
        </div>
      )}

      {/* Sidebar Navigation */}
      <aside className="w-64 shrink-0 bg-[#0c1220] border-r border-[#1f2937] flex flex-col justify-between h-full">
        <div>
          <div className="flex items-center gap-3 px-6 py-5 border-b border-[#1f2937]">
            <Activity className="h-6 w-6 text-red-500 animate-pulse" />
            <span className="font-bold text-white tracking-wider">SENTRAFLOW</span>
          </div>
          
          <nav className="p-4 space-y-1">
            <button 
              onClick={() => setActiveTab("dashboard")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "dashboard" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <LayoutDashboard className="h-4 w-4" />
              <span>Dashboard</span>
            </button>
            <button 
              onClick={() => setActiveTab("transactions")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "transactions" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <Layers className="h-4 w-4" />
              <span>Transactions</span>
            </button>
            <button 
              onClick={() => setActiveTab("alerts")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all relative ${
                activeTab === "alerts" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <ShieldAlert className="h-4 w-4" />
              <span>Fraud Alerts</span>
              {dashboardStats.openAlerts > 0 && (
                <span className="absolute right-3 bg-red-600 text-white font-bold text-[10px] px-1.5 py-0.5 rounded-full">
                  {dashboardStats.openAlerts}
                </span>
              )}
            </button>
            <button 
              onClick={() => setActiveTab("pipelines")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "pipelines" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <PlayCircle className="h-4 w-4" />
              <span>Pipelines</span>
            </button>
            <button 
              onClick={() => setActiveTab("data-catalog")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "data-catalog" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <Database className="h-4 w-4" />
              <span>Data Catalog</span>
            </button>
            <button 
              onClick={() => setActiveTab("lineage")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "lineage" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <GitBranch className="h-4 w-4" />
              <span>Lineage</span>
            </button>
            <button 
              onClick={() => setActiveTab("pii-governance")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "pii-governance" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <Lock className="h-4 w-4" />
              <span>PII Governance</span>
            </button>
            <button 
              onClick={() => setActiveTab("model-monitoring")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === "model-monitoring" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
              }`}
            >
              <TrendingUp className="h-4 w-4" />
              <span>Model Monitoring</span>
            </button>
            {user?.role !== "analyst" && (
              <button 
                onClick={() => setActiveTab("audit")}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  activeTab === "audit" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
                }`}
              >
                <FileText className="h-4 w-4" />
                <span>Audit Logs</span>
              </button>
            )}
            {user?.role === "admin" && (
              <button 
                onClick={() => setActiveTab("admin")}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  activeTab === "admin" ? "bg-red-600/10 text-red-400 border-l-2 border-red-500 pl-3" : "hover:bg-[#111827] text-gray-400"
                }`}
              >
                <Settings className="h-4 w-4" />
                <span>Admin</span>
              </button>
            )}
          </nav>
        </div>

        {/* User / Session footer */}
        <div className="p-4 border-t border-[#1f2937] bg-[#090d16]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-red-400" />
              <div>
                <p className="text-xs font-semibold text-white truncate max-w-[130px]">{user?.email}</p>
                <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">{user?.role}</p>
              </div>
            </div>
            <button 
              onClick={handleLogout}
              className="text-gray-400 hover:text-red-400 p-1 rounded hover:bg-[#111827]"
              title="Log Out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-[#0c1220] border-b border-[#1f2937] px-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-white capitalize">{activeTab.replace("-", " ")}</h2>
          </div>
          
          <div className="flex items-center gap-6">
            {/* Live Streaming Indicator */}
            <div className="flex items-center gap-2 bg-[#111827] px-3.5 py-1.5 rounded-full border border-[#1f2937] text-xs">
              <span className={`h-2.5 w-2.5 rounded-full ${wsStatus === 'CONNECTED' ? 'bg-emerald-500 animate-ping' : 'bg-red-500'}`} />
              <span className="font-semibold text-gray-300">Live Ingest:</span>
              <span className={`font-bold ${wsStatus === 'CONNECTED' ? 'text-emerald-400' : 'text-red-400'}`}>{wsStatus}</span>
            </div>
            
            {/* Medallion Pipeline pill */}
            <div className="flex items-center gap-2 bg-[#111827] px-3.5 py-1.5 rounded-full border border-[#1f2937] text-xs">
              <Server className="h-3.5 w-3.5 text-red-400" />
              <span className="font-semibold text-gray-300">Warehouse:</span>
              <span className="text-emerald-400 font-bold">ONLINE</span>
            </div>
          </div>
        </header>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-8 bg-[#090d16]">
          
          {/* TAB 1: DASHBOARD */}
          {activeTab === "dashboard" && (
            <div className="space-y-8">
              {/* Metric Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Total Transactions</p>
                    <h3 className="text-2xl font-bold text-white">{dashboardStats.transactions.toLocaleString()}</h3>
                  </div>
                  <div className="h-10 w-10 bg-blue-500/10 rounded-lg flex items-center justify-center text-blue-400">
                    <Database className="h-5 w-5" />
                  </div>
                </div>
                
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Open Fraud Alerts</p>
                    <h3 className="text-2xl font-bold text-red-400">{dashboardStats.openAlerts}</h3>
                  </div>
                  <div className="h-10 w-10 bg-red-500/10 rounded-lg flex items-center justify-center text-red-400">
                    <ShieldAlert className="h-5 w-5" />
                  </div>
                </div>
                
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">DQ Rule Pass Rate</p>
                    <h3 className="text-2xl font-bold text-emerald-400">{dashboardStats.dqPassRate}%</h3>
                  </div>
                  <div className="h-10 w-10 bg-emerald-500/10 rounded-lg flex items-center justify-center text-emerald-400">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                </div>
                
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">DAG Ingest Success</p>
                    <h3 className="text-2xl font-bold text-purple-400">{dashboardStats.pipelineSuccess}%</h3>
                  </div>
                  <div className="h-10 w-10 bg-purple-500/10 rounded-lg flex items-center justify-center text-purple-400">
                    <PlayCircle className="h-5 w-5" />
                  </div>
                </div>
              </div>

              {/* Medallion Pipeline Diagram */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Pipeline Health & Ingest State</h4>
                <div className="grid grid-cols-3 gap-6 relative">
                  <div className="bg-[#111827] border border-emerald-500/20 rounded-lg p-5 flex flex-col items-center relative z-10">
                    <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold px-2 py-0.5 rounded-full mb-3">BRONZE</span>
                    <h5 className="font-bold text-white text-sm">s3://sentraflow-lake/bronze/</h5>
                    <p className="text-xs text-gray-400 mt-2">Clean-up status: Complete</p>
                    <div className="flex items-center gap-2 mt-4 text-emerald-400 font-bold text-xs">
                      <CheckCircle className="h-4 w-4" /> Passed Schema Gate
                    </div>
                  </div>
                  
                  <div className="bg-[#111827] border border-emerald-500/20 rounded-lg p-5 flex flex-col items-center relative z-10">
                    <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold px-2 py-0.5 rounded-full mb-3">SILVER</span>
                    <h5 className="font-bold text-white text-sm">s3://sentraflow-lake/silver/</h5>
                    <p className="text-xs text-gray-400 mt-2">PII Masking status: Enforced</p>
                    <div className="flex items-center gap-2 mt-4 text-emerald-400 font-bold text-xs">
                      <CheckCircle className="h-4 w-4" /> PII Classified & Safe
                    </div>
                  </div>

                  <div className="bg-[#111827] border border-emerald-500/20 rounded-lg p-5 flex flex-col items-center relative z-10">
                    <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold px-2 py-0.5 rounded-full mb-3">GOLD (WAREHOUSE)</span>
                    <h5 className="font-bold text-white text-sm">warehouse.fact_transactions</h5>
                    <p className="text-xs text-gray-400 mt-2"> dbt Models status: Ready</p>
                    <div className="flex items-center gap-2 mt-4 text-emerald-400 font-bold text-xs">
                      <CheckCircle className="h-4 w-4" /> DQ Validation Passed
                    </div>
                  </div>
                </div>
              </div>

              {/* Graphics Area */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Recharts Area for Transaction Flow */}
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg md:col-span-2">
                  <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Transactions Activity (Gold)</h4>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timeChartData}>
                        <defs>
                          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis dataKey="name" stroke="#64748b" />
                        <YAxis stroke="#64748b" />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1f2937', color: '#fff' }} />
                        <Area type="monotone" dataKey="value" stroke="#ef4444" fillOpacity={1} fill="url(#colorValue)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Risk Distribution Breakdown */}
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg">
                  <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Fraud Risk Distribution</h4>
                  <div className="space-y-4">
                    {riskDistribution.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3.5 bg-[#111827] rounded-lg border border-[#1f2937]">
                        <div className="flex items-center gap-3">
                          <span className="h-3.5 w-3.5 rounded-full" style={{ backgroundColor: item.color }} />
                          <span className="font-bold text-white text-xs">{item.name}</span>
                        </div>
                        <span className="text-xs text-gray-400 font-semibold">{item.count} txs</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: TRANSACTIONS */}
          {activeTab === "transactions" && (
            <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
              <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Transactions Audit Trail (Gold fact)</h4>
              
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                      <th className="pb-4">Transaction ID</th>
                      <th className="pb-4">Account ID</th>
                      <th className="pb-4">Date Key</th>
                      <th className="pb-4">Amount (USD)</th>
                      <th className="pb-4">Type</th>
                      <th className="pb-4">Source</th>
                      <th className="pb-4">Risk Score</th>
                      <th className="pb-4">Flagged</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300">
                    {transactions.map((tx, idx) => (
                      <tr key={idx} className="hover:bg-[#111827]/50 transition-colors">
                        <td className="py-4 font-mono font-bold text-white">{tx.transaction_id}</td>
                        <td className="py-4 font-mono">{tx.account_id}</td>
                        <td className="py-4">{tx.date_key}</td>
                        <td className="py-4 font-bold text-white">${Number(tx.amount).toFixed(2)}</td>
                        <td className="py-4 font-mono text-xs">{tx.transaction_type}</td>
                        <td className="py-4 capitalize"><span className={`px-2 py-0.5 rounded text-[10px] font-bold ${tx.source === 'batch' ? 'bg-blue-500/10 text-blue-400' : 'bg-orange-500/10 text-orange-400'}`}>{tx.source}</span></td>
                        <td className="py-4 font-bold">{tx.risk_score.toFixed(3)}</td>
                        <td className="py-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            tx.is_flagged ? "bg-red-500/10 text-red-400" : "bg-emerald-500/10 text-emerald-400"
                          }`}>
                            {tx.is_flagged ? "Flagged" : "Clear"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: FRAUD ALERTS */}
          {activeTab === "alerts" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Alerts Grid */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 lg:col-span-2">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Open Fraud Risk Alerts</h4>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                        <th className="pb-4">Alert ID</th>
                        <th className="pb-4">Transaction ID</th>
                        <th className="pb-4">Risk Score</th>
                        <th className="pb-4">Severity</th>
                        <th className="pb-4">Status</th>
                        <th className="pb-4">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300">
                      {alerts.map((alt, idx) => (
                        <tr key={idx} className="hover:bg-[#111827]/50 transition-colors">
                          <td className="py-4 font-bold text-white">#ALT_{alt.id}</td>
                          <td className="py-4 font-mono">{alt.transaction_id}</td>
                          <td className="py-4 font-bold text-red-400">{alt.risk_score.toFixed(3)}</td>
                          <td className="py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              alt.risk_level === 'CRITICAL' ? 'bg-red-600 text-white' :
                              alt.risk_level === 'HIGH' ? 'bg-red-500/10 text-red-400' :
                              'bg-amber-500/10 text-amber-400'
                            }`}>
                              {alt.risk_level}
                            </span>
                          </td>
                          <td className="py-4 capitalize">{alt.status}</td>
                          <td className="py-4">
                            <button 
                              onClick={() => {
                                setSelectedAlert(alt);
                                setResolutionReason("");
                              }}
                              className="text-xs bg-red-600/10 text-red-400 hover:bg-red-600 hover:text-white px-2.5 py-1 rounded border border-red-500/20 font-bold transition-all"
                            >
                              Investigate
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Investigation Drawer */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Risk Investigation & SHAP</h4>
                {selectedAlert ? (
                  <div className="space-y-6">
                    <div>
                      <h5 className="font-bold text-white">Alert #ALT_{selectedAlert.id}</h5>
                      <p className="text-xs text-gray-400 mt-1">Transaction Natural Key: <span className="font-mono">{selectedAlert.transaction_id}</span></p>
                      <p className="text-xs text-gray-400 mt-1">Risk Score: <span className="text-red-400 font-bold font-mono">{selectedAlert.risk_score.toFixed(3)}</span></p>
                    </div>

                    {/* SHAP Explanations Chart Bar Chart */}
                    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
                      <h6 className="text-[10px] font-bold uppercase text-gray-400 tracking-wider mb-3">Model Attributions (SHAP)</h6>
                      <div className="space-y-3">
                        <div>
                          <div className="flex justify-between text-xs mb-1 font-mono">
                            <span>errorBalanceOrig</span>
                            <span className="text-red-400">+0.25 (Critical)</span>
                          </div>
                          <div className="w-full bg-[#1e293b] h-2 rounded-full overflow-hidden">
                            <div className="bg-red-500 h-full rounded-full" style={{ width: "85%" }} />
                          </div>
                        </div>
                        <div>
                          <div className="flex justify-between text-xs mb-1 font-mono">
                            <span>amount_orig_ratio</span>
                            <span className="text-red-400">+0.15</span>
                          </div>
                          <div className="w-full bg-[#1e293b] h-2 rounded-full overflow-hidden">
                            <div className="bg-red-500 h-full rounded-full" style={{ width: "60%" }} />
                          </div>
                        </div>
                        <div>
                          <div className="flex justify-between text-xs mb-1 font-mono">
                            <span>errorBalanceDest</span>
                            <span className="text-red-400">+0.12</span>
                          </div>
                          <div className="w-full bg-[#1e293b] h-2 rounded-full overflow-hidden">
                            <div className="bg-red-500 h-full rounded-full" style={{ width: "45%" }} />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Resolution Form (restricted to analyst/admin) */}
                    <form onSubmit={handleResolveAlert} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Resolution Note</label>
                        <textarea
                          required
                          rows={3}
                          className="w-full bg-[#1e293b] border border-[#334155] rounded-lg p-3 text-white text-sm focus:outline-none focus:border-red-500 transition-colors"
                          placeholder="Provide auditable justification..."
                          value={resolutionReason}
                          onChange={e => setResolutionReason(e.target.value)}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <button
                          type="submit"
                          className="w-full bg-emerald-600 hover:bg-emerald-700 font-bold py-2 rounded-lg text-xs tracking-wider uppercase text-white shadow-lg shadow-emerald-600/20"
                        >
                          Resolve Alert
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            const data = await apiCall(`/api/alerts/${selectedAlert.id}`, "PATCH", {
                              status: "false_positive",
                              reason: resolutionReason
                            });
                            if (data) {
                              showToast("Alert marked as False Positive", "success");
                              setSelectedAlert(null);
                              setResolutionReason("");
                              fetchAlerts();
                              fetchDashboardStats();
                            }
                          }}
                          className="w-full bg-[#1e293b] border border-[#334155] text-gray-300 hover:bg-[#334155] font-bold py-2 rounded-lg text-xs tracking-wider uppercase"
                        >
                          False Positive
                        </button>
                      </div>
                    </form>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                    <Info className="h-8 w-8 mb-2" />
                    <p className="text-sm">Select an alert to investigate SHAP attributions and resolve.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: PIPELINES */}
          {activeTab === "pipelines" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Pipeline Runs list */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 lg:col-span-2">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Medallion DAG executions</h4>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                        <th className="pb-4">Run ID</th>
                        <th className="pb-4">Pipeline version</th>
                        <th className="pb-4">Code commit</th>
                        <th className="pb-4">Schema v</th>
                        <th className="pb-4">Started At</th>
                        <th className="pb-4">Status</th>
                        <th className="pb-4">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300">
                      {pipelines.map((run, idx) => (
                        <tr key={idx} className="hover:bg-[#111827]/50 transition-colors">
                          <td className="py-4 font-mono font-bold text-white truncate max-w-[150px]">{run.run_id}</td>
                          <td className="py-4 font-mono text-xs">{run.pipeline_version}</td>
                          <td className="py-4 font-mono text-xs">{run.code_version}</td>
                          <td className="py-4 font-mono text-xs">{run.schema_version}</td>
                          <td className="py-4 text-xs">{new Date(run.started_at).toLocaleString()}</td>
                          <td className="py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              run.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' :
                              run.status === 'failed' ? 'bg-red-500/10 text-red-400' :
                              'bg-blue-500/10 text-blue-400'
                            }`}>
                              {run.status}
                            </span>
                          </td>
                          <td className="py-4">
                            <button
                              onClick={() => {
                                setSelectedRun(run);
                                setReplayReason("");
                                setReplayStatus(null);
                              }}
                              className="text-xs bg-[#1e293b] border border-[#334155] text-gray-300 hover:bg-[#334155] px-2 py-1 rounded transition-all"
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Replay / Sandbox detail pane */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Run Phase Status & Sandbox Replay</h4>
                {selectedRun ? (
                  <div className="space-y-6">
                    <div>
                      <h5 className="font-bold text-white font-mono text-sm truncate">{selectedRun.run_id}</h5>
                      <p className="text-xs text-gray-400 mt-1">Started: {new Date(selectedRun.started_at).toLocaleString()}</p>
                    </div>

                    {/* Step-by-Step Medallion Checkpoints */}
                    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-4 space-y-4">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-gray-400">Bronze Phase Ingestion</span>
                        <span className={`font-bold capitalize ${selectedRun.bronze_status === 'success' ? 'text-emerald-400' : selectedRun.bronze_status === 'failed' ? 'text-red-400' : 'text-gray-400'}`}>{selectedRun.bronze_status}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-gray-400">Silver Phase Transformation</span>
                        <span className={`font-bold capitalize ${selectedRun.silver_status === 'success' ? 'text-emerald-400' : selectedRun.silver_status === 'failed' ? 'text-red-400' : 'text-gray-400'}`}>{selectedRun.silver_status}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-gray-400">PII Gate Shield Status</span>
                        <span className={`font-bold capitalize ${selectedRun.pii_status === 'success' ? 'text-emerald-400' : selectedRun.pii_status === 'failed_closed' ? 'text-red-500 font-extrabold' : 'text-gray-400'}`}>{selectedRun.pii_status}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-gray-400">Data Quality (dbt test)</span>
                        <span className={`font-bold capitalize ${selectedRun.dq_status === 'success' ? 'text-emerald-400' : selectedRun.dq_status === 'failed' ? 'text-red-400' : 'text-gray-400'}`}>{selectedRun.dq_status}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-gray-400">Gold Warehouse Load</span>
                        <span className={`font-bold capitalize ${selectedRun.gold_status === 'success' ? 'text-emerald-400' : selectedRun.gold_status === 'failed' ? 'text-red-400' : 'text-gray-400'}`}>{selectedRun.gold_status}</span>
                      </div>
                    </div>

                    {/* Replay action */}
                    {user?.role === "admin" && (
                      <form onSubmit={handleTriggerReplay} className="space-y-4 pt-4 border-t border-[#1f2937]">
                        <h6 className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Trigger Sandbox Replay</h6>
                        <input
                          required
                          type="text"
                          className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-red-500 transition-colors"
                          placeholder="Reason for replay debugging..."
                          value={replayReason}
                          onChange={e => setReplayReason(e.target.value)}
                        />
                        <button
                          type="submit"
                          disabled={replayStatus && replayStatus.status === "running"}
                          className="w-full bg-red-600 hover:bg-red-700 disabled:bg-gray-700 font-bold py-2 rounded-lg text-xs tracking-wider uppercase text-white shadow-lg shadow-red-600/20 transition-all"
                        >
                          Replay Failure in Sandbox
                        </button>
                      </form>
                    )}

                    {/* Replay progress status */}
                    {replayStatus && (
                      <div className="bg-[#111827] border border-red-500/20 rounded-lg p-4 text-xs font-mono text-red-400">
                        <p className="font-bold text-white mb-2">Sandbox Replay Execution Log:</p>
                        <p>Bronze Status: {replayStatus.bronze_status}</p>
                        <p>Silver Status: {replayStatus.silver_status}</p>
                        <p>PII Gate: {replayStatus.pii_status}</p>
                        <p>dbt Test status: {replayStatus.dq_status}</p>
                        <p>Gold Load: {replayStatus.gold_status}</p>
                        <p className="font-bold mt-2">Overall: {replayStatus.status}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                    <Info className="h-8 w-8 mb-2" />
                    <p className="text-sm">Select a pipeline run to inspect medallions checkpoints and trigger replay.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: DATA CATALOG */}
          {activeTab === "data-catalog" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Dataset list */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 lg:col-span-1">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Catalog Datasets</h4>
                <div className="space-y-4">
                  {datasets.map((dataset, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedDataset(dataset)}
                      className={`w-full text-left p-4 rounded-lg border transition-all ${
                        selectedDataset?.id === dataset.id ? "bg-red-600/10 border-red-500 text-white" : "bg-[#111827] border-[#1f2937] hover:bg-[#111827]/70 text-gray-300"
                      }`}
                    >
                      <h5 className="font-bold text-sm font-mono">{dataset.name}</h5>
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{dataset.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Schema explorer */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 lg:col-span-2">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Schema & Sensitivity Metadata</h4>
                {selectedDataset ? (
                  <div className="space-y-6">
                    <div>
                      <h5 className="font-bold text-white text-base font-mono">{selectedDataset.name}</h5>
                      <p className="text-sm text-gray-400 mt-2">{selectedDataset.description}</p>
                      <div className="grid grid-cols-2 gap-4 mt-4 text-xs font-mono bg-[#111827] p-3 rounded-lg border border-[#1f2937]">
                        <p><span className="text-gray-400">Data Owner:</span> {selectedDataset.owner}</p>
                        <p><span className="text-gray-400">Storage Location:</span> {selectedDataset.storage_path}</p>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                            <th className="pb-4">Column Name</th>
                            <th className="pb-4">Data Type</th>
                            <th className="pb-4">PII</th>
                            <th className="pb-4">Sensitivity</th>
                            <th className="pb-4">Masking Strategy</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300 font-mono">
                          {columns.filter(c => c.dataset_id === selectedDataset.id).map((col, idx) => (
                            <tr key={idx}>
                              <td className="py-4 text-white font-bold">{col.name}</td>
                              <td className="py-4 text-xs">{col.data_type}</td>
                              <td className="py-4">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  col.is_pii ? "bg-red-500/10 text-red-400" : "bg-gray-800 text-gray-500"
                                }`}>
                                  {col.is_pii ? "PII" : "No"}
                                </span>
                              </td>
                              <td className="py-4 capitalize">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  col.sensitivity === 'critical' ? 'bg-red-600 text-white' :
                                  col.sensitivity === 'high' ? 'bg-red-500/10 text-red-400' :
                                  col.sensitivity === 'medium' ? 'bg-amber-500/10 text-amber-400' :
                                  'bg-gray-800 text-gray-400'
                                }`}>
                                  {col.sensitivity}
                                </span>
                              </td>
                              <td className="py-4 capitalize font-semibold">{col.masking_strategy}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                    <Info className="h-8 w-8 mb-2" />
                    <p className="text-sm">Select a dataset to view column details.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 6: LINEAGE */}
          {activeTab === "lineage" && (
            <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 flex flex-col h-[calc(100vh-200px)]">
              <div className="flex gap-6 mb-6 items-center shrink-0">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider">Recursive Column Lineage</h4>
                
                {/* Search / Target selects */}
                <div className="flex gap-4 items-center">
                  <span className="text-xs text-gray-400 font-semibold font-mono">Target Column:</span>
                  <select
                    className="bg-[#1e293b] border border-[#334155] text-white text-xs px-3 py-1.5 rounded focus:outline-none"
                    value={lineageTable}
                    onChange={e => setLineageTable(e.target.value)}
                  >
                    <option value="fact_transactions">fact_transactions</option>
                    <option value="dim_customer">dim_customer</option>
                  </select>
                  <select
                    className="bg-[#1e293b] border border-[#334155] text-white text-xs px-3 py-1.5 rounded focus:outline-none"
                    value={lineageColumn}
                    onChange={e => setLineageColumn(e.target.value)}
                  >
                    {lineageTable === "fact_transactions" ? (
                      <>
                        <option value="transaction_id">transaction_id</option>
                        <option value="account_id">account_id</option>
                        <option value="amount">amount</option>
                        <option value="transaction_type">transaction_type</option>
                      </>
                    ) : (
                      <>
                        <option value="first_name">first_name</option>
                        <option value="last_name">last_name</option>
                        <option value="email">email</option>
                        <option value="phone">phone</option>
                      </>
                    )}
                  </select>
                </div>
              </div>

              {/* React Flow Lineage Graph Canvas */}
              <div className="flex-1 bg-[#090d16] border border-[#1f2937] rounded-lg overflow-hidden relative">
                <ReactFlow 
                  nodes={lineageFlow.nodes} 
                  edges={lineageFlow.edges}
                  fitView
                >
                  <Background color="#334155" gap={16} />
                  <Controls />
                  <MiniMap nodeStrokeColor="#475569" nodeColor="#1e293b" />
                </ReactFlow>
              </div>
            </div>
          )}

          {/* TAB 7: PII GOVERNANCE */}
          {activeTab === "pii-governance" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Active Rules list */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6 lg:col-span-2">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Active PII Classification Rules</h4>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                        <th className="pb-4">Pattern ID</th>
                        <th className="pb-4">Column Pattern</th>
                        <th className="pb-4">Detection Method</th>
                        <th className="pb-4">Masking Strategy</th>
                        <th className="pb-4">Active</th>
                        {user?.role === "admin" && <th className="pb-4">Toggle</th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300 font-mono">
                      {piiRules.map((rule, idx) => (
                        <tr key={idx} className="hover:bg-[#111827]/50 transition-colors">
                          <td className="py-4 text-white">#PII_{rule.id}</td>
                          <td className="py-4 font-bold text-red-400">{rule.column_pattern}</td>
                          <td className="py-4 capitalize">{rule.rule_type}</td>
                          <td className="py-4 capitalize">{rule.masking_strategy}</td>
                          <td className="py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              rule.active ? "bg-emerald-500/10 text-emerald-400" : "bg-gray-800 text-gray-500"
                            }`}>
                              {rule.active ? "Active" : "Disabled"}
                            </span>
                          </td>
                          {user?.role === "admin" && (
                            <td className="py-4">
                              <button 
                                onClick={() => handleToggleRule(rule.id)}
                                className="text-xs bg-[#1e293b] border border-[#334155] text-gray-300 hover:bg-[#334155] px-2 py-1 rounded transition-all"
                              >
                                Toggle
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Add rule form */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Register PII Masking Rule</h4>
                {user?.role === "admin" ? (
                  <form onSubmit={handleCreateRule} className="space-y-6">
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Column name Pattern (SQL wildcard)</label>
                      <input
                        required
                        type="text"
                        className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-red-500 transition-colors font-mono"
                        placeholder="%credit_card%"
                        value={newRulePattern}
                        onChange={e => setNewRulePattern(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Classification Method</label>
                      <select
                        className="w-full bg-[#1e293b] border border-[#334155] text-white rounded-lg px-4 py-3 text-sm focus:outline-none"
                        value={newRuleType}
                        onChange={e => setNewRuleType(e.target.value)}
                      >
                        <option value="regex">Regex Bank Match</option>
                        <option value="classifier">Entropy Heuristics Classifier</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Masking Strategy</label>
                      <select
                        className="w-full bg-[#1e293b] border border-[#334155] text-white rounded-lg px-4 py-3 text-sm focus:outline-none"
                        value={newRuleStrategy}
                        onChange={e => setNewRuleStrategy(e.target.value)}
                      >
                        <option value="hash">SHA-256 Hash</option>
                        <option value="redact">Partial Redaction (X*****X)</option>
                        <option value="tokenize">Reversible Tokenization (TOK_XXX)</option>
                      </select>
                    </div>
                    <button
                      type="submit"
                      className="w-full bg-red-600 hover:bg-red-700 font-bold py-3 rounded-lg text-xs tracking-wider uppercase text-white shadow-lg shadow-red-600/20"
                    >
                      Deploy Masking Rule
                    </button>
                  </form>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                    <Lock className="h-8 w-8 mb-2" />
                    <p className="text-sm">Admin access required to create PII Masking rules.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 8: MODEL MONITORING */}
          {activeTab === "model-monitoring" && (
            <div className="space-y-8">
              {/* registered models table */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Model Registry</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                        <th className="pb-4">Model Version</th>
                        <th className="pb-4">Training Dataset</th>
                        <th className="pb-4">Feature Set</th>
                        <th className="pb-4">Precision</th>
                        <th className="pb-4">Recall</th>
                        <th className="pb-4">F1 Score</th>
                        <th className="pb-4">ROC-AUC</th>
                        <th className="pb-4">Deploy Status</th>
                        <th className="pb-4">Drift Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300 font-mono">
                      {models.map((model, idx) => (
                        <tr key={idx}>
                          <td className="py-4 font-bold text-white">{model.model_version}</td>
                          <td className="py-4 text-xs">{model.training_dataset_version}</td>
                          <td className="py-4 text-xs">{model.feature_version}</td>
                          <td className="py-4 font-bold">{model.precision}</td>
                          <td className="py-4 font-bold">{model.recall}</td>
                          <td className="py-4 font-bold">{model.f1}</td>
                          <td className="py-4 font-bold text-emerald-400">{model.roc_auc}</td>
                          <td className="py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              model.status === 'production' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-800 text-gray-500'
                            }`}>
                              {model.status}
                            </span>
                          </td>
                          <td className="py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              model.drift_status === 'stable' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                            }`}>
                              {model.drift_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Data/Model Drift Monitoring metrics */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg md:col-span-2">
                  <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Population Stability Index (PSI) Drift Track</h4>
                  
                  {/* Mock live PSI stats */}
                  <div className="flex gap-8 mb-6 items-center">
                    <div className="bg-[#111827] border border-[#1f2937] p-4 rounded-lg">
                      <p className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Live PSI Calculation</p>
                      <h5 className={`text-2xl font-bold mt-1 ${predictionPSI > 0.2 ? 'text-red-400 animate-pulse' : predictionPSI > 0.1 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {predictionPSI.toFixed(3)}
                      </h5>
                    </div>
                    <div className="text-xs space-y-1">
                      <p className="font-semibold"><span className="text-gray-400">Status:</span> <span className={predictionPSI > 0.2 ? 'text-red-400 font-bold' : 'text-emerald-400 font-bold'}>{predictionPSI > 0.2 ? 'DRIFT WARNING' : 'HEALTHY'}</span></p>
                      <p className="text-gray-400">PSI threshold: &lt; 0.1 stable, &gt; 0.2 significant shift</p>
                    </div>
                  </div>

                  <div className="h-64 flex items-end justify-between px-6 pt-4 bg-[#111827] rounded-lg border border-[#1f2937]">
                    {/* Visualizing buckets */}
                    {[0.02, 0.04, 0.05, 0.08, 0.03, 0.12, 0.06, 0.04, 0.03, 0.02].map((v, idx) => (
                      <div key={idx} className="flex flex-col items-center flex-1 space-y-2">
                        <div className="w-8 bg-red-600/30 hover:bg-red-600/50 rounded-t transition-all relative group" style={{ height: `${v * 1200}px` }}>
                          <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[9px] bg-slate-900 border border-slate-700 px-1 py-0.5 rounded hidden group-hover:block font-mono text-white">{(v*100).toFixed(0)}%</span>
                        </div>
                        <span className="text-[9px] font-mono text-gray-500 font-bold">B{idx+1}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-6 shadow-lg">
                  <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Model Feature Importances</h4>
                  <div className="space-y-4 font-mono text-xs">
                    {[
                      { name: "errorBalanceOrig", value: "31.2%" },
                      { name: "amount_orig_ratio", value: "19.5%" },
                      { name: "errorBalanceDest", value: "15.4%" },
                      { name: "amount_dest_ratio", value: "12.0%" },
                      { name: "type_TRANSFER", value: "8.1%" }
                    ].map((item, idx) => (
                      <div key={idx} className="flex justify-between items-center p-3 bg-[#111827] rounded border border-[#1f2937]">
                        <span className="font-semibold text-gray-300">{item.name}</span>
                        <span className="font-bold text-white">{item.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 9: AUDIT LOGS */}
          {activeTab === "audit" && (
            <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
              <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Platform Mutation Audit Logs (Immutable)</h4>
              
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                      <th className="pb-4">Audit ID</th>
                      <th className="pb-4">Timestamp</th>
                      <th className="pb-4">Actor ID</th>
                      <th className="pb-4">Action</th>
                      <th className="pb-4">Resource</th>
                      <th className="pb-4">Reason / Notes</th>
                      <th className="pb-4">IP Address</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300 font-mono">
                    {auditLogs.map((log, idx) => (
                      <tr key={idx} className="hover:bg-[#111827]/50 transition-colors">
                        <td className="py-4 font-bold text-white">#AUD_{log.id}</td>
                        <td className="py-4 text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                        <td className="py-4">User #{log.actor_id}</td>
                        <td className="py-4 font-bold text-red-400">{log.action}</td>
                        <td className="py-4 text-xs capitalize">{log.resource}</td>
                        <td className="py-4 max-w-[200px] truncate text-gray-400" title={log.reason}>{log.reason}</td>
                        <td className="py-4 text-xs text-gray-500">{log.ip_address}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 10: ADMIN */}
          {activeTab === "admin" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Create platform user */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Register Platform User</h4>
                <form onSubmit={handleCreateUser} className="space-y-6">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Email Address</label>
                    <input
                      required
                      type="email"
                      className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-red-500 transition-colors"
                      placeholder="user@sentraflow.com"
                      value={newUsrEmail}
                      onChange={e => setNewUsrEmail(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Password</label>
                    <input
                      required
                      type="password"
                      className="w-full bg-[#1e293b] border border-[#334155] rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-red-500 transition-colors"
                      placeholder="••••••••"
                      value={newUsrPassword}
                      onChange={e => setNewUsrPassword(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Access Role</label>
                    <select
                      className="w-full bg-[#1e293b] border border-[#334155] text-white rounded-lg px-4 py-3 text-sm focus:outline-none"
                      value={newUsrRole}
                      onChange={e => setNewUsrRole(e.target.value)}
                    >
                      <option value="analyst">Analyst</option>
                      <option value="auditor">Auditor (Compliance)</option>
                      <option value="admin">Platform Admin</option>
                    </select>
                  </div>
                  <button
                    type="submit"
                    className="w-full bg-red-600 hover:bg-red-700 font-bold py-3 rounded-lg text-xs tracking-wider uppercase text-white shadow-lg shadow-red-600/20"
                  >
                    Provision Account
                  </button>
                </form>
              </div>

              {/* User management list */}
              <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl shadow-lg p-6">
                <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-6">Active Platform Users</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#1f2937] text-xs text-gray-400 font-semibold uppercase tracking-wider">
                        <th className="pb-4">User ID</th>
                        <th className="pb-4">Email</th>
                        <th className="pb-4">Role</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-sm text-gray-300 font-mono">
                      {usersList.map((usr, idx) => (
                        <tr key={idx}>
                          <td className="py-4 text-white">#USR_{usr.id}</td>
                          <td className="py-4 font-bold">{usr.email}</td>
                          <td className="py-4 uppercase text-xs font-bold text-gray-400">{usr.role}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
