"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  CartesianGrid,
} from "recharts";
import { ShapStep } from "@/lib/api";

interface ShapWaterfallProps {
  baseValue: number;
  finalScore: number;
  steps: ShapStep[];
}

interface WaterfallBarItem {
  name: string;
  value: number;
  rawContrib: number;
  cumulative?: number;
  isBase?: boolean;
  isFinal?: boolean;
  impact: string;
}

export const ShapWaterfall: React.FC<ShapWaterfallProps> = ({ baseValue, finalScore, steps }) => {
  const chartData: WaterfallBarItem[] = [
    {
      name: "Prior Baseline",
      value: baseValue,
      rawContrib: baseValue,
      isBase: true,
      isFinal: false,
      impact: "BASELINE",
    },
    ...steps.map((s) => ({
      name: s.feature_name.replace(/_/g, " "),
      value: s.contribution,
      rawContrib: s.contribution,
      cumulative: s.cumulative_score,
      isBase: false,
      isFinal: false,
      impact: s.impact,
    })),
    {
      name: "Final Score",
      value: finalScore,
      rawContrib: finalScore,
      isBase: false,
      isFinal: true,
      impact: finalScore > 0.5 ? "HIGH_RISK" : "LOW_RISK",
    },
  ];

  return (
    <div className="panel-card p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <div className="text-sm font-semibold text-[#f4f4f6]">
            SHAP Decision Attribution
          </div>
          <div className="text-[11px] text-[#9e9ea7]">
            Additive feature contributions explaining XGBoost model score
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 text-[#e06677]">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#c8102e]" />
            <span>Increases Risk</span>
          </div>
          <div className="flex items-center gap-1.5 text-[#55ba82]">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#10b981]" />
            <span>Decreases Risk</span>
          </div>
          <div className="flex items-center gap-1.5 text-[#9e9ea7]">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#4a4a52]" />
            <span>Baseline</span>
          </div>
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 15, right: 20, left: -10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222227" vertical={false} />
            <XAxis dataKey="name" stroke="#686873" fontSize={11} tickLine={false} />
            <YAxis stroke="#686873" fontSize={11} domain={[0, 1]} tickLine={false} />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  return (
                    <div className="bg-[#1c1c20] border border-[#33333d] p-2.5 rounded-md text-xs shadow-lg">
                      <div className="font-semibold text-white capitalize">{data.name}</div>
                      <div className="text-[#9e9ea7] mt-0.5">
                        Contribution: <span className="font-mono text-white">{data.rawContrib > 0 ? `+${data.rawContrib}` : data.rawContrib}</span>
                      </div>
                      {data.cumulative !== undefined && (
                        <div className="text-[#686873] text-[11px]">
                          Cumulative: <span className="font-mono text-[#a1a1aa]">{data.cumulative}</span>
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine y={0.5} stroke="#c8102e" strokeDasharray="3 3" strokeOpacity={0.6} />
            <Bar dataKey="value" radius={[2, 2, 0, 0]}>
              {chartData.map((entry, index) => {
                let color = "#4a4a52"; // Baseline neutral dark
                if (entry.isFinal) {
                  color = entry.value >= 0.5 ? "#c8102e" : "#10b981";
                } else if (!entry.isBase) {
                  color = entry.impact === "INCREASES_RISK" ? "#c8102e" : "#10b981";
                }
                return <Cell key={`cell-${index}`} fill={color} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
