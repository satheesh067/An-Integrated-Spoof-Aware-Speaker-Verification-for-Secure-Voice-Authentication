# Revised Plan: Integrated Spoof-Aware Speaker Verification

## Project goal

Authenticate a claimed user by checking **speaker identity**, **audio authenticity**, and a **fresh spoken challenge**. The core research contribution is a trained, evaluated SASV decision rule and a measured challenge-response workflow built on pretrained speech models. A lightweight spoof-model adaptation is an optional comparison. Enrollment creates a voice template from several user recordings.

The three questions are:

1. Does this voice match the enrolled user? ECAPA-TDNN provides a speaker similarity score.
2. Is the audio likely bona fide? A pretrained AASIST detector provides the first spoof score. A lightweight adapted detector is an experiment if resources permit.
3. Was the current one-use phrase spoken in time? ASR checks the words against a server-issued challenge.

The challenge makes an old fixed recording less useful. It does not prove human physical presence or defeat a live relay or responsive voice generator, so these remain test cases.

## Data and evaluation protocol come first

Create a manifest containing source, speaker ID when known, label, attack type, channel/codec, partition, and permitted use. Detect duplicate recordings and speaker or attack overlap before training. Freeze final test partitions. Never use them to select a model, threshold, or preprocessing rule.

| Data source | Role in this project |
| --- | --- |
| Fake-or-Real (FoR), used by the second GitHub repository | Use a small, balanced subset to verify the data and training pipeline. Full reproduction is optional cloud work. Its published result is not a SASV result. |
| ASVspoof 2019 LA and PA | Select documented training subsets for local adaptation and test synthetic and replay cases. Full archives are optional; an official benchmark claim requires the required official partitions and protocol. |
| ASVspoof 2021 LA, DF, and PA | Separate external tests for codec conditions, deepfakes, and physical replay. |
| ASVspoof 5 | Optional newer training and SASV evaluation route. Choose an official condition or label our protocol as custom; check its data-overlap rules. |
| VoxCeleb2 | Optional speaker adaptation data if access and compute permit. The core project uses a pretrained ECAPA encoder and enrolls local users without downloading all of VoxCeleb2. |
| Consented local recordings | Evaluate challenge response, microphones, replay, and application usability with separate people/sessions for final testing. |

Use SASV trials with **target bona fide**, **impostor bona fide**, and **spoof** test audio. Also tag whether spoof audio imitates the target. The challenge-response application needs an additional, separately reported test set.

## Resource-aware implementation order

The minimum complete system uses pretrained ECAPA and AASIST checkpoints, Whisper for phrase recognition, and a **small fusion model trained by us**. User enrollment adapts a stored voice template; it does not retrain ECAPA. This fits the project objective without a full speech-model training run.

Our local GPU has 4 GB VRAM and the installed PyTorch build currently has no CUDA support. First set up a compatible CUDA-enabled PyTorch environment and measure peak memory and end-to-end latency on a few clips. Use micro-batches, short windows, and checkpointed runs where needed. Do not assume a particular batch size or millisecond latency before measuring.

### 1. Establish pretrained baselines and a small data pilot

Run pretrained ECAPA and AASIST inference first. Use a small balanced FoR subset to verify labels, score direction, preprocessing, and metrics. The second repository's full FoR training result is a reference, not a prerequisite for the application.

### 2. Optional lightweight anti-spoof adaptation

If the pretrained AASIST baseline fails on our selected attacks, adapt a small classifier using cached features from a frozen speech encoder and a documented subset of permitted spoof training data. The second repository's WavLM plus AASIST design is a reference. Try WavLM Base+ before WavLM-Large for local feature extraction; changing the encoder requires training a compatible classifier head. Fine-tuning WavLM-Large is an optional cloud experiment only after the smaller system and benchmark are complete. Training WavLM from random initialization is outside scope.

Use RawBoost-like noise/channel transformations and actual codec augmentation in training only. Log every applied augmentation; an unavailable codec must not silently count as an augmentation. Evaluate TTS, voice conversion, replay, codecs, and unseen attack methods separately.

### 3. Enroll and evaluate speakers

Use the pretrained SpeechBrain ECAPA-TDNN encoder. Evaluate speaker-disjoint target and impostor trials, including short utterances and device changes. Enroll a user with several quality-checked genuine recordings, normalize their embeddings, and form a template. Fine-tuning ECAPA on a permitted small speaker dataset is optional if the baseline is inadequate; full VoxCeleb2 training is not required.

### 4. Implement the spoken challenge

The server issues a random phrase bound to the session and claimed identity. It expires quickly and can be consumed once. ASR measures phrase match and timeout. The same response is scored by ECAPA and the spoof model. Uploaded audio can support research diagnostics, but an upload alone cannot establish a live challenge response.

### 5. Learn the integrated decision

First implement mandatory checks: usable audio, successful fresh challenge, speaker match, and acceptable spoof score. A missing required model causes reject or retry. Then train a small fusion model on SASV development trials, starting with logistic regression over the raw speaker and spoof scores. Add interactions or more complex fusion only if held-out results improve.

The first repository's risk engine informs the **explanation format and decision categories**. Its manually chosen weights and thresholds are not copied. Select our thresholds from development data with explicit false-accept and false-reject costs. A 0-100 display is a decision score unless calibration supports a probability interpretation.

## Audio processing

Decode safely, check speech duration, silence, clipping, and usable level, then resample to mono 16 kHz. Keep a common decoded waveform and apply model-specific preparation afterward. Avoid aggressive filtering that removes spoof artifacts. Use consistent preparation within each model across train, validation, and inference.

The second repository cuts or pads to four seconds. A longer challenge response should be scored across multiple windows and aggregated so later speech is not discarded. Poor-quality input receives a distinct retry/reject outcome.

## Evaluation

Compare on the same held-out trials: speaker-only, independent speaker/spoof gates, learned fusion, and fusion plus challenge. Report:

- Speaker EER for target versus bona fide impostor trials.
- Countermeasure EER for bona fide versus spoof audio, with results by attack family.
- SASV-EER for target bona fide versus both impostor and spoof trials.
- False accepts and false rejects at the selected operating point, including challenge errors and retries for the application workflow.
- Latency, unseen-generator, replay, microphone, noise, and codec results.
- a-DCF or t-DCF only with the exact protocol, costs, and definition stated.

Report sample counts and uncertainty. Do not turn conceptual curves into measured results.

## Software modules and deliverables

| Module | Purpose |
| --- | --- |
| `src/data/` | Manifests, split audits, preprocessing, training augmentation |
| `src/models/` | Pretrained ECAPA and AASIST, optional lightweight adapted spoof model, ASR, and saved model versions |
| `src/train/` | Reproducible fusion training and optional small spoof or speaker adaptation |
| `src/eval/` | Trials, metrics, robustness reports |
| `src/core/` | Enrollment, one-use challenge, policy, explanations |
| `src/api/` and `src/db/` | FastAPI endpoints, templates, challenge state, audit metadata |
| `frontend/` | Enrollment, microphone challenge, explanation, research view |

Milestones: **(1)** data and protocol audit; **(2)** CUDA setup and pretrained inference baselines; **(3)** small fusion training and SASV comparison; **(4)** challenge API and interface; **(5)** untouched final evaluation; **(6)** optional lightweight spoof adaptation and a measured comparison against the baseline. Training and application inference must load the same saved preprocessing settings and model versions.

## Review-deck corrections

- Present ECAPA and AASIST as pretrained baseline models. State clearly that we train the fusion model and may adapt a smaller spoof classifier. Distinguish raw-waveform AASIST from the optional WavLM-feature variant; they do not share a single “spectrogram input” description.
- Reword the passphrase claim: it resists old recordings but does not prove physical presence or stop all responsive synthesis.
- Name training and test datasets separately. Label unmeasured accuracy and attack-detection charts as conceptual until experiments produce results.
- Make SASV-EER the primary integrated metric. Define a-DCF or t-DCF precisely before using it. Do not promise improvement before testing.
- Remove or explicitly scope “post-login security” unless continuous authentication becomes part of the deliverable.

## Sources

- Second repository: https://github.com/satyatupati/deepfake-audio-detection
- First repository: https://github.com/Saqib-Hussain-xo/SIH26104-voice-security
- SASV protocol: https://sasv-challenge.github.io/pdfs/2022_SASV_evaluation_plan_v0.1.pdf
- ASVspoof 5 protocol: https://www.asvspoof.org/file/ASVspoof5___Evaluation_Plan_Phase2.pdf
- ASVspoof 2021 data: https://www.asvspoof.org/index2021.html
- VoxCeleb: https://www.robots.ox.ac.uk/~vgg/data/voxceleb/index.html
