<#
.SYNOPSIS
  Registra (o quita) la corrida diaria del Radar de Precios en el Programador de tareas.

.DESCRIPTION
  Crea una tarea diaria que ejecuta scripts\corrida_diaria.cmd
  (= py -m pipeline.run --todo). Se registra con /IT: corre SOLO con tu sesión
  iniciada, porque Google Drive para escritorio (RAW_DIR) se monta por sesión;
  sin sesión la unidad no existe y la corrida fallaría al validar RAW_DIR.
  Si el PC está apagado a esa hora, la corrida de ese día no se hace.

.EXAMPLE
  .\scripts\instalar_tarea_windows.ps1 -Hora 04:30
  .\scripts\instalar_tarea_windows.ps1 -Hora 04:30 -Simular   # muestra el comando, no registra
  .\scripts\instalar_tarea_windows.ps1 -Quitar

.NOTES
  Ver la tarea:      schtasks /Query /TN RadarPrecios-CorridaDiaria /V /FO LIST
  Correrla ya:       schtasks /Run /TN RadarPrecios-CorridaDiaria
  Leer el último log: Get-ChildItem data\logs\run_*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Tail 30
#>
param(
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$Hora = "04:30",
    [string]$Nombre = "RadarPrecios-CorridaDiaria",
    [switch]$Quitar,
    [switch]$Simular
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$cmd = Join-Path $repo "scripts\corrida_diaria.cmd"

if ($Quitar) {
    $argumentos = @("/Delete", "/TN", $Nombre, "/F")
} else {
    if (-not (Test-Path $cmd)) { throw "No existe $cmd" }
    if (-not (Test-Path (Join-Path $repo ".env"))) {
        Write-Warning "No hay .env en $repo : la corrida no tendrá RAW_DIR ni llaves Algolia."
    }
    $argumentos = @("/Create", "/SC", "DAILY", "/ST", $Hora, "/TN", $Nombre,
                    "/TR", "`"$cmd`"", "/IT", "/F")
}

if ($Simular) {
    Write-Output ("schtasks " + ($argumentos -join " "))
    return
}

& schtasks.exe @argumentos
if ($LASTEXITCODE -ne 0) { throw "schtasks terminó con código $LASTEXITCODE" }
if (-not $Quitar) {
    Write-Output "Tarea '$Nombre' registrada: diaria a las $Hora (solo con sesión iniciada)."
    Write-Output "Logs: $(Join-Path $repo 'data\logs')"
}
