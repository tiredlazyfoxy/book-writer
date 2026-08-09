param(
    [Alias("app", "api")]
    [switch]$Backend,

    [Alias("ui", "web")]
    [switch]$Frontend,

    [switch]$Test
)

if (-not $Backend -and -not $Frontend) {
    Write-Host "Usage: .\start.ps1 -app | -ui [-test]"
    Write-Host "  -app, --app, -api, --api   Start backend (uvicorn, port 8185)"
    Write-Host "  -ui,  --ui,  -web, --web   Start frontend (vite, port 8194)"
    Write-Host "  -test                      Use separate test database"
    exit 1
}

if ($Backend) {
    Write-Host "Starting backend on :8185 ..."
    Push-Location "$PSScriptRoot\backend"
    if ($Test) {
        $env:BOOKWRITER_DB_PATH = "$PSScriptRoot\backend\data\test\bookwriter_test.db"
        Write-Host "  Using test DB: $env:BOOKWRITER_DB_PATH"
    }
    $env:BOOKWRITER_LOG_DIR = "$PSScriptRoot/logs"
    Write-Host "  Logging to: $env:BOOKWRITER_LOG_DIR"
    & .venv\Scripts\uvicorn app.main:app --port 8185 --reload
    Pop-Location
}

if ($Frontend) {
    Write-Host "Starting frontend on :8194 ..."
    Push-Location "$PSScriptRoot\frontend"
    & npx vite --port 8194
    Pop-Location
}
