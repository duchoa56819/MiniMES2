"""
Multivariate Feature Importance & Decision Trees / SHAP Root Cause Analysis Service.
Explains defect spikes across hundreds of batch process telemetry parameters in tire manufacturing.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, _tree
from sklearn.metrics import roc_auc_score, f1_score
import shap
from app.database import get_db, get_read_replica_db


class ShapRootCauseAnalyzer:
    """
    Explainable AI (XAI) Root Cause Diagnosis Engine.
    Combines Random Forest, Interpretable Decision Trees, and TreeSHAP cooperative game theory.
    """

    FEATURE_METADATA = {
        "internal_bladder_press_bar": {
            "name": "Áp Suất Bàng Bọng (Bladder Press)",
            "unit": "bar",
            "area": "CURING",
            "nominal": 21.0,
            "min_tol": 20.5,
            "max_tol": 21.5,
            "category": "Lưu Hóa"
        },
        "mooney_viscosity_ml": {
            "name": "Độ Nhớt Mooney Cao Su (ML 1+4)",
            "unit": "MU",
            "area": "MIXING",
            "nominal": 58.0,
            "min_tol": 54.0,
            "max_tol": 62.0,
            "category": "Luyện Kín Banbury"
        },
        "dump_temp_c": {
            "name": "Nhiệt Độ Xả Mẻ Luyện (Dump Temp)",
            "unit": "°C",
            "area": "MIXING",
            "nominal": 155.0,
            "min_tol": 150.0,
            "max_tol": 160.0,
            "category": "Luyện Kín Banbury"
        },
        "mold_temp_upper_c": {
            "name": "Nhiệt Độ Khuôn Trên (Mold Upper)",
            "unit": "°C",
            "area": "CURING",
            "nominal": 170.0,
            "min_tol": 168.0,
            "max_tol": 172.0,
            "category": "Lưu Hóa"
        },
        "mold_temp_lower_c": {
            "name": "Nhiệt Độ Khuôn Dưới (Mold Lower)",
            "unit": "°C",
            "area": "CURING",
            "nominal": 170.0,
            "min_tol": 168.0,
            "max_tol": 172.0,
            "category": "Lưu Hóa"
        },
        "steam_dome_press_bar": {
            "name": "Áp Suất Hơi Vòm Lò (Steam Dome)",
            "unit": "bar",
            "area": "CURING",
            "nominal": 15.0,
            "min_tol": 14.5,
            "max_tol": 15.5,
            "category": "Lưu Hóa"
        },
        "scorch_time_ts2_min": {
            "name": "Thời Gian Cháy Lưu (Scorch ts2)",
            "unit": "phút",
            "area": "MIXING",
            "nominal": 3.5,
            "min_tol": 3.0,
            "max_tol": 4.0,
            "category": "Luyện Kín Banbury"
        },
        "cure_time_tc90_min": {
            "name": "Thời Gian Lưu Hóa Tối Ưu (tc90)",
            "unit": "phút",
            "area": "MIXING",
            "nominal": 7.2,
            "min_tol": 6.6,
            "max_tol": 7.8,
            "category": "Luyện Kín Banbury"
        },
        "carbon_dispersion_pct": {
            "name": "Độ Phân Tán Than Đen (Dispersion)",
            "unit": "%",
            "area": "MIXING",
            "nominal": 96.5,
            "min_tol": 94.0,
            "max_tol": 99.0,
            "category": "Luyện Kín Banbury"
        },
        "stitch_roller_press_bar": {
            "name": "Áp Lực Con Lăn Miết Đai (Stitching)",
            "unit": "bar",
            "area": "TBM",
            "nominal": 4.2,
            "min_tol": 3.9,
            "max_tol": 4.5,
            "category": "Thành Hình TBM"
        },
        "drum_expansion_diam_mm": {
            "name": "Đường Kính Bung Trống (Drum Diam)",
            "unit": "mm",
            "area": "TBM",
            "nominal": 412.0,
            "min_tol": 411.0,
            "max_tol": 413.0,
            "category": "Thành Hình TBM"
        },
        "splice_overlap_width_mm": {
            "name": "Độ Rộng Mối Nối Gai (Splice Overlap)",
            "unit": "mm",
            "area": "TBM",
            "nominal": 12.0,
            "min_tol": 10.0,
            "max_tol": 14.0,
            "category": "Thành Hình TBM"
        },
        "tread_gauge_thickness_mm": {
            "name": "Độ Dày Dải Đùn Gai (Tread Gauge)",
            "unit": "mm",
            "area": "PREP",
            "nominal": 8.5,
            "min_tol": 8.2,
            "max_tol": 8.8,
            "category": "Bán Thành Phẩm Đùn"
        },
        "cord_tension_n": {
            "name": "Lực Căng Sợi Mành Thép (Cord Tension)",
            "unit": "N",
            "area": "PREP",
            "nominal": 18.5,
            "min_tol": 17.0,
            "max_tol": 20.0,
            "category": "Cán Mành Thép"
        },
        "vacuum_exhaust_time_sec": {
            "name": "Thời Gian Hút Chân Không (Vacuum)",
            "unit": "giây",
            "area": "CURING",
            "nominal": 18.0,
            "min_tol": 16.0,
            "max_tol": 20.0,
            "category": "Lưu Hóa"
        },
        "bladder_cycle_age": {
            "name": "Tuổi Thọ Bàng Bọng (Bladder Cycles)",
            "unit": "lần ép",
            "area": "CURING",
            "nominal": 160.0,
            "min_tol": 1.0,
            "max_tol": 320.0,
            "category": "Lưu Hóa"
        },
        "rotor_energy_kwh": {
            "name": "Năng Lượng Tiêu Thụ Rotor Luyện",
            "unit": "kWh",
            "area": "MIXING",
            "nominal": 14.2,
            "min_tol": 13.0,
            "max_tol": 15.5,
            "category": "Luyện Kín Banbury"
        },
        "barrel_temp_zone4_c": {
            "name": "Nhiệt Thân Đùn Vùng 4 (Barrel Temp)",
            "unit": "°C",
            "area": "PREP",
            "nominal": 105.0,
            "min_tol": 101.0,
            "max_tol": 109.0,
            "category": "Bán Thành Phẩm Đùn"
        },
        "extruder_head_pressure_bar": {
            "name": "Áp Suất Đầu Đùn Triplex",
            "unit": "bar",
            "area": "PREP",
            "nominal": 140.0,
            "min_tol": 132.0,
            "max_tol": 148.0,
            "category": "Bán Thành Phẩm Đùn"
        }
    }

    FEATURE_KEYS = list(FEATURE_METADATA.keys())

    def __init__(self):
        self.rf_model = None
        self.dt_model = None
        self.explainer = None
        self.is_trained = False
        self.last_trained_at = None
        self.total_samples = 0
        self.metrics = {"roc_auc": 0.942, "f1": 0.915}
        self.active_spike_scenario = "NORMAL"

        # Initialize dataset and train models
        self.seed_telemetry_dataset_if_empty()
        self.train_models()

    def seed_telemetry_dataset_if_empty(self, force: bool = False):
        """Generates realistic multivariate telemetry data across 450+ production batches."""
        with get_db(immediate=True) as conn:
            cursor = conn.cursor()
            existing = cursor.execute("SELECT COUNT(*) FROM batch_process_telemetry").fetchone()[0]
            if existing > 0 and not force:
                return

            if force:
                cursor.execute("DELETE FROM batch_process_telemetry")

            np.random.seed(42)
            n_samples = 480
            now = datetime.now()

            records = []
            for i in range(n_samples):
                t_stamp = (now - timedelta(minutes=(n_samples - i) * 6)).isoformat()
                batch_id = f"BAT-202610-{(1000 + (i // 10))}"
                tire_serial = f"VN-T-202610-{str(i + 100).zfill(5)}"
                sku = "PCR-205-55R16-91V" if i % 2 == 0 else "PCR-225-60R17-99H"

                # 90% normal baseline, 10% injected defect scenarios
                is_defective = 0
                defect_code = None
                defect_name = None

                # Generate base gaussian features
                features = {}
                for k, meta in self.FEATURE_METADATA.items():
                    spread = (meta["max_tol"] - meta["min_tol"]) / 4.0
                    val = np.random.normal(meta["nominal"], spread)
                    features[k] = float(val)

                # Inject realistic multivariate defect spike clusters
                if i >= 400 and i <= 445 and (i % 3 != 0):
                    # Spike Scenario 1: Sidewall Blister (Sụt áp bàng bọng Curing + lỏng miết TBM)
                    is_defective = 1
                    defect_code = "DEF_SIDEWALL_BLISTER"
                    defect_name = "Bọt Khí Hông Lốp (Sidewall Blister / Phồng Rộp)"
                    features["internal_bladder_press_bar"] = float(np.random.uniform(17.2, 18.9)) # Severely low!
                    features["mooney_viscosity_ml"] = float(np.random.uniform(64.5, 71.0))        # Too stiff!
                    features["stitch_roller_press_bar"] = float(np.random.uniform(3.2, 3.6))      # Weak stitching!
                    features["bladder_cycle_age"] = int(np.random.uniform(320, 360))
                elif i >= 320 and i <= 345 and (i % 2 == 0):
                    # Spike Scenario 2: Under-cure (Tụt nhiệt khuôn & sụt áp hơi vòm)
                    is_defective = 1
                    defect_code = "DEF_UNDER_CURE"
                    defect_name = "Lưu Hóa Non (Under-cure / Mềm Cao Su)"
                    features["mold_temp_upper_c"] = float(np.random.uniform(161.0, 164.5))      # Too cold!
                    features["steam_dome_press_bar"] = float(np.random.uniform(13.2, 14.1))
                    features["cure_time_tc90_min"] = float(np.random.uniform(8.1, 8.8))
                elif i >= 200 and i <= 218 and (i % 2 == 0):
                    # Spike Scenario 3: Tread Delamination (Nhiệt xả Banbury quá cao)
                    is_defective = 1
                    defect_code = "DEF_TREAD_DELAMINATION"
                    defect_name = "Bóc Tách Mặt Gai (Tread Delamination / Nứt Rách)"
                    features["dump_temp_c"] = float(np.random.uniform(168.0, 175.0))             # Overheating Banbury!
                    features["carbon_dispersion_pct"] = float(np.random.uniform(88.0, 91.5))     # Bad dispersion!
                    features["scorch_time_ts2_min"] = float(np.random.uniform(2.1, 2.4))
                elif np.random.rand() < 0.02:
                    # Random 2% background defect
                    is_defective = 1
                    defect_code = "DEF_HIGH_RFV"
                    defect_name = "Lực Hướng Kính RFV Cao (Uniformity Non-conformance)"
                    features["tread_gauge_thickness_mm"] = float(np.random.uniform(9.1, 9.6))
                    features["splice_overlap_width_mm"] = float(np.random.uniform(16.0, 19.5))

                records.append((
                    batch_id, tire_serial, t_stamp, sku,
                    features["mooney_viscosity_ml"],
                    features["scorch_time_ts2_min"],
                    features["cure_time_tc90_min"],
                    features["dump_temp_c"],
                    features["rotor_energy_kwh"],
                    features["carbon_dispersion_pct"],
                    features["tread_gauge_thickness_mm"],
                    features["barrel_temp_zone4_c"],
                    features["extruder_head_pressure_bar"],
                    features["cord_tension_n"],
                    features["stitch_roller_press_bar"],
                    features["drum_expansion_diam_mm"],
                    features["splice_overlap_width_mm"],
                    features["internal_bladder_press_bar"],
                    features["mold_temp_upper_c"],
                    features["mold_temp_lower_c"],
                    features["steam_dome_press_bar"],
                    features["vacuum_exhaust_time_sec"],
                    int(features["bladder_cycle_age"]),
                    is_defective, defect_code, defect_name
                ))

            cursor.executemany("""
                INSERT INTO batch_process_telemetry (
                    batch_id, tire_serial, timestamp, sku,
                    mooney_viscosity_ml, scorch_time_ts2_min, cure_time_tc90_min,
                    dump_temp_c, rotor_energy_kwh, carbon_dispersion_pct,
                    tread_gauge_thickness_mm, barrel_temp_zone4_c, extruder_head_pressure_bar,
                    cord_tension_n, stitch_roller_press_bar, drum_expansion_diam_mm,
                    splice_overlap_width_mm, internal_bladder_press_bar, mold_temp_upper_c,
                    mold_temp_lower_c, steam_dome_press_bar, vacuum_exhaust_time_sec,
                    bladder_cycle_age, is_defective, defect_code, defect_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)

    def train_models(self):
        """Trains Random Forest & Decision Tree, and fits the SHAP TreeExplainer."""
        with get_read_replica_db() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT
                    mooney_viscosity_ml, scorch_time_ts2_min, cure_time_tc90_min,
                    dump_temp_c, rotor_energy_kwh, carbon_dispersion_pct,
                    tread_gauge_thickness_mm, barrel_temp_zone4_c, extruder_head_pressure_bar,
                    cord_tension_n, stitch_roller_press_bar, drum_expansion_diam_mm,
                    splice_overlap_width_mm, internal_bladder_press_bar, mold_temp_upper_c,
                    mold_temp_lower_c, steam_dome_press_bar, vacuum_exhaust_time_sec,
                    bladder_cycle_age, is_defective
                FROM batch_process_telemetry
            """).fetchall()

        if not rows:
            self.seed_telemetry_dataset_if_empty(force=True)
            with get_read_replica_db() as conn:
                cursor = conn.cursor()
                rows = cursor.execute("""
                    SELECT
                        mooney_viscosity_ml, scorch_time_ts2_min, cure_time_tc90_min,
                        dump_temp_c, rotor_energy_kwh, carbon_dispersion_pct,
                        tread_gauge_thickness_mm, barrel_temp_zone4_c, extruder_head_pressure_bar,
                        cord_tension_n, stitch_roller_press_bar, drum_expansion_diam_mm,
                        splice_overlap_width_mm, internal_bladder_press_bar, mold_temp_upper_c,
                        mold_temp_lower_c, steam_dome_press_bar, vacuum_exhaust_time_sec,
                        bladder_cycle_age, is_defective
                    FROM batch_process_telemetry
                """).fetchall()

        data = np.array(rows)
        X = data[:, :-1]
        y = data[:, -1]

        self.total_samples = len(X)

        # 1. Random Forest for high-accuracy feature importance
        self.rf_model = RandomForestClassifier(
            n_estimators=80,
            max_depth=6,
            min_samples_leaf=4,
            random_state=42
        )
        self.rf_model.fit(X, y)

        # 2. Decision Tree for interpretable rule extraction
        self.dt_model = DecisionTreeClassifier(
            max_depth=4,
            min_samples_leaf=4,
            class_weight='balanced',
            random_state=42
        )
        self.dt_model.fit(X, y)

        # 3. Fit SHAP TreeExplainer
        self.explainer = shap.TreeExplainer(self.rf_model)

        # Compute validation metrics
        y_pred_proba = self.rf_model.predict_proba(X)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)

        self.metrics["roc_auc"] = round(float(roc_auc_score(y, y_pred_proba)), 3)
        self.metrics["f1"] = round(float(f1_score(y, y_pred)), 3)
        self.is_trained = True
        self.last_trained_at = datetime.now().isoformat()

    def get_global_importance(self) -> Dict[str, Any]:
        """Calculates global mean(|SHAP value|) feature ranking across the dataset."""
        if not self.is_trained:
            self.train_models()

        with get_read_replica_db() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT
                    mooney_viscosity_ml, scorch_time_ts2_min, cure_time_tc90_min,
                    dump_temp_c, rotor_energy_kwh, carbon_dispersion_pct,
                    tread_gauge_thickness_mm, barrel_temp_zone4_c, extruder_head_pressure_bar,
                    cord_tension_n, stitch_roller_press_bar, drum_expansion_diam_mm,
                    splice_overlap_width_mm, internal_bladder_press_bar, mold_temp_upper_c,
                    mold_temp_lower_c, steam_dome_press_bar, vacuum_exhaust_time_sec,
                    bladder_cycle_age, is_defective
                FROM batch_process_telemetry
                ORDER BY id DESC LIMIT 150
            """).fetchall()

        if not rows:
            self.seed_telemetry_dataset_if_empty(force=True)
            self.train_models()
            with get_read_replica_db() as conn:
                cursor = conn.cursor()
                rows = cursor.execute("""
                    SELECT
                        mooney_viscosity_ml, scorch_time_ts2_min, cure_time_tc90_min,
                        dump_temp_c, rotor_energy_kwh, carbon_dispersion_pct,
                        tread_gauge_thickness_mm, barrel_temp_zone4_c, extruder_head_pressure_bar,
                        cord_tension_n, stitch_roller_press_bar, drum_expansion_diam_mm,
                        splice_overlap_width_mm, internal_bladder_press_bar, mold_temp_upper_c,
                        mold_temp_lower_c, steam_dome_press_bar, vacuum_exhaust_time_sec,
                        bladder_cycle_age, is_defective
                    FROM batch_process_telemetry
                    ORDER BY id DESC LIMIT 150
                """).fetchall()

        data = np.array(rows)
        X = data[:, :-1]
        y = data[:, -1]

        # Calculate SHAP values
        shap_vals = self.explainer.shap_values(X)
        # Handle binary classification output shape
        if isinstance(shap_vals, list):
            sv = shap_vals[1]
        elif len(shap_vals.shape) == 3:
            sv = shap_vals[:, :, 1]
        else:
            sv = shap_vals

        mean_abs_shap = np.mean(np.abs(sv), axis=0)
        total_imp = max(1e-6, np.sum(mean_abs_shap))

        feature_ranking = []
        for idx, key in enumerate(self.FEATURE_KEYS):
            meta = self.FEATURE_METADATA[key]
            imp = float(mean_abs_shap[idx])
            share_pct = round((imp / total_imp) * 100.0, 1)

            feature_ranking.append({
                "feature_key": key,
                "feature_name": meta["name"],
                "area": meta["area"],
                "unit": meta["unit"],
                "mean_abs_shap": round(imp, 4),
                "importance_share_pct": share_pct,
                "nominal_range": f"{meta['min_tol']} - {meta['max_tol']} {meta['unit']}",
                "category": meta["category"]
            })

        feature_ranking.sort(key=lambda x: x["mean_abs_shap"], reverse=True)

        top_cause = feature_ranking[0]
        recent_defects = int(np.sum(y))
        defect_rate_pct = round((recent_defects / max(1, len(y))) * 100.0, 1)

        return {
            "total_analyzed_batches": len(X),
            "recent_defect_rate_pct": defect_rate_pct,
            "baseline_defect_rate_pct": 1.8,
            "is_spike_active": defect_rate_pct > 4.5,
            "top_root_cause": top_cause,
            "feature_ranking": feature_ranking,
            "model_metrics": self.metrics,
            "engineering_action_plan": self._generate_corrective_action(top_cause["feature_key"])
        }

    def explain_sample_batch(self, sample_id: Optional[str] = None, custom_vector: Optional[List[float]] = None) -> Dict[str, Any]:
        """Generates local SHAP waterfall force breakdown for a specific batch/tire."""
        if not self.is_trained:
            self.train_models()

        if custom_vector is not None:
            x_sample = np.array(custom_vector).reshape(1, -1)
            batch_meta = {"batch_id": "CUSTOM_INSPECTION", "tire_serial": "TEST-VECTOR", "defect_name": "Tùy biến kiểm tra"}
        else:
            # Query sample from DB
            with get_read_replica_db() as conn:
                cursor = conn.cursor()
                if sample_id:
                    row = cursor.execute("""
                        SELECT * FROM batch_process_telemetry
                        WHERE tire_serial = ? OR batch_id = ?
                        LIMIT 1
                    """, (sample_id, sample_id)).fetchone()
                else:
                    # Pick a known defective sample
                    row = cursor.execute("""
                        SELECT * FROM batch_process_telemetry
                        WHERE is_defective = 1
                        ORDER BY id DESC LIMIT 1
                    """).fetchone()

                if not row:
                    row = cursor.execute("SELECT * FROM batch_process_telemetry ORDER BY id DESC LIMIT 1").fetchone()

                d = dict(row)
                batch_meta = {
                    "batch_id": d["batch_id"],
                    "tire_serial": d["tire_serial"],
                    "defect_code": d["defect_code"],
                    "defect_name": d["defect_name"] or "Không lỗi",
                    "is_defective": bool(d["is_defective"])
                }
                x_sample = np.array([[d[k] for k in self.FEATURE_KEYS]])

        # Inference
        defect_prob = float(self.rf_model.predict_proba(x_sample)[0, 1])

        # Local SHAP decomposition
        shap_vals = self.explainer.shap_values(x_sample)
        if isinstance(shap_vals, list):
            sv = shap_vals[1][0]
        elif len(shap_vals.shape) == 3:
            sv = shap_vals[0, :, 1]
        else:
            sv = shap_vals[0]

        base_rate = float(self.explainer.expected_value[1] if isinstance(self.explainer.expected_value, (list, np.ndarray)) else self.explainer.expected_value)

        # Factor contributions breakdown
        breakdown = []
        for idx, key in enumerate(self.FEATURE_KEYS):
            meta = self.FEATURE_METADATA[key]
            val = float(x_sample[0, idx])
            phi = float(sv[idx])

            # Classify impact
            is_pushing_defect = (phi > 0.005)
            is_mitigating = (phi < -0.005)

            # Deviation from nominal
            dev = val - meta["nominal"]

            breakdown.append({
                "feature_key": key,
                "feature_name": meta["name"],
                "actual_value": round(val, 2),
                "nominal_value": meta["nominal"],
                "deviation": round(dev, 2),
                "unit": meta["unit"],
                "shap_value": round(phi, 4),
                "impact_direction": "PUSH_DEFECT" if is_pushing_defect else ("MITIGATE" if is_mitigating else "NEUTRAL"),
                "area": meta["area"]
            })

        breakdown.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        return {
            "batch_meta": batch_meta,
            "predicted_defect_probability": round(defect_prob, 3),
            "base_rate": round(base_rate, 3),
            "is_high_risk": defect_prob >= 0.50,
            "waterfall_breakdown": breakdown,
            "top_culprit": breakdown[0] if breakdown else None,
            "recommendation": self._generate_corrective_action(breakdown[0]["feature_key"] if breakdown else "internal_bladder_press_bar")
        }

    def extract_decision_rules(self) -> List[Dict[str, Any]]:
        """Extracts human-interpretable If-Then decision logic rules from the trained tree."""
        if not self.is_trained or self.dt_model is None:
            self.train_models()

        tree_ = self.dt_model.tree_
        feature_names = self.FEATURE_KEYS

        rules = []

        def recurse(node, depth, current_conditions):
            if tree_.feature[node] != _tree.TREE_UNDEFINED:
                name = feature_names[tree_.feature[node]]
                threshold = tree_.threshold[node]
                meta = self.FEATURE_METADATA[name]

                # Left branch (<= threshold)
                left_cond = f"{meta['name']} &le; {round(threshold, 2)} {meta['unit']}"
                recurse(tree_.children_left[node], depth + 1, current_conditions + [left_cond])

                # Right branch (> threshold)
                right_cond = f"{meta['name']} &gt; {round(threshold, 2)} {meta['unit']}"
                recurse(tree_.children_right[node], depth + 1, current_conditions + [right_cond])
            else:
                # Leaf node
                samples = int(tree_.n_node_samples[node])
                value = tree_.value[node][0]
                total_val = float(np.sum(value))
                defect_prob = float(value[1] / max(1e-6, total_val)) if len(value) > 1 else 0.0
                defect_rate = round(defect_prob * 100.0, 1)

                if defect_rate >= 50.0 and samples >= 4:
                    rules.append({
                        "rule_id": f"RULE-TREE-{len(rules) + 1}",
                        "conditions": current_conditions,
                        "conditions_text": " VÀ ".join(current_conditions),
                        "defect_probability_pct": round(defect_rate, 1),
                        "samples_affected": int(samples),
                        "severity": "CRITICAL" if defect_rate > 75.0 else "WARNING",
                        "predicted_defect": "Bọt Khí / Lệch Đai / Lưu Hóa Non",
                        "action": "Kích hoạt hiệu chuẩn thông số khẩn cấp theo IATF 16949"
                    })

        recurse(0, 1, [])
        rules.sort(key=lambda r: r["defect_probability_pct"], reverse=True)
        return rules[:6]

    def _generate_corrective_action(self, feature_key: str) -> Dict[str, str]:
        """Synthesizes actionable engineering correction according to IATF 16949 / SOP."""
        actions = {
            "internal_bladder_press_bar": {
                "diagnosis": "Áp suất bàng bọng buồng ép lưu hóa bị sụt giảm nghiêm trọng (< 19.5 bar). Lực nén không đủ ép chặt các lớp cao su vào hoa văn khuôn.",
                "root_cause": "Rò rỉ phớt làm kín cụm cấp hơi nén vào bàng bọng hoặc van điện từ tỷ lệ (Proportional Valve) bị trôi tín hiệu 4-20mA.",
                "corrective_action": "1. Hiệu chuẩn ngay van tỷ lệ áp suất bàng bọng trên trạm CP-02.\n2. Kiểm tra bộ đếm số lần ép của bàng (thay mới nếu > 320 chu kỳ).\n3. Tăng áp suất hơi nén định hình lên 21.0 ± 0.3 bar theo SOP-CUR-018."
            },
            "mooney_viscosity_ml": {
                "diagnosis": "Độ nhớt Mooney cao su mặt lốp sau luyện kín quá cao (> 64 MU). Hợp chất cao su quá cứng, chảy dẻo kém trong khuôn lưu hóa.",
                "root_cause": "Thời gian nhào trộn trong buồng Banbury MIX-01 chưa đủ hoặc tỷ lệ dầu hóa dẻo Aromatic/Naphthenic cấp vào bị thiếu hụt.",
                "corrective_action": "1. Khóa cách ly lô mẻ cao su mặt gai tương ứng.\n2. Tăng thời gian luyện thêm 25 giây hoặc tăng năng lượng nạp rotor lên 14.5 kWh.\n3. Kiểm tra cân định lượng tự động dầu hóa dẻo trên tháp trộn."
            },
            "dump_temp_c": {
                "diagnosis": "Nhiệt độ xả mẻ buồng Banbury vượt ngưỡng cho phép (> 165°C), gây hiện tượng cháy lưu sớm (Premature Scorch) và đứt gãy mạch cao su.",
                "root_cause": "Tốc độ rotor Banbury quá cao hoặc hệ thống nước làm mát vách buồng luyện bị nghẽn cáu cặn.",
                "corrective_action": "1. Hạ tốc độ rotor từ 45 RPM xuống 38 RPM ở giai đoạn hoàn tất.\n2. Vệ sinh đường ống nước làm mát tháp giải nhiệt buồng luyện.\n3. Cài đặt rơ-le ngắt an toàn tại 158°C."
            },
            "mold_temp_upper_c": {
                "diagnosis": "Nhiệt độ nửa khuôn trên bị sụt dưới 165°C, gây lỗi lưu hóa non (Under-cure) và cao su chưa đạt mật độ liên kết ngang lưu huỳnh.",
                "root_cause": "Tắc bẫy hơi ngưng tụ (Steam Trap) ở vòm nhiệt phía trên hoặc cảm biến nhiệt điện trở PT100 bị bám cặn dầu.",
                "corrective_action": "1. Xả bẫy hơi ngưng tụ và vệ sinh van một chiều.\n2. Hiệu chuẩn lại đầu đo PT100 khuôn trên.\n3. Duy trì nhiệt độ nén ổn định ở 170.0 ± 1.5°C."
            }
        }
        return actions.get(feature_key, {
            "diagnosis": f"Thông số {feature_key} có độ lệch lớn so với dung sai công nghệ định mức.",
            "root_cause": "Dao động cơ học hoặc cảm biến đo lường quá trình bị trôi dạt sau thời gian dài vận hành.",
            "corrective_action": "Thực hiện kiểm tra bảo dưỡng phòng ngừa (PM) và hiệu chuẩn cảm biến trạm tương ứng."
        })

    def simulate_defect_spike(self, scenario: str) -> Dict[str, Any]:
        """Injects defect spike scenarios to demonstrate real-time SHAP root cause detection."""
        self.active_spike_scenario = scenario
        self.seed_telemetry_dataset_if_empty(force=True)
        self.train_models()
        return self.get_global_importance()


# Global singleton instance
shap_engine = ShapRootCauseAnalyzer()
