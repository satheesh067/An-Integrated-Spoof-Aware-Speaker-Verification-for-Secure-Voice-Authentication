"""Dependency-light regression checks for UI-related backend repairs."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api.input_validation import canonical_username, audio_suffix
from src.core.decision_engine import SASVDecisionEngine


class BackendRegressions(unittest.TestCase):
    def test_identifiers_cannot_escape_storage(self):
        for value in ("../escape", "C:\\escape", "a/b", "a\\b", "", "a" * 65, "CON", "lpt1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_username(value)
        self.assertEqual(canonical_username(" Speaker Alpha "), "speaker_alpha")
        self.assertEqual(audio_suffix("../../recording.WAV"), ".wav")
        with self.assertRaises(ValueError):
            audio_suffix("payload.exe")

    def test_missing_metadata_initializes_and_strict_gate_blocks(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "scratch") as directory:
            engine = SASVDecisionEngine(fusion_metadata_path=directory + "/missing.json", live_metadata_path=directory + "/missing-live.json")
            self.assertFalse(engine.has_fusion_model)
            self.assertTrue(engine.require_cm_gate)
            self.assertEqual(engine.evaluate_fusion(.99, -10).decision, "ACCESS_DENIED")
            original = vars(engine).copy()
            with self.assertRaises(ValueError):
                engine.apply_policy("unknown")
            self.assertEqual(vars(engine), original)

    def test_offline_metadata_and_policy_switch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "scratch") as directory:
            path = Path(directory) / "fusion.json"
            path.write_text(json.dumps({"weights": {"w_asv": 12, "w_cm": .2, "bias": -3}, "dev_metrics": {"eer_threshold": .7, "strict_security_threshold": 1.4}}))
            engine = SASVDecisionEngine(fusion_metadata_path=str(path), live_metadata_path=directory + "/missing.json", calibration_mode="offline_benchmark")
            self.assertEqual(engine.fusion_threshold, 1.4)
            engine.apply_policy("balanced")
            self.assertEqual(engine.fusion_threshold, .7)
            self.assertFalse(engine.require_cm_gate)
            engine.apply_policy("strict_security")
            self.assertTrue(engine.require_cm_gate)

    def test_existing_live_metadata(self):
        engine = SASVDecisionEngine()
        self.assertEqual(engine.calibration_source, "experimental_pilot_live_audio")
        engine.apply_policy("balanced")
        engine.apply_policy("strict_security")
        self.assertTrue(engine.require_cm_gate)


if __name__ == "__main__":
    unittest.main()
