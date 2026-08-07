"""Synthetic DLA medical supply data generation package."""

from .config import GenerationConfig, SCALE_PROFILES
from .pipeline import generate_all, expected_scale

__all__ = ["GenerationConfig", "SCALE_PROFILES", "generate_all", "expected_scale"]
