/**
 * SentraFlow API Client.
 * Connects to the FastAPI backend with JWT authorization and error handling.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "fraud_analyst" | "data_engineer" | "compliance_auditor" | "viewer";
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Transaction {
  txn_id: string;
  account_id: string;
  customer_id: string;
  pan: string;
  email: string;
  phone: string;
  amount: number;
  currency: string;
  channel: string;
  status: string;
  fraud_score: number;
  txn_ts: string;
}

export interface FraudQueueItem {
  txn_id: string;
  account_id: string;
  customer_id: string;
  amount: number;
  channel: string;
  fraud_score: number;
  status: string;
  txn_ts: string;
  flagged_reasons: string[];
}

export interface ShapStep {
  feature_name: string;
  feature_value: number;
  contribution: number;
  cumulative_score: number;
  impact: string;
}

export interface FraudExplanation {
  txn_id: string;
  account_id?: string;
  customer_id?: string;
  amount?: number;
  channel?: string;
  pan_masked?: string;
  phone_masked?: string;
  txn_ts?: string;
  base_value: number;
  final_score: number;
  steps: ShapStep[];
}

export interface LineageNode {
  id: string;
  label: string;
  layer: string;
  table: string;
  pii_type: string;
}

export interface LineageEdge {
  source: string;
  target: string;
  type: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface GateAuditRun {
  batch_id: string;
  table_name: string;
  passed: boolean;
  records_scanned: number;
  residual_pii_count: number;
  signature: string;
  executed_at: string;
}

export interface DQCheck {
  check: string;
  layer: string;
  status: string;
  observed_value: any;
  threshold: any;
}

export interface DQScorecard {
  suite_name: string;
  overall_status: string;
  pass_rate_pct: number;
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  checks: DQCheck[];
  evaluated_at: string;
}

class ApiClient {
  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("sentraflow_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return headers;
  }

  async login(email: string, password: string): Promise<AuthTokens> {
    const res = await fetch(`${API_BASE_URL}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error(`Login failed: ${res.statusText}`);
    const data = await res.json();
    if (typeof window !== "undefined") {
      localStorage.setItem("sentraflow_token", data.access_token);
      localStorage.setItem("sentraflow_refresh", data.refresh_token);
    }
    return data;
  }

  async getMe(): Promise<UserProfile> {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch user profile`);
    return res.json();
  }

  async getTransactions(page: number = 1, pageSize: number = 20): Promise<{ total: number; items: Transaction[] }> {
    const res = await fetch(`${API_BASE_URL}/transactions?page=${page}&page_size=${pageSize}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch transactions`);
    return res.json();
  }

  async getFraudQueue(): Promise<FraudQueueItem[]> {
    const res = await fetch(`${API_BASE_URL}/fraud/queue`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch fraud queue`);
    return res.json();
  }

  async getFraudExplanation(txnId: string): Promise<FraudExplanation> {
    const res = await fetch(`${API_BASE_URL}/fraud/${txnId}/explanation`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch explanation for ${txnId}`);
    return res.json();
  }

  async overrideFraudDecision(txnId: string, decision: "CONFIRMED_FRAUD" | "FALSE_POSITIVE", notes: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/fraud/${txnId}/override`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ decision, notes }),
    });
    if (!res.ok) throw new Error(`Failed to submit override`);
    return res.json();
  }

  async getLineageGraph(): Promise<LineageGraph> {
    const res = await fetch(`${API_BASE_URL}/lineage/graph`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch lineage graph`);
    return res.json();
  }

  async getGateRuns(): Promise<GateAuditRun[]> {
    const res = await fetch(`${API_BASE_URL}/governance/gate-runs`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch gate audit runs`);
    return res.json();
  }

  async getDQScorecard(): Promise<DQScorecard> {
    const res = await fetch(`${API_BASE_URL}/dq/scorecard`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch DQ scorecard`);
    return res.json();
  }

  async triggerPipeline(dagId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/pipelines/trigger/${dagId}`, {
      method: "POST",
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to trigger pipeline`);
    return res.json();
  }
}

export const api = new ApiClient();

