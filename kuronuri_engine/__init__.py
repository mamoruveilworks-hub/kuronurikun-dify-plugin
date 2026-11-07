"""Japanese PII detection engine of Kuronuri-kun, bundled so the plugin can run without sending text anywhere.

Copied from the Kuronuri-kun API by tools/sync_plugin_engine.py. Standard library only.
"""

from .engine import detect
from .entities import DEFAULT_TYPES, OPTIONAL_TYPES, EntityType
from .replace import MaskStyle, mask, unmask

__all__ = ["detect", "mask", "unmask", "MaskStyle", "EntityType", "DEFAULT_TYPES", "OPTIONAL_TYPES"]
