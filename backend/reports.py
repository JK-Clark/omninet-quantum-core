# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/reports.py — PDF report generation with ReportLab

import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

import models


def generate_device_report(device_id: int, db: Session) -> StreamingResponse:
    """Generate a PDF report for a device and return it as a StreamingResponse."""
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found",
        )

    alerts = (
        db.query(models.Alert)
        .filter(models.Alert.device_id == device_id)
        .order_by(models.Alert.created_at.desc())
        .limit(10)
        .all()
    )

    prediction = (
        db.query(models.AIprediction)
        .filter(models.AIprediction.device_id == device_id)
        .order_by(models.AIprediction.created_at.desc())
        .first()
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Title ────────────────────────────────────────────────────────────────
    story.append(Paragraph("OmniNet Quantum-Core — Device Report", styles["Title"]))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 0.5 * cm))

    # ── Device Info ───────────────────────────────────────────────────────────
    story.append(Paragraph("Device Information", styles["Heading2"]))
    device_data = [
        ["Hostname", device.hostname],
        ["IP Address", device.ip_address],
        ["Device Type", device.device_type or "N/A"],
        ["Vendor", device.vendor or "N/A"],
        ["Model", device.model or "N/A"],
        ["Status", device.status.upper()],
        ["Last Seen", device.last_seen.strftime("%Y-%m-%d %H:%M UTC") if device.last_seen else "N/A"],
    ]
    device_table = Table(device_data, colWidths=[6 * cm, 10 * cm])
    device_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(device_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── AI Prediction ─────────────────────────────────────────────────────────
    story.append(Paragraph("AI Health Prediction", styles["Heading2"]))
    if prediction:
        health_bar = _text_progress_bar(prediction.health_score)
        pred_data = [
            ["Health Score", f"{prediction.health_score:.1f}/100  {health_bar}"],
            ["Confidence", f"{(prediction.confidence or 0) * 100:.0f}%"],
            [
                "Predicted Failure",
                prediction.predicted_failure_at.strftime("%Y-%m-%d %H:%M UTC")
                if prediction.predicted_failure_at
                else "No failure predicted",
            ],
            ["Recommendation", prediction.recommendation or "N/A"],
        ]
    else:
        pred_data = [["Health Score", "No prediction available"]]

    pred_table = Table(pred_data, colWidths=[6 * cm, 10 * cm])
    pred_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightblue),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.whitesmoke]),
            ]
        )
    )
    story.append(pred_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Alerts ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Recent Alerts", styles["Heading2"]))
    if alerts:
        alert_data = [["Date", "Severity", "Message", "Resolved"]]
        for alert in alerts:
            alert_data.append(
                [
                    alert.created_at.strftime("%Y-%m-%d %H:%M"),
                    alert.severity.upper(),
                    alert.message[:60] + ("…" if len(alert.message) > 60 else ""),
                    "Yes" if alert.is_resolved else "No",
                ]
            )
        alert_table = Table(alert_data, colWidths=[4 * cm, 3 * cm, 8 * cm, 2.5 * cm])
        alert_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(alert_table)
    else:
        story.append(Paragraph("No alerts recorded for this device.", styles["Normal"]))

    story.append(Spacer(1, cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Paragraph("© 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    filename = f"omninet_report_{device.hostname}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _text_progress_bar(score: float, width: int = 20) -> str:
    """Return a simple ASCII progress bar for the health score."""
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"
