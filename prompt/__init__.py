"""
Módulo de Prompt (prompt).

System prompt PURO + su metadata, desacoplado del código. Para ajustar la
persona o las instrucciones del agente solo se edita system_prompt.yaml.
"""

import os

import yaml

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "system_prompt.yaml"
)


def load_system_prompt(path: str = _PROMPT_PATH) -> str:
    """Carga system_prompt.yaml y devuelve solo el texto del prompt."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"].rstrip()


__all__ = ["load_system_prompt"]
