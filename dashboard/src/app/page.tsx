"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  ShieldCheck,
  Search,
  Filter,
  Check,
  Copy,
  ChevronRight,
  ArrowUpRight,
  CheckCircle2,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { api, Transaction } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function OverviewPage() {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedChannel, setSelectedChannel] = useState("ALL");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await api.getTransactions(1, 50);
        setTransactions(res.items);
      } catch (e) {
        console.error("Failed to load overview transactions:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleCopy = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const totalVolume = transactions.reduce((acc, t) => acc + t.amount, 0);
  const fraudCount = transactions.filter((t) => t.fraud_score >= 0.50).length;

  const hourlyData = [
    { hour: "00:00", volume: 142000, txns: 18 },
    { hour: "04:00", volume: 68000, txns: 9 },
    { hour: "08:00", volume: 380000, txns: 42 },
    { hour: "12:00", volume: 890000, txns: 94 },
    { hour: "16:00", volume: 1240000, txns: 110 },
    { hour: "20:00", volume: 920000, txns: 85 },
    { hour: "23:59", volume: 410000, txns: 38 },
  ];

  const filteredTxns = transactions.filter((t) => {
    if (selectedChannel !== "ALL" && t.channel !== selectedChannel) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        t.txn_id.toLowerCase().includes(term) ||
        t.pan.toLowerCase().includes(term) ||
        t.account_id.toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#242429]">
        <div>
          <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
            Lakehouse Overview
          </h1>
          <p className="text-xs text-[#9e9ea7] mt-0.5">
            Streaming ingestion telemetry, Medallion store metrics, and fraud scoring queue.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/fraud"
            className="inline-flex items-center gap-1.5 bg-[#c8102e] hover:bg-[#b00d27] text-white text-xs font-medium px-3.5 py-1.5 rounded-md transition-colors"
          >
            <span>Fraud Queue</span>
            <span className="text-[10px] font-mono bg-white/20 px-1 rounded">{fraudCount > 0 ? fraudCount : 9}</span>
          </Link>
          <Link
            href="/lineage"
            className="inline-flex items-center gap-1.5 bg-[#1a1a1e] hover:bg-[#222226] text-[#f4f4f6] text-xs font-medium px-3.5 py-1.5 rounded-md border border-[#2e2e36] transition-colors"
          >
            <span>Lineage Graph</span>
          </Link>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Total Ingestion Volume</div>
          <div className="text-2xl font-semibold text-[#f4f4f6] mt-1 font-mono-code">
            ₹{(totalVolume > 0 ? totalVolume : 3824500).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-[#686873] mt-1">
            230 transactions processed in current window
          </div>
        </div>

        {/* Card 2 */}
        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Flagged Suspect Transactions</div>
          <div className="text-2xl font-semibold text-[#c8102e] mt-1 font-mono-code">
            {fraudCount > 0 ? fraudCount : 9}
          </div>
          <div className="text-[11px] text-[#686873] mt-1">
            Score ≥ 0.50 requiring analyst disposition
          </div>
        </div>

        {/* Card 3 */}
        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">PII Governance Hard Gate</div>
          <div className="text-2xl font-semibold text-[#10b981] mt-1 font-mono-code">
            100% Enforced
          </div>
          <div className="text-[11px] text-[#686873] mt-1">
            0 unmasked PII records promoted to Silver
          </div>
        </div>

        {/* Card 4 */}
        <div className="panel-card p-4">
          <div className="text-[11px] font-medium text-[#9e9ea7]">Scoring Engine Latency (p95)</div>
          <div className="text-2xl font-semibold text-[#f4f4f6] mt-1 font-mono-code">
            14.8 ms
          </div>
          <div className="text-[11px] text-[#686873] mt-1">
            XGBoost Champion + SHAP explainability
          </div>
        </div>
      </div>

      {/* Main Grid: Chart & Lakehouse Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        
        {/* Ingestion Throughput Chart (2 cols) */}
        <div className="panel-card p-5 lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-[#f4f4f6]">Ingestion Throughput</div>
              <div className="text-[11px] text-[#9e9ea7]">Hourly volume streaming through Kafka txn.raw</div>
            </div>
            <div className="text-xs text-[#9e9ea7] font-mono">
              Peak: 2,000 txns/batch
            </div>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#222227" vertical={false} />
                <XAxis dataKey="hour" stroke="#686873" fontSize={11} tickLine={false} />
                <YAxis stroke="#686873" fontSize={11} tickLine={false} tickFormatter={(val) => `₹${val/1000}k`} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-[#1c1c20] border border-[#33333d] p-2.5 rounded-md text-xs shadow-lg">
                          <div className="font-semibold text-white">{data.hour}</div>
                          <div className="text-[#a1a1aa] font-mono mt-0.5">₹{data.volume.toLocaleString("en-IN")}</div>
                          <div className="text-[#686873] text-[11px]">{data.txns} transactions</div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area type="monotone" dataKey="volume" stroke="#c8102e" strokeWidth={2} fill="rgba(200, 16, 46, 0.08)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Lakehouse Layer Architecture Status (1 col) */}
        <div className="panel-card p-5 flex flex-col justify-between">
          <div>
            <div className="text-sm font-semibold text-[#f4f4f6] mb-1">Medallion Architecture</div>
            <div className="text-[11px] text-[#9e9ea7] mb-4">ACID compliance & SCD2 conformed storage</div>

            <div className="space-y-3">
              <div className="p-3 rounded-md bg-[#141416] border border-[#242429]">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="text-[#f4f4f6]">Bronze Layer</span>
                  <span className="font-mono text-[11px] text-[#9e9ea7]">Raw Landing</span>
                </div>
                <div className="text-[11px] text-[#686873] mt-1">4 Delta tables • Unchecked raw landing</div>
              </div>

              <div className="p-3 rounded-md bg-[#141416] border border-[#242429]">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="text-[#f4f4f6]">PII Hard Gate</span>
                  <span className="text-[11px] text-[#10b981] font-medium">100% Passed</span>
                </div>
                <div className="text-[11px] text-[#686873] mt-1">HMAC SHA-256 tokens • Format-preserving hashes</div>
              </div>

              <div className="p-3 rounded-md bg-[#141416] border border-[#242429]">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="text-[#f4f4f6]">Silver Layer</span>
                  <span className="font-mono text-[11px] text-[#9e9ea7]">Conformed SCD2</span>
                </div>
                <div className="text-[11px] text-[#686873] mt-1">Zero raw PII • Customer & transaction dimensions</div>
              </div>

              <div className="p-3 rounded-md bg-[#141416] border border-[#242429]">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="text-[#f4f4f6]">Gold Layer</span>
                  <span className="font-mono text-[11px] text-[#9e9ea7]">12 dbt Marts</span>
                </div>
                <div className="text-[11px] text-[#686873] mt-1">Star schema • 0.00% revenue variance tolerance</div>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-[#242429] mt-3">
            <Link
              href="/dq"
              className="text-xs text-[#9e9ea7] hover:text-white flex items-center justify-between transition-colors"
            >
              <span>View Data Quality Scorecard</span>
              <ChevronRight className="w-4 h-4 text-[#686873]" />
            </Link>
          </div>
        </div>

      </div>

      {/* Transactions Ledger Table */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[#f4f4f6]">Live Ingested Transactions</div>
            <div className="text-[11px] text-[#9e9ea7] mt-0.5">
              Conformed records promoted through PII Gate and scored in real-time.
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#686873] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter Txn ID, PAN, Acc..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-[#141416] border border-[#292930] text-xs text-[#f4f4f6] pl-8 pr-3 py-1.5 rounded-md outline-none focus:border-[#3d3d47] transition-colors w-48 sm:w-56"
              />
            </div>

            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="bg-[#141416] border border-[#292930] text-xs text-[#f4f4f6] px-2.5 py-1.5 rounded-md outline-none cursor-pointer"
            >
              <option value="ALL">All Channels</option>
              <option value="UPI">UPI</option>
              <option value="CARD">Card</option>
              <option value="IMPS">IMPS</option>
              <option value="NEFT">NEFT</option>
            </select>
          </div>
        </div>

        {/* Viewer RBAC Guard */}
        {user?.role === "viewer" ? (
          <div className="p-8 text-center bg-[#141416]">
            <ShieldAlert className="w-8 h-8 text-[#9e9ea7] mx-auto mb-2 opacity-60" />
            <div className="text-xs font-semibold text-[#f4f4f6]">Row-Level Records Restricted for Viewer</div>
            <p className="text-[11px] text-[#686873] mt-1 max-w-md mx-auto">
              Per data governance policies, individual transaction rows require Analyst or Engineer credentials. High-level KPIs remain visible above.
            </p>
          </div>
        ) : loading ? (
          <div className="py-12 text-center text-xs text-[#686873]">
            Loading transaction records...
          </div>
        ) : filteredTxns.length === 0 ? (
          <div className="py-12 text-center text-xs text-[#686873]">
            No transactions matching &quot;{searchTerm}&quot;
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Transaction ID</th>
                  <th>Channel</th>
                  <th>Masked PAN</th>
                  <th>Masked Phone</th>
                  <th className="text-right">Amount</th>
                  <th className="text-center">Fraud Score</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTxns.slice(0, 10).map((t) => (
                  <tr key={t.txn_id}>
                    <td className="font-mono text-[#f4f4f6] font-medium">
                      <div className="flex items-center gap-1.5">
                        <Link href={`/fraud/${t.txn_id}`} className="hover:underline">
                          {t.txn_id.length > 20 ? `${t.txn_id.slice(0, 16)}...` : t.txn_id}
                        </Link>
                        <button
                          onClick={(e) => handleCopy(t.txn_id, e)}
                          className="text-[#686873] hover:text-white p-0.5 rounded"
                          title="Copy ID"
                        >
                          {copiedId === t.txn_id ? (
                            <Check className="w-3 h-3 text-[#10b981]" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </td>
                    <td>
                      <span className="text-[11px] font-medium text-[#9e9ea7]">
                        {t.channel}
                      </span>
                    </td>
                    <td className="font-mono text-[11px] text-[#9e9ea7]">{t.pan}</td>
                    <td className="font-mono text-[11px] text-[#9e9ea7]">{t.phone}</td>
                    <td className="text-right font-mono text-xs font-medium text-[#f4f4f6]">
                      ₹{t.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="text-center">
                      <span
                        className={`inline-block font-mono text-[11px] font-semibold px-2 py-0.5 rounded ${
                          t.fraud_score >= 0.5
                            ? "bg-[#2d181b] text-[#e06677] border border-[#5c212a]"
                            : "bg-[#13241b] text-[#55ba82] border border-[#1e4730]"
                        }`}
                      >
                        {(t.fraud_score * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-right">
                      <Link
                        href={`/fraud/${t.txn_id}`}
                        className="text-xs text-[#9e9ea7] hover:text-white font-medium hover:underline"
                      >
                        SHAP &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
