"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ShieldAlert,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { api, FraudExplanation } from "@/lib/api";
import { ShapWaterfall } from "@/components/ShapWaterfall";
import { useAuth } from "@/context/AuthContext";

export default function FraudDetailPage() {
  const params = useParams();
  const router = useRouter();
  const txnId = params.id as string;
  const { hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "fraud_analyst"]);

  const [explanation, setExplanation] = useState<FraudExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedStatus, setSubmittedStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!isAllowed) return;
    async function loadData() {
      try {
        const exp = await api.getFraudExplanation(txnId);
        setExplanation(exp);
      } catch (e) {
        console.error("Failed to load explanation:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [txnId, isAllowed]);

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <ShieldAlert className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          Only fraud analysts and administrators are authorized to review transaction risk explanations.
        </p>
      </div>
    );
  }

  const handleDecision = async (decision: "CONFIRMED_FRAUD" | "FALSE_POSITIVE") => {
    setSubmitting(true);
    try {
      await api.overrideFraudDecision(txnId, decision, notes);
      setSubmittedStatus(decision);
    } catch (err) {
      console.error("Override failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Navigation Header */}
      <div className="flex items-center justify-between pb-4 border-b border-[#242429]">
        <Link
          href="/fraud"
          className="inline-flex items-center gap-1.5 text-xs text-[#9e9ea7] hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Fraud Queue</span>
        </Link>

        {submittedStatus && (
          <div className="text-xs font-medium text-[#10b981] flex items-center gap-1.5 bg-[#13241b] border border-[#1e4730] px-2.5 py-1 rounded">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Decision recorded: {submittedStatus}</span>
          </div>
        )}
      </div>

      {/* Transaction Summary Card */}
      <div className="panel-card p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-base font-semibold text-[#f4f4f6]">{txnId}</span>
              <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded bg-[#2d181b] text-[#e06677] border border-[#5c212a]">
                SUSPECT
              </span>
            </div>
            <p className="text-xs text-[#9e9ea7] mt-1">
              TreeExplainer additive SHAP attribution for champion XGBoost model.
            </p>
          </div>

          <div className="flex items-center gap-4 bg-[#141416] p-3 rounded border border-[#242429]">
            <div>
              <div className="text-[10px] text-[#686873] uppercase font-semibold">Calculated Risk</div>
              <div className="text-xl font-mono font-semibold text-[#c8102e]">
                {explanation ? `${(explanation.final_score * 100).toFixed(1)}%` : "—"}
              </div>
            </div>
            <div className="pl-4 border-l border-[#242429]">
              <div className="text-[10px] text-[#686873] uppercase font-semibold">Recommendation</div>
              <div className="text-xs font-semibold text-[#f4f4f6]">BLOCK &amp; VERIFY</div>
            </div>
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mt-5 pt-4 border-t border-[#242429] text-xs">
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Amount</span>
            <span className="font-mono text-[#f4f4f6] font-medium text-xs mt-0.5 block">
              ₹{explanation?.amount ? explanation.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"}
            </span>
          </div>
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Channel</span>
            <span className="text-[#f4f4f6] font-medium mt-0.5 block">{explanation?.channel || "CARD"}</span>
          </div>
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Masked PAN</span>
            <span className="font-mono text-[#9e9ea7] mt-0.5 block">{explanation?.pan_masked || "XXXXX1234A"}</span>
          </div>
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Masked Phone</span>
            <span className="font-mono text-[#9e9ea7] mt-0.5 block">{explanation?.phone_masked || "XXXXXX1234"}</span>
          </div>
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Account ID</span>
            <span className="font-mono text-[#f4f4f6] mt-0.5 block">{explanation?.account_id || "ACC_1001"}</span>
          </div>
          <div>
            <span className="text-[#686873] block text-[10px] uppercase font-medium">Timestamp</span>
            <span className="text-[#9e9ea7] mt-0.5 block">
              {explanation?.txn_ts ? new Date(explanation.txn_ts).toLocaleTimeString() : "Live Stream"}
            </span>
          </div>
        </div>
      </div>

      {/* SHAP Waterfall Chart */}
      {explanation && (
        <ShapWaterfall
          baseValue={explanation.base_value}
          finalScore={explanation.final_score}
          steps={explanation.steps}
        />
      )}

      {/* Decision Action Box */}
      <div className="panel-card p-5">
        <div className="text-sm font-semibold text-[#f4f4f6]">Analyst Disposition &amp; Audit Log</div>
        <p className="text-xs text-[#9e9ea7] mt-0.5 mb-4">
          Actions taken are recorded with the analyst user signature in the immutable audit table.
        </p>

        <div className="space-y-3.5">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reason for disposition (e.g., Customer verified unusual travel velocity over SMS)..."
            className="w-full bg-[#141416] border border-[#292930] rounded-md p-3 text-xs text-[#f4f4f6] placeholder-[#55555e] focus:border-[#40404a] outline-none h-20"
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => handleDecision("CONFIRMED_FRAUD")}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 bg-[#c8102e] hover:bg-[#b00d27] disabled:opacity-50 text-white font-medium text-xs px-4 py-2 rounded-md transition-colors cursor-pointer"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Confirm Fraud &amp; Block</span>
            </button>
            <button
              onClick={() => handleDecision("FALSE_POSITIVE")}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 bg-[#1a1a1e] hover:bg-[#25252b] text-[#10b981] border border-[#1e4730] disabled:opacity-50 font-medium text-xs px-4 py-2 rounded-md transition-colors cursor-pointer"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Mark False Positive &amp; Approve</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
