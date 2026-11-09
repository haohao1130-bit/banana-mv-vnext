param(
    [string]$ComfyRoot = (Join-Path $env:USERPROFILE 'Documents\ComfyUI'),
    [string]$ComfyUrl = 'http://127.0.0.1:8000',
    [string]$PythonPath = '',
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'BananaMVVNext'),
    [int]$Port = 8190
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $ComfyRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python not found: $PythonPath. Pass -PythonPath with your ComfyUI Python path."
}
foreach ($binary in @('ffmpeg','ffprobe')) {
    if (-not (Get-Command $binary -ErrorAction SilentlyContinue)) {
        throw "$binary is missing from PATH. Install FFmpeg (for example: winget install --id Gyan.FFmpeg -e), then open a new PowerShell and run this launcher again."
    }
}
& $PythonPath -c 'import PIL, numpy'
if ($LASTEXITCODE -ne 0) { throw 'The selected Python needs Pillow and numpy.' }
$nodes = Invoke-RestMethod -Uri "$($ComfyUrl.TrimEnd('/'))/object_info" -TimeoutSec 10
if ($null -eq $nodes.TextGenerate) { throw 'This ComfyUI does not expose TextGenerate.' }
$model = 'minimax_h3_rewriter_ref2va_qwen3.5_9b_w4a8.safetensors'
$names = @($nodes.CLIPLoader.input.required.clip_name[0])
if ($names -notcontains $model) {
    throw "ComfyUI cannot see $model. Restart the ComfyUI instance after downloading the model, then retry."
}
$inputDir = Join-Path $ComfyRoot 'input'
if (-not (Test-Path -LiteralPath $inputDir -PathType Container)) {
    throw "Input directory not found: $inputDir. Set -ComfyRoot to the data folder shown in Desktop Storage."
}
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
$configPath = Join-Path $DataRoot 'config.json'
$config = [pscustomobject]@{}
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
}
$config | Add-Member -NotePropertyName 'comfy_url' -NotePropertyValue ($ComfyUrl.TrimEnd('/')) -Force
$config | Add-Member -NotePropertyName 'comfy_input_dir' -NotePropertyValue $inputDir -Force
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 20), $utf8)
$oldData = $env:BANANA_DATA
$oldPort = $env:BANANA_PORT
try {
    $env:BANANA_DATA = $DataRoot
    $env:BANANA_PORT = [string]$Port
    Write-Host "Banana MV: http://127.0.0.1:$Port"
    Write-Host "ComfyUI: $ComfyUrl"
    Write-Host "Project data: $DataRoot"
    Write-Host 'For recipe-only testing, select Prepare recipe in the UI; do not start video rendering.'
    Write-Host 'Disable music-structure analysis for this first local test; basic audio analysis is supported.'
    Push-Location $projectRoot
    try { & $PythonPath -m banana_mv.server }
    finally { Pop-Location }
} finally {
    $env:BANANA_DATA = $oldData
    $env:BANANA_PORT = $oldPort
}
