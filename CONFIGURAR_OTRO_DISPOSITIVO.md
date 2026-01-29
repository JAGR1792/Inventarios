# 🔧 Configurar en Otro Dispositivo

Esta guía te ayuda a configurar la aplicación en un segundo dispositivo (laptop, tablet, etc.) para que ambos sincronicen con el mismo Google Sheets.

## 📋 Requisitos

- Python 3.11+ instalado
- Git (opcional, para clonar el proyecto)
- Acceso al Google Sheet compartido

## 🚀 Pasos de Instalación

### 1️⃣ Copiar el Proyecto

**Opción A: Clonar desde GitHub**
```powershell
git clone https://github.com/TU_USUARIO/Inventarios.git
cd Inventarios
```

**Opción B: Copiar carpeta manualmente**
- Copia toda la carpeta del proyecto al nuevo dispositivo
- Colócala en una ubicación como `C:\Users\TU_USUARIO\Documents\GitHub\Inventarios`

### 2️⃣ Copiar Archivos de Configuración

Copia estos **2 archivos** desde el dispositivo original:

```
KEY.json        → Credenciales de Google Cloud (Service Account)
.env            → Configuración de la aplicación
```

Colócalos en la **raíz del proyecto** (mismo nivel que `main.py`)

### 3️⃣ Instalar Dependencias

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
pip install -r requirements.txt
```

### 4️⃣ Verificar Configuración

Abre el archivo `.env` y confirma que tenga:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=1bz8eO7vDA8H0YTViEKfI_Snil3Yibh9qnd_3mirAH9M
GOOGLE_SHEETS_WORKSHEET_NAME=INVENTARIO
GOOGLE_CREDENTIALS_FILE=KEY.json
```

### 5️⃣ Probar la Conexión

Ejecuta el script de prueba:

```powershell
python scripts/test_google_sheets.py
```

Si ves "✅ Importados X productos", ¡está funcionando!

### 6️⃣ Iniciar la Aplicación

**Para escritorio:**
```powershell
python run_desktop.py
```

**Para tablet (servidor web):**
```powershell
python run_server.py
```

## 🔄 Sincronización Automática

La aplicación **sincroniza automáticamente**:

✅ **Al iniciar**: Importa productos desde Google Sheets  
✅ **Al editar productos**: Exporta cambios inmediatamente  
✅ **Al cambiar stock**: Exporta automáticamente  
✅ **Al crear/eliminar productos**: Exporta automáticamente  
✅ **Al cerrar caja**: Exporta inventario completo

## ⚠️ Notas Importantes

### Base de Datos Local
- Cada dispositivo tiene su propia base de datos SQLite local (`instance/pos.sqlite`)
- Las **ventas NO se sincronizan** entre dispositivos (solo el inventario)
- El inventario se sincroniza a través de Google Sheets

### Uso Simultáneo
- **✅ Puedes editar productos desde ambos dispositivos**
- **⚠️ Si ambos exportan al mismo tiempo, el último sobrescribe**
- **💡 Recomendación**: Usa un dispositivo principal para editar inventario

### Conflictos
Si ambos dispositivos editan el mismo producto al mismo tiempo:
1. El último cambio gana (sobrescribe el anterior)
2. Para resolver: Importa manualmente desde Google Sheets

## 🛠️ Solución de Problemas

### Error: "This operation is not supported"
- El archivo debe ser un **Google Sheets nativo** (no una conversión/preview)
- Solución: Archivo → Guardar como Google Sheets

### Error: "Insufficient permissions"
- El Service Account no tiene permisos
- Solución: Comparte el Google Sheet con el email `garom-40@inventario-garom.iam.gserviceaccount.com` como **Editor**

### No importa/exporta automáticamente
- Verifica que `GOOGLE_SHEETS_ENABLED=true` en `.env`
- Verifica que `KEY.json` exista en la raíz del proyecto
- Revisa los logs en la consola al iniciar la app

## 📁 Archivos que NO Debes Compartir en Git

Si usas Git, agrega esto a `.gitignore`:

```gitignore
.env
KEY.json
instance/
*.sqlite
*.sqlite-shm
*.sqlite-wal
```

## 🆘 Ayuda Rápida

**Ver logs detallados:**
```powershell
python run_desktop.py
# Observa la consola al iniciar
```

**Forzar importación manual:**
- Abre la app → Inventario → Botón "Importar"

**Forzar exportación manual:**
- Abre la app → Inventario → Botón "Exportar"

---

**¿Problemas?** Revisa el archivo de logs o contacta al desarrollador.
