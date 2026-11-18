"use client";

import React from "react";
import { Menu } from "lucide-react";
import { DEMO_ACCOUNTS, useAuth } from "@/context/AuthContext";

interface HeaderProps {
  onToggleMobileMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleMobileMenu }) => {
  const { user, loginAs } = useAuth();

  return (
    <header className="h-16 bg-[#141416] border-b border-[#242429] flex items-center justify-between px-5 sm:px-8 sticky top-0 z-30">
      {/* Mobile Toggle & Environment Indicator */}
      <div className="flex items-center gap-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden text-[#9e9ea7] hover:text-white p-1.5 -ml-1 rounded-md"
            aria-label="Toggle navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        <div className="flex items-center gap-2 text-xs text-[#9e9ea7]">
          <span className="w-2 h-2 rounded-full bg-[#10b981]" />
          <span className="font-medium text-[#f4f4f6]">Cluster Live</span>
          <span className="text-[#4a4a52] hidden sm:inline">•</span>
          <span className="text-[#686873] hidden sm:inline font-mono text-[11px]">AWS eu-west-1 (Delta Lake 3.2)</span>
        </div>
      </div>

      {/* Role Switcher & User Profile */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Fast Role Switcher */}
        <div className="flex items-center gap-2 bg-[#1a1a1e] border border-[#2b2b32] rounded-md px-2.5 py-1">
          <span className="text-[11px] text-[#686873] font-medium hidden sm:inline">Role:</span>
          <select
            value={user?.email || ""}
            onChange={(e) => loginAs(e.target.value)}
            className="bg-transparent text-xs font-medium text-[#f4f4f6] outline-none cursor-pointer max-w-[130px] sm:max-w-none"
          >
            {DEMO_ACCOUNTS.map((acc) => (
              <option key={acc.email} value={acc.email} className="bg-[#1a1a1e] text-[#f4f4f6]">
                {acc.label}
              </option>
            ))}
          </select>
        </div>

        {/* User Avatar */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-[#242429]">
          <div className="w-7 h-7 rounded bg-[#222227] border border-[#33333d] flex items-center justify-center text-[#f4f4f6] font-medium text-xs">
            {user?.full_name?.charAt(0) || "U"}
          </div>
          <div className="text-left hidden md:block">
            <div className="text-xs font-medium text-[#f4f4f6] truncate max-w-[120px]">{user?.full_name || "Analyst"}</div>
            <div className="text-[10px] text-[#686873] capitalize">{user?.role?.replace("_", " ")}</div>
          </div>
        </div>
      </div>
    </header>
  );
};
