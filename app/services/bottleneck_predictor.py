"""
Dynamic Bottleneck Prediction & Automated Material Rerouting Service.
Predicts bottleneck shifts across tire manufacturing stations in 2–4 hours horizon
and triggers automated material diverting to alternate production lines.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
from app.database import get_db, get_read_replica_db


class DynamicBottleneckPredictor:
    """
    AI-driven Predictive Dispatching & Dynamic Bottleneck Shifting Engine.
    Combines Discrete Flow Balance, Multi-Horizon State Forecasting, and Heuristic Dynamic Rerouting.
    """

    def __init__(self):
        # Master definition of production stations and baseline capacities
        self.stations = {
            "TBM-01": {
                "name": "Máy Thành Hình Lốp PCR (VMI MAXX)",
                "area": "TBM",
                "rated_rate_uph": 80.0,       # Units per hour (takt 45s)
                "max_wip_capacity": 40,
                "current_wip": 18,
                "current_takt_sec": 46.2,
                "status": "RUNNING",
                "alternate_station": "TBM-02"
            },
            "TBM-02": {
                "name": "Máy Thành Hình Lốp TBR/EV (HF Tire Tech)",
                "area": "TBM",
                "rated_rate_uph": 60.0,       # Units per hour (takt 60s)
                "max_wip_capacity": 35,
                "current_wip": 12,
                "current_takt_sec": 59.5,
                "status": "RUNNING",
                "alternate_station": "TBM-01"
            },
            "BUFFER_GREEN_TIRE": {
                "name": "Giàn Treo Đệm Lốp Sống (Green Tire Monorail Buffer)",
                "area": "WIP_BUFFER",
                "rated_rate_uph": 120.0,
                "max_wip_capacity": 120,
                "current_wip": 68,            # 56.6% fill
                "current_takt_sec": 0.0,
                "status": "RUNNING",
                "alternate_station": None
            },
            "CP-01": {
                "name": "Máy Lưu Hóa Lốp 01 (Cavity L & R)",
                "area": "CURING",
                "rated_rate_uph": 9.2,         # 2 cavities * 780s cure = 9.2 uph
                "max_wip_capacity": 10,
                "current_wip": 4,
                "current_takt_sec": 782.0,
                "status": "RUNNING",
                "alternate_station": "CP-03"
            },
            "CP-02": {
                "name": "Máy Lưu Hóa Lốp 02 (Cavity L & R)",
                "area": "CURING",
                "rated_rate_uph": 9.2,
                "max_wip_capacity": 10,
                "current_wip": 5,
                "current_takt_sec": 795.0,
                "status": "RUNNING",
                "alternate_station": "CP-04"
            },
            "CP-03": {
                "name": "Máy Lưu Hóa Lốp 03 (Cavity L & R - Dự Phòng)",
                "area": "CURING",
                "rated_rate_uph": 9.2,
                "max_wip_capacity": 10,
                "current_wip": 2,
                "current_takt_sec": 780.0,
                "status": "RUNNING",
                "alternate_station": "CP-01"
            },
            "CP-04": {
                "name": "Máy Lưu Hóa Lốp 04 (Cavity L & R - Dự Phòng)",
                "area": "CURING",
                "rated_rate_uph": 9.2,
                "max_wip_capacity": 10,
                "current_wip": 2,
                "current_takt_sec": 780.0,
                "status": "RUNNING",
                "alternate_station": "CP-02"
            },
            "XR-01": {
                "name": "Máy Soi Tia X Kết Cấu Lốp (Yxlon X-Ray Inspection)",
                "area": "FINISHING",
                "rated_rate_uph": 45.0,
                "max_wip_capacity": 25,
                "current_wip": 8,
                "current_takt_sec": 78.0,
                "status": "RUNNING",
                "alternate_station": "UF-01"
            },
            "UF-01": {
                "name": "Máy Kiểm Tra Độ Đồng Đều Lốp (Tire Uniformity Machine)",
                "area": "FINISHING",
                "rated_rate_uph": 50.0,
                "max_wip_capacity": 25,
                "current_wip": 6,
                "current_takt_sec": 72.0,
                "status": "RUNNING",
                "alternate_station": "XR-01"
            }
        }

        # Active simulation parameters (can be adjusted via simulate-surge)
        self.simulation_modifiers: Dict[str, float] = {}
        self.seed_default_routing_rules()

    def seed_default_routing_rules(self):
        """Initializes default routing and diverting rules in database if empty."""
        with get_db(immediate=True) as conn:
            cursor = conn.cursor()
            existing = cursor.execute("SELECT COUNT(*) FROM dynamic_routing_rules").fetchone()[0]
            if existing == 0:
                rules = [
                    (
                        "RULE-TBM-CURING-PRIMARY",
                        "BUFFER_GREEN_TIRE",
                        "CP-01",
                        "CP-03",
                        "GREEN_TIRE",
                        0,
                        0.0,
                        "Luồng chuẩn: Cấp 50% lốp sống sang buồng ép CP-01",
                        None,
                        14.5
                    ),
                    (
                        "RULE-TBM-CURING-SECONDARY",
                        "BUFFER_GREEN_TIRE",
                        "CP-02",
                        "CP-04",
                        "GREEN_TIRE",
                        0,
                        0.0,
                        "Luồng chuẩn: Cấp 50% lốp sống sang buồng ép CP-02",
                        None,
                        16.0
                    ),
                    (
                        "RULE-TBM-PARALLEL-SPLIT",
                        "TBM-01",
                        "TBM-01",
                        "TBM-02",
                        "WORK_ORDER",
                        0,
                        0.0,
                        "Luồng chuẩn: Lệnh PCR xử lý tại TBM-01",
                        None,
                        12.0
                    ),
                    (
                        "RULE-QC-BALANCING",
                        "XR-01",
                        "XR-01",
                        "UF-01",
                        "CURED_TIRE",
                        0,
                        0.0,
                        "Luồng chuẩn: 100% lốp qua trạm X-Ray XR-01",
                        None,
                        18.0
                    )
                ]
                cursor.executemany("""
                    INSERT INTO dynamic_routing_rules (
                        rule_id, source_station, target_station, alternate_station,
                        material_type, is_diverted, divert_ratio_pct, divert_reason,
                        activated_at, throughput_gain_forecast_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rules)

    def forecast_horizons(self, horizons_hours: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Calculates Bottleneck Likelihood Index (BLI) across 1h, 2h, 3h, 4h horizons.
        Detects if and when bottleneck shifts from current station to a downstream station.
        """
        if horizons_hours is None:
            horizons_hours = [1, 2, 3, 4]

        now = datetime.now()
        horizon_results = []

        # Current station metrics (T=0)
        current_bli_map = {}
        for st_id, st_data in self.stations.items():
            mod = self.simulation_modifiers.get(st_id, 1.0)
            fill_pct = st_data["current_wip"] / max(1, st_data["max_wip_capacity"])
            # Effective rate with modifier
            eff_rate = st_data["rated_rate_uph"] * mod
            util = min(1.5, (st_data["current_wip"] * 2.0) / max(1.0, eff_rate))
            # Current BLI score
            bli = 0.5 * fill_pct + 0.5 * min(1.0, util)
            current_bli_map[st_id] = round(float(np.clip(bli, 0.05, 0.98)), 3)

        current_bottleneck = max(current_bli_map, key=current_bli_map.get)

        # Multi-horizon dynamic simulation forward propagation
        simulated_wips = {k: v["current_wip"] for k, v in self.stations.items()}

        for h in horizons_hours:
            dt = 1.0  # hour step
            step_bli_map = {}
            step_wip_levels = {}
            root_causes = {}

            # Dynamic flow propagation model:
            # 1. TBM inflow -> Buffer -> Curing Presses -> QC -> Warehouse
            tbm1_mod = self.simulation_modifiers.get("TBM-01", 1.0)
            tbm2_mod = self.simulation_modifiers.get("TBM-02", 1.0)
            cp1_mod = self.simulation_modifiers.get("CP-01", 1.0)
            cp2_mod = self.simulation_modifiers.get("CP-02", 1.0)
            cp3_mod = self.simulation_modifiers.get("CP-03", 1.0)
            cp4_mod = self.simulation_modifiers.get("CP-04", 1.0)
            xr_mod = self.simulation_modifiers.get("XR-01", 1.0)

            # Check if auto-rerouting is active
            active_rules = self.get_active_divert_rules()
            is_curing_diverted = any(r["is_diverted"] for r in active_rules if "CURING" in r["rule_id"])
            is_tbm_diverted = any(r["is_diverted"] for r in active_rules if "TBM" in r["rule_id"])

            # Production flow rates
            tbm1_output = min(simulated_wips["TBM-01"] + 20.0, 75.0 * tbm1_mod)
            tbm2_output = min(simulated_wips["TBM-02"] + 15.0, 55.0 * tbm2_mod)

            if is_tbm_diverted:
                # 30% load shifted to TBM-02
                tbm1_output *= 0.7
                tbm2_output = min(simulated_wips["TBM-02"] + 30.0, 68.0)

            total_green_tires_inflow = (tbm1_output + tbm2_output) * 0.35 # normalized scale for simulation

            # Curing absorption
            cp1_cap = 9.0 * cp1_mod
            cp2_cap = 8.5 * cp2_mod
            cp3_cap = 9.0 * cp3_mod * (1.8 if is_curing_diverted else 0.4) # Standby press takes load if diverted
            cp4_cap = 9.0 * cp4_mod * (1.8 if is_curing_diverted else 0.4)

            total_curing_burn = cp1_cap + cp2_cap + cp3_cap + cp4_cap

            # Buffer accumulation rate: dWIP = Inflow - Outflow
            buffer_net = (total_green_tires_inflow - total_curing_burn) * dt
            simulated_wips["BUFFER_GREEN_TIRE"] = max(10, min(120, simulated_wips["BUFFER_GREEN_TIRE"] + buffer_net * (h * 0.8)))

            # If CP-02 has steam valve drift, its WIP creeps up
            if cp2_mod < 0.85:
                simulated_wips["CP-02"] = min(10, simulated_wips["CP-02"] + 1.2 * h)
                root_causes["CP-02"] = f"Suy giảm áp suất hơi buồng ép & trễ chu kỳ gia nhiệt (Takt 860s so với 780s định mức)"

            # Buffer congestion
            buf_fill_pct = simulated_wips["BUFFER_GREEN_TIRE"] / 120.0
            if buf_fill_pct > 0.75:
                root_causes["BUFFER_GREEN_TIRE"] = f"Giàn treo lốp sống tích tụ quá mức ({round(buf_fill_pct * 100, 1)}% dung tích), nguy cơ kích hoạt khóa ngược TBM (Backpressure)"

            # Calculate BLI for each station at horizon h
            for st_id, st_data in self.stations.items():
                cur_wip = simulated_wips.get(st_id, st_data["current_wip"])
                step_wip_levels[st_id] = round(float(cur_wip), 1)

                cap = st_data["max_wip_capacity"]
                fill = cur_wip / max(1.0, cap)
                st_mod = self.simulation_modifiers.get(st_id, 1.0)

                # Horizon time-decay & drift factor
                h_factor = 1.0 + (h * 0.12)
                if st_mod < 1.0:
                    bli = fill * 0.45 + (1.0 / max(0.2, st_mod)) * 0.35 + (h_factor * 0.15)
                else:
                    bli = fill * 0.55 + (0.35 / h_factor)

                # Buffer backpressure reflection
                if st_id in ["TBM-01", "TBM-02"] and buf_fill_pct > 0.85:
                    bli += 0.28
                    root_causes[st_id] = "Nguy cơ dừng máy cưỡng bức do giàn treo đệm trung gian tràn 90% (Backpressure Lockout)"

                step_bli_map[st_id] = round(float(np.clip(bli, 0.08, 0.98)), 3)

            # Determine predicted bottleneck at this horizon
            pred_bottleneck = max(step_bli_map, key=step_bli_map.get)
            shift_detected = (pred_bottleneck != current_bottleneck)
            shift_prob = round(float(min(0.96, step_bli_map[pred_bottleneck] * 1.05)), 3)

            # Determine if rerouting is recommended
            reroute_needed = (step_bli_map[pred_bottleneck] >= 0.70)

            # Generate recommended reroute plan
            rec_plan = self._generate_reroute_plan(current_bottleneck, pred_bottleneck, step_bli_map)

            forecast_item = {
                "horizon_hours": h,
                "horizon_time": (now + timedelta(hours=h)).strftime("%H:%M"),
                "current_bottleneck_station": current_bottleneck,
                "current_bottleneck_name": self.stations[current_bottleneck]["name"],
                "predicted_bottleneck_station": pred_bottleneck,
                "predicted_bottleneck_name": self.stations[pred_bottleneck]["name"],
                "shift_detected": shift_detected,
                "shift_probability": shift_prob,
                "station_bli_scores": step_bli_map,
                "predicted_wip_levels": step_wip_levels,
                "buffer_fill_pct": round(buf_fill_pct * 100, 1),
                "root_cause_factors": root_causes.get(pred_bottleneck, "Mất cân đối nhịp chuyền giữa các công đoạn liên tiếp"),
                "reroute_action_needed": reroute_needed,
                "recommended_plan": rec_plan
            }
            horizon_results.append(forecast_item)

        # Pick primary 2h-4h horizon summary
        primary_2h = next((f for f in horizon_results if f["horizon_hours"] == 2), horizon_results[0])
        primary_4h = next((f for f in horizon_results if f["horizon_hours"] == 4), horizon_results[-1])

        # Save latest forecast to DB
        self._persist_forecast(primary_2h)

        return {
            "timestamp": now.isoformat(),
            "current_bottleneck": {
                "station_id": current_bottleneck,
                "station_name": self.stations[current_bottleneck]["name"],
                "current_bli": current_bli_map[current_bottleneck],
                "status": "ACTIVE_PACEMAKER"
            },
            "forecast_2h": primary_2h,
            "forecast_4h": primary_4h,
            "all_horizons": horizon_results,
            "is_rerouting_active": any(r["is_diverted"] for r in self.get_active_divert_rules()),
            "plant_throughput_protected_pct": 14.5 if any(r["is_diverted"] for r in self.get_active_divert_rules()) else 0.0
        }

    def _generate_reroute_plan(self, current_bn: str, pred_bn: str, bli_scores: Dict[str, float]) -> Dict[str, Any]:
        """Synthesizes actionable dynamic rerouting strategy to avert bottleneck."""
        if pred_bn in ["CP-01", "CP-02"]:
            return {
                "action_type": "DIVERSE_CURING_CLUSTER",
                "title": "Bẻ Ghi Lốp Sống Sang Cụm Buồng Ép CP-03 & CP-04",
                "source_buffer": "BUFFER_GREEN_TIRE",
                "bottleneck_node": pred_bn,
                "alternate_nodes": ["CP-03", "CP-04"],
                "divert_ratio_pct": 45.0,
                "expected_throughput_gain_uph": 8.5,
                "estimated_takt_saving_sec": 35.0,
                "description": f"Chuyển hướng 45% lốp sống từ giàn treo sang buồng ép CP-03 và CP-04 (đang có tải dự phòng rảnh BLI={bli_scores.get('CP-03', 0.2)}), giải tỏa nguy cơ kẹt lốp tại {pred_bn}."
            }
        elif pred_bn == "BUFFER_GREEN_TIRE":
            return {
                "action_type": "THROTTLE_UPSTREAM_TBM",
                "title": "Điều Tiết Nhịp Thành Hình & Tái Phân Bổ Mã Lốp",
                "source_buffer": "TBM-01",
                "bottleneck_node": "BUFFER_GREEN_TIRE",
                "alternate_nodes": ["TBM-02"],
                "divert_ratio_pct": 30.0,
                "expected_throughput_gain_uph": 11.0,
                "estimated_takt_saving_sec": 40.0,
                "description": "Điều chuyển 30% lệnh sản xuất PCR sang máy TBM-02 và đồng bộ nhịp nạp phôi từ công đoạn Đùn mặt gai để triệt tiêu hiện tượng dội ngược giàn đệm."
            }
        elif pred_bn == "TBM-01":
            return {
                "action_type": "PARALLEL_RE_DISPATCH",
                "title": "Tái Điều Phối Lệnh Sản Xuất Sang TBM-02",
                "source_buffer": "TBM-01",
                "bottleneck_node": "TBM-01",
                "alternate_nodes": ["TBM-02"],
                "divert_ratio_pct": 40.0,
                "expected_throughput_gain_uph": 12.0,
                "estimated_takt_saving_sec": 28.0,
                "description": f"Điều hướng 40% sản lượng lốp PCR sang máy TBM-02 (BLI={bli_scores.get('TBM-02', 0.25)}), giải phóng thời gian thay cuộn tanh tại TBM-01."
            }
        else:
            return {
                "action_type": "QUALITY_DYNAMIC_DISPATCH",
                "title": "Phân Luồng Kiểm Nghiệm KCS Bán Tự Động",
                "source_buffer": "CP_UNLOAD",
                "bottleneck_node": pred_bn,
                "alternate_nodes": ["UF-01"],
                "divert_ratio_pct": 35.0,
                "expected_throughput_gain_uph": 9.0,
                "estimated_takt_saving_sec": 22.0,
                "description": f"Mở luồng kiểm tra song song tại máy thử độ đồng đều UF-01 để giảm tải cho {pred_bn}."
            }

    def _persist_forecast(self, fc: Dict[str, Any]):
        """Saves dynamic forecast prediction to SQLite database."""
        try:
            with get_db(immediate=True) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bottleneck_forecasts (
                        timestamp, horizon_hours, current_bottleneck_station,
                        predicted_bottleneck_station, shift_detected, shift_probability,
                        station_bli_scores, predicted_wip_levels, root_cause_factors,
                        reroute_action_needed, recommended_plan, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    fc["horizon_hours"],
                    fc["current_bottleneck_station"],
                    fc["predicted_bottleneck_station"],
                    1 if fc["shift_detected"] else 0,
                    fc["shift_probability"],
                    json.dumps(fc["station_bli_scores"]),
                    json.dumps(fc["predicted_wip_levels"]),
                    json.dumps(fc["root_cause_factors"], ensure_ascii=False),
                    1 if fc["reroute_action_needed"] else 0,
                    json.dumps(fc["recommended_plan"], ensure_ascii=False),
                    "PREDICTED"
                ))
        except Exception as e:
            print(f"Error persisting forecast: {e}")

    def apply_reroute(self, rule_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes automated material diverting in MES.
        Updates physical routing rules, marks diverted state, and prevents bottleneck congestion.
        """
        self.seed_default_routing_rules()
        with get_db(immediate=True) as conn:
            cursor = conn.cursor()
            now_str = datetime.now().isoformat()

            if rule_id:
                cursor.execute("""
                    UPDATE dynamic_routing_rules
                    SET is_diverted = 1, divert_ratio_pct = 45.0, activated_at = ?
                    WHERE rule_id = ?
                """, (now_str, rule_id))
            else:
                # Activate both curing and TBM auto-balancing
                cursor.execute("""
                    UPDATE dynamic_routing_rules
                    SET is_diverted = 1, divert_ratio_pct = 45.0, activated_at = ?
                    WHERE rule_id LIKE 'RULE-TBM-CURING%'
                """, (now_str,))

            # Update latest forecast state
            cursor.execute("""
                UPDATE bottleneck_forecasts
                SET status = 'REROUTED'
                WHERE status = 'PREDICTED'
            """)

        return {
            "success": True,
            "message": "ĐÃ KÍCH HOẠT ĐIỀU HƯỚNG TỰ ĐỘNG! Bẻ ghi 45% lưu lượng sang dây chuyền dự phòng CP-03 & CP-04.",
            "activated_at": datetime.now().isoformat(),
            "expected_oee_protection_pct": 14.5,
            "rules": self.get_active_divert_rules()
        }

    def reset_routing(self) -> Dict[str, Any]:
        """Reverts plant material flow to standard SOP routing."""
        with get_db(immediate=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dynamic_routing_rules
                SET is_diverted = 0, divert_ratio_pct = 0.0, activated_at = NULL
            """)
            cursor.execute("""
                UPDATE bottleneck_forecasts
                SET status = 'NORMALIZED'
                WHERE status IN ('PREDICTED', 'REROUTED')
            """)

        self.simulation_modifiers.clear()

        return {
            "success": True,
            "message": "Đã khôi phục lại tuyến phân bổ lưu lượng tiêu chuẩn (Standard SOP Flow)!",
            "rules": self.get_active_divert_rules()
        }

    def get_active_divert_rules(self) -> List[Dict[str, Any]]:
        """Retrieves current dynamic routing rules from database."""
        self.seed_default_routing_rules()
        with get_read_replica_db() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM dynamic_routing_rules").fetchall()
            return [dict(r) for r in rows]

    def simulate_surge(self, scenario: str) -> Dict[str, Any]:
        """
        Injects realistic production surge / degradation scenarios:
        - CURING_VALVE_DEGRADE: CP-02 steam valve drifts, causing curing bottleneck shift in 2h.
        - TBM_INFLOW_SURGE: TBM speeds up, overwhelming Green Tire Buffer Monorail in 3h.
        - NORMAL: Resets modifiers.
        """
        if scenario == "CURING_VALVE_DEGRADE":
            self.simulation_modifiers["CP-02"] = 0.55  # 45% speed drop due to valve latency
            self.simulation_modifiers["CP-01"] = 0.85
            self.simulation_modifiers["TBM-01"] = 1.15 # Upstream still pushing
            msg = "Đã kích hoạt kịch bản: 'Trôi van hơi & sụt áp buồng ép CP-02' (-45% công suất). Dự báo điểm nghẽn sẽ dịch chuyển về CP-02 sau 2 giờ!"
        elif scenario == "TBM_INFLOW_SURGE":
            self.simulation_modifiers["TBM-01"] = 1.45 # Massive surge
            self.simulation_modifiers["TBM-02"] = 1.30
            self.simulation_modifiers["CP-01"] = 0.90
            self.simulation_modifiers["CP-02"] = 0.90
            msg = "Đã kích hoạt kịch bản: 'Sốc tải lốp sống từ TBM-01' (+45% sản lượng). Giàn đệm sẽ đầy 95% và nghẽn trong 2-3 giờ!"
        elif scenario == "XR_HIGH_SCRAP":
            self.simulation_modifiers["XR-01"] = 0.40  # Massive inspection queue
            msg = "Đã kích hoạt kịch bản: 'Lô lốp nghi vấn tăng tỷ lệ soi tia X lại' (XR-01 quá tải). Điểm nghẽn dịch chuyển sang KCS sau 3 giờ!"
        else:
            self.simulation_modifiers.clear()
            msg = "Đã xóa toàn bộ kịch bản sốc tải, đưa xưởng về trạng thái vận hành ổn định."

        forecast = self.forecast_horizons()
        return {
            "scenario": scenario,
            "message": msg,
            "forecast": forecast
        }


# Global singleton instance
bottleneck_engine = DynamicBottleneckPredictor()
