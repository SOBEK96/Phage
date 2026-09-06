import json
import pytest

CONTRACT_PATH = "contracts/phage_sentinel.py"
PROMPT_PATTERN = r".*Security Triage Sentinel.*"

ATTO = 10**18
MIN_REPORTER_BOND = ATTO // 10
BASE_BOUNTY_REWARD = 1 * ATTO


def mock_telemetry_success(direct_vm, body_dict: dict):
    direct_vm.mock_web(
        r".*",
        {
            "status": 200,
            "body": json.dumps(body_dict),
        },
    )


def mock_telemetry_status(direct_vm, status: int, body: str = ""):
    direct_vm.mock_web(
        r".*",
        {
            "status": status,
            "body": body,
        },
    )


def mock_pathogen_verdict(
    direct_vm,
    tier: str = "TIER_PATHOGEN_CRITICAL",
    pathogen_type: str = "PROMPT_INJECTION",
    rationale: str = "Active exploit confirmed from forensic logs.",
):
    direct_vm.mock_llm(
        PROMPT_PATTERN,
        json.dumps({
            "tier": tier,
            "pathogen_type": pathogen_type,
            "rationale": rationale,
        }),
    )
