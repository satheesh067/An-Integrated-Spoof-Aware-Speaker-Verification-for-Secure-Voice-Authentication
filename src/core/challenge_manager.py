"""Dynamic Spoken Challenge and Liveness Manager.

Generates single-use, time-bound randomized spoken challenges.
Uses Whisper ASR to transcribe incoming audio and verify prompt compliance.
Defeats static audio replays and pre-synthesized attacks.
"""

import difflib
import hashlib
import hmac
import os
import random
import re
import secrets
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import whisper


# Everyday, easy-to-pronounce seed words for dynamic spoken challenges
ADJECTIVES = [
    "blue", "green", "red", "gold", "clear", "bright", "cool", "warm",
    "quick", "happy", "calm", "fresh", "sweet", "light", "pure", "true"
]
NOUNS = [
    "sky", "tree", "river", "star", "sun", "bird", "moon", "home",
    "door", "book", "ship", "hill", "lake", "park", "wave", "cloud"
]
VERBS = [
    "looks", "moves", "shines", "opens", "calls", "turns", "holds", "comes",
    "runs", "stays", "shows", "brings", "finds", "leads"
]
DIRECTIONS = [
    "up", "down", "in", "out", "left", "right", "near", "here"
]


class ChallengeManager:
    """Issues and validates single-use, time-bound spoken challenge prompts."""

    def __init__(
        self,
        ttl_seconds: int = 45,
        whisper_model_name: Optional[str] = None,
        server_secret: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.server_secret = (server_secret or os.getenv("SASV_SECRET_KEY") or secrets.token_hex(32)).encode()
        self.device = device or os.getenv("SASV_WHISPER_DEVICE", "cpu")

        # In-memory store for active nonces to enforce single-use
        # Format: {session_id: {"phrase": str, "username": str, "expires_at": float, "consumed": bool}}
        self.active_challenges: Dict[str, Dict] = {}

        # Lazy load Whisper
        self.whisper_model_name = whisper_model_name or os.getenv("SASV_WHISPER_MODEL", "small.en")
        self._whisper: Optional[whisper.Whisper] = None

    @property
    def whisper_model(self) -> whisper.Whisper:
        if self._whisper is None:
            print(f"Loading Whisper '{self.whisper_model_name}' on {self.device}...")
            self._whisper = whisper.load_model(self.whisper_model_name, device=self.device)
        return self._whisper

    def generate_phrase(self) -> str:
        """Generates a 3-token challenge: a lead-in word, a target security word, and a 2-digit number (e.g. 'clear star 95').
        
        The first word serves as an acoustic lead-in buffer to let the microphone and speaker gain stabilize.
        Verification requires matching the second word (target word) and the 2-digit number.
        """
        lead_word = random.choice(ADJECTIVES)
        target_word = random.choice(NOUNS)
        num = random.randint(11, 99)
        return f"{lead_word} {target_word} {num}"

    def issue_challenge(self, username: str) -> Dict:
        """Creates a signed, time-bound challenge session for a user."""
        self._cleanup_expired()

        session_id = secrets.token_hex(16)
        phrase = self.generate_phrase()
        now = time.time()
        expires_at = now + self.ttl_seconds

        # Cryptographic HMAC signature
        payload = f"{session_id}:{username}:{phrase}:{expires_at}"
        signature = hmac.new(self.server_secret, payload.encode(), hashlib.sha256).hexdigest()

        # Store in active nonces
        self.active_challenges[session_id] = {
            "session_id": session_id,
            "username": username.strip().lower(),
            "phrase": phrase,
            "expires_at": expires_at,
            "consumed": False,
        }

        return {
            "session_id": session_id,
            "username": username,
            "challenge_phrase": phrase,
            "expires_at": expires_at,
            "ttl_seconds": self.ttl_seconds,
            "signature": signature,
        }

    def verify_challenge(
        self,
        session_id: str,
        username: str,
        audio_input: np.ndarray,
        sample_rate: int = 16000,
    ) -> Dict:
        """Verifies that the provided audio speaks the issued challenge phrase within TTL."""
        now = time.time()
        record = self.active_challenges.get(session_id)

        # 1. Nonce existence check
        if not record:
            return {
                "passed": False,
                "reason": "Invalid or unknown session ID. Challenge must be requested before authentication.",
                "transcription": "",
                "word_match_pct": 0.0,
            }

        # 2. Single-use enforcement
        if record["consumed"]:
            return {
                "passed": False,
                "reason": "Replay Detected: This challenge token has already been consumed. Each phrase is single-use.",
                "transcription": "",
                "word_match_pct": 0.0,
            }

        # 3. User binding check
        if record["username"] != username.strip().lower():
            return {
                "passed": False,
                "reason": f"Session mismatch: Challenge was issued to '{record['username']}', not '{username}'.",
                "transcription": "",
                "word_match_pct": 0.0,
            }

        # 4. TTL expiration check
        if now > record["expires_at"]:
            record["consumed"] = True
            return {
                "passed": False,
                "reason": f"Challenge Expired: Response submitted {now - record['expires_at']:.1f}s after expiration.",
                "transcription": "",
                "word_match_pct": 0.0,
            }

        # Mark challenge as consumed immediately to prevent race-condition replays
        record["consumed"] = True

        # 5. Whisper ASR Transcription
        if audio_input.dtype != np.float32:
            audio_input = audio_input.astype(np.float32)

        t0 = time.perf_counter()
        # Whisper expects float32 1D audio normalized to [-1, 1]
        try:
            transcription_result = self.whisper_model.transcribe(
                audio_input,
                language="en",
                # Fixed beam decoding avoids stochastic temperature fallback on
                # short clips. Full precision avoids unstable half-precision ASR.
                fp16=False,
                temperature=0,
                beam_size=5,
                condition_on_previous_text=False,
                # Describe the grammar, never supply the expected security phrase.
                initial_prompt="An English voice challenge: an adjective, a noun, and a number from eleven to ninety-nine.",
            )
        except Exception as e:
            if "cuda" in str(e).lower() or "accelerator" in str(e).lower():
                print(f"[WARN] Whisper GPU transcription encountered CUDA issue ({e}). Falling back to CPU...", flush=True)
                self.whisper_model = whisper.load_model(self.whisper_model_name, device="cpu")
                transcription_result = self.whisper_model.transcribe(
                    audio_input,
                    language="en",
                    fp16=False,
                    temperature=0,
                    beam_size=5,
                    condition_on_previous_text=False,
                    initial_prompt="An English voice challenge: an adjective, a noun, and a number from eleven to ninety-nine.",
                )
            else:
                raise
        asr_latency_ms = (time.perf_counter() - t0) * 1000
        transcribed_text = transcription_result.get("text", "").strip()

        # 6. Word-level and numeric fuzzy similarity matching
        target_phrase = record["phrase"]
        match_pct, matched_words, missing_words, number_matched = self._calculate_phrase_match(target_phrase, transcribed_text)

        # Security rule: Token match must be >= 60% AND the random numeric code MUST be present
        if not number_matched:
            passed = False
            reason = f"Challenge Failed: Missing required 2-digit security number from spoken phrase ('{transcribed_text}')."
        elif match_pct < 60.0:
            passed = False
            reason = f"Spoken phrase mismatch ({match_pct:.1f}% match: '{transcribed_text}' vs expected '{target_phrase}')."
        else:
            passed = True
            reason = "Challenge passed: Spoken phrase and security number verified."

        return {
            "passed": passed,
            "target_phrase": target_phrase,
            "transcription": transcribed_text,
            "word_match_pct": round(match_pct, 2),
            "number_matched": number_matched,
            "matched_words": matched_words,
            "missing_words": missing_words,
            "asr_latency_ms": round(asr_latency_ms, 2),
            "asr_model": self.whisper_model_name,
            "asr_decoding": "beam5_temperature0_fp32",
            "reason": reason,
        }

    def _calculate_phrase_match(self, expected: str, actual: str) -> Tuple[float, List[str], List[str], bool]:
        """Calculates token overlap and explicitly verifies presence of the challenge number.
        
        Note: Passing transcription confirms prompt compliance against static recordings;
        it does not, by itself, prove physical human presence against live responsive synthesis.
        """
        # Normalize: lower, strip non-alphanumeric except spaces
        norm_expected = re.sub(r"[^a-z0-9\s]", " ", expected.lower()).split()
        norm_actual = re.sub(r"[^a-z0-9\s]", " ", actual.lower()).split()

        # Identify target number (the last token in our generator)
        target_number = None
        for tok in norm_expected:
            if tok.isdigit():
                target_number = tok
                break

        # Parse complete numeric tokens. Matching substrings or just the tens
        # word made "eighty one" incorrectly satisfy a challenge for "80".
        units = {w: i for i, w in enumerate(['zero','one','two','three','four','five','six','seven','eight','nine'])}
        teens = {w: i+10 for i, w in enumerate(['ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen'])}
        tens = dict(zip(['twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety'],range(20,100,10)))
        spoken_numbers = set()
        i = 0
        while i < len(norm_actual):
            tok = norm_actual[i]
            if tok.isdigit():
                spoken_numbers.add(str(int(tok)))
            elif tok in tens:
                value = tens[tok]
                if i+1 < len(norm_actual) and norm_actual[i+1] in units and units[norm_actual[i+1]] > 0:
                    i += 1
                    value += units[norm_actual[i]]
                spoken_numbers.add(str(value))
            elif tok in teens:
                spoken_numbers.add(str(teens[tok]))
            elif tok in units:
                spoken_numbers.add(str(units[tok]))
            i += 1

        WORD_ALIASES = {
            "road": ["route", "rode", "roads"],
            "sun": ["son"],
            "blue": ["blew"],
            "red": ["read"],
            "star": ["start", "stars"],
            "sea": ["see"],
            "here": ["hear"],
        }

        matched = []
        missing = []
        actual_text = " ".join(norm_actual)
        number_matched = False

        for w in norm_expected:
            is_num_token = (w == target_number)
            is_found = False

            if is_num_token:
                is_found = target_number in spoken_numbers
            elif w in norm_actual or w in actual_text:
                is_found = True
            elif any(alias in norm_actual or alias in actual_text for alias in WORD_ALIASES.get(w, [])):
                is_found = True
            elif any(difflib.SequenceMatcher(None, w, act_tok).ratio() >= 0.60 for act_tok in norm_actual):
                is_found = True

            if is_found:
                matched.append(w)
                if is_num_token:
                    number_matched = True
            else:
                missing.append(w)

        # If phrase has 3 tokens (e.g. 'clear star 95'), the first word is an acoustic lead-in buffer;
        # verification evaluates only the required target word and 2-digit number (norm_expected[1:]).
        if len(norm_expected) >= 3:
            required_tokens = norm_expected[1:]
            required_matched = [w for w in matched if w in required_tokens]
            match_pct = (len(required_matched) / len(required_tokens)) * 100.0
        else:
            match_pct = (len(matched) / max(len(norm_expected), 1)) * 100.0
        return match_pct, matched, missing, number_matched

    def _cleanup_expired(self):
        """Removes expired nonces older than 2 minutes."""
        now = time.time()
        to_del = [sid for sid, r in self.active_challenges.items() if now > (r["expires_at"] + 120)]
        for sid in to_del:
            del self.active_challenges[sid]


if __name__ == "__main__":
    cm = ChallengeManager()
    ch = cm.issue_challenge("test_user")
    print("Issued Challenge:", ch)
    # Test matching logic
    target = ch["challenge_phrase"]
    print("Simulated Whisper transcript:", target)
    # Check matching with dummy audio array (simulate match calculation)
    match_pct, matched, missing = cm._calculate_phrase_match(target, target.upper() + "!")
    print(f"Match: {match_pct}% (Matched: {matched}, Missing: {missing})")
