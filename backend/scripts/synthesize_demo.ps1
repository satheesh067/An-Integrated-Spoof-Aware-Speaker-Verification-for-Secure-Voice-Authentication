param([Parameter(Mandatory=$true)][string]$RequestPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$demoRequest = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($demoRequest.voice -eq 'female') { $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) }
    if ($demoRequest.voice -eq 'male') { $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male) }
    $synth.Rate = -1
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile($OutputPath, $format)
    $synth.Speak([string]$demoRequest.phrase)
    $synth.SetOutputToNull()
} finally { $synth.Dispose() }
