"use client";

import React, { useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  ShieldAlert,
  Info,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface NodeDetail {
  id: string;
  title: string;
  layer: "BRONZE" | "GATE" | "SILVER" | "GOLD";
  table: string;
  column: string;
  piiStatus: string;
  piiSeverity: "HIGH_RISK" | "GATEWAY" | "MASKED_SAFE" | "ANALYTICAL";
  maskingRule: string;
  gatePassed: boolean;
  upstream: string[];
  downstream: string[];
  complianceNote: string;
}

const NODE_DETAILS: Record<string, NodeDetail> = {
  "bronze.customers.pan": {
    id: "bronze.customers.pan",
    title: "Customer PAN Number",
    layer: "BRONZE",
    table: "bronze.customers",
    column: "pan",
    piiStatus: "Direct PII (Restricted)",
    piiSeverity: "HIGH_RISK",
    maskingRule: "Unmasked in raw landing (KMS SSE-S3 encrypted)",
    gatePassed: true,
    upstream: ["landing/customers/batch_id=batch_prod_001/customers.parquet"],
    downstream: ["gate.pii_masking_gate"],
    complianceNote: "Blocked from Silver promotion without regex conformance & 5-char mask.",
  },
  "bronze.customers.email": {
    id: "bronze.customers.email",
    title: "Customer Email Address",
    layer: "BRONZE",
    table: "bronze.customers",
    column: "email",
    piiStatus: "Direct PII (Contact Identity)",
    piiSeverity: "HIGH_RISK",
    maskingRule: "Raw RFC 5322 string in Bronze (Audited & quarantined if malformed)",
    gatePassed: true,
    upstream: ["landing/customers/batch_id=batch_prod_001/customers.parquet"],
    downstream: ["gate.pii_masking_gate"],
    complianceNote: "Requires salted SHA-256 format-preserving pseudonymization.",
  },
  "bronze.txns.amount": {
    id: "bronze.txns.amount",
    title: "Raw Transaction Amount",
    layer: "BRONZE",
    table: "bronze.transactions",
    column: "amount",
    piiStatus: "Non-PII Metric",
    piiSeverity: "ANALYTICAL",
    maskingRule: "Direct pass-through with positive float validation",
    gatePassed: true,
    upstream: ["landing/transactions/batch_id=batch_prod_001/transactions.parquet"],
    downstream: ["silver.txns.amount"],
    complianceNote: "Reconciled with 0.00% variance tolerance via dbt singular test.",
  },
  "gate.pii_masking_gate": {
    id: "gate.pii_masking_gate",
    title: "PII Governance Hard Gate",
    layer: "GATE",
    table: "governance.pii_gate_audit",
    column: "all_sensitive_columns",
    piiStatus: "Central Security Gate (Zero Leakage Check)",
    piiSeverity: "GATEWAY",
    maskingRule: "HMAC-SHA256 Tokenization, Partial Masking, Salted Hash",
    gatePassed: true,
    upstream: ["bronze.customers.pan", "bronze.customers.email"],
    downstream: ["silver.customers.pan_masked", "silver.customers.email_masked"],
    complianceNote: "Fails pipeline execution if unmasked PII reaches Silver layer.",
  },
  "silver.customers.pan_masked": {
    id: "silver.customers.pan_masked",
    title: "Conformed Masked PAN",
    layer: "SILVER",
    table: "silver.customers",
    column: "pan_masked",
    piiStatus: "Pseudonymized (RBI DPDP Compliant)",
    piiSeverity: "MASKED_SAFE",
    maskingRule: "XXXXX + Last 4 Digits + HMAC Checksum",
    gatePassed: true,
    upstream: ["gate.pii_masking_gate"],
    downstream: ["gold.mart_customer_360.pan_masked"],
    complianceNote: "Meets RBI DPDP Act 2023 pseudonymization standards.",
  },
  "silver.customers.email_masked": {
    id: "silver.customers.email_masked",
    title: "Pseudonymized Customer Email",
    layer: "SILVER",
    table: "silver.customers",
    column: "email_masked",
    piiStatus: "Format-Preserving Hashed",
    piiSeverity: "MASKED_SAFE",
    maskingRule: "h_<salted_sha256_prefix>@domain.com",
    gatePassed: true,
    upstream: ["gate.pii_masking_gate"],
    downstream: ["gold.mart_customer_360.email_masked"],
    complianceNote: "Irreversible without corporate KMS key; joinable across domains.",
  },
  "silver.txns.amount": {
    id: "silver.txns.amount",
    title: "Conformed Transaction Amount",
    layer: "SILVER",
    table: "silver.transactions",
    column: "amount",
    piiStatus: "Financial Metric",
    piiSeverity: "ANALYTICAL",
    maskingRule: "Currency normalization & 2 decimal places fixed precision",
    gatePassed: true,
    upstream: ["bronze.txns.amount"],
    downstream: ["gold.mart_daily_spend.total_spend"],
    complianceNote: "Input to XGBoost fraud velocity feature store.",
  },
  "gold.mart_customer_360": {
    id: "gold.mart_customer_360",
    title: "Customer 360 Dimension Mart",
    layer: "GOLD",
    table: "gold.dim_customers",
    column: "full_dimension_row",
    piiStatus: "Analytical Store",
    piiSeverity: "ANALYTICAL",
    maskingRule: "Contains zero raw PII attributes; only pseudonymized tokens",
    gatePassed: true,
    upstream: ["silver.customers.pan_masked", "silver.customers.email_masked"],
    downstream: ["PowerBI Dashboard", "Risk Reporting API"],
    complianceNote: "Accessible to business analysts with RBAC role filtering.",
  },
  "gold.mart_daily_spend": {
    id: "gold.mart_daily_spend",
    title: "Daily Spend Summary Mart",
    layer: "GOLD",
    table: "gold.fct_daily_spend",
    column: "aggregated_metrics",
    piiStatus: "Aggregated KPI Store",
    piiSeverity: "ANALYTICAL",
    maskingRule: "Customer ID pseudonymized; financial rollups summed",
    gatePassed: true,
    upstream: ["silver.txns.amount"],
    downstream: ["Executive KPI Cockpit", "Finance General Ledger"],
    complianceNote: "Reconciled against bank core ledger daily at 00:05 UTC.",
  },
};

export default function LineagePage() {
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "data_engineer", "compliance_auditor"]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("gate.pii_masking_gate");

  const initialNodes: Node[] = [
    // Bronze Layer
    { id: "bronze.customers.pan", position: { x: 50, y: 100 }, data: { label: "bronze.customers.pan\n[Raw Direct PII]" }, style: { background: "#1f1416", color: "#e06677", border: "1px solid #5c212a", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },
    { id: "bronze.customers.email", position: { x: 50, y: 220 }, data: { label: "bronze.customers.email\n[Raw Direct PII]" }, style: { background: "#1f1416", color: "#e06677", border: "1px solid #5c212a", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },
    { id: "bronze.txns.amount", position: { x: 50, y: 340 }, data: { label: "bronze.transactions.amount\n[Metric]" }, style: { background: "#1c1c20", color: "#f4f4f6", border: "1px solid #33333d", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },

    // Governance Hard Gate
    {
      id: "gate.pii_masking_gate",
      position: { x: 350, y: 140 },
      data: { label: "PII GOVERNANCE GATE\n[Zero Leaks Check]" },
      style: { background: "#13241b", color: "#55ba82", border: "1px solid #1e4730", borderRadius: 8, padding: 14, fontWeight: "600", fontSize: 12, textAlign: "center" as const },
    },

    // Silver Conformed
    { id: "silver.customers.pan_masked", position: { x: 650, y: 100 }, data: { label: "silver.customers.pan_masked\n[Conformed Mask]" }, style: { background: "#18181c", color: "#9e9ea7", border: "1px solid #2e2e36", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },
    { id: "silver.customers.email_masked", position: { x: 650, y: 220 }, data: { label: "silver.customers.email_masked\n[Salted Hash]" }, style: { background: "#18181c", color: "#9e9ea7", border: "1px solid #2e2e36", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },
    { id: "silver.txns.amount", position: { x: 650, y: 340 }, data: { label: "silver.transactions.amount\n[Cleaned Metric]" }, style: { background: "#18181c", color: "#9e9ea7", border: "1px solid #2e2e36", borderRadius: 6, padding: 10, fontSize: 11, fontFamily: "monospace" } },

    // Gold Marts
    { id: "gold.mart_customer_360", position: { x: 960, y: 150 }, data: { label: "gold.mart_customer_360\n[Customer Dimension]" }, style: { background: "#141418", color: "#f4f4f6", border: "1px solid #383845", borderRadius: 6, padding: 12, fontWeight: "500", fontSize: 11, fontFamily: "monospace" } },
    { id: "gold.mart_daily_spend", position: { x: 960, y: 300 }, data: { label: "gold.mart_daily_spend\n[Spend Aggregates]" }, style: { background: "#141418", color: "#f4f4f6", border: "1px solid #383845", borderRadius: 6, padding: 12, fontWeight: "500", fontSize: 11, fontFamily: "monospace" } },
  ];

  const initialEdges = [
    { id: "e1", source: "bronze.customers.pan", target: "gate.pii_masking_gate", animated: false, style: { stroke: "#c8102e", strokeWidth: 1.5 } },
    { id: "e2", source: "bronze.customers.email", target: "gate.pii_masking_gate", animated: false, style: { stroke: "#c8102e", strokeWidth: 1.5 } },
    { id: "e3", source: "bronze.txns.amount", target: "silver.txns.amount", animated: false, style: { stroke: "#4a4a52", strokeWidth: 1 } },
    { id: "e4", source: "gate.pii_masking_gate", target: "silver.customers.pan_masked", animated: false, style: { stroke: "#10b981", strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" } },
    { id: "e5", source: "gate.pii_masking_gate", target: "silver.customers.email_masked", animated: false, style: { stroke: "#10b981", strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" } },
    { id: "e6", source: "silver.customers.pan_masked", target: "gold.mart_customer_360", animated: false, style: { stroke: "#4a4a52", strokeWidth: 1 } },
    { id: "e7", source: "silver.customers.email_masked", target: "gold.mart_customer_360", animated: false, style: { stroke: "#4a4a52", strokeWidth: 1 } },
    { id: "e8", source: "silver.txns.amount", target: "gold.mart_daily_spend", animated: false, style: { stroke: "#4a4a52", strokeWidth: 1 } },
  ];

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <ShieldAlert className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          Lineage Explorer requires data engineer, compliance auditor, or administrator permissions.
        </p>
      </div>
    );
  }

  const selectedNode = NODE_DETAILS[selectedNodeId] || NODE_DETAILS["gate.pii_masking_gate"];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#242429]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
              Column-Level Lineage
            </h1>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#13241b] text-[#55ba82] border border-[#1e4730]">
              Zero-Bypass Verified
            </span>
          </div>
          <p className="text-xs text-[#9e9ea7] mt-0.5">
            Trace source parquet attributes through PII transformation gates into Gold star schema marts.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-[#9e9ea7]">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#c8102e]" />
            <span>Raw Bronze</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#10b981]" />
            <span>PII Gate</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#686873]" />
            <span>Silver Conformed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#a1a1aa]" />
            <span>Gold Marts</span>
          </div>
        </div>
      </div>

      {/* React Flow Container */}
      <div className="panel-card h-[460px] w-full overflow-hidden relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={(_, node: Node) => setSelectedNodeId(node.id)}
          fitView
        >
          <Background color="#1e1e24" gap={20} />
          <Controls className="bg-[#1a1a1e] border-[#2b2b32] text-white fill-white" />
          <MiniMap
            nodeColor={(n) => {
              if (n.id.includes("gate")) return "#10b981";
              if (n.id.includes("bronze")) return "#c8102e";
              return "#4a4a52";
            }}
            className="bg-[#141416] border border-[#242429] rounded"
          />
        </ReactFlow>

        <div className="absolute top-3 left-3 bg-[#141416]/95 border border-[#242429] px-2.5 py-1 rounded text-[11px] text-[#9e9ea7] pointer-events-none flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-[#686873]" />
          <span>Click any node to inspect governance specifications</span>
        </div>
      </div>

      {/* Selected Node Governance Inspector */}
      {selectedNode && (
        <div className="panel-card p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#242429]">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[#f4f4f6]">{selectedNode.title}</span>
                <span className="font-mono text-[11px] bg-[#141416] text-[#9e9ea7] border border-[#242429] px-2 py-0.5 rounded">
                  {selectedNode.id}
                </span>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-[#1a1a1e] text-[#a1a1aa] border border-[#2b2b32]">
                  Layer: {selectedNode.layer}
                </span>
              </div>
              <p className="text-xs text-[#686873] mt-1 font-mono">
                Table: {selectedNode.table} • Column: {selectedNode.column}
              </p>
            </div>

            <div className="text-xs text-[#10b981] flex items-center gap-1.5 font-medium">
              <CheckCircle2 className="w-4 h-4" />
              <span>Gate Compliant</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3 bg-[#141416] border border-[#242429] rounded-md">
              <div className="text-[10px] text-[#686873] uppercase font-semibold mb-1">Classification</div>
              <div className="text-[#f4f4f6] font-medium">{selectedNode.piiStatus}</div>
            </div>

            <div className="p-3 bg-[#141416] border border-[#242429] rounded-md">
              <div className="text-[10px] text-[#686873] uppercase font-semibold mb-1">Masking Engine Rule</div>
              <div className="text-[#f4f4f6] font-mono text-[11px]">{selectedNode.maskingRule}</div>
            </div>

            <div className="p-3 bg-[#141416] border border-[#242429] rounded-md">
              <div className="text-[10px] text-[#686873] uppercase font-semibold mb-1">Compliance Requirement</div>
              <div className="text-[#9e9ea7]">{selectedNode.complianceNote}</div>
            </div>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-[#686873] border-t border-[#242429]">
            <div className="flex items-center gap-2">
              <span className="font-medium text-[#9e9ea7]">Upstream:</span>
              <div className="flex flex-wrap gap-1">
                {selectedNode.upstream.map((src, i) => (
                  <span key={i} className="font-mono text-[10px] bg-[#141416] text-[#9e9ea7] px-1.5 py-0.5 rounded border border-[#242429]">
                    {src}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-medium text-[#9e9ea7]">Downstream:</span>
              <div className="flex flex-wrap gap-1">
                {selectedNode.downstream.map((dst, i) => (
                  <span key={i} className="font-mono text-[10px] bg-[#141416] text-[#9e9ea7] px-1.5 py-0.5 rounded border border-[#242429]">
                    {dst}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
