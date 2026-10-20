
import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from erp_api.data_loader import store
from erp_api.models import HealthResponse
from erp_api.routers import items

def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Loads the item master data on startup.
    """
    root_dir = get_project_root()
    # Load from staged/erp/ (drift-injected data) if available, else fall back to raw/
    staged_erp_path = root_dir / "data" / "staged" / "erp"
    raw_data_path = root_dir / "data" / "raw"
    if staged_erp_path.exists() and any(staged_erp_path.iterdir()):
        store.load_data(staged_erp_path)
    else:
        store.load_data(raw_data_path)
    yield
    # No teardown required

app = FastAPI(
    title="ERP Item Master API",
    description="Simulated ERP system serving product/item master data",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware allowing all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include items router
app.include_router(items.router)

@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """
    Health check endpoint returning system status and item count.
    """
    return HealthResponse(
        status="ok",
        item_count=store.count(),
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
