# Script para ejecutar ms_ml_despacho en Docker
# Conectando a SQL Server en la máquina local
# Uso: .\docker-run.ps1

Write-Host "=== MS ML DESPACHO - Docker Setup ===" -ForegroundColor Green
Write-Host ""

# Validar que Docker está instalado
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker no está instalado" -ForegroundColor Red
    exit 1
}

# 1. Detener contenedor anterior
Write-Host "1. Deteniendo contenedor anterior (si existe)..." -ForegroundColor Yellow
docker-compose down 2>$null

# 2. Construir imagen
Write-Host "2. Construyendo imagen Docker..." -ForegroundColor Yellow
docker-compose build --no-cache

# 3. Iniciar contenedor
Write-Host "3. Iniciando contenedor..." -ForegroundColor Yellow
docker-compose up -d

# 4. Esperar a que el servicio esté listo
Write-Host "4. Esperando a que el servicio esté listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 5. Verificar que el contenedor está corriendo
$containerRunning = docker-compose ps | Select-String "hads-ml-service"

if ($containerRunning) {
    Write-Host "✓ Contenedor iniciado exitosamente" -ForegroundColor Green
    Write-Host ""
    Write-Host "Información del servicio:" -ForegroundColor Green
    Write-Host "  - URL: http://localhost:5000"
    Write-Host "  - BD: SQL Server en host.docker.internal:1433"
    Write-Host "  - Base de datos: ms_ml_despacho"
    Write-Host ""
    Write-Host "Comandos útiles:" -ForegroundColor Yellow
    Write-Host "  Ver logs:     docker-compose logs -f hads-ml-service"
    Write-Host "  Detener:      docker-compose down"
    Write-Host "  Reiniciar:    docker-compose restart"
    Write-Host ""
} else {
    Write-Host "✗ Error: El contenedor no se inició correctamente" -ForegroundColor Red
    Write-Host "Revisa los logs con: docker-compose logs"
    exit 1
}
