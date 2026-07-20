"""Carga el techo de ofertas del cliente activo (spec §8).

JSON y no markdown a propósito: lo consume un guard de seguridad, y parsear
prosa dentro de un hook que decide si una escritura de precio pasa es frágil.
Misma lección que los backups (.json, no .md) del spec padre §6.

LIMITACIÓN CONOCIDA (spec §9.7): el guard no sabe cuál es el cliente activo.
Con un solo cliente en el repo no hay ambigüedad. Con dos o más devolvemos
None, que el guard traduce en BLOQUEO — falla cerrado, no abierto.
"""
import json
from pathlib import Path

REQUIRED_KEYS = {"maxDiscountPct", "maxDurationDays", "maxTiers",
                 "requireEndsAt", "allowCollectionScope", "enabledStrategies"}


def load_policy(root):
    """dict con la política, o None si no hay exactamente una."""
    hits = sorted(Path(root).glob("clients/*/deal-policy.json"))
    # El template no es un cliente: es el scaffold del próximo.
    hits = [p for p in hits if p.parent.name != "_template"]
    if len(hits) != 1:
        return None
    try:
        data = json.loads(hits[0].read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not REQUIRED_KEYS.issubset(data.keys()):
        return None
    return data
