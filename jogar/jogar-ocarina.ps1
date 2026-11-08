# Abre o Ocarina Recomp.
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
if (Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }) { $env:TOTK_GPU_NAME = "NVIDIA" }
# Without an NVIDIA card keep the ten giant compute programs skipped (v0.2.7 runs eight of them: ~400 ms per frame on an AMD iGPU).
if (-not $env:TOTK_GPU_NAME -and -not $env:DKB_SKIP_CS) { $env:DKB_SKIP_CS = "3bdfe449de832903,909139c13b510f1f,753f8ab880fe7923,c968ad44272dcbb4,785a41d2df6dc095,db8c39bdb420e068,dec1feb3c7fa967a,09931d0c57c6b67f,13cab66ee383c4f4,3f6f2b1d671badcd" }
$raiz = Split-Path $PSScriptRoot -Parent
$env:TOTK_PROFILE_DIR = Join-Path $raiz "perfil"
# The previous run's logs go to logs\ (the newest 10 runs) before this one overwrites them: a crash log used to be lost
# as soon as the game was opened again. jogar\medir-partida.ps1 reads them.
$saida = Join-Path $raiz "ultima-partida.log"
$erros = Join-Path $raiz "ultima-partida-erros.log"
if ((Test-Path -LiteralPath $erros) -and (Get-Item -LiteralPath $erros).Length -gt 0) {
    try {
        $logs = Join-Path $raiz "logs"
        New-Item -ItemType Directory -Force -Path $logs | Out-Null
        $quando = (Get-Item -LiteralPath $erros).LastWriteTime.ToString('yyyy-MM-dd_HH-mm-ss')
        Move-Item -LiteralPath $erros -Destination (Join-Path $logs "partida-$quando-erros.log") -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $saida) { Move-Item -LiteralPath $saida -Destination (Join-Path $logs "partida-$quando.log") -Force }
        Get-ChildItem -LiteralPath $logs -Filter 'partida-*-erros.log' | Sort-Object Name -Descending | Select-Object -Skip 10 | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            $par = $_.FullName -replace '-erros\.log$', '.log'
            if (Test-Path -LiteralPath $par) { Remove-Item -LiteralPath $par -Force }
        }
    } catch {
        # the game is still open and holds the log: leave it, Start-Process below says so
    }
}
Set-Location (Join-Path $raiz "build\oot111")
$extras = if ($args.Count) { @{ ArgumentList = $args } } else { @{} }
Start-Process .\ocarina.exe @extras -RedirectStandardOutput $saida -RedirectStandardError $erros
