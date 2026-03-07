# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
Predictive AI failure detection module.

Uses IsolationForest (scikit-learn) to detect anomalies in device telemetry
and estimate failure probability and time-to-failure.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/tmp/omninet_models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

ALERT_THRESHOLD = 0.75
FEATURES = ["cpu_percent", "ram_percent", "error_rate", "latency_ms"]


class FailurePredictor:
    """IsolationForest-based predictive failure module."""

    def __init__(self) -> None:
        self._models: Dict[int, IsolationForest] = {}

    # ─── Public API ──────────────────────────────────────────────────────

    def train(self, device_id: int, historical_data: List[Dict[str, float]]) -> None:
        """Fit the anomaly detection model on *historical_data*.

        Args:
            device_id: Unique device identifier.
            historical_data: List of metric dicts with keys matching ``FEATURES``.
        """
        if len(historical_data) < 10:
            logger.warning(
                "Device %d has only %d samples; skipping training.",
                device_id,
                len(historical_data),
            )
            return

        X = self._extract_features(historical_data)
        model = IsolationForest(
            n_estimators=200,
            contamination=0.05,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X)
        self._models[device_id] = model
        self._save(device_id, model)
        logger.info("Trained IsolationForest for device %d on %d samples.", device_id, len(X))

    def predict(
        self, device_id: int, current_metrics: Dict[str, float]
    ) -> Tuple[float, Optional[float]]:
        """Return (failure_probability, time_to_failure_hours).

        time_to_failure_hours is None when the model cannot make a reliable
        estimate (e.g. probability below threshold).
        """
        model = self._load(device_id)
        if model is None:
            return 0.0, None

        X = self._extract_features([current_metrics])
        # score_samples returns negative anomaly scores; map to [0,1]
        raw_score = float(model.score_samples(X)[0])
        # Typical range is roughly [-0.5, 0.5]; normalise to [0,1]
        probability = max(0.0, min(1.0, 0.5 - raw_score))

        time_to_failure: Optional[float] = None
        if probability >= ALERT_THRESHOLD:
            # Heuristic: higher anomaly score → shorter time-to-failure
            deviation = probability - ALERT_THRESHOLD
            time_to_failure = max(1.0, round(24.0 * (1.0 - deviation / 0.25), 1))

        return probability, time_to_failure

    def generate_alert(
        self,
        device_id: int,
        prediction: Tuple[float, Optional[float]],
        db: Any,
    ) -> Optional[Any]:
        """Create an Alert DB record if failure probability exceeds threshold.

        Args:
            device_id: Device identifier.
            prediction: (probability, time_to_failure_hours) tuple.
            db: SQLAlchemy session.

        Returns:
            The created Alert ORM object, or None if no alert was needed.
        """
        from models import Alert  # local import to avoid circular deps

        probability, ttf = prediction
        if probability < ALERT_THRESHOLD:
            return None

        severity = "critical" if probability >= 0.90 else "warning"
        ttf_str = f"{ttf:.1f}h" if ttf is not None else "unknown"
        message = (
            f"AI predicts {probability * 100:.1f}% failure probability. "
            f"Estimated time to failure: {ttf_str}."
        )
        alert = Alert(
            device_id=device_id,
            severity=severity,
            message=message,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.info(
            "Alert created for device %d: probability=%.2f, ttf=%s",
            device_id,
            probability,
            ttf_str,
        )
        return alert

    # ─── Persistence helpers ─────────────────────────────────────────────

    def _model_path(self, device_id: int) -> Path:
        return MODEL_DIR / f"device_{device_id}.joblib"

    def _save(self, device_id: int, model: IsolationForest) -> None:
        joblib.dump(model, self._model_path(device_id))

    def _load(self, device_id: int) -> Optional[IsolationForest]:
        if device_id in self._models:
            return self._models[device_id]
        path = self._model_path(device_id)
        if path.exists():
            model = joblib.load(path)
            self._models[device_id] = model
            return model
        return None

    # ─── Feature engineering ─────────────────────────────────────────────

    @staticmethod
    def _extract_features(samples: List[Dict[str, float]]) -> np.ndarray:
        rows: List[List[float]] = []
        for s in samples:
            rows.append([float(s.get(f, 0.0)) for f in FEATURES])
        return np.array(rows, dtype=np.float64)


# Module-level singleton used by FastAPI routes
_predictor: Optional[FailurePredictor] = None


def get_predictor() -> FailurePredictor:
    """FastAPI dependency: returns the module-level predictor singleton."""
    global _predictor
    if _predictor is None:
        _predictor = FailurePredictor()
    return _predictor
