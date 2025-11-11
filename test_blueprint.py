#!/usr/bin/env python
"""
Script para verificar que el blueprint está registrado
"""

import sys
import os

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from flask import Flask

    print("✓ Flask importado correctamente")

    from api.dispatch_assignment_routes import dispatch_assignment_bp

    print("✓ Blueprint importado correctamente")
    print(f"  - Blueprint name: {dispatch_assignment_bp.name}")
    print(f"  - URL prefix: {dispatch_assignment_bp.url_prefix}")

    # Crear app de test
    app = Flask(__name__)
    app.register_blueprint(dispatch_assignment_bp)

    print("✓ Blueprint registrado en Flask")

    # Listar todas las rutas
    print("\nRutas registradas:")
    for rule in app.url_map.iter_rules():
        if 'dispatch' in rule.rule:
            print(f"  - {rule.rule} [{', '.join(rule.methods)}]")

    print("\n✅ TODO OK - Blueprint está correctamente registrado")

except ImportError as e:
    print(f"❌ Error de importación: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
