<#
.SYNOPSIS
  Keep long ASTRA benchmark runs off the interactive foreground.

.DESCRIPTION
  Lowers the priority of the benchmark runner started from this checkout and
  of the model CLI subprocesses it spawned, found by walking the process tree
  rather than by name. Matching on name alone would also demote the
  operator's own interactive `claude`/`node` sessions, which is the opposite
  of the goal.

  Child processes inherit the parent priority class on Windows, but a CLI
  started before this script ran keeps its original class, so re-running the
  script while a benchmark is in flight is both safe and useful.

  Measured 2026-08-12: 99.35% of a cycle is spent waiting on remote model
  inference rather than on local compute, so lowering priority costs the
  benchmark almost nothing while keeping the workstation responsive.

.EXAMPLE
  .\scripts\set_benchmark_priority.ps1
  .\scripts\set_benchmark_priority.ps1 -Priority Idle
  .\scripts\set_benchmark_priority.ps1 -Restore
#>
param(
    [ValidateSet('Idle', 'BelowNormal', 'Normal')]
    [string]$Priority = 'BelowNormal',
    [switch]$Restore
)

if ($Restore) { $Priority = 'Normal' }
$checkout = Split-Path -Parent $PSScriptRoot

$roots = Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$checkout*" }
if (-not $roots) {
    Write-Host "No benchmark process is running from $checkout."
    return
}

# Map every process to its parent once, then collect the roots' descendants.
$all = Get-CimInstance Win32_Process |
    Select-Object ProcessId, ParentProcessId, Name
$childrenOf = @{}
foreach ($proc in $all) {
    $parent = [int]$proc.ParentProcessId
    if (-not $childrenOf.ContainsKey($parent)) { $childrenOf[$parent] = @() }
    $childrenOf[$parent] += [int]$proc.ProcessId
}

$targets = [System.Collections.Generic.HashSet[int]]::new()
$queue = [System.Collections.Queue]::new()
foreach ($root in $roots) { [void]$queue.Enqueue([int]$root.Id) }
# NOTE: $pid is a read-only automatic variable in PowerShell; using it here
# would silently leave the shell's own id in scope and demote this process.
while ($queue.Count -gt 0) {
    $current = [int]$queue.Dequeue()
    if (-not $targets.Add($current)) { continue }
    foreach ($child in ($childrenOf[$current] | Where-Object { $_ })) {
        [void]$queue.Enqueue([int]$child)
    }
}

$changed = 0
foreach ($id in ($targets | Sort-Object)) {
    try {
        $proc = Get-Process -Id $id -ErrorAction Stop
        if ($proc.PriorityClass -ne $Priority) {
            $proc.PriorityClass = $Priority
            Write-Host "$($proc.ProcessName) PID $id -> $Priority"
            $changed++
        }
    } catch {
        # Process exited between the snapshot and the update; nothing to do.
    }
}
Write-Host "$changed process(es) set to $Priority (tree of $($roots.Count) runner(s))."
