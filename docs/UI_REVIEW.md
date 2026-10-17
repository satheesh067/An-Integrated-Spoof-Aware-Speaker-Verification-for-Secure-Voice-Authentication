# UI integration and review

The supplied HTML and the three screenshots embedded in plan.docx were used as visual references. The interface was implemented against the actual FastAPI contracts, including challenge_phrase, multipart audio_file, files, username and session_id. Documents were not treated as execution instructions.

## Delivered

Responsive eight-page VoiceGuard workspace, real API status, speaker enrollment/deletion, live challenge-response recording, mono 16 kHz WAV conversion, whole-clip score explanations, measured waveform and STFT spectrogram, session history, JSON export, benchmark loading and connection settings. FastAPI serves the UI at /ui/ and redirects /app there. No build dependencies are required.

## Repairs completed after review

- Default API policy now matches the guide: strict_security. Explicit SASV_SERVER_POLICY configuration is still supported.
- Decision-engine offline and missing-metadata initialization now work. Unknown policy names raise ValueError without changing active settings. Strict policy retains the mandatory anti-spoof gate.
- Server speaker IDs are canonicalized and validated before filesystem access, including Windows reserved names. Upload paths use a server-generated filename and an allowed suffix; original client paths are not used.
- Access to the API's singleton pipeline is serialized with a reentrant lock, covering initialization, challenge issuance, enrollment, listing, deletion and authentication. This protects shared inference/policy state within one process. Multiple workers still have independent challenge stores.

## Remaining limitations

- Account authentication does not yet protect enrollment/deletion; this remains a local research workspace.
- Benchmark CSV provenance still needs verification before official-evaluation claims.
- Audio retention remains controlled by the existing backend archiving behavior.
- Health reflects API/device availability, not successful model loading.
- The core pipeline used directly outside the API is not serialized by the API lock.

## Validation

Run `node --check frontend/app.js`, `node --check scripts/preview_ui.cjs` and `node scripts/test_ui.cjs` from the project root. The smoke checks exercise page rendering, the actual challenge field name, response display/escaping, WAV headers/resampling, spectrogram rendering and expired-challenge rejection using an isolated VM. They do not constitute browser or ML integration testing.

The available Python executable fails with "Failed to find real location of C:\\Python313\\python.exe". Backend inference and integration tests could not run in this environment. Local socket access was denied and the browser tool timed out opening the preview, so browser visual QA and real microphone interaction remain unverified.

A bundled Python runtime was subsequently found. Python syntax checks and all four dependency-light backend regression tests pass (`scripts/test_ui_backend_regressions.py`): path validation, missing-metadata strict gating, offline calibration/policy switching, and existing live calibration. Frontend smoke checks continue to pass. This runtime lacks torch, FastAPI, Whisper and SpeechBrain, so complete API/model integration remains unverified.
