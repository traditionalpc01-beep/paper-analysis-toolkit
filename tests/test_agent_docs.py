from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_required_agent_docs_exist_and_have_expected_sections():
    required_docs = {
        "docs/ARCHITECTURE.md": ["# Agent-Friendly Architecture", "## 2. 模块分层"],
        "docs/PIPELINE_STAGES.md": ["# Pipeline Stages", "## Stage 5: 期刊与影响因子补全"],
        "docs/AGENT_WORKFLOW.md": ["# Agent Workflow", "## 3. 推荐提示词模板"],
        "docs/QUALITY_GATES.md": ["# Quality Gates", "## 6. 最小 harness 入口"],
        "docs/KNOWN_GAPS.md": ["# Known Gaps", "## 4. 容易产生 AI slop 的位置"],
        "docs/CODEX_AGENT_FIRST_PLAYBOOK.md": ["# Codex Agent-First 八步手册", "## Step 4：实现最小 harness"],
        "docs/agent_harness_issues.md": ["# Agent-First Phase 1 Issues", "## AH-005 Codex 八步交互手册"],
    }

    for rel_path, markers in required_docs.items():
        content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content


def test_agents_route_table_points_to_new_agent_docs():
    content = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for route in [
        "docs/ARCHITECTURE.md",
        "docs/PIPELINE_STAGES.md",
        "docs/AGENT_WORKFLOW.md",
        "docs/QUALITY_GATES.md",
        "docs/KNOWN_GAPS.md",
        "docs/CODEX_AGENT_FIRST_PLAYBOOK.md",
        "docs/agent_harness_issues.md",
        "scripts/check_agent_harness.py",
    ]:
        assert route in content
