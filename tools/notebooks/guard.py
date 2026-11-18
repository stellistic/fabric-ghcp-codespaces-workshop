"""Fail-closed Fabric notebook authorization, also embedded by the builder."""

import re
from uuid import UUID


def require_uuid(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an explicit canonical UUID")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be an explicit canonical UUID") from error
    if str(parsed) != value or parsed.int == 0:
        raise ValueError(f"{label} must be a nonzero lowercase canonical UUID")
    return value


def assert_sandbox_context(runtime_context, *, workspace_id: str, lakehouse_id: str,
                           sandbox: bool, approval: str, batch_id: str) -> None:
    """Names, implicit current-workspace defaults, and truthy strings are not consent."""
    require_uuid(workspace_id, "workspace_id")
    require_uuid(lakehouse_id, "lakehouse_id")
    if sandbox is not True or approval != workspace_id:
        raise ValueError("Require sandbox=True and approval equal to the exact workspace UUID")
    if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", batch_id):
        raise ValueError("batch_id must be a nonempty, path-safe run identifier (at most 80 characters)")
    try:
        current_workspace = runtime_context["currentWorkspaceId"]
        default_lakehouse = runtime_context["defaultLakehouseId"]
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Fabric runtime workspace and default lakehouse UUIDs are required") from error
    if current_workspace != workspace_id or default_lakehouse != lakehouse_id:
        raise ValueError("Fabric runtime UUIDs do not match the explicitly approved sandbox")
    attached_workspace = runtime_context.get("defaultLakehouseWorkspaceId")
    if attached_workspace and attached_workspace != workspace_id:
        raise ValueError("Cross-workspace default lakehouses are not supported by this workshop")


def assert_model_target(*, workspace_id: str, model_workspace_id: str,
                        expected_model_id: str) -> None:
    require_uuid(model_workspace_id, "model_workspace_id")
    require_uuid(expected_model_id, "expected_model_id")
    if model_workspace_id != workspace_id:
        raise ValueError("The model must be in the explicitly approved sandbox workspace")
