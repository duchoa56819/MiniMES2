"""
AI Unsupervised Anomaly Detection Service for Tire Manufacturing MES.
Dual-Engine Architecture:
1. Isolation Forest (Tree-based Path Isolation for high-dimensional tabular outliers)
2. Deep PyTorch Autoencoder (Neural Latent Representation & Reconstruction Error MSE)

Monitors:
- Machine Takt Time (Chu kỳ máy thực tế vs Tiêu chuẩn)
- WIP Queue Dwell Time (Thời gian chờ đệm giữa các công đoạn)
- Micro-stoppages & Hidden Productivity Degradation (Hao hụt công suất ngầm)
"""

import os
import random
import math
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from sklearn.ensemble import IsolationForest
import torch
import torch.nn as nn
import torch.optim as optim

from app.database import get_db, get_read_replica_db


# =============================================================================
# 1. PYTORCH DEEP AUTOENCODER MODEL
# =============================================================================
class TaktDwellAutoencoder(nn.Module):
    """
    Symmetric Deep Autoencoder for Time-Series Process Telemetry.
    Compresses 5-dimensional feature space down to 2-dimensional latent bottleneck,
    then reconstructs. High MSE reconstruction error indicates an abnormal process cycle.
    """
    def __init__(self, input_dim: int = 5, latent_dim: int = 2):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.LeakyReLU(0.2),
            nn.Linear(16, 8),
            nn.LeakyReLU(0.2),
            nn.Linear(8, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 8),
            nn.LeakyReLU(0.2),
            nn.Linear(8, 16),
            nn.LeakyReLU(0.2),
            nn.Linear(16, input_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        x_rec = self.decoder(z)
        return x_rec


# =============================================================================
# 2. CORE AI DETECTOR ENGINE (SINGLETON)
# =============================================================================
class AiAnomalyDetectionEngine:
    def __init__(self):
        self.feature_names = [
            "takt_time_sec",
            "takt_deviation_sec",
            "wip_queue_dwell_min",
            "temp_deviation_c",
            "pressure_deviation_bar"
        ]
        self.input_dim = len(self.feature_names)
        self.iforest = None
        self.autoencoder = None
        self.scaler_min = None
        self.scaler_max = None
        self.ae_threshold = 0.05
        self.is_trained = False
        self.last_trained_at = None
        self.total_samples_trained = 0

        # Auto-train on initialize
        self.train_models()

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        denom = np.where((self.scaler_max - self.scaler_min) == 0, 1.0, (self.scaler_max - self.scaler_min))
        return (x - self.scaler_min) / denom

    def generate_baseline_data(self, n_normal: int = 300, n_anomaly: int = 25) -> np.ndarray:
        """
        Generates realistic industrial baseline time-series training data
        combining TBM cycles, Curing presses, and cooling conveyors.
        """
        np.random.seed(42)
        random.seed(42)

        data = []

        # 1. Normal TBM & Curing Cycles (90% of data)
        for _ in range(n_normal):
            is_curing = random.random() > 0.4
            if is_curing:
                target_takt = 780.0
                actual_takt = np.random.normal(780.5, 3.2)
                takt_dev = actual_takt - target_takt
                wip_dwell = np.random.normal(45.0, 12.0)  # 45 min waiting queue
                temp_dev = np.random.normal(0.0, 0.6)
                press_dev = np.random.normal(0.0, 0.4)
            else:
                target_takt = 45.0
                actual_takt = np.random.normal(45.2, 1.1)
                takt_dev = actual_takt - target_takt
                wip_dwell = np.random.normal(60.0, 15.0)  # Storage rack dwell
                temp_dev = 0.0
                press_dev = 0.0

            data.append([actual_takt, takt_dev, max(5.0, wip_dwell), temp_dev, press_dev])

        # 2. Abnormal Samples (Hidden Micro-stoppages & Buffer Delays)
        for _ in range(n_anomaly):
            anomaly_type = random.choice(["TAKT_CREEP", "WIP_CONGESTION", "THERMAL_CHOKE"])
            if anomaly_type == "TAKT_CREEP":
                # Cycle takes 40-90s longer due to hydraulic valve sticking
                actual_takt = 780.0 + random.uniform(45.0, 95.0)
                takt_dev = actual_takt - 780.0
                wip_dwell = random.uniform(35.0, 60.0)
                temp_dev = random.uniform(-1.2, 1.0)
                press_dev = random.uniform(-1.5, 0.5)
            elif anomaly_type == "WIP_CONGESTION":
                # Tire sat in buffer for 5 to 8 hours!
                actual_takt = 780.0 + random.uniform(-2.0, 4.0)
                takt_dev = actual_takt - 780.0
                wip_dwell = random.uniform(300.0, 480.0)  # 5-8 hours queue
                temp_dev = 0.0
                press_dev = 0.0
            else:
                # Thermal / pressure degradation
                actual_takt = 780.0 + random.uniform(15.0, 35.0)
                takt_dev = actual_takt - 780.0
                wip_dwell = random.uniform(40.0, 80.0)
                temp_dev = random.uniform(-6.5, -3.5)  # Under-temperature!
                press_dev = random.uniform(-4.0, -2.0)  # Bladder leak!

            data.append([actual_takt, takt_dev, wip_dwell, temp_dev, press_dev])

        return np.array(data, dtype=np.float32)

    def train_models(self):
        """Trains Isolation Forest and PyTorch Deep Autoencoder."""
        raw_data = self.generate_baseline_data()
        self.scaler_min = np.min(raw_data, axis=0)
        self.scaler_max = np.max(raw_data, axis=0)

        norm_data = self._normalize(raw_data)

        # 1. Train Isolation Forest
        self.iforest = IsolationForest(
            n_estimators=100,
            contamination=0.08,
            random_state=42,
            n_jobs=-1
        )
        self.iforest.fit(norm_data)

        # 2. Train PyTorch Deep Autoencoder
        torch.manual_seed(42)
        self.autoencoder = TaktDwellAutoencoder(input_dim=self.input_dim, latent_dim=2)
        optimizer = optim.Adam(self.autoencoder.parameters(), lr=0.01, weight_decay=1e-5)
        criterion = nn.MSELoss()

        tensor_data = torch.tensor(norm_data, dtype=torch.float32)

        self.autoencoder.train()
        for epoch in range(40):
            optimizer.zero_grad()
            reconstructed = self.autoencoder(tensor_data)
            loss = criterion(reconstructed, tensor_data)
            loss.backward()
            optimizer.step()

        # Compute AE threshold (95th percentile of baseline normal losses)
        self.autoencoder.eval()
        with torch.no_grad():
            train_rec = self.autoencoder(tensor_data)
            losses = torch.mean((tensor_data - train_rec) ** 2, dim=1).numpy()
            self.ae_threshold = float(np.percentile(losses, 92))

        self.is_trained = True
        self.last_trained_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.total_samples_trained = len(raw_data)

    def evaluate_vector(self, raw_features: List[float]) -> Dict[str, Any]:
        """
        Runs inference on a single 5-dimensional feature vector.
        Combines Isolation Forest decision score with Autoencoder Reconstruction MSE.
        """
        arr = np.array([raw_features], dtype=np.float32)
        norm_arr = self._normalize(arr)

        # 1. Isolation Forest Score
        # decision_function gives negative for outliers, positive for inliers
        # Map to [0, 1] where 1.0 is highest anomaly
        raw_if_score = self.iforest.decision_function(norm_arr)[0]
        # raw_if_score typically in [-0.5, 0.5]
        if_anomaly_score = float(1.0 / (1.0 + math.exp(raw_if_score * 8.0)))

        # 2. Autoencoder Reconstruction Loss
        self.autoencoder.eval()
        with torch.no_grad():
            tensor_in = torch.tensor(norm_arr, dtype=torch.float32)
            tensor_rec = self.autoencoder(tensor_in)
            mse_loss = float(torch.mean((tensor_in - tensor_rec) ** 2).item())

        # Scale AE score
        ae_anomaly_score = min(1.0, mse_loss / (self.ae_threshold * 1.8))

        # Ensemble Score
        ensemble_score = round(0.5 * if_anomaly_score + 0.5 * ae_anomaly_score, 3)

        # Severity Classification
        if ensemble_score >= 0.70:
            severity = "CRITICAL"
        elif ensemble_score >= 0.50:
            severity = "WARNING"
        else:
            severity = "INFO"

        # AI Root Cause Diagnosis
        actual_takt = raw_features[0]
        takt_dev = raw_features[1]
        wip_dwell = raw_features[2]
        temp_dev = raw_features[3]
        press_dev = raw_features[4]

        diagnosis = []
        action = []

        if takt_dev > 30.0:
            diagnosis.append(f"Chu kỳ máy kéo dài bất thường (+{round(takt_dev, 1)}s so với chuẩn). Dấu hiệu suy giảm thủy lực/van xả.")
            action.append("Kiểm tra áp lực dầu trạm bơm thủy lực và vệ sinh van xả chân không lò ép.")
        if wip_dwell > 180.0:
            diagnosis.append(f"Thời gian chờ đệm WIP quá ngưỡng ({round(wip_dwell, 1)} phút > 180 phút). Nguy cơ khô bề mặt cao su hoặc nghẽn băng tải.")
            action.append("Điều phối xe AGV giải tỏa giá đệm lốp sống hoặc tăng nhịp độ nạp lò lưu hóa.")
        elif wip_dwell < 15.0 and actual_takt > 100.0:
            diagnosis.append("Thời gian làm nguội lốp trước khi soi X-Ray quá ngắn (< 15 phút). Cao su chưa ổn định ứng suất.")
            action.append("Hãm nhịp nạp băng chuyền làm nguội trước khi đưa vào mâm xoay KCS.")
        if temp_dev < -2.5:
            diagnosis.append(f"Tụt nhiệt độ khuôn ({round(temp_dev, 1)}°C). Nguy cơ cao su chín không đều (Under-cure).")
            action.append("Kiểm tra bẫy hơi nước ngưng (Steam Trap) và đường ống cấp nhiệt bản mặt.")
        if press_dev < -1.8:
            diagnosis.append(f"Sụt áp suất bóng ép bàng lưu hóa ({round(press_dev, 1)} bar). Rò rỉ khí bàng.")
            action.append("Thực hiện kiểm tra bàng lưu hóa và gioăng làm kín hộc khuôn.")

        if not diagnosis:
            diag_str = "Chu kỳ hoạt động ổn định, năng suất đạt chuẩn kỹ thuật (Normal Operating Range)."
            action_str = "Duy trì chế độ vận hành tự động theo kế hoạch sản xuất."
        else:
            diag_str = " | ".join(diagnosis)
            action_str = " | ".join(action)

        return {
            "ensemble_anomaly_score": ensemble_score,
            "isolation_forest_score": round(if_anomaly_score, 3),
            "autoencoder_mse_loss": round(mse_loss, 4),
            "autoencoder_score": round(ae_anomaly_score, 3),
            "ae_threshold": round(self.ae_threshold, 4),
            "is_anomaly": ensemble_score >= 0.50,
            "severity": severity,
            "root_cause_diagnosis": diag_str,
            "mitigation_action": action_str,
            "metrics": {
                "actual_takt_sec": round(actual_takt, 1),
                "takt_deviation_sec": round(takt_dev, 1),
                "wip_queue_dwell_min": round(wip_dwell, 1),
                "temp_deviation_c": round(temp_dev, 1),
                "pressure_deviation_bar": round(press_dev, 1)
            }
        }

    def seed_initial_telemetry_cycles(self):
        """Populates production_cycle_telemetry with realistic historical cycles if empty."""
        with get_db(immediate=True) as conn:
            cursor = conn.cursor()
            count = cursor.execute("SELECT count(*) FROM production_cycle_telemetry").fetchone()[0]
            if count >= 30:
                return

            now = datetime.now()
            machines = [
                ("TBM-01", "TBM_BUILD", 45.0, "PCR-205-55R16-91V"),
                ("TBM-02", "TBM_BUILD", 90.0, "TBR-315-80R22.5-156K"),
                ("CP-01", "CURING_CYCLE", 780.0, "PCR-205-55R16-91V"),
                ("CP-02", "CURING_CYCLE", 780.0, "PCR-205-55R16-91V"),
                ("CP-03", "CURING_CYCLE", 840.0, "PCR-225-60R17-99H"),
                ("CP-04", "CURING_CYCLE", 2400.0, "TBR-315-80R22.5-156K"),
            ]

            rows_to_insert = []
            for i in range(45):
                m_id, c_type, tgt_takt, sku = random.choice(machines)
                t_stamp = (now - timedelta(minutes=45 * 5 - i * 5)).strftime("%Y-%m-%d %H:%M:%S")

                # Inject 4 realistic anomalies into the history
                if i in (12, 23):
                    # Hydraulic valve lag anomaly on CP-02
                    actual_takt = tgt_takt + random.uniform(55.0, 85.0)
                    takt_dev = actual_takt - tgt_takt
                    wip_dwell = random.uniform(40.0, 70.0)
                    t_dev = -1.2
                    p_dev = -0.5
                elif i in (18, 37):
                    # WIP Queue buffer delay on TBM-01 / Buffer
                    actual_takt = tgt_takt + random.uniform(-1.0, 3.0)
                    takt_dev = actual_takt - tgt_takt
                    wip_dwell = random.uniform(280.0, 360.0)  # > 4.5 hours!
                    t_dev = 0.0
                    p_dev = 0.0
                else:
                    # Normal cycle
                    actual_takt = tgt_takt + np.random.normal(0.8, 1.5)
                    takt_dev = actual_takt - tgt_takt
                    wip_dwell = random.uniform(30.0, 90.0)
                    t_dev = np.random.normal(0.0, 0.4)
                    p_dev = np.random.normal(0.0, 0.3)

                rows_to_insert.append((
                    t_stamp, m_id, c_type, sku, round(actual_takt, 1),
                    tgt_takt, round(takt_dev, 1), round(wip_dwell, 1),
                    round(t_dev, 1), round(p_dev, 1)
                ))

            cursor.executemany("""
                INSERT INTO production_cycle_telemetry (
                    timestamp, machine_id, cycle_type, sku,
                    actual_takt_sec, target_takt_sec, takt_deviation_sec,
                    wip_queue_dwell_min, temp_deviation_c, pressure_deviation_bar
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows_to_insert)

    def scan_all_cycles(self) -> List[Dict[str, Any]]:
        """
        Runs comprehensive unsupervised scan across all machines,
        detecting subtle productivity degradation.
        Logs anomalies into ai_anomaly_logs table.
        """
        self.seed_initial_telemetry_cycles()

        with get_read_replica_db() as ro_conn:
            cursor = ro_conn.cursor()
            rows = cursor.execute("""
                SELECT * FROM production_cycle_telemetry
                ORDER BY timestamp DESC LIMIT 50
            """).fetchall()

        results = []
        anomalies_to_record = []

        for r in rows:
            feat_vector = [
                r["actual_takt_sec"],
                r["takt_deviation_sec"],
                r["wip_queue_dwell_min"],
                r["temp_deviation_c"],
                r["pressure_deviation_bar"]
            ]
            eval_res = self.evaluate_vector(feat_vector)
            eval_res["id"] = r["id"]
            eval_res["timestamp"] = r["timestamp"]
            eval_res["machine_id"] = r["machine_id"]
            eval_res["cycle_type"] = r["cycle_type"]
            eval_res["sku"] = r["sku"]

            results.append(eval_res)

            if eval_res["is_anomaly"]:
                anomalies_to_record.append((
                    r["timestamp"], r["machine_id"], "MACHINE", "ENSEMBLE",
                    r["actual_takt_sec"], r["wip_queue_dwell_min"],
                    eval_res["ensemble_anomaly_score"], eval_res["severity"],
                    eval_res["root_cause_diagnosis"], eval_res["mitigation_action"]
                ))

        # Store detected anomalies if not already present
        if anomalies_to_record:
            with get_db(immediate=True) as conn:
                cur = conn.cursor()
                for item in anomalies_to_record:
                    # check if already logged
                    exists = cur.execute("""
                        SELECT 1 FROM ai_anomaly_logs
                        WHERE timestamp = ? AND entity_id = ?
                    """, (item[0], item[1])).fetchone()
                    if not exists:
                        cur.execute("""
                            INSERT INTO ai_anomaly_logs (
                                timestamp, entity_id, entity_type, model_type,
                                takt_time_sec, wip_queue_time_min, anomaly_score,
                                severity, root_cause_diagnosis, mitigation_action, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DETECTED')
                        """, item)

        return results


# Global singleton instance
ai_engine = AiAnomalyDetectionEngine()
