#!/bin/bash

# Script para ejecutar ms_ml_despacho en Docker
# Conectando a SQL Server en la máquina local

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MS ML DESPACHO - Docker Setup ===${NC}\n"

# Validar que Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker no está instalado${NC}"
    exit 1
fi

echo -e "${YELLOW}1. Deteniendo contenedor anterior (si existe)...${NC}"
docker-compose down 2>/dev/null || true

echo -e "${YELLOW}2. Construyendo imagen Docker...${NC}"
docker-compose build --no-cache

echo -e "${YELLOW}3. Iniciando contenedor...${NC}"
docker-compose up -d

echo -e "${YELLOW}4. Esperando a que el servicio esté listo...${NC}"
sleep 10

# Verificar que el contenedor está corriendo
if docker-compose ps | grep -q "hads-ml-service"; then
    echo -e "${GREEN}✓ Contenedor iniciado exitosamente${NC}\n"
    echo -e "${GREEN}Información del servicio:${NC}"
    echo "  - URL: http://localhost:5000"
    echo "  - BD: SQL Server en host.docker.internal:1433"
    echo "  - Base de datos: ms_ml_despacho"
    echo ""
    echo -e "${YELLOW}Comandos útiles:${NC}"
    echo "  Ver logs:     docker-compose logs -f hads-ml-service"
    echo "  Detener:      docker-compose down"
    echo "  Reiniciar:    docker-compose restart"
    echo ""
else
    echo -e "${RED}✗ Error: El contenedor no se inició correctamente${NC}"
    echo "Revisa los logs con: docker-compose logs"
    exit 1
fi
