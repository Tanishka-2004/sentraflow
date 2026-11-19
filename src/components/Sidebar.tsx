"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ShieldAlert,
  GitBranch,
  ShieldCheck,
  CheckCircle2,
  Workflow,
  Users,
  LayoutDashboard,
  Lock,
  X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  const pathname = usePathname();
  const { user, hasRole } = useAuth();

  const navItems = [
    { label: "Overview", href: "/", icon: LayoutDashboard, roles: ["admin", "fraud_analyst", "data_engineer", "compliance_auditor", "viewer"] },
    { label: "Fraud Queue", href: "/fraud", icon: ShieldAlert, roles: ["admin", "fraud_analyst"], badge: "9" },
    { label: "Lineage Explorer", href: "/lineage", icon: GitBranch, roles: ["admin", "data_engineer", "compliance_auditor"] },
    { label: "Governance & PII", href: "/governance", icon: ShieldCheck, roles: ["admin", "compliance_auditor", "data_engineer"] },
    { label: "Data Quality", href: "/dq", icon: CheckCircle2, roles: ["admin", "data_engineer", "compliance_auditor"] },
    { label: "Pipelines", href: "/pipelines", icon: Workflow, roles: ["admin", "data_engineer"] },
    { label: "Admin & Access", href: "/admin", icon: Users, roles: ["admin"] },
  ];

  return (
    <aside
      className={`w-64 bg-[#141416] border-r border-[#242429] flex flex-col h-screen fixed left-0 top-0 select-none z-40 transition-transform duration-200 ease-in-out md:translate-x-0 ${
        isOpen ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-6 border-b border-[#242429]">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-[#c8102e] rounded flex items-center justify-center text-white text-xs font-black shadow-sm">
            ▲
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-[#f4f4f6]">
              SentraFlow
            </div>
            <div className="text-[10px] text-[#8c785c] tracking-wide font-medium">
              Lakehouse Console
            </div>
          </div>
        </div>

        {/* Mobile close button */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden text-[#9e9ea7] hover:text-white p-1 rounded-md"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <div className="text-[10px] font-semibold text-[#686873] uppercase tracking-wider px-3 py-2">
          Platform
        </div>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          const isAllowed = hasRole(item.roles);
          const Icon = item.icon;

          if (!isAllowed) {
            return (
              <div
                key={item.href}
                className="flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium text-[#4a4a52] cursor-not-allowed select-none"
                title={`Requires roles: ${item.roles.join(", ")}`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4 text-[#4a4a52]" />
                  <span>{item.label}</span>
                </div>
                <Lock className="w-3 h-3 text-[#4a4a52]" />
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => onClose && onClose()}
              className={`flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                isActive
                  ? "bg-[#222227] text-white border-l-2 border-[#c8102e]"
                  : "text-[#9e9ea7] hover:bg-[#1a1a1e] hover:text-[#f4f4f6]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? "text-[#c8102e]" : "text-[#7a7a85]"}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-[#2b181b] text-[#e06677] border border-[#5c212a]">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Security Persona Info Footer */}
      <div className="p-4 border-t border-[#242429] bg-[#111113]">
        <div className="flex items-center justify-between">
          <div className="truncate">
            <div className="text-[10px] text-[#686873] uppercase tracking-wider font-semibold">Active Persona</div>
            <div className="text-xs font-medium text-[#f4f4f6] capitalize mt-0.5 truncate">
              {user?.role.replace("_", " ") || "Viewer"}
            </div>
          </div>
          <span className="w-2 h-2 rounded-full bg-[#10b981]" title="System operational" />
        </div>
      </div>
    </aside>
  );
};
