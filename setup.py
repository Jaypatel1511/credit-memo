"""Compatibility shim.

All project metadata — name, version, dependencies and the package list —
lives in pyproject.toml. Keeping a second copy here was how credit-memo 0.1.0
shipped with three separate version strings; this file deliberately declares
nothing so pyproject.toml is the single source of truth.
"""
from setuptools import setup

setup()
