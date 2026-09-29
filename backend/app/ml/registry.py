# app/ml/registry.py — artifact loading with strict validation (Slice 4).
# Missing dir, checksum mismatch, schema mismatch, or unloadable file all
# fall back to None. The API must always start (kill-switch, tested).
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.ml.features import N_FEATURES, SCHEMA_VERSION

logger = logging.getLogger("vh-s02")


@dataclass(frozen=True)
class ModelHandle:
    backend: str
    version: str
    model: object


def artifacts_dir() -> Path:
    override = os.environ.get("ML_ARTIFACTS_DIR")
    if override:
        return Path(override)
    return Path(__file__).parent / "artifacts"


def _read_metadata(directory: Path) -> dict | None:
    try:
        return json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("ML metadata unreadable in %s: %s", directory, exc)
        return None


def load(backend: str, directory: Path | None = None) -> ModelHandle | None:
    """Load and validate artifacts. Returns None on any failure (never raises)."""
    if not backend or backend == "none":
        return None
    directory = directory or artifacts_dir()
    metadata = _read_metadata(directory)
    if metadata is None:
        return None
    if metadata.get("feature_schema") != SCHEMA_VERSION:
        logger.error("ML schema mismatch: artifact=%r expected=%r",
                     metadata.get("feature_schema"), SCHEMA_VERSION)
        return None
    if metadata.get("n_features") != N_FEATURES:
        logger.error("ML feature-count mismatch: artifact=%r expected=%r",
                     metadata.get("n_features"), N_FEATURES)
        return None
    model_path = directory / "model.joblib"
    try:
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    except OSError as exc:
        logger.error("ML artifact unreadable: %s", exc)
        return None
    if digest != metadata.get("sha256"):
        logger.error("ML checksum mismatch in %s", directory)
        return None
    try:
        import joblib
        model = joblib.load(model_path)
    except Exception as exc:  # corrupt or hostile pickle must not take down boot
        logger.error("ML artifact unloadable: %s", exc)
        return None
    version = str(metadata.get("version", backend))
    logger.info("ML backend ready: %s (sha256=%s...)", version, digest[:12])
    return ModelHandle(backend=backend, version=version, model=model)


_cache: dict[str, ModelHandle | None] = {}


def get(backend: str) -> ModelHandle | None:
    """Cached handle for a backend name. Missing/invalid -> None (never raises)."""
    if backend not in _cache:
        _cache[backend] = load(backend)
    return _cache[backend]


def reset() -> None:
    """Clear the cache (tests only)."""
    _cache.clear()


def preload(settings_backend: str) -> ModelHandle | None:
    """Startup entry: best-effort load, silent fallback to None."""
    try:
        return get(settings_backend)
    except Exception as exc:  # never block API startup
        logger.error("ML preload failed (continuing without model): %s", exc)
        return None
