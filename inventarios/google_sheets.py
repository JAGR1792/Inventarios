"""
Integración con Google Sheets para sincronización automática del inventario.

Requisitos:
1. Instalar dependencias: pip install google-auth google-auth-oauthlib google-api-python-client
2. Crear proyecto en Google Cloud Console: https://console.cloud.google.com/
3. Habilitar Google Sheets API
4. Crear credenciales OAuth 2.0 y descargar como credentials.json
5. Configurar variables de entorno en .env:
   GOOGLE_SHEETS_ENABLED=true
   GOOGLE_SHEETS_SPREADSHEET_ID=tu_spreadsheet_id
   GOOGLE_SHEETS_WORKSHEET_NAME=INVENTARIO
   
Uso:
    from inventarios.google_sheets import GoogleSheetsSync
    
    sync = GoogleSheetsSync()
    if sync.enabled:
        # Exportar productos a Google Sheets
        sync.export_products(products)
        
        # Importar productos desde Google Sheets
        products = sync.import_products()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from inventarios.settings import Settings

logger = logging.getLogger(__name__)

# Google Sheets imports are optional
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.info("Google Sheets libraries not available. Install with: pip install google-auth google-auth-oauthlib google-api-python-client")


# If modifying scopes, delete token.json
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


@dataclass
class SheetProduct:
    """Producto en formato de Google Sheets."""
    key: str
    producto: str
    descripcion: str
    unidades: int
    precio_final: Decimal


class GoogleSheetsSync:
    """Sincronización bidireccional con Google Sheets."""
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.enabled = self.settings.GOOGLE_SHEETS_ENABLED and GOOGLE_SHEETS_AVAILABLE
        self._service = None
        
        if not GOOGLE_SHEETS_AVAILABLE and self.settings.GOOGLE_SHEETS_ENABLED:
            logger.warning(
                "Google Sheets está habilitado en configuración pero las librerías no están instaladas. "
                "Instala con: pip install google-auth google-auth-oauthlib google-api-python-client"
            )
    
    def _get_credentials(self) -> Credentials | None:
        """Obtiene credenciales de Google (Service Account o OAuth2)."""
        if not self.enabled:
            return None
            
        creds_file = Path(self.settings.GOOGLE_CREDENTIALS_FILE)
        
        if not creds_file.exists():
            logger.error(
                f"Archivo de credenciales {creds_file} no encontrado. "
                "Descárgalo desde Google Cloud Console."
            )
            return None
        
        # Detectar si es Service Account o OAuth2
        try:
            import json
            with open(creds_file, 'r') as f:
                creds_data = json.load(f)
            
            # Si tiene "type": "service_account", usar Service Account
            if creds_data.get('type') == 'service_account':
                logger.info("Usando Service Account para autenticación")
                creds = service_account.Credentials.from_service_account_file(
                    str(creds_file),
                    scopes=SCOPES
                )
                return creds
        except Exception as e:
            logger.warning(f"Error detectando tipo de credenciales: {e}")
        
        # Flujo OAuth2 tradicional (si no es Service Account)
        logger.info("Usando OAuth2 para autenticación")
        creds = None
        token_file = Path(self.settings.GOOGLE_TOKEN_FILE)
        
        # El archivo token.json guarda los tokens de acceso y refresh del usuario
        if token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            except Exception as e:
                logger.error(f"Error cargando token: {e}")
        
        # Si no hay credenciales válidas, pedir login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refrescando token: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Error en flujo OAuth: {e}")
                    return None
            
            # Guardar credenciales para la próxima ejecución
            try:
                token_file.write_text(creds.to_json())
            except Exception as e:
                logger.error(f"Error guardando token: {e}")
        
        return creds
    
    def _get_service(self):
        """Obtiene el servicio de Google Sheets API."""
        if not self.enabled:
            return None
            
        if self._service:
            return self._service
            
        creds = self._get_credentials()
        if not creds:
            return None
            
        try:
            self._service = build('sheets', 'v4', credentials=creds)
            return self._service
        except Exception as e:
            logger.error(f"Error creando servicio de Google Sheets: {e}")
            return None
    
    def export_products(self, products: list[Any]) -> bool:
        """
        Exporta productos a Google Sheets.
        
        Args:
            products: Lista de objetos Product de SQLAlchemy
            
        Returns:
            True si la exportación fue exitosa
        """
        if not self.enabled:
            logger.info("Google Sheets sync no habilitado")
            return False
            
        service = self._get_service()
        if not service:
            return False
        
        try:
            spreadsheet_id = self.settings.GOOGLE_SHEETS_SPREADSHEET_ID
            worksheet_name = self.settings.GOOGLE_SHEETS_WORKSHEET_NAME
            
            # Preparar datos con el formato que usa la dueña
            headers = [['PRODUCTO', 'PESO', 'UNIDADES', 'PRECIO UNITARIO VENTA']]
            rows = []
            
            for p in products:
                # Extraer producto y peso del key o campos separados
                producto_nombre = p.producto
                peso = p.descripcion or ''
                
                # Formatear precio con signo $ y separador de miles
                precio_str = f"$ {int(p.precio_final):,}".replace(',', '.')
                
                rows.append([
                    producto_nombre,
                    peso,
                    int(p.unidades),
                    precio_str
                ])
            
            values = headers + rows
            
            # Limpiar hoja y escribir datos
            range_name = f'{worksheet_name}!A1:D{len(values)}'
            
            # Primero limpiar la hoja
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f'{worksheet_name}!A:D'
            ).execute()
            
            # Luego escribir datos
            body = {'values': values}
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',  # Permite que Google interprete los valores
                body=body
            ).execute()
            
            updated = result.get('updatedCells', 0)
            logger.info(f"Exportados {len(products)} productos a Google Sheets ({updated} celdas actualizadas)")
            return True
            
        except Exception as e:
            logger.error(f"Error exportando a Google Sheets: {e}")
            return False
    
    def import_products(self) -> list[SheetProduct]:
        """
        Importa productos desde Google Sheets.
        Lee el formato: PRODUCTO, PESO, UNIDADES, PRECIO UNITARIO VENTA
        
        Returns:
            Lista de productos en formato SheetProduct
        """
        if not self.enabled:
            logger.info("Google Sheets sync no habilitado")
            return []
            
        service = self._get_service()
        if not service:
            return []
        
        try:
            spreadsheet_id = self.settings.GOOGLE_SHEETS_SPREADSHEET_ID
            worksheet_name = self.settings.GOOGLE_SHEETS_WORKSHEET_NAME
            range_name = f'{worksheet_name}!A2:D'  # Saltar headers, leer hasta columna D
            
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            rows = result.get('values', [])
            products = []
            
            for row in rows:
                if len(row) < 3:  # Necesitamos al menos PRODUCTO, PESO, UNIDADES
                    continue
                    
                try:
                    # Columna A: PRODUCTO
                    producto = str(row[0]).strip()
                    if not producto:
                        continue
                    
                    # Columna B: PESO (descripcion)
                    peso = str(row[1]).strip() if len(row) > 1 else ''
                    
                    # Columna C: UNIDADES (stock)
                    unidades_raw = str(row[2]).strip() if len(row) > 2 else '0'
                    # Limpiar posibles caracteres no numéricos
                    unidades_clean = ''.join(c for c in unidades_raw if c.isdigit())
                    unidades = int(unidades_clean) if unidades_clean else 0
                    
                    # Columna D: PRECIO UNITARIO VENTA
                    precio_raw = str(row[3]).strip() if len(row) > 3 else '0'
                    # Limpiar $ y separadores de miles (puntos)
                    precio_clean = precio_raw.replace('$', '').replace('.', '').replace(',', '.').strip()
                    precio = Decimal(precio_clean) if precio_clean else Decimal('0')
                    
                    # Generar key como "PRODUCTO - PESO"
                    key = f"{producto} - {peso}" if peso else producto
                    
                    product = SheetProduct(
                        key=key,
                        producto=producto,
                        descripcion=peso,
                        unidades=unidades,
                        precio_final=precio
                    )
                    products.append(product)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parseando fila {row}: {e}")
                    continue
            
            logger.info(f"Importados {len(products)} productos desde Google Sheets")
            return products
            
        except Exception as e:
            logger.error(f"Error importando desde Google Sheets: {e}")
            return []
    
    def get_spreadsheet_url(self) -> str:
        """Obtiene la URL del spreadsheet configurado."""
        if not self.settings.GOOGLE_SHEETS_SPREADSHEET_ID:
            return ""
        return f"https://docs.google.com/spreadsheets/d/{self.settings.GOOGLE_SHEETS_SPREADSHEET_ID}/edit"
    
    def _ensure_worksheet_exists(self, service, spreadsheet_id: str, worksheet_name: str) -> bool:
        """Asegura que la hoja existe, creándola si es necesario."""
        try:
            # Obtener información del spreadsheet para ver las hojas existentes
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            # Verificar si la hoja ya existe
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == worksheet_name:
                    return True
            
            # Crear la hoja si no existe
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': worksheet_name
                        }
                    }
                }]
            }
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            logger.info(f"Creada nueva hoja: {worksheet_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error verificando/creando hoja {worksheet_name}: {e}")
            return False
    
    def export_sales(self, sales: list) -> bool:
        """
        Exporta ventas a la hoja VENTAS en Google Sheets.
        Cada venta se registra como una fila (factura) con sus productos resumidos.
        """
        if not self.enabled:
            logger.warning("Google Sheets no está configurado")
            return False
            
        service = self._get_service()
        if not service:
            return False
            
        try:
            spreadsheet_id = self.settings.GOOGLE_SHEETS_SPREADSHEET_ID
            worksheet_name = "VENTAS"
            
            # Asegurar que la hoja VENTAS existe
            if not self._ensure_worksheet_exists(service, spreadsheet_id, worksheet_name):
                return False
            
            # Headers para la hoja VENTAS (formato factura)
            headers = [
                "ID VENTA",
                "FECHA",
                "HORA",
                "METODO PAGO",
                "PRODUCTOS",
                "CANT. ITEMS",
                "TOTAL VENTA"
            ]
            
            # Preparar datos - una fila por venta (factura)
            rows = [headers]
            
            for sale in sales:
                sale_id = sale.id
                fecha = sale.created_at.strftime("%Y-%m-%d")
                hora = sale.created_at.strftime("%H:%M:%S")
                metodo = sale.payment_method.upper()
                total_venta = float(sale.total)
                
                # Construir resumen de productos
                productos_list = []
                total_items = 0
                for line in sale.lines:
                    qty = int(line.qty)
                    total_items += qty
                    desc = line.descripcion or ""
                    if qty > 1:
                        productos_list.append(f"{qty}x {line.producto} {desc}".strip())
                    else:
                        productos_list.append(f"{line.producto} {desc}".strip())
                
                productos_str = " | ".join(productos_list)
                
                # Formatear total con signo $
                total_str = f"$ {int(total_venta):,}".replace(',', '.')
                
                row = [
                    sale_id,
                    fecha,
                    hora,
                    metodo,
                    productos_str,
                    total_items,
                    total_str
                ]
                rows.append(row)
            
            # Limpiar hoja y escribir datos
            range_name = f'{worksheet_name}!A1:G{len(rows)}'
            
            # Primero limpiar la hoja
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f'{worksheet_name}!A:J'
            ).execute()
            
            # Luego escribir datos
            body = {'values': rows}
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            updated = result.get('updatedCells', 0)
            logger.info(f"Exportadas {len(sales)} ventas a Google Sheets ({updated} celdas)")
            return True
            
        except Exception as e:
            logger.error(f"Error exportando ventas a Google Sheets: {e}")
            return False
