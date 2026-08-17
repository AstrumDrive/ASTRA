# Measure the production line (ASTRA 1.0) on the same standard benchmark that
# produced the 2.0 numbers, so the two can be compared at all.
#
# Production's only deposited benchmark data is eight smoke runs with zero
# scientific and zero audit cases; every rich figure we quote - false acceptance
# 0.0, accuracy 0.696, audit recall 1.0 - was measured on the 2.0 code with
# production's CONFIGURATION, which measures 2.0.
#
# This waits for the machine to be free before starting. A model-heavy run
# launched while a campaign cycle holds the shared account set would contend for
# the same CLIs and contaminate both, which is exactly how three ablation runs
# were lost on 2026-08-15/16.
#
# It writes only to production's workspace (benchmark reports). No production
# code is touched.

$ErrorActionPreference = 'Stop'
$prod = 'C:\Users\Nelson\Dev\ASTRA'
$log  = 'C:\Users\Nelson\Dev\ASTRA-2.0\workspace\benchmark_runs\prod_baseline_console.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Machine-Busy {
    $procs = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
        Where-Object { $_.CommandLine -like '*step_campaign*' -or
                       $_.CommandLine -like '*astra_tool*' -or
                       $_.CommandLine -like '*cycle_job_runner*' })
    if ($procs.Count -gt 0) { return $true }
    $lock = "$env:LOCALAPPDATA\astra\locks\deliberative_cycle_0.lock"
    if (Test-Path $lock) {
        $holder = (Get-Content $lock -Raw | ConvertFrom-Json).pid
        if (Get-Process -Id $holder -ErrorAction SilentlyContinue) { return $true }
    }
    return $false
}

$waited = 0
while ((Machine-Busy) -and $waited -lt 7200) {
    Start-Sleep -Seconds 60
    $waited += 60
}
if (Machine-Busy) {
    "ABORTED: machine still busy after $waited s; not starting a contended run" |
        Tee-Object -FilePath $log
    exit 1
}

"starting production baseline at $(Get-Date -Format o) (waited ${waited}s)" |
    Tee-Object -FilePath $log

Set-Location -LiteralPath $prod
$p = Start-Process -FilePath "$prod\venv\Scripts\python.exe" `
    -ArgumentList 'scripts\run_quality_benchmarks.py', '--tier', 'standard',
                  '--oracle', 'local', '--jobs', '2' `
    -RedirectStandardOutput "$log.out" -RedirectStandardError "$log.err" `
    -WindowStyle Hidden -PassThru

# Keep Nelson's interactive session responsive: the benchmark is long and
# CPU-hungry, and demoting it costs nothing on a run measured in hours.
Start-Sleep -Seconds 5
try { $p.PriorityClass = 'BelowNormal' } catch {}

"pid $($p.Id) launched, priority BelowNormal" | Tee-Object -FilePath $log -Append
$p.WaitForExit()
"exited $($p.ExitCode) at $(Get-Date -Format o)" | Tee-Object -FilePath $log -Append
