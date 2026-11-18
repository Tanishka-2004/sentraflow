"""
Smoke and Integrity Tests for Next.js 14 Dashboard Architecture.

Verifies page definitions, App Router hierarchy, component exports,
and RBAC demo personas.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

DASHBOARD_DIR = Path("dashboard")


def test_dashboard_package_configuration() -> None:
    pkg_file = DASHBOARD_DIR / "package.json"
    assert pkg_file.exists()

    with open(pkg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    deps = data.get("dependencies", {})
    assert "@xyflow/react" in deps
    assert "recharts" in deps
    assert "next" in deps
    assert "react" in deps
    assert "lucide-react" in deps


def test_app_router_pages_exist() -> None:
    required_routes = [
        "src/app/layout.tsx",
        "src/app/page.tsx",
        "src/app/login/page.tsx",
        "src/app/fraud/page.tsx",
        "src/app/fraud/[id]/page.tsx",
        "src/app/lineage/page.tsx",
        "src/app/governance/page.tsx",
        "src/app/dq/page.tsx",
        "src/app/pipelines/page.tsx",
        "src/app/admin/page.tsx",
    ]

    for route in required_routes:
        p = DASHBOARD_DIR / route
        assert p.exists(), f"Missing required Next.js page route: {route}"


def test_dashboard_components_and_context() -> None:
    required_modules = [
        "src/components/Sidebar.tsx",
        "src/components/Header.tsx",
        "src/components/ShapWaterfall.tsx",
        "src/context/AuthContext.tsx",
        "src/lib/api.ts",
    ]

    for mod in required_modules:
        p = DASHBOARD_DIR / mod
        assert p.exists(), f"Missing required dashboard module: {mod}"

    # Verify 5 roles in AuthContext
    auth_ctx = (DASHBOARD_DIR / "src/context/AuthContext.tsx").read_text(encoding="utf-8")
    for role in ["admin", "fraud_analyst", "data_engineer", "compliance_auditor", "viewer"]:
        assert role in auth_ctx

