"""
Unit Tests for SentraFlow Infrastructure, CI/CD, and Observability.

Verifies Terraform modular definitions, IAM least-privilege boundaries,
GitHub Actions workflow configurations, and Prometheus/Grafana schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

TF_DIR = Path("infra/terraform")
MONITORING_DIR = Path("monitoring")
CI_FILE = Path(".github/workflows/ci.yml")


def test_terraform_modules_exist() -> None:
    required_tf_files = [
        "main.tf",
        "variables.tf",
        "s3.tf",
        "glue.tf",
        "athena.tf",
        "iam.tf",
        "msk.tf",
        "outputs.tf",
    ]
    for fname in required_tf_files:
        p = TF_DIR / fname
        assert p.exists(), f"Missing Terraform file: {fname}"


def test_iam_least_privilege_boundaries() -> None:
    iam_tf = (TF_DIR / "iam.tf").read_text(encoding="utf-8")

    # 1. Gate role must have exclusive PutObject on Silver
    assert "spark_gate_role" in iam_tf
    assert "ExclusiveSilverPutObjectPermission" in iam_tf
    assert "silver" in iam_tf

    # 2. Gold role writes to Gold and reads Silver
    assert "spark_gold_role" in iam_tf
    assert "WriteGoldMarts" in iam_tf

    # 3. Analyst role queries Athena and reads Gold only
    assert "analyst_role" in iam_tf
    assert "ReadGoldOnly" in iam_tf
    assert "athena:StartQueryExecution" in iam_tf


def test_s3_lifecycle_and_encryption() -> None:
    s3_tf = (TF_DIR / "s3.tf").read_text(encoding="utf-8")
    assert "abort-incomplete-multipart" in s3_tf
    assert "GLACIER" in s3_tf
    assert "aws_kms_key" in s3_tf


def test_github_actions_ci_workflow() -> None:
    assert CI_FILE.exists()
    content = CI_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "jobs" in data
    jobs = data["jobs"]
    assert "lint-and-typecheck" in jobs
    assert "test-and-coverage" in jobs
    assert "dbt-compile-and-validate" in jobs
    assert "governance-gate-bypass-security-check" in jobs
    assert "terraform-validate" in jobs


def test_grafana_dashboard_schema() -> None:
    dash_file = MONITORING_DIR / "grafana_dashboard.json"
    assert dash_file.exists()

    with open(dash_file, "r", encoding="utf-8") as f:
        dash = json.load(f)

    assert "panels" in dash
    assert len(dash["panels"]) >= 10
    titles = [p.get("title", "") for p in dash["panels"]]
    assert any("Pipeline & Governance Health" in t for t in titles)
    assert any("Real-Time Fraud Engine" in t for t in titles)

