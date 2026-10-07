"""
Curing Router - Station 2: Curing Presses SCADA & Vulcanization (Lưu hóa lốp).
Handles cavity management, green tire loading, cycle execution, telemetry, and cured tire serial generation.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.models import CuringLoadRequest, CuringStartRequest, CuringUnloadRequest

router = APIRouter(prefix="/api/curing", tags=["Curing Presses"])


@router.get("/cavities")
def list_curing_cavities():
    """Returns real-time status of all curing press cavities with live PLC metrics."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT c.*, e.machine_name, e.model,
                   p.sku, p.tire_size, p.pattern_name,
                   gt.wo_id
            FROM curing_press_cavities c
            JOIN master_equipment e ON c.press_id = e.machine_id
            LEFT JOIN production_green_tires gt ON c.current_gt_barcode = gt.gt_barcode
            LEFT JOIN master_products p ON gt.sku = p.sku
            ORDER BY c.press_id ASC, c.cavity_side ASC
        """).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            # Enforce clean state: if no green tire loaded, cavity must be EMPTY
            if not d.get("current_gt_barcode") and d.get("state") == "CURING":
                d["state"] = "EMPTY"
                d["cure_elapsed_seconds"] = 0
                d["bladder_press_bar"] = 0.0
            target = d["cure_target_seconds"]
            elapsed = d["cure_elapsed_seconds"]
            d["progress_percent"] = min(100.0, round((elapsed / target * 100), 1)) if target > 0 else 0.0
            d["remaining_seconds"] = max(0, target - elapsed)
            result.append(d)
        return result


@router.get("/available-green-tires")
def get_available_green_tires():
    """Returns green tires that have been built but not yet cured or loaded into curing."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT gt.gt_barcode, gt.wo_id, gt.sku, gt.build_timestamp, gt.actual_weight_kg,
                   p.tire_size, p.pattern_name
            FROM production_green_tires gt
            JOIN master_products p ON gt.sku = p.sku
            WHERE gt.status IN ('BUILT', 'BUFFER')
            ORDER BY gt.build_timestamp DESC
            LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]


@router.post("/load")
def load_green_tire(req: CuringLoadRequest):
    """
    Loads a Green Tire into a specific curing cavity.
    Verifies Green Tire existence and status.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Check cavity
        cav = cursor.execute("""
            SELECT * FROM curing_press_cavities
            WHERE press_id = ? AND cavity_side = ?
        """, (req.press_id, req.cavity_side)).fetchone()

        if not cav:
            raise HTTPException(status_code=404, detail="Không tìm thấy hộc khuôn lưu hóa!")

        if cav["state"] not in ("EMPTY", "MOLD_CLEANING"):
            raise HTTPException(status_code=400, detail=f"Hộc khuôn {req.press_id}-{req.cavity_side} hiện không trống (Trạng thái: {cav['state']})!")

        # Check Green Tire
        gt = cursor.execute("SELECT * FROM production_green_tires WHERE gt_barcode = ?", (req.gt_barcode,)).fetchone()
        if not gt:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lốp sống với mã '{req.gt_barcode}'!")

        if gt["status"] not in ("BUILT", "BUFFER"):
            raise HTTPException(status_code=400, detail=f"Lốp sống '{req.gt_barcode}' ở trạng thái {gt['status']}, không thể nạp vào lò!")

        # Fetch recipe for target time
        recipe = cursor.execute("SELECT * FROM master_curing_recipes WHERE sku = ?", (gt["sku"],)).fetchone()
        cure_target = recipe["cure_time_sec"] if recipe else 780
        mold_temp = recipe["mold_temp_target_c"] if recipe else 170.0

        # Update cavity state to LOADED
        cursor.execute("""
            UPDATE curing_press_cavities
            SET current_gt_barcode = ?,
                state = 'LOADED',
                cure_target_seconds = ?,
                cure_elapsed_seconds = 0,
                mold_temp_c = ?
            WHERE press_id = ? AND cavity_side = ?
        """, (req.gt_barcode, cure_target, mold_temp, req.press_id, req.cavity_side))

        # Update Green Tire state
        cursor.execute("""
            UPDATE production_green_tires
            SET status = 'IN_CURING'
            WHERE gt_barcode = ?
        """, (req.gt_barcode,))

        return {
            "success": True,
            "message": f"Nạp lốp sống {req.gt_barcode} vào lò {req.press_id} (Hộc {req.cavity_side}) thành công!",
            "press_id": req.press_id,
            "cavity_side": req.cavity_side,
            "gt_barcode": req.gt_barcode
        }


@router.post("/start")
def start_curing_cycle(req: CuringStartRequest):
    """
    Closes mold and starts the automated vulcanization sequence:
    Steam injection, shaping bladder inflation to 21 bar.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()

        cav = cursor.execute("""
            SELECT * FROM curing_press_cavities
            WHERE press_id = ? AND cavity_side = ?
        """, (req.press_id, req.cavity_side)).fetchone()

        if not cav or cav["state"] != "LOADED":
            raise HTTPException(status_code=400, detail="Hộc khuôn phải ở trạng thái ĐÃ NẠP LỐP (LOADED) mới có thể kích hoạt ép lưu hóa!")

        cursor.execute("""
            UPDATE curing_press_cavities
            SET state = 'CURING',
                cure_start_time = ?,
                cure_elapsed_seconds = 0,
                bladder_press_bar = 21.0,
                steam_press_bar = 15.2
            WHERE press_id = ? AND cavity_side = ?
        """, (now_str, req.press_id, req.cavity_side))

        return {
            "success": True,
            "message": f"Kích hoạt chu kỳ lưu hóa lò {req.press_id}-{req.cavity_side} thành công! Bắt đầu đếm thời gian chín."
        }


@router.post("/simulate-complete")
def simulate_fast_cure(req: CuringStartRequest):
    """
    Engineering/Demo shortcut: Accelerates cure timer to 100% complete
    so testing can proceed without waiting 13 real minutes.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cav = cursor.execute("""
            SELECT * FROM curing_press_cavities
            WHERE press_id = ? AND cavity_side = ?
        """, (req.press_id, req.cavity_side)).fetchone()

        if not cav:
            raise HTTPException(status_code=404, detail="Không tìm thấy hộc khuôn lưu hóa!")

        if not cav["current_gt_barcode"]:
            raise HTTPException(status_code=400, detail="Hộc khuôn hiện chưa nạp lốp sống (EMPTY)! Vui lòng bấm '+ Nạp Lốp Sống' trước khi lưu hóa.")

        if cav["state"] not in ("CURING", "LOADED"):
            raise HTTPException(status_code=400, detail=f"Hộc khuôn đang ở trạng thái {cav['state']}, không thể tua nhanh!")

        target = cav["cure_target_seconds"]
        cursor.execute("""
            UPDATE curing_press_cavities
            SET state = 'COMPLETED',
                cure_elapsed_seconds = ?,
                bladder_press_bar = 0.0
            WHERE press_id = ? AND cavity_side = ?
        """, (target, req.press_id, req.cavity_side))

        return {
            "success": True,
            "message": f"Đã tua nhanh hoàn tất lưu hóa lò {req.press_id}-{req.cavity_side}! Lốp {cav['current_gt_barcode']} đã chín 100%, sẵn sàng dỡ khuôn.",
            "gt_barcode": cav["current_gt_barcode"]
        }


@router.post("/unload")
def unload_cured_tire(req: CuringUnloadRequest):
    """
    Unloads the cured tire:
    - Generates permanent vulcanized Tire Serial ID
    - Increments bladder cycle count
    - Stores cured tire record in production_cured_tires
    - Enqueues tire for Quality Inspection
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_prefix = now.strftime("%Y%m%d")

    with get_db() as conn:
        cursor = conn.cursor()

        cav = cursor.execute("""
            SELECT * FROM curing_press_cavities
            WHERE press_id = ? AND cavity_side = ?
        """, (req.press_id, req.cavity_side)).fetchone()

        if not cav or cav["state"] != "COMPLETED":
            raise HTTPException(status_code=400, detail="Hộc khuôn chưa hoàn tất chu kỳ lưu hóa (COMPLETED) để dỡ lốp!")

        gt_barcode = cav["current_gt_barcode"]
        gt = cursor.execute("SELECT * FROM production_green_tires WHERE gt_barcode = ?", (gt_barcode,)).fetchone()
        if not gt:
            raise HTTPException(status_code=400, detail="Dữ liệu lốp sống bị thất lạc!")

        # Generate Tire Serial
        count_cured = cursor.execute("""
            SELECT count(*) FROM production_cured_tires
            WHERE cure_end_time LIKE ?
        """, (f"{now.strftime('%Y-%m-%d')}%",)).fetchone()[0]

        tire_serial = f"VN-T-{date_prefix}-{(100 + count_cured + 1):05d}"

        # Fetch recipe ID
        recipe = cursor.execute("SELECT recipe_id FROM master_curing_recipes WHERE sku = ?", (gt["sku"],)).fetchone()
        recipe_id = recipe["recipe_id"] if recipe else "RCP-DEFAULT"

        # Insert Cured Tire Record
        cursor.execute("""
            INSERT INTO production_cured_tires (
                tire_serial, gt_barcode, sku, press_id, cavity_side, mold_id,
                curing_recipe_id, cure_start_time, cure_end_time, actual_cure_sec,
                avg_mold_temp_c, avg_bladder_press_bar, cure_quality_result, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PASS', 'IN_INSPECTION')
        """, (
            tire_serial, gt_barcode, gt["sku"], req.press_id, req.cavity_side, cav["mold_id"],
            recipe_id, cav["cure_start_time"] or now_str, now_str, cav["cure_elapsed_seconds"],
            cav["mold_temp_c"], 21.0
        ))

        # Update Green Tire status
        cursor.execute("UPDATE production_green_tires SET status = 'CURED' WHERE gt_barcode = ?", (gt_barcode,))

        # Update Work Order completed count
        cursor.execute("""
            UPDATE work_orders
            SET completed_qty = completed_qty + 1
            WHERE wo_id = ?
        """, (gt["wo_id"],))

        # Increment Bladder cycles & reset cavity
        new_bladder_count = cav["bladder_cycle_count"] + 1
        cursor.execute("""
            UPDATE curing_press_cavities
            SET state = 'EMPTY',
                current_gt_barcode = NULL,
                current_tire_serial = NULL,
                cure_start_time = NULL,
                cure_elapsed_seconds = 0,
                bladder_press_bar = 0.0,
                bladder_cycle_count = ?
            WHERE press_id = ? AND cavity_side = ?
        """, (new_bladder_count, req.press_id, req.cavity_side))

        # Check bladder replacement alert (>350 cycles)
        bladder_warning = None
        if new_bladder_count >= 350:
            bladder_warning = f"CẢNH BÁO: Bàng lưu hóa hộc {req.press_id}-{req.cavity_side} đã đạt {new_bladder_count}/350 chu kỳ! Cần lên kế hoạch thay thế."

        return {
            "success": True,
            "tire_serial": tire_serial,
            "gt_barcode": gt_barcode,
            "message": f"Dỡ lốp chín thành công! Đã khắc số sê-ri lốp: {tire_serial}. Đã chuyển sang trạm KCS.",
            "bladder_count": new_bladder_count,
            "bladder_warning": bladder_warning
        }


@router.get("/telemetry/{press_id}/{cavity_side}")
def get_curing_telemetry(press_id: str, cavity_side: str):
    """Fetches telemetry curves (temperature, pressure) for process auditing."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT * FROM curing_telemetry_history
            WHERE press_id = ? AND cavity_side = ?
            ORDER BY timestamp DESC LIMIT 30
        """, (press_id, cavity_side)).fetchall()

        # Reverse to show chronological order
        return [dict(r) for r in reversed(rows)]
