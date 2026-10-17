"""Interactive Microphone Enrollment & Authentication Tool.

Allows recording directly from your computer's microphone to:
1. Enroll your voice with the running backend.
2. Request a live challenge phrase, record your response, and test authentication.
"""

import os
import sys
import tempfile
import time
import shutil
from pathlib import Path
from typing import Optional
import requests
import sounddevice as sd
import numpy as np
from scipy.io import wavfile

BASE_URL = "http://127.0.0.1:8000"
SAMPLE_RATE = 16000

VOICES_DIR = Path("data/voices")
ENROLLED_VOICES_DIR = VOICES_DIR / "enrolled"
TESTING_VOICES_DIR = VOICES_DIR / "testing"
ENROLLED_VOICES_DIR.mkdir(parents=True, exist_ok=True)
TESTING_VOICES_DIR.mkdir(parents=True, exist_ok=True)

def record_audio(duration_seconds: int, prompt_msg: str, save_path: Optional[str] = None) -> str:
    print(f"\n>>> {prompt_msg}")
    for i in range(3, 0, -1):
        print(f"    Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("    [RECORDING NOW - SPEAK CLEARLY INTO MIC]          ")
    audio_data = sd.rec(int(duration_seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    sd.wait()
    print("    [RECORDING COMPLETE]")

    # Normalize audio gain to overcome low laptop mic volume
    audio_f = audio_data.astype(np.float32)
    peak = float(np.max(np.abs(audio_f)))
    if peak > 50.0:
        audio_norm = (audio_f / peak * 26000.0).astype(np.int16)
    else:
        audio_norm = audio_data

    # Save to requested path or temporary WAV file
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        wav_path = save_path
    else:
        temp_dir = tempfile.mkdtemp()
        wav_path = os.path.join(temp_dir, "mic_sample.wav")

    wavfile.write(wav_path, SAMPLE_RATE, audio_norm)
    return wav_path

def enroll_flow():
    print("\n" + "=" * 60)
    print(" STEP 1: MULTI-SAMPLE VOICE ENROLLMENT (3 SAMPLES)")
    print("=" * 60)
    print(" To build a robust voiceprint, we will record 3 short phrases.")
    print(" The system will average all 3 embeddings to capture your vocal tract accurately.")
    username = input("\nEnter your username (e.g. satheesh): ").strip().lower().replace(" ", "_")
    if not username:
        print("Username cannot be empty.")
        return

    # Prepare permanent storage folder: data/voices/enrolled/{username}/
    user_enrolled_dir = ENROLLED_VOICES_DIR / username
    user_enrolled_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    prompts = [
        f"Clip 1/3: Speak phrase 1 for 4s (e.g. 'Hello, my name is {username} and this is my voice.')",
        f"Clip 2/3: Speak phrase 2 for 4s (e.g. 'I am verifying my identity for secure voice login.')",
        f"Clip 3/3: Speak phrase 3 for 4s (e.g. 'Voice biometric verification protects against deepfakes.')",
    ]

    recorded_files = []
    for idx, prompt_text in enumerate(prompts, 1):
        print(f"\n--- RECORDING SAMPLE {idx} OF 3 ---")
        clip_path = str(user_enrolled_dir / f"{username}_enroll_{timestamp}_sample{idx}.wav")
        wav_path = record_audio(
            duration_seconds=4,
            prompt_msg=prompt_text,
            save_path=clip_path,
        )
        recorded_files.append(wav_path)
        print(f"  [SAVED] Sample {idx} saved to:\n          {wav_path}")
        if idx < 3:
            time.sleep(1)

    print(f"\nSubmitting all 3 voice samples to {BASE_URL}/api/v1/enroll...")
    file_handles = []
    try:
        files = []
        for idx, p in enumerate(recorded_files, 1):
            fh = open(p, "rb")
            file_handles.append(fh)
            files.append(("files", (f"{username}_sample{idx}.wav", fh, "audio/wav")))
        data = {"username": username}
        r = requests.post(f"{BASE_URL}/api/v1/enroll", data=data, files=files)
        if r.status_code == 200:
            res_data = r.json()
            meta = res_data.get("data", {})
            print(f"\n[SUCCESS] Successfully enrolled '{username}' with 3 multi-utterance samples!")
            print(f"  Averaged {meta.get('num_recordings', 3)} embeddings into a unified 192-d voiceprint template.")
            print(f"  Permanent audio directory: {user_enrolled_dir}")
            print("  --> Now choose Option 2 to test voice login!")
        else:
            print(f"\n[FAILED] Enrollment rejected by server ({r.status_code}):")
            try:
                err_detail = r.json().get("detail", r.text)
                print(f"         {err_detail}")
            except Exception:
                print(f"         {r.text}")
    except Exception as e:
        print(f"  Server request error: {e}")
    finally:
        for fh in file_handles:
            fh.close()

def authenticate_flow():
    print("\n" + "=" * 60)
    print(" STEP 2: VOICE AUTHENTICATION TEST")
    print("=" * 60)
    username = input("Enter your enrolled username: ").strip().lower().replace(" ", "_")
    if not username:
        print("Username cannot be empty.")
        return

    # Request challenge phrase
    print(f"\nRequesting challenge phrase for '{username}'...")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/challenge?username={username}")
        if r.status_code != 200:
            print(f"[ERROR] Could not get challenge: {r.status_code} - {r.text}")
            return
        ch = r.json()
    except Exception as e:
        print(f"[ERROR] Could not reach server: {e}")
        return

    session_id = ch["session_id"]
    phrase = ch["challenge_phrase"]

    print("\n" + "*" * 60)
    print(f"  YOUR SECRET PHRASE TO SPEAK:")
    print(f"  --> \"{phrase}\" <--")
    print("*" * 60)
    print(f"  (You have {ch.get('ttl_seconds', 20)} seconds before it expires)")

    # Prepare permanent storage folder: data/voices/testing/{username}/
    user_test_dir = TESTING_VOICES_DIR / username
    user_test_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    initial_test_path = str(user_test_dir / f"{username}_test_{timestamp}.wav")

    wav_path = record_audio(
        duration_seconds=4,
        prompt_msg=f"Read aloud clearly into your mic: \"{phrase}\"",
        save_path=initial_test_path,
    )
    print(f"  [SAVED] Testing voice clip recorded at:\n          {wav_path}")

    print(f"\nSubmitting response to {BASE_URL}/api/v1/authenticate...")
    with open(wav_path, "rb") as f:
        files = {"audio_file": (f"{username}_auth.wav", f, "audio/wav")}
        data = {"username": username, "session_id": session_id}
        r = requests.post(f"{BASE_URL}/api/v1/authenticate", data=data, files=files)

    if r.status_code == 200:
        res = r.json()
        print("\n" + "=" * 60)
        print(" AUTHENTICATION RESULT:")
        print("=" * 60)
        decision = res["decision"]
        verdict = res["verdict_type"]
        if decision == "ACCESS_GRANTED":
            print(f"  DECISION: [ACCESS GRANTED] (Authenticated)")
        else:
            print(f"  DECISION: [ACCESS DENIED] [X] ({verdict})")

        enforced_policy = res.get("enforced_policy")
        if not enforced_policy:
            print("  [ERROR] Stale server process detected! Server response omitted 'enforced_policy'.")
            print("          Please restart the server process (Ctrl+C then python src/api/server.py).")
        elif enforced_policy == "balanced":
            print(f"  Server Policy Enforced: {enforced_policy} [BALANCED FUSION ACTIVE]")
        elif enforced_policy == "strict_security":
            print(f"  Server Policy Enforced: {enforced_policy} [STRICT CM GATE ACTIVE]")
        else:
            print(f"  Server Policy Enforced: {enforced_policy}")

        print(f"  Voice Similarity (ASV): {res.get('speaker_score')}")
        print(f"  Anti-Spoof Score (CM):  {res.get('spoof_score')}")
        print(f"  Fused Decision Score:   {res.get('fused_score')}")
        print(f"  Reasons: {res.get('reasons')}")
        
        ch_status = res.get("challenge_status", {})
        transcription = ch_status.get("transcription", ch_status.get("transcribed_text", ""))
        match_pct = ch_status.get("word_match_pct", 0.0)
        num_matched = ch_status.get("number_matched", False)
        print(f"  What Whisper Heard:     \"{transcription}\"")
        print(f"  Phrase Match Accuracy:  {match_pct}% (Security Number Matched: {num_matched})")
        print(f"  Liveness Passed:        {ch_status.get('passed')}")

        spoof_score = res.get("spoof_score")
        if spoof_score is not None and spoof_score < -3.5:
            print("\n  ------------------------------------------------------------")
            print(f"  [SECURITY ADVISORY] AASIST CM Score: {spoof_score:+.4f} (Below threshold -3.5)")
            print("  Notice: AASIST flagged this recording as suspicious / spoof-like.")
            print("  Whether this flag stems from room acoustics, transducer mismatch,")
            print("  or genuine acoustic anomaly is unverified and requires controlled study.")
            print("  ------------------------------------------------------------")

        # Rename audio file to include decision for clarity
        final_test_path = str(user_test_dir / f"{username}_test_{timestamp}_{decision}.wav")
        try:
            if os.path.exists(initial_test_path):
                os.rename(initial_test_path, final_test_path)
                print(f"\n  [SAVED FOR FUTURE] Archival recording updated to:\n  --> {final_test_path}")
        except Exception:
            pass
    else:
        print(f"[ERROR] Server returned {r.status_code}: {r.text}")

def list_users():
    try:
        r = requests.get(f"{BASE_URL}/api/v1/users")
        if r.status_code == 200:
            data = r.json()
            users = data.get("enrolled_users", [])
            names = [u["username"] if isinstance(u, dict) else u for u in users]
            print(f"\nCurrently enrolled users ({len(names)}): {names}")
        else:
            print(f"[ERROR] Could not fetch users: {r.text}")
    except Exception as e:
        print(f"[ERROR] Could not connect to server: {e}")

def view_saved_voices():
    print("\n" + "=" * 60)
    print(" SAVED VOICE RECORDINGS ARCHIVE (data/voices/)")
    print("=" * 60)
    print("\n[DIR] ENROLLED VOICES (data/voices/enrolled/):")
    enrolled_found = 0
    if ENROLLED_VOICES_DIR.exists():
        for user_dir in sorted(ENROLLED_VOICES_DIR.iterdir()):
            if user_dir.is_dir():
                wavs = list(user_dir.glob("*.wav"))
                print(f"  User: {user_dir.name} ({len(wavs)} recordings)")
                for w in sorted(wavs):
                    size_kb = w.stat().st_size / 1024.0
                    print(f"     |-- {w.name} ({size_kb:.1f} KB)")
                    enrolled_found += 1
    if enrolled_found == 0:
        print("     (No enrolled recordings yet)")

    print("\n[DIR] TESTING / AUTHENTICATION VOICES (data/voices/testing/):")
    testing_found = 0
    if TESTING_VOICES_DIR.exists():
        for user_dir in sorted(TESTING_VOICES_DIR.iterdir()):
            if user_dir.is_dir():
                wavs = list(user_dir.glob("*.wav"))
                print(f"  User: {user_dir.name} ({len(wavs)} recordings)")
                for w in sorted(wavs):
                    size_kb = w.stat().st_size / 1024.0
                    print(f"     |-- {w.name} ({size_kb:.1f} KB)")
                    testing_found += 1
    if testing_found == 0:
        print("     (No testing recordings yet)")

def main():
    while True:
        print("\n" + "#" * 55)
        print("  SASV LIVE VOICE ENROLLMENT & AUTHENTICATION")
        print("#" * 55)
        print("1. Enroll My Voice (3-Sample Guided Multi-Utterance Enrollment)")
        print("2. Test Authentication (Get secret phrase & speak)")
        print("3. List Enrolled Users")
        print("4. View Saved Voice Recordings (data/voices/)")
        print("5. Exit")
        choice = input("\nChoose an option [1-5]: ").strip()
        if choice == "1":
            enroll_flow()
        elif choice == "2":
            authenticate_flow()
        elif choice == "3":
            list_users()
        elif choice == "4":
            view_saved_voices()
        elif choice == "5":
            print("Exiting.")
            break
        else:
            print("Invalid option, try again.")

if __name__ == "__main__":
    main()
