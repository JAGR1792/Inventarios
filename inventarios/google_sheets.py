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
