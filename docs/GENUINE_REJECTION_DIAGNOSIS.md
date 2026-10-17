# Genuine speech rejection diagnosis

The user's reported CM score was reproduced from `data/voices/testing/pawan/pawan_test_20261011_225024_ACCESS_DENIED.wav`.

| Input | Original upload CM | Calibrated preprocessing CM |
|---|---:|---:|
| Pawan response at 22:50:24 | -8.8592 | -5.8763 |
| Pawan response at 22:48:33 | -9.3665 | -6.1201 |

Small last-digit differences from the displayed score are normal across GPU runs. The unchanged strict CM threshold is -4.0694. Speaker similarities after calibrated preprocessing were 0.5776 and 0.6168, respectively, above the 0.3237 identity threshold. The remaining rejection is the countermeasure, not identity mismatch.

Root cause repaired: authentication's bytes branch bypassed peak normalization while enrollment and DEV calibration used AudioProcessor's normalization. Both paths now use the same processor. Original signal RMS/clipping measurements remain available, so normalization cannot make silent inputs pass the quality gate.

Capture repairs: microphone echo cancellation, noise suppression and automatic gain control are requested off. Native browser filtered resampling replaces box averaging when producing the 16 kHz WAV. These affect fresh recordings; previous processing artifacts cannot be undone in archived audio.

Silence trimming was measured but not adopted: it worsened these responses to -6.7788 and -8.1937 and changes the calibrated model input.

A global cutoff reduction is not a validated fix. The existing EVAL table reports genuine Beta at -6.2595, a target clone at -6.0606 and a target replay at -5.8459. A cutoff accepting the observed genuine sample also accepts those attacks. A new microphone trial is necessary after the capture repair; if genuine speech still fails, representative labelled live genuine/replay/synthetic data and model adaptation are required. The current pilot calibration does not establish reliable live microphone accuracy.

Evidence: scratch/anti_spoof_diagnosis.json and scratch/speech_bounds_diagnosis.json. Diagnostics only; these samples were not used to lower thresholds or train the countermeasure.


Fresh-capture follow-up: the user-confirmed recording at 22:56:09 (“calm sky 80”) scored CM +0.9457 and speaker similarity +0.4558 under the corrected preprocessing. Both passed the existing gates. Its original API attempt stopped at ASR and showed unavailable model scores; the base multilingual recognizer returned incorrect text. The English small.en model with beam size 5, temperature 0 and full precision has been validated against this exact recording. The expected random phrase is not supplied as an ASR prompt. Numeric matching is also repaired so “eighty one” cannot satisfy “80”.


Final model integration validation (`scripts/test_recorded_challenge.py`):
- Target challenge: calm sky 80. Recognized: Com sky eighty. The existing policy checks the target noun and number; the lead-in word remains optional.
- ACCESS_GRANTED: speaker 0.4558 >= 0.3237, CM 0.9457 >= -4.0694, fusion 2.4896 >= 0.5052.
- Processing: 1.94 seconds on this recorded trial.
- Consumed-nonce replay rejected. The same audio for calm sky 81 rejected for the incorrect number.
- Test fixture changes the phrase generator only in its separate test process. Production still issues random challenges and has no expected-phrase override endpoint.
- Evidence saved to scratch/recorded_challenge_validation.json. This validates the reported fresh recording, not population accuracy or all microphones.


Follow-up counterexample: blue door 37, recorded at 23:07:01, passed the spoken challenge and scored speaker 0.5988 and fusion 3.2903, but CM -4.8249 failed the unchanged -4.0694 gate. The audio was not clipped; RMS 0.0206, duration 3.24 seconds, normalization gain 6.7865. The previous bright bird 49 recording at 23:04:57 passed with CM -2.0948. This demonstrates residual phrase-dependent genuine rejection after the preprocessing and ASR repairs. The successful calm sky 80 test was a clip-specific regression, not proof that live authentication false rejection was fully resolved. Representative labelled microphone genuine and target replay/synthetic recordings, followed by separate validation, are needed before changing the countermeasure or its operating point. No global cutoff reduction has been applied on the basis of this sample.
