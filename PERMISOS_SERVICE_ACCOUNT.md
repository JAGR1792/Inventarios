# 📋 PASO FINAL: Dar Permisos al Service Account

Tu archivo `KEY.json` es una **Service Account** (cuenta de servicio). Para que funcione, necesitas darle permisos para acceder a tu Google Sheet.

## 🔑 Email del Service Account

```
garom-40@inventario-garom.iam.gserviceaccount.com
```

## 📝 Pasos para dar permisos:

### 1. Abre tu Google Sheet
Ve a: https://docs.google.com/spreadsheets/d/1XzAJhg7FPxL86sblcGYmqZTzgqJjffRi/edit

### 2. Compartir con el Service Account

1. Haz clic en el botón **"Compartir"** (arriba a la derecha)
2. En el campo "Añadir personas y grupos", pega:
   ```
   garom-40@inventario-garom.iam.gserviceaccount.com
   ```
3. Selecciona el rol: **Editor** (para que pueda leer y escribir)
4. **DESMARCA** la casilla "Notificar a las personas" (no es necesario notificar a un bot)
5. Clic en **"Compartir"** o **"Enviar"**

### 3. ¡Listo!

Una vez compartido, el sistema podrá:
- ✅ Leer productos desde Google Sheets
- ✅ Escribir/actualizar productos en Google Sheets
- ✅ Sincronización automática en tiempo real

## 🧪 Probar la configuración

Ejecuta el script de prueba:

```powershell
python scripts/test_google_sheets.py
```

Deberías ver:
- ✅ Librerías instaladas
- ✅ Credenciales encontradas
- ✅ Spreadsheet ID configurado
- ✅ Menú de opciones para importar/exportar

## 🎯 Uso en la Aplicación

### Importar (Botón "Importar")
- Ahora importará automáticamente desde Google Sheets
- Ya no te pedirá seleccionar un archivo
- Descarga directamente desde la nube

### Exportar (Botón "Exportar")
- Exporta automáticamente a Google Sheets
- **En tiempo real** - actualización instantánea
- Ya no necesitas seleccionar archivo

## 📊 Estructura del Google Sheet

El sistema espera esta estructura en la hoja llamada "INVENTARIO":

| key | producto | descripcion | unidades | precio_final |
|-----|----------|-------------|----------|--------------|
| Coca Cola - 500ml | Coca Cola | 500ml | 10 | 3500 |
| Papas - 150g | Papas Margarita | 150g | 5 | 2500 |

**Headers en fila 1, datos desde fila 2**

## ⚙️ Configuración Actual en .env

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=1XzAJhg7FPxL86sblcGYmqZTzgqJjffRi
GOOGLE_SHEETS_WORKSHEET_NAME=INVENTARIO
GOOGLE_CREDENTIALS_FILE=KEY.json
```

## 🔄 Sincronización Automática (Opcional)

Si quieres que exporte automáticamente cada 5 minutos, puedes configurar un scheduler. Por ahora, la exportación se hace:
- Al presionar "Exportar"
- Al cerrar caja (si está configurado)

## ⚠️ Importante

- El Service Account **NO necesita autenticación OAuth** (no se abrirá navegador)
- Debe tener permisos de **Editor** en el spreadsheet
- El archivo `KEY.json` debe estar en la raíz del proyecto
- **NO compartas** el archivo `KEY.json` públicamente (contiene la clave privada)

## 🐛 Problemas Comunes

### Error: "Insufficient permissions"
→ Asegúrate de haber compartido el spreadsheet con el email del Service Account

### Error: "Spreadsheet not found"
→ Verifica que el ID del spreadsheet sea correcto en `.env`

### Error: "Worksheet INVENTARIO not found"
→ Asegúrate de que la hoja se llame exactamente "INVENTARIO" (mayúsculas)

### No se actualizan los datos
→ Revisa que los headers sean exactos: `key`, `producto`, `descripcion`, `unidades`, `precio_final`
