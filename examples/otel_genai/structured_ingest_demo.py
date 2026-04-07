#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "requests",
# ]
# ///
"""Structured Ingest Demo — ATIF + OpenHands + Native Format.

Sends realistic conversations to the Weave Agents structured ingest endpoints:
  POST /agents/conversations/ingest  (native Weave format)
  POST /agents/ingest/atif           (ATIF trajectory format)
  POST /agents/ingest/openhands      (OpenHands event stream format)

Usage:
  devall uv run examples/otel_genai/structured_ingest_demo.py
  devall uv run examples/otel_genai/structured_ingest_demo.py --project my-project
"""

import argparse
import os

import requests

DEFAULT_ENTITY = "ben-urmomsclothes"
DEFAULT_PROJECT = "genai-otel-test"


def _url():
    return os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345").rstrip("/")


def _auth():
    key = os.environ.get("WANDB_API_KEY", "")
    return ("api", key) if key else None


def post(endpoint, payload, project_id=None):
    """POST to trace server and print result."""
    url = f"{_url()}{endpoint}"
    params = {}
    if project_id:
        params["project_id"] = project_id
    print(f"  POST {url}" + (f"?project_id={project_id}" if project_id else ""))
    r = requests.post(url, json=payload, params=params, auth=_auth(), timeout=30)
    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text[:500]}")
        return {}
    d = r.json()
    print(
        f"  -> conv={d.get('conversation_id', '?')[:16]}…  "
        f"turns={len(d.get('trace_ids', []))}  spans={d.get('span_count', '?')}"
    )
    return d


# ---------------------------------------------------------------------------
# ATIF trajectories
# ---------------------------------------------------------------------------


def atif_financial_research():
    """Multi-turn financial agent: parallel tool calls, reasoning, metrics."""
    return {
        "schema_version": "ATIF-v1.4",
        "session_id": "atif-financial-001",
        "agent": {
            "name": "harbor-finance-agent",
            "version": "1.0.0",
            "model_name": "gemini-2.5-flash",
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-10-11T10:30:00Z",
                "source": "user",
                "message": "What is the current trading price of Alphabet (GOOGL) and how has it performed this quarter?",
            },
            {
                "step_id": 2,
                "timestamp": "2025-10-11T10:30:02Z",
                "source": "agent",
                "message": "I'll search for the current trading price and quarterly performance for GOOGL.",
                "reasoning_content": "The request requires two data points: current stock price and quarterly performance. I'll execute parallel tool calls.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_price_1",
                        "function_name": "financial_search",
                        "arguments": {"ticker": "GOOGL", "metric": "price"},
                    },
                    {
                        "tool_call_id": "call_perf_2",
                        "function_name": "financial_search",
                        "arguments": {
                            "ticker": "GOOGL",
                            "metric": "quarterly_performance",
                        },
                    },
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_price_1",
                            "content": "GOOGL is currently trading at $185.35 (Close: 10/11/2025). Day range: $183.20-$186.90. Volume: 1.5M shares.",
                        },
                        {
                            "source_call_id": "call_perf_2",
                            "content": "GOOGL Q3 2025 performance: +12.3% QoQ. Started Q3 at $165.00. 52-week high: $191.75. P/E ratio: 24.8.",
                        },
                    ]
                },
                "metrics": {
                    "prompt_tokens": 520,
                    "completion_tokens": 80,
                    "cached_tokens": 200,
                    "cost_usd": 0.00045,
                },
            },
            {
                "step_id": 3,
                "timestamp": "2025-10-11T10:30:05Z",
                "source": "agent",
                "message": "As of October 11, 2025, Alphabet (GOOGL) is trading at **$185.35** with daily volume of 1.5M shares.\n\n**Q3 2025 Performance:**\n- Quarter-over-quarter: **+12.3%** (from $165.00)\n- Near 52-week high of $191.75\n- P/E ratio: 24.8\n\nStrong quarterly momentum, outperforming the broader market.",
                "reasoning_content": "All data retrieved. Formatting a comprehensive response.",
                "metrics": {
                    "prompt_tokens": 600,
                    "completion_tokens": 95,
                    "cost_usd": 0.00033,
                },
            },
            {
                "step_id": 4,
                "timestamp": "2025-10-11T10:30:15Z",
                "source": "user",
                "message": "Compare that with MSFT and AAPL performance this quarter.",
            },
            {
                "step_id": 5,
                "timestamp": "2025-10-11T10:30:17Z",
                "source": "agent",
                "message": "Pulling quarterly performance for Microsoft and Apple.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_msft",
                        "function_name": "financial_search",
                        "arguments": {
                            "ticker": "MSFT",
                            "metric": "quarterly_performance",
                        },
                    },
                    {
                        "tool_call_id": "call_aapl",
                        "function_name": "financial_search",
                        "arguments": {
                            "ticker": "AAPL",
                            "metric": "quarterly_performance",
                        },
                    },
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_msft",
                            "content": "MSFT Q3 2025: +8.7% QoQ. Current: $445.20. P/E: 35.2. 52-week high: $468.35.",
                        },
                        {
                            "source_call_id": "call_aapl",
                            "content": "AAPL Q3 2025: +5.2% QoQ. Current: $235.80. P/E: 31.5. 52-week high: $243.90.",
                        },
                    ]
                },
                "metrics": {
                    "prompt_tokens": 850,
                    "completion_tokens": 65,
                    "cost_usd": 0.00052,
                },
            },
            {
                "step_id": 6,
                "timestamp": "2025-10-11T10:30:20Z",
                "source": "agent",
                "message": "**Q3 2025 Big Tech Comparison:**\n\n| Ticker | Q3 Return | Price | P/E |\n|--------|-----------|-------|-----|\n| **GOOGL** | **+12.3%** | $185.35 | 24.8 |\n| MSFT | +8.7% | $445.20 | 35.2 |\n| AAPL | +5.2% | $235.80 | 31.5 |\n\nAlphabet leads with the strongest return and most attractive valuation.",
                "metrics": {
                    "prompt_tokens": 920,
                    "completion_tokens": 120,
                    "cost_usd": 0.00061,
                },
            },
        ],
    }


def atif_coding_agent():
    """SWE-agent debugging pytest failures: system prompt, bash, file edits."""
    return {
        "schema_version": "ATIF-v1.4",
        "session_id": "atif-coding-002",
        "agent": {
            "name": "swe-agent",
            "version": "2.1.0",
            "model_name": "claude-3-5-sonnet-20241022",
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-10-12T14:00:00Z",
                "source": "system",
                "message": "You are an expert software engineer. Fix issues in the repository at /workspace.",
            },
            {
                "step_id": 2,
                "timestamp": "2025-10-12T14:00:01Z",
                "source": "user",
                "message": "The CI is failing. `pytest tests/test_auth.py` has 2 failures. Investigate and fix.",
            },
            {
                "step_id": 3,
                "timestamp": "2025-10-12T14:00:03Z",
                "source": "agent",
                "message": "Running the failing tests to see the errors.",
                "reasoning_content": "Reproduce failures first, then read code.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_run",
                        "function_name": "bash",
                        "arguments": {
                            "command": "cd /workspace && pytest tests/test_auth.py -v 2>&1 | tail -40"
                        },
                    }
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_run",
                            "content": "tests/test_auth.py::test_login_with_valid_token PASSED\ntests/test_auth.py::test_login_with_expired_token FAILED\ntests/test_auth.py::test_refresh_token PASSED\ntests/test_auth.py::test_logout PASSED\ntests/test_auth.py::test_password_reset FAILED\n\nFAILURES:\ntest_login_with_expired_token - AssertionError: Expected 401, got 200\ntest_password_reset - KeyError: 'reset_token'\n\n3 passed, 2 failed",
                        }
                    ]
                },
                "metrics": {"prompt_tokens": 1200, "completion_tokens": 45},
            },
            {
                "step_id": 4,
                "timestamp": "2025-10-12T14:00:08Z",
                "source": "agent",
                "message": "Reading the auth module to understand token validation.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_read",
                        "function_name": "bash",
                        "arguments": {"command": "cat /workspace/src/auth.py"},
                    }
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_read",
                            "content": 'import jwt\nimport datetime\n\nSECRET_KEY = "dev-secret"\n\ndef validate_token(token: str) -> dict:\n    try:\n        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])\n        return {"valid": True, "user": payload["sub"]}\n    except jwt.ExpiredSignatureError:\n        return {"valid": True, "user": "expired"}  # BUG\n    except jwt.InvalidTokenError:\n        return {"valid": False, "error": "invalid_token"}\n\ndef create_reset_token(email: str) -> dict:\n    payload = {"sub": email, "type": "reset"}\n    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")\n    return {"token": token}  # BUG: should be \'reset_token\'',
                        }
                    ]
                },
                "metrics": {"prompt_tokens": 1800, "completion_tokens": 38},
            },
            {
                "step_id": 5,
                "timestamp": "2025-10-12T14:00:12Z",
                "source": "agent",
                "message": "Found both bugs. Fixing:\n1. `validate_token` returns `valid=True` for expired tokens\n2. `create_reset_token` returns key `token` instead of `reset_token`",
                "reasoning_content": "Both straightforward: expired handler returns wrong valid flag, reset token dict key mismatches API contract.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_fix1",
                        "function_name": "file_edit",
                        "arguments": {
                            "path": "/workspace/src/auth.py",
                            "old": 'return {"valid": True, "user": "expired"}  # BUG',
                            "new": 'return {"valid": False, "error": "token_expired"}',
                        },
                    },
                    {
                        "tool_call_id": "call_fix2",
                        "function_name": "file_edit",
                        "arguments": {
                            "path": "/workspace/src/auth.py",
                            "old": "return {\"token\": token}  # BUG: should be 'reset_token'",
                            "new": 'return {"reset_token": token}',
                        },
                    },
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_fix1",
                            "content": "Applied edit to /workspace/src/auth.py (line 12)",
                        },
                        {
                            "source_call_id": "call_fix2",
                            "content": "Applied edit to /workspace/src/auth.py (line 19)",
                        },
                    ]
                },
                "metrics": {"prompt_tokens": 2100, "completion_tokens": 92},
            },
            {
                "step_id": 6,
                "timestamp": "2025-10-12T14:00:16Z",
                "source": "agent",
                "message": "Re-running tests to verify.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_rerun",
                        "function_name": "bash",
                        "arguments": {
                            "command": "cd /workspace && pytest tests/test_auth.py -v"
                        },
                    }
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_rerun",
                            "content": "tests/test_auth.py::test_login_with_valid_token PASSED\ntests/test_auth.py::test_login_with_expired_token PASSED\ntests/test_auth.py::test_refresh_token PASSED\ntests/test_auth.py::test_logout PASSED\ntests/test_auth.py::test_password_reset PASSED\n\n5 passed in 0.42s",
                        }
                    ]
                },
                "metrics": {"prompt_tokens": 2400, "completion_tokens": 30},
            },
            {
                "step_id": 7,
                "timestamp": "2025-10-12T14:00:20Z",
                "source": "agent",
                "message": "All 5 tests pass. Fixed:\n1. **Expired token** (auth.py:12): Now returns `valid=False`\n2. **Reset token key** (auth.py:19): Returns `reset_token` instead of `token`",
                "metrics": {"prompt_tokens": 2600, "completion_tokens": 110},
            },
        ],
    }


def atif_data_analysis():
    """Data analyst agent: SQL queries and chart generation."""
    return {
        "schema_version": "ATIF-v1.4",
        "session_id": "atif-data-003",
        "agent": {
            "name": "data-analyst",
            "version": "1.0.0",
            "model_name": "gpt-4o",
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-11-01T09:00:00Z",
                "source": "system",
                "message": "You are a data analyst with access to SQL and Python tools. The database has tables: orders, customers, products.",
            },
            {
                "step_id": 2,
                "timestamp": "2025-11-01T09:00:01Z",
                "source": "user",
                "message": "Show me revenue by product category for Q3 2025, and highlight any categories that grew more than 20% vs Q2.",
            },
            {
                "step_id": 3,
                "timestamp": "2025-11-01T09:00:04Z",
                "source": "agent",
                "message": "I'll query revenue by category for Q2 and Q3 to compare.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_sql",
                        "function_name": "sql_query",
                        "arguments": {
                            "query": "SELECT p.category, SUM(CASE WHEN o.created_at BETWEEN '2025-04-01' AND '2025-06-30' THEN o.total ELSE 0 END) as q2_revenue, SUM(CASE WHEN o.created_at BETWEEN '2025-07-01' AND '2025-09-30' THEN o.total ELSE 0 END) as q3_revenue FROM orders o JOIN products p ON o.product_id = p.id WHERE o.created_at BETWEEN '2025-04-01' AND '2025-09-30' GROUP BY p.category ORDER BY q3_revenue DESC"
                        },
                    }
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_sql",
                            "content": "category      | q2_revenue | q3_revenue\n--------------+------------+-----------\nElectronics   |   2,450,000|  3,120,000\nClothing      |   1,890,000|  2,340,000\nHome & Garden |     980,000|  1,250,000\nBooks         |     620,000|    710,000\nSports        |     450,000|    380,000",
                        }
                    ]
                },
                "metrics": {"prompt_tokens": 680, "completion_tokens": 55},
            },
            {
                "step_id": 4,
                "timestamp": "2025-11-01T09:00:08Z",
                "source": "agent",
                "message": "Now creating a comparison chart.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_chart",
                        "function_name": "python_exec",
                        "arguments": {
                            "code": "import matplotlib.pyplot as plt\ncategories = ['Electronics','Clothing','Home & Garden','Books','Sports']\nq2 = [2.45,1.89,0.98,0.62,0.45]\nq3 = [3.12,2.34,1.25,0.71,0.38]\ngrowth = [(q3[i]-q2[i])/q2[i]*100 for i in range(len(q2))]\nplt.figure(figsize=(10,6))\nx = range(len(categories))\nplt.bar([i-0.2 for i in x], q2, 0.4, label='Q2', color='#6366f1')\nplt.bar([i+0.2 for i in x], q3, 0.4, label='Q3', color='#22c55e')\nfor i,g in enumerate(growth):\n    if g > 20: plt.annotate(f'+{g:.0f}%', (i+0.2, q3[i]+0.05), fontweight='bold', color='green')\nplt.xticks(x, categories)\nplt.ylabel('Revenue ($M)')\nplt.title('Revenue by Category: Q2 vs Q3 2025')\nplt.legend()\nplt.savefig('/tmp/q3_revenue.png')\nprint('Chart saved')"
                        },
                    }
                ],
                "observation": {
                    "results": [
                        {"source_call_id": "call_chart", "content": "Chart saved"}
                    ]
                },
                "metrics": {"prompt_tokens": 1200, "completion_tokens": 120},
            },
            {
                "step_id": 5,
                "timestamp": "2025-11-01T09:00:12Z",
                "source": "agent",
                "message": "Here's the Q3 2025 revenue analysis:\n\n**Categories with 20%+ growth (Q2 → Q3):**\n- **Electronics**: $2.45M → $3.12M (**+27.3%**)\n- **Home & Garden**: $0.98M → $1.25M (**+27.6%**)\n- **Clothing**: $1.89M → $2.34M (**+23.8%**)\n\n**Below threshold:**\n- Books: $0.62M → $0.71M (+14.5%)\n- Sports: $0.45M → $0.38M (**-15.6%** — declining)\n\nTotal revenue grew from $6.39M to $7.80M (+22.1%). Sports is the only declining category and may warrant investigation.",
                "metrics": {"prompt_tokens": 1400, "completion_tokens": 150},
            },
        ],
    }


# ---------------------------------------------------------------------------
# OpenHands event streams
# ---------------------------------------------------------------------------


def openhands_fix_test():
    """OpenHands: agent fixes a failing test using file_editor and terminal."""
    return {
        "session_id": "oh-fix-test-001",
        "events": [
            {
                "id": 0,
                "timestamp": "2026-03-26T10:00:00Z",
                "source": "agent",
                "event_type": "system_prompt",
                "system_prompt": "You are a helpful coding assistant with access to terminal and file editor.",
            },
            {
                "id": 1,
                "timestamp": "2026-03-26T10:00:01Z",
                "source": "user",
                "event_type": "message",
                "content": "The test `test_basic_format` in `tests/test_utils.py` is failing. The `format_name` function should return `John Doe` for inputs `john`, `doe`, but the test expects `foo`. Fix the test.",
            },
            {
                "id": 2,
                "timestamp": "2026-03-26T10:00:02.5Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_view_test",
                "thought": "Let me look at the test file first.",
                "arguments": {
                    "command": "view",
                    "path": "/workspace/tests/test_utils.py",
                },
            },
            {
                "id": 3,
                "timestamp": "2026-03-26T10:00:03Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_view_test",
                "tool_name": "file_editor",
                "observation_content": "     1\timport unittest\n     2\tfrom src.utils import format_name\n     3\t\n     4\tclass TestFormatName(unittest.TestCase):\n     5\t    def test_basic_format(self):\n     6\t        result = format_name('john', 'doe')\n     7\t        self.assertEqual(result, 'foo')  # WRONG\n     8\t\n     9\t    def test_empty_input(self):\n    10\t        result = format_name('', '')\n    11\t        self.assertEqual(result, ' ')",
            },
            {
                "id": 4,
                "timestamp": "2026-03-26T10:00:04Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_view_src",
                "thought": "Line 7 expects 'foo'. Let me check the source to confirm the return value.",
                "arguments": {"command": "view", "path": "/workspace/src/utils.py"},
            },
            {
                "id": 5,
                "timestamp": "2026-03-26T10:00:04.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_view_src",
                "tool_name": "file_editor",
                "observation_content": 'def format_name(first: str, last: str) -> str:\n    """Format a full name."""\n    return f"{first.capitalize()} {last.capitalize()}"',
            },
            {
                "id": 6,
                "timestamp": "2026-03-26T10:00:05.5Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_fix",
                "thought": "Function returns 'John Doe'. Fixing the assertion.",
                "arguments": {
                    "command": "str_replace",
                    "path": "/workspace/tests/test_utils.py",
                    "old_str": "        self.assertEqual(result, 'foo')  # WRONG",
                    "new_str": "        self.assertEqual(result, 'John Doe')",
                },
            },
            {
                "id": 7,
                "timestamp": "2026-03-26T10:00:06Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_fix",
                "tool_name": "file_editor",
                "observation_content": "Edit applied successfully.",
            },
            {
                "id": 8,
                "timestamp": "2026-03-26T10:00:07Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "terminal",
                "tool_call_id": "call_test",
                "thought": "Running tests to verify.",
                "arguments": {
                    "command": "cd /workspace && python -m pytest tests/test_utils.py -v"
                },
            },
            {
                "id": 9,
                "timestamp": "2026-03-26T10:00:09Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_test",
                "tool_name": "terminal",
                "observation_content": "tests/test_utils.py::TestFormatName::test_basic_format PASSED  [33%]\ntests/test_utils.py::TestFormatName::test_empty_input PASSED   [66%]\ntests/test_utils.py::TestFormatName::test_single_name PASSED   [100%]\n\n3 passed in 0.02s",
            },
            {
                "id": 10,
                "timestamp": "2026-03-26T10:00:10Z",
                "source": "agent",
                "event_type": "message",
                "content": "Fixed the test. The assertion on line 7 expected `'foo'` but `format_name('john', 'doe')` returns `'John Doe'`. All 3 tests pass now.",
            },
        ],
    }


def openhands_deploy_feature():
    """OpenHands: multi-turn — add endpoint then enhance it on follow-up."""
    return {
        "session_id": "oh-deploy-002",
        "events": [
            {
                "id": 0,
                "timestamp": "2026-03-26T11:00:00Z",
                "source": "agent",
                "event_type": "system_prompt",
                "system_prompt": "Expert developer assistant with terminal and file editor tools.",
            },
            # --- Turn 1 ---
            {
                "id": 1,
                "timestamp": "2026-03-26T11:00:01Z",
                "source": "user",
                "event_type": "message",
                "content": 'Add a /health endpoint to our FastAPI app in src/main.py that returns {"status": "ok", "version": "1.2.0"}. Add a test too.',
            },
            {
                "id": 2,
                "timestamp": "2026-03-26T11:00:03Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_view",
                "thought": "Checking the current app structure.",
                "arguments": {"command": "view", "path": "/workspace/src/main.py"},
            },
            {
                "id": 3,
                "timestamp": "2026-03-26T11:00:03.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_view",
                "tool_name": "file_editor",
                "observation_content": 'from fastapi import FastAPI\n\napp = FastAPI(title="MyAPI", version="1.2.0")\n\n@app.get("/")\ndef root():\n    return {"message": "Welcome"}',
            },
            {
                "id": 4,
                "timestamp": "2026-03-26T11:00:05Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_add",
                "thought": "Adding the /health endpoint.",
                "arguments": {
                    "command": "insert",
                    "path": "/workspace/src/main.py",
                    "new_str": '\n@app.get("/health")\ndef health_check():\n    return {"status": "ok", "version": app.version}\n',
                },
            },
            {
                "id": 5,
                "timestamp": "2026-03-26T11:00:05.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_add",
                "tool_name": "file_editor",
                "observation_content": "Content inserted.",
            },
            {
                "id": 6,
                "timestamp": "2026-03-26T11:00:07Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_test_file",
                "thought": "Creating the test file.",
                "arguments": {
                    "command": "create",
                    "path": "/workspace/tests/test_health.py",
                    "file_text": 'from fastapi.testclient import TestClient\nfrom src.main import app\n\nclient = TestClient(app)\n\ndef test_health():\n    r = client.get("/health")\n    assert r.status_code == 200\n    assert r.json()["status"] == "ok"\n    assert r.json()["version"] == "1.2.0"\n',
                },
            },
            {
                "id": 7,
                "timestamp": "2026-03-26T11:00:07.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_test_file",
                "tool_name": "file_editor",
                "observation_content": "File created.",
            },
            {
                "id": 8,
                "timestamp": "2026-03-26T11:00:09Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "terminal",
                "tool_call_id": "call_run",
                "thought": "Running the test.",
                "arguments": {
                    "command": "cd /workspace && python -m pytest tests/test_health.py -v"
                },
            },
            {
                "id": 9,
                "timestamp": "2026-03-26T11:00:11Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_run",
                "tool_name": "terminal",
                "observation_content": "tests/test_health.py::test_health PASSED [100%]\n\n1 passed in 0.15s",
            },
            {
                "id": 10,
                "timestamp": "2026-03-26T11:00:12Z",
                "source": "agent",
                "event_type": "message",
                "content": 'Added `GET /health` returning `{"status": "ok", "version": "1.2.0"}` and a test. Passes.',
            },
            # --- Turn 2 ---
            {
                "id": 11,
                "timestamp": "2026-03-26T11:01:00Z",
                "source": "user",
                "event_type": "message",
                "content": "Nice! Also add a database connectivity check using `db.ping()` from `src/database.py`.",
            },
            {
                "id": 12,
                "timestamp": "2026-03-26T11:01:02Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_view_db",
                "thought": "Checking the database module.",
                "arguments": {"command": "view", "path": "/workspace/src/database.py"},
            },
            {
                "id": 13,
                "timestamp": "2026-03-26T11:01:02.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_view_db",
                "tool_name": "file_editor",
                "observation_content": 'import sqlalchemy\nengine = sqlalchemy.create_engine("sqlite:///app.db")\n\ndef ping() -> bool:\n    try:\n        with engine.connect() as conn:\n            conn.execute(sqlalchemy.text("SELECT 1"))\n        return True\n    except Exception:\n        return False',
            },
            {
                "id": 14,
                "timestamp": "2026-03-26T11:01:04Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "file_editor",
                "tool_call_id": "call_update",
                "thought": "Adding DB check to the health endpoint.",
                "arguments": {
                    "command": "str_replace",
                    "path": "/workspace/src/main.py",
                    "old_str": '@app.get("/health")\ndef health_check():\n    return {"status": "ok", "version": app.version}',
                    "new_str": '@app.get("/health")\ndef health_check():\n    from src.database import ping as db_ping\n    db_ok = db_ping()\n    return {"status": "ok" if db_ok else "degraded", "version": app.version, "database": db_ok}',
                },
            },
            {
                "id": 15,
                "timestamp": "2026-03-26T11:01:04.5Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_update",
                "tool_name": "file_editor",
                "observation_content": "Edit applied.",
            },
            {
                "id": 16,
                "timestamp": "2026-03-26T11:01:06Z",
                "source": "agent",
                "event_type": "action",
                "tool_name": "terminal",
                "tool_call_id": "call_run2",
                "thought": "Running all tests.",
                "arguments": {"command": "cd /workspace && python -m pytest tests/ -v"},
            },
            {
                "id": 17,
                "timestamp": "2026-03-26T11:01:08Z",
                "source": "environment",
                "event_type": "observation",
                "tool_call_id": "call_run2",
                "tool_name": "terminal",
                "observation_content": "tests/test_health.py::test_health PASSED      [25%]\ntests/test_main.py::test_root PASSED         [50%]\ntests/test_main.py::test_users PASSED        [75%]\ntests/test_auth.py::test_login PASSED        [100%]\n\n4 passed in 0.31s",
            },
            {
                "id": 18,
                "timestamp": "2026-03-26T11:01:09Z",
                "source": "agent",
                "event_type": "message",
                "content": 'Updated `/health` to include DB connectivity check. Returns `"database": true/false` and `"status": "degraded"` when DB is down. All 4 tests pass.',
            },
        ],
    }


# ---------------------------------------------------------------------------
# Native Weave format
# ---------------------------------------------------------------------------


def native_customer_support():
    """3-turn customer support with tool calls."""
    return {
        "conversation_name": "Order #12847 — shipping delay",
        "provider_name": "openai",
        "agent_name": "support-agent",
        "turns": [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful customer support agent. Be empathetic and solution-oriented.",
                    },
                    {
                        "role": "user",
                        "content": "Hi, I ordered a laptop 2 weeks ago (order #12847) and it still hasn't shipped. Can you help?",
                    },
                    {
                        "role": "assistant",
                        "content": "I'm sorry about the delay with order #12847. Let me look into this right away.",
                    },
                ],
                "tool_calls": [
                    {
                        "tool_name": "order_lookup",
                        "arguments": '{"order_id": "12847"}',
                        "result": '{"order_id": "12847", "product": "ThinkPad X1 Carbon Gen 12", "status": "processing", "placed_at": "2026-03-12", "estimated_ship": "2026-03-20", "reason_delayed": "backorder_component"}',
                        "duration_ms": 120,
                    },
                ],
                "model": "gpt-4o",
                "input_tokens": 180,
                "output_tokens": 95,
                "system_instructions": [
                    "You are a helpful customer support agent. Be empathetic and solution-oriented."
                ],
            },
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "That's frustrating. When will it actually ship?",
                    },
                    {
                        "role": "assistant",
                        "content": "I understand your frustration. The ThinkPad X1 Carbon was delayed due to a component backorder. The estimated ship date of March 20th has passed. Let me check current inventory and expedite options.",
                    },
                ],
                "tool_calls": [
                    {
                        "tool_name": "inventory_check",
                        "arguments": '{"sku": "TPX1C-G12", "warehouse": "west-coast-1"}',
                        "result": '{"available": true, "quantity": 3}',
                        "duration_ms": 85,
                    },
                    {
                        "tool_name": "shipping_options",
                        "arguments": '{"order_id": "12847", "priority": "expedited"}',
                        "result": '{"options": [{"method": "express_2day", "cost": 0, "arrival": "2026-03-28"}, {"method": "overnight", "cost": 15.99, "arrival": "2026-03-27"}]}',
                        "duration_ms": 95,
                    },
                ],
                "model": "gpt-4o",
                "input_tokens": 340,
                "output_tokens": 180,
            },
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Can you upgrade me to overnight shipping for free? This is really late.",
                    },
                    {
                        "role": "assistant",
                        "content": "Absolutely — given the delay, I've upgraded you to overnight at no charge.\n\n- **Order #12847**: ThinkPad X1 Carbon Gen 12\n- **Shipping**: Overnight (free upgrade)\n- **Ships**: Today, March 26\n- **Arrives**: March 27\n\nI've also applied a 10% discount on your next order. You'll get a shipping confirmation within the hour.",
                    },
                ],
                "tool_calls": [
                    {
                        "tool_name": "order_update",
                        "arguments": '{"order_id": "12847", "shipping_method": "overnight", "waive_cost": true, "next_order_discount": 0.10}',
                        "result": '{"success": true, "tracking": "1Z999AA10123456784", "arrives_at": "2026-03-27T12:00:00Z"}',
                        "duration_ms": 200,
                    },
                ],
                "model": "gpt-4o",
                "input_tokens": 520,
                "output_tokens": 210,
            },
        ],
    }


def native_research_assistant():
    """Single-turn research with multiple tool calls."""
    return {
        "conversation_name": "Climate change mitigation review",
        "provider_name": "anthropic",
        "agent_name": "research-assistant",
        "turns": [
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Summarize the top 3 most promising climate change mitigation technologies in 2025, with recent data on cost reduction trends.",
                    },
                    {
                        "role": "assistant",
                        "content": "Here's a summary of the top 3 climate mitigation technologies:\n\n**1. Solar PV + Battery Storage**\nSolar LCOE dropped to $24/MWh (down 12% YoY). Battery costs at $115/kWh, projected to hit $80 by 2027. Combined solar+storage now cheaper than new gas peakers in 90% of markets.\n\n**2. Green Hydrogen Electrolysis**\nCost fell to $3.50/kg (from $5.00 in 2023). New PEM electrolyzer efficiency at 74%. EU and US subsidies closing the gap with grey hydrogen ($1.50/kg). Break-even projected for 2028.\n\n**3. Direct Air Capture (DAC)**\nCost dropped from $600/ton to $350/ton CO₂. Climeworks' new Mammoth plant captures 36,000 tons/year. DOE funding $3.5B for regional DAC hubs. Target: $100/ton by 2030.",
                    },
                ],
                "tool_calls": [
                    {
                        "tool_name": "academic_search",
                        "arguments": '{"query": "solar PV cost reduction 2025 LCOE", "limit": 5}',
                        "result": "Top results: (1) IRENA 2025 Report: Global solar LCOE $24/MWh, (2) BloombergNEF: Solar costs down 12% YoY, (3) Nature Energy: Solar+storage beats gas peakers in 90% of markets",
                        "duration_ms": 450,
                    },
                    {
                        "tool_name": "academic_search",
                        "arguments": '{"query": "green hydrogen electrolysis cost 2025", "limit": 5}',
                        "result": "Top results: (1) IEA Hydrogen Report: Green H2 at $3.50/kg, (2) PEM efficiency reaches 74%, (3) EU/US subsidies analysis",
                        "duration_ms": 380,
                    },
                    {
                        "tool_name": "academic_search",
                        "arguments": '{"query": "direct air capture cost progress 2025", "limit": 5}',
                        "result": "Top results: (1) Climeworks Mammoth plant: 36k tons/yr, (2) DOE $3.5B DAC hubs, (3) Cost trajectory: $350/ton, target $100 by 2030",
                        "duration_ms": 410,
                    },
                ],
                "model": "claude-3-5-sonnet-20241022",
                "input_tokens": 450,
                "output_tokens": 380,
                "reasoning_content": "User wants a focused summary with data. I should search for each technology separately to get the most current cost figures, then synthesize into a clear comparison.",
            },
        ],
    }


def atif_financial_research_2():
    """Financial research with parallel tool calls via ATIF v1.5."""
    return {
        "schema_version": "ATIF-v1.5",
        "session_id": "025B810F-B3A2-4C67-93C0-FE7A142A947A",
        "agent": {
            "name": "harbor-agent",
            "version": "1.0.0",
            "model_name": "gemini-2.5-flash",
            "tool_definitions": [
                {
                    "type": "function",
                    "function": {
                        "name": "financial_search",
                        "description": "Search for financial data for a given stock ticker",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticker": {
                                    "type": "string",
                                    "description": "Stock ticker symbol",
                                },
                                "metric": {
                                    "type": "string",
                                    "description": "The financial metric to retrieve (e.g., price, volume)",
                                },
                            },
                            "required": ["ticker", "metric"],
                        },
                    },
                }
            ],
            "extra": {},
        },
        "notes": "Initial test trajectory for financial data retrieval using a single-hop ReAct pattern, focusing on multi-tool execution in Step 2.",
        "extra": {},
        "final_metrics": {
            "total_prompt_tokens": 1120,
            "total_completion_tokens": 124,
            "total_cached_tokens": 200,
            "total_cost_usd": 0.00078,
            "total_steps": 3,
            "extra": {},
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-10-11T10:30:00Z",
                "source": "user",
                "message": "What is the current trading price of Alphabet (GOOGL)?",
                "extra": {},
            },
            {
                "step_id": 2,
                "timestamp": "2025-10-11T10:30:02Z",
                "source": "agent",
                "model_name": "gemini-2.5-flash",
                "reasoning_effort": "medium",
                "message": "I will search for the current trading price and volume for GOOGL.",
                "reasoning_content": "The request requires two data points: the current stock price and the latest volume data. I will execute two simultaneous tool calls—one for price and one for volume—to retrieve this information in a single step.",
                "tool_calls": [
                    {
                        "tool_call_id": "call_price_1",
                        "function_name": "financial_search",
                        "arguments": {"ticker": "GOOGL", "metric": "price"},
                    },
                    {
                        "tool_call_id": "call_volume_2",
                        "function_name": "financial_search",
                        "arguments": {"ticker": "GOOGL", "metric": "volume"},
                    },
                ],
                "observation": {
                    "results": [
                        {
                            "source_call_id": "call_price_1",
                            "content": "GOOGL is currently trading at $185.35 (Close: 10/11/2025)",
                        },
                        {
                            "source_call_id": "call_volume_2",
                            "content": "GOOGL volume: 1.5M shares traded.",
                        },
                    ]
                },
                "metrics": {
                    "prompt_tokens": 520,
                    "completion_tokens": 80,
                    "cached_tokens": 200,
                    "cost_usd": 0.00045,
                },
            },
            {
                "step_id": 3,
                "timestamp": "2025-10-11T10:30:05Z",
                "source": "agent",
                "model_name": "gemini-2.5-flash",
                "reasoning_effort": "low",
                "message": "As of October 11, 2025, Alphabet (GOOGL) is trading at $185.35 with a volume of 1.5M shares traded.",
                "reasoning_content": "The previous step retrieved all necessary data. I will now format this into a final conversational response for the user and terminate the task.",
                "metrics": {
                    "prompt_tokens": 600,
                    "completion_tokens": 44,
                    "completion_token_ids": [
                        1722,
                        310,
                        5533,
                        1722,
                        13,
                        1640,
                        13,
                        1423,
                        13,
                        8425,
                        338,
                        313,
                        18672,
                        29,
                        338,
                        11302,
                        472,
                        395,
                        29896,
                        29945,
                        29945,
                        29889,
                        29941,
                        29945,
                        411,
                        263,
                        7977,
                        310,
                        29871,
                        29896,
                        29889,
                        29945,
                        29924,
                        29358,
                        3534,
                        287,
                        29889,
                    ],
                    "logprobs": [
                        -0.1,
                        -0.05,
                        -0.02,
                        -0.01,
                        -0.2,
                        -0.15,
                        -0.08,
                        -0.03,
                        -0.12,
                        -0.06,
                        -0.04,
                        -0.11,
                        -0.07,
                        -0.09,
                        -0.13,
                        -0.05,
                        -0.02,
                        -0.08,
                        -0.14,
                        -0.06,
                        -0.03,
                        -0.1,
                        -0.04,
                        -0.07,
                        -0.05,
                        -0.09,
                        -0.03,
                        -0.11,
                        -0.08,
                        -0.06,
                        -0.12,
                        -0.04,
                        -0.07,
                        -0.05,
                        -0.1,
                        -0.03,
                        -0.08,
                        -0.06,
                        -0.11,
                        -0.04,
                        -0.07,
                        -0.05,
                        -0.09,
                        -0.02,
                    ],
                    "cost_usd": 0.00033,
                    "extra": {"reasoning_tokens": 12},
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Structured ingest demo")
    parser.add_argument(
        "--entity", default=os.environ.get("WANDB_ENTITY", DEFAULT_ENTITY)
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    args = parser.parse_args()

    pid = f"{args.entity}/{args.project}"
    print(f"\n{'=' * 60}")
    print("Structured Ingest Demo")
    print(f"  Server: {_url()}")
    print(f"  Project: {pid}")
    print(f"{'=' * 60}\n")

    print("ATIF Trajectories")
    print("-" * 40)
    print("1. Financial research (parallel tool calls, 2 turns):")
    post("/agents/ingest/atif", atif_financial_research(), project_id=pid)
    print("\n2. SWE-agent debug (system prompt, bash+file_edit, 2 turns):")
    post("/agents/ingest/atif", atif_coding_agent(), project_id=pid)
    print("\n3. Data analyst (SQL+Python, chart generation):")
    post("/agents/ingest/atif", atif_data_analysis(), project_id=pid)

    print("\nOpenHands Event Streams")
    print("-" * 40)
    print("4. Fix failing test (file_editor+terminal):")
    post("/agents/ingest/openhands", openhands_fix_test(), project_id=pid)
    print("\n5. Add /health endpoint (multi-turn follow-up):")
    post("/agents/ingest/openhands", openhands_deploy_feature(), project_id=pid)

    print("\nNative Weave Format")
    print("-" * 40)
    print("6. Customer support (3-turn, order tools):")
    post("/agents/conversations/ingest", native_customer_support(), project_id=pid)
    print("\n7. Research assistant (multi-tool academic search):")
    post("/agents/conversations/ingest", native_research_assistant(), project_id=pid)
    print("\n8. Financial research (2-turn, parallel tool calls):")
    post("/agents/ingest/atif", atif_financial_research_2(), project_id=pid)

    print(f"\n{'=' * 60}")
    print("Done! 8 conversations ingested.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
