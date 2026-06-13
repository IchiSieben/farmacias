"""core — motor genérico de FarmaComparador Perú.

Contiene el modelo de datos normalizado (`modelo.Producto`), la interfaz común
de adaptadores (`adapter_base.AdapterBase`) y los adaptadores por cadena
(`core.adapters`). El motor es agnóstico al rubro: clonar a otro negocio es
cambiar config, no código (ver SPEC §10).
"""
