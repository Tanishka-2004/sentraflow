"use client";

import React, { useState } from "react";
import { Workflow, Play, CheckCircle2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface PipelineRunItem {
  runId: string;
  dagId: string;
  status: "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED";
  triggeredAt: string;
  duration: string;
}

export default function PipelinesPage() {
  const { user, hasRole } = useAuth();
  const isAllowed = hasRole(["admin", "data_engineer"]);

  const [triggeringDag, setTriggeringDag] = useState<string | null>(null);
  const [lastTriggerResult, setLastTriggerResult] = useState<string | null>(null);

  const [runsHistory, setRunsHistory] = useState<PipelineRunItem[]>([
    { runId: "scheduled__2026-11-19T01:00:00", dagId: "sentraflow_batch_pipeline", status: "SUCCESS", triggeredAt: "1h 19m ago", duration: "4m 12s" },
    { runId: "scheduled__2026-11-18T22:00:00", dagId: "sentraflow_dq_monitor", status: "SUCCESS", triggeredAt: "4h 19m ago", duration: "1m 45s" },
    { runId: "scheduled__2026-11-18T00:00:00", dagId: "sentraflow_model_retrain", status: "SUCCESS", triggeredAt: "1d ago", duration: "12m 30s" },
    { runId: "scheduled__2026-11-15T00:00:00", dagId: "sentraflow_maintenance", status: "SUCCESS", triggeredAt: "4d ago", duration: "8m 15s" },
  ]);

  const dags = [
    { id: "sentraflow_batch_pipeline", schedule: "@hourly", status: "SUCCESS", lastRun: "24 mins ago", duration: "4m 12s", desc: "Bronze Ingest -> PII Gate -> Silver Conform -> dbt Gold Marts" },
    { id: "sentraflow_dq_monitor", schedule: "@daily", status: "SUCCESS", lastRun: "3 hours ago", duration: "1m 45s", desc: "Great Expectations + dbt Singular Revenue Reconciliation" },
    { id: "sentraflow_model_retrain", schedule: "@weekly", status: "SUCCESS", lastRun: "2 days ago", duration: "12m 30s", desc: "Population Drift Evaluation -> XGBoost Retraining -> MLflow Registration" },
    { id: "sentraflow_maintenance", schedule: "@weekly", status: "SUCCESS", lastRun: "5 days ago", duration: "8m 15s", desc: "Delta Lake OPTIMIZE Z-ORDER & VACUUM (7-Day Retention)" },
  ];

  if (!isAllowed) {
    return (
      <div className="panel-card p-8 text-center max-w-lg mx-auto my-12">
        <Workflow className="w-10 h-10 text-[#686873] mx-auto mb-3" />
        <h2 className="text-sm font-semibold text-[#f4f4f6]">Access Restricted</h2>
        <p className="text-xs text-[#9e9ea7] mt-1.5">
          Airflow pipeline orchestration and manual triggers are restricted to data engineers and administrators.
        </p>
      </div>
    );
  }

  const handleTrigger = async (dagId: string) => {
    setTriggeringDag(dagId);
    setLastTriggerResult(null);
    try {
      const res = await api.triggerPipeline(dagId);
      setLastTriggerResult(`Triggered: ${res.run_id}`);
      
      const newRun: PipelineRunItem = {
        runId: res.run_id,
        dagId: dagId,
        status: "SUCCESS",
        triggeredAt: "Just now",
        duration: "In progress",
      };
      setRunsHistory((prev) => [newRun, ...prev]);
    } catch (e: any) {
      setLastTriggerResult(`Trigger failed: ${e.message}`);
    } finally {
      setTriggeringDag(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#242429]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[#f4f4f6] tracking-tight">
              Pipelines &amp; Orchestration
            </h1>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-[#1a1a1e] text-[#a1a1aa] border border-[#2b2b32]">
              Airflow 2.9
            </span>
          </div>
          <p className="text-xs text-[#9e9ea7] mt-0.5">
            Scheduled lakehouse DAGs with SLA tracking, retries, and manual trigger controls.
          </p>
        </div>

        {lastTriggerResult && (
          <div className="text-xs font-mono text-[#55ba82] bg-[#13241b] border border-[#1e4730] px-3 py-1.5 rounded-md flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{lastTriggerResult}</span>
          </div>
        )}
      </div>

      {/* DAG Cards */}
      <div className="space-y-3">
        {dags.map((dag) => {
          const isTriggeringThis = triggeringDag === dag.id;

          return (
            <div
              key={dag.id}
              className="panel-card p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-mono text-sm font-semibold text-[#f4f4f6]">{dag.id}</span>
                  <span className="text-[10px] font-mono text-[#9e9ea7] bg-[#141416] px-1.5 py-0.5 rounded border border-[#242429]">
                    {dag.schedule}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10b981]">
                    <CheckCircle2 className="w-3 h-3" />
                    {dag.status}
                  </span>
                </div>
                <p className="text-xs text-[#9e9ea7]">{dag.desc}</p>
                <div className="flex items-center gap-4 text-[11px] text-[#686873] pt-1">
                  <span>Last Run: <strong className="text-[#a1a1aa] font-medium">{dag.lastRun}</strong></span>
                  <span>Duration: <strong className="text-[#a1a1aa] font-medium">{dag.duration}</strong></span>
                </div>
              </div>

              <button
                onClick={() => handleTrigger(dag.id)}
                disabled={isTriggeringThis}
                className="inline-flex items-center gap-1.5 bg-[#1a1a1e] hover:bg-[#25252b] disabled:opacity-50 text-[#f4f4f6] font-medium text-xs px-3.5 py-1.5 rounded-md border border-[#2e2e36] transition-colors self-start md:self-center cursor-pointer"
              >
                {isTriggeringThis ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    <span>Triggering...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 fill-current text-[#9e9ea7]" />
                    <span>Run DAG</span>
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Execution Run History */}
      <div className="panel-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#242429] flex items-center justify-between">
          <div className="text-sm font-semibold text-[#f4f4f6]">Recent DAG Execution Runs</div>
          <span className="text-xs text-[#686873] font-mono">Airflow Metadata</span>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>DAG Identifier</th>
                <th>Execution State</th>
                <th>Triggered</th>
                <th className="text-right">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runsHistory.map((run, i) => (
                <tr key={i}>
                  <td className="font-mono text-xs text-[#f4f4f6] font-medium">{run.runId}</td>
                  <td className="font-mono text-xs text-[#9e9ea7]">{run.dagId}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10b981]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {run.status}
                    </span>
                  </td>
                  <td className="text-xs text-[#9e9ea7]">{run.triggeredAt}</td>
                  <td className="text-right font-mono text-xs text-[#9e9ea7]">{run.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
