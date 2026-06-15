"""
config.py — Konfigurasi terpusat untuk Tomato AIoT Relay Control.

Semua parameter default dapat di-override melalui command-line arguments
pada program utama (aiot_inference.py).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Path — dihitung relatif terhadap lokasi file ini, bukan cwd
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent

MODEL_PATH: str = str(PROJECT_ROOT / "models" / "best_scratch.keras")
LOG_DIR: str = str(PROJECT_ROOT / "logs")
SCREENSHOT_DIR: str = str(PROJECT_ROOT / "screenshots")

# ---------------------------------------------------------------------------
# Serial
# ---------------------------------------------------------------------------
SERIAL_PORT: str = "COM8"
BAUD_RATE: int = 115200
SERIAL_TIMEOUT: float = 1.0
SERIAL_RECONNECT_INTERVAL: float = 5.0  # detik antara percobaan reconnect

# ---------------------------------------------------------------------------
# Kamera
# ---------------------------------------------------------------------------
CAMERA_INDEX: int = 1
CAMERA_WIDTH: int = 640
CAMERA_HEIGHT: int = 480
CAMERA_FPS: int = 20

# ---------------------------------------------------------------------------
# Model & Inferensi
# ---------------------------------------------------------------------------
IMAGE_WIDTH: int = 224
IMAGE_HEIGHT: int = 224

CONFIDENCE_THRESHOLD: float = 0.60
REQUIRED_STABLE_FRAMES: int = 5
STATE_RESET_SECONDS: float = 2.0

# ---------------------------------------------------------------------------
# Tampilan
# ---------------------------------------------------------------------------
SHOW_FPS: bool = True
SAVE_HISTORY: bool = True

# ---------------------------------------------------------------------------
# Nama kelas — urutan sesuai output model (alfabet)
# ---------------------------------------------------------------------------
CLASS_NAMES: list[str] = [
    "bacterial_spot",
    "early_blight",
    "healthy",
    "late_blight",
    "leaf_mold",
    "septoria_leaf_spot",
    "target_spot",
    "tomato_mosaic_virus",
    "tomato_yellow_leaf_curl_virus",
    "two_spotted_spider_mite",
]

# ---------------------------------------------------------------------------
# Pemetaan kelas → kategori relay
# ---------------------------------------------------------------------------
CLASS_TO_CATEGORY: dict[str, str] = {
    "healthy": "healthy",
    "early_blight": "fungal",
    "late_blight": "fungal",
    "leaf_mold": "fungal",
    "septoria_leaf_spot": "fungal",
    "target_spot": "fungal",
    "bacterial_spot": "bacterial",
    "two_spotted_spider_mite": "bacterial",
    "tomato_mosaic_virus": "virus",
    "tomato_yellow_leaf_curl_virus": "virus",
}

# ---------------------------------------------------------------------------
# Pemetaan kategori → perintah serial & relay
# ---------------------------------------------------------------------------
CATEGORY_TO_COMMAND: dict[str, str] = {
    "healthy": "H",
    "fungal": "F",
    "bacterial": "B",
    "virus": "V",
    "unknown": "O",
}

CATEGORY_TO_RELAY: dict[str, str] = {
    "healthy": "Relay 1 ON",
    "fungal": "Relay 2 ON",
    "bacterial": "Relay 3 ON",
    "virus": "Relay 4 ON",
    "unknown": "All OFF",
}

# ---------------------------------------------------------------------------
# Warna OpenCV (BGR) untuk overlay UI
# ---------------------------------------------------------------------------
CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "healthy": (0, 200, 0),       # Hijau
    "fungal": (0, 220, 255),      # Kuning
    "bacterial": (0, 140, 255),   # Oranye
    "virus": (0, 0, 230),         # Merah
    "unknown": (160, 160, 160),   # Abu-abu
}
