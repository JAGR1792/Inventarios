# Integración con Google Sheets

Este documento explica cómo configurar la sincronización automática del inventario con Google Sheets.

## 🎯 Funcionalidad

La integración permite:
- **Exportar** inventario automáticamente a Google Sheets
- **Importar** cambios desde Google Sheets al sistema
- **Sincronización bidireccional** en tiempo real
- **Acceso desde cualquier lugar** con tu cuenta de Google

## 📋 Requisitos Previos

1. Cuenta de Google (Gmail)
2. Acceso a Google Cloud Console
3. Python 3.11+ instalado

## 🚀 Configuración Paso a Paso

### 1. Instalar Dependencias

Descomenta las líneas en `requirements.txt` y ejecuta:

```powershell
pip install google-auth google-auth-oauthlib google-api-python-client
```

### 2. Crear Proyecto en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto nuevo: **"Inventarios POS"**
3. Selecciona el proyecto

### 3. Habilitar Google Sheets API

1. En el menú lateral: **APIs y servicios** → **Biblioteca**
2. Busca: **"Google Sheets API"**
3. Haz clic en **HABILITAR**

### 4. Crear Credenciales OAuth 2.0

1. Ve a **APIs y servicios** → **Credenciales**
2. Clic en **+ CREAR CREDENCIALES** → **ID de cliente de OAuth**
3. Si te pide configurar pantalla de consentimiento:
   - Tipo: **Externo**
   - Nombre: **Inventarios POS**
   - Correo: tu correo
   - Guarda y continúa
4. Tipo de aplicación: **Aplicación de escritorio**
5. Nombre: **Inventarios POS Desktop**
6. Clic en **CREAR**
7. **DESCARGAR JSON** → guárdalo como `credentials.json` en la carpeta del proyecto

### 5. Crear Google Spreadsheet

1. Ve a [Google Sheets](https://sheets.google.com/)
2. Crea una nueva hoja: **"Inventario POS"**
3. Copia el **ID del spreadsheet** de la URL:
   ```
   https://docs.google.com/spreadsheets/d/TU_ID_AQUI/edit
   ```

### 6. Configurar Variables de Entorno

Crea o edita el archivo `.env` en la raíz del proyecto:

```env
# Google Sheets Integration
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=tu_spreadsheet_id_aqui
GOOGLE_SHEETS_WORKSHEET_NAME=INVENTARIO
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
GOOGLE_SHEETS_SYNC_INTERVAL_SECONDS=300
```

**Importante**: Reemplaza `tu_spreadsheet_id_aqui` con el ID real de tu spreadsheet.

### 7. Primera Ejecución - Autorizar Acceso

1. Ejecuta el servidor:
   ```powershell
   python run_server.py
   ```

2. Se abrirá automáticamente tu navegador pidiendo permiso
3. Selecciona tu cuenta de Google
4. Acepta los permisos (ver y editar tus hojas de cálculo)
5. Se generará automáticamente `token.json` (no lo compartas)

## 🔄 Uso Diario

Una vez configurado, la sincronización es automática:

### Exportar a Google Sheets

```python
from inventarios.google_sheets import GoogleSheetsSync
from inventarios.repos import ProductRepo
from inventarios.db import session_scope

sync = GoogleSheetsSync()
if sync.enabled:
    with session_scope() as session:
        repo = ProductRepo(session)
        products = repo.list()
        sync.export_products(products)
```

### Importar desde Google Sheets

```python
from inventarios.google_sheets import GoogleSheetsSync

sync = GoogleSheetsSync()
if sync.enabled:
    products = sync.import_products()
    # Actualizar base de datos con productos importados
```

## 🎨 Interfaz de Usuario

Ya agregué:
- **Menú desplegable tipo acordeón** para organizar secciones
- **Slider horizontal** en productos estrella (desliza con mouse o touch)
- **Mejor visualización** de últimas ventas

## 📊 Estructura de Google Sheets

El spreadsheet tendrá las siguientes columnas:

| key | producto | descripcion | unidades | precio_final |
|-----|----------|-------------|----------|--------------|
| Coca Cola - 500ml | Coca Cola | 500ml | 10 | 3500.00 |
| Papas Margarita - 150g | Papas Margarita | 150g | 5 | 2500.00 |

## 🔒 Seguridad

- **credentials.json**: Contiene ID de cliente (seguro compartir en equipo)
- **token.json**: Contiene tus tokens de acceso (NO compartir, gitignore)
- Los tokens se refrescan automáticamente
- Puedes revocar acceso en cualquier momento desde tu cuenta de Google

## 🐛 Troubleshooting

### Error: "credentials.json not found"
- Asegúrate de haber descargado el archivo de Google Cloud Console
- Colócalo en la raíz del proyecto

### Error: "Token expired"
- Elimina `token.json`
- Vuelve a ejecutar el servidor para re-autorizar

### Error: "Spreadsheet not found"
- Verifica que el ID del spreadsheet sea correcto
- Asegúrate de que la hoja tenga permisos de lectura/escritura

### No se sincronizan los cambios
- Verifica que `GOOGLE_SHEETS_ENABLED=true` en `.env`
- Revisa los logs para mensajes de error
- El intervalo por defecto es 5 minutos (300 segundos)

## 📝 Próximos Pasos

Para implementar sincronización automática en background:
1. Crear tarea programada (Windows Task Scheduler)
2. O usar un servicio de background con APScheduler
3. Agregar botón manual "Sincronizar ahora" en la UI

## 🔗 Enlaces Útiles

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Sheets API Docs](https://developers.google.com/sheets/api)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
