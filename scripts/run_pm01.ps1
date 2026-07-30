# Run PM_01 — all permissions allow (positive).
param(
    [string]$Device = "ZA222RFQ75",
    [int]$MaxAttempts = 3
)

& $PSScriptRoot\run_permission_suite.ps1 -Device $Device -Mode Positive
exit $LASTEXITCODE
