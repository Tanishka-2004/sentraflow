# Phase 10: Next.js 14 Analyst Dashboard

## 1. Overview & Architecture

SentraFlow provides a modern, responsive web console built with **Next.js 14 (App Router)**, **TypeScript**, **Tailwind CSS**, **Recharts**, and **React Flow (@xyflow/react)**. The dashboard is tightly integrated with the FastAPI backend and enforces the 5 RBAC security personas directly in the interface.

```mermaid
flowchart TD
    subgraph UI ["Next.js 14 App Router (Port 3001)"]
        Nav["Sidebar Nav (Role-Gated)"]
        Top["Header + 1-Click Persona Switcher"]
        P1["Overview (KPIs + Ingestion Chart)"]
        P2["Fraud Queue (Live Risk Badges)"]
        P3["Txn Detail (/fraud/[id]) + SHAP Waterfall"]
        P4["Lineage Explorer (Interactive React Flow)"]
        P5["Governance & Audit Log (/governance)"]
        P6["Data Quality Scorecard (/dq)"]
        P7["Pipeline Orchestration (/pipelines)"]
        P8["Admin Console (/admin)"]
    end
    API["FastAPI Backend (Port 8000)"]
    Top -->|JWT Auth & Refresh| API
    P1 -->|GET /transactions| API
    P2 -->|GET /fraud/queue| API
    P3 -->|GET /fraud/{id}/explanation| API
    P3 -->|POST /fraud/{id}/override| API
    P4 -->|GET /lineage/graph| API
    P5 -->|GET /governance/gate-runs| API
    P6 -->|GET /dq/scorecard| API
    P7 -->|POST /pipelines/trigger| API
```

## 2. Key Pages & Visualizations

### 2.1 1-Click Role Switcher & Login (`/login`)
- Evaluator convenience: Instant one-click login switches between `Admin`, `Fraud Analyst`, `Data Engineer`, `Compliance Auditor`, and `Viewer` without typing passwords.
- Context updates across all components reactively.

### 2.2 Overview (`/`)
- Telemetry KPI cards: Processed Financial Volume, Active Fraud Suspects, 100% PII Gate Pass Rate, Delta Lakehouse storage breakdown.
- Ingestion Volume and Fraud Velocity area chart (Recharts).

### 2.3 Live Fraud Review Queue (`/fraud`)
- Color-coded risk badges:
  - Green `< 0.30` (Normal)
  - Amber `0.30 - 0.70` (Moderate Risk)
  - Red `> 0.70` (Fraud Suspect)
- Real-time filters by channel (UPI, Card, IMPS, NEFT) and minimum score threshold.
- Direct "Review" action button.

### 2.4 Transaction Detail & SHAP Waterfall (`/fraud/[id]`)
- Masked customer attributes (PAN, Phone, Channel).
- **SHAP Decision Waterfall Attribution (Recharts):** Floating step-by-step bars visualizing baseline prior $\rightarrow$ positive (red) and negative (green) feature contributions $\rightarrow$ final probability score.
- Analyst disposition panel: "Confirm Fraud & Block" vs "Mark False Positive" with mandatory audit notes.

### 2.5 Column-Level Lineage Explorer (`/lineage`)
- Interactive **React Flow** DAG rendering raw Bronze $\rightarrow$ Governance Gate (Centerpiece shield: "100% PII BLOCKED") $\rightarrow$ Silver $\rightarrow$ Gold Marts.
- Color-coded layers: Bronze (Red/Gray), Gate (Amber Shield), Silver (Blue), Gold (Indigo).

### 2.6 Governance & PII Certification (`/governance`)
- Automated gate execution logs (`governance.pii_gate_audit`) displaying batch IDs, records scanned, 0 residual PII certifications, and cryptographic SHA-256 signatures.
- Active masking policies from `policies.yaml`.

### 2.7 Data Quality (`/dq`) & Pipelines (`/pipelines`)
- Great Expectations scorecard with 100% assertion pass rates.
- Airflow DAG trigger controls (`sentraflow_batch_pipeline`, `sentraflow_dq_monitor`, etc.).

## 3. Verification

Smoke tests in `tests/test_dashboard_smoke.py` verify package integrity, all 10 App Router routes, reusable components (`Sidebar`, `Header`, `ShapWaterfall`), and AuthContext role mapping.

