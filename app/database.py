"""
MES Database Engine - SQLite Schema & Connection Handler
Compliant with ISA-95 Level 3 Manufacturing Execution System Standard for Tire Plants.
"""

import os
import sqlite3
from typing import Generator
from contextlib import contextmanager

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
DB_PATH = os.path.join(DB_DIR, "tire_mes.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dictionary-like row access, timeout, and WAL mode."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def get_read_replica_connection() -> sqlite3.Connection:
    """
    READ-REPLICA ENGINE (OLAP / Analytics / Dashboard Connection):
    Opens SQLite in strict READ-ONLY URI mode (mode=ro).
    - Guarantees 0% write-lock contention with shop floor transactional writers.
    - Any rogue INSERT/UPDATE/DELETE from analytics or reports will be rejected by SQLite engine.
    - Allows maximum read-concurrency with WAL mode.
    """
    db_uri = f"file:{os.path.abspath(DB_PATH).replace('\\', '/')}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


@contextmanager
def get_db(immediate: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """
    TRANSACTIONAL MASTER DB (OLTP Sàn Xưởng):
    When immediate=True, acquires RESERVED write lock immediately via 'BEGIN IMMEDIATE'.
    Prevents lock-upgrade deadlocks during high-concurrency barcode scans.
    """
    conn = get_db_connection()
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_read_replica_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for Read-Replica queries (Dashboard, Reports, Historical Audit)."""
    conn = get_read_replica_connection()
    try:
        yield conn
    finally:
        conn.close()



def init_db(force: bool = False):
    """Initializes the database schema for the Tire Manufacturing MES."""
    with get_db() as conn:
        cursor = conn.cursor()

        if force:
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.executescript("""
                DROP TABLE IF EXISTS bottleneck_forecasts;
                DROP TABLE IF EXISTS dynamic_routing_rules;
                DROP TABLE IF EXISTS ai_anomaly_logs;
                DROP TABLE IF EXISTS production_cycle_telemetry;
                DROP TABLE IF EXISTS tire_rework_history;
                DROP TABLE IF EXISTS quality_inspections;
                DROP TABLE IF EXISTS production_cured_tires;
                DROP TABLE IF EXISTS curing_press_cavities;
                DROP TABLE IF EXISTS production_green_tires;
                DROP TABLE IF EXISTS work_orders;
                DROP TABLE IF EXISTS inventory_components;
                DROP TABLE IF EXISTS master_boms;
                DROP TABLE IF EXISTS master_curing_recipes;
                DROP TABLE IF EXISTS master_defect_codes;
                DROP TABLE IF EXISTS master_operators;
                DROP TABLE IF EXISTS master_equipment;
                DROP TABLE IF EXISTS master_products;
                DROP TABLE IF EXISTS master_areas;
                DROP TABLE IF EXISTS equipment_downtime_logs;
                DROP TABLE IF EXISTS curing_telemetry_history;
                DROP TABLE IF EXISTS gateway_connectors;
                DROP TABLE IF EXISTS master_documents;
            """)
            cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.executescript("""
            -- =========================================================
            -- 1. MASTER DATA: PLANT HIERARCHY (ISA-95 Level 2 & 3)
            -- =========================================================
            CREATE TABLE IF NOT EXISTS master_areas (
                area_code TEXT PRIMARY KEY,
                area_name TEXT NOT NULL,
                description TEXT,
                sequence_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS master_equipment (
                machine_id TEXT PRIMARY KEY,
                machine_name TEXT NOT NULL,
                area_code TEXT NOT NULL,
                model TEXT,
                status TEXT CHECK(status IN ('RUNNING', 'IDLE', 'BREAKDOWN', 'CHANGEOVER', 'MAINTENANCE')) DEFAULT 'IDLE',
                cavities_count INTEGER DEFAULT 1,
                target_cycle_time_sec INTEGER DEFAULT 60,
                current_wo_id TEXT,
                total_cycles INTEGER DEFAULT 0,
                last_maintenance_date TEXT,
                oee_target REAL DEFAULT 85.0,
                FOREIGN KEY (area_code) REFERENCES master_areas(area_code)
            );

            -- =========================================================
            -- 2. MASTER DATA: PRODUCT & RECIPES
            -- =========================================================
            CREATE TABLE IF NOT EXISTS master_products (
                sku TEXT PRIMARY KEY,
                tire_size TEXT NOT NULL,
                pattern_name TEXT NOT NULL,
                segment TEXT CHECK(segment IN ('PCR', 'TBR', 'EV', 'OTR')) DEFAULT 'PCR',
                load_index TEXT NOT NULL,
                speed_rating TEXT NOT NULL,
                standard_weight_kg REAL NOT NULL,
                weight_tolerance_kg REAL DEFAULT 0.25,
                std_tbm_time_sec INTEGER DEFAULT 45,
                std_cure_time_sec INTEGER DEFAULT 780,
                std_cure_temp_c REAL DEFAULT 170.0,
                std_bladder_press_bar REAL DEFAULT 21.0,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS master_boms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                component_type TEXT CHECK(component_type IN ('TREAD', 'SIDEWALL', 'BELT_1', 'BELT_2', 'PLY', 'BEAD', 'INNERLINER')) NOT NULL,
                spec_code TEXT NOT NULL,
                compound_code TEXT NOT NULL,
                standard_qty REAL NOT NULL,
                unit TEXT DEFAULT 'PCS',
                FOREIGN KEY (sku) REFERENCES master_products(sku)
            );

            CREATE TABLE IF NOT EXISTS master_curing_recipes (
                recipe_id TEXT PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                cure_time_sec INTEGER NOT NULL,
                mold_temp_target_c REAL NOT NULL,
                mold_temp_tolerance_c REAL DEFAULT 2.5,
                platen_steam_bar REAL NOT NULL,
                bladder_press_bar REAL NOT NULL,
                vacuum_exhaust_sec INTEGER DEFAULT 40,
                max_bladder_cycles INTEGER DEFAULT 350,
                FOREIGN KEY (sku) REFERENCES master_products(sku)
            );

            CREATE TABLE IF NOT EXISTS master_defect_codes (
                defect_code TEXT PRIMARY KEY,
                defect_name_vi TEXT NOT NULL,
                defect_name_en TEXT NOT NULL,
                inspection_station TEXT CHECK(inspection_station IN ('VISUAL', 'XRAY', 'UNIFORMITY', 'ALL')) NOT NULL,
                severity TEXT CHECK(severity IN ('MINOR', 'MAJOR', 'CRITICAL')) NOT NULL,
                default_disposition TEXT CHECK(default_disposition IN ('REWORK', 'GRADE_B', 'SCRAP')) NOT NULL,
                root_cause_area TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS master_operators (
                badge_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                role TEXT CHECK(role IN ('TBM_OPERATOR', 'CURING_TECH', 'QC_INSPECTOR', 'SUPERVISOR')) NOT NULL,
                current_shift TEXT CHECK(current_shift IN ('SHIFT_A', 'SHIFT_B', 'SHIFT_C')) DEFAULT 'SHIFT_A',
                skill_level INTEGER CHECK(skill_level BETWEEN 1 AND 5) DEFAULT 3
            );

            -- =========================================================
            -- 3. INVENTORY: SEMI-FINISHED COMPONENTS & TRACEABILITY LOTS
            -- =========================================================
            CREATE TABLE IF NOT EXISTS inventory_components (
                lot_id TEXT PRIMARY KEY,
                component_type TEXT CHECK(component_type IN ('TREAD', 'SIDEWALL', 'BELT_1', 'BELT_2', 'PLY', 'BEAD', 'INNERLINER')) NOT NULL,
                spec_code TEXT NOT NULL,
                compound_code TEXT NOT NULL,
                produced_time TEXT NOT NULL,
                expiry_time TEXT NOT NULL,
                remaining_qty INTEGER NOT NULL DEFAULT 50,
                status TEXT CHECK(status IN ('AVAILABLE', 'RESERVED', 'EXPIRED', 'DEPLETED', 'QUARANTINE')) DEFAULT 'AVAILABLE',
                storage_location TEXT NOT NULL,
                raw_batch_ref TEXT NOT NULL
            );

            -- =========================================================
            -- 4. PRODUCTION PLANNING & EXECUTION: WORK ORDERS
            -- =========================================================
            CREATE TABLE IF NOT EXISTS work_orders (
                wo_id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                target_qty INTEGER NOT NULL,
                completed_qty INTEGER DEFAULT 0,
                scrap_qty INTEGER DEFAULT 0,
                planned_start TEXT NOT NULL,
                planned_end TEXT NOT NULL,
                actual_start TEXT,
                actual_end TEXT,
                status TEXT CHECK(status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'PAUSED')) DEFAULT 'RELEASED',
                priority TEXT CHECK(priority IN ('NORMAL', 'HIGH', 'URGENT')) DEFAULT 'NORMAL',
                assigned_machine TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sku) REFERENCES master_products(sku)
            );

            -- =========================================================
            -- 5. STAGE 1 EXECUTION: GREEN TIRES (LỐP SỐNG - TBM OUTPUT)
            -- =========================================================
            CREATE TABLE IF NOT EXISTS production_green_tires (
                gt_barcode TEXT PRIMARY KEY,
                wo_id TEXT NOT NULL,
                sku TEXT NOT NULL,
                tbm_machine_id TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                build_timestamp TEXT NOT NULL,
                actual_weight_kg REAL NOT NULL,
                tread_lot TEXT NOT NULL,
                sidewall_lot TEXT NOT NULL,
                belt1_lot TEXT NOT NULL,
                belt2_lot TEXT NOT NULL,
                ply_lot TEXT NOT NULL,
                bead_lot TEXT NOT NULL,
                innerliner_lot TEXT NOT NULL,
                poka_yoke_status TEXT CHECK(poka_yoke_status IN ('VERIFIED_PASS', 'OVERRIDDEN')) DEFAULT 'VERIFIED_PASS',
                status TEXT CHECK(status IN ('BUILT', 'BUFFER', 'IN_CURING', 'CURED', 'SCRAPPED', 'QUARANTINED')) DEFAULT 'BUILT',
                FOREIGN KEY (wo_id) REFERENCES work_orders(wo_id),
                FOREIGN KEY (sku) REFERENCES master_products(sku),
                FOREIGN KEY (tbm_machine_id) REFERENCES master_equipment(machine_id),
                FOREIGN KEY (operator_id) REFERENCES master_operators(badge_id)
            );

            -- =========================================================
            -- 6. STAGE 2 EXECUTION: CURING PRESSES & TELEMETRY
            -- =========================================================
            CREATE TABLE IF NOT EXISTS curing_press_cavities (
                press_id TEXT NOT NULL,
                cavity_side TEXT CHECK(cavity_side IN ('L', 'R')) NOT NULL,
                mold_id TEXT NOT NULL,
                current_gt_barcode TEXT,
                current_tire_serial TEXT,
                state TEXT CHECK(state IN ('EMPTY', 'LOADED', 'CURING', 'COMPLETED', 'ALARM')) DEFAULT 'EMPTY',
                cure_start_time TEXT,
                cure_target_seconds INTEGER DEFAULT 780,
                cure_elapsed_seconds INTEGER DEFAULT 0,
                mold_temp_c REAL DEFAULT 170.0,
                bladder_press_bar REAL DEFAULT 21.0,
                steam_press_bar REAL DEFAULT 15.0,
                bladder_cycle_count INTEGER DEFAULT 0,
                PRIMARY KEY (press_id, cavity_side),
                FOREIGN KEY (press_id) REFERENCES master_equipment(machine_id)
            );

            CREATE TABLE IF NOT EXISTS production_cured_tires (
                tire_serial TEXT PRIMARY KEY,
                gt_barcode TEXT NOT NULL UNIQUE,
                sku TEXT NOT NULL,
                press_id TEXT NOT NULL,
                cavity_side TEXT NOT NULL,
                mold_id TEXT NOT NULL,
                curing_recipe_id TEXT NOT NULL,
                cure_start_time TEXT NOT NULL,
                cure_end_time TEXT NOT NULL,
                actual_cure_sec INTEGER NOT NULL,
                avg_mold_temp_c REAL NOT NULL,
                avg_bladder_press_bar REAL NOT NULL,
                cure_quality_result TEXT CHECK(cure_quality_result IN ('PASS', 'TEMP_DEVIATION', 'PRESSURE_DROP')) DEFAULT 'PASS',
                status TEXT CHECK(status IN ('CURED', 'IN_INSPECTION', 'INSPECTED', 'SCRAPPED', 'QUARANTINED')) DEFAULT 'CURED',
                FOREIGN KEY (gt_barcode) REFERENCES production_green_tires(gt_barcode),
                FOREIGN KEY (sku) REFERENCES master_products(sku),
                FOREIGN KEY (press_id) REFERENCES master_equipment(machine_id)
            );

            -- =========================================================
            -- 7. STAGE 3 EXECUTION: QUALITY INSPECTION & DISPOSITION (KCS)
            -- =========================================================
            CREATE TABLE IF NOT EXISTS quality_inspections (
                inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tire_serial TEXT NOT NULL UNIQUE,
                inspection_timestamp TEXT NOT NULL,
                inspector_id TEXT NOT NULL,
                visual_result TEXT CHECK(visual_result IN ('PASS', 'FAIL')) NOT NULL,
                visual_defect_code TEXT,
                defect_location TEXT,
                xray_result TEXT CHECK(xray_result IN ('PASS', 'FAIL')) NOT NULL,
                xray_defect_code TEXT,
                belt_alignment_mm REAL DEFAULT 0.0,
                uniformity_rfv_n REAL DEFAULT 45.0,
                uniformity_lfv_n REAL DEFAULT 22.0,
                dynamic_balance_g REAL DEFAULT 18.0,
                final_grade TEXT CHECK(final_grade IN ('GRADE_A', 'GRADE_B', 'REWORK', 'SCRAP')) NOT NULL,
                passed INTEGER CHECK(passed IN (0, 1)) NOT NULL,
                disposition_notes TEXT,
                FOREIGN KEY (tire_serial) REFERENCES production_cured_tires(tire_serial),
                FOREIGN KEY (inspector_id) REFERENCES master_operators(badge_id),
                FOREIGN KEY (visual_defect_code) REFERENCES master_defect_codes(defect_code),
                FOREIGN KEY (xray_defect_code) REFERENCES master_defect_codes(defect_code)
            );

            CREATE TABLE IF NOT EXISTS tire_rework_history (
                rework_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tire_serial TEXT NOT NULL,
                rework_count INTEGER NOT NULL,
                rework_timestamp TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                pre_rework_grade TEXT NOT NULL,
                post_rework_status TEXT NOT NULL,
                FOREIGN KEY (tire_serial) REFERENCES production_cured_tires(tire_serial),
                FOREIGN KEY (operator_id) REFERENCES master_operators(badge_id)
            );

            -- =========================================================
            -- 8. OEE & DOWNTIME TRACKING & SENSOR TELEMETRY LOGS
            -- =========================================================
            CREATE TABLE IF NOT EXISTS equipment_downtime_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_minutes INTEGER DEFAULT 0,
                reason_code TEXT CHECK(reason_code IN ('MOLD_CHANGE', 'BREAKDOWN', 'NO_MATERIAL', 'PM', 'OPERATOR_REST', 'BLADDER_REPLACE')) NOT NULL,
                comments TEXT,
                FOREIGN KEY (machine_id) REFERENCES master_equipment(machine_id)
            );

            CREATE TABLE IF NOT EXISTS curing_telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                press_id TEXT NOT NULL,
                cavity_side TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                mold_temp REAL NOT NULL,
                bladder_press REAL NOT NULL,
                steam_press REAL NOT NULL,
                phase TEXT CHECK(phase IN ('SHAPING', 'HIGH_PRESSURE_CURE', 'EXHAUST', 'IDLE')) NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gateway_connectors (
                connector_id TEXT PRIMARY KEY,
                protocol_type TEXT CHECK(protocol_type IN ('OPC_UA', 'OPC_DA', 'MODBUS_TCP', 'MQTT', 'TCP_SOCKET')) NOT NULL,
                name TEXT NOT NULL,
                target_equipment TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                port INTEGER NOT NULL,
                scan_rate_ms INTEGER DEFAULT 1000,
                status TEXT CHECK(status IN ('CONNECTED', 'STANDBY', 'ERROR', 'DISCONNECTED')) DEFAULT 'CONNECTED',
                last_ping_ms REAL DEFAULT 12.5,
                sample_payload TEXT NOT NULL,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS master_documents (
                doc_id TEXT PRIMARY KEY,
                doc_code TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT CHECK(category IN ('SOP', 'DRAWING', 'RECIPE_SPEC', 'WORK_INSTRUCTION')) NOT NULL,
                target_area TEXT NOT NULL,
                revision TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                summary TEXT NOT NULL,
                content_html TEXT NOT NULL
            );

            -- =========================================================
            -- 9. AI UNSUPERVISED ANOMALY DETECTION & PRODUCTIVITY LOGS
            -- =========================================================
            CREATE TABLE IF NOT EXISTS ai_anomaly_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_type TEXT CHECK(entity_type IN ('MACHINE', 'TIRE', 'WIP_BUFFER')) NOT NULL,
                model_type TEXT CHECK(model_type IN ('ISOLATION_FOREST', 'AUTOENCODER', 'ENSEMBLE')) NOT NULL,
                takt_time_sec REAL NOT NULL,
                wip_queue_time_min REAL NOT NULL,
                anomaly_score REAL NOT NULL,
                severity TEXT CHECK(severity IN ('INFO', 'WARNING', 'CRITICAL')) NOT NULL,
                root_cause_diagnosis TEXT NOT NULL,
                mitigation_action TEXT NOT NULL,
                status TEXT CHECK(status IN ('DETECTED', 'ACKNOWLEDGED', 'RESOLVED')) DEFAULT 'DETECTED'
            );

            CREATE TABLE IF NOT EXISTS production_cycle_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                cycle_type TEXT CHECK(cycle_type IN ('TBM_BUILD', 'CURING_CYCLE', 'QC_SCAN')) NOT NULL,
                sku TEXT NOT NULL,
                actual_takt_sec REAL NOT NULL,
                target_takt_sec REAL NOT NULL,
                takt_deviation_sec REAL NOT NULL,
                wip_queue_dwell_min REAL NOT NULL,
                temp_deviation_c REAL DEFAULT 0.0,
                pressure_deviation_bar REAL DEFAULT 0.0
            );

            -- =========================================================
            -- 10. DYNAMIC BOTTLENECK PREDICTION & MATERIAL REROUTING
            -- =========================================================
            CREATE TABLE IF NOT EXISTS bottleneck_forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                horizon_hours INTEGER NOT NULL,
                current_bottleneck_station TEXT NOT NULL,
                predicted_bottleneck_station TEXT NOT NULL,
                shift_detected BOOLEAN NOT NULL DEFAULT 0,
                shift_probability REAL NOT NULL,
                station_bli_scores TEXT NOT NULL,
                predicted_wip_levels TEXT NOT NULL,
                root_cause_factors TEXT NOT NULL,
                reroute_action_needed BOOLEAN NOT NULL DEFAULT 0,
                recommended_plan TEXT,
                status TEXT CHECK(status IN ('PREDICTED', 'REROUTED', 'NORMALIZED')) DEFAULT 'PREDICTED'
            );

            CREATE TABLE IF NOT EXISTS dynamic_routing_rules (
                rule_id TEXT PRIMARY KEY,
                source_station TEXT NOT NULL,
                target_station TEXT NOT NULL,
                alternate_station TEXT NOT NULL,
                material_type TEXT NOT NULL,
                is_diverted BOOLEAN DEFAULT 0,
                divert_ratio_pct REAL DEFAULT 0.0,
                divert_reason TEXT,
                activated_at TEXT,
                throughput_gain_forecast_pct REAL DEFAULT 15.0
            );

            -- Create Performance Indexes for real-time querying
            CREATE INDEX IF NOT EXISTS idx_green_tire_sku ON production_green_tires(sku);
            CREATE INDEX IF NOT EXISTS idx_green_tire_wo ON production_green_tires(wo_id);
            CREATE INDEX IF NOT EXISTS idx_cured_tire_gt ON production_cured_tires(gt_barcode);
            CREATE INDEX IF NOT EXISTS idx_quality_serial ON quality_inspections(tire_serial);
            CREATE INDEX IF NOT EXISTS idx_wo_status ON work_orders(status);
            CREATE INDEX IF NOT EXISTS idx_components_lot ON inventory_components(lot_id);
            CREATE INDEX IF NOT EXISTS idx_anomaly_time ON ai_anomaly_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_cycle_machine ON production_cycle_telemetry(machine_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_bottleneck_time ON bottleneck_forecasts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_routing_source ON dynamic_routing_rules(source_station);
        """)


if __name__ == "__main__":
    init_db(force=True)
    print(f"Database initialized successfully at: {DB_PATH}")
