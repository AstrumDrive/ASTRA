<#
.SYNOPSIS
    One-paste setup of ASTRA + ASTRUM access on a collaborator's Windows PC.

.DESCRIPTION
    Installs the prerequisites with winget, clones or updates ASTRA, runs
    install.ps1, creates the collaborator's SSH key, writes the SSH alias and
    the .env remote block, registers ASTRA in the Claude Desktop app, waits
    until the ASTRUM administrator authorizes the key, and runs the doctor.
    Every step is idempotent: running it again repairs or confirms the setup.

    The administrator gives the collaborator one line to paste, for example:

      irm https://raw.githubusercontent.com/AstrumDrive/ASTRA/main/scripts/setup_windows_collaborator.ps1 -OutFile $env:TEMP\astra_setup.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\astra_setup.ps1 -AstrumUser NAME -AstrumHost TAILSCALE_IP

    Host and user are parameters on purpose: this repository is public.
    See docs/onboarding/ASTRA_WINDOWS_INSTALL_EN.md for the manual procedure.
#>
param(
    [string]$AstrumUser = "",
    [string]$AstrumHost = "",
    [string]$InstallDir = "C:\Dev\ASTRA",
    [string]$RepoUrl = "https://github.com/AstrumDrive/ASTRA.git",
    [int]$WaitForKeyMinutes = 30,
    [switch]$SkipPrerequisites,
    [switch]$SkipClaudeDesktop,
    [switch]$WithModelClis
)

$KeyName = "astra_astrum_ed25519"
$WindowsSsh = "C:\Windows\System32\OpenSSH\ssh.exe"

# ---------------------------------------------------------------- output

function Write-Step([string]$Number, [string]$Text) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor Cyan
    Write-Host " STEP $Number - $Text" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor Cyan
}

function Write-Ok([string]$Text) { Write-Host "  OK  $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "      $Text" }
function Write-Warn([string]$Text) { Write-Host "  !!  $Text" -ForegroundColor Yellow }

function Write-Action([string]$Text) {
    Write-Host ""
    Write-Host "  >>> $Text" -ForegroundColor Black -BackgroundColor Yellow
    Write-Host ""
}

function Stop-Setup([string]$Text) {
    Write-Host ""
    Write-Host "  STOPPED: $Text" -ForegroundColor White -BackgroundColor DarkRed
    Write-Host "  Send the file $env:USERPROFILE\astra_setup_log.txt to the ASTRUM administrator." -ForegroundColor Yellow
    throw $Text
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

# ---------------------------------------------------------------- config writers (tested)

function Set-AstrumSshConfig {
    <# Replace or append the "Host astrum" block; other hosts are kept. #>
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$User,
        [Parameter(Mandatory = $true)][string]$HostName,
        [string]$IdentityFile = "~/.ssh/astra_astrum_ed25519"
    )
    $block = @(
        "Host astrum",
        "    HostName $HostName",
        "    User $User",
        "    IdentityFile $IdentityFile",
        "    IdentitiesOnly yes",
        "    ProxyCommand tailscale nc %h %p",
        "    StrictHostKeyChecking accept-new",
        "    ConnectTimeout 20",
        "    ServerAliveInterval 30"
    )
    $lines = @()
    if (Test-Path -LiteralPath $ConfigPath) { $lines = @(Get-Content -LiteralPath $ConfigPath) }
    $out = New-Object System.Collections.Generic.List[string]
    $inAstrum = $false
    $replaced = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*(Host|Match)\s') {
            if ($line -match '^\s*Host\s+astrum\s*$') {
                $inAstrum = $true
                if (-not $replaced) { foreach ($b in $block) { $out.Add($b) }; $replaced = $true }
                continue
            }
            $inAstrum = $false
        }
        if (-not $inAstrum) { $out.Add($line) }
    }
    if (-not $replaced) {
        if ($out.Count -gt 0 -and $out[$out.Count - 1].Trim() -ne "") { $out.Add("") }
        foreach ($b in $block) { $out.Add($b) }
    }
    $dir = Split-Path -Parent $ConfigPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($ConfigPath, (($out -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
}

function Set-AstraEnvBlock {
    <# Replace the remote-access keys in ASTRA's .env and keep everything else. #>
    param(
        [Parameter(Mandatory = $true)][string]$EnvPath,
        [Parameter(Mandatory = $true)][string]$ClientId
    )
    $new = @(
        "ASTRA_ORACLE_MODE=local",
        "ASTRA_REMOTE_HOST=astrum",
        "ASTRA_REMOTE_SSH_BIN=C:\Windows\System32\OpenSSH\ssh.exe",
        "ASTRA_REMOTE_SSH_OPTIONS=",
        "ASTRA_REMOTE_PYTHON=~/astra-worker/venv/bin/python",
        "ASTRA_REMOTE_WORKER=~/astra-worker/astra_remote_worker.py",
        "ASTRA_REMOTE_WORKDIR=~/astra-worker/workspace",
        "ASTRA_REMOTE_CONNECT_TIMEOUT=15",
        "ASTRA_CLIENT_ID=$ClientId",
        "ASTRA_PROJECT_ID=general",
        "ASTRA_REMOTE_SCHEDULER=1",
        "ASTRA_REMOTE_CLUSTER_MANAGER=~/astra-worker/astra_cluster_manager.py",
        "ASTRA_REMOTE_QUEUE_WAIT=300"
    )
    $keys = $new | ForEach-Object { ($_ -split '=', 2)[0] }
    $kept = @()
    if (Test-Path -LiteralPath $EnvPath) {
        $kept = @(Get-Content -LiteralPath $EnvPath | Where-Object { $keys -notcontains (($_ -split '=', 2)[0].Trim()) })
    }
    while ($kept.Count -gt 0 -and $kept[$kept.Count - 1].Trim() -eq "") { $kept = @($kept[0..($kept.Count - 2)]) }
    $all = @($kept) + @("", "# ASTRUM remote access (written by scripts/setup_windows_collaborator.ps1)") + $new
    [IO.File]::WriteAllText($EnvPath, (($all -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
}

function Get-ClaudeDesktopConfigPath {
    <# The packaged (MSIX) app reads its own virtualized AppData; prefer it when present. #>
    $packaged = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Packages") -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "LocalCache\Roaming\Claude" } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($packaged) { return (Join-Path $packaged "claude_desktop_config.json") }
    return (Join-Path $env:APPDATA "Claude\claude_desktop_config.json")
}

function Set-ClaudeDesktopMcp {
    <# Add or replace mcpServers.astra; keep every other key and server. #>
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$ServerScript
    )
    $config = New-Object PSObject
    if (Test-Path -LiteralPath $ConfigPath) {
        $raw = [IO.File]::ReadAllText($ConfigPath).TrimStart([char]0xFEFF)
        if ($raw.Trim()) {
            $config = $raw | ConvertFrom-Json
            Copy-Item -LiteralPath $ConfigPath -Destination ("$ConfigPath." + (Get-Date -Format "yyyyMMdd_HHmmss") + ".bak")
        }
    }
    if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
        $config | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object PSObject)
    }
    $entry = [pscustomobject]@{ command = $PythonExe; args = @($ServerScript) }
    if ($config.mcpServers.PSObject.Properties.Name -contains "astra") {
        $config.mcpServers.astra = $entry
    } else {
        $config.mcpServers | Add-Member -NotePropertyName astra -NotePropertyValue $entry
    }
    $dir = Split-Path -Parent $ConfigPath
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $json = ConvertTo-Json -InputObject $config -Depth 32
    [IO.File]::WriteAllText($ConfigPath, $json, (New-Object System.Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- steps

function Install-WingetPackage([string]$Id, [string]$Label) {
    Write-Info "Installing $Label (a Windows 'Yes/No' window may appear: click Yes) ..."
    & winget install -e --id $Id --accept-source-agreements --accept-package-agreements --silent | Out-Host
    Update-SessionPath
}

function Find-Python312 {
    <# Path of a real Python 3.12 (never the Microsoft Store alias), or $null. #>
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $exe = (& $py.Source -3.12 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path -LiteralPath $exe.Trim())) { return $exe.Trim() }
    }
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        "C:\Program Files\Python312\python.exe"
    )) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Install-Prerequisites {
    Write-Step "1/8" "Programs (Git, Python 3.12, Node.js, Tailscale, Claude app)"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Stop-Setup "winget is not available. Update 'App Installer' from the Microsoft Store and run this again."
    }
    if (Get-Command git -ErrorAction SilentlyContinue) { Write-Ok "Git" } else { Install-WingetPackage "Git.Git" "Git" }
    if (Find-Python312) { Write-Ok "Python 3.12" } else { Install-WingetPackage "Python.Python.3.12" "Python 3.12" }
    if (Get-Command node -ErrorAction SilentlyContinue) { Write-Ok "Node.js" } else { Install-WingetPackage "OpenJS.NodeJS.LTS" "Node.js" }
    $tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
    if (-not $tailscale -and (Test-Path "C:\Program Files\Tailscale\tailscale.exe")) { $env:Path += ";C:\Program Files\Tailscale" }
    if (Get-Command tailscale -ErrorAction SilentlyContinue) { Write-Ok "Tailscale" } else { Install-WingetPackage "Tailscale.Tailscale" "Tailscale" }
    if (-not $SkipClaudeDesktop) {
        $claudeInstalled = (Get-AppxPackage -Name "Claude" -ErrorAction SilentlyContinue) -or
            (Test-Path (Join-Path $env:LOCALAPPDATA "AnthropicClaude"))
        if ($claudeInstalled) { Write-Ok "Claude app" } else { Install-WingetPackage "Anthropic.Claude" "Claude app" }
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { $env:Path += ";C:\Program Files\Git\cmd" }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Stop-Setup "Git did not install correctly." }
    if (-not (Find-Python312)) { Stop-Setup "Python 3.12 did not install correctly." }
}

function Test-Tailscale {
    Write-Step "2/8" "Tailscale connection"
    $exe = (Get-Command tailscale -ErrorAction SilentlyContinue)
    if (-not $exe) { Stop-Setup "Tailscale is not installed." }
    for ($i = 0; $i -lt 60; $i++) {
        & $exe.Source status *> $null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Tailscale is connected"; return }
        if ($i -eq 0) { Write-Action "Open Tailscale (icon next to the clock), sign in, and make sure it says Connected." }
        Start-Sleep -Seconds 5
    }
    Stop-Setup "Tailscale is still not connected after 5 minutes."
}

function Install-Astra {
    Write-Step "3/8" "ASTRA (download and install; this takes several minutes)"
    if (Test-Path -LiteralPath (Join-Path $InstallDir ".git")) {
        & git -C $InstallDir pull --ff-only | Out-Host
        if ($LASTEXITCODE -ne 0) { Stop-Setup "git pull failed in $InstallDir." }
    } else {
        $parent = Split-Path -Parent $InstallDir
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        & git clone $RepoUrl $InstallDir | Out-Host
        if ($LASTEXITCODE -ne 0) { Stop-Setup "git clone failed." }
    }
    $python = Find-Python312
    if (-not $python) { Stop-Setup "Python 3.12 was not found." }
    Write-Info "Using $python"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallDir "install.ps1") -NonInteractive -PythonPath $python | Out-Host
    if ($LASTEXITCODE -ne 0) { Stop-Setup "install.ps1 failed (see the red lines above)." }
    Write-Ok "ASTRA installed in $InstallDir"
}

function New-AstrumKey {
    Write-Step "4/8" "Your personal key for ASTRUM"
    $sshDir = Join-Path $env:USERPROFILE ".ssh"
    if (-not (Test-Path -LiteralPath $sshDir)) { New-Item -ItemType Directory -Force -Path $sshDir | Out-Null }
    $key = Join-Path $sshDir $KeyName
    if (Test-Path -LiteralPath $key) {
        Write-Ok "Key already exists: $key"
    } else {
        # ArgumentList as one string so that -N "" reaches ssh-keygen as an empty passphrase
        # in both Windows PowerShell 5.1 and PowerShell 7.
        Start-Process -FilePath "C:\Windows\System32\OpenSSH\ssh-keygen.exe" -NoNewWindow -Wait `
            -ArgumentList "-q -t ed25519 -f `"$key`" -N `"`" -C astra-$AstrumUser"
        if (-not (Test-Path -LiteralPath "$key.pub")) { Stop-Setup "The SSH key could not be created." }
        Write-Ok "Key created: $key"
    }
    $pub = (Get-Content -LiteralPath "$key.pub" -Raw).Trim()
    Set-Clipboard -Value $pub
    Write-Host ""
    Write-Host "  Your PUBLIC key (safe to share):" -ForegroundColor Cyan
    Write-Host "  $pub" -ForegroundColor White
    Write-Action "It is already copied. Paste it in the Google Meet chat now: click the chat, press Ctrl+V, press Enter."
    return $key
}

function Set-AstrumAccess {
    Write-Step "5/8" "Connection settings"
    Set-AstrumSshConfig -ConfigPath (Join-Path $env:USERPROFILE ".ssh\config") -User $AstrumUser -HostName $AstrumHost
    Write-Ok "SSH alias 'astrum' -> user $AstrumUser"
    Set-AstraEnvBlock -EnvPath (Join-Path $InstallDir ".env") -ClientId $AstrumUser
    Write-Ok "ASTRA settings (.env) for $AstrumUser"
}

function Register-ClaudeDesktop {
    Write-Step "6/8" "Connect ASTRA to the Claude app"
    if ($SkipClaudeDesktop) { Write-Info "Skipped (-SkipClaudeDesktop)."; return }
    $configPath = Get-ClaudeDesktopConfigPath
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $configPath))) {
        Write-Action "Open the Claude app once (Start menu -> Claude) and sign in with the Astrum Drive Google account."
        for ($i = 0; $i -lt 120 -and -not (Test-Path -LiteralPath (Split-Path -Parent (Get-ClaudeDesktopConfigPath))); $i++) { Start-Sleep -Seconds 5 }
        $configPath = Get-ClaudeDesktopConfigPath
    }
    Get-Process -Name "Claude" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Set-ClaudeDesktopMcp -ConfigPath $configPath `
        -PythonExe (Join-Path $InstallDir "venv\Scripts\python.exe") `
        -ServerScript (Join-Path $InstallDir "mcp_server\server.py")
    Write-Ok "ASTRA registered in $configPath"
    $app = Get-StartApps -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "Claude" } | Select-Object -First 1
    if ($app) {
        Start-Process ("shell:AppsFolder\" + $app.AppID)
        Write-Ok "Claude app restarted"
    } else {
        Write-Action "Open the Claude app again from the Start menu."
    }
}

function Install-ModelClis {
    if (-not $WithModelClis) { return }
    Write-Step "6b" "Model command-line tools (optional)"
    & npm install -g "@anthropic-ai/claude-code" "@openai/codex" | Out-Host
    Write-Action "Later, sign in once: run 'claude' (subscription login, then /exit) and 'codex login'."
}

function Wait-ForAuthorization {
    Write-Step "7/8" "Waiting for the administrator to authorize your key"
    Write-Info "Keep this window open. It checks every 15 seconds."
    $deadline = (Get-Date).AddMinutes($WaitForKeyMinutes)
    $hintShown = $false
    while ((Get-Date) -lt $deadline) {
        $output = (& $WindowsSsh -o BatchMode=yes -o ConnectTimeout=20 astrum info 2>&1 | Out-String)
        try {
            $info = $output | ConvertFrom-Json
            if ($info.authenticated -and $info.client_id -eq $AstrumUser) {
                Write-Ok ("Connected to {0} as {1}" -f $info.host, $info.client_id)
                return
            }
        } catch { }
        if (-not $hintShown -and ($output -match "502|timed out|Could not resolve|connectex")) {
            Write-Warn "ASTRUM is not reachable: check that Tailscale says Connected."
            $hintShown = $true
        }
        Write-Info ("{0}  not authorized yet ..." -f (Get-Date -Format "HH:mm:ss"))
        Start-Sleep -Seconds 15
    }
    Stop-Setup "The key was not authorized within $WaitForKeyMinutes minutes. Run this script again later; it resumes here."
}

function Invoke-Doctor {
    Write-Step "8/8" "Final check (does not use any AI quota)"
    & (Join-Path $InstallDir "venv\Scripts\python.exe") (Join-Path $InstallDir "scripts\astra_doctor.py") --remote | Out-Host
    $prompt = "Run astra_status, then astra_cluster_capacity, then submit a job with astra_cluster_submit that prints hello (engine python, max_seconds 30), wait for it with astra_cluster_job and show me its client_id."
    Set-Clipboard -Value $prompt
    Write-Host ""
    Write-Host ("#" * 72) -ForegroundColor Green
    Write-Host "  ALL DONE." -ForegroundColor Green
    Write-Host "  In the Claude app: new chat -> press Ctrl+V -> press Enter." -ForegroundColor Green
    Write-Host "  (The test request is already copied.) The job must show client_id $AstrumUser." -ForegroundColor Green
    Write-Host ("#" * 72) -ForegroundColor Green
}

function Invoke-Main {
    if (-not $AstrumUser -or -not $AstrumHost) {
        throw "Usage: setup_windows_collaborator.ps1 -AstrumUser NAME -AstrumHost TAILSCALE_IP"
    }
    $AstrumUser = $AstrumUser.Trim().ToLower()
    Start-Transcript -Path (Join-Path $env:USERPROFILE "astra_setup_log.txt") -Append | Out-Null
    try {
        Write-Host "ASTRA + ASTRUM setup for '$AstrumUser'. Follow the yellow instructions; everything else is automatic." -ForegroundColor Cyan
        if (-not $SkipPrerequisites) { Install-Prerequisites } else { Update-SessionPath }
        Test-Tailscale
        Install-Astra
        New-AstrumKey | Out-Null
        Set-AstrumAccess
        Register-ClaudeDesktop
        Install-ModelClis
        Wait-ForAuthorization
        Invoke-Doctor
    } finally {
        Stop-Transcript | Out-Null
    }
}

if ($MyInvocation.InvocationName -ne ".") { Invoke-Main }
