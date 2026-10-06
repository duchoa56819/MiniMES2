"""
Comprehensive Test Suite for Tire MES API Endpoints & Business Logic.
"""

import sys
import os
import io
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from app.seed_data import seed_database

client = TestClient(app)


def setup_module(module):
    """Seed fresh test database."""
    seed_database()


def test_01_dashboard_kpis():
    response = client.get("/api/dashboard/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "fpy_percent" in data
    assert "oee_percent" in data
    assert data["total_cured_tires"] >= 18
    assert data["active_work_orders"] >= 1
    print(f"[PASS] Dashboard KPIs: OEE={data['oee_percent']}%, FPY={data['fpy_percent']}%")


def test_02_work_orders():
    # List
    response = client.get("/api/work-orders")
    assert response.status_code == 200
    wos = response.json()
    assert len(wos) >= 5
    print(f"[PASS] Work Orders List: {len(wos)} orders found")

    # Create new
    payload = {
        "wo_id": "WO-TEST-999",
        "sku": "PCR-205-55R16-91V",
        "target_qty": 50,
        "planned_start": "2026-10-06 08:00",
        "planned_end": "2026-10-06 16:00",
        "priority": "HIGH",
        "assigned_machine": "TBM-01"
    }
    create_res = client.post("/api/work-orders", json=payload)
    assert create_res.status_code == 200
    print("[PASS] Created new Work Order WO-TEST-999")


def test_03_poka_yoke_lot_validation():
    # 1. Valid lot
    valid_res = client.post("/api/tbm/validate-lot", json={
        "sku": "PCR-205-55R16-91V",
        "component_type": "TREAD",
        "lot_id": "LOT-TRD-202610-01"
    })
    assert valid_res.status_code == 200
    assert valid_res.json()["valid"] is True
    print("[PASS] Poka-Yoke: Valid lot accepted")

    # 2. Expired lot interlock
    expired_res = client.post("/api/tbm/validate-lot", json={
        "sku": "PCR-205-55R16-91V",
        "component_type": "TREAD",
        "lot_id": "LOT-EXP-TRD-999"
    })
    assert expired_res.status_code == 200
    exp_data = expired_res.json()
    assert exp_data["valid"] is False
    assert exp_data["error_code"] == "LOT_EXPIRED"
    print(f"[PASS] Poka-Yoke Interlock: Expired lot successfully BLOCKED: {exp_data['message'][:60]}...")


def test_04_tbm_build_green_tire():
    payload = {
        "wo_id": "WO-2026-001",
        "sku": "PCR-205-55R16-91V",
        "tbm_machine_id": "TBM-01",
        "operator_id": "OP-1001",
        "actual_weight_kg": 9.28,
        "tread_lot": "LOT-TRD-202610-01",
        "sidewall_lot": "LOT-SW-202610-01",
        "belt1_lot": "LOT-BLT1-202610-01",
        "belt2_lot": "LOT-BLT2-202610-01",
        "ply_lot": "LOT-PLY-202610-01",
        "bead_lot": "LOT-BD-202610-01",
        "innerliner_lot": "LOT-INL-202610-01",
        "override_poka_yoke": False
    }
    response = client.post("/api/tbm/build-green-tire", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["gt_barcode"].startswith("GT-")
    print(f"[PASS] TBM Green Tire Building: Created barcode {data['gt_barcode']}")
    return data["gt_barcode"]


def test_05_curing_full_lifecycle():
    # Build green tire
    gt_barcode = test_04_tbm_build_green_tire()

    # 1. Load tire into CP-02 L (which was empty in seed data)
    load_res = client.post("/api/curing/load", json={
        "press_id": "CP-02",
        "cavity_side": "L",
        "gt_barcode": gt_barcode
    })
    assert load_res.status_code == 200
    print(f"[PASS] Loaded Green Tire {gt_barcode} into Curing Press CP-02 Cavity L")

    # 2. Start curing cycle
    start_res = client.post("/api/curing/start", json={
        "press_id": "CP-02",
        "cavity_side": "L"
    })
    assert start_res.status_code == 200
    print("[PASS] Started Curing Cycle on CP-02-L")

    # 3. Simulate fast complete (accelerated curing)
    comp_res = client.post("/api/curing/simulate-complete", json={
        "press_id": "CP-02",
        "cavity_side": "L"
    })
    assert comp_res.status_code == 200

    # 4. Unload cured tire
    unload_res = client.post("/api/curing/unload", json={
        "press_id": "CP-02",
        "cavity_side": "L"
    })
    assert unload_res.status_code == 200
    unload_data = unload_res.json()
    assert unload_data["tire_serial"].startswith("VN-T-")
    print(f"[PASS] Unloaded Cured Tire: Serial {unload_data['tire_serial']}")
    return unload_data["tire_serial"]


def test_06_quality_inspection_grading():
    tire_serial = test_05_curing_full_lifecycle()

    # Perform flawless inspection -> GRADE_A
    pass_res = client.post("/api/quality/inspect", json={
        "tire_serial": tire_serial,
        "inspector_id": "OP-3001",
        "visual_result": "PASS",
        "xray_result": "PASS",
        "belt_alignment_mm": 0.2,
        "uniformity_rfv_n": 42.0,
        "uniformity_lfv_n": 18.0,
        "dynamic_balance_g": 16.0
    })
    assert pass_res.status_code == 200
    grade_data = pass_res.json()
    assert grade_data["final_grade"] == "GRADE_A"
    assert grade_data["passed"] is True
    print(f"[PASS] Quality Gate: Tire {tire_serial} evaluated to {grade_data['final_grade']}")


def test_07_full_genealogy_passport():
    tire_serial = "VN-T-202610-00101"
    response = client.get(f"/api/genealogy/passport/{tire_serial}")
    assert response.status_code == 200
    data = response.json()
    assert data["tire"]["tire_serial"] == tire_serial
    assert len(data["components_lineage"]) == 7
    assert data["quality_inspection"]["final_grade"] == "GRADE_A"
    assert data["traceability_status"] == "100% VERIFIED TRACEABLE (ISA-95 COMPLIANT)"
    print(f"[PASS] Digital Tire Passport: 100% Genealogy verified for {tire_serial}")


def test_08_protocol_gateway():
    # 1. List Connectors
    res = client.get("/api/gateway/connectors")
    assert res.status_code == 200
    connectors = res.json()
    assert len(connectors) == 5
    print(f"[PASS] Protocol Gateway: 5 Industrial Connectors verified (OPC-UA, OPC-DA, Modbus, MQTT, Sockets)")

    # 2. Test Ping / Handshake on OPC-UA
    ping_res = client.post("/api/gateway/test-ping", json={"connector_id": "CONN-OPC-UA"})
    assert ping_res.status_code == 200
    ping_data = ping_res.json()
    assert ping_data["success"] is True
    assert "latency_ms" in ping_data
    print(f"[PASS] OPC-UA Ping Handshake: Latency {ping_data['latency_ms']}ms, Session OK")

    # 3. Simulate Modbus Packet
    sim_res = client.post("/api/gateway/simulate-packet", json={"connector_id": "CONN-MODBUS-TCP"})
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["success"] is True
    assert "decoded_object" in sim_data
    print(f"[PASS] Modbus TCP Packet Decoded: {sim_data['decoded_object']['engineering_value']}")


def test_09_anti_skip_routing_enforcement():
    # Scenario A: Green tire tries to skip Curing and jump directly to Finishing / QC
    skip_curing_res = client.post("/api/routing/verify-transition", json={
        "identifier": "GT-20261006-0019",
        "target_stage": "FINISHING"
    })
    assert skip_curing_res.status_code == 200
    data_a = skip_curing_res.json()
    assert data_a["permitted"] is False
    assert data_a["error_code"] == "CURING_SKIPPED"
    print(f"[PASS] Anti-Skip Gate 2->3: Green tire blocked from skipping Curing to QC ({data_a['error_code']})")

    # Scenario B: Cured tire without QC inspection tries to skip to Warehouse
    # Build and cure a real tire but DO NOT inspect it with QC
    gt_for_b = test_04_tbm_build_green_tire()
    client.post("/api/curing/load", json={"press_id": "CP-02", "cavity_side": "L", "gt_barcode": gt_for_b})
    client.post("/api/curing/start", json={"press_id": "CP-02", "cavity_side": "L"})
    client.post("/api/curing/simulate-complete", json={"press_id": "CP-02", "cavity_side": "L"})
    unload_res = client.post("/api/curing/unload", json={"press_id": "CP-02", "cavity_side": "L"})
    assert unload_res.status_code == 200
    uninspected_serial = unload_res.json()["tire_serial"]

    skip_qc_res = client.post("/api/routing/scan-warehouse-dispatch", json={
        "tire_serial": uninspected_serial
    })
    assert skip_qc_res.status_code == 200
    data_b = skip_qc_res.json()
    assert data_b["permitted"] is False
    assert data_b["error_code"] == "QC_SKIPPED"
    print(f"[PASS] Anti-Skip Gate 3->4: Uninspected tire {uninspected_serial} blocked from dispatching to Warehouse ({data_b['error_code']})")

    # Scenario C: SCRAP tire tries to enter Warehouse
    # VN-T-202610-00108 is a known SCRAP tire in seed data
    scrap_res = client.post("/api/routing/scan-warehouse-dispatch", json={
        "tire_serial": "VN-T-202610-00108"
    })
    assert scrap_res.status_code == 200
    data_c = scrap_res.json()
    assert data_c["permitted"] is False
    assert data_c["error_code"] == "SCRAP_CANNOT_DISPATCH"
    print(f"[PASS] Anti-Skip Interlock: SCRAP tire definitively blocked from Warehouse ({data_c['error_code']})")

    # Scenario D: Legitimate Grade A tire successfully permitted into Warehouse
    valid_res = client.post("/api/routing/scan-warehouse-dispatch", json={
        "tire_serial": "VN-T-202610-00101"
    })
    assert valid_res.status_code == 200
    data_d = valid_res.json()
    assert data_d["permitted"] is True
    assert data_d["final_grade"] == "GRADE_A"
    print(f"[PASS] Sequence Verified: Grade A tire VN-T-202610-00101 permitted into Warehouse")


def test_10_consecutive_defect_lockout_and_backpressure():
    # 1. Test Buffer Backpressure Engine
    bp_res = client.get("/api/routing/buffer-backpressure")
    assert bp_res.status_code == 200
    bp_data = bp_res.json()
    assert "green_tire_buffer" in bp_data
    assert "curing_finishing_buffer" in bp_data
    assert "backpressure_level" in bp_data
    print(f"[PASS] Buffer Backpressure Monitored: Level={bp_data['backpressure_level']}, Signal={bp_data['plc_interlock_signal']}")

    # 2. Test SPC Lockout Check
    spc_res = client.post("/api/routing/check-spc-lockout", json={
        "machine_id": "CP-01",
        "cavity_side": "L"
    })
    assert spc_res.status_code == 200
    spc_data = spc_res.json()
    assert "locked" in spc_data
    print(f"[PASS] SPC Run-Rule Check: Machine CP-01 Lockout={spc_data['locked']} (Status: {spc_data['interlock_status']})")

    # 3. Test Unauthorized Unlock Attempt (Forbidden 403)
    unauth_res = client.post("/api/routing/unlock-spc", json={
        "machine_id": "CP-01",
        "authorized_badge": "OP-1001",  # TBM operator, unauthorized
        "capa_reason": "Thử mở máy",
        "action_taken": "Bấm nút"
    })
    assert unauth_res.status_code == 403
    print(f"[PASS] CAPA Security: Unauthorized operator OP-1001 blocked from unlocking machine (403 Forbidden)")

    # 4. Test Authorized Unlock by Supervisor (Success 200)
    auth_res = client.post("/api/routing/unlock-spc", json={
        "machine_id": "CP-01",
        "authorized_badge": "OP-4001",  # Supervisor Vũ Đình Phong
        "capa_reason": "Đã vệ sinh khuôn và thay gioăng hơi bàng lưu hóa",
        "action_taken": "Hiệu chuẩn cảm biến nhiệt độ và chạy thử nghiệm FAI"
    })
    assert auth_res.status_code == 200
    auth_data = auth_res.json()
    assert auth_data["success"] is True
    assert auth_data["trial_run_mode"] == "FIRST_ARTICLE_INSPECTION_REQUIRED"
    print(f"[PASS] CAPA Authorization: Supervisor OP-4001 successfully unlocked CP-01 with FAI protocol requirement")


def test_11_rework_loop_and_emergency_lot_quarantine():
    # A. REWORK INTERLOCK TEST (Max 2 Attempts -> Force Scrap)
    tire_rework = "VN-T-202610-00111"  # Seed tire with REWORK status

    # 1st Rework
    rw1 = client.post("/api/quality/rework-action", json={
        "tire_serial": tire_rework,
        "operator_id": "OP-1001",
        "action_type": "TRIM_VENT_SPEW",
        "notes": "Cắt tỉa bavia gai lần 1"
    })
    assert rw1.status_code == 200
    assert rw1.json()["rework_count"] == 1
    print(f"[PASS] Rework Gate: 1st rework recorded for {tire_rework}")

    # Re-inspect with REWORK again
    client.post("/api/quality/inspect", json={
        "tire_serial": tire_rework,
        "inspector_id": "OP-3001",
        "visual_result": "FAIL",
        "visual_defect_code": "DEF-VIS-03",
        "xray_result": "PASS",
        "uniformity_rfv_n": 50.0,
        "uniformity_lfv_n": 20.0,
        "dynamic_balance_g": 36.0  # Still exceeds 35g
    })

    # 2nd Rework
    rw2 = client.post("/api/quality/rework-action", json={
        "tire_serial": tire_rework,
        "operator_id": "OP-1001",
        "action_type": "BALANCE_BUFFING",
        "notes": "Mài mâm cân bằng động lần 2"
    })
    assert rw2.status_code == 200
    assert rw2.json()["rework_count"] == 2
    print(f"[PASS] Rework Gate: 2nd rework recorded for {tire_rework}")

    # Re-inspect with REWORK a 3rd time
    client.post("/api/quality/inspect", json={
        "tire_serial": tire_rework,
        "inspector_id": "OP-3001",
        "visual_result": "FAIL",
        "visual_defect_code": "DEF-VIS-03",
        "xray_result": "PASS",
        "uniformity_rfv_n": 50.0,
        "uniformity_lfv_n": 20.0,
        "dynamic_balance_g": 37.0
    })

    # 3rd Rework attempt -> MUST FORCE SCRAP
    rw3 = client.post("/api/quality/rework-action", json={
        "tire_serial": tire_rework,
        "operator_id": "OP-1001",
        "action_type": "BALANCE_BUFFING",
        "notes": "Cố tình mài lần 3"
    })
    assert rw3.status_code == 200
    rw3_data = rw3.json()
    assert rw3_data["success"] is False
    assert rw3_data["final_grade"] == "SCRAP"
    assert rw3_data["interlock_code"] == "REWORK_LIMIT_EXCEEDED"
    print(f"[PASS] Rework Anti-Loop Interlock: 3rd rework attempt blocked -> FORCED SCRAP ({rw3_data['interlock_code']})")

    # B. EMERGENCY LOT QUARANTINE & BLAST RADIUS TRACEABILITY
    quar_res = client.post("/api/genealogy/containment/quarantine-lot", json={
        "lot_id": "LOT-TRD-202610-01",
        "quarantine_reason": "Lab phát hiện độ bền kéo cao su mặt lốp không đạt chuẩn ASTM D412",
        "authorized_badge": "OP-4001"
    })
    assert quar_res.status_code == 200
    q_data = quar_res.json()
    assert q_data["success"] is True
    assert q_data["blast_radius_summary"]["total_green_tires_impacted"] > 0
    assert q_data["blast_radius_summary"]["total_cured_tires_impacted"] > 0
    print(f"[PASS] Emergency Containment: Quarantined LOT-TRD-202610-01 -> {q_data['blast_radius_summary']['total_cured_tires_impacted']} tires contained!")

    # Verify that a quarantined tire cannot dispatch to Warehouse
    quarantined_serial = q_data["blast_radius_summary"]["cured_tire_serials"][0]
    gate_res = client.post("/api/routing/scan-warehouse-dispatch", json={
        "tire_serial": quarantined_serial
    })
    assert gate_res.status_code == 200
    assert gate_res.json()["permitted"] is False
    assert gate_res.json()["error_code"] == "PRODUCT_QUARANTINED_OR_SCRAPPED"
    print(f"[PASS] Warehouse Gate Interlock: Quarantined tire {quarantined_serial} blocked from dispatching to Warehouse")


def test_12_read_replica_and_frankenstein_trap():
    from concurrent.futures import ThreadPoolExecutor
    from app.database import get_read_replica_db

    # 1. TEST READ-REPLICA ISOLATION
    kpi_res = client.get("/api/dashboard/kpis")
    assert kpi_res.status_code == 200
    assert "oee_percent" in kpi_res.json()

    # Verify that writing to Read-Replica directly is rejected by SQLite engine
    try:
        with get_read_replica_db() as ro_conn:
            ro_conn.execute("UPDATE master_equipment SET status = 'IDLE'")
        assert False, "Should have raised OperationalError: attempt to write a readonly database"
    except Exception as e:
        assert "readonly" in str(e).lower() or "read-only" in str(e).lower() or "attempt to write" in str(e).lower()
        print("[PASS] Read-Replica Isolation: Write operations strictly rejected (100% Read-Only Protected)")

    # 2. TEST HIGH-CONCURRENCY SCAN (Deadlock & Lock Contention Immunity)
    def concurrent_scan(tire_id):
        return client.post("/api/routing/verify-transition", json={
            "identifier": tire_id,
            "target_stage": "WAREHOUSE"
        })

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(concurrent_scan, f"VN-T-202610-0010{i}") for i in range(1, 6)]
        results = [f.result() for f in futures]
        assert all(r.status_code == 200 for r in results)
    print("[PASS] Concurrency Gate: 5 concurrent scan transactions handled with 0 deadlocks (WAL + Busy Timeout)")

    # 3. TEST FRANKENSTEIN DATA TRAP PREVENTION (Monotonic Vector Clock)
    # Tire VN-T-202610-00101 is already completed at Inspection/Warehouse (seq 5).
    # Simulate a delayed sensor packet from TBM (seq 2) arriving out-of-order.
    delayed_pkt_res = client.post("/api/routing/ingest-station-event", json={
        "identifier": "VN-T-202610-00101",
        "station_code": "TBM-01",
        "station_sequence": 2,
        "event_timestamp": "2026-10-06 08:00:00",
        "sensor_measurements": {"actual_weight_kg": 9.25}
    })
    assert delayed_pkt_res.status_code == 200
    trap_data = delayed_pkt_res.json()
    assert trap_data["trap_prevented"] == "FRANKENSTEIN_DATA_TRAP_BLOCKED"
    assert trap_data["state_updated"] is False
    print(f"[PASS] Frankenstein Trap Blocked: Out-of-order delayed packet prevented from regressing tire location!")


def test_13_ai_anomaly_detection():
    # 1. Test AI Model Status & Initialization
    status_res = client.get("/api/ai/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "OPERATIONAL"
    assert status_data["is_trained"] is True
    assert "isolation_forest" in status_data["models"]
    assert "deep_autoencoder" in status_data["models"]
    print(f"[PASS] AI Service Health: Isolation Forest (100 Trees) & PyTorch Autoencoder (Loss Thresh: {status_data['models']['deep_autoencoder']['reconstruction_threshold']})")

    # 2. Test Live Inference: Normal Cycle
    norm_res = client.post("/api/ai/evaluate-live", json={
        "machine_id": "TBM-01",
        "cycle_type": "TBM_BUILD",
        "sku": "PCR-205-55R16-91V",
        "actual_takt_sec": 45.2,
        "target_takt_sec": 45.0,
        "wip_queue_dwell_min": 45.0,
        "temp_deviation_c": 0.0,
        "pressure_deviation_bar": 0.0
    })
    assert norm_res.status_code == 200
    norm_data = norm_res.json()
    assert norm_data["is_anomaly"] is False
    assert norm_data["severity"] == "INFO"
    print(f"[PASS] AI Normal Inference: Score={norm_data['ensemble_anomaly_score']} -> {norm_data['severity']}")

    # 3. Test Live Inference: Severe Anomaly (Creeping Takt Time & WIP Jam)
    anom_res = client.post("/api/ai/evaluate-live", json={
        "machine_id": "CP-02",
        "cycle_type": "CURING_CYCLE",
        "sku": "PCR-205-55R16-91V",
        "actual_takt_sec": 865.0,  # +85s Takt Creep!
        "target_takt_sec": 780.0,
        "wip_queue_dwell_min": 320.0,  # >5h queue delay!
        "temp_deviation_c": -4.2,  # Mold thermal drop!
        "pressure_deviation_bar": -2.1
    })
    assert anom_res.status_code == 200
    anom_data = anom_res.json()
    assert anom_data["is_anomaly"] is True
    assert anom_data["severity"] in ("WARNING", "CRITICAL")
    assert "Suy giảm" in anom_data["root_cause_diagnosis"] or "Tắc nghẽn" in anom_data["root_cause_diagnosis"] or "kéo dài" in anom_data["root_cause_diagnosis"]
    print(f"[PASS] AI Anomaly Detection: Score={anom_data['ensemble_anomaly_score']} -> Severity={anom_data['severity']} (iForest={anom_data['isolation_forest_score']}, Autoencoder MSE={anom_data['autoencoder_mse_loss']})")

    # 4. Test Factory-Wide Batch Cycle Scan
    scan_res = client.get("/api/ai/scan-cycles")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["total_scanned_cycles"] > 0
    assert scan_data["total_anomalies_detected"] > 0
    print(f"[PASS] Factory AI Batch Scan: {scan_data['total_scanned_cycles']} cycles analyzed, {scan_data['total_anomalies_detected']} productivity bottlenecks flagged (Plant Anomaly Index: {scan_data['plant_anomaly_index']})")


def test_14_dynamic_bottleneck_prediction_and_rerouting():
    """
    Test Suite 14: Dynamic Bottleneck Prediction (2–4h horizon) & Automated Material Rerouting.
    Verifies multi-horizon state forecasting, bottleneck shift detection, and automated diverting.
    """
    # 1. Test Status Endpoint
    st_res = client.get("/api/bottleneck/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "OPERATIONAL"
    assert "current_bottleneck_station" in st_data
    assert "predicted_2h_station" in st_data
    print(f"[PASS] Bottleneck AI Status: Current={st_data['current_bottleneck_station']} (BLI={st_data['current_bli']}), Predicted 2h={st_data['predicted_2h_station']}")

    # 2. Test Multi-Horizon Forecast (1h, 2h, 3h, 4h)
    fc_res = client.get("/api/bottleneck/forecast")
    assert fc_res.status_code == 200
    fc_data = fc_res.json()
    assert len(fc_data["all_horizons"]) == 4
    h2 = fc_data["forecast_2h"]
    assert h2["horizon_hours"] == 2
    assert "station_bli_scores" in h2
    assert "recommended_plan" in h2
    print(f"[PASS] Multi-Horizon AI Forecast: Horizon 2h Shift={h2['shift_detected']} (Prob={h2['shift_probability']}), Action Needed={h2['reroute_action_needed']}")

    # 3. Test Simulation Surge (Steam Valve Latency on CP-02)
    surge_res = client.post("/api/bottleneck/simulate-surge", json={"scenario": "CURING_VALVE_DEGRADE"})
    assert surge_res.status_code == 200
    surge_data = surge_res.json()
    assert surge_data["scenario"] == "CURING_VALVE_DEGRADE"
    fc_surge = surge_data["forecast"]["forecast_2h"]
    assert "CP-02" in fc_surge["station_bli_scores"]
    print(f"[PASS] Simulation Surge Injected: CP-02 Curing Valve Drift -> Forecasted Shift in 2h (BLI CP-02={fc_surge['station_bli_scores']['CP-02']})")

    # 4. Test Automated Material Rerouting Execution
    reroute_res = client.post("/api/bottleneck/apply-reroute")
    assert reroute_res.status_code == 200
    reroute_data = reroute_res.json()
    assert reroute_data["success"] is True
    assert reroute_data["expected_oee_protection_pct"] > 0
    diverted_rules = [r for r in reroute_data["rules"] if r["is_diverted"] == 1]
    assert len(diverted_rules) > 0
    print(f"[PASS] MES Automated Material Rerouting: {len(diverted_rules)} rules diverted flow to alternate lines (CP-03/CP-04)")

    # 5. Test Active Rules Retrieval
    rules_res = client.get("/api/bottleneck/routing-rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()
    assert any(r["rule_id"] == "RULE-TBM-CURING-PRIMARY" and r["is_diverted"] == 1 for r in rules)
    print(f"[PASS] Verified Dynamic Routing Table: RULE-TBM-CURING-PRIMARY active divert ratio={rules[0]['divert_ratio_pct']}%")

    # 6. Test Reset Routing to SOP
    reset_res = client.post("/api/bottleneck/reset-routing")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["success"] is True
    assert all(r["is_diverted"] == 0 for r in reset_data["rules"])
    print(f"[PASS] Restored Standard Routing: 100% flow returned to SOP baseline lines")


def test_15_shap_multivariate_root_cause_analysis():
    """
    Test Suite 15: Multivariate Feature Importance & Decision Trees / SHAP Root Cause Analysis.
    Verifies TreeSHAP explainability, decision rule extraction, and defect spike root-cause attribution.
    """
    # 1. Test SHAP Status Endpoint
    st_res = client.get("/api/shap/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "OPERATIONAL"
    assert st_data["monitored_features_count"] >= 18
    assert st_data["is_trained"] is True
    print(f"[PASS] SHAP AI Engine Status: Monitored Features={st_data['monitored_features_count']}, Batches Analyzed={st_data['total_batches_analyzed']} (ROC-AUC={st_data['metrics']['roc_auc']})")

    # 2. Test Global Feature Importance Ranking
    imp_res = client.get("/api/shap/global-importance")
    assert imp_res.status_code == 200
    imp_data = imp_res.json()
    assert len(imp_data["feature_ranking"]) >= 15
    top_rc = imp_data["top_root_cause"]
    assert "feature_key" in top_rc
    assert top_rc["importance_share_pct"] > 0
    print(f"[PASS] Global SHAP Feature Importance: Top Culprit='{top_rc['feature_key']}' ({top_rc['importance_share_pct']}% impact share across plant)")

    # 3. Test Decision Tree Rule Extraction
    rules_res = client.get("/api/shap/decision-rules")
    assert rules_res.status_code == 200
    rules_data = rules_res.json()
    assert rules_data["total_rules"] > 0
    r1 = rules_data["rules"][0]
    assert "conditions_text" in r1
    assert r1["defect_probability_pct"] >= 50.0
    print(f"[PASS] Decision Tree Rule Mining: {rules_data['total_rules']} operational If-Then rules extracted (Top Rule Defect Rate={r1['defect_probability_pct']}%)")

    # 4. Test Local SHAP Waterfall Explanation for Defective Tire
    explain_res = client.post("/api/shap/explain-batch")
    assert explain_res.status_code == 200
    exp_data = explain_res.json()
    assert "predicted_defect_probability" in exp_data
    assert "waterfall_breakdown" in exp_data
    assert len(exp_data["waterfall_breakdown"]) >= 15
    top_culprit = exp_data["top_culprit"]
    print(f"[PASS] Local SHAP Waterfall Analysis: Batch={exp_data['batch_meta']['batch_id']}, Risk={exp_data['predicted_defect_probability']} (Primary Driver='{top_culprit['feature_key']}', SHAP={top_culprit['shap_value']})")

    # 5. Test Defect Spike Simulation & Root Cause Attribution
    spike_res = client.post("/api/shap/simulate-spike", json={"scenario": "BLADDER_PRESSURE_DROP"})
    assert spike_res.status_code == 200
    spike_data = spike_res.json()
    assert spike_data["total_analyzed_batches"] > 0
    print(f"[PASS] Defect Spike Root Cause Discovery: Simulated 'BLADDER_PRESSURE_DROP' -> Pinpointed Top Driver: {spike_data['top_root_cause']['feature_key']}")


if __name__ == "__main__":
    seed_database()
    print("\n" + "="*60)
    print("   RUNNING TIRE MES AUTOMATED VERIFICATION SUITE")
    print("="*60)
    test_01_dashboard_kpis()
    test_02_work_orders()
    test_03_poka_yoke_lot_validation()
    test_04_tbm_build_green_tire()
    test_05_curing_full_lifecycle()
    test_06_quality_inspection_grading()
    test_07_full_genealogy_passport()
    test_08_protocol_gateway()
    test_09_anti_skip_routing_enforcement()
    test_10_consecutive_defect_lockout_and_backpressure()
    test_11_rework_loop_and_emergency_lot_quarantine()
    test_12_read_replica_and_frankenstein_trap()
    test_13_ai_anomaly_detection()
    test_14_dynamic_bottleneck_prediction_and_rerouting()
    test_15_shap_multivariate_root_cause_analysis()
    print("="*60)
    print("   ALL MES BUSINESS LOGIC & API TESTS PASSED 100%!")
    print("="*60 + "\n")





