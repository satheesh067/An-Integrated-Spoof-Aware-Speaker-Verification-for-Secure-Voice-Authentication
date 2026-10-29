"""Comprehensive Backend Verification Suite.

Tests all core backend modules and FastAPI REST endpoints:
1. Multi-utterance speaker enrollment and template persistence.
2. Anti-spoof gate during enrollment (blocks enrollment of synthetic/replay clips).
3. Single-use dynamic spoken challenge generation and replay defense.
4. End-to-end voice authentication pipeline with genuine, impostor, and spoof cases.
5. FastAPI REST API endpoints using TestClient.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api.server import app, get_pipeline
from src.core.authentication_pipeline import AuthenticationPipeline
from src.core.challenge_manager import ChallengeManager
from src.core.enrollment_manager import EnrollmentManager


def test_enrollment_and_spoof_gate():
    print("\n[TEST 1] Testing Speaker Enrollment and Anti-Spoof Gate...")
    pipeline = get_pipeline()
    enroll_manager = pipeline.enrollment

    genuine_clip = "data/pilot/audio/speaker_alpha_enroll.wav"
    replay_clip = "data/pilot/audio/speaker_alpha_replay_spoof.wav"

    assert os.path.exists(genuine_clip), f"Missing genuine clip: {genuine_clip}"

    # 1. Enroll genuine speaker
    meta = enroll_manager.enroll_user("speaker_alpha", [genuine_clip], verify_authenticity=False)
    assert meta["username"] == "speaker_alpha"
    assert meta["embedding_dim"] == 192

    template = enroll_manager.get_template("speaker_alpha")
    assert template is not None
    assert template.shape == (192,)
    # Verify unit norm
    assert np.isclose(np.linalg.norm(template), 1.0, atol=1e-3)
    print("  [OK] Genuine speaker enrolled successfully. Voiceprint shape: (192,), Unit norm: OK.")

    # 2. Test Anti-Spoof gate on enrollment
    if os.path.exists(replay_clip):
        spoof_blocked = False
        try:
            enroll_manager.enroll_user("malicious_attacker", [replay_clip], verify_authenticity=True)
        except ValueError as e:
            if "failed anti-spoof verification" in str(e):
                spoof_blocked = True
        assert spoof_blocked, "Anti-spoof gate failed: Replay audio was improperly accepted during enrollment!"
        print("  [OK] Anti-spoof gate verified: Attack recording was correctly rejected during enrollment.")


def test_challenge_manager():
    print("\n[TEST 2] Testing Dynamic Challenge Generation and Replay Defense...")
    cm = ChallengeManager(ttl_seconds=5)

    # 1. Issue challenge
    ch = cm.issue_challenge("test_user")
    session_id = ch["session_id"]
    phrase = ch["challenge_phrase"]
    assert len(session_id) == 32
    assert len(phrase.split()) == 3
    print(f"  [OK] Issued Challenge Phrase: '{phrase}' (Session ID: {session_id[:8]}...)")

    # 2. Test phrase matching logic
    match_pct, matched, missing, number_matched = cm._calculate_phrase_match(phrase, phrase)
    assert match_pct == 100.0
    assert number_matched is True
    print("  [OK] Phrase matching exact token overlap: 100% OK (Number matched: True).")

    # 2b. Test lead-in start word buffer tolerance (mishearing word 1 does NOT fail match)
    p_tokens = phrase.split()
    misheard_first = f"garbled {p_tokens[1]} {p_tokens[2]}"
    m_pct_buf, _, _, num_m_buf = cm._calculate_phrase_match(phrase, misheard_first)
    assert m_pct_buf == 100.0, f"Expected 100% on target tokens, got {m_pct_buf}"
    assert num_m_buf is True
    print("  [OK] Lead-in word tolerance: Start word distortion did not degrade target verification.")

    # 3. Test number omission detection
    no_num_phrase = f"{p_tokens[0]} {p_tokens[1]}"
    m_pct, m_words, miss_words, num_m = cm._calculate_phrase_match(phrase, no_num_phrase)
    assert num_m is False, "Number omission must set number_matched to False!"
    print("  [OK] Security check: Number omission was correctly detected and flagged.")

    # 4. Simulate consumption and single-use enforcement
    dummy_audio = np.zeros(16000 * 2, dtype=np.float32)
    res1 = cm.verify_challenge(session_id, "test_user", dummy_audio)
    # The session is now consumed. An immediate second submission must be blocked!
    res2 = cm.verify_challenge(session_id, "test_user", dummy_audio)
    assert res2["passed"] is False
    assert "already been consumed" in res2["reason"]
    print("  [OK] Single-use enforcement verified: Immediate reuse blocked with replay defense.")


def test_authentication_pipeline():
    """Validates component execution flow and structured decision formatting.
    
    CRITICAL DISTINCTION:
    The relaxed pilot thresholds configured in this test suite are strictly intended
    for functional unit/integration sanity checks across the backend components.
    They DO NOT establish live biometric security performance, operational FAR/FRR,
    or attack resistance.
    Live operational thresholds must be calibrated via calibrate_live_pipeline.py,
    and offline benchmark evaluation is governed by the official SASV 2022 protocol.
    """
    pipeline = get_pipeline()
    # Validate default loaded operational policy directly from live_pipeline_metadata.json
    print(f"  Loaded Policy: Source={pipeline.decision_engine.calibration_source}, "
          f"Status={getattr(pipeline.decision_engine, 'calibration_status', 'UNKNOWN')}, "
          f"Th_Fusion={pipeline.decision_engine.fusion_threshold:+.3f}, "
          f"Th_ASV={pipeline.decision_engine.speaker_threshold:+.3f}, "
          f"Th_CM={pipeline.decision_engine.spoof_threshold:+.3f}")

    # Ensure speaker_alpha is enrolled
    pipeline.enrollment.enroll_user(
        "speaker_alpha",
        ["data/pilot/audio/speaker_alpha_enroll.wav"],
        verify_authenticity=False,
    )

    # Case A: Genuine speaker (tested in both fusion and tandem mode)
    res_gen = pipeline.authenticate(
        username="speaker_alpha",
        audio_source="data/pilot/audio/speaker_alpha_genuine.wav",
        require_challenge=False,
        decision_mode="fusion",
    )
    print(f"  Genuine Case (Fusion): Decision={res_gen.decision}, Verdict={res_gen.verdict_type}, "
          f"ASV={res_gen.speaker_score:+.3f}, CM={res_gen.spoof_score:+.3f}, Fused={res_gen.fused_score:+.3f}")
    assert res_gen.decision == "ACCESS_GRANTED"
    assert res_gen.verdict_type == "AUTHENTICATED", f"Expected 'AUTHENTICATED', got '{res_gen.verdict_type}'"
    assert res_gen.calibration_status == "EXPERIMENTAL_PILOT_ONLY", f"Expected EXPERIMENTAL_PILOT_ONLY, got {res_gen.calibration_status}"
    assert res_gen.calibration_source == "experimental_pilot_live_audio"
    assert res_gen.telemetry["calibration_status"] == "EXPERIMENTAL_PILOT_ONLY"

    res_gen_tandem = pipeline.authenticate(
        username="speaker_alpha",
        audio_source="data/pilot/audio/speaker_alpha_genuine.wav",
        require_challenge=False,
        decision_mode="tandem",
    )
    print(f"  Genuine Case (Tandem): Decision={res_gen_tandem.decision}, Verdict={res_gen_tandem.verdict_type}")
    assert res_gen_tandem.decision == "ACCESS_GRANTED"
    assert res_gen_tandem.verdict_type == "AUTHENTICATED", f"Expected 'AUTHENTICATED', got '{res_gen_tandem.verdict_type}'"
    assert res_gen_tandem.calibration_status == "EXPERIMENTAL_PILOT_ONLY"

    # Case B: Human Impostor
    res_imp = pipeline.authenticate(
        username="speaker_alpha",
        audio_source="data/pilot/audio/speaker_beta_impostor.wav",
        require_challenge=False,
        decision_mode="tandem",
    )
    print(f"  Impostor Case: Decision={res_imp.decision}, Verdict={res_imp.verdict_type}, "
          f"ASV={res_imp.speaker_score:+.3f}, CM={res_imp.spoof_score:+.3f}")
    assert res_imp.decision == "ACCESS_DENIED"

    # Case C: Replay Spoof
    res_spf = pipeline.authenticate(
        username="speaker_alpha",
        audio_source="data/pilot/audio/speaker_alpha_replay_spoof.wav",
        require_challenge=False,
        decision_mode="tandem",
    )
    print(f"  Replay Spoof Case: Decision={res_spf.decision}, Verdict={res_spf.verdict_type}, "
          f"ASV={res_spf.speaker_score:+.3f}, CM={res_spf.spoof_score:+.3f}")
    assert res_spf.decision == "ACCESS_DENIED"

    # Case D: Target Spoof Attack against Enrolled Identity (Target Voice Clone)
    # Tests that mandatory CM gate blocks attacks even when speaker similarity is high (+0.718)
    pipeline.enrollment.enroll_user(
        "speaker_beta",
        ["data/benchmark/eval/audio/spk_beta_enroll.wav"],
        verify_authenticity=False,
    )
    res_target_spf = pipeline.authenticate(
        username="speaker_beta",
        audio_source="data/benchmark/eval/audio/spk_beta_eval_synth_target.wav",
        require_challenge=False,
        decision_mode="fusion",
    )
    print(f"  Target Clone Attack (Fusion + Mandatory CM Gate): Decision={res_target_spf.decision}, "
          f"Verdict={res_target_spf.verdict_type}, ASV={res_target_spf.speaker_score:+.3f}, "
          f"CM={res_target_spf.spoof_score:+.3f}, Fused={res_target_spf.fused_score:+.3f}")
    assert res_target_spf.decision == "ACCESS_DENIED"
    assert res_target_spf.verdict_type == "SUSPECTED_SPOOF"
    print("  [OK] Mandatory Anti-Spoof Safeguard: High-similarity voice clone correctly blocked as 'SUSPECTED_SPOOF'.")
    print("  [OK] All test cases produced correct access decisions.")


def test_fastapi_endpoints():
    print("\n[TEST 4] Testing FastAPI REST Endpoints via TestClient...")
    client = TestClient(app)

    # 1. Health check
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    print(f"  [OK] GET /health: OK ({data.get('gpu_name', 'CPU')})")

    # 2. Challenge endpoint
    r = client.get("/api/v1/challenge?username=speaker_alpha")
    assert r.status_code == 200
    ch_data = r.json()
    assert "session_id" in ch_data
    assert "challenge_phrase" in ch_data
    print(f"  [OK] GET /api/v1/challenge: OK (Phrase: '{ch_data['challenge_phrase']}')")

    # 3. Users list
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    users_data = r.json()
    assert "enrolled_users" in users_data
    print(f"  [OK] GET /api/v1/users: OK ({len(users_data['enrolled_users'])} users enrolled)")

    # 4. Benchmark endpoint
    r = client.get("/api/v1/benchmark")
    assert r.status_code == 200
    bench_data = r.json()
    assert "results" in bench_data
    assert len(bench_data["results"]) >= 4
    print(f"  [OK] GET /api/v1/benchmark: OK ({len(bench_data['results'])} systems evaluated)")

    # 5. Policy Enforcement: Omitting session_id must be rejected
    with open("data/pilot/audio/speaker_alpha_genuine.wav", "rb") as f:
        files = {"audio_file": ("test.wav", f, "audio/wav")}
        data = {"username": "speaker_alpha"}
        r = client.post("/api/v1/authenticate", data=data, files=files)
        assert r.status_code == 422, "Omitting mandatory session_id must return 422 validation error!"
        print("  [OK] Security Policy: Omitting mandatory session_id was rejected with HTTP 422.")

    # 6. Dynamic Challenge Enforcement: Submit with valid challenge session
    ch_resp = client.get("/api/v1/challenge?username=speaker_alpha")
    session_id = ch_resp.json()["session_id"]
    with open("data/pilot/audio/speaker_alpha_genuine.wav", "rb") as f:
        files = {"audio_file": ("test.wav", f, "audio/wav")}
        data = {"username": "speaker_alpha", "session_id": session_id}
        r = client.post("/api/v1/authenticate", data=data, files=files)
        assert r.status_code == 200
        auth_data = r.json()
        # Since test.wav does not speak the fresh random phrase, it must be rejected as CHALLENGE_FAILED!
        assert auth_data["decision"] == "ACCESS_DENIED"
        assert auth_data["verdict_type"] == "CHALLENGE_FAILED"
        assert auth_data["calibration_status"] == "EXPERIMENTAL_PILOT_ONLY"
        assert auth_data["telemetry"]["calibration_status"] == "EXPERIMENTAL_PILOT_ONLY"
        print(f"  [OK] Liveness Defense: Prerecorded audio correctly rejected as '{auth_data['verdict_type']}'.")
        print(f"  [OK] Response Labeling: Verified calibration_status='{auth_data['calibration_status']}'.")

    # 7. Mandatory Anti-Spoof Gate on Enrollment Endpoint
    with open("data/pilot/audio/speaker_alpha_replay_spoof.wav", "rb") as f:
        files = [("files", ("replay.wav", f, "audio/wav"))]
        data = {"username": "test_spoof_attacker"}
        r_spoof = client.post("/api/v1/enroll", data=data, files=files)
        assert r_spoof.status_code == 400, f"Replay enrollment attack must return 400, got {r_spoof.status_code}"
        assert "failed anti-spoof verification" in r_spoof.json()["detail"]
        print("  [OK] Security Enforcement: POST /api/v1/enroll rejected spoof attack with HTTP 400.")

    with open("data/pilot/audio/speaker_alpha_enroll.wav", "rb") as f:
        files = [("files", ("genuine.wav", f, "audio/wav"))]
        data = {"username": "test_genuine_user"}
        r_gen = client.post("/api/v1/enroll", data=data, files=files)
        assert r_gen.status_code == 200, f"Genuine enrollment must return 200, got {r_gen.status_code}: {r_gen.text}"
        print("  [OK] Security Enforcement: POST /api/v1/enroll accepted genuine audio with HTTP 200.")


if __name__ == "__main__":
    print("=" * 78)
    print(" EXECUTING COMPREHENSIVE BACKEND VERIFICATION SUITE")
    print("=" * 78)

    test_enrollment_and_spoof_gate()
    test_challenge_manager()
    test_authentication_pipeline()
    test_fastapi_endpoints()

    print("\n" + "=" * 78)
    print(" ALL BACKEND VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 78)
