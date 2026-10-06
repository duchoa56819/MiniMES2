# TIRE-MES 4.0: HỆ THỐNG ĐIỀU HÀNH SẢN XUẤT NHÀ MÁY LỐP XE
### *Kiến trúc & Triển khai bởi Kỹ sư MES với 10 năm kinh nghiệm trong ngành sản xuất lốp xe*
### *Tuân thủ tiêu chuẩn quốc tế ANSI/ISA-95 Level 3 (MOM / MES Core Functions)*

---

## 1. TỔNG QUAN NGÀNH & BỐI CẢNH SẢN XUẤT LỐP XE

Ngành sản xuất lốp xe (Tire Manufacturing) là một trong những ngành công nghiệp sản xuất phức tạp nhất thế giới, kết hợp cả ba mô hình sản xuất: **Batch Processing** (Luyện kín cao su), **Continuous Processing** (Đùn mặt lốp & Cán tráng mành thép/mành sợi), và **Discrete Manufacturing** (Đóng lốp thành hình TBM, Lưu hóa lốp và KCS hoàn thiện).

Một chiếc lốp xe hiện đại (ví dụ lốp du lịch Radial PCR hoặc lốp xe tải toàn thép TBR) là sự tích hợp của hơn **15 loại vật liệu và hợp phần cấu trúc**:
1. **Mặt lốp (Tread Cap & Base)**: Chịu mài mòn, bám đường ướt, kháng lực cản lăn.
2. **Hông lốp (Sidewall)**: Chịu biến dạng uốn gấp liên tục, kháng ô-zôn và thời tiết.
3. **Đai mành thép 1 & 2 (Steel Belts)**: Tạo độ cứng vững hướng kính, bảo vệ thân lốp dưới tốc độ cao.
4. **Lớp mành sợi thân (Body Plies / Carcass)**: Sợi Polyester, Rayon hoặc Thép chịu áp suất khí nén bên trong.
5. **Vòng tanh thép & Lõi tanh (Bead Rings & Apex)**: Cố định lốp vào vành la-zăng xe an toàn.
6. **Màng kín khí (Innerliner)**: 100% cao su Halobutyl ngăn rò rỉ áp suất lốp không săm.

**TIRE-MES 4.0** được thiết kế để đóng vai trò là "hệ thần kinh trung ương" kết nối giữa tầng hoạch định doanh nghiệp (ERP - SAP/Oracle Level 4) và tầng điều khiển tự động hóa thiết bị nhà xưởng (PLC/SCADA Siemens, Rockwell Level 1 & 2).

> 📖 **Tài liệu chuyên sâu**: Chi tiết về cơ chế truyền thông và bắt tay (Handshake) giữa PLC và MES được đặc tả đầy đủ tại tệp [`PLC_MES_COMMUNICATION.md`](PLC_MES_COMMUNICATION.md).

---

## 2. DÂY CHUYỀN SẢN XUẤT KHÉP KÍN (ISA-95 PRODUCTION HIERARCHY)

```
[ Giai đoạn 1 ]          [ Giai đoạn 2 ]          [ Giai đoạn 3 ]
Luyện Kín Banbury  ───>  Bán Thành Phẩm    ───>  Thành Hình TBM
(Master/Final Batch)      (Extruder & Calender)    (Poka-Yoke Scan 7 Lots)
         │                       │                       │
         ▼                       ▼                       ▼
   Mooney Viscosity        Hạn dùng 48-72h       Cấp mã Lốp sống
   Rheometer Curve         Đo độ dày/khối lượng    (Green Tire ID: GT-...)
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                          [ Giai đoạn 4 ]
                          Lò Lưu Hóa Curing
                          (170°C, 21 bar Bladder,
                           Thời gian nén 13 phút)
                                 │
                                 ▼
                           Khắc Số Sê-ri Vĩnh Viễn
                           (Tire Serial: VN-T-...)
                                 │
                                 ▼
                          [ Giai đoạn 5 ]
                          Kiểm Tra Hoàn Thiện KCS
                          ┌──────────────────────────┐
                          │ 1. Soi Ngoại Quan        │
                          │ 2. Soi X-Ray Mành Thép   │
                          │ 3. Đo Độ Đồng Đều UF/RFV │
                          └──────────┬───────────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
            [ HẠNG A ]          [ HẠNG B ]          [ PHẾ PHẨM ]
            OE Xuất Khẩu     Thương Mại Đổi Lốp    Cắt Tanh Hủy Bỏ
                 │                   │
                 └─────────┬─────────┘
                           ▼
                    [ Giai đoạn 6 ]
                  Kho Thành Phẩm (WMS)
                  Hộ Chiếu Số Lốp 100%
```

---

## 3. KIẾN TRÚC CƠ SỞ DỮ LIỆU CHUẨN ISA-95 & MÔ HÌNH THỰC THỂ (DATABASE SCHEMA & ER DIAGRAM)

> 📊 **Đặc Tả Toàn Diện & Sơ Đồ Mermaid ER**: Toàn bộ sơ đồ thiết kế 27 bảng dữ liệu, khóa chính, khóa ngoại và từ điển dữ liệu chuẩn ANSI/ISA-95 Level 3 & IATF 16949 được biên soạn chi tiết tại tệp [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md).

Cơ sở dữ liệu được xây dựng trên SQLite Engine hiệu năng cao với WAL mode (`PRAGMA journal_mode = WAL`), cơ chế chống khóa chết (`PRAGMA busy_timeout = 60000`), phân tách Read-Replica chỉ đọc và cơ chế toàn vẹn ràng buộc khóa ngoại nghiêm ngặt:

### 3.1. Nhóm Dữ Liệu Danh Mục Nền Tảng (Master Data)
- `master_areas`: Phân vùng 6 khu vực sản xuất theo cấp bậc ISA-95 (MIXING, PREP, TBM, CURING, FINISHING, WAREHOUSE).
- `master_equipment`: 11 thiết bị then chốt (Máy luyện Banbury BB-270, Máy đùn Triplex, Máy cán mành thép 4 trục, Máy đóng lốp VMI MAXX PCR, Máy đóng lốp TBR, Các lò lưu hóa thủy lực 63.5" và cơ khí, Hệ thống soi X-Ray tự động Yxlon MTIS, Máy đo cân bằng động Hofmann UF).
- `master_products`: Danh mục quy cách lốp (PCR 205/55R16, PCR 225/60R17 SUV, EV 245/45R19 UHP, TBR 315/80R22.5, TBR 11R22.5) với trọng lượng chuẩn, dung sai, chu kỳ tiêu chuẩn.
- `master_boms`: Định mức Bill of Materials cho từng mã lốp (Tread, Sidewall, Belt 1, Belt 2, Ply, Bead, Innerliner) tương ứng với từng mã cao su hợp phần (`CP-TRD-101`, `CP-SW-202`, `CP-INL-303`...).
- `master_curing_recipes`: Đơn công nghệ lưu hóa: Nhiệt độ khuôn setpoint (170°C), Áp suất hơi platen (15 bar), Áp suất bàng bọng nở (21 bar), Thời gian nén nhiệt (780 giây), Ngưỡng mỏi bàng bọng (350 lần).
- `master_defect_codes`: Thư viện 12 mã khuyết tật tiêu chuẩn ngành lốp (Song ngữ Việt - Anh): Bọt khí hông lốp, Lệch tâm hoa gai, Bavia quá dài, Móp méo tanh, Khuyết hoa gai, Đè mép mành thép X-Ray, Dãn cách mành không đều, Dị vật kim loại, Lực RFV vượt ngưỡng, Mất cân bằng động, Non lưu hóa.
- `master_operators`: Quản lý 8 công nhân viên vận hành bậc 1 đến bậc 5 theo các Ca làm việc (Ca A, Ca B, Ca C).
- `master_documents`: Quản lý tài liệu SOP/Work Instructions điện tử và ECN.

### 3.2. Nhóm Bán Thành Phẩm & Điều Độ Lệnh (Inventory & Planning)
- `inventory_components`: Quản lý kho cuộn/giá chứa bán thành phẩm theo Số lô Barcode (`LOT-TRD-...`, `LOT-SW-...`), thời gian sản xuất, vị trí giá đỡ và **hạn sử dụng (Shelf-life)**.
- `work_orders`: Lệnh sản xuất điều độ chuyền (Mã WO, Mục tiêu, Số lượng hoàn thành, Số lượng phế phẩm, Máy phân bổ, Độ ưu tiên).

### 3.3. Nhóm Điều Hành Shop Floor & Phả Hệ Lốp (Shop Floor Execution & Genealogy)
- `production_green_tires`: Bảng ghi nhận lốp sống sau khi rời máy TBM: Mã vạch GT (`GT-YYYYMMDD-XXXX`), Lệnh sản xuất, Người đóng, Trọng lượng thực tế, Trạng thái Poka-Yoke, và **7 mã lô hợp phần được khóa chặt vào phả hệ lốp**.
- `curing_press_cavities`: Trạng thái thời gian thực của từng hộc khuôn lò lưu hóa (Hộc L/Trái và Hộc R/Phải): Trạng thái (EMPTY, LOADED, CURING, COMPLETED), Nhiệt độ khuôn cảm biến PLC, Áp suất bàng bọng, Thời gian đếm ngược chu kỳ chín, và Bộ đếm tuổi thọ bàng bọng.
- `production_cured_tires`: Bảng ghi nhận lốp chín sau khi dỡ khỏi lò: Khắc Số Sê-ri Vĩnh Viễn (`VN-T-YYYYMMDD-XXXXX`), liên kết ngược về mã lốp sống GT, lò ép, hộc khuôn, thời gian nén nhiệt thực tế, thông số lưu hóa trung bình.
- `quality_inspections`: Bảng ghi nhận kết quả kiểm tra KCS độc lập: Soi ngoại quan, Soi cấu trúc X-Ray, Đo lực biến thiên hướng kính RFV, LFV, Khối lượng mất cân bằng động (g), Cấp phân loại tự động (`GRADE_A`, `GRADE_B`, `REWORK`, `SCRAP`), và Ghi chú xử lý.
- `tire_rework_history`: Nhật ký sửa hàng có khóa **Anti-Loop Interlock** tối đa 2 lần sửa chữa.
- `curing_telemetry_history`: Lịch sử vi phân nhiệt áp lưu hóa theo từng giây phục vụ phân tích SPC/CPK.
- `equipment_downtime_logs`: Nhật ký dừng máy sự cố/thay khuôn/bảo trì định kỳ phục vụ tính toán OEE.

### 3.4. Nhóm Tích Hợp IIoT & Trí Tuệ Nhân Tạo (IIoT Gateway & Industrial AI Suite)
- `gateway_connectors`: Cấu hình 5 giao thức công nghiệp kết nối PLC/SCADA (OPC-UA, OPC-DA, Modbus-TCP, MQTT, Sockets).
- `production_cycle_telemetry`: Dữ liệu chuỗi thời gian Takt Time và thời gian chờ hàng WIP.
- `ai_anomaly_logs`: Nhật ký phát hiện bất thường Takt Time (Isolation Forest & Deep Autoencoders).
- `bottleneck_forecasts` & `dynamic_routing_rules`: Dự báo tắc nghẽn 2-4h và ma trận điều hướng luồng vật tư động.
- `batch_process_telemetry` & `shap_root_cause_reports`: Phân tích căn nguyên đa biến XAI (TreeSHAP & Decision Trees) trên 19 thông số mẻ.
- `graph_genealogy_edges`, `graph_risk_propagation_runs` & `graph_order_risk_scores`: Mạng đồ thị phả hệ tri thức (Heterogeneous MPNN & RWR Diffusion) dự báo bán kính lây lan IATF 16949 Section 8.7.

---

## 4. CÁC TÍNH NĂNG NỔI BẬT ĐƯỢC XÂY DỰNG

### 4.1. Dashboard Điều Hành Thời Gian Thực (Executive SCADA Dashboard)
- Giám sát đồng thời các chỉ số cốt lõi của nhà máy:
  - **OEE (Overall Equipment Effectiveness)**: Tính toán tự động theo công thức $OEE = Availability \times Performance \times Quality$.
  - **FPY (First Pass Yield)**: Tỷ lệ lốp đạt chuẩn Hạng A ngay từ lần kiểm tra đầu tiên.
  - **Scrap Rate**: Tỷ lệ phế phẩm trên tổng sản lượng.
  - **Sản lượng ngày**: Số lốp sống đã đóng, lốp chín đã ra lò, số thiết bị đang Online.
- Sơ đồ dòng chảy sản xuất ISA-95 đa khu vực với trạng thái máy móc trực quan.
- Biểu đồ phân bổ cấp hạng lốp (Grade A / Grade B / Rework / Scrap).
- Biểu đồ Pareto phân tích nguyên nhân lỗi hàng đầu.
- Luồng sự kiện nhà xưởng (Live Event Stream) cập nhật liên tục mỗi 3 giây.

### 4.2. Trạm Thành Hình TBM Terminal & Cơ Chế Kiểm Soát Poka-Yoke
- Giao diện HMI công nghiệp dành cho công nhân máy đóng lốp VMI MAXX.
- **Cơ chế Poka-Yoke Interlock**: Khi công nhân quét mã vạch 7 hợp phần:
  - Hệ thống kiểm tra xem mã lô có tồn tại và còn tồn kho hay không.
  - Kiểm tra xem loại hợp phần và mã cao su có khớp 100% với định mức BOM của mã lốp hay không.
  - **Khóa an toàn hạn dùng cao su sống**: Nếu quét phải lô cao su quá hạn 48-72 giờ (cao su sống bắt đầu tự lưu hóa sơ bộ), hệ thống lập tức phát chuông cảnh báo đỏ, khóa nút đóng lốp và từ chối cho phép sản xuất!
- Tự động cấp mã vạch Lốp sống (`GT-YYYYMMDD-XXXX`) và hiển thị bản in nhãn mã vạch tiêu chuẩn công nghiệp.

### 4.3. Trạm SCADA Lò Lưu Hóa Lốp (Curing Presses Matrix)
- Ma trận giám sát toàn bộ các lò lưu hóa đôi (CP-01 đến CP-04) với hai hộc độc lập (Cavity L và Cavity R).
- Hiển thị thông số từ cảm biến nhiệt/áp thời gian thực: Nhiệt độ khuôn (°C), Áp suất bàng bọng (bar), Áp suất hơi vòm (bar).
- Thanh tiến trình đếm ngược chu kỳ lưu hóa trực quan.
- Cảnh báo tuổi thọ bàng lưu hóa (Bladder cycle counter) khi vượt quá 350 chu kỳ để phòng ngừa nổ bàng.
- Cho phép Nạp lốp sống ➔ Bắt đầu ép lưu hóa ➔ Dỡ lốp chín & Tự động cấp Số sê-ri lốp chuyển sang trạm KCS.
- Tích hợp nút **"⏩ Tua Nhanh Chín (Demo)"** giúp kỹ sư/người đánh giá trải nghiệm nhanh mà không cần chờ đủ 13 phút chu kỳ thực tế.

### 4.4. Trạm Kiểm Tra Hoàn Thiện & KCS (Finishing & Quality Gate)
- Hàng đợi lốp chín tự động tiếp nhận lốp ngay khi dỡ khỏi lò lưu hóa.
- Bàn thử nghiệm 3 công đoạn:
  1. **Ngoại quan (Visual Inspection)**: Đạt / Không Đạt kèm danh mục mã lỗi và vị trí khuyết tật.
  2. **Soi X-Ray (X-Ray Steel Belts)**: Soi cấu trúc mành thép đai, đo độ lệch mép mành (mm), phát hiện đè mép mành hoặc dị vật kim loại.
  3. **Độ đồng đều & Cân bằng động (UF Balancer)**: Đo biến thiên lực hướng kính (RFV trong đơn vị Newton), LFV, và khối lượng mất cân bằng (gram).
- **Cây quyết định phân loại tự động (Automated Grading Engine)**:
  - Nếu có lỗi Critical (Bọt khí, Đè mép mành X-Ray, Non lưu hóa) ➔ **PHẾ PHẨM (SCRAP)**, tự động trừ vào tỷ lệ FPY và ghi tăng phế phẩm trong Lệnh sản xuất.
  - Nếu có lỗi Major hoặc lực RFV > 80N ➔ **HẠNG B (GRADE B)** tiêu thụ thị trường thay thế.
  - Nếu có lỗi Minor (Bavia quá dài) ➔ **TÁI CHẾ (REWORK)** chuyển sang mài tỉa.
  - Nếu hoàn hảo ➔ **HẠNG A (GRADE A)** cấp chứng nhận OE First Class xuất khẩu.

### 4.5. Hộ Chiếu Số Lốp & Truy Xuất Nguồn Gốc 100% (Digital Tire Passport)
- Cho phép tra cứu bất kỳ Số sê-ri lốp (`VN-T-...`) hoặc Mã lốp sống (`GT-...`).
- Hiển thị trọn vẹn **Cây phả hệ sản xuất 5 giai đoạn khép kín**:
  1. Mẻ cao su Banbury, độ nhớt Mooney ML(1+4), thử nghiệm lưu hóa kế.
  2. Toàn bộ 7 mã lô bán thành phẩm cấu thành, ngày sản xuất và vị trí lưu kho.
  3. Máy đóng lốp, công nhân vận hành, thời gian đóng và trọng lượng thực tế.
  4. Lò lưu hóa, hộc khuôn, mã khuôn hoa gai, thời gian nén và biểu đồ nhiệt áp thực tế.
  5. Kết quả kiểm tra KCS, thông số X-Ray, giá trị RFV/LFV/Balance và cấp chứng chỉ sản phẩm.
- Hỗ trợ xem và in Giấy Chứng Nhận Hộ Chiếu Số Lốp đạt chuẩn kiểm định.

---

## 5. HƯỚNG DẪN CÀI ĐẶT & KHỞI CHẠY HỆ THỐNG

### 5.1. Yêu cầu môi trường
- Python 3.10 trở lên (Đã kiểm thử hoàn hảo trên Python 3.13)
- Trình duyệt web hiện đại (Google Chrome, Microsoft Edge, Firefox)

### 5.2. Khởi chạy 1-Click trên Windows
Bạn chỉ cần nhấp đúp chuột vào tệp:
```cmd
run.bat
```
Tệp batch sẽ tự động:
1. Kiểm tra môi trường Python.
2. Khởi động máy chủ MES FastAPI tại cổng `http://localhost:8000`.
3. Tự động mở trình duyệt web hiển thị Dashboard điều hành.

### 5.3. Khởi chạy thủ công qua Terminal / Command Prompt
```bash
# 1. Cài đặt các gói thư viện (nếu chưa có)
pip install -r requirements.txt

# 2. Khởi động máy chủ MES
python main.py
```

Sau đó mở trình duyệt và truy cập:
- **Giao diện Dashboard MES**: [http://localhost:8000](http://localhost:8000)
- **Tài liệu Swagger API Interactive**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5.4. Chạy bộ kiểm thử tự động (Unit & Integration Tests)
```bash
python tests/test_mes_api.py
```
Toàn bộ kịch bản kiểm thử logic nghiệp vụ (Poka-Yoke, Vòng đời lưu hóa, Phân loại KCS, Phả hệ lốp) sẽ được thực thi và báo cáo kết quả.

---

## 6. KỊCH BẢN TRẢI NGHIỆM ĐƯỢC ĐỀ XUẤT (STEP-BY-STEP DEMO)

Để đánh giá toàn diện năng lực của ứng dụng Mini MES:

1. **Trải nghiệm Poka-Yoke tại Trạm Thành Hình TBM**:
   - Chuyển sang Tab **"3. Trạm Thành Hình TBM"**.
   - Bấm nút **"⚠️ Thử Nạp Lô HẾT HẠN (Poka-Yoke Alarm Demo!)"**.
   - Quan sát hệ thống lập tức khóa an toàn, phát còi cảnh báo màu đỏ giải thích lô cao su mặt lốp `LOT-EXP-TRD-999` đã quá hạn sử dụng và từ chối đóng lốp.
   - Bấm nút **"⚡ Nạp Nhanh Lô Hợp Lệ"** để chuyển sang các lô đạt chuẩn ➔ Nút **"KÍCH HOẠT ĐÓNG LỐP"** sáng xanh ➔ Bấm để đóng lốp và xem nhãn Barcode lốp sống vừa sinh ra.

2. **Trải nghiệm Quy Trình Ép Lưu Hóa & Cấp Sê-ri Lốp**:
   - Chuyển sang Tab **"4. Trạm Lưu Hóa Lốp"**.
   - Chọn hộc trống (ví dụ `CP-02 Hộc L`) ➔ Bấm **"+ Nạp Lốp Sống"** (mã vừa đóng hoặc mã mặc định).
   - Bấm **"🔥 Bắt Đầu Ép Lưu Hóa"** ➔ Quan sát nhiệt độ 170°C và áp suất bàng bọng 21 bar bơm vào, thời gian bắt đầu đếm ngược.
   - Bấm **"⏩ Tua Nhanh Chín (Demo)"** để hoàn tất ngay chu kỳ.
   - Bấm **"📦 Dỡ Lốp Chín & Cấp Sê-ri"** ➔ Xem số sê-ri lốp vĩnh viễn (`VN-T-...`) được khắc và chuyển sang hàng đợi KCS.

3. **Trải nghiệm Nghiệm Thu KCS & Tự Động Phân Hạng**:
   - Chuyển sang Tab **"5. Trạm KCS & Hoàn Thiện"**.
   - Chọn chiếc lốp vừa ra lò từ danh sách bên trái.
   - Thử nghiệm đánh dấu một lỗi nghiêm trọng (ví dụ chọn X-Ray = Không Đạt với lỗi `DEF-XRAY-01: Đè mép mành thép`) ➔ Bấm **"XÁC NHẬN KẾT QUẢ KCS"** ➔ Hệ thống tự động phân loại thành `PHẾ PHẨM (SCRAP)` và cập nhật vào báo cáo phế phẩm của Lệnh sản xuất.
   - Thử nghiệm với một chiếc lốp hoàn hảo để được cấp `HẠNG A (GRADE A)`.

4. **Trải nghiệm Tra Cứu Hộ Chiếu Số Lốp 100%**:
   - Chuyển sang Tab **"6. Truy Xuất Nguồn Gốc 100%"**.
   - Bấm vào các nút mẫu thử nghiệm nhanh:
     - `✨ Lốp Hạng A Xuất Khẩu (VN-T-202610-00101)`
     - `⚠️ Lốp Hạng B Thương Mại (VN-T-202610-00105)`
     - `❌ Lốp Phế Phẩm X-Ray (VN-T-202610-00108)`
   - Khám phá trọn vẹn từng mẻ cao su Banbury, cuộn mành thép, công nhân đóng lốp, thông số lò lưu hóa đến KCS.

---

## 7. CẤU TRÚC THƯ MỤC DỰ ÁN

```
c:\Users\Tuan\Downloads\MES\
├── app/
│   ├── database.py              # Schema SQLite chuẩn ISA-95 & kết nối WAL
│   ├── models.py                # Pydantic Schemas & DTOs
│   ├── seed_data.py             # Dữ liệu mẫu chuẩn nhà máy lốp xe thực tế
│   ├── simulator.py             # Bộ mô phỏng cảm biến IoT SCADA Curing Press
│   ├── routers/
│   │   ├── dashboard.py         # KPIs OEE, FPY, Scrap rate, Lines status
│   │   ├── work_orders.py       # Quản lý Lệnh sản xuất & Kế hoạch
│   │   ├── tbm.py               # Trạm đóng lốp TBM & Poka-Yoke Scanning
│   │   ├── curing.py            # SCADA Lò lưu hóa & Quản lý bàng bọng
│   │   ├── quality.py           # KCS Ngoại quan, X-Ray, UF Balancer & Grading
│   │   ├── genealogy.py         # Hộ chiếu số Digital Tire Passport 100%
│   │   └── master_data.py       # Quản lý SKU, BOM, Đơn công nghệ, Mã lỗi
│   └── static/                  # Single Page Application Frontend
│       ├── index.html           # Giao diện Dashboard SCADA Dark Mode
│       ├── css/
│       │   └── style.css        # Thiết kế chuẩn HMI công nghiệp
│       └── js/
│           └── app.js           # Bộ điều khiển State & SCADA Polling
├── database/
│   └── tire_mes.db              # Tệp Cơ sở dữ liệu SQLite
├── tests/
│   └── test_mes_api.py          # Bộ kiểm thử tự động toàn diện
├── main.py                      # FastAPI Application Server Entrypoint
├── run.bat                      # Kịch bản 1-click khởi chạy trên Windows
├── requirements.txt             # Danh sách gói phụ thuộc Python
└── README.md                    # Tài liệu đặc tả kỹ thuật & vận hành
```

---
*Bản quyền dự án & Kiến trúc kỹ thuật: Senior Tire MES Engineer (10+ Years Manufacturing Excellence).*
