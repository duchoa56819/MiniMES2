"""
Standalone Industrial Multi-PLC Pipeline Simulator CLI for Tire MES.
Simulates real-time inputs from 5 plant PLCs with protocol frame decoding.

Usage:
    python scripts/run_plc_pipeline.py --scenario NORMAL --interval 2.0
    python scripts/run_plc_pipeline.py --scenario TAKT_CREEP --interval 1.5
    python scripts/run_plc_pipeline.py --scenario DEFECT_SPIKE --interval 1.0
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.services.plc_pipeline_simulator import plc_pipeline, IndustrialProtocolFramer


def main():
    parser = argparse.ArgumentParser(description="Tire Factory Multi-PLC Industrial Pipeline Simulator")
    parser.add_argument("--scenario", type=str, default="NORMAL", choices=["NORMAL", "TAKT_CREEP", "BOTTLENECK_SURGE", "DEFECT_SPIKE"],
                        help="Factory operational scenario")
    parser.add_argument("--interval", type=float, default=2.0, help="Scan interval in seconds (default: 2.0)")
    parser.add_argument("--max-ticks", type=int, default=0, help="Maximum ticks to run (0 = infinite)")

    args = parser.parse_args()

    plc_pipeline.set_scenario(args.scenario)

    print("\n" + "=" * 80)
    print("   TIRE-MES 4.0 - AUTOMATED MULTI-PLC INDUSTRIAL PIPELINE SIMULATOR")
    print("   ANSI/ISA-95 Level 3 | Real-time OT Protocols (OPC-UA, Modbus, MQTT)")
    print(f"   [SCENARIO] : {args.scenario} ({plc_pipeline.get_status()['scenario_descriptions'].get(args.scenario, '')})")
    print(f"   [INTERVAL] : {args.interval}s per PLC scan cycle")
    print("=" * 80 + "\n")

    tick = 0
    try:
        while True:
            tick += 1
            res = plc_pipeline.execute_tick()
            ts = res["timestamp"]
            scenario = res["scenario"]

            print(f"\n>>> [PLC TICK #{tick:04d}] {ts} | SCENARIO: {scenario}")
            frames = plc_pipeline.get_recent_frames(limit=4)

            for f in frames:
                proto = f.get("protocol")
                if proto == "OPC_UA":
                    node = f.get("node_id", "")
                    val = f.get("value")
                    lat = f.get("latency_ms", 10.0)
                    status = f.get("status_code", "Good")
                    print(f"  [OPC-UA]    {node:<38} = {val} ({status}, {lat}ms)")
                elif proto == "MODBUS_TCP":
                    reg = f.get("register_address", "")
                    val = f.get("scaled_engineering_value")
                    desc = f.get("description", "")
                    raw = f.get("raw_hex", "")
                    print(f"  [MODBUS]    Unit:{f.get('unit_id')} Reg:{reg} ({raw}) = {val:<8} | {desc}")
                elif proto == "MQTT_SPARKPLUG_B":
                    metric = f.get("metrics", [{}])[0]
                    m_name = metric.get("name", "")
                    m_val = metric.get("value")
                    m_unit = metric.get("unit", "")
                    topic = f.get("topic", "")
                    print(f"  [MQTT/SpB]  {topic} -> {m_name}: {m_val} {m_unit}")

            if args.max_ticks > 0 and tick >= args.max_ticks:
                print(f"\n[PLC Pipeline] Reached target {args.max_ticks} ticks. Finished.")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\n[PLC Pipeline] Interrupted by user (Ctrl+C). Pipeline stopped safely.")


if __name__ == "__main__":
    main()
