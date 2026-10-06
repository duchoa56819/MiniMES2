"""
Comprehensive Seed Dataset for Tire Plant MES.
Populates standard tire industry master data, BOMs, recipes, inventory lots,
work orders, operators, defect codes, and historical tire genealogy.
"""

from datetime import datetime, timedelta
from app.database import get_db, init_db


def seed_database():
    """Populates the database with realistic industrial tire manufacturing data."""
    init_db(force=True)

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()

        # =====================================================================
        # 1. MASTER AREAS
        # =====================================================================
        areas = [
            ("MIXING", "Luyện Kín Cao Su (Banbury Mixing)", "Khu vực luyện kín Masterbatch & Finalbatch, kiểm tra độ nhớt Mooney & lưu hóa kế", 1),
            ("PREP", "Bán Thành Phẩm (Component Prep)", "Đùn mặt lốp, hông lốp, cán mành thép, mành sợi, cán màng kín khí, cuộn tanh", 2),
            ("TBM", "Thành Hình Lốp (Tire Building)", "Đóng lốp 1 giai đoạn (Uni-stage) & 2 giai đoạn tạo lốp sống (Green Tire)", 3),
            ("CURING", "Lưu Hóa (Curing & Vulcanization)", "Ép lưu hóa nhiệt áp lực cao bằng lò lưu hóa thủy lực và khuôn segmented", 4),
            ("FINISHING", "Kiểm Tra Hoàn Thiện & KCS (Finishing & QC)", "Kiểm tra ngoại quan, soi cấu trúc X-Ray, đo cân bằng động và lực đồng đều UF", 5),
            ("WAREHOUSE", "Kho Thành Phẩm & Xuất Xưởng (Warehouse)", "Dán mã vạch lưu thông, phân loại cấp hạng (Grade A/B), đóng gói xuất kho", 6),
        ]
        cursor.executemany("INSERT INTO master_areas VALUES (?, ?, ?, ?)", areas)

        # =====================================================================
        # 2. MASTER EQUIPMENT
        # =====================================================================
        equipment = [
            ("MIX-01", "Máy Luyện Banbury BB-270", "MIXING", "Kobe Steel 270L Mixer", "RUNNING", 1, 180, None, 14200, "2026-09-15", 92.5),
            ("EXT-01", "Dây Chuyền Đùn Mặt Lốp Triplex", "PREP", "KraussMaffei Quadruplex 4-Roll", "RUNNING", 1, 12, None, 85600, "2026-09-20", 88.0),
            ("CAL-01", "Máy Cán Mành Thép 4 Trục", "PREP", "Comerio Ercole 4-Roll Calender", "RUNNING", 1, 30, None, 45100, "2026-09-18", 89.2),
            ("TBM-01", "Máy Đóng Lốp PCR TBM-01", "TBM", "VMI MAXX Uni-Stage PCR Builder", "RUNNING", 1, 45, "WO-2026-001", 32800, "2026-09-25", 91.0),
            ("TBM-02", "Máy Đóng Lốp TBR TBM-02", "TBM", "HF Tire Tech 2-Stage TBR Builder", "RUNNING", 1, 90, "WO-2026-004", 18400, "2026-09-22", 86.5),
            ("CP-01", "Lò Lưu Hóa Thủy Lực CP-01 (63.5\")", "CURING", "Herbert Dual Hydraulic 63.5\"", "RUNNING", 2, 780, "WO-2026-001", 24600, "2026-09-28", 94.0),
            ("CP-02", "Lò Lưu Hóa Cơ Khí CP-02 (63.5\")", "CURING", "Krupp Dual Mechanical 63.5\"", "RUNNING", 2, 780, "WO-2026-001", 31200, "2026-09-26", 90.5),
            ("CP-03", "Lò Lưu Hóa Du Lịch CP-03 (55\")", "CURING", "McNeil Dual Dome Press 55\"", "RUNNING", 2, 840, "WO-2026-002", 28900, "2026-09-24", 93.0),
            ("CP-04", "Lò Lưu Hóa Xe Tải CP-04 (75\")", "CURING", "Continental TBR Giant Press 75\"", "RUNNING", 2, 2400, "WO-2026-004", 9400, "2026-09-10", 87.5),
            ("XR-01", "Hệ Thống Soi X-Ray Lốp Tự Động", "FINISHING", "Yxlon MTIS Automated Tire X-Ray", "RUNNING", 1, 35, None, 92100, "2026-09-29", 96.0),
            ("UF-01", "Máy Đo Đồng Đều & Cân Bằng Động UF", "FINISHING", "Hofmann Universal Dynamic Balancer", "RUNNING", 1, 28, None, 88700, "2026-09-27", 95.5),
        ]
        cursor.executemany("INSERT INTO master_equipment VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", equipment)

        # =====================================================================
        # 3. MASTER PRODUCTS (SKUs)
        # =====================================================================
        products = [
            (
                "PCR-205-55R16-91V", "205/55R16", "TURBO-GRIP T7", "PCR", "91", "V",
                9.25, 0.25, 45, 780, 170.0, 21.0,
                "Lốp du lịch cao cấp cho sedan phân khúc C (Toyota Corolla, Mazda 3, Kia Cerato). Lực cản lăn thấp, bám đường ướt hạng A."
            ),
            (
                "PCR-225-60R17-99H", "225/60R17", "ECO-SUV S2", "PCR", "99", "H",
                12.10, 0.30, 52, 840, 168.0, 20.5,
                "Lốp đa dụng gầm cao Crossover/SUV (Honda CR-V, Tucson, CX-5). Bền bỉ trên đường trường và đường hỗn hợp."
            ),
            (
                "EV-245-45R19-102Y", "245/45R19", "AERO-SILENT EV9", "EV", "102", "Y",
                11.45, 0.20, 50, 760, 172.0, 21.5,
                "Lốp xe điện siêu êm UHP (VinFast VF8, Tesla Model 3). Foam tiêu âm Polyurethane bên trong màng lót, chịu tải nặng mô-men xoắn cao."
            ),
            (
                "TBR-315-80R22.5-156K", "315/80R22.5", "HEAVY-MAX H8", "TBR", "156/150", "K",
                68.50, 1.20, 110, 2400, 150.0, 22.0,
                "Lốp xe tải nặng toàn thép (All-Steel Radial) đường trường tải trọng cao. Kháng rách chém, khả năng dán đắp gai 3 lần."
            ),
            (
                "TBR-11R22.5-148L", "11R22.5", "ROAD-MASTER R5", "TBR", "148/145", "L",
                54.20, 0.90, 95, 2100, 152.0, 21.8,
                "Lốp xe khách giường nằm liên tỉnh và xe tải trung. Gai dẫn hướng chạy êm, mòn đều, tiết kiệm nhiên liệu."
            ),
        ]
        cursor.executemany("INSERT INTO master_products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", products)

        # =====================================================================
        # 4. MASTER BOMS (Bill of Materials)
        # =====================================================================
        boms = [
            # PCR-205-55R16-91V
            ("PCR-205-55R16-91V", "TREAD", "TRD-SP-205", "CP-TRD-101", 3.20, "KG"),
            ("PCR-205-55R16-91V", "SIDEWALL", "SW-SP-16", "CP-SW-202", 1.85, "KG"),
            ("PCR-205-55R16-91V", "BELT_1", "ST-BLT-1-205", "CP-SK-404", 1.15, "KG"),
            ("PCR-205-55R16-91V", "BELT_2", "ST-BLT-2-205", "CP-SK-404", 1.10, "KG"),
            ("PCR-205-55R16-91V", "PLY", "PLY-POLY-16", "CP-SK-404", 0.75, "KG"),
            ("PCR-205-55R16-91V", "BEAD", "BD-RING-16-HEX", "CP-BD-505", 0.65, "KG"),
            ("PCR-205-55R16-91V", "INNERLINER", "INL-BIIR-205", "CP-INL-303", 0.55, "KG"),

            # PCR-225-60R17-99H
            ("PCR-225-60R17-99H", "TREAD", "TRD-SP-225", "CP-TRD-101", 4.10, "KG"),
            ("PCR-225-60R17-99H", "SIDEWALL", "SW-SP-17", "CP-SW-202", 2.30, "KG"),
            ("PCR-225-60R17-99H", "BELT_1", "ST-BLT-1-225", "CP-SK-404", 1.50, "KG"),
            ("PCR-225-60R17-99H", "BELT_2", "ST-BLT-2-225", "CP-SK-404", 1.45, "KG"),
            ("PCR-225-60R17-99H", "PLY", "PLY-POLY-17", "CP-SK-404", 1.05, "KG"),
            ("PCR-225-60R17-99H", "BEAD", "BD-RING-17-HEX", "CP-BD-505", 0.90, "KG"),
            ("PCR-225-60R17-99H", "INNERLINER", "INL-BIIR-225", "CP-INL-303", 0.80, "KG"),

            # EV-245-45R19-102Y
            ("EV-245-45R19-102Y", "TREAD", "TRD-EV-245", "CP-TRD-102", 3.85, "KG"),
            ("EV-245-45R19-102Y", "SIDEWALL", "SW-EV-19", "CP-SW-202", 2.10, "KG"),
            ("EV-245-45R19-102Y", "BELT_1", "ST-BLT-1-245", "CP-SK-404", 1.40, "KG"),
            ("EV-245-45R19-102Y", "BELT_2", "ST-BLT-2-245", "CP-SK-404", 1.35, "KG"),
            ("EV-245-45R19-102Y", "PLY", "PLY-ARAMID-19", "CP-SK-404", 0.95, "KG"),
            ("EV-245-45R19-102Y", "BEAD", "BD-RING-19-HEX", "CP-BD-505", 0.90, "KG"),
            ("EV-245-45R19-102Y", "INNERLINER", "INL-FOAM-245", "CP-INL-303", 0.90, "KG"),

            # TBR-315-80R22.5-156K
            ("TBR-315-80R22.5-156K", "TREAD", "TRD-TBR-315", "CP-TRD-103", 24.50, "KG"),
            ("TBR-315-80R22.5-156K", "SIDEWALL", "SW-TBR-225", "CP-SW-203", 11.20, "KG"),
            ("TBR-315-80R22.5-156K", "BELT_1", "ST-TBR-BLT1", "CP-SK-404", 7.80, "KG"),
            ("TBR-315-80R22.5-156K", "BELT_2", "ST-TBR-BLT2", "CP-SK-404", 7.60, "KG"),
            ("TBR-315-80R22.5-156K", "PLY", "PLY-STEEL-TBR", "CP-SK-404", 8.90, "KG"),
            ("TBR-315-80R22.5-156K", "BEAD", "BD-TBR-HEAVY", "CP-BD-506", 5.10, "KG"),
            ("TBR-315-80R22.5-156K", "INNERLINER", "INL-TBR-315", "CP-INL-303", 3.40, "KG"),

            # TBR-11R22.5-148L
            ("TBR-11R22.5-148L", "TREAD", "TRD-TBR-11R", "CP-TRD-103", 19.80, "KG"),
            ("TBR-11R22.5-148L", "SIDEWALL", "SW-TBR-11R", "CP-SW-203", 9.40, "KG"),
            ("TBR-11R22.5-148L", "BELT_1", "ST-TBR-11R-B1", "CP-SK-404", 6.20, "KG"),
            ("TBR-11R22.5-148L", "BELT_2", "ST-TBR-11R-B2", "CP-SK-404", 5.90, "KG"),
            ("TBR-11R22.5-148L", "PLY", "PLY-STEEL-11R", "CP-SK-404", 7.10, "KG"),
            ("TBR-11R22.5-148L", "BEAD", "BD-TBR-11R", "CP-BD-506", 4.20, "KG"),
            ("TBR-11R22.5-148L", "INNERLINER", "INL-TBR-11R", "CP-INL-303", 2.60, "KG"),
        ]
        cursor.executemany("INSERT INTO master_boms (sku, component_type, spec_code, compound_code, standard_qty, unit) VALUES (?, ?, ?, ?, ?, ?)", boms)

        # =====================================================================
        # 5. MASTER CURING RECIPES
        # =====================================================================
        recipes = [
            ("RCP-PCR-205-55R16", "PCR-205-55R16-91V", 780, 170.0, 2.0, 15.2, 21.0, 40, 350),
            ("RCP-PCR-225-60R17", "PCR-225-60R17-99H", 840, 168.0, 2.0, 15.0, 20.5, 45, 350),
            ("RCP-EV-245-45R19", "EV-245-45R19-102Y", 760, 172.0, 1.5, 15.5, 21.5, 35, 300),
            ("RCP-TBR-315-80R22", "TBR-315-80R22.5-156K", 2400, 150.0, 2.5, 14.5, 22.0, 60, 250),
            ("RCP-TBR-11R22.5", "TBR-11R22.5-148L", 2100, 152.0, 2.5, 14.8, 21.8, 55, 250),
        ]
        cursor.executemany("INSERT INTO master_curing_recipes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", recipes)

        # =====================================================================
        # 6. MASTER DEFECT CODES
        # =====================================================================
        defects = [
            ("DEF-VIS-01", "Bọt khí hông lốp", "Sidewall Blister / Air Pocket", "VISUAL", "CRITICAL", "SCRAP", "CURING"),
            ("DEF-VIS-02", "Lệch tâm gai mặt lốp", "Tread Off-center / Dog-leg Splice", "VISUAL", "MAJOR", "GRADE_B", "TBM"),
            ("DEF-VIS-03", "Bavia lỗ thoát khí quá dài", "Excess Vent Spew / Heavy Flash", "VISUAL", "MINOR", "REWORK", "CURING"),
            ("DEF-VIS-04", "Vẹo mép tanh / Biến dạng tanh", "Bead Distortion / Folded Bead", "VISUAL", "CRITICAL", "SCRAP", "TBM"),
            ("DEF-VIS-05", "Khuyết cao su hoa gai", "Mold Bare / Rubber Shortage", "VISUAL", "MAJOR", "GRADE_B", "CURING"),
            ("DEF-VIS-06", "Hở nối lớp lót kín khí", "Innerliner Open Splice", "VISUAL", "CRITICAL", "SCRAP", "TBM"),
            ("DEF-XRAY-01", "Đè mép mành thép Belt 1 & 2", "Belt Crossing / Overlap Flaw", "XRAY", "CRITICAL", "SCRAP", "PREP"),
            ("DEF-XRAY-02", "Mành thép bị dãn cách không đều", "Cord Wave / Wide Spacing", "XRAY", "MAJOR", "GRADE_B", "PREP"),
            ("DEF-XRAY-03", "Dị vật kim loại trong lốp", "Foreign Metallic Inclusions", "XRAY", "CRITICAL", "SCRAP", "MIXING"),
            ("DEF-UNIF-01", "Lực hướng kính biến thiên cao (RFV)", "High Radial Force Variation (>90N)", "UNIFORMITY", "MAJOR", "GRADE_B", "TBM"),
            ("DEF-UNIF-02", "Mất cân bằng động quá lớn", "Dynamic Imbalance (>40g)", "UNIFORMITY", "MINOR", "REWORK", "CURING"),
            ("DEF-CUR-01", "Non lưu hóa do tụt nhiệt áp lò", "Under-cure by Pressure Drop", "ALL", "CRITICAL", "SCRAP", "CURING"),
        ]
        cursor.executemany("INSERT INTO master_defect_codes VALUES (?, ?, ?, ?, ?, ?, ?)", defects)

        # =====================================================================
        # 7. MASTER OPERATORS
        # =====================================================================
        operators = [
            ("OP-1001", "Nguyễn Văn Hùng", "TBM_OPERATOR", "SHIFT_A", 5),
            ("OP-1002", "Trần Quốc Toản", "TBM_OPERATOR", "SHIFT_B", 4),
            ("OP-1003", "Đặng Văn Lâm", "TBM_OPERATOR", "SHIFT_C", 3),
            ("OP-2001", "Lê Hoàng Nam", "CURING_TECH", "SHIFT_A", 5),
            ("OP-2002", "Phạm Minh Tuấn", "CURING_TECH", "SHIFT_B", 4),
            ("OP-3001", "Đỗ Thị Mai", "QC_INSPECTOR", "SHIFT_A", 5),
            ("OP-3002", "Hoàng Đức Trọng", "QC_INSPECTOR", "SHIFT_B", 4),
            ("OP-4001", "Vũ Đình Phong", "SUPERVISOR", "SHIFT_A", 5),
        ]
        cursor.executemany("INSERT INTO master_operators VALUES (?, ?, ?, ?, ?)", operators)

        # =====================================================================
        # 8. INVENTORY COMPONENTS (Semi-finished components with Shelf-Life)
        # =====================================================================
        valid_exp = (now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        past_prod = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        expired_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        old_prod = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")

        components = [
            # Lots for PCR-205-55R16-91V
            ("LOT-TRD-202610-01", "TREAD", "TRD-SP-205", "CP-TRD-101", past_prod, valid_exp, 45, "AVAILABLE", "RACK-TRD-01", "BB-MB-8921"),
            ("LOT-SW-202610-01", "SIDEWALL", "SW-SP-16", "CP-SW-202", past_prod, valid_exp, 60, "AVAILABLE", "RACK-SW-01", "BB-MB-8922"),
            ("LOT-BLT1-202610-01", "BELT_1", "ST-BLT-1-205", "CP-SK-404", past_prod, valid_exp, 80, "AVAILABLE", "CART-BLT-01", "CAL-BATCH-104"),
            ("LOT-BLT2-202610-01", "BELT_2", "ST-BLT-2-205", "CP-SK-404", past_prod, valid_exp, 80, "AVAILABLE", "CART-BLT-02", "CAL-BATCH-105"),
            ("LOT-PLY-202610-01", "PLY", "PLY-POLY-16", "CP-SK-404", past_prod, valid_exp, 90, "AVAILABLE", "SPOOL-PLY-01", "CAL-BATCH-106"),
            ("LOT-BD-202610-01", "BEAD", "BD-RING-16-HEX", "CP-BD-505", past_prod, valid_exp, 120, "AVAILABLE", "BIN-BD-01", "BD-WIND-088"),
            ("LOT-INL-202610-01", "INNERLINER", "INL-BIIR-205", "CP-INL-303", past_prod, valid_exp, 55, "AVAILABLE", "ROLL-INL-01", "CAL-INL-302"),

            # Lots for PCR-225-60R17-99H
            ("LOT-TRD-202610-02", "TREAD", "TRD-SP-225", "CP-TRD-101", past_prod, valid_exp, 35, "AVAILABLE", "RACK-TRD-02", "BB-MB-8923"),
            ("LOT-SW-202610-02", "SIDEWALL", "SW-SP-17", "CP-SW-202", past_prod, valid_exp, 40, "AVAILABLE", "RACK-SW-02", "BB-MB-8924"),
            ("LOT-BLT1-202610-02", "BELT_1", "ST-BLT-1-225", "CP-SK-404", past_prod, valid_exp, 50, "AVAILABLE", "CART-BLT-03", "CAL-BATCH-107"),
            ("LOT-BLT2-202610-02", "BELT_2", "ST-BLT-2-225", "CP-SK-404", past_prod, valid_exp, 50, "AVAILABLE", "CART-BLT-04", "CAL-BATCH-108"),
            ("LOT-PLY-202610-02", "PLY", "PLY-POLY-17", "CP-SK-404", past_prod, valid_exp, 65, "AVAILABLE", "SPOOL-PLY-02", "CAL-BATCH-109"),
            ("LOT-BD-202610-02", "BEAD", "BD-RING-17-HEX", "CP-BD-505", past_prod, valid_exp, 80, "AVAILABLE", "BIN-BD-02", "BD-WIND-089"),
            ("LOT-INL-202610-02", "INNERLINER", "INL-BIIR-225", "CP-INL-303", past_prod, valid_exp, 45, "AVAILABLE", "ROLL-INL-02", "CAL-INL-303"),

            # Expired lot for Poka-Yoke refusal demo
            ("LOT-EXP-TRD-999", "TREAD", "TRD-SP-205", "CP-TRD-101", old_prod, expired_time, 15, "EXPIRED", "QUARANTINE-01", "BB-MB-8500"),
        ]
        cursor.executemany("INSERT INTO inventory_components VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", components)

        # =====================================================================
        # 9. WORK ORDERS
        # =====================================================================
        wos = [
            ("WO-2026-001", "PCR-205-55R16-91V", 250, 185, 3, (now - timedelta(hours=8)).strftime("%Y-%m-%d 06:00"), (now + timedelta(hours=6)).strftime("%Y-%m-%d 22:00"), (now - timedelta(hours=8)).strftime("%Y-%m-%d 06:15"), None, "IN_PROGRESS", "HIGH", "TBM-01", now_str),
            ("WO-2026-002", "PCR-225-60R17-99H", 180, 120, 2, (now - timedelta(hours=5)).strftime("%Y-%m-%d 08:00"), (now + timedelta(hours=8)).strftime("%Y-%m-%d 20:00"), (now - timedelta(hours=5)).strftime("%Y-%m-%d 08:10"), None, "IN_PROGRESS", "NORMAL", "TBM-01", now_str),
            ("WO-2026-003", "EV-245-45R19-102Y", 100, 95, 1, (now - timedelta(hours=14)).strftime("%Y-%m-%d 00:00"), (now - timedelta(hours=2)).strftime("%Y-%m-%d 12:00"), (now - timedelta(hours=14)).strftime("%Y-%m-%d 00:20"), (now - timedelta(hours=2)).strftime("%Y-%m-%d 11:45"), "COMPLETED", "URGENT", "TBM-01", now_str),
            ("WO-2026-004", "TBR-315-80R22.5-156K", 60, 28, 1, (now - timedelta(hours=10)).strftime("%Y-%m-%d 06:00"), (now + timedelta(hours=12)).strftime("%Y-%m-%d 23:59"), (now - timedelta(hours=10)).strftime("%Y-%m-%d 06:30"), None, "IN_PROGRESS", "NORMAL", "TBM-02", now_str),
            ("WO-2026-005", "TBR-11R22.5-148L", 80, 0, 0, (now + timedelta(hours=4)).strftime("%Y-%m-%d 14:00"), (now + timedelta(hours=18)).strftime("%Y-%m-%d 06:00"), None, None, "RELEASED", "NORMAL", "TBM-02", now_str),
        ]
        cursor.executemany("INSERT INTO work_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", wos)

        # =====================================================================
        # 10. CURING PRESS CAVITIES LIVE STATE
        # =====================================================================
        cavities = [
            ("CP-01", "L", "MLD-16-042", "GT-202610-0019", "VN-T-202610-00119", "CURING", (now - timedelta(seconds=420)).strftime("%Y-%m-%d %H:%M:%S"), 780, 420, 170.2, 21.1, 15.2, 142),
            ("CP-01", "R", "MLD-16-043", "GT-202610-0020", "VN-T-202610-00120", "CURING", (now - timedelta(seconds=690)).strftime("%Y-%m-%d %H:%M:%S"), 780, 690, 169.8, 20.9, 15.1, 143),
            ("CP-02", "L", "MLD-16-055", None, None, "EMPTY", None, 780, 0, 170.0, 0.0, 15.0, 280),
            ("CP-02", "R", "MLD-16-056", "GT-202610-0021", "VN-T-202610-00121", "COMPLETED", (now - timedelta(seconds=790)).strftime("%Y-%m-%d %H:%M:%S"), 780, 780, 169.5, 0.5, 14.9, 281),
            ("CP-03", "L", "MLD-17-010", "GT-202610-0022", "VN-T-202610-00122", "CURING", (now - timedelta(seconds=310)).strftime("%Y-%m-%d %H:%M:%S"), 840, 310, 168.1, 20.6, 15.0, 95),
            ("CP-03", "R", "MLD-17-011", None, None, "EMPTY", None, 840, 0, 168.0, 0.0, 15.0, 96),
            ("CP-04", "L", "MLD-TBR-01", "GT-202610-0023", "VN-T-202610-00123", "CURING", (now - timedelta(seconds=1500)).strftime("%Y-%m-%d %H:%M:%S"), 2400, 1500, 150.3, 22.0, 14.6, 88),
            ("CP-04", "R", "MLD-TBR-02", None, None, "EMPTY", None, 2400, 0, 150.0, 0.0, 14.5, 89),
        ]
        cursor.executemany("INSERT INTO curing_press_cavities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", cavities)

        # =====================================================================
        # 11. HISTORICAL PRODUCTION TIRES (GENEALOGY & TRACEABILITY)
        # =====================================================================
        # Seed 18 realistic historical tires spanning Grade A, Grade B, Rework, Scrap
        for i in range(1, 19):
            gt_id = f"GT-202610-{i:04d}"
            tire_serial = f"VN-T-202610-{100+i:05d}"
            build_time = (now - timedelta(hours=6, minutes=30 - i*8)).strftime("%Y-%m-%d %H:%M:%S")
            cure_start = (now - timedelta(hours=5, minutes=20 - i*8)).strftime("%Y-%m-%d %H:%M:%S")
            cure_end = (now - timedelta(hours=5, minutes=7 - i*8)).strftime("%Y-%m-%d %H:%M:%S")
            insp_time = (now - timedelta(hours=4, minutes=45 - i*8)).strftime("%Y-%m-%d %H:%M:%S")

            sku = "PCR-205-55R16-91V"
            weight = round(9.20 + (i % 5) * 0.03, 2)
            press = "CP-01" if i % 2 == 1 else "CP-02"
            cavity = "L" if i % 4 < 2 else "R"
            mold = f"MLD-16-04{i%4 + 2}"

            # TBM Green Tire
            cursor.execute("""
                INSERT INTO production_green_tires VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gt_id, "WO-2026-001", sku, "TBM-01", "OP-1001" if i % 2 == 1 else "OP-1002",
                build_time, weight, "LOT-TRD-202610-01", "LOT-SW-202610-01",
                "LOT-BLT1-202610-01", "LOT-BLT2-202610-01", "LOT-PLY-202610-01",
                "LOT-BD-202610-01", "LOT-INL-202610-01", "VERIFIED_PASS", "CURED"
            ))

            # Curing Record
            cure_quality = "PASS"
            if i == 14:
                cure_quality = "PRESSURE_DROP"

            cursor.execute("""
                INSERT INTO production_cured_tires VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tire_serial, gt_id, sku, press, cavity, mold, "RCP-PCR-205-55R16",
                cure_start, cure_end, 780, 170.1 if i != 14 else 164.2,
                21.0 if i != 14 else 17.5, cure_quality, "INSPECTED"
            ))

            # Quality Inspection Record
            if i == 5:
                # Grade B due to slight tread off-center
                cursor.execute("""
                    INSERT INTO quality_inspections (tire_serial, inspection_timestamp, inspector_id, visual_result, visual_defect_code, defect_location, xray_result, xray_defect_code, belt_alignment_mm, uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g, final_grade, passed, disposition_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tire_serial, insp_time, "OP-3001", "FAIL", "DEF-VIS-02", "Mặt lốp lệch 1.8mm", "PASS", None, 0.4, 62.0, 24.0, 22.0, "GRADE_B", 1, "Đạt chuẩn xuất bán thương mại aftermarket, không đạt xuất khẩu OEM"
                ))
            elif i == 8:
                # Scrap due to Belt Crossing on X-Ray
                cursor.execute("""
                    INSERT INTO quality_inspections (tire_serial, inspection_timestamp, inspector_id, visual_result, visual_defect_code, defect_location, xray_result, xray_defect_code, belt_alignment_mm, uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g, final_grade, passed, disposition_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tire_serial, insp_time, "OP-3002", "PASS", None, None, "FAIL", "DEF-XRAY-01", 3.2, 98.0, 48.0, 38.0, "SCRAP", 0, "Mép mành thép Belt 1 đè chéo Belt 2 vượt giới hạn 2.0mm. Đã cắt tanh phế phẩm."
                ))
            elif i == 11:
                # Rework due to Excess Vent Spew
                cursor.execute("""
                    INSERT INTO quality_inspections (tire_serial, inspection_timestamp, inspector_id, visual_result, visual_defect_code, defect_location, xray_result, xray_defect_code, belt_alignment_mm, uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g, final_grade, passed, disposition_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tire_serial, insp_time, "OP-3001", "FAIL", "DEF-VIS-03", "Khuôn vai lốp", "PASS", None, 0.2, 44.0, 19.0, 21.0, "REWORK", 1, "Bavia lỗ thoát khí dài > 10mm. Chuyển trạm cắt tỉa hoàn thiện thủ công."
                ))
            elif i == 14:
                # Scrap due to under-cure (pressure drop during vulcanization)
                cursor.execute("""
                    INSERT INTO quality_inspections (tire_serial, inspection_timestamp, inspector_id, visual_result, visual_defect_code, defect_location, xray_result, xray_defect_code, belt_alignment_mm, uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g, final_grade, passed, disposition_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tire_serial, insp_time, "OP-3001", "FAIL", "DEF-CUR-01", "Toàn thân lốp", "FAIL", "DEF-XRAY-02", 1.8, 115.0, 52.0, 45.0, "SCRAP", 0, "Lò CP-02 bị sụt áp suất bàng lưu hóa xuống 17.5 bar. Cao su chưa chín hoàn toàn (Under-cure). Hủy bỏ."
                ))
            else:
                # Perfect Grade A OE Tires
                rfv = round(38.0 + (i % 7) * 2.1, 1)
                lfv = round(16.0 + (i % 5) * 1.4, 1)
                bal = round(14.0 + (i % 6) * 1.8, 1)
                cursor.execute("""
                    INSERT INTO quality_inspections (tire_serial, inspection_timestamp, inspector_id, visual_result, visual_defect_code, defect_location, xray_result, xray_defect_code, belt_alignment_mm, uniformity_rfv_n, uniformity_lfv_n, dynamic_balance_g, final_grade, passed, disposition_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tire_serial, insp_time, "OP-3001" if i % 2 == 1 else "OP-3002", "PASS", None, None, "PASS", None, 0.15, rfv, lfv, bal, "GRADE_A", 1, "Chất lượng hoàn hảo, đạt chuẩn cấp hàng OEM xe cao cấp."
                ))

        # =====================================================================
        # 12. EQUIPMENT DOWNTIME LOGS
        # =====================================================================
        downtimes = [
            ("CP-02", (now - timedelta(hours=3, minutes=45)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(hours=3, minutes=15)).strftime("%Y-%m-%d %H:%M:%S"), 30, "MOLD_CHANGE", "Thay đổi khuôn kích cỡ từ 205/55R16 sang 225/60R17 theo kế hoạch điều độ."),
            ("TBM-02", (now - timedelta(hours=6, minutes=20)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(hours=5, minutes=50)).strftime("%Y-%m-%d %H:%M:%S"), 30, "NO_MATERIAL", "Chờ cuộn mành tanh thép từ khu vực chuẩn bị bán thành phẩm."),
            ("CP-04", (now - timedelta(hours=8, minutes=0)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(hours=7, minutes=20)).strftime("%Y-%m-%d %H:%M:%S"), 40, "BLADDER_REPLACE", "Thay bàng lưu hóa định kỳ sau 250 chu kỳ nén nhiệt."),
        ]
        cursor.executemany("INSERT INTO equipment_downtime_logs (machine_id, start_time, end_time, duration_minutes, reason_code, comments) VALUES (?, ?, ?, ?, ?, ?)", downtimes)

        # =====================================================================
        # 13. SENSOR TELEMETRY HISTORY
        # =====================================================================
        telemetry = []
        for minute in range(20):
            t_str = (now - timedelta(minutes=20 - minute)).strftime("%Y-%m-%d %H:%M:%S")
            telemetry.append(("CP-01", "L", t_str, 170.0 + (minute % 3)*0.2 - 0.1, 21.0 + (minute % 2)*0.1, 15.2, "HIGH_PRESSURE_CURE"))
            telemetry.append(("CP-01", "R", t_str, 169.8 + (minute % 4)*0.15, 20.9 + (minute % 3)*0.1, 15.1, "HIGH_PRESSURE_CURE"))
        cursor.executemany("INSERT INTO curing_telemetry_history (press_id, cavity_side, timestamp, mold_temp, bladder_press, steam_press, phase) VALUES (?, ?, ?, ?, ?, ?, ?)", telemetry)

        # =====================================================================
        # 14. INDUSTRIAL PROTOCOL GATEWAY CONNECTORS
        # =====================================================================
        connectors = [
            (
                "CONN-OPC-UA", "OPC_UA", "Siemens S7-1500 / VMI MAXX OPC-UA Gateway",
                "TBM-01, TBM-02, CP-01, CP-02", "opc.tcp://192.168.1.50:4840/Siemens/Server", 4840, 500,
                "CONNECTED", 8.4,
                '{"NodeId": "ns=2;s=CP01.CavityL.MoldTemp", "Value": 170.2, "StatusCode": "Good", "SourceTimestamp": "2026-10-06T10:05:00Z"}',
                "Giao thức bảo mật công nghiệp cao cấp, mã hóa TLS/X.509, sử dụng cho máy đóng lốp VMI MAXX và lò lưu hóa Herbert 63.5\"."
            ),
            (
                "CONN-OPC-DA", "OPC_DA", "Kepware DCOM Classic OPC-DA Server",
                "MIX-01 (Banbury 270L), EXT-01 (Triplex)", "opcda://192.168.1.10/Kepware.KEPServerEX.V5", 135, 1000,
                "CONNECTED", 15.2,
                '{"ItemID": "Banbury01.Mixer.MooneyViscosity", "Value": 68.4, "Quality": 192, "Timestamp": "2026-10-06 10:05:01"}',
                "Chuẩn DCOM kinh điển trên nền Windows cho máy luyện cao su Kobe Steel và dây chuyền đùn 4 trục cũ."
            ),
            (
                "CONN-MODBUS-TCP", "MODBUS_TCP", "Modbus TCP Gateway - Steam Boiler & Temp Controllers",
                "BOILER-01, CHILLER-01, CP-03, CP-04", "modbus://192.168.1.60:502", 502, 1000,
                "CONNECTED", 11.0,
                '{"UnitId": 1, "Function": 3, "Address": 40001, "Registers": [1702, 210, 151], "Scale": 0.1, "Description": "Mold Temp 170.2C, Bladder 21.0 bar, Steam 15.1 bar"}',
                "Giao thức thanh ghi Modbus công nghiệp điều khiển trạm cấp hơi Platen Steam 15 bar và cảm biến áp suất bàng bọng."
            ),
            (
                "CONN-MQTT", "MQTT", "IIoT MQTT Broker (Sparkplug B / JSON)",
                "Cảm biến rung động Banbury, Đồng hồ năng lượng hơi nhiệt", "mqtt://broker.tireplant.lan:1883/tireplant/edge/telemetry", 1883, 2000,
                "CONNECTED", 18.5,
                '{"timestamp": 1791277500, "metrics": [{"name": "Banbury_Bearing_Vibration_RMS", "value": 2.45}, {"name": "Steam_Flow_KgPerHour", "value": 1420.5}]}',
                "Kiến trúc Publish/Subscribe nhẹ cho cảm biến rung động ổ bi máy luyện Banbury và giám sát năng lượng hơi nhiệt toàn nhà máy."
            ),
            (
                "CONN-TCP-SOCKET", "TCP_SOCKET", "Raw TCP/IP Socket - Cognex Scanners & Mettler Scale",
                "Đầu đọc mã vạch Cognex TBM-01, Cân điện tử Mettler Toledo", "tcp://192.168.1.75:2001", 2001, 0,
                "CONNECTED", 4.2,
                '<STX>SCANNER_ID=COG-TBM-01;BARCODE=GT-20261006-0019;SCALE_WEIGHT=9.28KG;STATUS=PASS<ETX>',
                "Luồng byte ASCII trực tiếp từ đầu đọc mã vạch công nghiệp Cognex DataMan 370 và đầu cân điện tử Mettler Toledo."
            ),
        ]
        cursor.executemany("INSERT INTO gateway_connectors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", connectors)

        # =====================================================================
        # 15. MASTER DOCUMENTS (MODULE 4: DOCUMENT CONTROL & ELECTRONIC SOPS)
        # =====================================================================
        documents = [
            (
                "DOC-SOP-TBM-01", "SOP-TBM-042",
                "Quy trình thao tác chuẩn máy thành hình lốp du lịch VMI MAXX (Poka-Yoke & Chống dính)",
                "SOP", "TBM", "Rev 3.2", "2026-01-15", "Trưởng Phòng Công Nghệ - Trần Đình Vũ",
                "Quy chuẩn kiểm tra 7 hợp phần, áp lực lăn miết 4.2 bar, căn chỉnh tâm trống và kiểm tra hạn dùng cao su sống.",
                "<p><strong>1. Mục đích:</strong> Đảm bảo công nhân máy TBM tuân thủ nghiêm ngặt quy trình quét mã vạch 7 hợp phần trước khi kích hoạt trống thành hình.</p><p><strong>2. An toàn Poka-Yoke:</strong> Cấm tuyệt đối dán hợp phần quá hạn 48 giờ. Áp lực con lăn miết đai thép: 4.2 &plusmn; 0.2 bar.</p>"
            ),
            (
                "DOC-DWG-PCR-205", "DWG-205-55R16-STR",
                "Bản vẽ kỹ thuật kết cấu mặt cắt lốp du lịch 205/55R16 (Cấu trúc 7 lớp tiêu chuẩn)",
                "DRAWING", "TBM", "Rev 4.0", "2026-03-01", "Kỹ Sư Trưởng Thiết Kế Lốp - Đặng Hoàng Quân",
                "Bản vẽ mặt cắt ngang chi tiết: Mặt lốp (Tread Cap/Base), 2 lớp đai thép góc 21 độ, Mành sợi Polyester, Vòng tanh lục giác, Màng kín khí Halobutyl.",
                "<p><strong>Cấu trúc chi tiết:</strong><br>- Lớp 1: Mặt lốp gai Turbo-Grip (Dày 8.5mm)<br>- Lớp 2-3: Đai thép Belt 1 (Góc +21&deg;), Belt 2 (Góc -21&deg;)<br>- Lớp 4: Lớp đệm mành nylon dệt xoắn JLB<br>- Lớp 5: Thân mành sợi Polyester 1500D/2<br>- Lớp 6: Vòng tanh thép lục giác Hexagonal Bead Wire (Dây 0.96mm x 5 sợi x 4 hàng)<br>- Lớp 7: Màng kín khí Bromobutyl CIIR 100% không săm (Dày 1.2mm).</p>"
            ),
            (
                "DOC-SOP-CUR-02", "SOP-CUR-018",
                "Quy trình vận hành lò lưu hóa thủy lực 63.5\" và kiểm soát tuổi thọ bàng bọng Bladder",
                "SOP", "CURING", "Rev 2.1", "2026-02-10", "Quản Đốc Phân Xưởng Lưu Hóa - Lê Hoàng Nam",
                "Quy định thông số nén nhiệt: Nhiệt độ khuôn 170°C, áp suất hơi vòm 15.2 bar, áp suất bàng bọng 21 bar, thay bàng định kỳ 350 chu kỳ.",
                "<p><strong>Quy trình thao tác:</strong><br>1. Kiểm tra bề mặt khuôn, xịt dung dịch chống dính bàng định kỳ 10 chu kỳ/lần.<br>2. Cài đặt đơn công nghệ Recipe tương ứng với kích cỡ lốp.<br>3. Kiểm tra áp suất bàng định hình (Shaping Steam): 2.5 bar trước khi đóng nắp lò.<br>4. Theo dõi bộ đếm tuổi thọ bàng lưu hóa: Không được vượt quá 350 lần ép.</p>"
            ),
            (
                "DOC-WI-QC-01", "WI-QC-009",
                "Hướng dẫn kiểm tra nghiệm thu KCS, soi X-Ray và giới hạn lực đồng đều RFV OE",
                "WORK_INSTRUCTION", "FINISHING", "Rev 5.0", "2026-04-12", "Trưởng Phòng Đảm Bảo Chất Lượng QA - Đỗ Thị Mai",
                "Tiêu chuẩn nghiệm thu Hạng A (OE First Class): Độ lệch mành thép X-Ray < 1.0mm, Lực biến thiên hướng kính RFV < 80N, Mất cân bằng động < 30g.",
                "<p><strong>Tiêu chuẩn phân loại sản phẩm:</strong><br>- <strong>HẠNG A:</strong> Không lỗi ngoại quan, X-Ray mành đều, RFV &le; 80N, Cân bằng động &le; 30g. Cấp tem xuất xưởng OE.<br>- <strong>HẠNG B:</strong> Lỗi thẩm mỹ nhẹ, RFV 81-90N. Bán thị trường thay thế nội địa.<br>- <strong>TÁI CHẾ:</strong> Bavia gai quá dài > 10mm. Chuyển trạm cắt tỉa thủ công.<br>- <strong>PHẾ PHẨM (SCRAP):</strong> Bọt khí hông lốp, đè mép mành thép, tụt áp non lưu hóa. Cắt tanh hủy bỏ ngay lập tức.</p>"
            )
        ]
        cursor.executemany("INSERT INTO master_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", documents)

        # =====================================================================
        # 16. DYNAMIC MATERIAL ROUTING & BOTTLENECK BALANCING RULES
        # =====================================================================
        rules = [
            (
                "RULE-TBM-CURING-PRIMARY", "BUFFER_GREEN_TIRE", "CP-01", "CP-03", "GREEN_TIRE",
                0, 0.0, "Luồng chuẩn: Cấp 50% lốp sống sang buồng ép CP-01", None, 14.5
            ),
            (
                "RULE-TBM-CURING-SECONDARY", "BUFFER_GREEN_TIRE", "CP-02", "CP-04", "GREEN_TIRE",
                0, 0.0, "Luồng chuẩn: Cấp 50% lốp sống sang buồng ép CP-02", None, 16.0
            ),
            (
                "RULE-TBM-PARALLEL-SPLIT", "TBM-01", "TBM-01", "TBM-02", "WORK_ORDER",
                0, 0.0, "Luồng chuẩn: Lệnh PCR xử lý tại TBM-01", None, 12.0
            ),
            (
                "RULE-QC-BALANCING", "XR-01", "XR-01", "UF-01", "CURED_TIRE",
                0, 0.0, "Luồng chuẩn: 100% lốp qua trạm X-Ray XR-01", None, 18.0
            )
        ]
        cursor.executemany("""
            INSERT INTO dynamic_routing_rules (
                rule_id, source_station, target_station, alternate_station,
                material_type, is_diverted, divert_ratio_pct, divert_reason,
                activated_at, throughput_gain_forecast_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rules)




if __name__ == "__main__":
    seed_database()
    print("Realistic Tire Plant MES seed data successfully created!")
