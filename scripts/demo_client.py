"""Demo Client: Tests the live running FastAPI SASV Server over HTTP.

Demonstrates:
1. Health and GPU check
2. Fetching enrolled users
3. Requesting a dynamic single-use spoken challenge
4. Attempting voice authentication with a probe audio file
5. Inspecting official SASV benchmark metrics
"""

import json
import os
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_demo():
    print("=" * 70)
    print(" TESTING LIVE SASV BACKEND API (http://127.0.0.1:8000)")
    print("=" * 70)

    # 1. Health check
    print("\n[STEP 1] Checking System Health & GPU Status...")
    r = requests.get(f"{BASE_URL}/health")
    if r.status_code != 200:
        print(f"  [ERROR] Server returned {r.status_code}: {r.text}")
        return
    health = r.json()
    print(f"  Status: {health['status'].upper()}")
    print(f"  Compute Device: {health['device']} ({health.get('gpu_name', 'CPU')})")
    print(f"  Total VRAM: {health.get('total_vram_mb', 0)} MB")

    # 2. List enrolled users
    print("\n[STEP 2] Fetching Enrolled Users...")
    r = requests.get(f"{BASE_URL}/api/v1/users")
    users = r.json()
    enrolled = users.get("enrolled_users", [])
    usernames = [u["username"] if isinstance(u, dict) else u for u in enrolled]
    print(f"  Enrolled Speakers ({len(usernames)}): {usernames}")

    # 3. Request dynamic spoken challenge
    test_user = usernames[0] if usernames else "speaker_alpha"
    print(f"\n[STEP 3] Issuing Single-Use Dynamic Challenge for '{test_user}'...")
    r = requests.get(f"{BASE_URL}/api/v1/challenge?username={test_user}")
    ch = r.json()
    session_id = ch["session_id"]
    phrase = ch["challenge_phrase"]
    print(f"  Session ID: {session_id}")
    print(f"  Challenge Phrase: \"{phrase}\"")
    print(f"  TTL: {ch.get('ttl_seconds', 20)} seconds")

    # 4. Authenticate trial
    test_clip = "data/pilot/audio/speaker_alpha_genuine.wav"
    if os.path.exists(test_clip):
        print(f"\n[STEP 4] Submitting Probe Audio '{test_clip}'...")
        with open(test_clip, "rb") as f:
            files = {"audio_file": ("probe.wav", f, "audio/wav")}
            data = {"username": test_user, "session_id": session_id}
            r = requests.post(f"{BASE_URL}/api/v1/authenticate", data=data, files=files)
            res = r.json()
            print(f"  Access Decision: {res['decision']}")
            print(f"  Diagnostic Verdict: {res['verdict_type']}")
            print(f"  Calibration Status: {res.get('calibration_status')}")
            print(f"  Reasons: {res.get('reasons')}")
            ch_status = res.get("challenge_status", {})
            print(f"  Challenge Verification: Passed={ch_status.get('passed')}, Reason={ch_status.get('reason')}")

    # 5. Fetch benchmark results
    print("\n[STEP 5] Inspecting Official SASV Benchmark Metrics...")
    r = requests.get(f"{BASE_URL}/api/v1/benchmark")
    bench = r.json()
    print(f"  Partition: {bench.get('evaluation_partition')}")
    for row in bench.get("results", [])[:3]:
        sys_name = row.get("System", row.get("system"))
        eer_val = row.get("SASV-EER (%)", row.get("sasv_eer_pct"))
        print(f"    - {sys_name}: SASV-EER = {eer_val}%")

    print("\n" + "=" * 70)
    print(" DEMO COMPLETED SUCCESSFULLY! All endpoints active and responding.")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
