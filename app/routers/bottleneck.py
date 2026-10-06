"""
Dynamic Bottleneck Prediction & Automated Material Rerouting API Router.
Predicts bottleneck shifts in 2–4 hours and directs material flows to alternate lines.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.bottleneck_predictor import bottleneck_engine
from app.database import get_read_replica_db
import json

router = APIRouter(prefix="/api/bottleneck", tags=["Dynamic Bottleneck Prediction"])


class SurgeSimulationRequest(BaseModel):
    scenario: str = "CURING_VALVE_DEGRADE"


class ApplyRerouteRequest(BaseModel):
    rule_id: Optional[str] = None


@router.get("/forecast")
def get_bottleneck_forecast(horizons: Optional[str] = "1,2,3,4"):
    """
    Returns multi-horizon dynamic bottleneck predictions across plant stations.
    Forecasts whether the active bottleneck will shift in 2–4 hours.
    """
    try:
        horizon_list = [int(h.strip()) for h in horizons.split(",") if h.strip()]
    except Exception:
        horizon_list = [1, 2, 3, 4]

    return bottleneck_engine.forecast_horizons(horizon_list)


@router.get("/status")
def get_bottleneck_status():
    """
    Provides real-time summary of current vs predicted bottlenecks for plant KPI cards.
    """
    fc = bottleneck_engine.forecast_horizons([2, 4])
    curr = fc["current_bottleneck"]
    fc2 = fc["forecast_2h"]
    fc4 = fc["forecast_4h"]

    return {
        "status": "OPERATIONAL",
        "current_bottleneck_station": curr["station_id"],
        "current_bottleneck_name": curr["station_name"],
        "current_bli": curr["current_bli"],
        "predicted_2h_station": fc2["predicted_bottleneck_station"],
        "predicted_2h_name": fc2["predicted_bottleneck_name"],
        "shift_detected_2h": fc2["shift_detected"],
        "shift_probability_2h": fc2["shift_probability"],
        "predicted_4h_station": fc4["predicted_bottleneck_station"],
        "predicted_4h_name": fc4["predicted_bottleneck_name"],
        "shift_detected_4h": fc4["shift_detected"],
        "buffer_fill_pct": fc2["buffer_fill_pct"],
        "is_rerouting_active": fc["is_rerouting_active"],
        "plant_throughput_protected_pct": fc["plant_throughput_protected_pct"]
    }


@router.post("/apply-reroute")
def apply_reroute_plan(req: Optional[ApplyRerouteRequest] = None):
    """
    Triggers automated material diverting in MES.
    Diverts WIP flow to alternate parallel lines (e.g., CP-03/CP-04 or TBM-02).
    """
    rule_id = req.rule_id if req else None
    result = bottleneck_engine.apply_reroute(rule_id)
    return result


@router.post("/reset-routing")
def reset_to_standard_routing():
    """
    Restores material routing back to standard SOP line flow.
    """
    result = bottleneck_engine.reset_routing()
    return result


@router.post("/simulate-surge")
def simulate_production_surge(req: SurgeSimulationRequest):
    """
    Injects realistic production surges or micro-stoppage degradation scenarios.
    Scenarios: 'CURING_VALVE_DEGRADE', 'TBM_INFLOW_SURGE', 'XR_HIGH_SCRAP', 'NORMAL'.
    """
    return bottleneck_engine.simulate_surge(req.scenario)


@router.get("/routing-rules")
def get_plant_routing_rules():
    """
    Lists all dynamic material routing rules, diverting status, and alternate stations.
    """
    return bottleneck_engine.get_active_divert_rules()


@router.get("/history")
def get_bottleneck_forecast_history(limit: int = 20):
    """
    Retrieves historical bottleneck predictions from the database.
    """
    with get_read_replica_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT * FROM bottleneck_forecasts
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            try:
                d["station_bli_scores"] = json.loads(d["station_bli_scores"])
                d["predicted_wip_levels"] = json.loads(d["predicted_wip_levels"])
                d["root_cause_factors"] = json.loads(d["root_cause_factors"]) if d["root_cause_factors"].startswith("{") else d["root_cause_factors"]
                d["recommended_plan"] = json.loads(d["recommended_plan"]) if d.get("recommended_plan") else None
            except Exception:
                pass
            results.append(d)
        return results
