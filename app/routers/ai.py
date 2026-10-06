"""
AI Anomaly Detection Router - Unsupervised Machine Learning.
Isolation Forest + PyTorch Deep Autoencoder for Time-Series Takt & WIP Queue Analysis.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.ai_detector import ai_engine
from app.database import get_db, get_read_replica_db

router = APIRouter(prefix="/api/ai", tags=["AI Anomaly Detection"])


class LiveCycleEvaluateRequest(BaseModel):
    machine_id: str
    cycle_type: str
    sku: str
    actual_takt_sec: float
    target_takt_sec: float
    wip_queue_dwell_min: float
    temp_deviation_c: Optional[float] = 0.0
    pressure_deviation_bar: Optional[float] = 0.0


@router.get("/status")
def get_ai_status():
    """Returns AI model health, parameters, and training metrics."""
    return {
        "status": "OPERATIONAL",
        "models": {
            "isolation_forest": {
                "algorithm": "Isolation Forest (iTree Path Length)",
                "trees_count": 100,
                "contamination": 0.08,
                "purpose": "Định vị các điểm dị biệt đa chiều trong chu kỳ máy (Takt Time Outliers)"
            },
            "deep_autoencoder": {
                "framework": "PyTorch 2.x Deep Neural Network",
                "architecture": "5 -> 16 -> 8 -> 2 (Latent Bottleneck) -> 8 -> 16 -> 5",
                "loss_metric": "Mean Squared Error (MSE Reconstruction Loss)",
                "reconstruction_threshold": ai_engine.ae_threshold,
                "purpose": "Học biểu diễn không gian ẩn & Phát hiện suy giảm hiệu suất ngầm (Subtle Drift)"
            }
        },
        "is_trained": ai_engine.is_trained,
        "last_trained_at": ai_engine.last_trained_at,
        "total_baseline_samples": ai_engine.total_samples_trained,
        "monitored_metrics": [
            "Thời gian chu kỳ máy (Actual vs Target Takt Time)",
            "Thời gian chờ đệm trung gian (WIP Queue Dwell Time)",
            "Hao hụt công suất ẩn (Micro-stoppages & Creeping Cycle Time)",
            "Độ trôi nhiệt độ và áp suất lưu hóa (Thermal & Pressure Drift)"
        ]
    }


@router.post("/train")
def retrain_ai_models():
    """Triggers re-training of both Isolation Forest and Deep Autoencoder on baseline data."""
    ai_engine.train_models()
    return {
        "success": True,
        "message": "Đã tái huấn luyện thành công mô hình Isolation Forest (100 Trees) và Deep Autoencoder (PyTorch)!",
        "last_trained_at": ai_engine.last_trained_at,
        "baseline_samples": ai_engine.total_samples_trained,
        "ae_threshold": ai_engine.ae_threshold
    }


@router.get("/scan-cycles")
def scan_cycles_for_anomalies():
    """
    Scans recent production cycles across all plant machines using AI.
    Returns anomaly scores, severity, and root cause diagnosis.
    """
    cycles = ai_engine.scan_all_cycles()
    anomalies = [c for c in cycles if c["is_anomaly"]]

    # Calculate plant statistics
    avg_score = round(sum(c["ensemble_anomaly_score"] for c in cycles) / max(1, len(cycles)), 3)
    takt_deviations = [c["metrics"]["takt_deviation_sec"] for c in cycles if c["metrics"]["takt_deviation_sec"] > 0]
    avg_takt_creep = round(sum(takt_deviations) / max(1, len(takt_deviations)), 1) if takt_deviations else 0.0

    return {
        "total_scanned_cycles": len(cycles),
        "total_anomalies_detected": len(anomalies),
        "plant_anomaly_index": avg_score,
        "avg_takt_creep_sec": avg_takt_creep,
        "anomalies": anomalies,
        "all_cycles": cycles[:30]  # Return top 30 for visualization
    }


@router.get("/anomalies-log")
def get_logged_anomalies(limit: int = 50):
    """Retrieves detected anomalies from the persistent ai_anomaly_logs table."""
    with get_read_replica_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT * FROM ai_anomaly_logs
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/evaluate-live")
def evaluate_live_cycle(req: LiveCycleEvaluateRequest):
    """
    Real-time inference endpoint for streaming Edge PLC telemetry.
    Instantly returns AI anomaly score, severity, and mitigation advice.
    """
    takt_dev = req.actual_takt_sec - req.target_takt_sec
    features = [
        req.actual_takt_sec,
        takt_dev,
        req.wip_queue_dwell_min,
        req.temp_deviation_c or 0.0,
        req.pressure_deviation_bar or 0.0
    ]

    result = ai_engine.evaluate_vector(features)
    result["machine_id"] = req.machine_id
    result["cycle_type"] = req.cycle_type
    result["sku"] = req.sku

    return result


@router.post("/acknowledge/{anomaly_id}")
def acknowledge_anomaly(anomaly_id: int):
    """Marks an anomaly alert as acknowledged by plant supervisor."""
    with get_db(immediate=True) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE ai_anomaly_logs SET status = 'ACKNOWLEDGED' WHERE id = ?", (anomaly_id,))
        return {"success": True, "anomaly_id": anomaly_id, "status": "ACKNOWLEDGED"}
