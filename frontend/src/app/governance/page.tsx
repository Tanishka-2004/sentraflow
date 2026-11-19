"use client";

import React, { useEffect, useState } from "react";
import { ShieldAlert, CheckCircle2 } from "lucide-react";
import { api, GateAuditRun } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function GovernancePage() {
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "compliance_auditor", "data_engineer"]);

  const [gateRuns, setGateRuns] = useState<GateAuditRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAllowed) return;
    async function loadData() {
      try {
        const runs = await api.getGateRuns();
        setGateRuns(runs);
      } catch (e) {
        console.error("Failed to load gate runs:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [isAllowed]);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <ShieldAlert className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          Governance audit records and cryptographic gate signatures are restricted to compliance auditors, data engineers, and administrators.
        </p>
      </div>
    );
  }

  const policies = [
    { entity: "PAN Card", classification: "PII Direct", technique: "MASK_PARTIAL", rule: "Preserves first 5 letters as XXXXX, reveals last 4" },
    { entity: "Aadhaar ID", classification: "PII Direct", technique: "TOKENIZE_HMAC", rule: "Deterministic HMAC-SHA256 keyed tokenization (joinable)" },
    { entity: "Email Address", classification: "PII Direct", technique: "HASH_EMAIL", rule: "Format-preserving salted SHA-256 hash (h_XXXX@domain)" },
    { entity: "Phone Number", classification: "PII Direct", technique: "MASK_PHONE", rule: "Redacts initial 6 digits as XXXXXX, reveals last 4 digits" },
    { entity: "Date of Birth", classification: "PII Quasi", technique: "GENERALIZE_AGE", rule: "Converts exact birthdate to demographic 5-year age bands" },
    { entity: "Postal Pincode", classification: "PII Quasi", technique: "TRUNCATE_PREFIX", rule: "Truncates 6-digit postal code to first 3 area digits" },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div className="pb-4 border-b border-[#242429]">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
            Data Governance &amp; PII Certification
          </h1>
          <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#13241b] text-[#55ba82] border border-[#1e4730]">
            Zero Leaks
          </span>
        </div>
        <p className="text-xs text-[#9e9ea7] mt-0.5">
          Cryptographically signed automated security audit logs certifying zero raw PII reaches Silver and Gold layers.
        </p>
      </div>

      {/* Gate Audit Log Table */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429] flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[#f4f4f6]">Automated PII Gate Execution Audit Log</div>
            <div className="text-[11px] text-[#9e9ea7] mt-0.5 font-mono">governance.pii_gate_audit</div>
          </div>
          <span className="text-xs font-mono text-[#686873]">KMS HMAC-SHA256</span>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Table Name</th>
                <th>Status</th>
                <th>Records Scanned</th>
                <th>Residual Violations</th>
                <th>Cryptographic Signature</th>
                <th className="text-right">Executed At</th>
              </tr>
            </thead>
            <tbody>
              {gateRuns.map((run, idx) => (
                <tr key={idx}>
                  <td className="font-mono text-xs font-medium text-[#f4f4f6]">{run.batch_id}</td>
                  <td className="text-xs text-[#f4f4f6]">{run.table_name}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10b981]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Passed
                    </span>
                  </td>
                  <td className="font-mono text-xs text-[#9e9ea7]">{run.records_scanned.toLocaleString()}</td>
                  <td className="font-mono text-xs font-semibold text-[#10b981]">{run.residual_pii_count}</td>
                  <td className="font-mono text-[10px] text-[#686873] max-w-xs truncate">{run.signature}</td>
                  <td className="text-right text-[#9e9ea7] font-mono text-[11px]">{new Date(run.executed_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Masking Policies Table */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429] flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[#f4f4f6]">Active Masking &amp; Tokenization Policies</div>
            <div className="text-[11px] text-[#9e9ea7] mt-0.5">Defined in governance/policies.yaml</div>
          </div>
          <span className="text-xs text-[#686873]">RBI DPDP Compliance</span>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Classification Tier</th>
                <th>Technique</th>
                <th>Specification &amp; Transformation Rule</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p, idx) => (
                <tr key={idx}>
                  <td className="font-medium text-[#f4f4f6] text-xs">{p.entity}</td>
                  <td>
                    <span className="text-[11px] font-mono text-[#9e9ea7]">
                      {p.classification}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-[#f4f4f6]">{p.technique}</td>
                  <td className="text-xs text-[#9e9ea7]">{p.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
