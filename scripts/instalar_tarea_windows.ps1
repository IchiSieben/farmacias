<#
.SYNOPSIS
  Registra (o quita) la corrida diaria del Radar de Precios en el Programador de tareas.

.DESCRIPTION
  Crea una tarea diaria que ejecuta scripts\corrida_diaria.cmd
  (= py -m pipeline.run --todo: captura, procesado, exportación a staging y
  rclone copy a Drive). Se registra con /IT: corre con tu sesión iniciada
  (bloqueada vale) y así no hace falta guardar tu contraseña en la tarea; usa
  tu .env y tu configuración de rclone (%APPDATA%\rclone). Con la sesión cerrada
  o el PC apagado a esa hora, la corrida de ese día no se hace.

  Duración medida (2026-09-25, --objetivo 150): 52 min de captura y procesado +
  ~1,5 min de rclone. A las 02:00 termina hacia las 03:00, con margen de sobra
  antes del día. NO publica: web/data.json solo cambia con pipeline.publish.

.EXAMPLE
  .\scripts\instalar_tarea_windows.ps1                # diaria a las 02:00
  .\scripts\instalar_tarea_windows.ps1 -Hora 02:00 -Simular   # muestra el comando, no registra
  .\scripts\instalar_tarea_windows.ps1 -Quitar

.NOTES
  Ver la tarea:      schtasks /Query /TN RadarPrecios-CorridaDiaria /V /FO LIST
  Correrla ya:       schtasks /Run /TN RadarPrecios-CorridaDiaria
  Leer el último log: Get-ChildItem data\logs\run_*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Tail 30
#>
param(
    [ValidatePattern('^\d{2}:\d{2}$')]
    [string]$Hora = "02:00",
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
