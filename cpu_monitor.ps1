# Simple CPU monitor: samples total CPU % and top CPU processes every 3s.
$logicalCores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
Write-Output "Monitoring CPU (logical cores: $logicalCores). Ctrl+C to stop."
Write-Output ("{0,-10} {1,-8} {2}" -f "time", "cpu%", "top-processes (name:cpu%)")
while ($true) {
    $total = (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue
    $top = Get-Process |
        Where-Object { $_.CPU -ne $null } |
        Sort-Object -Property CPU -Descending |
        Select-Object -First 5 |
        ForEach-Object { "{0}:{1:N0}s" -f $_.ProcessName, $_.CPU }
    $ts = (Get-Date).ToString("HH:mm:ss")
    Write-Output ("{0,-10} {1,-8:N1} {2}" -f $ts, $total, ($top -join "  "))
    Start-Sleep -Seconds 3
}
