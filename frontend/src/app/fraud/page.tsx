"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldAlert, ArrowRight, Filter } from "lucide-react";
import { api, FraudQueueItem } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function FraudQueuePage() {
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "fraud_analyst"]);

  const [queue, setQueue] = useState<FraudQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedChannel, setSelectedChannel] = useState<string>("ALL");
  const [minScore, setMinScore] = useState<number>(0.0);

  useEffect(() => {
    if (!isAllowed) return;
    async function fetchQueue() {
      try {
        const items = await api.getFraudQueue();
        setQueue(items);
      } catch (err) {
        console.error("Failed to fetch fraud queue:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchQueue();
  }, [isAllowed]);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <ShieldAlert className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted by Policy</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          The Fraud Queue requires <span className="font-medium text-white">fraud_analyst</span> or <span className="font-medium text-white">admin</span> credentials. Switch your active role in the header to review transactions.
        </p>
      </div>
    );
  }

  const filteredQueue = queue.filter((item) => {
    if (selectedChannel !== "ALL" && item.channel !== selectedChannel) return false;
    if (item.fraud_score < minScore) return false;
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#242429]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
              Fraud Review Queue
            </h1>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#2d181b] text-[#e06677] border border-[#5c212a]">
              {filteredQueue.length} Pending
            </span>
          </div>
          <p className="text-xs text-[#9e9ea7] mt-0.5">
            Suspect transactions scored by champion XGBoost model awaiting analyst disposition.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2.5 text-xs">
          <div className="flex items-center gap-1.5 bg-[#1a1a1e] border border-[#2b2b32] px-2.5 py-1.5 rounded-md">
            <span className="text-[#686873]">Channel:</span>
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="bg-transparent text-[#f4f4f6] outline-none cursor-pointer"
            >
              <option value="ALL" className="bg-[#1a1a1e]">All</option>
              <option value="UPI" className="bg-[#1a1a1e]">UPI</option>
              <option value="CARD" className="bg-[#1a1a1e]">Card</option>
              <option value="IMPS" className="bg-[#1a1a1e]">IMPS</option>
              <option value="NEFT" className="bg-[#1a1a1e]">NEFT</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 bg-[#1a1a1e] border border-[#2b2b32] px-2.5 py-1.5 rounded-md">
            <span className="text-[#686873]">Threshold:</span>
            <select
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="bg-transparent text-[#f4f4f6] outline-none cursor-pointer"
            >
              <option value="0.0" className="bg-[#1a1a1e]">All (≥ 0.00)</option>
              <option value="0.5" className="bg-[#1a1a1e]">Suspect (≥ 0.50)</option>
              <option value="0.7" className="bg-[#1a1a1e]">Severe (≥ 0.70)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Fraud Queue Table */}
      <div className="panel-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Transaction ID</th>
                <th>Account / Customer</th>
                <th>Amount (INR)</th>
                <th>Channel</th>
                <th>Risk Score</th>
                <th>Flagged Triggers</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-[#686873]">
                    Loading queue items...
                  </td>
                </tr>
              ) : filteredQueue.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-[#686873]">
                    No transactions currently in queue matching the active filter.
                  </td>
                </tr>
              ) : (
                filteredQueue.map((item) => {
                  const isSevere = item.fraud_score >= 0.70;
                  return (
                    <tr key={item.txn_id}>
                      <td className="font-mono text-xs font-medium text-[#f4f4f6]">
                        {item.txn_id}
                      </td>
                      <td>
                        <div className="text-xs text-[#f4f4f6]">{item.account_id}</div>
                        <div className="text-[10px] text-[#686873] font-mono">{item.customer_id}</div>
                      </td>
                      <td className="font-mono text-xs font-medium text-[#f4f4f6]">
                        ₹{item.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                      <td>
                        <span className="text-[11px] font-medium text-[#9e9ea7]">
                          {item.channel}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`inline-block font-mono text-[11px] font-semibold px-2 py-0.5 rounded ${
                            isSevere
                              ? "bg-[#2d181b] text-[#e06677] border border-[#5c212a]"
                              : "bg-[#261f14] text-[#d49e55] border border-[#4d381c]"
                          }`}
                        >
                          {(item.fraud_score * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="max-w-xs truncate text-[#9e9ea7] text-[11px]">
                        {item.flagged_reasons.join(" • ") || "Elevated anomaly score"}
                      </td>
                      <td className="text-right">
                        <Link
                          href={`/fraud/${item.txn_id}`}
                          className="inline-flex items-center gap-1 bg-[#1a1a1e] hover:bg-[#25252b] text-[#f4f4f6] font-medium text-xs px-2.5 py-1 rounded border border-[#2e2e36] transition-colors"
                        >
                          <span>Review</span>
                          <ArrowRight className="w-3 h-3 text-[#9e9ea7]" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
