# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
# QERRA-v2 Classical -- Demo 10 Launcher: Asynchronous Telemetry Integrity

$ErrorActionPreference = "Stop"

# 1. Discover Repository Root & Demo 10 World
$Repo = if ($PSScriptRoot) {
    Split-Path -Parent $PSScriptRoot
} else {
    "C:\Users\marun\PycharmProjects\QERRA-v2-classical"
}
$World = Join-Path $Repo "worlds\demo10_hsr_integrity.wbt"

if (-not (Test-Path $World)) {
    throw "Demo 10 world file not found: $World"
}

# 2. Locate Webots R2025a on Windows 11
$Candidates = @()

if ($env:WEBOTS_HOME) {
    $Candidates += "$env:WEBOTS_HOME\webots.exe"
    $Candidates += "$env:WEBOTS_HOME\msys64\mingw64\bin\webots.exe"
    $Candidates += "$env:WEBOTS_HOME\msys64\ucrt64\bin\webots.exe"
}

$Candidates += "$env:LOCALAPPDATA\Programs\Webots\webots.exe"
$Candidates += "$env:LOCALAPPDATA\Programs\Webots\msys64\mingw64\bin\webots.exe"
$Candidates += "C:\Program Files\Webots\webots.exe"
$Candidates += "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"

$WebotsCommand = Get-Command webots.exe -ErrorAction SilentlyContinue
if ($WebotsCommand) {
    $Candidates = @($WebotsCommand.Source) + $Candidates
}

$WebotsExe = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $WebotsExe) {
    throw "Cannot locate webots.exe. Please verify your Webots R2025a installation path."
}

# Set WEBOTS_HOME if needed
if ($WebotsExe -match '^(.*)\\msys64\\(?:mingw64|ucrt64)\\bin\\webots\.exe$') {
    $env:WEBOTS_HOME = $Matches[1]
} elseif (-not $env:WEBOTS_HOME) {
    $env:WEBOTS_HOME = Split-Path $WebotsExe -Parent
}

# 3. Clean any stale QERRA variables from the current shell
Get-ChildItem Env: | Where-Object { $_.Name -like "QERRA_*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }

# 4. Set Explicit Demo 10 Configuration
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$env:QERRA_ROOT = $Repo
$env:QERRA_RUN_ID = "DEMO10_FROZEN_FRAME_$Timestamp"

$env:QERRA_HSR_SOURCE = "udp"
$env:QERRA_HSR_MODE = "frozen_frame"
$env:QERRA_HSR_PORT = "5008"
$env:QERRA_HSR_STATE_PORT = "5009"
$env:QERRA_SKIP_HSR_PRODUCER = "0"

$env:QERRA_HSR_EVENT = "none"
$env:QERRA_HSR_EVENT_SIM_S = "4.0"
$env:QERRA_HSR_EVENT_END_SIM_S = "7.0"

$env:QERRA_AUTO_RESET_AT_US = "1200000"
$env:QERRA_AUTO_RESET2_AT_US = "5000000"
$env:QERRA_AUTO_RESET3_AT_US = "8300000"

$env:QERRA_END_AT_S = "14.02"
$env:QERRA_SMOKE_OBSTACLE = "0"
$env:QERRA_LIDAR_FAULT = "none"
$env:QERRA_PROPOSER_FAULT = "none"

# 5. Banner Display
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " QERRA-v2 Classical -- Demo 10 (Asynchronous HSR Integrity)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Repo Root        : $Repo"
Write-Host "  Webots Executable: $WebotsExe"
Write-Host "  World Target     : $World"
Write-Host "  Run ID           : $env:QERRA_RUN_ID"
Write-Host "  HSR Source       : $env:QERRA_HSR_SOURCE (Port: $env:QERRA_HSR_PORT)"
Write-Host "  HSR Clock Port   : Port $env:QERRA_HSR_STATE_PORT"
Write-Host "  HSR Fault Mode   : $env:QERRA_HSR_MODE (4.0s to 7.0s)"
Write-Host "  Recovery Reset   : Scheduled at 8.30s (post-calm dwell)"
Write-Host "  End Condition    : $env:QERRA_END_AT_S s"
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 6. Launch Webots with inherited environment in Real-Time mode
Set-Location $Repo
& $WebotsExe --mode=realtime $World
