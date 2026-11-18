"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#101012] text-[#f4f4f6] antialiased w-full selection:bg-[#c8102e] selection:text-white">
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          onClick={() => setMobileMenuOpen(false)}
          className="fixed inset-0 bg-black/60 z-30 md:hidden transition-opacity"
        />
      )}

      {/* Sidebar with Mobile Slide-over */}
      <Sidebar
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:pl-64 min-w-0 transition-all duration-150">
        <Header onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)} />
        <main className="flex-1 p-5 sm:p-7 lg:p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
