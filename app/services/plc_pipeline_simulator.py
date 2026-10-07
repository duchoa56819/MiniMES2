"""
Automated Multi-PLC Industrial Pipeline Simulator for Tire MES.
Simulates realistic real-time telemetry inputs from factory PLCs:
- PLC-MIX: Banbury Mixer (Siemens S7-300 / OPC-DA)
- PLC-EXT & CAL: Triplex Extruder & 4-Roll Calender (Siemens S7-1500 / OPC-UA)
- PLC-TBM: Tire Building Machine (VMI MAXX / TCP Socket & OPC-UA)
- PLC-CUR: Curing Presses Herbert/Krupp (Modbus TCP & OPC-UA)
- PLC-FIN: Quality X-Ray & Dynamic Balancer (Yxlon / Hofmann / OPC-UA)

Includes:
- Industrial Protocol Packet Framing (OPC-UA, Modbus-TCP, MQTT Sparkplug B, TCP Socket)
- Realistic Physical Noise & Thermodynamics (Gaussian & Random Walk)
- Multi-station State Machines & Handshakes
- Scenario Injection: NORMAL, TAKT_CREEP, BOTTLENECK_SURGE, DEFECT_SPIKE
- Ingestion into MES Database & Memory Ring-Buffer for Real-Time Streaming
"""

import os
import time
import math
import json
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from app.database import get_db, get_read_replica_db


# =============================================================================
# 1. INDUSTRIAL PROTOCOL FRAMER
# =============================================================================

class IndustrialProtocolFramer:
    """Generates authentic industrial protocol packets for factory telemetry."""

    @staticmethod
    def frame_opc_ua(machine_id: str, tag_name: str, value: Any, data_type: str = "Float", quality: str = "Good") -> Dict[str, Any]:
        """Encapsulates an OPC-UA MonitoredItem Notification packet (IEC 62541)."""
        now = datetime.now()
        return {
            "protocol": "OPC_UA",
            "endpoint": f"opc.tcp://192.168.1.{random.randint(10, 99)}:4840",
            "node_id": f"ns=2;s={machine_id}.ProcessData.{tag_name}",
            "value": round(value, 3) if isinstance(value, float) else value,
            "data_type": data_type,
            "status_code": "0x00000000 (Good)" if quality == "Good" else "0x80000000 (Bad)",
            "source_timestamp": now.isoformat() + "Z",
            "server_timestamp": (now + timedelta(milliseconds=random.randint(2, 8))).isoformat() + "Z",
            "latency_ms": round(random.uniform(5.2, 14.8), 2)
        }

    @staticmethod
    def frame_modbus_tcp(unit_id: int, register_addr: int, raw_value: float, description: str) -> Dict[str, Any]:
        """Encapsulates a Modbus-TCP Application Data Unit (ADU) packet."""
        # Convert float to simulated 16-bit registers (scaled x10)
        reg_val = int(raw_value * 10) & 0xFFFF
        hex_data = f"{reg_val:04X}"
        return {
            "protocol": "MODBUS_TCP",
            "port": 502,
            "transaction_id": random.randint(1000, 9999),
            "protocol_id": 0,
            "length": 6,
            "unit_id": unit_id,
            "function_code": "03 (Read Holding Registers)",
            "register_address": f"40{register_addr:04d}",
            "raw_hex": f"0x{hex_data}",
            "scaled_engineering_value": round(raw_value, 2),
            "description": description,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }

    @staticmethod
    def frame_mqtt_sparkplug(edge_node: str, metric_name: str, value: Any, unit: str) -> Dict[str, Any]:
        """Encapsulates an MQTT Sparkplug B DDATA payload."""
        return {
            "protocol": "MQTT_SPARKPLUG_B",
            "topic": f"spBv1.0/Factory_VN/DDATA/{edge_node}",
            "timestamp_epoch_ms": int(time.time() * 1000),
            "seq": random.randint(1, 65535),
            "metrics": [{
                "name": metric_name,
                "value": round(value, 2) if isinstance(value, float) else value,
                "datatype": "Float" if isinstance(value, float) else "String",
                "unit": unit
            }]
        }

    @staticmethod
    def frame_tcp_socket(device_id: str, barcode: str, weight_kg: float) -> str:
        """Simulates raw ASCII stream from industrial barcode scanner and digital scale."""
        return f"\x02{device_id}|BC:{barcode}|WT:{weight_kg:.3f}KG|ST:OK\x03\r\n"


# =============================================================================
# 2. MULTI-PLC PIPELINE SIMULATOR ENGINE
# =============================================================================

class PLCPipelineSimulator:
    """
    Industrial Multi-PLC Telemetry Pipeline Engine.
    Simulates real-world behavior of 5 core plant stations in real time.
    """

    def __init__(self):
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.tick_interval_sec: float = 2.0
        self.scenario: str = "NORMAL"  # "NORMAL", "TAKT_CREEP", "BOTTLENECK_SURGE", "DEFECT_SPIKE"

        # Telemetry metrics and statistics
        self.total_ticks: int = 0
        self.total_frames_generated: int = 0
        self.last_tick_time: str = ""
        self.recent_frames: List[Dict[str, Any]] = []
        self._max_recent_frames: int = 60
        self._lock = threading.Lock()

        # Simulated Internal Station State Counters
        self.tbm_cycle_progress_sec: float = 0.0
        self.tbm_target_takt_sec: float = 45.0

        self.curing_active_presses = ["CP-01", "CP-02", "CP-03", "CP-04"]
        self.mixer_batch_count: int = 100
        self.tbm_built_count: int = 100

        # Physical Process Baselines
        self.baselines = {
            "mixer_temp": 158.0,
            "mixer_mooney": 58.0,
            "curing_mold_temp": 170.0,
            "curing_bladder_press": 21.0,
            "curing_steam_press": 15.1,
            "tbm_takt_time": 45.0,
            "tread_thickness_mm": 8.50,
            "cord_tension_n": 450.0
        }

    def set_scenario(self, scenario: str):
        """Sets the active factory simulation scenario."""
        valid_scenarios = ["NORMAL", "TAKT_CREEP", "BOTTLENECK_SURGE", "DEFECT_SPIKE"]
        scenario_upper = scenario.upper()
        if scenario_upper in valid_scenarios:
            self.scenario = scenario_upper
            print(f"[PLC Pipeline] Switched to scenario: {self.scenario}")
            return True
        return False

    def start(self, interval_sec: float = 2.0):
        """Starts the PLC pipeline background loop."""
        with self._lock:
            if not self.running:
                self.running = True
                self.tick_interval_sec = max(0.5, float(interval_sec))
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
                print(f"[PLC Pipeline] Started background simulation (Interval: {self.tick_interval_sec}s, Scenario: {self.scenario})")

    def stop(self):
        """Stops the PLC pipeline."""
        with self._lock:
            self.running = False
            print("[PLC Pipeline] Simulation stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status of the PLC pipeline."""
        with self._lock:
            return {
                "running": self.running,
                "scenario": self.scenario,
                "tick_interval_sec": self.tick_interval_sec,
                "total_ticks": self.total_ticks,
                "total_frames_generated": self.total_frames_generated,
                "last_tick_time": self.last_tick_time,
                "active_stations": {
                    "PLC-MIX": "RUNNING (Banbury BB-270)",
                    "PLC-EXT": "RUNNING (Triplex Extruder)",
                    "PLC-TBM": "RUNNING (VMI MAXX PCR)",
                    "PLC-CUR": f"RUNNING (Curing Presses: {', '.join(self.curing_active_presses)})",
                    "PLC-FIN": "RUNNING (X-Ray & Hofmann Balancer)"
                },
                "scenario_descriptions": {
                    "NORMAL": "Vận hành chuẩn SOP: Takt time 45s, nhiệt áp 170°C/21 bar, FPY > 90%",
                    "TAKT_CREEP": "Mòn dao cắt/trôi chu kỳ TBM: Takt time kéo dài lên 65–80s (Kích hoạt AI Anomaly)",
                    "BOTTLENECK_SURGE": "Sóng tải dồn ứ: Sản lượng TBM tăng gấp đôi trong khi Curing quá tải (Kích hoạt Bottleneck Rerouting)",
                    "DEFECT_SPIKE": "Tụt áp bàng bọng 18.2 bar & quá nhiệt mẻ luyện: Tỷ lệ lỗi tăng vọt (Kích hoạt TreeSHAP & Graph ML)"
                }
            }

    def get_recent_frames(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns the most recent industrial protocol frames generated by the pipeline."""
        with self._lock:
            return list(reversed(self.recent_frames[-limit:]))

    def _push_frame(self, frame: Dict[str, Any]):
        """Appends a generated packet frame into the memory buffer."""
        self.recent_frames.append(frame)
        self.total_frames_generated += 1
        if len(self.recent_frames) > self._max_recent_frames:
            self.recent_frames.pop(0)

    # =========================================================================
    # CORE PIPELINE TICK SIMULATION
    # =========================================================================

    def execute_tick(self) -> Dict[str, Any]:
        """
        Executes a single synchronized tick across all 5 plant PLC stations.
        Writes physics to DB and buffers protocol frames.
        """
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        self.last_tick_time = now_str
        self.total_ticks += 1

        generated_packets = []

        # ---------------------------------------------------------------------
        # 1. PLC-MIX: BANBURY MIXER TELEMETRY
        # ---------------------------------------------------------------------
        # Physics calculation based on scenario
        if self.scenario == "DEFECT_SPIKE":
            mix_temp = self.baselines["mixer_temp"] + random.uniform(8.0, 14.5)  # Overheating
            mooney = self.baselines["mixer_mooney"] + random.uniform(6.0, 11.0)
        else:
            mix_temp = self.baselines["mixer_temp"] + random.gauss(0, 1.2)
            mooney = self.baselines["mixer_mooney"] + random.gauss(0, 1.0)

        mix_frame_opc = IndustrialProtocolFramer.frame_opc_ua(
            "MIX-01", "ChamberDumpTemp", mix_temp, "Float", "Good"
        )
        mix_frame_sparkplug = IndustrialProtocolFramer.frame_mqtt_sparkplug(
            "MIX-01", "MooneyViscosity_ML1_4", mooney, "MU"
        )
        self._push_frame(mix_frame_opc)
        self._push_frame(mix_frame_sparkplug)
        generated_packets.extend([mix_frame_opc, mix_frame_sparkplug])

        # ---------------------------------------------------------------------
        # 2. PLC-EXT & CAL: EXTRUSION & STEEL CORD CALENDER
        # ---------------------------------------------------------------------
        if self.scenario == "DEFECT_SPIKE":
            cord_tension = self.baselines["cord_tension_n"] + random.uniform(45.0, 85.0)  # Extreme cord tension
            gauge_thick = self.baselines["tread_thickness_mm"] + random.uniform(0.35, 0.70)
        else:
            cord_tension = self.baselines["cord_tension_n"] + random.gauss(0, 7.5)
            gauge_thick = self.baselines["tread_thickness_mm"] + random.gauss(0, 0.05)

        ext_frame = IndustrialProtocolFramer.frame_opc_ua(
            "EXT-01", "ProfileThicknessLaser_mm", gauge_thick, "Float"
        )
        cal_frame = IndustrialProtocolFramer.frame_modbus_tcp(
            unit_id=2, register_addr=104, raw_value=cord_tension, description="Steel Cord Tension (Newtons)"
        )
        self._push_frame(ext_frame)
        self._push_frame(cal_frame)
        generated_packets.extend([ext_frame, cal_frame])

        # ---------------------------------------------------------------------
        # 3. PLC-TBM: TIRE BUILDING MACHINE (VMI MAXX PCR)
        # ---------------------------------------------------------------------
        # Calculate Takt Time based on scenario
        if self.scenario == "TAKT_CREEP":
            current_takt = round(self.baselines["tbm_takt_time"] + random.uniform(22.0, 38.0), 1)  # Abnormal creep
            wip_dwell = round(random.uniform(25.0, 48.0), 1)
        elif self.scenario == "BOTTLENECK_SURGE":
            current_takt = round(self.baselines["tbm_takt_time"] - random.uniform(8.0, 12.0), 1)  # Ultra fast output
            wip_dwell = round(random.uniform(32.0, 60.0), 1)
        else:
            current_takt = round(self.baselines["tbm_takt_time"] + random.gauss(0, 1.8), 1)
            wip_dwell = round(random.uniform(5.0, 12.0), 1)

        tbm_frame = IndustrialProtocolFramer.frame_opc_ua(
            "TBM-01", "ActualTaktTime_Sec", current_takt, "Float"
        )
        tbm_socket_sample = IndustrialProtocolFramer.frame_tcp_socket(
            "TBM-01", f"GT-20261006-{random.randint(100, 999)}", 9.25 + random.gauss(0, 0.08)
        )
        self._push_frame(tbm_frame)
        generated_packets.append(tbm_frame)

        # ---------------------------------------------------------------------
        # 4. PLC-CUR: HERBERT / KRUPP DUAL CAVITY CURING PRESSES
        # ---------------------------------------------------------------------
        # Step each curing cavity in SQLite
        curing_updates = []
        with get_db() as conn:
            cursor = conn.cursor()

            # Record TBM cycle telemetry into database for AI Anomaly & Bottleneck
            cursor.execute("""
                INSERT INTO production_cycle_telemetry (
                    timestamp, machine_id, cycle_type, sku, actual_takt_sec,
                    target_takt_sec, takt_deviation_sec, wip_queue_dwell_min,
                    temp_deviation_c, pressure_deviation_bar
                ) VALUES (?, 'TBM-01', 'TBM_BUILD', 'PCR-205-55R16-91V', ?, 45.0, ?, ?, 0.0, 0.0)
            """, (now_str, current_takt, round(current_takt - 45.0, 1), wip_dwell))

            # Fetch active cavities
            cavities = cursor.execute("SELECT * FROM curing_press_cavities").fetchall()
            for cav in cavities:
                p_id = cav["press_id"]
                side = cav["cavity_side"]
                state = cav["state"]
                elapsed = cav["cure_elapsed_seconds"]
                target = cav["cure_target_seconds"]

                gt_barcode = cav["current_gt_barcode"]

                # Apply physics according to scenario
                if self.scenario == "DEFECT_SPIKE" and p_id == "CP-02":
                    # Severe Bladder Pressure Drop fault injection!
                    m_temp = round(169.2 + random.gauss(0, 0.4), 1)
                    b_press = round(18.2 + random.gauss(0, 0.3), 1)  # Sub-nominal (<20.5 bar)
                    s_press = round(14.8 + random.gauss(0, 0.2), 1)
                elif self.scenario == "BOTTLENECK_SURGE" and p_id == "CP-01":
                    # Thermal controller lag: temperature slows down
                    m_temp = round(164.5 + random.gauss(0, 0.5), 1)
                    b_press = round(21.0 + random.gauss(0, 0.2), 1)
                    s_press = round(15.0 + random.gauss(0, 0.2), 1)
                else:
                    m_temp = round(170.0 + random.gauss(0, 0.4), 1)
                    b_press = round(21.0 + random.gauss(0, 0.2), 1)
                    s_press = round(15.1 + random.gauss(0, 0.2), 1)

                if state == "CURING":
                    # Critical Check: A cavity without a green tire MUST NOT cure!
                    if not gt_barcode:
                        cursor.execute("""
                            UPDATE curing_press_cavities
                            SET state = 'EMPTY', cure_elapsed_seconds = 0,
                                bladder_press_bar = 0.0, current_tire_serial = NULL
                            WHERE press_id = ? AND cavity_side = ?
                        """, (p_id, side))
                        continue

                    new_elapsed = elapsed + int(self.tick_interval_sec)
                    if new_elapsed >= target:
                        # Cycle completed: transition to COMPLETED
                        cursor.execute("""
                            UPDATE curing_press_cavities
                            SET state = 'COMPLETED', cure_elapsed_seconds = ?,
                                mold_temp_c = ?, bladder_press_bar = 0.0, steam_press_bar = ?
                            WHERE press_id = ? AND cavity_side = ?
                        """, (target, m_temp, s_press, p_id, side))
                    else:
                        cursor.execute("""
                            UPDATE curing_press_cavities
                            SET cure_elapsed_seconds = ?, mold_temp_c = ?,
                                bladder_press_bar = ?, steam_press_bar = ?
                            WHERE press_id = ? AND cavity_side = ?
                        """, (new_elapsed, m_temp, b_press, s_press, p_id, side))

                    # Log high-resolution telemetry point with tire_code
                    cursor.execute("""
                        INSERT INTO curing_telemetry_history (
                            press_id, cavity_side, timestamp, mold_temp, bladder_press, steam_press, phase, tire_code
                        ) VALUES (?, ?, ?, ?, ?, ?, 'HIGH_PRESSURE_CURE', ?)
                    """, (p_id, side, now_str, m_temp, b_press, s_press, gt_barcode))

                elif state == "COMPLETED":
                    # If ghost completed cavity without green tire, reset to EMPTY
                    if not gt_barcode:
                        cursor.execute("""
                            UPDATE curing_press_cavities
                            SET state = 'EMPTY', cure_elapsed_seconds = 0,
                                bladder_press_bar = 0.0, current_tire_serial = NULL
                            WHERE press_id = ? AND cavity_side = ?
                        """, (p_id, side))
                        continue

                    # Automatic unload in background with realistic pacing
                    if random.random() < 0.10:
                        self._simulate_curing_and_qc(cursor, p_id, side, cav, now_str)

                elif state == "EMPTY":
                    # Factory automation: If cavity is empty and green tires are waiting in buffer, auto-feed
                    if self.total_ticks % 10 == 0:
                        avail_gt = cursor.execute("""
                            SELECT gt_barcode, sku FROM production_green_tires
                            WHERE status IN ('BUILT', 'BUFFER')
                            ORDER BY build_timestamp ASC LIMIT 1
                        """).fetchone()
                        if avail_gt:
                            gt_code = avail_gt["gt_barcode"]
                            cursor.execute("""
                                UPDATE curing_press_cavities
                                SET state = 'CURING', current_gt_barcode = ?, cure_elapsed_seconds = 0,
                                    cure_start_time = ?, mold_temp_c = 170.0, bladder_press_bar = 21.0, steam_press_bar = 15.1
                                WHERE press_id = ? AND cavity_side = ?
                            """, (gt_code, now_str, p_id, side))
                            cursor.execute("UPDATE production_green_tires SET status = 'IN_CURING' WHERE gt_barcode = ?", (gt_code,))

                curing_updates.append((p_id, side, m_temp, b_press if state == "CURING" else 0.0))

            # Periodic Banbury Batch Telemetry (Every 8 ticks)
            if self.total_ticks % 8 == 0:
                self._simulate_mixer_batch(cursor, now_str)

            # Periodic TBM Green Tire Building (Every 12 ticks)
            if self.total_ticks % 12 == 0:
                self._simulate_tbm_green_tire_build(cursor, now_str)


            # -----------------------------------------------------------------
            # 5. SYNCHRONIZE OPC-UA & MODBUS FRAMES FOR CURING
            # -----------------------------------------------------------------
            if curing_updates:
                p_lead = curing_updates[0]
                cur_opc = IndustrialProtocolFramer.frame_opc_ua(
                    f"{p_lead[0]}.{p_lead[1]}", "BladderInternalPressure_Bar", p_lead[3], "Float"
                )
                cur_modbus = IndustrialProtocolFramer.frame_modbus_tcp(
                    unit_id=1, register_addr=201, raw_value=p_lead[2],
                    description=f"{p_lead[0]} Mold Temperature Setpoint 170.0C"
                )
                self._push_frame(cur_opc)
                self._push_frame(cur_modbus)
                generated_packets.extend([cur_opc, cur_modbus])

        return {
            "tick": self.total_ticks,
            "timestamp": now_str,
            "scenario": self.scenario,
            "generated_packets_count": len(generated_packets),
            "sample_packets": generated_packets[:4]
        }

    def _simulate_mixer_batch(self, cursor, now_str: str):
        """Simulates periodic Banbury mixer batch discharge and inserts into batch_process_telemetry."""
        self.mixer_batch_count += 1
        batch_id = f"BAT-{datetime.now().strftime('%Y%m')}-{self.mixer_batch_count:04d}"
        sku = "PCR-205-55R16-91V"

        is_defect = (self.scenario == "DEFECT_SPIKE" and random.random() < 0.75)
        if is_defect:
            dump_temp = 168.5 + random.uniform(2.0, 6.0)
            mooney = 66.0 + random.uniform(3.0, 7.0)
            bladder_p = 18.2 + random.uniform(-0.5, 0.4)
            cord_tension = 520.0 + random.uniform(20.0, 60.0)
            def_code = "DEF-CUR-001"
            def_name = "Bọt khí hông lốp do tụt áp bàng bọng"
        else:
            dump_temp = 158.0 + random.gauss(0, 1.2)
            mooney = 58.0 + random.gauss(0, 1.0)
            bladder_p = 21.0 + random.gauss(0, 0.2)
            cord_tension = 450.0 + random.gauss(0, 7.0)
            def_code = None
            def_name = None

        cursor.execute("""
            INSERT INTO batch_process_telemetry (
                batch_id, tire_serial, timestamp, sku, mooney_viscosity_ml,
                scorch_time_ts2_min, cure_time_tc90_min, dump_temp_c, rotor_energy_kwh,
                carbon_dispersion_pct, tread_gauge_thickness_mm, barrel_temp_zone4_c,
                extruder_head_pressure_bar, cord_tension_n, stitch_roller_press_bar,
                drum_expansion_diam_mm, splice_overlap_width_mm, internal_bladder_press_bar,
                mold_temp_upper_c, mold_temp_lower_c, steam_dome_press_bar,
                vacuum_exhaust_time_sec, bladder_cycle_age,
                is_defective, defect_code, defect_name
            ) VALUES (
                ?, NULL, ?, ?, ?, 3.5, 8.2, ?, 185.0, 96.5, 8.5, 105.0, 145.0, ?, 4.2,
                420.0, 12.0, ?, 170.0, 170.1, 15.1, 12.0, 140,
                ?, ?, ?
            )
        """, (
            batch_id, now_str, sku, round(mooney, 1), round(dump_temp, 1),
            round(cord_tension, 1), round(bladder_p, 1), 1 if is_defect else 0, def_code, def_name
        ))


    def _simulate_tbm_green_tire_build(self, cursor, now_str: str):
        """Simulates periodic Green Tire completion and adds to production_green_tires & work_orders."""
        self.tbm_built_count += 1
        now = datetime.now()
        date_prefix = now.strftime('%Y%m%d')

        count_today = cursor.execute("""
            SELECT count(*) FROM production_green_tires WHERE build_timestamp LIKE ?
        """, (f"{now.strftime('%Y-%m-%d')}%",)).fetchone()[0]

        gt_barcode = f"GT-{date_prefix}-{(count_today + 1):04d}"

        wo = cursor.execute("SELECT wo_id, sku FROM work_orders WHERE status = 'IN_PROGRESS' LIMIT 1").fetchone()
        if not wo:
            wo = cursor.execute("SELECT wo_id, sku FROM work_orders LIMIT 1").fetchone()
        wo_id = wo["wo_id"] if wo else "WO-2026-001"
        sku = wo["sku"] if wo else "PCR-205-55R16-91V"

        lots = cursor.execute("SELECT lot_id, component_type FROM inventory_components WHERE status = 'AVAILABLE' LIMIT 7").fetchall()
        lot_map = {r["component_type"]: r["lot_id"] for r in lots}

        cursor.execute("""
            INSERT INTO production_green_tires (
                gt_barcode, wo_id, sku, tbm_machine_id, operator_id,
                build_timestamp, actual_weight_kg,
                tread_lot, sidewall_lot, belt1_lot, belt2_lot, ply_lot, bead_lot, innerliner_lot,
                poka_yoke_status, status
            ) VALUES (?, ?, ?, 'TBM-01', 'OP-1001', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED_PASS', 'BUILT')
        """, (
            gt_barcode, wo_id, sku, now_str, round(9.25 + random.gauss(0, 0.08), 2),
            lot_map.get("TREAD", "LOT-TRD-202610-01"),
            lot_map.get("SIDEWALL", "LOT-SW-202610-01"),
            lot_map.get("BELT_1", "LOT-BLT1-202610-01"),
            lot_map.get("BELT_2", "LOT-BLT2-202610-01"),
            lot_map.get("PLY", "LOT-PLY-202610-01"),
            lot_map.get("BEAD", "LOT-BD-202610-01"),
            lot_map.get("INNERLINER", "LOT-INL-202610-01")
        ))

        cursor.execute("""
            UPDATE work_orders SET completed_qty = completed_qty + 1 WHERE wo_id = ?
        """, (wo_id,))

    def _simulate_curing_and_qc(self, cursor, p_id: str, side: str, cav: Any, now_str: str):
        """Unloads completed tire, stamps permanent serial, and runs QC auto-inspection."""
        gt_barcode = cav["current_gt_barcode"] if isinstance(cav, dict) else cav["current_gt_barcode"]
        if not gt_barcode:
            cursor.execute("""
                UPDATE curing_press_cavities
                SET state = 'EMPTY', cure_elapsed_seconds = 0,
                    mold_temp_c = 170.0, bladder_press_bar = 0.0, steam_press_bar = 15.0,
                    current_gt_barcode = NULL, current_tire_serial = NULL
                WHERE press_id = ? AND cavity_side = ?
            """, (p_id, side))
            return

        now = datetime.now()
        date_prefix = now.strftime('%Y%m%d')

        count_cured = cursor.execute("""
            SELECT count(*) FROM production_cured_tires WHERE cure_end_time LIKE ?
        """, (f"{now.strftime('%Y-%m-%d')}%",)).fetchone()[0]
        tire_serial = f"VN-T-{date_prefix}-{(100 + count_cured + 1):05d}"

        # Fetch SKU from green tire
        gt_row = cursor.execute("SELECT sku FROM production_green_tires WHERE gt_barcode = ?", (gt_barcode,)).fetchone()
        sku = gt_row["sku"] if gt_row else "PCR-205-55R16-91V"

        cursor.execute("""
            INSERT OR REPLACE INTO production_cured_tires (
                tire_serial, gt_barcode, sku, press_id, cavity_side, mold_id,
                curing_recipe_id, cure_start_time, cure_end_time, actual_cure_sec,
                avg_mold_temp_c, avg_bladder_press_bar, cure_quality_result, status
            ) VALUES (?, ?, ?, ?, ?, 'MOLD-PCR-01', 'RCP-PCR-205-55R16',
                      ?, ?, 780, 170.0, 21.0, 'PASS', 'INSPECTED')
        """, (tire_serial, gt_barcode, sku, p_id, side, now_str, now_str))

        cursor.execute("UPDATE production_green_tires SET status = 'CURED' WHERE gt_barcode = ?", (gt_barcode,))

        is_scrap = (self.scenario == "DEFECT_SPIKE" and random.random() < 0.6)
        if is_scrap:
            grade = "SCRAP"
            passed = 0
            v_code = "DEF-CUR-01"
            rfv = round(92.0 + random.uniform(5.0, 15.0), 1)
        else:
            grade = "GRADE_A"
            passed = 1
            v_code = None
            rfv = round(45.0 + random.gauss(0, 4.0), 1)

        cursor.execute("""
            INSERT OR REPLACE INTO quality_inspections (
                tire_serial, inspection_timestamp, inspector_id,
                visual_result, visual_defect_code, defect_location,
                xray_result, xray_defect_code, belt_alignment_mm,
                uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g,
                final_grade, passed, disposition_notes
            ) VALUES (?, ?, 'OP-3001', ?, ?, 'Tread Center', 'PASS', NULL, 0.4, ?, 22.0, 18.0, ?, ?, 'QC Inspector Automatic Verified')
        """, (
            tire_serial, now_str, "FAIL" if is_scrap else "PASS", v_code,
            rfv, grade, passed
        ))

        # Reset cavity to EMPTY (awaiting next green tire load)
        cursor.execute("""
            UPDATE curing_press_cavities
            SET state = 'EMPTY', cure_elapsed_seconds = 0,
                mold_temp_c = 170.0, bladder_press_bar = 0.0, steam_press_bar = 15.0,
                bladder_cycle_count = bladder_cycle_count + 1,
                current_gt_barcode = NULL, current_tire_serial = NULL
            WHERE press_id = ? AND cavity_side = ?
        """, (p_id, side))

    def _run_loop(self):

        """Continuous background thread loop."""
        while self.running:
            try:
                self.execute_tick()
            except Exception as e:
                print(f"[PLC Pipeline Warning] Error during tick: {e}")
            time.sleep(self.tick_interval_sec)


# Global singleton instance of the pipeline
plc_pipeline = PLCPipelineSimulator()
