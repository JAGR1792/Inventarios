# Manual rápido (Dueña) — Inventarios POS

Este manual es para el día a día (sin programar).

## 1) Dónde se guardan las imágenes

Las fotos de productos se guardan en una carpeta dentro de la **carpeta de datos** de la app ("instance").

- En la app, arriba tienes el botón **Imágenes**: abre la carpeta directamente.

Rutas típicas:
- Si ejecutas desde el proyecto (modo desarrollo): `Inventarios/instance/product_images/` (Probablemente solo yo lo hago así)
- Si es el `.exe` instalado: queda en una carpeta del usuario (AppData), por ejemplo:
  - `C:\Users\TU_USUARIO\AppData\Local\Inventarios_POS\instance\product_images\`

> Nota: el nombre exacto puede variar según el nombre de la app, pero el botón **Imágenes** siempre te lleva al lugar correcto.

## 2) Cómo poner una imagen a un producto (recomendado)

La forma correcta (y más fácil) es desde inventarios:

1. Ve a **INVENTARIO**.
2. Busca el producto.
3. Haz clic en el producto (se abre el modal).
4. Pulsa **Cambiar imagen**.
5. Elige una foto (jpg/png/webp).

La app copiará esa foto a su carpeta y la deja ligada a ese producto.

## 3) Si quieres cambiar una imagen “a mano” en la carpeta

Se puede, pero hay una regla importante:

- La app no “adivina” qué foto va con qué producto solo por copiar archivos.
- La relación producto↔imagen se guarda en la base de datos (mapeo).

Así que el uso “manual” recomendado es solo para **reemplazar** una imagen ya asignada:

1. Primero asigna la imagen una vez usando **Cambiar imagen** (paso 2).
2. Abre la carpeta con el botón **Imágenes**.
3. Identifica el archivo (normalmente se llama como la clave del producto, por ejemplo: `ABC123.jpg`).
4. Reemplaza el archivo por otro, usando **el mismo nombre y extensión**.

Consejos:
- Mantén el mismo formato (por ejemplo, reemplazar `.jpg` por `.jpg`).
- Si cambias la extensión (ej: de `.jpg` a `.png`), la app puede seguir apuntando al archivo viejo.

## 4) Qué pasa si usas “Reiniciar DB”

El botón **Reiniciar DB**:
- Borra ventas y movimientos de caja.
- Pone el stock en 0.
- **NO borra imágenes** (ni los archivos, ni los mapeos de qué foto corresponde a cada producto).

## 5) Recomendaciones de fotos

- Tamaño recomendado: 600×600 o 800×800 (cuadradas se ven mejor).
- Formatos: `.jpg`, `.png`, `.webp`.
- Evita fotos gigantes (más de 5–10 MB) para que cargue rápido.

## 6) Modo Tablet (WiFi/LAN) — cómo se inicia

Para que la tablet funcione, **la PC “servidor” debe tener el servidor iniciado**.

### Opción A (recomendada): con instalador y accesos directos

Cuando está instalado, deberías ver un acceso directo que se llama:
- **Inventarios POS - Servidor Tablet**

1. En la PC, haz doble clic en **Inventarios POS - Servidor Tablet**.
2. Sale un mensaje indicando la dirección (URL) para abrir en la tablet (ej: `http://192.168.1.50:8000/`).
3. En la tablet (en el navegador), abre esa dirección.

Durante la instalación, también puede aparecer una pregunta:
- **“¿Quieres que el Servidor Tablet se inicie automáticamente al prender Windows?”**

Si eliges **Sí**, la tablet funcionará aunque nadie abra nada (solo con prender la PC).

> Si NO ves el acceso directo “Servidor Tablet”, normalmente significa que el instalador no incluyó el ejecutable del servidor.
> En ese caso, busca en la carpeta donde quedó instalado y ejecuta:
> - `InventariosServer.exe`
> (también puedes crear un acceso directo a ese archivo).

### Opción B: si el servidor ya estaba iniciado

Si intentas iniciarlo y ya está funcionando, puede salir un aviso de que el puerto está ocupado.
En ese caso **no pasa nada**: normalmente significa que **ya está corriendo**.

### Opción C (solo si usas el proyecto en la PC, no el instalador)
Si estás usando el proyecto (con Python y dependencias instaladas), puedes iniciar con doble clic:

- `IniciarServidorTablet_Oculto.vbs` (recomendado)
- `IniciarServidorTablet.bat`

Y para detenerlo:

- `DetenerServidorTablet.bat`
