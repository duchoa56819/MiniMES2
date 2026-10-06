"""
Multivariate Feature Importance & Decision Trees / SHAP Root Cause API Router.
Identifies which batch process parameters caused defect spikes in tire manufacturing.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.shap_analyzer import shap_engine
from app.database import get_read_replica_db

router = APIRouter(prefix="/api/shap", tags=["SHAP Root Cause Analysis"])


class ExplainBatchRequest(BaseModel):
    sample_id: Optional[str] = None
    custom_vector: Optional[List[float]] = None


class SpikeSimulationRequest(BaseModel):
    scenario: str = "BLADDER_PRESSURE_DROP"


@router.get("/status")
def get_shap_status():
    """
    Returns SHAP and Decision Tree engine status, parameters count, and model metrics.
    """
    return {
        "status": "OPERATIONAL",
        "is_trained": shap_engine.is_trained,
        "last_trained_at": shap_engine.last_trained_at,
        "total_batches_analyzed": shap_engine.total_samples,
        "monitored_features_count": len(shap_engine.FEATURE_KEYS),
        "model_architecture": {
            "primary_model": "Random Forest Classifier (80 Trees, Max Depth 6)",
            "interpretable_model": "Decision Tree Classifier (Class-Balanced, Max Depth 4)",
            "xai_explainer": "TreeSHAP (Shapley Additive exPlanations - Game Theory)"
        },
        "metrics": shap_engine.metrics,
        "active_spike_scenario": shap_engine.active_spike_scenario
    }


@router.get("/global-importance")
def get_global_feature_importance():
    """
    Returns global multivariate feature ranking sorted by mean(|SHAP value|).
    Pinpoints which parameters caused defect spikes across the entire plant.
    """
    return shap_engine.get_global_importance()


@router.get("/decision-rules")
def get_decision_tree_rules():
    """
    Returns human-interpretable If-Then decision rules extracted from the trained decision tree.
    """
    rules = shap_engine.extract_decision_rules()
    return {
        "total_rules": len(rules),
        "rules": rules
    }


@router.post("/explain-batch")
def explain_single_batch(req: Optional[ExplainBatchRequest] = None):
    """
    Local SHAP waterfall force breakdown for an individual tire or batch.
    Decomposes the predicted defect probability into positive and negative attribute forces.
    """
    sample_id = req.sample_id if req else None
    custom_vec = req.custom_vector if req else None
    return shap_engine.explain_sample_batch(sample_id=sample_id, custom_vector=custom_vec)


@router.post("/simulate-spike")
def simulate_defect_spike(req: SpikeSimulationRequest):
    """
    Injects realistic defect spike scenarios to test SHAP root cause discovery.
    Scenarios:
    - 'BLADDER_PRESSURE_DROP': Sụt áp bàng bọng Curing & lỏng miết TBM (Bọt khí hông lốp).
    - 'UNDER_CURE_TEMPERATURE': Tụt nhiệt khuôn trên & áp hơi vòm (Lưu hóa non).
    - 'BANBURY_OVERHEAT': Nhiệt xả Banbury quá cao & độ nhớt Mooney cứng (Bóc tách gai).
    - 'NORMAL': Vận hành ổn định bình thường.
    """
    return shap_engine.simulate_defect_spike(req.scenario)


@router.post("/retrain")
def retrain_shap_models():
    """
    Triggers re-training of Random Forest, Decision Tree, and SHAP TreeExplainer.
    """
    shap_engine.train_models()
    return {
        "success": True,
        "message": "Đã tái huấn luyện thành công Random Forest, Decision Tree và SHAP TreeExplainer!",
        "metrics": shap_engine.metrics,
        "total_samples": shap_engine.total_samples
    }


@router.get("/samples")
def get_sample_batches(limit: int = 25):
    """
    Returns recent production batches for quick inspection in the UI.
    """
    with get_read_replica_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT
                id, batch_id, tire_serial, timestamp, sku,
                is_defective, defect_code, defect_name,
                internal_bladder_press_bar, mooney_viscosity_ml,
                dump_temp_c, mold_temp_upper_c
            FROM batch_process_telemetry
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
