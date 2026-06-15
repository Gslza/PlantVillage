"""
utils.py — Fungsi utilitas untuk Tomato AIoT Relay Control.

Berisi fungsi preprocessing gambar, pemetaan kelas, logging,
dan helper untuk tampilan OpenCV.
"""

import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

import config


# ═══════════════════════════════════════════════════════════════════════════
# Preprocessing Gambar
# ═══════════════════════════════════════════════════════════════════════════

def preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """Preprocessing frame webcam untuk inferensi CNN.

    Langkah:
        1. Resize ke IMAGE_WIDTH × IMAGE_HEIGHT
        2. Konversi BGR (OpenCV) → RGB
        3. Konversi ke float32
        4. Normalisasi pixel / 255.0
        5. Tambah batch dimension → (1, H, W, 3)

    Args:
        frame: Frame BGR dari OpenCV (numpy array).

    Returns:
        Array dengan shape (1, IMAGE_HEIGHT, IMAGE_WIDTH, 3), float32, range [0, 1].
    """
    resized = cv2.resize(frame, (config.IMAGE_WIDTH, config.IMAGE_HEIGHT))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    batched = np.expand_dims(normalized, axis=0)
    return batched


def extract_roi(frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Ambil Region of Interest (center crop persegi) dari frame.

    ROI berupa persegi berukuran min(width, height) yang diambil dari tengah frame.

    Args:
        frame: Frame BGR dari webcam.

    Returns:
        Tuple berisi:
            - roi: Crop persegi dari frame (numpy array BGR)
            - (x1, y1, x2, y2): Koordinat ROI pada frame asli
    """
    h, w = frame.shape[:2]
    side = min(h, w)
    x1 = (w - side) // 2
    y1 = (h - side) // 2
    x2 = x1 + side
    y2 = y1 + side
    roi = frame[y1:y2, x1:x2]
    return roi, (x1, y1, x2, y2)


# ═══════════════════════════════════════════════════════════════════════════
# Klasifikasi & Pemetaan
# ═══════════════════════════════════════════════════════════════════════════

def get_prediction(predictions: np.ndarray) -> tuple[str, float, int]:
    """Ambil kelas, confidence, dan index dari output softmax model.

    Args:
        predictions: Array softmax shape (1, 10).

    Returns:
        Tuple (class_name, confidence, class_index).
    """
    class_index = int(np.argmax(predictions[0]))
    confidence = float(predictions[0][class_index])
    class_name = config.CLASS_NAMES[class_index]
    return class_name, confidence, class_index


def get_category(class_name: str) -> str:
    """Map nama kelas ke kategori relay.

    Args:
        class_name: Nama kelas prediksi (misal 'late_blight').

    Returns:
        Kategori: 'healthy', 'fungal', 'bacterial', 'virus', atau 'unknown'.
    """
    return config.CLASS_TO_CATEGORY.get(class_name, "unknown")


def get_serial_command(category: str) -> str:
    """Dapatkan perintah serial untuk kategori tertentu.

    Args:
        category: Salah satu dari 'healthy', 'fungal', 'bacterial', 'virus', 'unknown'.

    Returns:
        Karakter perintah serial: 'H', 'F', 'B', 'V', atau 'O'.
    """
    return config.CATEGORY_TO_COMMAND.get(category, "O")


def get_relay_label(category: str) -> str:
    """Dapatkan label relay untuk tampilan UI.

    Args:
        category: Kategori relay.

    Returns:
        Label seperti 'Relay 2 ON' atau 'All OFF'.
    """
    return config.CATEGORY_TO_RELAY.get(category, "All OFF")


# ═══════════════════════════════════════════════════════════════════════════
# FPS Counter
# ═══════════════════════════════════════════════════════════════════════════

class FPSCounter:
    """Penghitung FPS menggunakan moving average."""

    def __init__(self, buffer_size: int = 30):
        self._buffer_size = buffer_size
        self._times: list[float] = []
        self._last_time: float = time.perf_counter()

    def tick(self) -> float:
        """Catat satu frame dan kembalikan FPS saat ini."""
        now = time.perf_counter()
        self._times.append(now - self._last_time)
        self._last_time = now
        if len(self._times) > self._buffer_size:
            self._times.pop(0)
        avg = sum(self._times) / len(self._times)
        return 1.0 / avg if avg > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Debounce & State Management
# ═══════════════════════════════════════════════════════════════════════════

class StateManager:
    """Mengelola consecutive-frame debounce dan state-change detection.

    Attributes:
        candidate_state: Kategori yang sedang diuji stabilitasnya.
        candidate_count: Jumlah frame berturut-turut untuk candidate_state.
        stable_state: Kategori yang sudah dianggap stabil.
        last_sent_state: State terakhir yang dikirim ke serial.
    """

    def __init__(self, required_frames: int = 5):
        self.required_frames: int = required_frames
        self.candidate_state: str = "unknown"
        self.candidate_count: int = 0
        self.stable_state: str = "unknown"
        self.last_sent_state: str = ""

    def update(self, current_state: str) -> bool:
        """Update state dengan kategori frame saat ini.

        Args:
            current_state: Kategori prediksi frame ini.

        Returns:
            True jika state berubah (perlu dikirim ke serial), False jika tidak.
        """
        # Debounce: hitung consecutive frames
        if current_state == self.candidate_state:
            self.candidate_count += 1
        else:
            self.candidate_state = current_state
            self.candidate_count = 1

        # Promosi ke stable jika memenuhi threshold
        if self.candidate_count >= self.required_frames:
            self.stable_state = self.candidate_state

        # State-change detection
        if self.stable_state != self.last_sent_state:
            return True
        return False

    def mark_sent(self) -> None:
        """Tandai bahwa state saat ini sudah dikirim ke serial."""
        self.last_sent_state = self.stable_state

    def reset(self) -> None:
        """Reset semua state ke unknown."""
        self.candidate_state = "unknown"
        self.candidate_count = 0
        self.stable_state = "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Detection History Logger
# ═══════════════════════════════════════════════════════════════════════════

class HistoryLogger:
    """Logger untuk menyimpan histori deteksi ke CSV.

    File CSV dibuat otomatis di folder logs/ jika SAVE_HISTORY aktif.
    """

    HEADERS = [
        "timestamp",
        "predicted_class",
        "confidence",
        "category",
        "command",
        "relay",
        "last_sent_state",
    ]

    def __init__(self, log_dir: Optional[str] = None):
        self._log_dir = Path(log_dir or config.LOG_DIR)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._filepath = self._log_dir / "detection_history.csv"
        self._ensure_header()

    def _ensure_header(self) -> None:
        """Tulis header CSV jika file belum ada."""
        if not self._filepath.exists():
            with open(self._filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADERS)

    def log(
        self,
        predicted_class: str,
        confidence: float,
        category: str,
        command: str,
        relay: str,
        last_sent_state: str,
    ) -> None:
        """Tulis satu baris log deteksi.

        Hanya dipanggil saat state berubah, bukan setiap frame.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self._filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                predicted_class,
                f"{confidence:.4f}",
                category,
                command,
                relay,
                last_sent_state,
            ])


# ═══════════════════════════════════════════════════════════════════════════
# OpenCV Overlay Drawing
# ═══════════════════════════════════════════════════════════════════════════

def draw_roi_box(
    frame: np.ndarray,
    roi_coords: tuple[int, int, int, int],
    color: tuple[int, int, int],
) -> None:
    """Gambar kotak ROI pada frame.

    Args:
        frame: Frame BGR untuk digambar.
        roi_coords: (x1, y1, x2, y2) koordinat ROI.
        color: Warna BGR kotak.
    """
    x1, y1, x2, y2 = roi_coords
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)


def draw_overlay(
    frame: np.ndarray,
    mode: str,
    predicted_class: str,
    category: str,
    confidence: float,
    stable_frames: int,
    required_frames: int,
    relay_label: str,
    serial_status: str,
    fps: float,
    color: tuple[int, int, int],
) -> None:
    """Gambar overlay informasi pada frame webcam.

    Args:
        frame: Frame BGR untuk digambar.
        mode: 'AUTO' atau 'MANUAL'.
        predicted_class: Nama kelas prediksi.
        category: Kategori relay.
        confidence: Nilai confidence (0.0 - 1.0).
        stable_frames: Jumlah frame stabil saat ini.
        required_frames: Jumlah frame stabil yang dibutuhkan.
        relay_label: Label status relay (misal 'Relay 2 ON').
        serial_status: Status koneksi serial.
        fps: FPS saat ini.
        color: Warna BGR untuk indikator.
    """
    # Background semi-transparan untuk info panel
    overlay = frame.copy()
    cv2.rectangle(overlay, (5, 5), (380, 235), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Indikator warna
    cv2.rectangle(frame, (10, 10), (30, 30), color, -1)
    cv2.rectangle(frame, (10, 10), (30, 30), (255, 255, 255), 1)

    # Teks info
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.50
    thickness = 1
    text_color = (255, 255, 255)
    y_start = 28
    line_height = 26

    lines = [
        f"  Mode          : {mode}",
        f"  Prediction    : {predicted_class}",
        f"  Category      : {category}",
        f"  Confidence    : {confidence * 100:.2f}%",
        f"  Stable Frames : {min(stable_frames, required_frames)}/{required_frames}",
        f"  Relay State   : {relay_label}",
        f"  Serial        : {serial_status}",
        f"  FPS           : {fps:.1f}",
    ]

    for i, line in enumerate(lines):
        y = y_start + i * line_height
        cv2.putText(frame, line, (35, y), font, font_scale, text_color, thickness,
                    cv2.LINE_AA)


def save_screenshot(frame: np.ndarray, screenshot_dir: Optional[str] = None) -> str:
    """Simpan screenshot frame saat ini.

    Args:
        frame: Frame BGR untuk disimpan.
        screenshot_dir: Direktori target (default dari config).

    Returns:
        Path file screenshot yang disimpan.
    """
    save_dir = Path(screenshot_dir or config.SCREENSHOT_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = save_dir / f"screenshot_{timestamp}.jpg"
    cv2.imwrite(str(filepath), frame)
    return str(filepath)
