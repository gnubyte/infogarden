"""
Dynamic module loader - automatically discovers and registers modules
"""
import os
import importlib
from flask import Blueprint

def load_modules(app, engine):
    """Dynamically load all modules and register their blueprints"""
    modules_dir = os.path.dirname(__file__)
    
    # List of modules to load
    modules = ['orgs', 'users', 'docs', 'contacts', 'passwords', 'locations', 'search']
    
    for module_name in modules:
        module_path = os.path.join(modules_dir, module_name)
        if os.path.isdir(module_path):
            try:
                # Import the module
                module = importlib.import_module(f'app.modules.{module_name}')
                
                # Register routes if they exist
                if hasattr(module, 'bp'):
                    app.register_blueprint(module.bp)
                    print(f"Registered module: {module_name}")
                
                # Register models - ensure tables are created
                # Models are already imported and registered in app/__init__.py
                # This section is kept for potential future use
                pass
            except Exception as e:
                print(f"Error loading module {module_name}: {str(e)}")
                import traceback
                traceback.print_exc()

