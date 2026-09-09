"""Read-only status endpoint for phase-eleven external pilot evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify

from services.validation.pilot import status_from_file


def create_validation_blueprint(*, results_file: Path) -> Blueprint:
    blueprint = Blueprint("v3_validation", __name__)

    @blueprint.get("/api/validation/status")
    def validation_status() -> Any:
        return jsonify(status_from_file(results_file))

    return blueprint
