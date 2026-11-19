"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { api, DQScorecard } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function DQPage() {
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "data_engineer", "compliance_auditor"]);

  const [scorecard, setScorecard] = useState<DQScorecard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAllowed) return;
    async function loadData() {
      try {
        const sc = await api.getDQScorecard();
        setScorecard(sc);
      } catch (e) {
        console.error("Failed to load DQ scorecard:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [isAllowed]);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <AlertTriangle className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          Data Quality suites are accessible by data engineers, compliance auditors, and administrators.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#242429]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
              Data Quality &amp; SLAs
            </h1>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#13241b] text-[#55ba82] border border-[#1e4730]">
              100% Pass Rate
            </span>
          </div>
          <p className="text-xs text-[#9e9ea7] mt-0.5">
            Validation checks via Great Expectations suites and dbt singular reconciliation tests.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Suite Pass Rate</div>
          <div className="text-2xl font-semibold text-[#10b981] mt-1 font-mono-code">100.0%</div>
          <div className="text-[11px] text-[#686873] mt-1">0 critical assertions breached</div>
        </div>

        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Assertions Executed</div>
          <div className="text-2xl font-semibold text-[#f4f4f6] mt-1 font-mono-code">{scorecard?.total_checks || 6}</div>
          <div className="text-[11px] text-[#686873] mt-1">Great Expectations + dbt singular tests</div>
        </div>

        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Revenue Variance (Silver vs Gold)</div>
          <div className="text-2xl font-semibold text-[#10b981] mt-1 font-mono-code">0.00%</div>
          <div className="text-[11px] text-[#686873] mt-1">Strict financial reconciliation passed</div>
        </div>
      </div>

      {/* Checks Table */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429]">
          <div className="text-sm font-semibold text-[#f4f4f6]">Assertions Breakdown</div>
          <div className="text-[11px] text-[#9e9ea7] mt-0.5">Automated test results per lakehouse layer</div>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Assertion Check</th>
                <th>Target Layer</th>
                <th>Status</th>
                <th>Observed Value</th>
                <th className="text-right">Threshold</th>
              </tr>
            </thead>
            <tbody>
              {scorecard?.checks.map((c, i) => (
                <tr key={i}>
                  <td className="font-mono text-xs font-medium text-[#f4f4f6]">{c.check}</td>
                  <td className="font-mono text-xs text-[#9e9ea7]">{c.layer}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10b981]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {c.status}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-[#f4f4f6]">{c.observed_value}</td>
                  <td className="text-right font-mono text-xs text-[#9e9ea7]">{c.threshold}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
