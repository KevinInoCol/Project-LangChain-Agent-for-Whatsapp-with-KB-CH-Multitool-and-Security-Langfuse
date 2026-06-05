"""
Módulo de Configuración del Modelo (model_config).

Config PURA del LLM y de la memoria, desacoplada del código. Para cambiar de
proveedor, modelo o temperatura solo se edita model.yaml — no el agente.
"""

import os

import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.yaml")


def load_model_config(path: str = _CONFIG_PATH) -> dict:
    """Carga model.yaml y devuelve el dict de configuración."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


__all__ = ["load_model_config"]
