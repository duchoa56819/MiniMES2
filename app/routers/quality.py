"""
Quality Inspection Router - Station 3: Finishing & Quality Gate (KCS & Kiểm tra hoàn thiện).
Visual, X-Ray, and Uniformity (RFV/LFV/Balance) inspection with automated grading rules.
"""

import random
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db
from app.models import QualityInspectionRequest

router = APIRouter(prefix="/api/quality", tags=["Quality Inspection"])


class ReworkActionRequest(BaseModel):
    tire_serial: str
    operator_id: str
    action_type: str  # TRIM_VENT_SPEW, BALANCE_BUFFING, BEAD_TOUCHUP
    notes: str = ""


class BatchAutoInspectRequest(BaseModel):
    tire_serials: Optional[List[str]] = None
    scenario: Optional[str] = "AUTO"
    inspector_id: Optional[str] = "OP-3001"



@router.get("/queue")
def get_inspection_queue():
    """Lists cured tires waiting in the inspection queue."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT c.*, p.tire_size, p.pattern_name, p.segment,
                   gt.build_timestamp, gt.tbm_machine_id
            FROM production_cured_tires c
            JOIN master_products p ON c.sku = p.sku
            JOIN production_green_tires gt ON c.gt_barcode = gt.gt_barcode
            WHERE c.status IN ('CURED', 'IN_INSPECTION')
            ORDER BY c.cure_end_time DESC
        """).fetchall()
        return [dict(r) for r in rows]


@router.get("/defects-catalog")
def get_defects_catalog():
    """Returns the standardized tire defect catalog."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM master_defect_codes ORDER BY defect_code ASC").fetchall()
        return [dict(r) for r in rows]


@router.post("/inspect")
def inspect_tire(req: QualityInspectionRequest):
    """
    Submits full quality inspection record and applies automated grading logic:
    - Critical defect / Belt crossing / Under-cure -> SCRAP
    - Major defect / RFV > 75N -> GRADE_B
    - Minor defect (excess flash) -> REWORK
    - Flawless & within OE specs -> GRADE_A
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()

        # Check tire
        tire = cursor.execute("SELECT * FROM production_cured_tires WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if not tire:
            raise HTTPException(status_code=404, detail="Không tìm thấy sê-ri lốp!")

        # Automated Grading Decision Tree
        final_grade = "GRADE_A"
        passed = 1
        disposition_reason = []

        # 1. Visual Defect Check
        if req.visual_result == "FAIL" and req.visual_defect_code:
            v_def = cursor.execute("SELECT * FROM master_defect_codes WHERE defect_code = ?", (req.visual_defect_code,)).fetchone()
            if v_def:
                disposition_reason.append(f"Ngoại quan: {v_def['defect_name_vi']}")
                if v_def["severity"] == "CRITICAL" or v_def["default_disposition"] == "SCRAP":
                    final_grade = "SCRAP"
                    passed = 0
                elif v_def["default_disposition"] == "GRADE_B" and final_grade != "SCRAP":
                    final_grade = "GRADE_B"
                elif v_def["default_disposition"] == "REWORK" and final_grade == "GRADE_A":
                    final_grade = "REWORK"

        # 2. X-Ray Defect Check
        if req.xray_result == "FAIL" and req.xray_defect_code:
            x_def = cursor.execute("SELECT * FROM master_defect_codes WHERE defect_code = ?", (req.xray_defect_code,)).fetchone()
            if x_def:
                disposition_reason.append(f"X-Ray: {x_def['defect_name_vi']}")
                if x_def["severity"] == "CRITICAL" or x_def["default_disposition"] == "SCRAP":
                    final_grade = "SCRAP"
                    passed = 0
                elif x_def["default_disposition"] == "GRADE_B" and final_grade != "SCRAP":
                    final_grade = "GRADE_B"

        # 3. Uniformity & Balance Threshold Check (RFV > 80N or Balance > 35g)
        if final_grade not in ("SCRAP", "GRADE_B"):
            if req.uniformity_rfv_n > 80.0:
                final_grade = "GRADE_B"
                disposition_reason.append(f"Lực RFV ({req.uniformity_rfv_n} N) vượt ngưỡng OE (< 80 N)")
            elif req.dynamic_balance_g > 35.0:
                final_grade = "REWORK"
                disposition_reason.append(f"Cân bằng động ({req.dynamic_balance_g} g) cần cân mài lại")

        if final_grade == "GRADE_A":
            disposition_reason.append("Đạt tiêu chuẩn chất lượng Hạng A (OE First Class). Cho phép dán nhãn xuất khẩu.")

        notes = req.disposition_notes or " | ".join(disposition_reason)

        # Check existing inspection or insert
        existing = cursor.execute("SELECT 1 FROM quality_inspections WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if existing:
            cursor.execute("""
                UPDATE quality_inspections
                SET inspection_timestamp = ?, inspector_id = ?,
                    visual_result = ?, visual_defect_code = ?, defect_location = ?,
                    xray_result = ?, xray_defect_code = ?, belt_alignment_mm = ?,
                    uniformity_rfv_n = ?, uniformity_lfv_n = ?, dynamic_balance_g = ?,
                    final_grade = ?, passed = ?, disposition_notes = ?
                WHERE tire_serial = ?
            """, (
                now_str, req.inspector_id, req.visual_result, req.visual_defect_code, req.defect_location,
                req.xray_result, req.xray_defect_code, req.belt_alignment_mm,
                req.uniformity_rfv_n, req.uniformity_lfv_n, req.dynamic_balance_g,
                final_grade, passed, notes, req.tire_serial
            ))
        else:
            cursor.execute("""
                INSERT INTO quality_inspections (
                    tire_serial, inspection_timestamp, inspector_id,
                    visual_result, visual_defect_code, defect_location,
                    xray_result, xray_defect_code, belt_alignment_mm,
                    uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g,
                    final_grade, passed, disposition_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.tire_serial, now_str, req.inspector_id,
                req.visual_result, req.visual_defect_code, req.defect_location,
                req.xray_result, req.xray_defect_code, req.belt_alignment_mm,
                req.uniformity_rfv_n, req.uniformity_lfv_n, req.dynamic_balance_g,
                final_grade, passed, notes
            ))

        # Update tire status
        tire_new_status = "SCRAPPED" if final_grade == "SCRAP" else "INSPECTED"
        cursor.execute("UPDATE production_cured_tires SET status = ? WHERE tire_serial = ?", (tire_new_status, req.tire_serial))

        # If SCRAP, also update Green Tire and increment WO scrap qty
        if final_grade == "SCRAP":
            cursor.execute("UPDATE production_green_tires SET status = 'SCRAPPED' WHERE gt_barcode = ?", (tire["gt_barcode"],))
            # Find work order
            gt = cursor.execute("SELECT wo_id FROM production_green_tires WHERE gt_barcode = ?", (tire["gt_barcode"],)).fetchone()
            if gt:
                cursor.execute("UPDATE work_orders SET scrap_qty = scrap_qty + 1 WHERE wo_id = ?", (gt["wo_id"],))

        return {
            "success": True,
            "tire_serial": req.tire_serial,
            "final_grade": final_grade,
            "passed": bool(passed),
            "disposition_notes": notes,
            "message": f"Kiểm tra hoàn tất: Cấp phân loại [{final_grade}]!"
        }


@router.get("/history")
def get_inspection_history(limit: int = 50):
    """Returns recent quality inspection records with full defect names."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT q.*, c.sku, p.tire_size, p.pattern_name, o.full_name as inspector_name,
                   dv.defect_name_vi as visual_defect_name,
                   dx.defect_name_vi as xray_defect_name
            FROM quality_inspections q
            JOIN production_cured_tires c ON q.tire_serial = c.tire_serial
            JOIN master_products p ON c.sku = p.sku
            LEFT JOIN master_operators o ON q.inspector_id = o.badge_id
            LEFT JOIN master_defect_codes dv ON q.visual_defect_code = dv.defect_code
            LEFT JOIN master_defect_codes dx ON q.xray_defect_code = dx.defect_code
            ORDER BY q.inspection_timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


@router.post("/rework-action")
def execute_rework_action(req: ReworkActionRequest):
    """
    IATF 16949 REWORK CONTROL & ANTI-INFINITE-LOOP INTERLOCK:
    - Enforces maximum 2 rework attempts per tire.
    - Prevents excessive buffing/grinding that weakens tire structure.
    - Preserves genealogy audit trail in tire_rework_history.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()

        # Check tire and inspection status
        qc = cursor.execute("SELECT * FROM quality_inspections WHERE tire_serial = ?", (req.tire_serial,)).fetchone()
        if not qc:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiếu kiểm định KCS của lốp này!")

        if qc["final_grade"] != "REWORK":
            raise HTTPException(
                status_code=400,
                detail=f"Lốp '{req.tire_serial}' không ở trạng thái REWORK (Trạng thái hiện tại: {qc['final_grade']})!"
            )

        # Check existing rework count
        existing_reworks = cursor.execute(
            "SELECT count(*) FROM tire_rework_history WHERE tire_serial = ?", (req.tire_serial,)
        ).fetchone()[0]

        if existing_reworks >= 2:
            # FORCE SCRAP - IATF 16949 Section 8.7 Violation Prevention
            cursor.execute("""
                UPDATE quality_inspections
                SET final_grade = 'SCRAP', passed = 0,
                    disposition_notes = 'CƯỠNG CHẾ HỦY PHẾ PHẨM: Đã vượt quá giới hạn 2 lần sửa chữa cho phép theo tiêu chuẩn IATF 16949! Nguy cơ mỏng cao su mặt lốp.'
                WHERE tire_serial = ?
            """, (req.tire_serial,))
            cursor.execute("UPDATE production_cured_tires SET status = 'SCRAPPED' WHERE tire_serial = ?", (req.tire_serial,))

            return {
                "success": False,
                "tire_serial": req.tire_serial,
                "rework_count": existing_reworks + 1,
                "final_grade": "SCRAP",
                "interlock_code": "REWORK_LIMIT_EXCEEDED",
                "message": "CƯỠNG CHẾ HỦY PHẾ PHẨM (SCRAP): Chiếc lốp này đã sửa 2 lần nhưng vẫn không đạt. Cấm sửa tiếp để tránh mỏng cao su nguy hiểm!"
            }

        # Valid rework attempt (Count 1 or 2)
        new_count = existing_reworks + 1
        cursor.execute("""
            INSERT INTO tire_rework_history (
                tire_serial, rework_count, rework_timestamp, operator_id,
                action_type, action_description, pre_rework_grade, post_rework_status
            ) VALUES (?, ?, ?, ?, ?, ?, 'REWORK', 'READY_FOR_REINSPECTION')
        """, (req.tire_serial, new_count, now_str, req.operator_id, req.action_type, req.notes))

        # Reset tire status to IN_INSPECTION so it re-enters KCS queue
        cursor.execute("UPDATE production_cured_tires SET status = 'IN_INSPECTION' WHERE tire_serial = ?", (req.tire_serial,))

        return {
            "success": True,
            "tire_serial": req.tire_serial,
            "rework_count": new_count,
            "final_grade": "REWORK_COMPLETED",
            "next_stage": "RE_INSPECTION_GATE",
            "message": f"Sửa hàng lần {new_count}/2 hoàn tất ({req.action_type}). Lốp được chuyển lại hàng đợi KCS để tái kiểm định."
        }


def simulate_realistic_kcs_metrics(tire_serial: str, scenario: Optional[str] = "AUTO", conn=None) -> dict:
    """
    Industry 4.0 Automated Inspection Engine:
    - AI Vision (360-degree optical cameras)
    - X-Ray Automated Defect Recognition (ADR)
    - Tire Uniformity Machine (TUG) RFV & LFV force sensors
    - Dynamic Balancing Machine sensor telemetry
    - Automated Sorter Diverter Gate Recommendation
    """
    if conn is None:
        with get_db() as db_conn:
            return _simulate_realistic_kcs_metrics_core(tire_serial, scenario, db_conn)
    return _simulate_realistic_kcs_metrics_core(tire_serial, scenario, conn)


def _simulate_realistic_kcs_metrics_core(tire_serial: str, scenario: Optional[str], conn) -> dict:
    try:
        cursor = conn.cursor()
        tire = cursor.execute("""
            SELECT c.*, p.tire_size, p.pattern_name, p.segment,
                   gt.build_timestamp, gt.tbm_machine_id, gt.actual_weight_kg,
                   p.standard_weight_kg
            FROM production_cured_tires c
            JOIN master_products p ON c.sku = p.sku
            LEFT JOIN production_green_tires gt ON c.gt_barcode = gt.gt_barcode
            WHERE c.tire_serial = ?
        """, (tire_serial,)).fetchone()

        if not tire:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lốp sê-ri '{tire_serial}'!")

        tire_dict = dict(tire)
        sku = tire_dict.get("sku", "")
        segment = tire_dict.get("segment", "PCR")
        is_tbr = "TBR" in sku or segment == "TBR"
        cure_quality = tire_dict.get("cure_quality_result", "PASS")

        # Determine effective scenario
        effective_scenario = (scenario or "AUTO").upper()
        if effective_scenario == "AUTO":
            if cure_quality == "PRESSURE_DROP":
                effective_scenario = "DEFECT_PRESSURE_DROP"
            elif cure_quality == "TEMP_DEVIATION":
                effective_scenario = "DEFECT_TEMP_DEVIATION"
            else:
                effective_scenario = "NORMAL"

        # -------------------------------------------------------------
        # 1. AI COMPUTER VISION 360° (Mặt gai, hông trái, hông phải, lòng kín khí)
        # -------------------------------------------------------------
        if effective_scenario == "DEFECT_VISUAL":
            visual_result = "FAIL"
            visual_confidence = round(random.uniform(97.8, 99.2), 1)
            visual_defect_code = "DEF-VIS-03"  # Bavia gai quá dài
            defect_location = "Vai lốp ngoài góc 210°, bavia thoát khí dài 7.2mm (vượt ngưỡng 3.0mm)"
            cams = [
                {"cam_id": "CAM-01", "name": "Mặt gai lốp (Tread)", "status": "FAIL", "defect": "DEF-VIS-03: Bavia thoát khí quá dài", "confidence": visual_confidence, "defect_xy": [215, 84]},
                {"cam_id": "CAM-02", "name": "Hông lốp trái (Sidewall-L)", "status": "PASS", "defect": None, "confidence": 99.4, "defect_xy": None},
                {"cam_id": "CAM-03", "name": "Hông lốp phải (Sidewall-R)", "status": "PASS", "defect": None, "confidence": 99.5, "defect_xy": None},
                {"cam_id": "CAM-04", "name": "Lòng lốp kín khí (Innerliner)", "status": "PASS", "defect": None, "confidence": 99.2, "defect_xy": None},
            ]
        elif effective_scenario == "DEFECT_PRESSURE_DROP":
            visual_result = "FAIL"
            visual_confidence = round(random.uniform(98.1, 99.5), 1)
            visual_defect_code = "DEF-VIS-01"  # Bọt khí hông lốp
            defect_location = "Hông lốp trái góc 85°, phát hiện túi khí đường kính 8mm (do tụt áp bàng)"
            cams = [
                {"cam_id": "CAM-01", "name": "Mặt gai lốp (Tread)", "status": "PASS", "defect": None, "confidence": 99.1, "defect_xy": None},
                {"cam_id": "CAM-02", "name": "Hông lốp trái (Sidewall-L)", "status": "FAIL", "defect": "DEF-VIS-01: Bọt khí hông lốp", "confidence": visual_confidence, "defect_xy": [140, 96]},
                {"cam_id": "CAM-03", "name": "Hông lốp phải (Sidewall-R)", "status": "PASS", "defect": None, "confidence": 99.3, "defect_xy": None},
                {"cam_id": "CAM-04", "name": "Lòng lốp kín khí (Innerliner)", "status": "PASS", "defect": None, "confidence": 98.9, "defect_xy": None},
            ]
        elif effective_scenario == "DEFECT_TEMP_DEVIATION":
            visual_result = "FAIL"
            visual_confidence = round(random.uniform(98.0, 99.3), 1)
            visual_defect_code = "DEF-VIS-05"  # Khuyết cao su hoa gai
            defect_location = "Hoa gai trung tâm rãnh dọc số 2, thiếu dòng chảy lưu hóa"
            cams = [
                {"cam_id": "CAM-01", "name": "Mặt gai lốp (Tread)", "status": "FAIL", "defect": "DEF-VIS-05: Khuyết cao su hoa gai", "confidence": visual_confidence, "defect_xy": [180, 110]},
                {"cam_id": "CAM-02", "name": "Hông lốp trái (Sidewall-L)", "status": "PASS", "defect": None, "confidence": 99.2, "defect_xy": None},
                {"cam_id": "CAM-03", "name": "Hông lốp phải (Sidewall-R)", "status": "PASS", "defect": None, "confidence": 99.4, "defect_xy": None},
                {"cam_id": "CAM-04", "name": "Lòng lốp kín khí (Innerliner)", "status": "PASS", "defect": None, "confidence": 99.1, "defect_xy": None},
            ]
        else:
            visual_result = "PASS"
            visual_confidence = round(random.uniform(99.1, 99.8), 1)
            visual_defect_code = None
            defect_location = "Không phát hiện khuyết tật trên bề mặt 360°"
            cams = [
                {"cam_id": "CAM-01", "name": "Mặt gai lốp (Tread)", "status": "PASS", "defect": None, "confidence": 99.6, "defect_xy": None},
                {"cam_id": "CAM-02", "name": "Hông lốp trái (Sidewall-L)", "status": "PASS", "defect": None, "confidence": 99.4, "defect_xy": None},
                {"cam_id": "CAM-03", "name": "Hông lốp phải (Sidewall-R)", "status": "PASS", "defect": None, "confidence": 99.5, "defect_xy": None},
                {"cam_id": "CAM-04", "name": "Lòng lốp kín khí (Innerliner)", "status": "PASS", "defect": None, "confidence": 99.3, "defect_xy": None},
            ]

        # -------------------------------------------------------------
        # 2. X-RAY AUTOMATED DEFECT RECOGNITION (ADR)
        # -------------------------------------------------------------
        if effective_scenario == "DEFECT_XRAY":
            xray_result = "FAIL"
            xray_confidence = round(random.uniform(98.4, 99.6), 1)
            xray_defect_code = "DEF-XRAY-01"  # Đè mép mành thép Belt 1 & 2
            belt_alignment_mm = round(random.uniform(1.10, 1.35), 2)  # Vượt ngưỡng 0.8mm
            cord_spacing_mm = 0.85
            foreign_inclusions = "Phát hiện mép mành Belt 1 đè chéo mành Belt 2 tại góc 160°"
        else:
            xray_result = "PASS"
            xray_confidence = round(random.uniform(99.0, 99.9), 1)
            xray_defect_code = None
            belt_alignment_mm = round(max(0.10, random.gauss(0.24, 0.07)), 2)
            cord_spacing_mm = 0.04
            foreign_inclusions = "Không có dị vật kim loại (Ngưỡng quét < 0.2mm Fe)"

        # -------------------------------------------------------------
        # 3. TIRE UNIFORMITY MACHINE (TUG) - RFV & LFV
        # -------------------------------------------------------------
        if effective_scenario == "DEFECT_UNIFORMITY":
            if is_tbr:
                uniformity_rfv_n = round(random.uniform(185.0, 215.0), 1)
                uniformity_lfv_n = round(random.uniform(45.0, 60.0), 1)
            else:
                uniformity_rfv_n = round(random.uniform(86.0, 98.0), 1)  # Vượt ngưỡng 80N -> Grade B
                uniformity_lfv_n = round(random.uniform(25.0, 32.0), 1)
            conicity_n = 12.4
        else:
            if is_tbr:
                uniformity_rfv_n = round(max(60.0, random.gauss(92.0, 12.0)), 1)
                uniformity_lfv_n = round(max(20.0, random.gauss(34.0, 6.0)), 1)
            else:
                uniformity_rfv_n = round(max(24.0, min(65.0, random.gauss(41.5, 5.8))), 1)
                uniformity_lfv_n = round(max(10.0, min(26.0, random.gauss(17.2, 3.2))), 1)
            conicity_n = round(max(3.0, random.gauss(6.8, 1.8)), 1)

        # -------------------------------------------------------------
        # 4. DYNAMIC BALANCING MACHINE (Cân bằng động)
        # -------------------------------------------------------------
        if effective_scenario == "DEFECT_BALANCE":
            dynamic_balance_g = round(random.uniform(37.0, 48.0), 1)  # Vượt ngưỡng 30/35g -> Rework
            static_balance_g = 19.5
        else:
            if is_tbr:
                dynamic_balance_g = round(max(15.0, min(45.0, random.gauss(28.0, 6.0))), 1)
                static_balance_g = round(max(10.0, random.gauss(16.0, 3.5)), 1)
            else:
                dynamic_balance_g = round(max(6.0, min(25.0, random.gauss(14.2, 3.5))), 1)
                static_balance_g = round(max(4.0, min(15.0, random.gauss(8.1, 2.0))), 1)

        light_spot_angle_deg = random.randint(15, 345)

        # -------------------------------------------------------------
        # 5. PREDICTED FINAL GRADE & AUTOMATED SORTER ROUTING
        # -------------------------------------------------------------
        pred_grade = "GRADE_A"
        reasons = []

        if visual_result == "FAIL":
            if visual_defect_code in ("DEF-VIS-01", "DEF-VIS-04", "DEF-VIS-06"):
                pred_grade = "SCRAP"
                reasons.append("Ngoại quan nghiêm trọng -> Phế phẩm (SCRAP)")
            elif visual_defect_code in ("DEF-VIS-02", "DEF-VIS-05"):
                if pred_grade != "SCRAP":
                    pred_grade = "GRADE_B"
                reasons.append("Ngoại quan bậc trung -> Hạng B")
            elif visual_defect_code == "DEF-VIS-03":
                if pred_grade == "GRADE_A":
                    pred_grade = "REWORK"
                reasons.append("Bavia gai dài -> Cần gọt via (REWORK)")

        if xray_result == "FAIL":
            if xray_defect_code in ("DEF-XRAY-01", "DEF-XRAY-03"):
                pred_grade = "SCRAP"
                reasons.append("Cấu trúc mành thép vi phạm -> Phế phẩm (SCRAP)")
            elif xray_defect_code == "DEF-XRAY-02":
                if pred_grade != "SCRAP":
                    pred_grade = "GRADE_B"
                reasons.append("Dãn cách mành không đều -> Hạng B")

        if pred_grade not in ("SCRAP", "GRADE_B"):
            rfv_limit = 180.0 if is_tbr else 80.0
            if uniformity_rfv_n > rfv_limit:
                pred_grade = "GRADE_B"
                reasons.append(f"Lực RFV ({uniformity_rfv_n}N) vượt chuẩn OE (< {rfv_limit}N)")
            elif dynamic_balance_g > 35.0:
                pred_grade = "REWORK"
                reasons.append(f"Mất cân bằng ({dynamic_balance_g}g) cần mài cân bằng lại")

        if pred_grade == "GRADE_A":
            reasons.append("Đạt 100% tiêu chuẩn chất lượng OE First-Class xuất khẩu")
            sorter_lane = "LANE_1_WAREHOUSE_ASRS"
            sorter_desc = "Băng tải 1: Đẩy sang trạm dán nhãn tự động & Nhập Kho Thông Minh ASRS"
        elif pred_grade == "GRADE_B":
            sorter_lane = "LANE_2_GRADE_B_COMMERCIAL"
            sorter_desc = "Băng tải 2: Đẩy sang khu vực phân loại lốp thứ phẩm / bán lẻ"
        elif pred_grade == "REWORK":
            sorter_lane = "LANE_3_REWORK_BUFFING"
            sorter_desc = "Băng tải 3: Đẩy sang trạm gọt bavia / mài cân bằng động"
        else:  # SCRAP
            sorter_lane = "LANE_4_SCRAP_DEBREAKER"
            sorter_desc = "Băng tải 4: Đẩy sang máy cắt hủy lốp phế phẩm (Tiêu hủy an toàn)"

        return {
            "tire_serial": tire_dict["tire_serial"],
            "sku": sku,
            "tire_size": tire_dict.get("tire_size", ""),
            "pattern_name": tire_dict.get("pattern_name", ""),
            "segment": segment,
            "press_id": tire_dict.get("press_id", ""),
            "cavity_side": tire_dict.get("cavity_side", ""),
            "scenario_applied": effective_scenario,
            "inspector_id": "OP-3001",
            "inspector_name": "Đỗ Thị Mai (KCS Trưởng - AI Phê Duyệt)",
            "ai_vision": {
                "result": visual_result,
                "model": "YOLO-v8 TireVision 360° (v3.2)",
                "confidence_pct": visual_confidence,
                "defect_code": visual_defect_code,
                "defect_location": defect_location,
                "cameras": cams,
                "scan_duration_ms": 385
            },
            "xray_adr": {
                "result": xray_result,
                "engine": "Yxlon ADR Radiographic Neural Inspector (v4.1)",
                "confidence_pct": xray_confidence,
                "belt_alignment_mm": belt_alignment_mm,
                "belt_tolerance_max_mm": 0.8,
                "cord_spacing_mm": cord_spacing_mm,
                "foreign_inclusions": foreign_inclusions,
                "defect_code": xray_defect_code,
                "scan_duration_ms": 720
            },
            "uniformity_tug": {
                "rfv_n": uniformity_rfv_n,
                "rfv_tolerance_max_n": 180.0 if is_tbr else 80.0,
                "lfv_n": uniformity_lfv_n,
                "conicity_n": conicity_n,
                "inflation_press_bar": 2.2,
                "status": "PASS" if (uniformity_rfv_n <= (180.0 if is_tbr else 80.0)) else "FAIL"
            },
            "dynamic_balancing": {
                "dynamic_balance_g": dynamic_balance_g,
                "balance_tolerance_max_g": 35.0,
                "static_balance_g": static_balance_g,
                "light_spot_angle_deg": light_spot_angle_deg,
                "dot_marker": "YELLOW_DOT_APPLIED",
                "status": "PASS" if dynamic_balance_g <= 35.0 else "FAIL"
            },
            "predicted_grade": pred_grade,
            "disposition_notes": " | ".join(reasons),
            "sorter": {
                "lane": sorter_lane,
                "description": sorter_desc
            }
        }
    except Exception:
        raise


@router.get("/auto-scan/{tire_serial}")
def get_auto_scan_simulation(tire_serial: str, scenario: Optional[str] = "AUTO"):
    """
    Industry 4.0 Simulated Automated Inspection:
    - AI Vision (360-degree optical cameras)
    - X-Ray Automated Defect Recognition (ADR)
    - Tire Uniformity Machine (TUG) RFV & LFV force sensors
    - Dynamic Balancing Machine sensor telemetry
    - Automated Sorter Diverter Gate Recommendation
    """
    return simulate_realistic_kcs_metrics(tire_serial, scenario)


@router.post("/auto-inspect-batch")
def auto_inspect_batch(req: Optional[BatchAutoInspectRequest] = None):
    """
    Continuous Automated Quality Gate (Auto-Pilot):
    Executes automated inspection on cured tires waiting in the inspection queue.
    Applies AI Vision, X-Ray ADR, and Uniformity sensors and updates disposition automatically.
    """
    req_scenario = req.scenario if req and req.scenario else "AUTO"
    req_serials = req.tire_serials if req and req.tire_serials else None
    inspector_id = req.inspector_id if req and req.inspector_id else "OP-3001"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()
        if req_serials:
            placeholders = ",".join("?" for _ in req_serials)
            rows = cursor.execute(f"SELECT tire_serial FROM production_cured_tires WHERE tire_serial IN ({placeholders})", req_serials).fetchall()
        else:
            rows = cursor.execute("SELECT tire_serial FROM production_cured_tires WHERE status IN ('CURED', 'IN_INSPECTION') ORDER BY cure_end_time ASC").fetchall()

        if not rows:
            return {
                "success": True,
                "inspected_count": 0,
                "summary": {"GRADE_A": 0, "GRADE_B": 0, "REWORK": 0, "SCRAP": 0},
                "message": "Không có lốp nào trong hàng đợi cần kiểm định."
            }

        results = []
        summary = {"GRADE_A": 0, "GRADE_B": 0, "REWORK": 0, "SCRAP": 0}

        for r in rows:
            serial = r["tire_serial"]
            metrics = simulate_realistic_kcs_metrics(serial, req_scenario, conn=conn)
            final_grade = metrics["predicted_grade"]
            summary[final_grade] = summary.get(final_grade, 0) + 1
            passed = 1 if final_grade != "SCRAP" else 0

            # Upsert into quality_inspections
            cursor.execute("""
                INSERT INTO quality_inspections (
                    tire_serial, inspection_timestamp, inspector_id,
                    visual_result, visual_defect_code, defect_location,
                    xray_result, xray_defect_code, belt_alignment_mm,
                    uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g,
                    final_grade, passed, disposition_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tire_serial) DO UPDATE SET
                    inspection_timestamp = excluded.inspection_timestamp,
                    inspector_id = excluded.inspector_id,
                    visual_result = excluded.visual_result,
                    visual_defect_code = excluded.visual_defect_code,
                    defect_location = excluded.defect_location,
                    xray_result = excluded.xray_result,
                    xray_defect_code = excluded.xray_defect_code,
                    belt_alignment_mm = excluded.belt_alignment_mm,
                    uniformity_rfv_n = excluded.uniformity_rfv_n,
                    uniformity_lfv_n = excluded.uniformity_lfv_n,
                    dynamic_balance_g = excluded.dynamic_balance_g,
                    final_grade = excluded.final_grade,
                    passed = excluded.passed,
                    disposition_notes = excluded.disposition_notes
            """, (
                serial, now_str, inspector_id,
                metrics["ai_vision"]["result"], metrics["ai_vision"]["defect_code"], metrics["ai_vision"]["defect_location"],
                metrics["xray_adr"]["result"], metrics["xray_adr"]["defect_code"], metrics["xray_adr"]["belt_alignment_mm"],
                metrics["uniformity_tug"]["rfv_n"], metrics["uniformity_tug"]["lfv_n"], metrics["dynamic_balancing"]["dynamic_balance_g"],
                final_grade, passed, metrics["disposition_notes"]
            ))

            # Update tire status
            tire_new_status = "SCRAPPED" if final_grade == "SCRAP" else "INSPECTED"
            cursor.execute("UPDATE production_cured_tires SET status = ? WHERE tire_serial = ?", (tire_new_status, serial))

            # If SCRAP, also update green tire & work order
            if final_grade == "SCRAP":
                cured_row = cursor.execute("SELECT gt_barcode FROM production_cured_tires WHERE tire_serial = ?", (serial,)).fetchone()
                if cured_row:
                    cursor.execute("UPDATE production_green_tires SET status = 'SCRAPPED' WHERE gt_barcode = ?", (cured_row["gt_barcode"],))
                    gt_row = cursor.execute("SELECT wo_id FROM production_green_tires WHERE gt_barcode = ?", (cured_row["gt_barcode"],)).fetchone()
                    if gt_row:
                        cursor.execute("UPDATE work_orders SET scrap_qty = scrap_qty + 1 WHERE wo_id = ?", (gt_row["wo_id"],))

            results.append({
                "tire_serial": serial,
                "final_grade": final_grade,
                "sorter_lane": metrics["sorter"]["lane"],
                "disposition_notes": metrics["disposition_notes"]
            })

        return {
            "success": True,
            "inspected_count": len(results),
            "summary": summary,
            "results": results,
            "message": f"Tự động hoàn thiện KCS cho {len(results)} lốp thành công!"
        }

