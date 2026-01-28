# 🚀 Configuración Rápida de Google Sheets

## 📍 PASO 1: Abre tu archivo .env

**Ubicación**: `c:\Users\jorge\Documents\GitHub\Inventarios\.env`

Ya agregué las configuraciones necesarias. Busca esta sección:

```env
# ===== GOOGLE SHEETS INTEGRATION =====
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SHEETS_WORKSHEET_NAME=INVENTARIO
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
GOOGLE_SHEETS_SYNC_INTERVAL_SECONDS=300
```

## 📍 PASO 2: Crea tu Google Sheet

1. **Ve a**: https://sheets.google.com/
2. **Crea** una nueva hoja o abre una existente
3. **Copia el ID** de la URL:

```
https://docs.google.com/spreadsheets/d/1ABC123xyz-ESTE_ES_EL_ID_456/edit
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
```

4. **Pega el ID** en `.env`:

```env
GOOGLE_SHEETS_SPREADSHEET_ID=1ABC123xyz-ESTE_ES_EL_ID_456
```

## 📍 PASO 3: Obtén credentials.json de Google Cloud

### 3.1 Crear Proyecto

1. Ve a: https://console.cloud.google.com/
2. Clic en el menú desplegable de proyectos (arriba)
3. **"Proyecto Nuevo"**
4. Nombre: `Inventarios POS`
5. **Crear**

### 3.2 Habilitar Google Sheets API

1. En el menú lateral: **APIs y servicios** → **Biblioteca**
2. Busca: `Google Sheets API`
3. Clic en el resultado
4. **HABILITAR**

### 3.3 Configurar Pantalla de Consentimiento

1. **APIs y servicios** → **Pantalla de consentimiento de OAuth**
2. Tipo de usuario: **Externo**
3. **Crear**
4. Llena los campos:
   - Nombre de la app: `Inventarios POS`
   - Correo de asistencia: tu correo
   - Dominios autorizados: (deja vacío)
   - Correo del desarrollador: tu correo
5. **Guardar y continuar**
6. **Agregar o quitar alcances**: puedes saltar esto
7. **Guardar y continuar**
8. **Usuarios de prueba**: agrega tu correo de Gmail
9. **Guardar y continuar**

### 3.4 Crear Credenciales OAuth 2.0

1. **APIs y servicios** → **Credenciales**
2. **+ CREAR CREDENCIALES** → **ID de cliente de OAuth**
3. Tipo de aplicación: **Aplicación de escritorio**
4. Nombre: `Inventarios POS Desktop`
5. **CREAR**
6. Aparecerá un diálogo con tu client ID
7. **DESCARGAR JSON**

### 3.5 Colocar credentials.json

**Guarda el archivo descargado como**:
```
c:\Users\jorge\Documents\GitHub\Inventarios\credentials.json
```

**IMPORTANTE**: El archivo debe llamarse exactamente `credentials.json`

## 📍 PASO 4: Primera Ejecución (Autorizar)

Una vez que tengas:
- ✅ El ID del spreadsheet en `.env`
- ✅ El archivo `credentials.json` en la raíz del proyecto

Ejecuta el script de prueba:

```powershell
python scripts/test_google_sheets.py
```

**Se abrirá tu navegador automáticamente** pidiendo permiso:

1. Selecciona tu cuenta de Google
2. Verás una advertencia "Google hasn't verified this app"
3. Clic en **"Avanzado"** o **"Advanced"**
4. Clic en **"Ir a Inventarios POS (no seguro)"**
5. Acepta los permisos
6. Se generará automáticamente `token.json` (NO lo compartas)

## 🎯 PASO 5: ¡Listo para usar!

El script te mostrará un menú:

```
1. Exportar inventario actual a Google Sheets
2. Importar desde Google Sheets
3. Ver productos en base de datos local
4. Salir
```

### Exportar (1)
- Toma todos los productos de tu base de datos
- Los sube a Google Sheets
- Puedes editarlos desde cualquier lugar

### Importar (2)
- Lee los productos desde Google Sheets
- Los actualiza en tu base de datos local
- Sincronización bidireccional

## 📂 Archivos Importantes

```
Inventarios/
├── .env                    ← Aquí va el SPREADSHEET_ID
├── credentials.json        ← Descarga desde Google Cloud
├── token.json             ← Se genera automáticamente (gitignored)
├── GOOGLE_SHEETS_SETUP.md ← Guía completa con más detalles
└── scripts/
    └── test_google_sheets.py ← Script de prueba
```

## ⚠️ Seguridad

- **credentials.json**: Puedes compartir con tu equipo (es el ID de cliente)
- **token.json**: NO compartir (contiene tus tokens de acceso)
- El `.gitignore` ya está configurado para no subir `token.json`

## 🐛 Problemas Comunes

### Error: "File credentials.json not found"
→ Asegúrate de que el archivo esté en la raíz: `c:\Users\jorge\Documents\GitHub\Inventarios\credentials.json`

### Error: "SPREADSHEET_ID not configured"
→ Edita `.env` y agrega el ID del spreadsheet

### Error: "Access blocked: This app's request is invalid"
→ Asegúrate de haber agregado tu correo en "Usuarios de prueba" en Google Cloud Console

### La autorización no se abre en el navegador
→ El script mostrará una URL, cópiala y pégala manualmente en tu navegador

## 📞 Ayuda

Si tienes problemas:
1. Lee la guía completa: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)
2. Verifica los logs en la consola
3. Asegúrate de que todos los pasos anteriores estén completos

## ✨ Próximo Paso

Una vez configurado, puedes integrar la sincronización automática en el servidor agregando un scheduler en `run_server.py` para que exporte el inventario cada 5 minutos automáticamente.
