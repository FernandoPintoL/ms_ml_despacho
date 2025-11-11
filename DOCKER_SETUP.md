# Docker Setup - MS ML Despacho

Este documento explica cómo dockerizar `ms_ml_despacho` manteniendo la conexión a tu BD SQL Server local.

## Requisitos Previos

1. **Docker Desktop instalado** (con soporte para Docker Compose)
2. **SQL Server corriendo en tu máquina local** en el puerto 1433
3. **Base de datos `ms_ml_despacho` creada** en tu SQL Server

## Cambios Realizados

### 1. **Dockerfile**
- Arreglado error de sintaxis (línea 28 con `---`)
- Agregado soporte para Microsoft ODBC Driver 17 para SQL Server
- Mantiene la arquitectura multi-stage para imagen optimizada

### 2. **docker-compose.yml**
- **Removidos**: PostgreSQL, Redis, PgAdmin, Redis Commander, Prometheus, Grafana
- **Mantenido**: Solo el servicio `hads-ml-service`
- **Red**: Usa `bridge` para permitir conexión a servicios en la máquina host
- **Conexión a BD**: Usa `host.docker.internal` (que apunta a 127.0.0.1 en la máquina host)
- **Puerto**: Expone puerto 5000 para la aplicación

### 3. **Variables de Entorno**
El archivo `.env.docker` contiene las variables configuradas para conectar a SQL Server local:

```env
DATABASE_URL=mssql+pyodbc://sa:1234@host.docker.internal:1433/ms_ml_despacho?driver=ODBC+Driver+17+for+SQL+Server
DB_HOST=host.docker.internal
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=1234
DB_NAME=ms_ml_despacho
```

## Pasos para Ejecutar

### Opción 1: Windows (PowerShell)
```powershell
# Navega al directorio
cd D:\SWII\micro_servicios\ms_ml_despacho

# Dale permisos de ejecución al script (solo la primera vez)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Ejecuta el script
.\docker-run.ps1
```

### Opción 2: Linux/Mac/Git Bash
```bash
cd /path/to/ms_ml_despacho

# Dale permisos ejecutable
chmod +x docker-run.sh

# Ejecuta el script
./docker-run.sh
```

### Opción 3: Comandos manuales
```bash
# Construir la imagen
docker-compose build

# Iniciar el contenedor
docker-compose up -d

# Ver logs
docker-compose logs -f hads-ml-service

# Detener
docker-compose down
```

## Verificación

Una vez que el contenedor esté corriendo:

### 1. Ver estado del contenedor
```bash
docker-compose ps
```

### 2. Probar la conexión
```bash
# Health check
curl http://localhost:5000/health

# O desde PowerShell
Invoke-WebRequest -Uri http://localhost:5000/health
```

### 3. Ver logs
```bash
docker-compose logs -f hads-ml-service
```

## Solución de Problemas

### Error: "Cannot connect to SQL Server"
**Causa**: El contenedor no puede alcanzar la BD en el host.

**Solución**:
1. Verifica que SQL Server esté corriendo: `netstat -an | findstr 1433` (Windows) o `netstat -an | grep 1433` (Linux)
2. Asegúrate de que el usuario `sa` y contraseña `1234` sean correctos
3. Prueba la conexión desde el contenedor:
   ```bash
   docker-compose exec hads-ml-service bash
   apt-get install -y python3-pip
   pip install pyodbc
   python3 -c "import pyodbc; conn = pyodbc.connect('Driver={ODBC Driver 17 for SQL Server};Server=host.docker.internal;UID=sa;PWD=1234;Database=ms_ml_despacho')"
   ```

### Error: "Port 5000 already in use"
**Causa**: Ya hay otro proceso usando el puerto 5000.

**Solución**:
```bash
# Encuentra qué proceso usa el puerto
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows

# O cambia el puerto en docker-compose.yml
# ports:
#   - "5001:5000"  # Usa puerto 5001
```

### Error: "ODBC Driver not found"
**Causa**: El driver ODBC no se instaló correctamente en la imagen Docker.

**Solución**:
1. Reconstruye la imagen sin caché:
   ```bash
   docker-compose build --no-cache
   ```
2. Verifica que el Dockerfile tenga la sección de instalación de msodbcsql17

## Comandos Útiles

```bash
# Detener e iniciar sin reconstruir
docker-compose restart

# Ejecutar comandos en el contenedor
docker-compose exec hads-ml-service bash

# Ver uso de recursos
docker stats hads-ml-service

# Limpiar todo (contenedor + red + volúmenes)
docker-compose down -v

# Reconstruir sin caché
docker-compose build --no-cache

# Seguir logs en tiempo real
docker-compose logs -f --tail=50 hads-ml-service
```

## Variables de Entorno Personalizadas

Si quieres usar credenciales diferentes, edita el archivo `.env` antes de ejecutar:

```env
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=tu_base_de_datos
DB_PORT=tu_puerto
```

## Notas Importantes

1. **`host.docker.internal`**: Es un alias especial en Docker Desktop que apunta a la máquina host. Funciona en Windows y Mac, en Linux usa `127.0.0.1` o la IP de tu máquina.

2. **Red del contenedor**: El docker-compose usa `network_mode: bridge` para permitir que el contenedor acceda a servicios en el host.

3. **Volúmenes**: Los directorios `src/`, `models/` y `logs/` están mapeados para desarrollo en vivo. Cambios en estos directorios se reflejan inmediatamente.

4. **Health Check**: Se ejecuta cada 30 segundos. El contenedor se marca como "unhealthy" si falla 3 veces consecutivas.

5. **Credenciales**: Las credenciales de BD en este archivo son de ejemplo. **Cámbialas en producción**.

## Próximos Pasos

- Verifica que la aplicación puede consultar datos de la BD
- Valida que los endpoints `/health` y otros funcionen correctamente
- Integra con otros servicios (si es necesario)
- En producción, usa variables de entorno seguros (secretos)
