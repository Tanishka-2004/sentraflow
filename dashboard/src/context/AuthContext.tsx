"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserProfile, api } from "@/lib/api";

interface DemoAccount {
  label: string;
  email: string;
  role: string;
  badgeColor: string;
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { label: "Admin (Full Access)", email: "admin@sentraflow.io", role: "admin", badgeColor: "bg-purple-900/50 text-purple-300 border-purple-700" },
  { label: "Fraud Analyst", email: "analyst@sentraflow.io", role: "fraud_analyst", badgeColor: "bg-red-900/50 text-red-300 border-red-700" },
  { label: "Data Engineer", email: "engineer@sentraflow.io", role: "data_engineer", badgeColor: "bg-blue-900/50 text-blue-300 border-blue-700" },
  { label: "Compliance Auditor", email: "auditor@sentraflow.io", role: "compliance_auditor", badgeColor: "bg-amber-900/50 text-amber-300 border-amber-700" },
  { label: "Viewer (Aggregates Only)", email: "viewer@sentraflow.io", role: "viewer", badgeColor: "bg-gray-800 text-gray-300 border-gray-700" },
];

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  loginAs: (email: string) => Promise<void>;
  logout: () => void;
  hasRole: (allowedRoles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  loginAs: async () => {},
  logout: () => {},
  hasRole: () => false,
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProfile = async () => {
    try {
      const profile = await api.getMe();
      setUser(profile);
    } catch {
      // Default to fraud_analyst for instant local demo experience
      await loginAs("analyst@sentraflow.io");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const loginAs = async (email: string) => {
    setLoading(true);
    try {
      // Passwords follow role convention: CapitalizedRole@123
      const passMap: Record<string, string> = {
        "admin@sentraflow.io": "Admin@123",
        "analyst@sentraflow.io": "Analyst@123",
        "engineer@sentraflow.io": "Engineer@123",
        "auditor@sentraflow.io": "Auditor@123",
        "viewer@sentraflow.io": "Viewer@123",
      };
      const pwd = passMap[email] || "Analyst@123";
      await api.login(email, pwd);
      const profile = await api.getMe();
      setUser(profile);
    } catch (err) {
      console.error("Login failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("sentraflow_token");
      localStorage.removeItem("sentraflow_refresh");
    }
    setUser(null);
  };

  const hasRole = (allowedRoles: string[]): boolean => {
    if (!user) return false;
    return allowedRoles.includes(user.role);
  };

  return (
    <AuthContext.Provider value={{ user, loading, loginAs, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

