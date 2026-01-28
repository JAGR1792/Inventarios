"""
Script de prueba para Google Sheets Integration.

Este script te ayuda a:
1. Verificar que las credenciales estén configuradas
2. Probar la conexión con Google Sheets
3. Exportar el inventario actual
4. Importar desde Google Sheets
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inventarios.google_sheets import GoogleSheetsSync, GOOGLE_SHEETS_AVAILABLE
from inventarios.settings import Settings
from inventarios.db import create_engine_from_url, make_session_factory, session_scope, init_db
from inventarios.repos import ProductRepo


def main():
    print("=" * 60)
    print("Google Sheets Integration - Test Script")
    print("=" * 60)
    print()
    
    # Verificar que las librerías estén instaladas
    if not GOOGLE_SHEETS_AVAILABLE:
        print("❌ ERROR: Las librerías de Google Sheets no están instaladas.")
        print()
        print("Instala con:")
        print("  pip install google-auth google-auth-oauthlib google-api-python-client")
        print()
        return 1
    
    print("✅ Librerías de Google Sheets instaladas correctamente")
    print()
    
    # Verificar configuración
    settings = Settings()
    
    # Crear engine y session factory
    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    factory = make_session_factory(engine)
    print("📋 Configuración actual:")
    print(f"  GOOGLE_SHEETS_ENABLED: {settings.GOOGLE_SHEETS_ENABLED}")
    print(f"  GOOGLE_SHEETS_SPREADSHEET_ID: {settings.GOOGLE_SHEETS_SPREADSHEET_ID or '(no configurado)'}")
    print(f"  GOOGLE_SHEETS_WORKSHEET_NAME: {settings.GOOGLE_SHEETS_WORKSHEET_NAME}")
    print(f"  GOOGLE_CREDENTIALS_FILE: {settings.GOOGLE_CREDENTIALS_FILE}")
    print()
    
    if not settings.GOOGLE_SHEETS_ENABLED:
        print("⚠️  Google Sheets está deshabilitado en .env")
        print("   Cambia GOOGLE_SHEETS_ENABLED=true para habilitar")
        print()
        return 1
    
    if not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
        print("⚠️  GOOGLE_SHEETS_SPREADSHEET_ID no está configurado en .env")
        print()
        print("Pasos para configurar:")
        print("1. Ve a https://sheets.google.com/")
        print("2. Crea una nueva hoja o usa una existente")
        print("3. Copia el ID de la URL:")
        print("   https://docs.google.com/spreadsheets/d/TU_ID_AQUI/edit")
        print("4. Pégalo en .env en la línea:")
        print("   GOOGLE_SHEETS_SPREADSHEET_ID=TU_ID_AQUI")
        print()
        return 1
    
    # Verificar credentials.json
    creds_file = Path(settings.GOOGLE_CREDENTIALS_FILE)
    if not creds_file.exists():
        print(f"⚠️  Archivo {settings.GOOGLE_CREDENTIALS_FILE} no encontrado")
        print()
        print("Pasos para obtener credentials.json:")
        print("1. Ve a https://console.cloud.google.com/")
        print("2. Crea un proyecto o selecciona uno existente")
        print("3. Habilita Google Sheets API")
        print("4. Crea credenciales OAuth 2.0 (tipo: Aplicación de escritorio)")
        print("5. Descarga el JSON y guárdalo como 'credentials.json'")
        print(f"6. Colócalo en: {creds_file.absolute()}")
        print()
        print("Ver guía completa en: GOOGLE_SHEETS_SETUP.md")
        print()
        return 1
    
    print(f"✅ Archivo de credenciales encontrado: {creds_file}")
    print()
    
    # Inicializar sincronización
    print("🔄 Inicializando Google Sheets...")
    sync = GoogleSheetsSync(settings)
    
    if not sync.enabled:
        print("❌ Google Sheets sync no pudo inicializarse")
        return 1
    
    print("✅ Google Sheets inicializado correctamente")
    print()
    
    # Mostrar URL del spreadsheet
    url = sync.get_spreadsheet_url()
    print(f"📊 Spreadsheet URL: {url}")
    print()
    
    # Menú de opciones
    while True:
        print("=" * 60)
        print("Opciones:")
        print("  1. Exportar inventario actual a Google Sheets")
        print("  2. Importar desde Google Sheets")
        print("  3. Ver productos en base de datos local")
        print("  4. Salir")
        print()
        
        opcion = input("Selecciona una opción (1-4): ").strip()
        print()
        
        if opcion == "1":
            # Exportar
            print("📤 Exportando inventario a Google Sheets...")
            with session_scope(factory) as session:
                repo = ProductRepo(session)
                products = repo.list(limit=9999)
                
                if not products:
                    print("⚠️  No hay productos en la base de datos local")
                    print()
                    continue
                
                print(f"   Encontrados {len(products)} productos")
                success = sync.export_products(products)
                
                if success:
                    print(f"✅ Exportación exitosa!")
                    print(f"   Ver en: {url}")
                else:
                    print("❌ Error en la exportación")
                print()
        
        elif opcion == "2":
            # Importar
            print("📥 Importando desde Google Sheets...")
            products = sync.import_products()
            
            if not products:
                print("⚠️  No se encontraron productos en Google Sheets")
                print("   O la hoja está vacía o hay un error")
                print()
                continue
            
            print(f"✅ Importados {len(products)} productos:")
            for i, p in enumerate(products[:10], 1):
                print(f"   {i}. {p.producto} - Stock: {p.unidades} - ${p.precio_final}")
            
            if len(products) > 10:
                print(f"   ... y {len(products) - 10} productos más")
            print()
            
            # Preguntar si actualizar la base de datos
            respuesta = input("¿Actualizar base de datos con estos productos? (s/n): ").strip().lower()
            if respuesta == "s":
                with session_scope(factory) as session:
                    repo = ProductRepo(session)
                    # Convertir SheetProduct a ImportedProduct
                    from inventarios.excel_import import ImportedProduct
                    imported = [
                        ImportedProduct(
                            key=p.key,
                            producto=p.producto,
                            descripcion=p.descripcion,
                            unidades=p.unidades,
                            precio_final=p.precio_final
                        )
                        for p in products
                    ]
                    count = repo.upsert_many(imported)
                    print(f"✅ Actualizados {count} productos en la base de datos")
                print()
        
        elif opcion == "3":
            # Ver productos locales
            print("📦 Productos en base de datos local:")
            with session_scope(factory) as session:
                repo = ProductRepo(session)
                products = repo.list(limit=20)
                
                if not products:
                    print("   (vacío)")
                else:
                    for i, p in enumerate(products, 1):
                        print(f"   {i}. {p.producto} - Stock: {p.unidades} - ${p.precio_final}")
                    
                    total = len(repo.list(limit=9999))
                    if total > len(products):
                        print(f"   ... y {total - len(products)} productos más")
                print()
        
        elif opcion == "4":
            print("👋 ¡Hasta luego!")
            return 0
        
        else:
            print("❌ Opción inválida")
            print()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Cancelado por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
