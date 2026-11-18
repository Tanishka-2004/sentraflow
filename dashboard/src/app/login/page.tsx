"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, UserCheck, Lock } from "lucide-react";
import { DEMO_ACCOUNTS, useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { loginAs } = useAuth();
  const [email, setEmail] = useState("analyst@sentraflow.io");
  const [password, setPassword] = useState("Analyst@123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      await loginAs(email);
      router.push("/");
    } catch (err: any) {
      setError("Invalid email or password. Please select a demo account below.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDemo = async (demoEmail: string) => {
    await loginAs(demoEmail);
    router.push("/");
  };

  return (
    <div className="max-w-xl mx-auto py-12 px-4">
      {/* Brand Header */}
      <div className="text-center mb-8">
        <div className="inline-flex w-12 h-12 rounded-xl bg-blue-600 items-center justify-center font-bold text-white text-xl shadow-xl shadow-blue-500/30 mb-4">
          SF
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Sign in to SentraFlow</h1>
        <p className="text-xs text-gray-400 mt-1">Role-Based Financial Data Lakehouse & Fraud Intelligence Engine</p>
      </div>

      {/* Main Login Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-2xl">
        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-950/60 border border-red-800/60 text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 outline-none"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg shadow-lg shadow-blue-600/30 transition-all mt-2"
          >
            {loading ? "Authenticating..." : "Sign In with Credentials"}
          </button>
        </form>

        {/* 1-Click Role Switcher Demo Cards */}
        <div className="mt-8 pt-6 border-t border-gray-800">
          <div className="flex items-center gap-2 mb-4">
            <UserCheck className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-bold text-gray-300 uppercase tracking-wider">
              1-Click Demo Personas (Evaluator Quick Access)
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {DEMO_ACCOUNTS.map((acc) => (
              <button
                key={acc.email}
                type="button"
                onClick={() => handleSelectDemo(acc.email)}
                className={`text-left p-3 rounded-lg border text-xs font-medium transition-all hover:scale-[1.02] ${acc.badgeColor}`}
              >
                <div className="font-bold">{acc.label}</div>
                <div className="text-[10px] opacity-70 font-mono mt-0.5">{acc.email}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

