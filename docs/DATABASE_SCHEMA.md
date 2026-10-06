# Sơ Đồ Thiết Kế Cơ Sở Dữ Liệu Hệ Thống TIRE-MES (Database Architecture Specification)

Hệ thống Điều hành Sản xuất Nhà máy Lốp xe (**Tire Manufacturing Execution System - TIRE-MES**) được thiết kế tuân thủ nghiêm ngặt các tiêu chuẩn quốc tế:
* **ANSI/ISA-95 Level 3 (MOM - Manufacturing Operations Management)**
* **MESA-11 (11 Chức năng Cốt lõi của Hệ thống MES Quốc tế)**
* **IATF 16949 (Hệ thống Quản lý Chất lượng Ngành Công nghiệp Ô tô)**
* **ISO 9001 & ASTM Tire Testing Standards**

---

## 1. Sơ Đồ Thực Thể - Mối Quan Hệ Tổng Thể (Master Entity-Relationship Diagram)

Sơ đồ dưới đây mô tả toàn bộ **27 bảng dữ liệu**, các khóa chính (PK), khóa ngoại (FK) và mối quan hệ ràng buộc giữa các module sàn xưởng:

```mermaid
erDiagram
    %% ==========================================
    %% 1. PLANT HIERARCHY & MASTER DATA
    %% ==========================================
    master_areas ||--o{ master_equipment : "contains"
    master_equipment ||--o{ equipment_downtime_logs : "records_downtime"
    master_products ||--o{ master_boms : "defines_bill_of_materials"
    master_products ||--o| master_curing_recipes : "defines_cure_recipe"
    master_products ||--o{ work_orders : "ordered_in"
    master_equipment ||--o{ work_orders : "assigned_machine"
    master_operators ||--o{ production_green_tires : "builds_green_tire"
    master_operators ||--o{ quality_inspections : "inspects_tire"
    master_operators ||--o{ tire_rework_history : "performs_rework"
    master_defect_codes ||--o{ quality_inspections : "flags_defects"

    %% ==========================================
    %% 2. INVENTORY & PRODUCTION EXECUTION
    %% ==========================================
    inventory_components ||--o{ production_green_tires : "consumed_by_bom"
    work_orders ||--o{ production_green_tires : "batches"
    master_equipment ||--o{ production_green_tires : "built_on_tbm"
    master_equipment ||--o{ curing_press_cavities : "houses_cavities"

    %% ==========================================
    %% 3. CURING, QUALITY & REWORK
    %% ==========================================
    production_green_tires ||--o| production_cured_tires : "vulcanized_into"
    master_equipment ||--o{ production_cured_tires : "cured_on_press"
    production_cured_tires ||--o| quality_inspections : "verified_at_qc"
    production_cured_tires ||--o{ tire_rework_history : "repaired_in"
    production_cured_tires ||--o{ curing_telemetry_history : "monitored_cure_curve"

    %% ==========================================
    %% 4. IIOT, SCADA & PROTOCOL GATEWAY
    %% ==========================================
    master_equipment ||--o{ production_cycle_telemetry : "streams_cycle_time"
    gateway_connectors ||--o{ master_equipment : "interfaces_plc"

    %% ==========================================
    %% 5. AI SUITE: ANOMALY, BOTTLENECK, SHAP, GRAPH ML
    %% ==========================================
    master_equipment ||--o{ ai_anomaly_logs : "anomaly_flagged"
    master_equipment ||--o{ bottleneck_forecasts : "forecasts_bottleneck"
    master_equipment ||--o{ dynamic_routing_rules : "manages_divert_routes"
    production_cured_tires ||--o{ batch_process_telemetry : "telemetry_vector"
    production_green_tires ||--o{ batch_process_telemetry : "telemetry_green"
    graph_risk_propagation_runs ||--o{ graph_order_risk_scores : "evaluates_orders"
    work_orders ||--o{ graph_order_risk_scores : "scores_risk"

    %% ENTITY DEFINITIONS
    master_areas {
        string area_code PK "Mã khu vực (MIXING, PREP, TBM, CURING, FINISHING)"
        string area_name "Tên phân xưởng"
        string description "Mô tả công năng"
        int sequence_order "Thứ tự công đoạn"
    }

    master_equipment {
        string machine_id PK "Mã định danh máy (vd: TBM-01, CP-01)"
        string machine_name "Tên máy móc"
        string area_code FK "Khu vực trực thuộc"
        string model "Model nhà sản xuất"
        string status "RUNNING, IDLE, BREAKDOWN, CHANGEOVER, MAINTENANCE"
        int cavities_count "Số hốc lưu hóa (1 hoặc 2)"
        int target_cycle_time_sec "Takt Time chuẩn (giây)"
        string current_wo_id "Lệnh sản xuất hiện hành"
        int total_cycles "Tổng chu kỳ vận hành lũy kế"
        string last_maintenance_date "Ngày bảo dưỡng gần nhất"
        float oee_target "Mục tiêu OEE (%)"
    }

    master_products {
        string sku PK "Mã sản phẩm (vd: PCR-205-55R16-91V)"
        string tire_size "Quy cách kích cỡ lốp"
        string pattern_name "Tên mẫu hoa lốp"
        string segment "PCR, TBR, EV, OTR"
        string load_index "Chỉ số tải trọng"
        string speed_rating "Chỉ số tốc độ"
        float standard_weight_kg "Trọng lượng lốp tiêu chuẩn"
        float weight_tolerance_kg "Dung sai trọng lượng (+/- kg)"
        int std_tbm_time_sec "Thời gian thành hình chuẩn"
        int std_cure_time_sec "Thời gian lưu hóa chuẩn"
        float std_cure_temp_c "Nhiệt độ lưu hóa chuẩn"
        float std_bladder_press_bar "Áp suất bàng ép chuẩn"
    }

    master_boms {
        int id PK "Khóa chính tự tăng"
        string sku FK "Mã sản phẩm"
        string component_type "TREAD, SIDEWALL, BELT_1, BELT_2, PLY, BEAD, INNERLINER"
        string spec_code "Mã quy cách bán thành phẩm"
        string compound_code "Mã hợp phần cao su"
        float standard_qty "Định mức tiêu hao"
        string unit "Đơn vị tính (KG, PCS)"
    }

    master_curing_recipes {
        string recipe_id PK "Mã công thức lưu hóa"
        string sku FK "Mã sản phẩm duy nhất"
        int cure_time_sec "Thời gian lưu hóa (giây)"
        float mold_temp_target_c "Nhiệt độ khuôn đích (độ C)"
        float mold_temp_tolerance_c "Dung sai nhiệt độ"
        float platen_steam_bar "Áp suất hơi gia nhiệt khuôn"
        float bladder_press_bar "Áp suất bàng lưu hóa"
        int vacuum_exhaust_sec "Thời gian hút chân không"
        int max_bladder_cycles "Tuổi thọ bàng tối đa"
    }

    inventory_components {
        string lot_id PK "Mã lô bán thành phẩm (vd: LOT-TRD-202610-01)"
        string component_type "TREAD, SIDEWALL, BELT_1, BELT_2, PLY, BEAD, INNERLINER"
        string spec_code "Mã thông số kỹ thuật"
        string compound_code "Mã hỗn luyện cao su"
        string produced_time "Thời điểm sản xuất"
        string expiry_time "Hạn sử dụng (Shelf-life Poka-Yoke)"
        int remaining_qty "Số lượng tồn kho"
        string status "AVAILABLE, RESERVED, EXPIRED, DEPLETED, QUARANTINE"
        string storage_location "Vị trí giá đỡ / khay chứa"
        string raw_batch_ref "Mã mẻ luyện kín Banbury gốc"
    }

    work_orders {
        string wo_id PK "Mã lệnh sản xuất (vd: WO-2026-001)"
        string sku FK "Mã sản phẩm"
        int target_qty "Sản lượng kế hoạch"
        int completed_qty "Sản lượng hoàn thành"
        int scrap_qty "Số lượng phế phẩm"
        string planned_start "Thời gian bắt đầu kế hoạch"
        string planned_end "Thời gian kết thúc kế hoạch"
        string actual_start "Thời gian bắt đầu thực tế"
        string actual_end "Thời gian kết thúc thực tế"
        string status "PLANNED, RELEASED, IN_PROGRESS, COMPLETED, PAUSED"
        string priority "NORMAL, HIGH, URGENT"
        string assigned_machine "Máy được điều độ"
    }

    production_green_tires {
        string gt_barcode PK "Mã vạch lốp mộc duy nhất (GT-YYYYMMDD-XXXX)"
        string wo_id FK "Lệnh sản xuất"
        string sku FK "Mã sản phẩm"
        string tbm_machine_id FK "Máy thành hình TBM"
        string operator_id FK "Thợ vận hành"
        string build_timestamp "Thời điểm hoàn thành lốp mộc"
        float actual_weight_kg "Trọng lượng cân thực tế"
        string tread_lot "Lô mặt lốp (Tread)"
        string sidewall_lot "Lô hông lốp (Sidewall)"
        string belt1_lot "Lô mành đai 1 (Belt 1)"
        string belt2_lot "Lô mành đai 2 (Belt 2)"
        string ply_lot "Lô mành thân (Ply)"
        string bead_lot "Lô tanh thép (Bead)"
        string innerliner_lot "Lô màng kín khí (Innerliner)"
        string poka_yoke_status "VERIFIED_PASS, OVERRIDDEN"
        string status "BUILT, BUFFER, IN_CURING, CURED, SCRAPPED, QUARANTINED"
    }

    curing_press_cavities {
        string press_id PK "Mã máy lưu hóa (CP-01..CP-04)"
        string cavity_side PK "Hốc khuôn L (Trái) hoặc R (Phải)"
        string mold_id "Mã khuôn ép hiện hành"
        string current_gt_barcode "Mã lốp sống đang trong khuôn"
        string current_tire_serial "Số serial lốp thành phẩm đang nạp"
        string state "EMPTY, LOADED, CURING, COMPLETED, ALARM"
        string cure_start_time "Thời điểm bắt đầu chu kỳ"
        int cure_target_seconds "Thời gian lưu hóa mục tiêu"
        int cure_elapsed_seconds "Thời gian thực tế đã nướng"
        float mold_temp_c "Nhiệt độ khuôn đo thực thời"
        float bladder_press_bar "Áp suất bàng nén thực thời"
        float steam_press_bar "Áp suất hơi vòm cấp nhiệt"
        int bladder_cycle_count "Số chu kỳ ép của bàng hiện hành"
    }

    production_cured_tires {
        string tire_serial PK "Số serial lốp duy nhất (VN-T-YYYYMMDD-XXXXX)"
        string gt_barcode FK "Mã vạch lốp mộc liên kết"
        string sku FK "Mã sản phẩm"
        string press_id FK "Máy lưu hóa"
        string cavity_side "Hốc khuôn L hoặc R"
        string mold_id "Mã khuôn lưu hóa"
        string recipe_id "Công thức lưu hóa áp dụng"
        string cure_start_time "Thời điểm bắt đầu nướng"
        string cure_end_time "Thời điểm dỡ lốp"
        int actual_cure_sec "Tổng thời gian lưu hóa thực tế"
        float avg_mold_temp_c "Nhiệt độ khuôn trung bình"
        float avg_bladder_press_bar "Áp suất bàng trung bình"
        string cure_quality_result "PASS, TEMP_DROP, PRESSURE_DROP, OVER_CURE"
        string status "CURED, INSPECTED, SCRAPPED, REWORK, QUARANTINED"
    }

    quality_inspections {
        int inspection_id PK "Khóa chính tự tăng"
        string tire_serial FK "Số serial lốp kiểm định"
        string inspection_timestamp "Thời điểm kiểm tra KCS"
        string inspector_id FK "Mã kiểm định viên"
        string visual_result "PASS, FAIL"
        string visual_defect_code FK "Mã lỗi ngoại quan"
        string defect_location "Vị trí xuất hiện khuyết tật"
        string xray_result "PASS, FAIL"
        string xray_defect_code FK "Mã lỗi X-Ray mành thép"
        float belt_alignment_mm "Độ lệch mép mành đai"
        float uniformity_rfv_n "Lực hướng kính biến thiên RFV (N)"
        float uniformity_lfv_n "Lực hướng trục biến thiên LFV (N)"
        float dynamic_balance_g "Mất cân bằng động (g)"
        string final_grade "GRADE_A, GRADE_B, REWORK, SCRAP"
        int passed "Cờ đạt chuẩn xuất xưởng (0 hoặc 1)"
        string disposition_notes "Ghi chú xử lý chất lượng"
    }

    tire_rework_history {
        int rework_id PK "Khóa chính tự tăng"
        string tire_serial FK "Số serial lốp sửa chữa"
        string rework_timestamp "Thời điểm thực hiện sửa"
        string operator_id FK "Công nhân sửa hàng"
        string action_type "TRIM_VENT_SPEW, BALANCE_BUFFING, BEAD_TOUCHUP, COSMETIC"
        int rework_count "Số lần sửa lũy kế (Tối đa 2 lần)"
        string notes "Chi tiết kỹ thuật sửa hàng"
    }

    equipment_downtime_logs {
        int id PK "Khóa chính tự tăng"
        string machine_id FK "Mã máy gặp sự cố"
        string start_time "Thời điểm bắt đầu dừng"
        string end_time "Thời điểm phục hồi"
        int duration_minutes "Thời lượng dừng máy (phút)"
        string reason_code "Mã nguyên nhân dừng máy"
        string comments "Ghi chú khắc phục"
    }

    master_defect_codes {
        string defect_code PK "Mã khuyết tật (vd: DEF-VIS-01)"
        string defect_name_vi "Tên lỗi tiếng Việt"
        string defect_name_en "Tên lỗi tiếng Anh"
        string inspection_station "VISUAL, XRAY, UNIFORMITY, ALL"
        string severity "MINOR, MAJOR, CRITICAL"
        string default_disposition "REWORK, GRADE_B, SCRAP"
        string root_cause_area "MIXING, PREP, TBM, CURING"
    }

    master_operators {
        string badge_id PK "Mã thẻ nhân sự (OP-XXXX)"
        string full_name "Họ và tên công nhân / kỹ sư"
        string role "TBM_OPERATOR, CURING_TECH, QC_INSPECTOR, SUPERVISOR"
        string current_shift "Ca làm việc (SHIFT_A, SHIFT_B, SHIFT_C)"
        int skill_level "Bậc tay nghề (1 đến 5)"
    }

    master_documents {
        string doc_id PK "Mã tài liệu SOP / WI"
        string doc_name "Tên tài liệu hướng dẫn"
        string category "SOP, WORK_INSTRUCTION, SPECIFICATION, SAFETY"
        string applicable_area "Khu vực áp dụng"
        string applicable_sku "SKU áp dụng hoặc ALL"
        string version "Phiên bản tài liệu (vd: v2.1)"
        string effective_date "Ngày có hiệu lực"
        string status "ACTIVE, OBSOLETE, DRAFT"
        string approver_badge "Người ký duyệt"
        string content_markdown "Nội dung quy trình hướng dẫn"
    }

    gateway_connectors {
        string connector_id PK "Mã kết nối (vd: OPCUA-TBM-01)"
        string protocol_type "OPC_UA, OPC_DA, MODBUS_TCP, MQTT, INDUSTRIAL_SOCKET"
        string target_ip "Địa chỉ IP PLC / Cổng kết nối"
        int target_port "Cổng mạng giao tiếp"
        string status "CONNECTED, DEGRADED, DISCONNECTED, ERROR"
        float ping_latency_ms "Độ trễ truyền thông (ms)"
        string last_heartbeat "Thời điểm nhận gói tin cuối"
        string tags_mapping_json "Cấu hình ánh xạ Tag PLC"
    }

    production_cycle_telemetry {
        int id PK "Khóa chính tự tăng"
        string machine_id "Mã thiết bị"
        string area_code "Khu vực sản xuất"
        float cycle_time_sec "Takt time chu kỳ (giây)"
        float queue_time_sec "Thời gian chờ đệm hàng WIP"
        string status "COMPLETED, SCRAP, REWORK"
        string timestamp "Thời điểm ghi nhận telemetry"
    }

    ai_anomaly_logs {
        int id PK "Khóa chính tự tăng"
        string timestamp "Thời điểm phát hiện bất thường"
        string machine_id "Mã máy phát sinh sự cố"
        float actual_takt_time "Takt time thực tế đo được"
        float target_takt_time "Takt time chuẩn lý thuyết"
        float takt_deviation_pct "Độ lệch phần trăm (%)"
        float wip_queue_time "Thời gian nằm chờ đệm"
        float anomaly_score "Điểm bất thường AI [0.0 - 1.0]"
        string severity "NORMAL, WARNING, CRITICAL"
        string detection_source "ISOLATION_FOREST, AUTOENCODER, ENSEMBLE"
        string root_cause_hint "Gợi ý nguyên nhân kỹ thuật"
        int is_acknowledged "Trạng thái kỹ sư đã xác nhận"
    }

    bottleneck_forecasts {
        int id PK "Khóa chính tự tăng"
        string timestamp "Thời điểm chạy mô hình dự báo"
        string current_bottleneck "Trạm nghẽn hiện tại"
        string predicted_station_2h "Dự báo trạm nghẽn sau 2 giờ"
        string predicted_station_4h "Dự báo trạm nghẽn sau 4 giờ"
        float confidence_score "Độ tin cậy mô hình AI"
        int shift_probability_pct "Xác suất dịch chuyển cổ chai (%)"
        string recommended_action "Hành động điều hướng luồng khuyến nghị"
        int auto_reroute_triggered "Trạng thái tự động kích hoạt điều hướng"
    }

    dynamic_routing_rules {
        string rule_id PK "Mã luật điều hướng (vd: RULE-TBM-CURING-PRIMARY)"
        string source_station "Trạm nguồn phát sinh dòng chảy"
        string baseline_destination "Tuyến đích tiêu chuẩn SOP"
        string alternate_destination "Tuyến đích thay thế khi nghẽn"
        int priority "Độ ưu tiên điều phối"
        int is_active "Trạng thái kích hoạt (1 hoặc 0)"
        float current_divert_ratio "Tỷ lệ san tải chuyển hướng (%)"
        string trigger_condition "Điều kiện kích hoạt luật"
        string last_updated "Thời điểm cập nhật gần nhất"
    }

    batch_process_telemetry {
        int id PK "Khóa chính tự tăng"
        string batch_id "Mã mẻ luyện / mẻ lưu hóa"
        string green_tire_id "Mã lốp mộc liên kết"
        string tire_serial "Mã serial lốp thành phẩm"
        string timestamp "Thời điểm ghi nhận mẻ"
        float mooney_viscosity_ml "Độ nhớt Mooney ML(1+4)"
        float scorch_time_ts2_min "Thời gian lưu hóa sớm ts2"
        float cure_time_tc90_min "Thời gian chín tối ưu tc90"
        float dump_temp_c "Nhiệt độ xuất cao su mẻ luyện"
        float rotor_energy_kwh "Năng lượng trục trộn rotor"
        float carbon_dispersion_pct "Độ phân tán muội than"
        float tread_gauge_thickness_mm "Độ dày mặt lốp cán đùn"
        float barrel_temp_zone4_c "Nhiệt độ nòng đùn vùng 4"
        float extruder_head_pressure_bar "Áp suất đầu máy cán đùn"
        float cord_tension_n "Lực căng sợi mành thép"
        float stitch_roller_press_bar "Áp lực con lăn ép TBM"
        float drum_expansion_diam_mm "Đường kính bung trống TBM"
        float splice_overlap_width_mm "Bề rộng mép nối chồng dán"
        float internal_bladder_press_bar "Áp suất bàng nén lưu hóa"
        float mold_temp_upper_c "Nhiệt độ nắp khuôn trên"
        float mold_temp_lower_c "Nhiệt độ đáy khuôn dưới"
        float steam_dome_press_bar "Áp suất vòm cấp hơi"
        float vacuum_exhaust_time_sec "Thời gian hút chân không"
        int bladder_cycle_age "Tuổi thọ chu kỳ bàng lưu hóa"
        int is_defective "Cờ đánh giá phế phẩm (1 hoặc 0)"
        string defect_code "Mã lỗi ghi nhận"
        string defect_name "Tên khuyết tật"
    }

    shap_root_cause_reports {
        int id PK "Khóa chính tự tăng"
        string created_at "Thời điểm tạo báo cáo"
        string defect_spike_category "Danh mục đột biến phế phẩm"
        int total_batches_analyzed "Tổng số mẻ phân tích"
        float spike_defect_rate_pct "Tỷ lệ lỗi đợt đột biến (%)"
        float baseline_defect_rate_pct "Tỷ lệ lỗi nền bình thường (%)"
        string top_root_cause_feature "Thông số căn nguyên số 1"
        float top_root_cause_importance "Giá trị tầm quan trọng SHAP"
        string global_importance_json "Toàn văn JSON xếp hạng 19 thông số"
        string decision_rules_json "Toàn văn JSON cây quyết định If-Then"
        string corrective_action_recommendation "Khuyến nghị CAPA IATF 16949"
    }

    graph_genealogy_edges {
        int id PK "Khóa chính tự tăng"
        string source_id "Mã đỉnh nguồn (vd: LOT:LOT-TRD-01)"
        string source_type "Loại nút nguồn (LOT, BATCH, TIRE, MACHINE, WO)"
        string target_id "Mã đỉnh đích (vd: TIRE:GT-0001)"
        string target_type "Loại nút đích"
        string relation_type "Quan hệ (CONSUMES, PROCESSED_ON, SEQUENCE, TWIN_CAVITY)"
        float weight "Trọng số truyền tải rủi ro [0.0 - 1.0]"
        string metadata_json "Thông tin bổ trợ"
        string created_at "Thời điểm tạo liên kết"
    }

    graph_risk_propagation_runs {
        string run_id PK "Mã phiên phân tích đồ thị (RUN-GRAPH-YYYYMMDDHHMMSS)"
        string suspect_node_id "Mã đỉnh nghi vấn ổ dịch"
        string suspect_node_type "Loại đỉnh (LOT, BATCH, MACHINE)"
        string defect_description "Mô tả khuyết tật kiểm định"
        string algorithm "Thuật toán (ENSEMBLE_PYTORCH_GNN_AND_RWR_DIFFUSION)"
        int propagation_hops "Số bước nhảy truyền tin tối đa (hops)"
        int critical_wos_count "Số đơn hàng nguy cấp (CRITICAL)"
        int high_risk_wos_count "Số đơn hàng rủi ro cao (HIGH_RISK)"
        int total_tires_at_risk "Tổng số lốp bị đe dọa (Blast Radius)"
        string blast_radius_summary_json "Tóm tắt bán kính ảnh hưởng"
        int quarantine_applied "Cờ đã thực thi cách ly sàn xưởng (0 hoặc 1)"
        string created_at "Thời điểm quét đồ thị"
        string authorized_badge "Mã nhân sự cấp lệnh"
    }

    graph_order_risk_scores {
        int id PK "Khóa chính tự tăng"
        string run_id FK "Khóa ngoại liên kết phiên phân tích"
        string wo_id "Mã lệnh sản xuất"
        float risk_score "Xác suất rủi ro lây nhiễm [0.0 - 1.0]"
        string risk_tier "CRITICAL, HIGH_RISK, MEDIUM_RISK, LOW_RISK"
        int tires_at_risk "Số lốp thuộc đơn hàng chịu rủi ro"
        string primary_transmission_vector "Vectơ lây nhiễm (DIRECT, SHARED_MACHINE, ISOLATED)"
        string shortest_infection_path "Chuỗi truyền nhiễm ngắn nhất"
        string recommended_action "Hành động khuyến nghị (STOP_WORK, 100%_NDT, AQL)"
        string action_status "PENDING, QUARANTINED, CLEARED"
        string created_at "Thời điểm ghi nhận điểm số"
    }
```

---

## 2. Từ Điển Dữ Liệu & Chi Tiết 10 Miền Nghiệp Vụ (Data Dictionary & Domain Specs)

### Miền 1: Master Data & Phân Cấp Nhà Máy ISA-95 (Plant Hierarchy)
Quản lý cây tài sản vật lý nhà máy theo cấu trúc chuẩn **Enterprise $\to$ Site $\to$ Area $\to$ Work Center $\to$ Work Unit**:

1. **`master_areas`**: Quản lý 5 phân xưởng chính theo chuỗi giá trị sản xuất lốp:
   * `MIXING`: Luyện kín cao su (Banbury Internal Mixers).
   * `PREP`: Chuẩn bị bán thành phẩm (Cán đùn gai, Cán tráng mành thép, Cuộn tanh).
   * `TBM`: Thành hình lốp mộc (Tire Building Machines).
   * `CURING`: Lưu hóa lưu huỳnh (Vulcanization Presses).
   * `FINISHING`: Kiểm định KCS, Cắt bavia & Hoàn thiện (Finishing & Uniformity).
2. **`master_equipment`**: Thông số kỹ thuật của 11 máy móc chủ lực (`MIX-01`, `EXT-01`, `CAL-01`, `TBM-01`, `TBM-02`, `CP-01`..`CP-04`, `XR-01`, `UF-01`), Takt Time chuẩn, chu kỳ bảo trì TPM.
3. **`equipment_downtime_logs`**: Nhật ký dừng máy OEE theo chuẩn MESA (Availability Loss): Phân loại nguyên nhân dừng kỹ thuật, thay khuôn, thiếu vật tư, hỏng bàng lưu hóa.
4. **`master_products`**: Danh mục SKU lốp radial (PCR, TBR, EV cao cấp), tải trọng, cấp tốc độ, trọng lượng danh định và dung sai khắt khe ($\pm 0.25\text{ kg}$).
5. **`master_boms`**: Định mức tiêu hao bán thành phẩm cấu thành một chiếc lốp (Tread, Sidewall, Belt 1, Belt 2, Ply, Bead, Innerliner).
6. **`master_curing_recipes`**: Thông số nướng lốp SCADA chuẩn cho từng quy cách (Nhiệt độ khuôn $170^\circ\text{C}$, Áp suất bàng $21\text{ bar}$, Hơi vòm $15\text{ bar}$, Thời gian hút chân không $40\text{s}$, Tuổi thọ bàng nén tối đa 350 chu kỳ).
7. **`master_defect_codes`**: Bộ mã lỗi quốc tế phân bổ theo trạm kiểm tra (`VISUAL`, `XRAY`, `UNIFORMITY`) và hướng xử lý (`REWORK`, `GRADE_B`, `SCRAP`).
8. **`master_operators`**: Ma trận nhân sự, vai trò, ca làm việc và bậc tay nghề (Skill Matrix Levels 1-5).
9. **`master_documents`**: Hệ thống quản lý tài liệu SOP, Digital Work Instructions, khóa phiên bản ECN chống nhầm lẫn công nghệ.

---

### Miền 2: Quản Lý Kho & Lô Vật Tư Bán Thành Phẩm (Inventory & Material Traceability)
Đảm bảo khả năng truy vết nguồn gốc 100% hai chiều (**Bi-directional Genealogy Traceability**) theo IATF 16949 Section 8.5.2:

* **`inventory_components`**:
  * Mỗi cuộn/kệ vật tư có mã lô độc nhất `lot_id` (vd: `LOT-TRD-202610-01`).
  * Liên kết trực tiếp với mẻ luyện Banbury gốc qua `raw_batch_ref`.
  * Quản lý tuổi thọ cao su chưa lưu hóa (**Shelf-life Poka-Yoke**): Nếu `expiry_time < NOW()`, hệ thống tự động khóa trạng thái `EXPIRED` và kích hoạt Interlock cấm trạm TBM nạp cuộn vật tư vào trống.

---

### Miền 3: Kế Hoạch Sản Xuất & Thành Hình Lốp Mộc (TBM Green Tire Building)
Điều phối và thu thập dữ liệu công đoạn Stage 1:

1. **`work_orders`**: Lệnh sản xuất kế hoạch từ ERP/SAP, số lượng sản lượng hoàn thành, sản lượng phế phẩm, dây chuyền máy được giao.
2. **`production_green_tires`**: Bảng lõi ghi nhận từng chiếc lốp mộc được lắp ráp hoàn chỉnh:
   * Mã vạch duy nhất `gt_barcode` (in nhãn nhiệt dán bên trong lốp).
   * Lưu vết 100% phả hệ linh kiện cấu thành: `tread_lot`, `sidewall_lot`, `belt1_lot`, `belt2_lot`, `ply_lot`, `bead_lot`, `innerliner_lot`.
   * Ghi nhận trọng lượng cân thực tế `actual_weight_kg` để phát hiện khuyết tật thiếu thừa cao su trước khi đưa sang lò lưu hóa.

---

### Miền 4: Lưu Hóa Lốp & SCADA Telemetry (Curing & Vulcanization)
Công đoạn Stage 2 quyết định cơ lý tính và độ an toàn của lốp:

1. **`curing_press_cavities`**: Trạng thái thời gian thực của từng hốc khuôn (Hốc L & Hốc R): Nhiệt độ, áp suất bàng nén, áp suất hơi vòm, số chu kỳ ép lũy kế của bàng lưu hóa để phát hiện nguy cơ rách bàng.
2. **`production_cured_tires`**: Khai sinh **Digital Tire Passport** gắn với số serial duy nhất dập nổi trên hông lốp (`tire_serial` dạng `VN-T-YYYYMMDD-XXXXX`). Liên kết 1-1 với `gt_barcode`.
3. **`curing_telemetry_history`**: Lưu trữ chuỗi thời gian (Time-series) đường cong gia nhiệt và nén ép của từng mẻ để đối soát chất lượng chuyên sâu.

---

### Miền 5: Kiểm Định Chất Lượng & Vòng Lặp Sửa Chữa (QC Inspection & Anti-Loop Interlock)
Đảm bảo không bao giờ xuất xưởng lốp lỗi ra thị trường:

1. **`quality_inspections`**: Kết quả kiểm tra đa trạm (Ngoại quan bề mặt, Chụp X-Ray mành thép, Đo biến thiên lực hướng tâm RFV/LFV, Cân bằng động Dynamic Balance). Đánh giá phân hạng: `GRADE_A` (OEM), `GRADE_B` (Thương mại), `REWORK` (Sửa chữa), `SCRAP` (Phế phẩm tiêu hủy).
2. **`tire_rework_history`**: Nhật ký sửa hàng có khóa **Anti-Loop Interlock (IATF 16949 Section 8.7.1)**: Giới hạn tối đa 2 lần sửa chữa. Nếu cố tình sửa lần thứ 3, hệ thống tự động khóa cưỡng bức thành `SCRAP` để triệt tiêu rủi ro mỏi nhiệt cấu trúc lốp.

---

### Miền 6: Cổng Tích Hợp Giao Thức Công Nghiệp (IIoT & Protocol Gateway)
Kết nối vật lý giữa hệ điều hành MES với tầng điều khiển tự động hóa (OT - PLC/SCADA):

1. **`gateway_connectors`**: Cấu hình 5 giao thức công nghiệp phổ biến (`OPC-UA`, `OPC-DA`, `Modbus-TCP`, `MQTT`, `Industrial Sockets`), địa chỉ IP, cổng mạng, độ trễ Ping ms và cấu hình ánh xạ Tags.
2. **`production_cycle_telemetry`**: Dữ liệu chuỗi thời gian ghi nhận Takt Time và thời gian chờ đệm (WIP Queue Time) giữa các công đoạn để phục vụ giám sát năng suất.

---

### Miền 7: Module AI 1 - Unsupervised Anomaly Detection (Phát Hiện Bất Thường)
Giám sát suy giảm hiệu suất ngầm (Productivity Degradation):

* **`ai_anomaly_logs`**: Lưu nhật ký phát hiện bất thường kết hợp giữa **Isolation Forest (100 Decision Trees)** và **PyTorch Deep Autoencoders**. Tự động gắn nhãn mức độ `WARNING` hoặc `CRITICAL` khi chu kỳ Takt Time bị trôi dạt (Takt Creep) hoặc hàng nghẽn ứ đệm WIP.

---

### Miền 8: Module AI 2 - Dynamic Bottleneck Prediction & Automated Routing
Dự báo điểm nghẽn và tự động san tải dòng vật tư:

1. **`bottleneck_forecasts`**: Lưu kết quả dự báo điểm nghẽn chuyển dịch sang trạm nào trong **2–4 giờ tới** dựa trên mô hình Markov Chain và Random Forest Regressor.
2. **`dynamic_routing_rules`**: Bảng quy tắc định tuyến động của MES (Routing Engine). Cho phép tự động chuyển hướng tỷ lệ dòng lốp mộc từ chuyền nghẽn sang các dây chuyền thay thế còn dư công suất (vd: Chuyển hướng từ `CP-01/CP-02` sang `CP-03/CP-04`).

---

### Miền 9: Module AI 3 - Explainable AI (TreeSHAP & Decision Tree Root Cause)
Bóc tách căn nguyên đa biến gây bùng phát tỷ lệ phế phẩm:

1. **`batch_process_telemetry`**: Thu thập đồng bộ **19 thông số công nghệ cốt lõi** trải dài qua 5 công đoạn (Độ nhớt Mooney, thời gian ts2, nhiệt độ xuất mẻ, độ dày mặt lốp cán đùn, lực căng mành đai, áp suất bàng nén, độ phân tán muội than, áp lực con lăn TBM, thời gian hút chân không, v.v.).
2. **`shap_root_cause_reports`**: Báo cáo phân tích căn nguyên gốc rễ:
   * **Global Feature Importance**: Xếp hạng tỷ trọng đóng góp của 19 biến số trên toàn xưởng.
   * **Local Waterfall Decomposition**: Phân rã rủi ro từng lốp thành phần đóng góp dương (đẩy lỗi) và âm (kiềm chế lỗi) so với tỷ lệ nền $\mathbb{E}[f(X)]$.
   * **Decision Tree Rule Mining**: Khai phá các luật vận hành If-Then dễ hiểu cho kỹ sư CAPA.

---

### Miền 10: Module AI 4 - Graph Machine Learning (Traceability Contagion)
Biến phả hệ sản xuất thành mạng đồ thị để dự báo rủi ro lây lan ổ dịch:

1. **`graph_genealogy_edges`**: Lưu trữ toàn bộ 910 cạnh quan hệ đa chiều giữa các thực thể nhà máy (Cán đùn, Thành hình, Dư lượng máy chạy kế, Lưu hóa đồng thời hốc đôi Twin-Cavity).
2. **`graph_risk_propagation_runs`**: Nhật ký từng phiên chạy mô hình kết hợp **PyTorch Heterogeneous MPNN** và **Random Walk with Restart (RWR) Diffusion**.
3. **`graph_order_risk_scores`**: Đánh giá ma trận rủi ro lây nhiễm và phân hạng Tier cho từng đơn hàng đang chạy trên sàn (`CRITICAL`, `HIGH_RISK`, `MEDIUM_RISK`, `LOW_RISK`), xác định chuỗi lây nhiễm ngắn nhất (Shortest Path) và kích hoạt **Khóa Cách Ly Khẩn Cấp 1-Click MES Quarantine** theo IATF 16949 Section 8.7.

---

## 3. Kiến Trúc Hiệu Năng & Chống Khóa Chết (High-Concurrency Architecture)

Để đáp ứng hàng nghìn giao dịch quét mã vạch mỗi phút trên sàn xưởng lốp, cơ sở dữ liệu được tối ưu hóa ở mức nhân hệ điều hành:

### 3.1. Chế Độ Ghi Nhật Ký Write-Ahead Logging (WAL)
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -64000; -- 64MB Cache
```
* **Lợi ích:** Các giao dịch đọc (Dashboard, Báo cáo OEE, Quét tìm kiếm phả hệ) hoàn toàn **không bao giờ khóa** giao dịch ghi của công nhân tại trạm máy TBM và Curing.

### 3.2. Cơ Chế Chống Treo Giao Dịch Giờ Cao Điểm (Busy Timeout Interlock)
```sql
PRAGMA busy_timeout = 60000; -- 60 giây chờ giải phóng khóa trước khi báo lỗi
```
* Loại bỏ triệt để lỗi `database is locked` khi hàng chục đầu đọc mã vạch quét đồng thời lúc giao ca.

### 3.3. Tách Biệt Read-Replica Chỉ Đọc (Dashboard Isolation Pattern)
* Dashboard điều hành và báo cáo phân tích AI kết nối qua cờ `SQLITE_OPEN_READONLY`.
* Bất kỳ câu truy vấn báo cáo nặng nào chạy dài cũng không ảnh hưởng tới luồng ghi Transactional của dây chuyền sản xuất vật lý.

### 3.4. Hệ Thống Chỉ Mục Hiệu Năng Cao (Performance Indexes)
```sql
CREATE INDEX idx_green_tire_sku ON production_green_tires(sku);
CREATE INDEX idx_green_tire_wo ON production_green_tires(wo_id);
CREATE INDEX idx_cured_tire_gt ON production_cured_tires(gt_barcode);
CREATE INDEX idx_quality_serial ON quality_inspections(tire_serial);
CREATE INDEX idx_wo_status ON work_orders(status);
CREATE INDEX idx_components_lot ON inventory_components(lot_id);
CREATE INDEX idx_anomaly_time ON ai_anomaly_logs(timestamp);
CREATE INDEX idx_cycle_machine ON production_cycle_telemetry(machine_id, timestamp);
CREATE INDEX idx_bottleneck_time ON bottleneck_forecasts(timestamp);
CREATE INDEX idx_routing_source ON dynamic_routing_rules(source_station);
CREATE INDEX idx_batch_telemetry_time ON batch_process_telemetry(timestamp);
CREATE INDEX idx_batch_defective ON batch_process_telemetry(is_defective);
CREATE INDEX idx_batch_serial ON batch_process_telemetry(tire_serial);
CREATE INDEX idx_graph_edge_src ON graph_genealogy_edges(source_id);
CREATE INDEX idx_graph_edge_tgt ON graph_genealogy_edges(target_id);
CREATE INDEX idx_graph_runs_suspect ON graph_risk_propagation_runs(suspect_node_id);
CREATE INDEX idx_graph_scores_run ON graph_order_risk_scores(run_id);
```

---

## 4. Dòng Chảy Vòng Đời Dữ Liệu Thực Tế (End-to-End Tire Data Lifecycle)

```
[1. KHO BTP: inventory_components] 
       | (Quét mã vạch lô linh kiện & Kiểm tra hạn dùng Shelf-life Poka-Yoke)
       v
[2. THÀNH HÌNH TBM: production_green_tires] 
       | (Tạo nhãn lốp mộc GT-XXXX, liên kết WO-XXXX, cân trọng lượng)
       v
[3. ĐỆM CHỜ WIP: Anti-Skip Gate 2->3 Enforcement]
       | (Chặn lốp mộc nhảy cóc bỏ qua lưu hóa sang trạm KCS)
       v
[4. LƯU HÓA: curing_press_cavities -> production_cured_tires]
       | (Khởi tạo Digital Tire Passport VN-T-XXXXX, giám sát nhiệt độ, bàng nén)
       v
[5. KIỂM ĐỊNH KCS: quality_inspections]
       |---> GRADE_A / GRADE_B (Đạt chuẩn xuất xưởng)
       |---> REWORK (Sửa hàng -> tire_rework_history -> Tối đa 2 lần)
       |---> SCRAP (Phế phẩm -> Khóa Poka-Yoke cấm nhập kho thành phẩm)
       v
[6. AI GIÁM SÁT & BẢO VỆ TOÀN DIỆN]
       |---> Anomaly Detection: Quét trôi Takt Time và đọng hàng đệm
       |---> Bottleneck Predictor: Dự báo trước 2-4h & San tải tự động
       |---> TreeSHAP XAI: Chỉ điểm thông số công nghệ gây đột biến lỗi
       +---> Graph ML Contagion: Dự báo bán kính lây lan & Phong tỏa 1-Click
```

---
*Tài liệu kiến trúc cơ sở dữ liệu được biên soạn và chuẩn hóa bởi Senior MES Solution Architect - Phục vụ triển khai nhà máy thông minh Smart Factory theo chuẩn ISA-95 Level 3 & IATF 16949.*
