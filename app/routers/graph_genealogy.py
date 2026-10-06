"""
Graph Machine Learning Router - Traceability Graph & Contagion Risk Propagation
ANSI/ISA-95 Level 3 & IATF 16949 Section 8.5.2 / Section 8.7 Compliant.

REST API for querying the Heterogeneous Traceability Graph, running GNN + RWR
contagion risk simulations, and executing automated shopfloor containment.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.graph_genealogy_engine import graph_engine

router = APIRouter(prefix="/api/graph", tags=["Graph Machine Learning & Traceability Contagion"])


class SimulateOutbreakRequest(BaseModel):
    suspect_lot_id: str = Field(..., description="Mã lô linh kiện hoặc mẻ luyện kín nghi vấn lỗi (vd: LOT-TRD-202610-01)")
    defect_description: str = Field("Phát hiện bọt khí & tách lớp mành tanh", description="Mô tả khuyết tật phát hiện trong kiểm định")
    authorized_badge: str = Field("OP-4001", description="Mã thẻ nhân sự phát lệnh (Supervisor / QC Inspector)")


class ExecuteQuarantineRequest(BaseModel):
    run_id: str = Field(..., description="Mã phiên phân tích rủi ro phả hệ (vd: RUN-GRAPH-20261006120000)")
    authorized_badge: str = Field("OP-4001", description="Mã thẻ nhân sự cấp quyền cách ly (Supervisor)")


@router.get("/status")
def get_graph_engine_status():
    """
    Returns the real-time status of the Graph Machine Learning Engine:
    - Heterogeneous Graph Node/Edge count
    - PyTorch GNN Architecture & Device
    - Active Work Orders & Manufacturing Stations
    """
    try:
        G = graph_engine.build_heterogeneous_graph()
        with get_db() as conn:
            cursor = conn.cursor()
            wo_count = cursor.execute("SELECT count(*) FROM work_orders WHERE status IN ('IN_PROGRESS', 'RELEASED')").fetchone()[0]
            lot_count = cursor.execute("SELECT count(*) FROM inventory_components").fetchone()[0]
            runs_count = cursor.execute("SELECT count(*) FROM graph_risk_propagation_runs").fetchone()[0]

        return {
            "status": "ONLINE",
            "model_family": "Graph Machine Learning (Heterogeneous MPNN + Random Walk with Restart)",
            "framework": "PyTorch 2.11 + NetworkX 3.6",
            "graph_metrics": {
                "total_nodes": G.number_of_nodes(),
                "total_edges": G.number_of_edges(),
                "active_work_orders": wo_count,
                "inventory_lots": lot_count,
                "total_historical_runs": runs_count
            },
            "gnn_specs": {
                "layers": 2,
                "feature_dim": 16,
                "hidden_dim": 16,
                "readout": "MLP + Sigmoid",
                "restart_probability": 0.18,
                "attenuation_decay_hours": 5.0
            },
            "compliance_standards": ["IATF 16949 Section 8.5.2", "IATF 16949 Section 8.7", "ANSI/ISA-95 Level 3"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi kiểm tra trạng thái Graph Engine: {str(e)}")


@router.get("/topology")
def get_graph_topology(suspect_lot_id: Optional[str] = Query(None, description="Mã lô lỗi để tính toán rủi ro hiển thị màu sắc")):
    """
    Returns full heterogeneous graph topology with coordinates (x, y)
    optimized for HTML5 Canvas and SVG visual layout.
    """
    try:
        return graph_engine.get_topology_for_visualization(suspect_lot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi truy xuất cấu trúc mạng đồ thị: {str(e)}")


@router.get("/lots")
def list_available_lots():
    """
    Returns all inventory components and Banbury masterbatches
    available in the plant for simulation picker.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT lot_id, component_type, spec_code, compound_code,
                   remaining_qty, status, storage_location, raw_batch_ref,
                   produced_time, expiry_time
            FROM inventory_components
            ORDER BY produced_time DESC
        """).fetchall()

        lots = [dict(r) for r in rows]

        # Also get parent Banbury batches
        batches = cursor.execute("""
            SELECT DISTINCT raw_batch_ref, compound_code
            FROM inventory_components
            WHERE raw_batch_ref IS NOT NULL
        """).fetchall()

        return {
            "component_lots": lots,
            "parent_batches": [dict(b) for b in batches]
        }


@router.post("/simulate-outbreak")
def simulate_defect_outbreak(req: SimulateOutbreakRequest):
    """
    Simulates defect discovery on a specific component lot or Banbury batch.
    Predicts cross-contamination and contagion propagation to ALL active Work Orders.
    """
    try:
        result = graph_engine.simulate_lot_defect_outbreak(
            suspect_lot_id=req.suspect_lot_id,
            defect_description=req.defect_description,
            authorized_badge=req.authorized_badge
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chạy mô phỏng đồ thị lây nhiễm: {str(e)}")


@router.post("/execute-quarantine")
def execute_graph_quarantine(req: ExecuteQuarantineRequest):
    """
    Executes automated 1-Click Shopfloor Containment for Work Orders and Tires
    flagged as CRITICAL in the specified Graph ML analysis run.
    """
    try:
        result = graph_engine.execute_quarantine_containment(
            run_id=req.run_id,
            authorized_badge=req.authorized_badge
        )
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi cách ly đồ thị: {str(e)}")


@router.get("/runs")
def list_propagation_runs(limit: int = 10):
    """
    Returns recent historical graph risk propagation analysis runs.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT run_id, suspect_node_id, suspect_node_type, defect_description,
                   algorithm, critical_wos_count, high_risk_wos_count, total_tires_at_risk,
                   quarantine_applied, created_at, authorized_badge
            FROM graph_risk_propagation_runs
            ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()

        runs = []
        for r in rows:
            d = dict(r)
            # Fetch order scores
            scores = cursor.execute("""
                SELECT wo_id, risk_score, risk_tier, primary_transmission_vector,
                       recommended_action, action_status
                FROM graph_order_risk_scores
                WHERE run_id = ?
                ORDER BY risk_score DESC
            """, (d["run_id"],)).fetchall()
            d["order_scores"] = [dict(s) for s in scores]
            runs.append(d)

        return runs
