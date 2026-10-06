# Thiết Kế Kiến Trúc Cơ Sở Dữ Liệu TIRE-MES (Database Architecture & Modular ER Diagrams)

> **Tiêu chuẩn áp dụng:** ANSI/ISA-95 Level 3 (MOM / MES), MESA-11, IATF 16949 Section 8.5.2 & Section 8.7.  
> **Động cơ CSDL:** SQLite 3 Engine hiệu năng cao (Chế độ WAL, Busy Timeout 60s, Phân tách Read-Replica chỉ đọc).

---

## 1. Sơ Đồ Dòng Chảy Kiến Trúc Mức Cao (Level 0: High-Level Architecture Flowchart)

Thay vì nhìn vào một sơ đồ mạng nhện rối rắm, sơ đồ phân tầng dưới đây mô tả trực quan **luồng vận hành tổng thể** kết nối 27 bảng dữ liệu thành 5 khối chức năng liền mạch:

```mermaid
flowchart TD
    subgraph S1 ["🏭 1. MASTER DATA & ĐỊNH MỨC"]
        direction TB
        MA["Khu Vực Sản Xuất<br/><code>master_areas</code>"]
        ME["Thiết Bị & Máy Móc<br/><code>master_equipment</code>"]
        MP["Quy Cách Lốp SKU<br/><code>master_products</code>"]
        MB["Định Mức Vật Liệu<br/><code>master_boms</code>"]
        MR["Công Thức Lưu Hóa<br/><code>master_curing_recipes</code>"]
        MO["Ma Trận Thợ Vận Hành<br/><code>master_operators</code>"]
        
        MA --> ME
        MP --> MB
        MP --> MR
    end

    subgraph S2 ["📦 2. KHO BTP & ĐIỀU ĐỘ"]
        direction TB
        IC["Lô Bán Thành Phẩm<br/><code>inventory_components</code><br/><i>(Hạn dùng Shelf-life)</i>"]
        WO["Lệnh Sản Xuất ERP<br/><code>work_orders</code>"]
    end

    subgraph S3 ["⚙️ 3. VẬN HÀNH SHOP FLOOR & PHẢ HỆ LỐP"]
        direction TB
        PGT["Lốp Mộc Green Tire<br/><code>production_green_tires</code><br/><i>(Barcode GT-..., 7 Lô BTP)</i>"]
        CPC["Hốc Khuôn Lưu Hóa L/R<br/><code>curing_press_cavities</code>"]
        PCT["Lốp Chín Cured Tire<br/><code>production_cured_tires</code><br/><i>(Số Serial VN-T-...)</i>"]
        
        PGT -->|"Nạp khuôn"| CPC
        CPC -->|"Dỡ lốp chín"| PCT
    end

    subgraph S4 ["🔍 4. KCS, SỬA HÀNG & IIOT"]
        direction TB
        QI["Kiểm Định KCS Đa Trạm<br/><code>quality_inspections</code><br/><i>(Grade A, B, Rework, Scrap)</i>"]
        TRH["Nhật Ký Sửa Chữa<br/><code>tire_rework_history</code><br/><i>(Anti-Loop Max 2 lần)</i>"]
        GW["Cổng Giao Thức IIoT<br/><code>gateway_connectors</code><br/><i>(OPC-UA, Modbus, MQTT)</i>"]
        
        QI -->|"Khuyết tật"| TRH
    end

    subgraph S5 ["🧠 5. HỆ SINH THÁI AI CÔNG NGHIỆP"]
        direction TB
        AI1["AI 1: Bất Thường Takt Time<br/><code>ai_anomaly_logs</code>"]
        AI2["AI 2: Dự Báo Cổ Chai 2-4h<br/><code>bottleneck_forecasts</code> & <code>rules</code>"]
        AI3["AI 3: Căn Nguyên Lỗi SHAP<br/><code>batch_process_telemetry</code> & <code>reports</code>"]
        AI4["AI 4: Lan Truyền Đồ Thị GNN<br/><code>graph_edges</code>, <code>runs</code> & <code>scores</code>"]
    end

    %% LIÊN KẾT LIÊN KHỐI
    ME -->|"Giao máy"| WO
    MP -->|"Đặt hàng"| WO
    WO -->|"Cấp phát"| PGT
    IC -->|"Quét Poka-Yoke"| PGT
    ME -->|"Thành hình"| PGT
    ME -->|"Nướng lốp"| CPC
    PCT -->|"Kiểm tra"| QI
    ME -.->|"Telemetry chu kỳ"| S5
    PCT -.->|"19 biến telemetry"| AI3
    IC -.->|"Đồ thị phả hệ"| AI4
    WO -.->|"Dự báo lây lan"| AI4

    classDef masterStyle fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef invStyle fill:#1e293b,stroke:#fbbf24,stroke-width:1.5px,color:#fff;
    classDef prodStyle fill:#1e293b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef qcStyle fill:#1e293b,stroke:#f87171,stroke-width:1.5px,color:#fff;
    classDef aiStyle fill:#1e293b,stroke:#c084fc,stroke-width:1.5px,color:#fff;

    class MA,ME,MP,MB,MR,MO masterStyle;
    class IC,WO invStyle;
    class PGT,CPC,PCT prodStyle;
    class QI,TRH,GW qcStyle;
    class AI1,AI2,AI3,AI4 aiStyle;
```

---

## 2. Các Sơ Đồ ER Phân Hệ Chuyên Biệt (Level 1: Modular Domain ERDs)

Nhằm giúp kỹ sư dễ dàng quan sát, phân tích và truy vấn, 27 bảng dữ liệu được tách thành **4 sơ đồ thực thể độc lập** theo từng miền nghiệp vụ:

### Phân Hệ A: Master Data, Sản Phẩm & Định Mức Kỹ Thuật (BOM & Recipes)
Tập trung vào dữ liệu tĩnh, cấu trúc thiết bị và công nghệ sản xuất:

```mermaid
erDiagram
    master_areas ||--o{ master_equipment : "phân_vùng"
    master_products ||--o{ master_boms : "định_mức_vật_tư"
    master_products ||--o| master_curing_recipes : "công_thức_lưu_hóa"
    master_equipment ||--o{ equipment_downtime_logs : "ghi_nhận_dừng_máy"

    master_areas {
        string area_code PK "Mã khu vực (MIXING, PREP, TBM, CURING, FINISHING)"
        string area_name "Tên phân xưởng"
        int sequence_order "Thứ tự công đoạn"
    }

    master_equipment {
        string machine_id PK "Mã máy (TBM-01, CP-01...)"
        string machine_name "Tên thiết bị"
        string area_code FK "Khu vực trực thuộc"
        string status "RUNNING, IDLE, BREAKDOWN, MAINTENANCE"
        int target_cycle_time_sec "Takt time chuẩn (giây)"
        float oee_target "Mục tiêu OEE (%)"
    }

    master_products {
        string sku PK "Mã quy cách lốp (PCR-205-55R16-91V...)"
        string tire_size "Quy cách kích cỡ"
        string pattern_name "Mẫu hoa gai"
        string segment "PCR, TBR, EV, OTR"
        float standard_weight_kg "Trọng lượng danh định (kg)"
        float std_cure_temp_c "Nhiệt độ lưu hóa chuẩn (°C)"
        float std_bladder_press_bar "Áp suất bàng ép chuẩn (bar)"
    }

    master_boms {
        int id PK "ID tự tăng"
        string sku FK "Mã lốp liên kết"
        string component_type "TREAD, SIDEWALL, BELT_1/2, PLY, BEAD, INNERLINER"
        string spec_code "Mã quy cách BTP"
        string compound_code "Mã hợp phần cao su"
        float standard_qty "Định mức tiêu hao (kg)"
    }

    master_curing_recipes {
        string recipe_id PK "Mã công thức lưu hóa"
        string sku FK "Mã SKU duy nhất"
        int cure_time_sec "Thời gian lưu hóa (giây)"
        float mold_temp_target_c "Nhiệt độ khuôn setpoint (°C)"
        float bladder_press_bar "Áp suất bàng nén (bar)"
        int max_bladder_cycles "Tuổi thọ bàng tối đa"
    }

    master_operators {
        string badge_id PK "Mã thẻ nhân viên"
        string full_name "Họ và tên"
        string role "TBM_OPERATOR, CURING_TECH, QC_INSPECTOR, SUPERVISOR"
        string current_shift "Ca làm việc (SHIFT_A, B, C)"
        int skill_level "Bậc tay nghề (1 đến 5)"
    }
```

---

### Phân Hệ B: Dòng Chảy Vận Hành Sản Xuất & Phả Hệ Lốp (Core Lineage & Digital Tire Passport)
**Đây là xương sống quan trọng nhất của hệ thống MES**, quản lý việc biến 7 lô nguyên liệu thành lốp mộc và khắc số serial vĩnh viễn:

```mermaid
erDiagram
    work_orders ||--o{ production_green_tires : "chế_tạo_theo_lệnh"
    inventory_components ||--o{ production_green_tires : "tiêu_thụ_poka_yoke"
    master_equipment ||--o{ production_green_tires : "đóng_trên_máy_tbm"
    master_equipment ||--o{ curing_press_cavities : "chứa_hốc_khuôn"
    production_green_tires ||--o| production_cured_tires : "nướng_chín_thành"
    master_equipment ||--o{ production_cured_tires : "lưu_hóa_tại_lò"

    inventory_components {
        string lot_id PK "Mã lô BTP (LOT-TRD-202610-01...)"
        string component_type "Loại linh kiện"
        string compound_code "Mã cao su"
        string expiry_time "Hạn dùng Poka-Yoke (48-72h)"
        string status "AVAILABLE, EXPIRED, QUARANTINE"
        string raw_batch_ref "Mã mẻ Banbury gốc"
    }

    work_orders {
        string wo_id PK "Mã lệnh sản xuất (WO-2026-001...)"
        string sku FK "Mã sản phẩm"
        int target_qty "Sản lượng kế hoạch"
        int completed_qty "Đã hoàn thành"
        string status "RELEASED, IN_PROGRESS, COMPLETED, PAUSED"
        string assigned_machine "Máy được giao"
    }

    production_green_tires {
        string gt_barcode PK "Mã vạch lốp mộc duy nhất"
        string wo_id FK "Lệnh sản xuất"
        string sku FK "Quy cách lốp"
        string tbm_machine_id FK "Máy đóng lốp TBM"
        float actual_weight_kg "Cân nặng thực tế"
        string tread_lot "Lô mặt lốp"
        string sidewall_lot "Lô hông lốp"
        string belt1_lot "Lô mành đai 1"
        string bead_lot "Lô tanh thép"
        string poka_yoke_status "VERIFIED_PASS, OVERRIDDEN"
        string status "BUILT, BUFFER, CURED, QUARANTINED"
    }

    curing_press_cavities {
        string press_id PK "Mã máy lưu hóa (CP-01..04)"
        string cavity_side PK "Hốc Trái (L) hoặc Phải (R)"
        string mold_id "Mã khuôn ép"
        string current_gt_barcode "Mã lốp đang trong khuôn"
        string state "EMPTY, LOADED, CURING, COMPLETED"
        float mold_temp_c "Nhiệt độ khuôn thực thời"
        float bladder_press_bar "Áp suất bàng thực thời"
    }

    production_cured_tires {
        string tire_serial PK "Số Sê-ri vĩnh viễn (VN-T-...)"
        string gt_barcode FK "Mã lốp mộc gốc"
        string sku FK "Quy cách lốp"
        string press_id FK "Lò lưu hóa"
        string cavity_side "Hốc ép (L/R)"
        int actual_cure_sec "Thời gian nướng thực tế"
        string cure_quality_result "PASS, TEMP_DROP, PRESSURE_DROP"
        string status "CURED, INSPECTED, SCRAPPED, QUARANTINED"
    }
```

---

### Phân Hệ C: Kiểm Soát Chất Lượng KCS, Sửa Hàng & IIoT Gateway
Đảm bảo chất lượng xuất xưởng theo chuẩn IATF 16949 và kết nối tự động hóa:

```mermaid
erDiagram
    production_cured_tires ||--o| quality_inspections : "kiểm_định_kcs"
    master_defect_codes ||--o{ quality_inspections : "phân_loại_lỗi"
    production_cured_tires ||--o{ tire_rework_history : "sửa_hàng"
    master_equipment ||--o{ production_cycle_telemetry : "thu_thập_chu_kỳ"
    gateway_connectors ||--o{ master_equipment : "kết_nối_plc"

    quality_inspections {
        int inspection_id PK "ID kiểm định tự tăng"
        string tire_serial FK "Số sê-ri lốp kiểm tra"
        string visual_result "Ngoại quan (PASS/FAIL)"
        string visual_defect_code FK "Mã lỗi ngoại quan"
        string xray_result "Soi X-Ray (PASS/FAIL)"
        string xray_defect_code FK "Mã lỗi mành thép"
        float uniformity_rfv_n "Lực biến thiên hướng kính RFV (N)"
        float dynamic_balance_g "Mất cân bằng động (g)"
        string final_grade "GRADE_A, GRADE_B, REWORK, SCRAP"
        int passed "Cờ đạt chuẩn xuất kho (1/0)"
    }

    tire_rework_history {
        int rework_id PK "ID sửa chữa"
        string tire_serial FK "Số sê-ri lốp sửa"
        string action_type "Cắt bavia, Mài cân bằng, Chấm tanh"
        int rework_count "Lần sửa (Khóa Anti-Loop tối đa 2 lần)"
        string notes "Ghi chú kỹ thuật sửa"
    }

    master_defect_codes {
        string defect_code PK "Mã lỗi (DEF-VIS-01...)"
        string defect_name_vi "Tên lỗi tiếng Việt"
        string defect_name_en "Tên lỗi tiếng Anh"
        string inspection_station "VISUAL, XRAY, UNIFORMITY"
        string severity "MINOR, MAJOR, CRITICAL"
        string default_disposition "REWORK, GRADE_B, SCRAP"
    }

    gateway_connectors {
        string connector_id PK "Mã kết nối (OPCUA-TBM-01...)"
        string protocol_type "OPC_UA, OPC_DA, MODBUS_TCP, MQTT"
        string target_ip "Địa chỉ IP PLC"
        float ping_latency_ms "Độ trễ truyền thông (ms)"
        string status "CONNECTED, DEGRADED, DISCONNECTED"
    }

    production_cycle_telemetry {
        int id PK "ID tự tăng"
        string machine_id "Mã máy"
        float cycle_time_sec "Takt time chu kỳ (giây)"
        float queue_time_sec "Thời gian chờ đệm hàng WIP"
        string status "COMPLETED, SCRAP, REWORK"
    }
```

---

### Phân Hệ D: Hệ Sinh Thái Trí Tuệ Nhân Tạo (Industrial AI Ecosystem)
Bộ tứ động cơ AI bảo vệ toàn diện năng suất, chất lượng và phả hệ nhà máy:

```mermaid
erDiagram
    master_equipment ||--o{ ai_anomaly_logs : "phát_hiện_bất_thường"
    master_equipment ||--o{ bottleneck_forecasts : "dự_báo_nghẽn"
    master_equipment ||--o{ dynamic_routing_rules : "điều_hướng_dòng_chảy"
    production_cured_tires ||--o{ batch_process_telemetry : "vector_thông_số_mẻ"
    batch_process_telemetry ||--o{ shap_root_cause_reports : "bóc_tách_căn_nguyên"
    graph_risk_propagation_runs ||--o{ graph_order_risk_scores : "đánh_giá_rủi_ro_lệnh"
    work_orders ||--o{ graph_order_risk_scores : "chịu_ảnh_hưởng"

    ai_anomaly_logs {
        int id PK "ID phát hiện"
        string machine_id "Máy phát sinh sự cố"
        float takt_deviation_pct "Độ lệch Takt time (%)"
        float wip_queue_time "Thời gian nghẽn đệm (giây)"
        float anomaly_score "Điểm bất thường [0.0 - 1.0]"
        string severity "NORMAL, WARNING, CRITICAL"
        string detection_source "ISOLATION_FOREST, AUTOENCODER"
        string root_cause_hint "Gợi ý nguyên nhân kỹ thuật"
    }

    bottleneck_forecasts {
        int id PK "ID dự báo"
        string current_bottleneck "Trạm nghẽn hiện tại"
        string predicted_station_2h "Dự báo trạm nghẽn sau 2 giờ"
        string predicted_station_4h "Dự báo trạm nghẽn sau 4 giờ"
        float confidence_score "Độ tin cậy mô hình"
        int auto_reroute_triggered "Trạng thái tự động san tải"
    }

    dynamic_routing_rules {
        string rule_id PK "Mã luật điều hướng"
        string source_station "Trạm nguồn phát sinh"
        string baseline_destination "Tuyến đích chuẩn SOP"
        string alternate_destination "Tuyến thay thế khi nghẽn"
        float current_divert_ratio "Tỷ lệ san tải chuyển hướng (%)"
        int is_active "Trạng thái kích hoạt (1/0)"
    }

    batch_process_telemetry {
        int id PK "ID mẻ telemetry"
        string batch_id "Mã mẻ luyện/lưu hóa"
        string green_tire_id "Mã lốp mộc"
        string tire_serial "Mã serial lốp chín"
        float mooney_viscosity_ml "Độ nhớt Mooney ML(1+4)"
        float scorch_time_ts2_min "Thời gian cháy sớm ts2"
        float dump_temp_c "Nhiệt độ xuất cao su (°C)"
        float cord_tension_n "Lực căng mành thép (N)"
        float internal_bladder_press_bar "Áp suất bàng nén (bar)"
        int is_defective "Cờ phế phẩm (1/0)"
        string defect_code "Mã lỗi phát sinh"
    }

    shap_root_cause_reports {
        int id PK "ID báo cáo XAI"
        string defect_spike_category "Danh mục đột biến lỗi"
        string top_root_cause_feature "Yếu tố căn nguyên số 1"
        float top_root_cause_importance "Tầm quan trọng SHAP (%)"
        string global_importance_json "Xếp hạng 19 thông số"
        string decision_rules_json "Luật cây quyết định If-Then"
        string corrective_action_recommendation "Hành động CAPA IATF 16949"
    }

    graph_risk_propagation_runs {
        string run_id PK "Mã phiên phân tích đồ thị"
        string suspect_node_id "Lô linh kiện nghi vấn ổ dịch"
        string algorithm "ENSEMBLE_PYTORCH_GNN_AND_RWR"
        int critical_wos_count "Số đơn hàng nguy cấp (CRITICAL)"
        int total_tires_at_risk "Tổng số lốp bị đe dọa (Blast Radius)"
        int quarantine_applied "Đã phát lệnh cách ly (1/0)"
    }

    graph_order_risk_scores {
        int id PK "ID điểm rủi ro"
        string run_id FK "Phiên phân tích liên kết"
        string wo_id "Mã lệnh sản xuất"
        float risk_score "Xác suất lây nhiễm [0.0 - 1.0]"
        string risk_tier "CRITICAL, HIGH, MEDIUM, LOW"
        string primary_transmission_vector "Vectơ lây (DIRECT, SHARED_MACHINE)"
        string shortest_infection_path "Chuỗi truyền bệnh ngắn nhất"
        string recommended_action "STOP_WORK, 100%_NDT, AQL"
    }
```

---

## 3. Ma Trận Tra Cứu Liên Kết Khóa Ngoại 1 Phút (Quick Reference Matrix)

| Bảng Nguồn (Chứa Khóa Ngoại) | Cột Khóa Ngoại (FK) | Bảng Đích (Khóa Chính PK) | Mối Quan Hệ Nghiệp Vụ Thực Tế |
| :--- | :--- | :--- | :--- |
| `master_equipment` | `area_code` | `master_areas(area_code)` | Máy móc thuộc phân xưởng sản xuất nào (Mixing, TBM, Curing...) |
| `master_boms` | `sku` | `master_products(sku)` | Định mức 7 linh kiện cấu thành nên quy cách lốp |
| `master_curing_recipes` | `sku` | `master_products(sku)` | Công thức nhiệt, áp, thời gian lưu hóa riêng cho từng mã lốp |
| `work_orders` | `sku` | `master_products(sku)` | Đơn hàng chỉ định sản xuất loại lốp nào |
| `production_green_tires` | `wo_id` | `work_orders(wo_id)` | Lốp mộc được lắp ráp thuộc lệnh sản xuất nào |
| `production_green_tires` | `sku` | `master_products(sku)` | Quy cách kỹ thuật lốp mộc |
| `production_green_tires` | `tbm_machine_id` | `master_equipment(machine_id)` | Đóng trên máy thành hình TBM nào (VMI MAXX) |
| `production_green_tires` | `operator_id` | `master_operators(badge_id)` | Thợ thành hình chịu trách nhiệm tay nghề |
| `curing_press_cavities` | `press_id` | `master_equipment(machine_id)` | Hốc khuôn Trái/Phải thuộc cụm lò lưu hóa nào |
| `production_cured_tires` | `gt_barcode` | `production_green_tires(gt_barcode)` | **Khóa phả hệ 100%**: Lốp chín ra lò từ chiếc lốp mộc nào |
| `production_cured_tires` | `press_id` | `master_equipment(machine_id)` | Lò lưu hóa thực hiện nướng chín |
| `quality_inspections` | `tire_serial` | `production_cured_tires(tire_serial)` | Kết quả KCS thuộc về số sê-ri lốp duy nhất nào |
| `quality_inspections` | `visual_defect_code` | `master_defect_codes(defect_code)` | Mã lỗi ngoại quan theo thư viện tiêu chuẩn |
| `quality_inspections` | `xray_defect_code` | `master_defect_codes(defect_code)` | Mã lỗi soi mành thép X-Ray |
| `quality_inspections` | `inspector_id` | `master_operators(badge_id)` | KCS viên ký duyệt chất lượng |
| `tire_rework_history` | `tire_serial` | `production_cured_tires(tire_serial)` | Lốp nào đang được đưa vào luồng sửa chữa |
| `equipment_downtime_logs` | `machine_id` | `master_equipment(machine_id)` | Ghi nhận thời gian dừng máy tính toán OEE |
| `graph_order_risk_scores` | `run_id` | `graph_risk_propagation_runs(run_id)` | Điểm rủi ro lây lan thuộc phiên quét AI nào |

---

## 4. Từ Điển Dữ Liệu Chi Tiết 27 Bảng (Thu Gọn Tiện Tra Cứu)

<details>
<summary>▶ Bấm để mở Từ Điển Dữ Liệu Chi Tiết Của Toàn Bộ 27 Bảng</summary>

### 1. Bảng `master_areas`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `area_code` | TEXT | PRIMARY KEY | Mã khu vực (MIXING, PREP, TBM, CURING, FINISHING, WAREHOUSE) |
| `area_name` | TEXT | NOT NULL | Tên phân xưởng hiển thị |
| `description` | TEXT | NULL | Chức năng công nghệ |
| `sequence_order` | INTEGER | NOT NULL | Thứ tự công đoạn trong luồng sản xuất ISA-95 |

### 2. Bảng `master_equipment`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `machine_id` | TEXT | PRIMARY KEY | Mã định danh thiết bị (TBM-01, CP-01, MIX-01...) |
| `machine_name` | TEXT | NOT NULL | Tên máy móc |
| `area_code` | TEXT | FK -> master_areas | Khu vực trực thuộc |
| `status` | TEXT | CHECK IN (...) | Trạng thái: RUNNING, IDLE, BREAKDOWN, CHANGEOVER, MAINTENANCE |
| `cavities_count` | INTEGER | DEFAULT 1 | Số hốc ép (1 hoặc 2) |
| `target_cycle_time_sec`| INTEGER | DEFAULT 60 | Takt time chuẩn (giây) |
| `oee_target` | REAL | DEFAULT 85.0 | Mục tiêu OEE (%) |

### 3. Bảng `master_products`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `sku` | TEXT | PRIMARY KEY | Mã sản phẩm duy nhất (PCR-205-55R16-91V...) |
| `tire_size` | TEXT | NOT NULL | Quy cách kích cỡ lốp xe |
| `pattern_name` | TEXT | NOT NULL | Tên mẫu gai lốp |
| `segment` | TEXT | CHECK IN (...) | Phân khúc: PCR, TBR, EV, OTR |
| `standard_weight_kg` | REAL | NOT NULL | Trọng lượng tiêu chuẩn (kg) |
| `weight_tolerance_kg`| REAL | DEFAULT 0.25 | Dung sai trọng lượng cho phép (+/- kg) |
| `std_cure_temp_c` | REAL | DEFAULT 170.0 | Nhiệt độ lưu hóa danh định (°C) |
| `std_bladder_press_bar`| REAL | DEFAULT 21.0 | Áp suất bàng lưu hóa danh định (bar) |

### 4. Bảng `inventory_components`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `lot_id` | TEXT | PRIMARY KEY | Mã vạch lô bán thành phẩm (LOT-TRD-202610-01...) |
| `component_type` | TEXT | CHECK IN (...) | TREAD, SIDEWALL, BELT_1/2, PLY, BEAD, INNERLINER |
| `compound_code` | TEXT | NOT NULL | Mã hỗn luyện cao su |
| `produced_time` | TEXT | NOT NULL | Thời điểm xuất xưởng BTP |
| `expiry_time` | TEXT | NOT NULL | **Hạn dùng Poka-Yoke (Shelf-life 48-72h)** |
| `remaining_qty` | INTEGER | DEFAULT 50 | Số lượng cuộn/khay còn trong kho sàn |
| `status` | TEXT | CHECK IN (...) | AVAILABLE, RESERVED, EXPIRED, DEPLETED, QUARANTINE |
| `raw_batch_ref` | TEXT | NOT NULL | Mã mẻ luyện kín Banbury gốc phục vụ truy xuất ngược |

### 5. Bảng `work_orders`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `wo_id` | TEXT | PRIMARY KEY | Mã lệnh sản xuất (WO-2026-001...) |
| `sku` | TEXT | FK -> master_products | Quy cách lốp cần đóng |
| `target_qty` | INTEGER | NOT NULL | Sản lượng mục tiêu |
| `completed_qty` | INTEGER | DEFAULT 0 | Sản lượng hoàn thành |
| `scrap_qty` | INTEGER | DEFAULT 0 | Số lốp phế phẩm |
| `status` | TEXT | CHECK IN (...) | PLANNED, RELEASED, IN_PROGRESS, COMPLETED, PAUSED |
| `assigned_machine` | TEXT | NULL | Máy đóng lốp được phân bổ (TBM-01, TBM-02) |

### 6. Bảng `production_green_tires`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `gt_barcode` | TEXT | PRIMARY KEY | Mã vạch lốp mộc duy nhất (GT-YYYYMMDD-XXXX) |
| `wo_id` | TEXT | FK -> work_orders | Lệnh sản xuất trực thuộc |
| `sku` | TEXT | FK -> master_products | Mã quy cách lốp |
| `tbm_machine_id` | TEXT | FK -> master_equipment | Máy thành hình TBM |
| `operator_id` | TEXT | FK -> master_operators | Thợ đóng lốp |
| `actual_weight_kg` | REAL | NOT NULL | Khối lượng cân thực tế |
| `tread_lot` | TEXT | NOT NULL | Lô mặt lốp quét Poka-Yoke |
| `sidewall_lot` | TEXT | NOT NULL | Lô hông lốp quét Poka-Yoke |
| `belt1_lot` | TEXT | NOT NULL | Lô mành đai 1 quét Poka-Yoke |
| `belt2_lot` | TEXT | NOT NULL | Lô mành đai 2 quét Poka-Yoke |
| `ply_lot` | TEXT | NOT NULL | Lô mành thân quét Poka-Yoke |
| `bead_lot` | TEXT | NOT NULL | Lô tanh thép quét Poka-Yoke |
| `innerliner_lot` | TEXT | NOT NULL | Lô màng kín khí quét Poka-Yoke |
| `poka_yoke_status`| TEXT | DEFAULT 'VERIFIED_PASS'| Trạng thái xác thực chống nhầm |
| `status` | TEXT | CHECK IN (...) | BUILT, BUFFER, IN_CURING, CURED, SCRAPPED, QUARANTINED |

### 7. Bảng `production_cured_tires`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `tire_serial` | TEXT | PRIMARY KEY | **Số Sê-ri lốp duy nhất vĩnh viễn (VN-T-...)** |
| `gt_barcode` | TEXT | FK -> production_green_tires | Mã lốp mộc liên kết 100% |
| `sku` | TEXT | FK -> master_products | Mã quy cách sản phẩm |
| `press_id` | TEXT | FK -> master_equipment | Máy lưu hóa thực hiện nướng |
| `cavity_side` | TEXT | CHECK IN ('L', 'R') | Hốc khuôn Trái (L) hoặc Phải (R) |
| `actual_cure_sec` | INTEGER | NOT NULL | Tổng thời gian nén nhiệt thực tế |
| `avg_mold_temp_c` | REAL | NOT NULL | Nhiệt độ khuôn đo thực tế |
| `avg_bladder_press_bar`| REAL | NOT NULL | Áp suất bàng nén thực tế |
| `cure_quality_result`| TEXT | NOT NULL | PASS, TEMP_DROP, PRESSURE_DROP, OVER_CURE |
| `status` | TEXT | CHECK IN (...) | CURED, INSPECTED, SCRAPPED, REWORK, QUARANTINED |

### 8. Bảng `quality_inspections`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `inspection_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Khóa chính tự tăng |
| `tire_serial` | TEXT | FK -> production_cured_tires | Số sê-ri lốp kiểm tra KCS |
| `visual_result` | TEXT | CHECK IN ('PASS', 'FAIL') | Kết quả ngoại quan |
| `visual_defect_code`| TEXT | FK -> master_defect_codes | Mã lỗi ngoại quan |
| `xray_result` | TEXT | CHECK IN ('PASS', 'FAIL') | Kết quả soi mành X-Ray |
| `xray_defect_code` | TEXT | FK -> master_defect_codes | Mã lỗi kết cấu mành |
| `uniformity_rfv_n` | REAL | NOT NULL | Lực biến thiên hướng kính RFV (N) |
| `dynamic_balance_g`| REAL | NOT NULL | Độ mất cân bằng động (g) |
| `final_grade` | TEXT | CHECK IN (...) | GRADE_A (OEM), GRADE_B, REWORK, SCRAP |
| `passed` | INTEGER | CHECK IN (0, 1) | Cờ đạt chuẩn xuất xưởng |

### 9. Bảng `tire_rework_history`
| Cột | Kiểu | Ràng buộc | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- | :--- |
| `rework_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Khóa chính tự tăng |
| `tire_serial` | TEXT | FK -> production_cured_tires | Số sê-ri lốp đưa vào sửa chữa |
| `action_type` | TEXT | CHECK IN (...) | Cắt bavia, Mài cân bằng, Chấm tanh |
| `rework_count` | INTEGER | NOT NULL | **Số lần sửa lũy kế (Tối đa 2 lần)** |

*(Chi tiết 18 bảng còn lại về SCADA Telemetry, AI Anomaly, Dynamic Bottleneck, XAI SHAP và Graph ML Contagion được định nghĩa tương tự trong mã nguồn [`app/database.py`](../app/database.py)).*
</details>

---

## 5. Tối Ưu Chịu Tải Cao (High-Concurrency Tuning in Practice)

Để xử lý hàng nghìn lượt quét mã vạch mỗi phút trên sàn xưởng lốp mà không bị tắc nghẽn giao dịch, hệ thống áp dụng các tham số nhân SQLite:

1. **Chế Độ Ghi Nhật Ký WAL (Write-Ahead Logging):**
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA cache_size = -64000; -- 64MB Bộ nhớ đệm RAM
   ```
   * *Ý nghĩa:* Tách biệt luồng Đọc và Ghi. Các truy vấn báo cáo Dashboard và AI **hoàn toàn không khóa** thao tác ghi mã vạch của công nhân tại trạm máy TBM & Curing.

2. **Chống Treo Khóa Giao Dịch (Busy Timeout Interlock):**
   ```sql
   PRAGMA busy_timeout = 60000; -- Chờ tối đa 60 giây trước khi báo lỗi
   ```
   * *Ý nghĩa:* Loại bỏ triệt để lỗi `database is locked` khi hàng chục đầu đọc mã vạch quét đồng thời lúc giao ca.

3. **Phân Tách Read-Replica Chỉ Đọc:**
   * Dashboard điều hành SCADA và các tác vụ trích xuất báo cáo kết nối bằng cờ `SQLITE_OPEN_READONLY`, đảm bảo an toàn tuyệt đối cho Database Transactional chính.
