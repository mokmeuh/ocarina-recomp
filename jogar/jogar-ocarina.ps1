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
$proc = Start-Process .\ocarina.exe @extras -PassThru -RedirectStandardOutput $saida -RedirectStandardError $erros
# The game only reads the controller while its window has the focus: hide the console that comes with it and bring the game to the front.
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices;
public class OcaFront {
    delegate bool EP(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EP cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool f);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    public static bool Go(uint pid) {
        IntPtr game = IntPtr.Zero;
        EnumWindows((h, l) => {
            uint p; GetWindowThreadProcessId(h, out p);
            if (p != pid) return true;
            var c = new StringBuilder(64); GetClassName(h, c, 64); string n = c.ToString();
            if (n == "TotKRecompWindow") game = h;
            else if (n == "PseudoConsoleWindow" || n == "ConsoleWindowClass") ShowWindow(h, 0);
            return true;
        }, IntPtr.Zero);
        if (game == IntPtr.Zero) return false;
        uint fp; uint ft = GetWindowThreadProcessId(GetForegroundWindow(), out fp); uint me = GetCurrentThreadId();
        AttachThreadInput(me, ft, true); ShowWindow(game, 9); SetForegroundWindow(game); AttachThreadInput(me, ft, false);
        return true;
    }
}
'@
$visto = 0
for ($i = 0; $i -lt 160 -and $visto -lt 20 -and -not $proc.HasExited; $i++) {
    if ([OcaFront]::Go([uint32]$proc.Id)) { $visto++ }
    Start-Sleep -Milliseconds 500
}
