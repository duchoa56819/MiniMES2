"""
Tire Manufacturing Execution System (TIRE-MES) - ISA-95 Level 3
Production Application Server.
Senior MES Engineer Architecture.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import DB_PATH
from app.seed_data import seed_database
from app.simulator import start_simulator, stop_simulator

from app.routers import (
    dashboard,
    work_orders,
    tbm,
    curing,
    quality,
    genealogy,
    master_data,
    gateway,
    stream,
    routing,
    ai,
    bottleneck,
    shap_root_cause,
    graph_genealogy,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize and seed DB if missing
    if not os.path.exists(DB_PATH):
        print("Database not found. Initializing seed data...")
        seed_database()

    # Start shop floor IoT simulator
    start_simulator()
    yield
    # Shutdown: Stop simulator
    stop_simulator()


app = FastAPI(
    title="Tire MES - Manufacturing Execution System",
    description="Hệ thống Điều hành Sản xuất Nhà máy Lốp xe theo chuẩn ISA-95 Level 3",
    version="2.5.0",
    lifespan=lifespan
)

# Enable CORS for open integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(dashboard.router)
app.include_router(work_orders.router)
app.include_router(tbm.router)
app.include_router(curing.router)
app.include_router(quality.router)
app.include_router(genealogy.router)
app.include_router(master_data.router)
app.include_router(gateway.router)
app.include_router(stream.router)
app.include_router(routing.router)
app.include_router(ai.router)
app.include_router(bottleneck.router)
app.include_router(shap_root_cause.router)
app.include_router(graph_genealogy.router)


# Mount Static Assets
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_index():
    """Serves the main single-page MES Industrial Dashboard."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Tire MES Backend API is running. Web UI loading..."}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("   TIRE MANUFACTURING EXECUTION SYSTEM (TIRE-MES) - ISA-95 LEVEL 3")
    print("   Truy cập Web Dashboard tại: http://localhost:8000")
    print("   Tài liệu Swagger API tại:   http://localhost:8000/docs")
    print("="*70 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
