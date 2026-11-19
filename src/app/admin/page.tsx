"use client";

import React from "react";
import { Lock, CheckCircle2 } from "lucide-react";
import { DEMO_ACCOUNTS, useAuth } from "@/context/AuthContext";

export default function AdminPage() {
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin"]);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <Lock className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Administrator Access Required</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          User administration and RBAC role assignment is restricted to administrator credentials.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div className="pb-4 border-b border-[#242429]">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
            Access Control &amp; RBAC Personas
          </h1>
          <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#1a1a1e] text-[#a1a1aa] border border-[#2b2b32]">
            Admin
          </span>
        </div>
        <p className="text-xs text-[#9e9ea7] mt-0.5">
          Configured lakehouse personas, credentials, and least-privilege security boundaries.
        </p>
      </div>

      {/* Users Table */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429]">
          <div className="text-sm font-semibold text-[#f4f4f6]">Configured Security Personas</div>
          <div className="text-[11px] text-[#9e9ea7] mt-0.5">5 distinct roles with scoped API and column access</div>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Persona</th>
                <th>Email Identifier</th>
                <th>Assigned Role</th>
                <th>Access Scope</th>
                <th className="text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_ACCOUNTS.map((acc, idx) => (
                <tr key={idx}>
                  <td className="font-medium text-xs text-[#f4f4f6]">{acc.label}</td>
                  <td className="font-mono text-xs text-[#9e9ea7]">{acc.email}</td>
                  <td>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#141416] text-[#f4f4f6] border border-[#242429]">
                      {acc.role}
                    </span>
                  </td>
                  <td className="text-xs text-[#9e9ea7]">
                    {acc.role === "admin" && "Full administrative control, pipeline triggers, and user access"}
                    {acc.role === "fraud_analyst" && "Fraud review queue, SHAP explanations, manual overrides"}
                    {acc.role === "data_engineer" && "Lineage tracing, Airflow DAG triggers, Data Quality scorecard"}
                    {acc.role === "compliance_auditor" && "PII gate verification, policy audit logs, lineage audit"}
                    {acc.role === "viewer" && "Aggregated KPIs and reports only (Row-level transactions blocked)"}
                  </td>
                  <td className="text-right">
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10b981]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
