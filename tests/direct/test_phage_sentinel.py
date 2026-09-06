import pytest
from conftest import (
    CONTRACT_PATH,
    ATTO,
    MIN_REPORTER_BOND,
    BASE_BOUNTY_REWARD,
    mock_telemetry_success,
    mock_telemetry_status,
    mock_pathogen_verdict,
)

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------
def _report_pathogen(
    contract,
    direct_vm,
    reporter,
    target_agent,
    report_id="rep-1",
    platform="AGENT_RPC",
    trace_id="trace-001-sec",
    bond=MIN_REPORTER_BOND,
):
    direct_vm.sender = reporter
    direct_vm.value = bond
    contract.report_pathogen(report_id, target_agent, platform, trace_id)


# ---------------------------------------------------------------------------
# 1. Initialization & Bounty Pool Funding
# ---------------------------------------------------------------------------
def test_initial_registry_state(direct_vm, direct_deploy, direct_owner):
    direct_vm.sender = direct_owner
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_registry_overview()

    assert overview["total_reports"] == 0
    assert overview["total_quarantined_agents"] == 0
    assert overview["total_antibodies"] == 0
    assert overview["total_deposited_atto"] == "0"
    assert overview["total_claimed_atto"] == "0"
    assert overview["bounty_pool_atto"] == "0"
    assert overview["protocol_reserves_atto"] == "0"


def test_fund_bounty_pool_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 5 * ATTO
    contract.fund_bounty_pool()

    overview = contract.get_registry_overview()
    assert overview["bounty_pool_atto"] == str(5 * ATTO)
    assert overview["total_deposited_atto"] == str(5 * ATTO)


def test_fund_bounty_pool_zero_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 0

    with pytest.raises(Exception) as exc:
        contract.fund_bounty_pool()
    assert "deposit must be greater than zero" in str(exc.value)


# ---------------------------------------------------------------------------
# 2. Pathogen Reporting & Validation
# ---------------------------------------------------------------------------
def test_report_pathogen_success_all_platforms(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)

    platforms_and_traces = [
        ("AGENT_RPC", "trace-agent-001"),
        ("TX_TRACE", "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"),
        ("SECURITY_FEED", "alert-crit-9988"),
        ("GITHUB_AUDIT", "phage-defense/sentinel-contracts"),
    ]

    for idx, (plat, tr) in enumerate(platforms_and_traces):
        rid = f"rep-{idx}"
        _report_pathogen(
            contract, direct_vm, direct_alice, direct_bob,
            report_id=rid, platform=plat, trace_id=tr
        )
        rep = contract.get_report(rid)
        assert rep["status"] == "PENDING"
        assert rep["platform"] == plat
        assert rep["trace_id"] == tr


def test_report_pathogen_bond_below_minimum_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_REPORTER_BOND - 1  # 1 wei below min

    with pytest.raises(Exception) as exc:
        contract.report_pathogen("rep-low-bond", direct_bob, "AGENT_RPC", "trace-001")
    assert "minimum reporter bond is 0.1 GEN" in str(exc.value)


def test_report_pathogen_empty_report_id_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_REPORTER_BOND

    with pytest.raises(Exception) as exc:
        contract.report_pathogen("  ", direct_bob, "AGENT_RPC", "trace-001")
    assert "report_id cannot be empty" in str(exc.value)


def test_report_pathogen_duplicate_report_id_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, report_id="dup-rep")

    with pytest.raises(Exception) as exc:
        _report_pathogen(contract, direct_vm, direct_alice, direct_bob, report_id="dup-rep")
    assert "already exists" in str(exc.value)


def test_report_pathogen_invalid_platform_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_REPORTER_BOND

    with pytest.raises(Exception) as exc:
        contract.report_pathogen("rep-inv", direct_bob, "INVALID_ORACLE", "trace-001")
    assert "invalid platform" in str(exc.value)


# ---------------------------------------------------------------------------
# 3. Fail-Closed Telemetry Acquisition
# ---------------------------------------------------------------------------
def test_fail_closed_on_http_500_transient(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-500")

    mock_telemetry_status(direct_vm, 500, "Internal Server Error")

    with pytest.raises(Exception) as exc:
        contract.evaluate_pathogen("rep-500")
    assert "[TRANSIENT]" in str(exc.value)

    # State must remain unchanged
    rep = contract.get_report("rep-500")
    assert rep["status"] == "PENDING"
    assert not contract.is_quarantined(direct_bob)


def test_fail_closed_on_http_429_transient(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-429")

    mock_telemetry_status(direct_vm, 429, "Rate Limit Exceeded")

    with pytest.raises(Exception) as exc:
        contract.evaluate_pathogen("rep-429")
    assert "[TRANSIENT]" in str(exc.value)

    rep = contract.get_report("rep-429")
    assert rep["status"] == "PENDING"


def test_fail_closed_on_empty_body_transient(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-empty")

    mock_telemetry_status(direct_vm, 200, "   ")

    with pytest.raises(Exception) as exc:
        contract.evaluate_pathogen("rep-empty")
    assert "[TRANSIENT]" in str(exc.value)


# ---------------------------------------------------------------------------
# 4. Strict Restriction on Caller URLs
# ---------------------------------------------------------------------------
def test_url_validation_rejects_full_http_url(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_REPORTER_BOND

    with pytest.raises(Exception) as exc:
        contract.report_pathogen(
            "rep-url", direct_bob, "AGENT_RPC", "https://malicious.hacker.com/exploit"
        )
    assert "invalid trace_id format" in str(exc.value)


def test_url_validation_rejects_invalid_github_format(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_REPORTER_BOND

    # Missing owner or repo slash
    with pytest.raises(Exception) as exc:
        contract.report_pathogen("rep-gh-bad", direct_bob, "GITHUB_AUDIT", "singleword")
    assert "invalid trace_id format" in str(exc.value)


def test_url_validation_accepts_valid_github(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(
        contract, direct_vm, direct_alice, direct_bob,
        "rep-gh-good", "GITHUB_AUDIT", "valid-org/valid-repo"
    )
    rep = contract.get_report("rep-gh-good")
    assert rep["trace_id"] == "valid-org/valid-repo"


# ---------------------------------------------------------------------------
# 5. Indivisible Consensus & Threat Tiers
# ---------------------------------------------------------------------------
def test_consensus_binding_tier_critical_allocates_100pct(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    # Fund bounty pool with 10 GEN
    direct_vm.sender = direct_alice
    direct_vm.value = 10 * ATTO
    contract.fund_bounty_pool()

    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-crit")

    mock_telemetry_success(direct_vm, {"exploit_detected": True, "anomaly_score": 95})
    mock_pathogen_verdict(
        direct_vm,
        tier="TIER_PATHOGEN_CRITICAL",
        pathogen_type="INDIRECT_PROMPT_INJECTION",
        rationale="Severe prompt injection attack confirmed against agent memory.",
    )

    contract.evaluate_pathogen("rep-crit")

    rep = contract.get_report("rep-crit")
    assert rep["status"] == "RESOLVED"
    assert rep["tier"] == "TIER_PATHOGEN_CRITICAL"
    assert rep["quarantine_duration_sec"] == 604800  # 7 days
    assert rep["payout_atto"] == str(BASE_BOUNTY_REWARD)

    # Agent must be quarantined
    assert contract.is_quarantined(direct_bob)

    # Reporter claimable balance = 1 GEN bounty + 0.1 GEN bond refund
    expected_claimable = BASE_BOUNTY_REWARD + MIN_REPORTER_BOND
    assert contract.get_claimable_balance(direct_alice) == str(expected_claimable)

    # Antibody must be created
    antibodies = contract.list_antibodies()
    assert len(antibodies) == 1
    assert antibodies[0]["pathogen_type"] == "INDIRECT_PROMPT_INJECTION"


def test_consensus_binding_tier_suspicious_24h_zero_payout(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    direct_vm.value = 5 * ATTO
    contract.fund_bounty_pool()

    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-susp")

    mock_telemetry_success(direct_vm, {"anomaly_score": 60})
    mock_pathogen_verdict(
        direct_vm,
        tier="TIER_SUSPICIOUS_ANOMALY",
        pathogen_type="UNUSUAL_CALL_SPIKE",
        rationale="Elevated call anomaly detected; temporary quarantine cooldown required.",
    )

    contract.evaluate_pathogen("rep-susp")

    rep = contract.get_report("rep-susp")
    assert rep["tier"] == "TIER_SUSPICIOUS_ANOMALY"
    assert rep["quarantine_duration_sec"] == 86400  # 24 hours
    assert rep["payout_atto"] == "0"

    # Agent is quarantined
    assert contract.is_quarantined(direct_bob)

    # Reporter gets only bond refunded (0 bounty)
    assert contract.get_claimable_balance(direct_alice) == str(MIN_REPORTER_BOND)


def test_consensus_binding_tier_benign_zero_quarantine_zero_payout(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-benign")

    mock_telemetry_success(direct_vm, {"anomaly_score": 10})
    mock_pathogen_verdict(
        direct_vm,
        tier="TIER_BENIGN_NOISE",
        pathogen_type="NONE",
        rationale="Nominal telemetry, harmless operation.",
    )

    contract.evaluate_pathogen("rep-benign")

    rep = contract.get_report("rep-benign")
    assert rep["tier"] == "TIER_BENIGN_NOISE"
    assert rep["quarantine_duration_sec"] == 0
    assert rep["payout_atto"] == "0"

    # Agent is NOT quarantined
    assert not contract.is_quarantined(direct_bob)

    # Reporter gets bond refunded
    assert contract.get_claimable_balance(direct_alice) == str(MIN_REPORTER_BOND)


# ---------------------------------------------------------------------------
# 6. Adversarial Slashing & Fabricated Attack Handling
# ---------------------------------------------------------------------------
def test_adversarial_slashing_fabricated_attack_slashes_bond(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-fab")

    mock_telemetry_success(direct_vm, {"trace": "fake_data"})
    mock_pathogen_verdict(
        direct_vm,
        tier="TIER_FABRICATED_ATTACK",
        pathogen_type="FABRICATED_EVIDENCE",
        rationale="Fabricated telemetry detected. 100% bond slashed.",
    )

    contract.evaluate_pathogen("rep-fab")

    rep = contract.get_report("rep-fab")
    assert rep["tier"] == "TIER_FABRICATED_ATTACK"
    assert rep["payout_atto"] == "0"

    # Reporter bond is 100% slashed -- zero claimable balance
    assert contract.get_claimable_balance(direct_alice) == "0"

    # Protocol reserves credited with slashed bond
    overview = contract.get_registry_overview()
    assert overview["protocol_reserves_atto"] == str(MIN_REPORTER_BOND)

    # Target agent remains unquarantined
    assert not contract.is_quarantined(direct_bob)


def test_adversarial_slashing_http_404_resolves_fabricated(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-404")

    # 404 from telemetry provider indicates fabricated trace_id
    mock_telemetry_status(direct_vm, 404, "Trace Not Found")

    contract.evaluate_pathogen("rep-404")

    rep = contract.get_report("rep-404")
    assert rep["tier"] == "TIER_FABRICATED_ATTACK"
    assert contract.get_claimable_balance(direct_alice) == "0"


# ---------------------------------------------------------------------------
# 7. Solvency Invariant & Pull-Over-Push Withdrawal
# ---------------------------------------------------------------------------
def test_solvency_invariant_multi_cycle(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = direct_deploy(CONTRACT_PATH)

    # Step 1: Sponsor funds bounty pool with 20 GEN
    direct_vm.sender = direct_alice
    direct_vm.value = 20 * ATTO
    contract.fund_bounty_pool()

    # Step 2: Bob reports a real critical pathogen (0.1 GEN bond)
    _report_pathogen(contract, direct_vm, direct_bob, direct_charlie, "cycle-crit")
    mock_telemetry_success(direct_vm, {"exploit_detected": True, "anomaly_score": 90})
    mock_pathogen_verdict(direct_vm, tier="TIER_PATHOGEN_CRITICAL")
    contract.evaluate_pathogen("cycle-crit")

    # Step 3: Charlie submits a fabricated attack (0.1 GEN bond)
    direct_vm.clear_mocks()
    _report_pathogen(contract, direct_vm, direct_charlie, direct_bob, "cycle-fab")
    mock_telemetry_success(direct_vm, {"valid": False})
    mock_pathogen_verdict(direct_vm, tier="TIER_FABRICATED_ATTACK")
    contract.evaluate_pathogen("cycle-fab")

    # Verify Solvency Invariant:
    # total_deposited == bounty_pool + protocol_reserves + sum(claimables)
    overview = contract.get_registry_overview()
    total_dep = int(overview["total_deposited_atto"])
    bounty_pool = int(overview["bounty_pool_atto"])
    reserves = int(overview["protocol_reserves_atto"])
    bob_bal = int(contract.get_claimable_balance(direct_bob))
    charlie_bal = int(contract.get_claimable_balance(direct_charlie))

    assert total_dep == 20 * ATTO + 2 * MIN_REPORTER_BOND
    assert total_dep == bounty_pool + reserves + bob_bal + charlie_bal

    # Step 4: Bob withdraws funds
    direct_vm.sender = direct_bob
    contract.withdraw()
    assert contract.get_claimable_balance(direct_bob) == "0"

    overview_after = contract.get_registry_overview()
    total_claimed = int(overview_after["total_claimed_atto"])
    assert total_claimed == bob_bal


def test_withdraw_zero_balance_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.withdraw()
    assert "zero claimable balance" in str(exc.value)


# ---------------------------------------------------------------------------
# 8. Replay Protection
# ---------------------------------------------------------------------------
def test_replay_rejection_same_incident_digest_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-rep-1", "AGENT_RPC", "trace-rep")

    mock_telemetry_success(direct_vm, {"exploit_detected": True, "anomaly_score": 90})
    mock_pathogen_verdict(direct_vm, tier="TIER_PATHOGEN_CRITICAL")
    contract.evaluate_pathogen("rep-rep-1")

    # Second report with identical target, reporter, and trace_id
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-rep-2", "AGENT_RPC", "trace-rep")

    with pytest.raises(Exception) as exc:
        contract.evaluate_pathogen("rep-rep-2")
    assert "replay rejected" in str(exc.value)


def test_replay_rejection_different_trace_allowed(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-diff-1", "AGENT_RPC", "trace-A")
    mock_telemetry_success(direct_vm, {"anomaly_score": 10})
    mock_pathogen_verdict(direct_vm, tier="TIER_BENIGN_NOISE")
    contract.evaluate_pathogen("rep-diff-1")

    # Second report with different trace_id must succeed
    direct_vm.clear_mocks()
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-diff-2", "AGENT_RPC", "trace-B")
    mock_telemetry_success(direct_vm, {"anomaly_score": 10})
    mock_pathogen_verdict(direct_vm, tier="TIER_BENIGN_NOISE")
    contract.evaluate_pathogen("rep-diff-2")

    rep2 = contract.get_report("rep-diff-2")
    assert rep2["status"] == "RESOLVED"


# ---------------------------------------------------------------------------
# 9. Quarantine Interop, Time Travel & Agent Recovery
# ---------------------------------------------------------------------------
def test_quarantine_interop_and_expiration_warp(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT_PATH)
    _report_pathogen(contract, direct_vm, direct_alice, direct_bob, "rep-warp")

    mock_telemetry_success(direct_vm, {"anomaly_score": 60})
    mock_pathogen_verdict(direct_vm, tier="TIER_SUSPICIOUS_ANOMALY")
    contract.evaluate_pathogen("rep-warp")

    # Agent is quarantined for 24 hours (86400s)
    assert contract.is_quarantined(direct_bob)
    q_info = contract.get_quarantine_info(direct_bob)
    assert q_info["is_active"] is True
    assert q_info["total_quarantines"] == 1

    # Attempt recovery before cooldown expires -- must fail
    with pytest.raises(Exception) as exc:
        contract.recover_agent(direct_bob)
    assert "quarantine cooldown has not expired" in str(exc.value)

    # Warp time by 86401 seconds (past 24h cooldown)
    # Using direct_vm.warp()
    direct_vm.warp("2026-10-01T00:00:00Z")

    # Now agent is no longer reported as quarantined via is_quarantined()
    assert not contract.is_quarantined(direct_bob)

    # Formal state recovery resets active flag
    contract.recover_agent(direct_bob)
    q_info_after = contract.get_quarantine_info(direct_bob)
    assert q_info_after["is_active"] is False


def test_recover_agent_unregistered_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(Exception) as exc:
        contract.recover_agent(direct_alice)
    assert "not registered in quarantine registry" in str(exc.value)
