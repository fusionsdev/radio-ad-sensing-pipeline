Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$out = Join-Path $PSScriptRoot "..\data\classifier-test-accept.wav"
$s.SetOutputToWaveFile($out)
$s.Speak(
    "Need a personal loan today? Call now for fast cash with low monthly payments. " +
    "Apply online today. Fast approval from trusted lenders."
)
$s.Dispose()
Write-Host "Wrote $out ($((Get-Item $out).Length) bytes)"
