"""
Prompt template CRUD service.

Built-in templates (is_builtin=1) cannot be modified or deleted.
Custom templates are stored alongside them in the same table.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db.database import get_db

logger = logging.getLogger(__name__)


def get_all_templates() -> list[dict]:
    """Return all templates — built-ins first, then custom alphabetically."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM prompt_templates ORDER BY is_builtin DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_template(template_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM prompt_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None


def create_template(name: str, description: str, system_prompt: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    # Short human-readable ID
    template_id = "custom_" + str(uuid.uuid4())[:8]

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO prompt_templates
                (id, name, description, system_prompt, is_builtin, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (template_id, name, description, system_prompt, now, now),
        )

    logger.info("Created prompt template '%s' (%s)", name, template_id)
    return get_template(template_id)  # type: ignore[return-value]


def update_template(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[dict]:
    tmpl = get_template(template_id)
    if not tmpl:
        return None
    if tmpl["is_builtin"]:
        raise ValueError(f"Built-in template '{template_id}' cannot be modified.")

    now = datetime.now(timezone.utc).isoformat()
    fields: dict[str, object] = {"updated_at": now}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if system_prompt is not None:
        fields["system_prompt"] = system_prompt

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [template_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE prompt_templates SET {set_clause} WHERE id = ?", values
        )

    return get_template(template_id)


def delete_template(template_id: str) -> bool:
    tmpl = get_template(template_id)
    if not tmpl:
        return False
    if tmpl["is_builtin"]:
        raise ValueError(f"Built-in template '{template_id}' cannot be deleted.")

    with get_db() as conn:
        conn.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))

    logger.info("Deleted prompt template '%s'", template_id)
    return True
