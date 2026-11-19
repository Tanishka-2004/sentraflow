import React from "react";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { AppShell } from "@/components/AppShell";

export const metadata = {
  title: "SentraFlow | Governed Financial Lakehouse & Real-Time Fraud Engine",
  description: "Enterprise Lakehouse dashboard with Medallion Delta storage, PII governance gate, and explainable AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 flex min-h-screen antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
