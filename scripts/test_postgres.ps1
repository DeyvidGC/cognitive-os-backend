param([string]$PgBin = 'C:/Program Files/PostgreSQL/18/bin')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path $env:TEMP ('cognitive-api-tests-' + [guid]::NewGuid().ToString('N'))
$testData = Join-Path $testRoot 'data'
$previousUrl = $env:COGNITIVE_TEST_DATABASE_URL
$started = $false
$result = 1
New-Item -ItemType Directory -Path $testRoot | Out-Null
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$testPort = $listener.LocalEndpoint.Port
$listener.Stop()
Push-Location $projectRoot
try {
    & "$PgBin/initdb.exe" -D $testData -U postgres -A trust --no-locale --encoding=UTF8
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
    & "$PgBin/pg_ctl.exe" -D $testData -l (Join-Path $testRoot 'postgres.log') -o "-h 127.0.0.1 -p $testPort" -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL test server failed to start' }
    $started = $true
    & "$PgBin/createdb.exe" -h 127.0.0.1 -p $testPort -U postgres cognitive
    if ($LASTEXITCODE -ne 0) { throw 'Test database creation failed' }
    & "$PgBin/psql.exe" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p $testPort -U postgres -d cognitive -f migrations/001_initial.sql -f migrations/004_local_auth.sql
    if ($LASTEXITCODE -ne 0) { throw 'Test migrations failed' }
    $env:COGNITIVE_TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:$testPort/cognitive"
    & .venv/Scripts/python.exe -m pytest -q
    $result = $LASTEXITCODE
} finally {
    if ($started) {
        & "$PgBin/pg_ctl.exe" -D $testData -m fast -w stop
    }
    $env:COGNITIVE_TEST_DATABASE_URL = $previousUrl
    Pop-Location
    Write-Host "Test cluster stopped; files retained at $testRoot"
}
exit $result
