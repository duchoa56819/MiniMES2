"""
Industrial IoT & Shop Floor Simulator for Tire MES.
Simulates real-time Curing Press PLC telemetry, temperature/pressure profiles,
cycle countdowns, and shop-floor activity.
"""

import random
import threading
import time
from datetime import datetime, timedelta
from app.database import get_db

SIMULATOR_RUNNING = False
_simulator_thread = None


def simulator_tick():
    """Performs a single simulation step for all active machines and curing presses."""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Update Curing Press Cavities
        cavities = cursor.execute("SELECT * FROM curing_press_cavities").fetchall()
        for cav in cavities:
            press_id = cav["press_id"]
            side = cav["cavity_side"]
            state = cav["state"]
            elapsed = cav["cure_elapsed_seconds"]
            target = cav["cure_target_seconds"]
            mold_temp = cav["mold_temp_c"]
            bladder_press = cav["bladder_press_bar"]
            steam_press = cav["steam_press_bar"]

            if state == "CURING":
                new_elapsed = elapsed + 5
                # Normal thermal fluctuation around setpoint (170C, 21 bar)
                new_temp = round(170.0 + random.uniform(-0.6, 0.6), 1)
                new_bladder = round(21.0 + random.uniform(-0.3, 0.3), 1)
                new_steam = round(15.1 + random.uniform(-0.2, 0.2), 1)

                if new_elapsed >= target:
                    # Curing cycle complete! Bladder exhaust phase
                    cursor.execute("""
                        UPDATE curing_press_cavities
                        SET state = 'COMPLETED',
                            cure_elapsed_seconds = ?,
                            mold_temp_c = ?,
                            bladder_press_bar = 0.0,
                            steam_press_bar = ?
                        WHERE press_id = ? AND cavity_side = ?
                    """, (target, new_temp, new_steam, press_id, side))
                else:
                    cursor.execute("""
                        UPDATE curing_press_cavities
                        SET cure_elapsed_seconds = ?,
                            mold_temp_c = ?,
                            bladder_press_bar = ?,
                            steam_press_bar = ?
                        WHERE press_id = ? AND cavity_side = ?
                    """, (new_elapsed, new_temp, new_bladder, new_steam, press_id, side))

                # Log telemetry point with tire_code
                gt_barcode = cav["current_gt_barcode"]
                cursor.execute("""
                    INSERT INTO curing_telemetry_history (press_id, cavity_side, timestamp, mold_temp, bladder_press, steam_press, phase, tire_code)
                    VALUES (?, ?, ?, ?, ?, ?, 'HIGH_PRESSURE_CURE', ?)
                """, (press_id, side, now_str, new_temp, new_bladder, new_steam, gt_barcode))


from app.services.plc_pipeline_simulator import plc_pipeline

SIMULATOR_RUNNING = False


def simulator_tick():
    """Performs a single simulation step via the multi-PLC pipeline."""
    return plc_pipeline.execute_tick()


def start_simulator():
    """Starts the background telemetry simulator via plc_pipeline."""
    global SIMULATOR_RUNNING
    if not SIMULATOR_RUNNING:
        SIMULATOR_RUNNING = True
        plc_pipeline.start(interval_sec=2.0)
        print("Tire MES Industrial Multi-PLC Pipeline Simulator started.")


def stop_simulator():
    """Stops the simulator."""
    global SIMULATOR_RUNNING
    SIMULATOR_RUNNING = False
    plc_pipeline.stop()
    print("Tire MES Industrial Multi-PLC Pipeline Simulator stopped.")

