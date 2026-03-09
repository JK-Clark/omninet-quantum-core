# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/ai_predictor.py — Health scoring and failure prediction

import logging
import random
from datetime import datetime, timedelta
from typing import List

import numpy as np
from sqlalchemy.orm import Session

import models
import schemas

logger = logging.getLogger(__name__)


def _score_from_alerts(alerts: List[models.Alert]) -> float:
    """Derive a health score (0–100) from a list of alerts.

    Higher score = healthier.  Critical alerts weigh the most.
    """
    if not alerts:
        return 95.0

    penalty = 0.0
    for alert in alerts:
        if alert.is_resolved:
            continue
        if alert.severity == "critical":
            penalty += 25.0
        elif alert.severity == "warning":
            penalty += 10.0
        else:
            penalty += 2.0

    score = max(0.0, min(100.0, 100.0 - penalty))
    return score


def _simulate_health_series(base_score: float, hours: int = 24) -> List[float]:
    """Generate a realistic synthetic health time-series."""
    rng = np.random.default_rng(seed=int(base_score * 100))
    noise = rng.normal(0, 3, hours)
    series = np.clip(base_score + np.cumsum(noise * 0.1), 0, 100)
    return series.tolist()


def predict_device_health(device_id: int, db: Session) -> models.AIprediction:
    """Compute or refresh the health prediction for a single device."""
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device is None:
        raise ValueError(f"Device {device_id} not found")

    alerts = (
        db.query(models.Alert)
        .filter(models.Alert.device_id == device_id)
        .order_by(models.Alert.created_at.desc())
        .limit(20)
        .all()
    )

    health_score = _score_from_alerts(alerts)

    # Predict failure time based on score
    if health_score < 30:
        predicted_failure_at = datetime.utcnow() + timedelta(hours=random.randint(2, 12))
        confidence = 0.85
        recommendation = "Immediate intervention required — schedule maintenance within 12 hours."
    elif health_score < 60:
        predicted_failure_at = datetime.utcnow() + timedelta(days=random.randint(1, 3))
        confidence = 0.70
        recommendation = "Monitor closely. Plan preventive maintenance within 3 days."
    elif health_score < 80:
        predicted_failure_at = datetime.utcnow() + timedelta(days=random.randint(7, 30))
        confidence = 0.55
        recommendation = "Device is degraded. Schedule inspection during next maintenance window."
    else:
        predicted_failure_at = None
        confidence = 0.90
        recommendation = "Device is healthy. No immediate action required."

    # Upsert prediction
    existing = (
        db.query(models.AIprediction)
        .filter(models.AIprediction.device_id == device_id)
        .order_by(models.AIprediction.created_at.desc())
        .first()
    )

    if existing:
        existing.health_score = health_score
        existing.predicted_failure_at = predicted_failure_at
        existing.confidence = confidence
        existing.recommendation = recommendation
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    prediction = models.AIprediction(
        device_id=device_id,
        health_score=health_score,
        predicted_failure_at=predicted_failure_at,
        confidence=confidence,
        recommendation=recommendation,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def get_health_timeline(device_id: int, db: Session, hours: int = 24) -> schemas.HealthTimeline:
    """Return a synthetic health time-series for the last N hours."""
    latest = (
        db.query(models.AIprediction)
        .filter(models.AIprediction.device_id == device_id)
        .order_by(models.AIprediction.created_at.desc())
        .first()
    )
    base_score = latest.health_score if latest else 85.0
    series = _simulate_health_series(base_score, hours)

    now = datetime.utcnow()
    timeline = [
        schemas.HealthTimelinePoint(
            timestamp=now - timedelta(hours=hours - i),
            health_score=score,
        )
        for i, score in enumerate(series)
    ]

    return schemas.HealthTimeline(device_id=device_id, timeline=timeline)


def generate_predictions_all(db: Session) -> None:
    """Refresh predictions for every device in the database."""
    devices = db.query(models.Device).all()
    for device in devices:
        try:
            predict_device_health(device.id, db)
        except Exception as exc:
            logger.warning("Failed to generate prediction for device %s: %s", device.id, exc)


def ensure_demo_predictions(db: Session) -> None:
    """Generate initial predictions for all devices if none exist."""
    if db.query(models.AIprediction).count() == 0:
        generate_predictions_all(db)
