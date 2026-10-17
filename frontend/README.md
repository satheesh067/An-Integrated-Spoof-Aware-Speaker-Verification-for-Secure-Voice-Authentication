# VoiceGuard workspace

Run `./start_project.ps1` from the project root and open http://127.0.0.1:8000/ui/ . The launcher warms ECAPA, AASIST and Whisper; the browser UI needs no build step.

Select an enrolled identity, generate a fresh challenge, record the entire phrase, stop and click Verify voice within 45 seconds. The server applies its calibrated policy. Processing and errors are visible in the workspace. Results and history are held in the current browser tab.

New successful enrollments save a confirmed reference WAV. Older identities need re-enrollment to establish a reference; archived recordings are not automatically treated as approved samples. Reference and response waveforms use complete min/max sample bins on a fixed amplitude scale with independent time axes in seconds. Red shading marks clipping at peak amplitude 0.99 or higher. Amber marks 100 ms windows with RMS below 0.003. These are signal quality diagnostics, not segment-level speaker or spoof predictions. Different spoken phrases naturally have different waveforms.

Browser recording and uploads are converted to mono 16 kHz PCM WAV for verification. Microphone access requires localhost or HTTPS. Backend inference uses worker threads so health and static UI requests remain responsive. The backend archives probes; deletion removes voiceprints, not archived recordings.

Validation: `node scripts/test_ui.cjs` and `.venv/Scripts/python.exe scripts/test_ui_backend_regressions.py`.

The calibrated models remain experimental pilot models. Raw scores are not confidence probabilities, and the waveform cannot guarantee identity or authenticity.

Genuine-rejection repair: browser uploads now share enrollment/calibration peak normalization. Browser capture requests echo cancellation, noise suppression and auto gain off, and uses filtered 16 kHz resampling. See docs/GENUINE_REJECTION_DIAGNOSIS.md for measured scores and the remaining model calibration limitation. Strict CM thresholds are unchanged.

Short English challenges use Whisper small.en with deterministic beam decoding and full precision. The expected phrase is not included in the recognition prompt. First launch downloads the official model; subsequent launches use the cache. SASV_WHISPER_MODEL can explicitly select another installed Whisper model. Authentication response JSON is archived beside its WAV for diagnostics.

Light interface redesign: paired reference/response charts share a time scale and independently peak-normalize their display to 0.95. The plotted envelope covers every PCM sample; the original unscaled samples determine clipping and low-energy flags. Region chips highlight the same interval on both plots. Different challenge phrases are not speech-aligned, and these flags do not localize the cause of a biometric rejection. Existing Pawan and Satheesh enrollment references were recovered only after matching stored CM/RMS reports and reproducing the saved mean voiceprint (provenance recorded beside each reference).


Verification evidence: each speaker, countermeasure and fusion section expands independently. The API returns actual enrolled/probe ECAPA vectors, AASIST input-window/logit metadata and the exact fusion contributions. Speaker feature highlights show the greatest reductions from reference self-match; feature indices are not audio timestamps. Audio shading remains measured RMS/clipping diagnostics. The model provides no time-localized spoof attribution, and raw scores are not mathematical proof of a human identity.

Test With AI: choose an identity and synthetic voice, then Generate demo audio. If needed, a fresh random challenge is requested without microphone access. Offline Windows System.Speech creates a generic computer voice for that phrase; no voice cloning or remote synthesis is used. Listen to the loaded sample, then Verify identity before expiry. The sample is submitted to the same authentication endpoint with all enforced gates active. Client-declared synthetic-demo labels do not affect authorization. If a generated sample is accepted, the UI explicitly reports this as a model weakness.

Validation includes demo challenge binding/expiry/single-use guards, exact fusion arithmetic, evidence rendering and an actual browser generation-to-verification test. In the tested generic synthetic sample, the spoken challenge and CM gate passed; identity and fusion rejected access. This does not establish that all spoof attacks are detected.

A second browser demo used the selected female voice for red wave 93. The phrase passed; speaker -0.0189, CM -8.7276 and fusion -5.2604 all fell below their thresholds, rejecting access. Both default and female selections were verified through the browser; male synthesis was checked directly.

Recording history now persists on the local server in data/recording_history, including unverified microphone recordings, uploaded samples and synthetic demos. Each saved recording keeps its reference snapshot and any eventual verification response. Previous archived test recordings were imported; older archives without result JSON remain marked not verified because complete evidence is unavailable. Graph hover readouts show PCM time/amplitude, reference and response feature values, threshold margins and cumulative fusion contributions. Text uses larger, darker and heavier styles.
