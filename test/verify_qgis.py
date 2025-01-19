#!/usr/bin/env python3
"""
Verify QGIS environment setup
"""
import os
import sys

def check_environment():
    print("=== QGIS Environment Check ===")
    print(f"QGIS_PREFIX_PATH: {os.getenv('QGIS_PREFIX_PATH', 'Not set')}")
    print(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'Not set')}")
    
    print("\n=== QGIS Import Test ===")
    try:
        from qgis.core import QgsApplication
        # Initialize QGIS Application
        qgs = QgsApplication([], False)
        qgs.initQgis()
        print("QGIS Python bindings available")
        from qgis.core import QgsProviderRegistry
        r = QgsProviderRegistry.instance()
        providers = r.providerList()
        print(f"Available QGIS providers: {', '.join(providers)}")
        qgs.exitQgis()
        return 'gdal' in providers and 'ogr' in providers and 'postgres' in providers
    except Exception as e:
        print(f"Error with QGIS: {e}")
        return False

if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)
