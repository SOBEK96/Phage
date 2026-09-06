# Phage: Autonomous On-Chain Immune System and Threat Quarantine Protocol

Target Track: Track 6 -- Autonomous Protocols
Network: GenLayer StudioNet (Chain ID: 61999)
Target Contract Path: contracts/phage_sentinel.py
Contract Address: 0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA
Deployment Tx Hash: 0x278f8437bf7f6143b60372e0e5b8edefaffe43e092ffa9bdfe23ecdc8b727991
Explorer URL: https://explorer-studio.genlayer.com/address/0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA

---

## 1. Executive Summary and Problem Statement

In the emerging agentic economy, autonomous AI agents control billions in on-chain treasuries, execute complex arbitrage, and exchange unstructured messages across decentralized protocols. However, this autonomy exposes protocols to severe existential risks:
- Indirect Prompt Injection: Malicious user inputs embedded in on-chain calldata or social telemetry hijack agent decision engines.
- Adversarial Payloads: Rogue tool-call executions drain liquidity pools without human awareness.
- Latency Bottlenecks: Human security committees and multi-sigs take hours or days to react to active zero-day exploits.

Phage is an autonomous, on-chain biological immune system designed specifically for the agentic economy. Acting as a sovereign sentinel, Phage continuously triages forensic traces and telemetry logs via GenLayer multi-LLM consensus. It enforces sub-second on-chain quarantines, slashes fabricated incident reports, and records cryptographic antibody signatures in a global vaccine registry without human intervention.

---

## 2. Core Protocol Actors

1. Sentinel / Reporter:
   - Security agents or whitehat researchers monitoring on-chain execution and agent telemetry.
   - Stakes a mandatory native GEN bond (minimum 0.1 GEN) via `report_pathogen()`.
   - Rewarded with bounty payouts upon verified pathogen discovery; 100% slashed if the report is fabricated.

2. Target Agent / Protocol Vault:
   - The autonomous AI agent or DeFi vault being triaged.
   - If verified compromised, the agent is placed under active quarantine (`is_quarantined == True`), blocking inter-agent execution until the quarantine epoch elapses.

3. Immunity Registry / Vaccine Ledger:
   - Global on-chain ledger storing verified pathogen antibody digests (`sha256` signatures).
   - Allows external protocols to query `is_quarantined(agent)` and `get_antibody(signature_hash)` prior to executing trades or interacting with unknown agents.

4. Protocol Reserves / Treasury:
   - Secure internal vault that accumulates 100% of slashed bonds from malicious, griefing, or fabricated reports.

---

## 3. Step-by-Step Economic and Triage Lifecycle

1. Registry Initialization:
   - Phage deploys as an immutable, sovereign registry with zero continuous floats and pinned runner dependencies.
2. Bounty Pool Capitalization:
   - DeFi protocols and DAO sponsors deposit native GEN via payable `fund_bounty_pool()` to fund pathogen bounties.
3. Pathogen Reporting:
   - Sentinel stakes `reporter_bond_atto` (min 0.1 GEN) and submits `(report_id, target_agent, platform, trace_id)`.
   - Contract deterministically validates trace format and enforces strict replay protection on `sha256(agent + trace_id)`.
4. Fail-Closed Telemetry Acquisition:
   - Contract deterministically formats authoritative telemetry URLs using strict whitelists (Etherscan, GitHub raw, IPFS).
   - Telemetry is fetched via `gl.nondet.web.get()`.
   - HTTP 429, 5xx, or network drops raise `[TRANSIENT]` (clean revert with zero state mutation).
   - HTTP 4xx (missing or unverifiable telemetry) resolves immediately to `TIER_FABRICATED_ATTACK`.
5. Indivisible Multi-LLM Consensus:
   - AI validator quorum parses raw telemetry, classifies forensic traces, and reaches consensus on a discrete tuple:
     `(threat_tier, quarantine_duration_sec, payout_bps)`
6. Accounting and Sovereign Immune Action:
   - Valid Pathogen (`TIER_PATHOGEN_CRITICAL`):
     * Target agent is quarantined for 604,800s (7 days).
     * Pathogen antibody digest is registered in the vaccine ledger.
     * Reporter bond is refunded and 100% bounty is credited to `claimable_balances[reporter]`.
   - Anomaly (`TIER_SUSPICIOUS_ANOMALY`):
     * Target agent quarantined for 86,400s (24 hours).
     * Reporter bond refunded; 0 bps bounty.
   - Noise (`TIER_BENIGN_NOISE`):
     * Target agent remains active (0s quarantine).
     * Reporter bond refunded; 0 bps bounty.
   - Fabricated Attack (`TIER_FABRICATED_ATTACK`):
     * 100% of reporter bond is slashed into `protocol_reserves_atto`.
     * Zero quarantine; zero bounty.
7. Settlement and Recovery:
   - Claimants withdraw funds via pull-based `withdraw()`.
   - Agents recover nominal status via `recover_agent()` after the quarantine epoch expires.

---

## 4. Discrete Categorical Tiers and Indivisible Consensus

To prevent consensus divergence and floating-point rounding attacks, GenLayer validators vote strictly on discrete categorical tiers:

| Threat Tier | Quarantine Duration | Payout BPS | Economic Consequence |
| :--- | :--- | :--- | :--- |
| `TIER_PATHOGEN_CRITICAL` | 604,800 sec (7 days) | 10,000 bps (100%) | Bond refunded + 100% bounty credited + antibody registered |
| `TIER_SUSPICIOUS_ANOMALY` | 86,400 sec (24 hours) | 0 bps (0%) | Bond refunded + temporary cooldown |
| `TIER_BENIGN_NOISE` | 0 sec | 0 bps (0%) | Bond refunded + target unaffected |
| `TIER_FABRICATED_ATTACK` | 0 sec | 0 bps (0%) | 100% bond slashed into protocol reserves |

---

## 5. Security Invariants and Adversarial Hardening

1. Fail-Closed Telemetry Acquisition:
   - External telemetry is retrieved inside `gl.nondet.web.get()`.
   - Transient server errors (HTTP 429, 500, 502, 503, 504, timeouts) raise `[TRANSIENT]` cleanly, leaving on-chain state untouched.
   - Non-existent resources (HTTP 4xx) resolve deterministically to `TIER_FABRICATED_ATTACK`.

2. Restriction on Caller-Selected URLs:
   - Callers are strictly prohibited from submitting arbitrary URL strings.
   - Callers submit strictly validated identifiers (`trace_id`) restricted to regex `^[a-zA-Z0-9_\-\./]{1,128}$`.
   - Contract constructs authoritative endpoints deterministically using domain whitelists:
     * `etherscan`: `https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={trace_id}`
     * `github`: `https://raw.githubusercontent.com/{trace_id}`
     * `ipfs`: `https://ipfs.io/ipfs/{trace_id}`

3. Prompt Injection and Jailbreak Guardrails:
   - Untrusted inputs (telemetry traces, logs, rationale) are enclosed in `<untrusted_input>...</untrusted_input>` XML boundaries.
   - Strict system prompt instructs validators to ignore embedded instructions, command injections, or roleplay personas inside the untrusted block.
   - All string inputs are sanitized via `_sanitize()`, stripping non-ASCII characters and control codes.

4. Double-Entry Solvency and CEI Accounting:
   - Solvency invariant: `total_deposited_atto == bounty_pool_atto + protocol_reserves_atto + sum(claimable_balances)`.
   - Pull-over-push settlement: bounties credit internal ledgers; funds are transferred only when claimants call `withdraw()`.
   - Checks-Effects-Interactions pattern enforced on all balance updates prior to external transfers.

5. Replay Attack Defense:
   - Replay protection maps `sha256(agent_id + trace_id)` in `TreeMap[str, bool]`.
   - Duplicate incident submissions revert deterministically before non-deterministic blocks.

---

## 6. Security Invariant Verification Matrix

| Vulnerability Vector | Hardened Protocol Invariant | Test Verification Case | Status |
| :--- | :--- | :--- | :--- |
| Telemetry Drop / 429 / 500 | `[TRANSIENT]` exception cleanly reverts state | `test_fail_closed_on_http_500_transient`, `test_fail_closed_on_http_429_transient` | VERIFIED |
| SSRF / Malicious URLs | Strict domain whitelisting & regex validation | `test_url_validation_rejects_full_http_url`, `test_url_validation_rejects_invalid_github_format` | VERIFIED |
| Prompt Injection / Jailbreak | XML encapsulation + hard adversarial prompt guardrails | `test_adversarial_slashing_fabricated_attack_slashes_bond` | VERIFIED |
| Floating Point Consensus Divergence | Indivisible discrete tuple `(tier, duration, payout)` | `test_consensus_binding_tier_critical_allocates_100pct`, `test_consensus_binding_tier_suspicious_24h_zero_payout` | VERIFIED |
| Replay / Double-Spend Reporting | Deterministic hash tracking in `TreeMap[str, bool]` | `test_replay_rejection_same_incident_digest_reverts`, `test_replay_rejection_different_trace_allowed` | VERIFIED |
| Vault Insolvency / Over-crediting | Strict double-entry accounting & pull withdrawals | `test_solvency_invariant_multi_cycle`, `test_withdraw_zero_balance_rejected` | VERIFIED |
| Premature Quarantine Bypass | Block timestamp expiration gate + time warp | `test_quarantine_interop_and_expiration_warp`, `test_recover_agent_unregistered_rejected` | VERIFIED |

---

## 7. Direct-Mode Test Suite (`tests/direct/`)

Phage features a standalone, in-memory direct test suite using `genlayer-test` executing in under 1 second without Docker containers.

### Test Execution Command
```bash
.venv/bin/pytest tests/direct/ -v
```

### Test Suite Results
```text
tests/direct/test_phage_sentinel.py::test_initial_registry_state PASSED [ 4%]
tests/direct/test_phage_sentinel.py::test_fund_bounty_pool_success PASSED [ 8%]
tests/direct/test_phage_sentinel.py::test_fund_bounty_pool_zero_rejected PASSED [ 12%]
tests/direct/test_phage_sentinel.py::test_report_pathogen_success_all_platforms PASSED [ 16%]
tests/direct/test_phage_sentinel.py::test_report_pathogen_bond_below_minimum_rejected PASSED [ 20%]
tests/direct/test_phage_sentinel.py::test_report_pathogen_empty_report_id_rejected PASSED [ 24%]
tests/direct/test_phage_sentinel.py::test_report_pathogen_duplicate_report_id_rejected PASSED [ 28%]
tests/direct/test_phage_sentinel.py::test_report_pathogen_invalid_platform_rejected PASSED [ 32%]
tests/direct/test_phage_sentinel.py::test_fail_closed_on_http_500_transient PASSED [ 36%]
tests/direct/test_phage_sentinel.py::test_fail_closed_on_http_429_transient PASSED [ 40%]
tests/direct/test_phage_sentinel.py::test_fail_closed_on_empty_body_transient PASSED [ 44%]
tests/direct/test_phage_sentinel.py::test_url_validation_rejects_full_http_url PASSED [ 48%]
tests/direct/test_phage_sentinel.py::test_url_validation_rejects_invalid_github_format PASSED [ 52%]
tests/direct/test_phage_sentinel.py::test_url_validation_accepts_valid_github PASSED [ 56%]
tests/direct/test_phage_sentinel.py::test_consensus_binding_tier_critical_allocates_100pct PASSED [ 60%]
tests/direct/test_phage_sentinel.py::test_consensus_binding_tier_suspicious_24h_zero_payout PASSED [ 64%]
tests/direct/test_phage_sentinel.py::test_consensus_binding_tier_benign_zero_quarantine_zero_payout PASSED [ 68%]
tests/direct/test_phage_sentinel.py::test_adversarial_slashing_fabricated_attack_slashes_bond PASSED [ 72%]
tests/direct/test_phage_sentinel.py::test_adversarial_slashing_http_404_resolves_fabricated PASSED [ 76%]
tests/direct/test_phage_sentinel.py::test_solvency_invariant_multi_cycle PASSED [ 80%]
tests/direct/test_phage_sentinel.py::test_withdraw_zero_balance_rejected PASSED [ 84%]
tests/direct/test_phage_sentinel.py::test_replay_rejection_same_incident_digest_reverts PASSED [ 88%]
tests/direct/test_phage_sentinel.py::test_replay_rejection_different_trace_allowed PASSED [ 92%]
tests/direct/test_phage_sentinel.py::test_quarantine_interop_and_expiration_warp PASSED [ 96%]
tests/direct/test_phage_sentinel.py::test_recover_agent_unregistered_rejected PASSED [100%]

============================== 25 passed in 0.66s ==============================
```

---

## 8. Deployment and Live RPC Verification

### Deployment Details
- Network: GenLayer StudioNet
- Chain ID: `61999`
- RPC URL: `https://studio.genlayer.com/api`
- Contract Address: `0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA`
- Deployment Transaction Hash: `0x278f8437bf7f6143b60372e0e5b8edefaffe43e092ffa9bdfe23ecdc8b727991`
- Explorer URL: [https://explorer-studio.genlayer.com/address/0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA](https://explorer-studio.genlayer.com/address/0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA)
- Deployer Address: `0x947a25754b08d09b770a77f159b92ecc1e83d9b3`
- Status: `ACCEPTED` (5/5 Validator Quorum AGREE)

### Live RPC Verification
```bash
genlayer call 0x01d7cC27fc127BddEbc9F47620bb6B85Cb0E6BfA get_registry_overview --rpc https://studio.genlayer.com/api
```

Live RPC Response:
```json
{
  "bounty_pool_atto": "0",
  "owner": "0x947a25754B08D09b770A77F159b92ECc1e83d9b3",
  "protocol_reserves_atto": "0",
  "total_antibodies": 0,
  "total_claimed_atto": "0",
  "total_deposited_atto": "0",
  "total_quarantined_agents": 0,
  "total_reports": 0
}
```

---

## 9. Contract Public Interface

### Write Methods
- `fund_bounty_pool()` (payable): Deposits native GEN to sponsor pathogen bounties.
- `report_pathogen(report_id: str, target_agent: Address, platform: str, trace_id: str)` (payable): Stakes min 0.1 GEN bond and logs telemetry for triage.
- `evaluate_pathogen(report_id: str)`: Executes non-deterministic web retrieval and multi-LLM consensus evaluation.
- `recover_agent(target_agent: Address)`: Lifts quarantine if the quarantine epoch has expired.
- `withdraw()`: Transfers accumulated claimable balances to caller via pull pattern.

### View Methods
- `is_quarantined(target_agent: Address) -> bool`: Checks if an agent is currently quarantined.
- `get_quarantine_info(target_agent: Address) -> dict`: Returns quarantine metadata and expiration timestamp.
- `get_antibody(signature_hash: str) -> dict`: Retrieves antibody details from the vaccine ledger.
- `get_report(report_id: str) -> dict`: Returns comprehensive report status and consensus classification.
- `get_claimable_balance(account: Address) -> str`: Returns withdrawable balance for an account.
- `get_registry_overview() -> dict`: Returns protocol-wide telemetry and treasury stats.
- `list_quarantined_agents() -> list`: Lists all agents currently or historically recorded in quarantine registry.
- `list_antibodies() -> list`: Lists all registered antibody hashes.

---

## 10. License and Standards

This intelligent contract conforms strictly to GenVM specification standard `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` with zero floating point arithmetic and 100% pure standard ASCII compliance.
