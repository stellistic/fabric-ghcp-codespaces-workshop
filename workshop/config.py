"""Strict, fail-closed configuration; local overrides are complete files, not merges."""

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    pairs = loader.construct_pairs(node)
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate YAML key")
    return dict(pairs)


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class FabricConfig:
    tenant_id: str | None
    workspace_id: str | None
    workspace_name: str | None
    lakehouse_id: str | None
    model_id: str | None
    sandbox: bool


@dataclass(frozen=True)
class SecurityConfig:
    approved_data: str
    allow_live_read: bool
    allow_live_write: bool


@dataclass(frozen=True)
class Config:
    version: int
    profile: str
    seed: int
    fabric: FabricConfig
    security: SecurityConfig


def _keys(data, expected, label):
    if not isinstance(data, dict) or set(data) != set(expected):
        raise ValueError(f"{label}: expected exactly {', '.join(expected)}")


def _uuid(value, label):
    if value is not None:
        if not isinstance(value, str):
            raise ValueError(f"{label}: expected canonical UUID or null")
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label}: invalid UUID") from exc
        if str(parsed) != value or parsed.int == 0:
            raise ValueError(f"{label}: expected nonzero canonical UUID")


def load_config(path: Path) -> Config:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML configuration") from exc
    _keys(data, ("version", "profile", "seed", "fabric", "security"), "config")
    _keys(data["fabric"], FabricConfig.__dataclass_fields__, "fabric")
    _keys(data["security"], SecurityConfig.__dataclass_fields__, "security")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("unsupported config version")
    if data["profile"] != "synthetic-core" or data["seed"] != 20261001 or type(data["seed"]) is not int:
        raise ValueError("this workshop supports only the pinned synthetic-core profile and seed")
    fabric = FabricConfig(**data["fabric"])
    security = SecurityConfig(**data["security"])
    for key in ("tenant_id", "workspace_id", "lakehouse_id", "model_id"):
        _uuid(getattr(fabric, key), f"fabric.{key}")
    if fabric.workspace_name is not None and (
        not isinstance(fabric.workspace_name, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,99}", fabric.workspace_name)
    ):
        raise ValueError("workspace_name: use only letters, numbers, spaces, underscores and hyphens")
    for label, value in (
        ("sandbox", fabric.sandbox),
        ("allow_live_read", security.allow_live_read),
        ("allow_live_write", security.allow_live_write),
    ):
        if type(value) is not bool:
            raise ValueError(f"{label}: expected boolean")
    if security.approved_data not in ("synthetic-only", "approved-metadata"):
        raise ValueError("approved_data must be synthetic-only or approved-metadata")
    if security.allow_live_read and not (fabric.tenant_id and fabric.workspace_id and fabric.workspace_name):
        raise ValueError("live reads require an explicitly selected tenant, workspace UUID and workspace name")
    if security.allow_live_write and not (
        security.allow_live_read and fabric.sandbox and security.approved_data == "synthetic-only"
    ):
        raise ValueError("live writes require approved reads and an explicitly synthetic sandbox")
    return Config(data["version"], data["profile"], data["seed"], fabric, security)
