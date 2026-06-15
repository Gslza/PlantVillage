"""
aiot_inference.py — Program utama Tomato AIoT Relay Control.

Mendeteksi penyakit daun tomat secara real-time menggunakan webcam + CNN,
lalu mengirim perintah serial ke NodeMCU untuk mengontrol relay.

Fitur utama:
    - Inferensi CNN real-time pada ROI webcam
    - Confidence filtering (≥ 60%)
    - Consecutive-frame debounce (5 frame stabil)
    - State-change detection (kirim serial hanya saat berubah)
    - Mode AUTO / MANUAL
    - Fail-safe (semua relay OFF saat keluar/error)
    - Serial reconnect otomatis
    - Simpan histori deteksi ke CSV

Keyboard:
    Q = Keluar
    R = Reset semua relay
    S = Simpan screenshot
    P = Pause / lanjutkan inferensi
    1-4 = Manual relay
    0 = Manual semua OFF
    A = Kembali ke mode AUTO

Penggunaan:
    python aiot_inference.py
    python aiot_inference.py --port COM5 --confidence 0.60 --stable-frames 5
"""

import argparse
import sys
import time
from typing import Optional

import cv2
import numpy as np

import config
from utils import (
    FPSCounter,
    HistoryLogger,
    StateManager,
    draw_overlay,
    draw_roi_box,
    extract_roi,
    get_category,
    get_prediction,
    get_relay_label,
    get_serial_command,
    preprocess_frame,
    save_screenshot,
)

# ── Lazy imports ─────────────────────────────────────────────────────────
tf = None       # tensorflow — dimuat saat dibutuhkan
serial = None   # pyserial — dimuat saat dibutuhkan


def import_tensorflow():
    """Lazy-load TensorFlow."""
    global tf
    if tf is None:
        print("[INFO] Loading TensorFlow...")
        import tensorflow as _tf
        tf = _tf
        print(f"[INFO] TensorFlow {tf.__version__} loaded.")
    return tf


def import_serial():
    """Lazy-load pyserial."""
    global serial
    if serial is None:
        try:
            import serial as _serial
            serial = _serial
        except ImportError:
            print("[WARNING] Module 'pyserial' belum terinstal.")
            print("          Serial tidak tersedia. Inferensi tetap berjalan.")
            serial = None
    return serial


# ═══════════════════════════════════════════════════════════════════════════
# Serial Connection Manager
# ═══════════════════════════════════════════════════════════════════════════

class SerialManager:
    """Mengelola koneksi serial ke NodeMCU dengan reconnect otomatis."""

    def __init__(self, port: str, baud: int, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._conn: Optional[object] = None
        self._last_reconnect: float = 0.0

    @property
    def is_connected(self) -> bool:
        """Apakah serial port terhubung dan terbuka."""
        return self._conn is not None and self._conn.is_open

    @property
    def status_text(self) -> str:
        """Status koneksi untuk tampilan UI."""
        if self.is_connected:
            return f"Connected - {self.port}"
        return f"Disconnected - {self.port}"

    def connect(self) -> bool:
        """Coba buka koneksi serial.

        Returns:
            True jika berhasil, False jika gagal.
        """
        _serial = import_serial()
        if _serial is None:
            return False

        try:
            self._conn = _serial.Serial(self.port, self.baud, timeout=self.timeout)
            time.sleep(2)  # Tunggu NodeMCU boot / auto-reset
            print(f"[INFO] Terhubung ke {self.port} @ {self.baud} baud")
            return True
        except (_serial.SerialException, FileNotFoundError, OSError) as e:
            print(f"[WARNING] Gagal membuka {self.port}: {e}")
            self._conn = None
            return False

    def try_reconnect(self, interval: float = 5.0) -> bool:
        """Coba reconnect jika waktu sudah mencukupi.

        Args:
            interval: Detik minimum antar percobaan reconnect.

        Returns:
            True jika berhasil reconnect.
        """
        now = time.time()
        if now - self._last_reconnect < interval:
            return False
        self._last_reconnect = now
        print(f"[INFO] Mencoba reconnect ke {self.port}...")
        return self.connect()

    def send(self, command: str) -> bool:
        """Kirim perintah serial (1 karakter).

        Args:
            command: Karakter perintah ('H', 'F', 'B', 'V', 'O').

        Returns:
            True jika berhasil dikirim.
        """
        if not self.is_connected:
            return False
        try:
            self._conn.write(command.encode("utf-8"))
            self._conn.flush()
            return True
        except Exception as e:
            print(f"[ERROR] Gagal mengirim serial: {e}")
            self._conn = None
            return False

    def read_ack(self) -> Optional[str]:
        """Baca acknowledgement dari NodeMCU (non-blocking).

        Returns:
            String ACK atau None jika tidak ada data.
        """
        if not self.is_connected:
            return None
        try:
            if self._conn.in_waiting:
                response = self._conn.readline().decode(errors="ignore").strip()
                return response if response else None
        except Exception:
            pass
        return None

    def close(self) -> None:
        """Tutup koneksi serial dengan aman."""
        if self.is_connected:
            try:
                self._conn.close()
                print(f"[INFO] Port serial {self.port} ditutup.")
            except Exception:
                pass
            self._conn = None


# ═══════════════════════════════════════════════════════════════════════════
# Argument Parser
# ═══════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """Parse argumen command line."""
    parser = argparse.ArgumentParser(
        description="Tomato AIoT Relay Control — Real-time Inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python aiot_inference.py
  python aiot_inference.py --port COM5 --confidence 0.60
  python aiot_inference.py --model "../models/best_scratch.keras" --camera 0
        """,
    )
    parser.add_argument("--model", type=str, default=config.MODEL_PATH,
                        help=f"Path ke model Keras (default: config)")
    parser.add_argument("--port", type=str, default=config.SERIAL_PORT,
                        help=f"COM port serial (default: {config.SERIAL_PORT})")
    parser.add_argument("--baud", type=int, default=config.BAUD_RATE,
                        help=f"Baud rate (default: {config.BAUD_RATE})")
    parser.add_argument("--camera", type=int, default=config.CAMERA_INDEX,
                        help=f"Index webcam (default: {config.CAMERA_INDEX})")
    parser.add_argument("--confidence", type=float, default=config.CONFIDENCE_THRESHOLD,
                        help=f"Confidence threshold (default: {config.CONFIDENCE_THRESHOLD})")
    parser.add_argument("--stable-frames", type=int, default=config.REQUIRED_STABLE_FRAMES,
                        help=f"Frame stabil yang dibutuhkan (default: {config.REQUIRED_STABLE_FRAMES})")
    parser.add_argument("--no-serial", action="store_true",
                        help="Jalankan tanpa koneksi serial (mode offline)")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Entry point program utama."""
    args = parse_args()

    # ── 1. Load Model ────────────────────────────────────────────────────
    _tf = import_tensorflow()
    print(f"[INFO] Loading CNN model: {args.model}")
    try:
        model = _tf.keras.models.load_model(args.model)
        print("[INFO] Model loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Gagal memuat model: {e}")
        sys.exit(1)

    # ── 2. Buka Webcam ───────────────────────────────────────────────────
    print(f"[INFO] Opening camera index {args.camera}...")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("[ERROR] Gagal membuka webcam.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Camera opened: {actual_w}x{actual_h}")

    # ── 3. Buka Serial ──────────────────────────────────────────────────
    serial_mgr = SerialManager(args.port, args.baud)
    if not args.no_serial:
        print(f"[INFO] Connecting to {args.port}...")
        serial_mgr.connect()
    else:
        print("[INFO] Mode offline — serial dinonaktifkan.")

    # ── 4. Inisialisasi Komponen ─────────────────────────────────────────
    state_mgr = StateManager(required_frames=args.stable_frames)
    fps_counter = FPSCounter()
    history = HistoryLogger() if config.SAVE_HISTORY else None

    # State variabel
    mode = "AUTO"           # AUTO atau MANUAL
    paused = False          # Pause inferensi
    current_class = "—"
    current_category = "unknown"
    current_confidence = 0.0
    current_relay = "All OFF"
    last_low_conf_time = time.time()

    # ── 5. Fail-safe: kirim O saat startup ───────────────────────────────
    if serial_mgr.is_connected:
        serial_mgr.send("O")
        print("[INFO] Startup: semua relay OFF.")

    # ── 6. Tampilkan kontrol keyboard ────────────────────────────────────
    print("\n" + "=" * 55)
    print("  TOMATO AIoT RELAY CONTROL")
    print("=" * 55)
    print("  Q = Keluar          R = Reset relay")
    print("  S = Screenshot      P = Pause/Resume")
    print("  1-4 = Manual relay  0 = Semua OFF")
    print("  A = Mode AUTO")
    print("=" * 55 + "\n")

    # ── 7. Main Loop ────────────────────────────────────────────────────
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Gagal membaca frame dari webcam.")
                # Fail-safe: kirim O saat kamera gagal
                if serial_mgr.is_connected:
                    serial_mgr.send("O")
                time.sleep(0.1)
                continue

            fps = fps_counter.tick()

            # ── Baca ACK dari NodeMCU (non-blocking) ─────────────────────
            ack = serial_mgr.read_ack()
            if ack:
                print(f"[ESP] {ack}")

            # ── Reconnect serial jika terputus ───────────────────────────
            if not args.no_serial and not serial_mgr.is_connected:
                serial_mgr.try_reconnect(config.SERIAL_RECONNECT_INTERVAL)

            # ── Extract ROI ──────────────────────────────────────────────
            roi, roi_coords = extract_roi(frame)
            color = config.CATEGORY_COLORS.get(current_category, (160, 160, 160))

            if not paused and mode == "AUTO":
                # ── Preprocessing & Inferensi ────────────────────────────
                processed = preprocess_frame(roi)
                predictions = model.predict(processed, verbose=0)
                class_name, confidence, class_idx = get_prediction(predictions)

                current_class = class_name
                current_confidence = confidence

                # ── Confidence Filtering ─────────────────────────────────
                if confidence >= args.confidence:
                    current_category = get_category(class_name)
                    last_low_conf_time = time.time()
                else:
                    current_category = "unknown"
                    # Fail-safe: reset setelah timeout confidence rendah
                    if time.time() - last_low_conf_time > config.STATE_RESET_SECONDS:
                        state_mgr.reset()

                # ── Debounce + State Change ──────────────────────────────
                state_changed = state_mgr.update(current_category)
                current_relay = get_relay_label(state_mgr.stable_state)
                color = config.CATEGORY_COLORS.get(
                    state_mgr.stable_state, (160, 160, 160)
                )

                if state_changed:
                    command = get_serial_command(state_mgr.stable_state)

                    print(f"[DETECTION] {current_class} | "
                          f"{current_confidence * 100:.2f}% | "
                          f"{state_mgr.stable_state}")

                    if serial_mgr.send(command):
                        print(f"[SERIAL] Sent: {command} | "
                              f"Category: {state_mgr.stable_state}")
                        relay_label = get_relay_label(state_mgr.stable_state)
                        print(f"[INFO] {relay_label} activated.")
                    else:
                        print(f"[WARNING] Serial tidak tersedia. "
                              f"Command {command} tidak dikirim.")

                    state_mgr.mark_sent()

                    # Log ke CSV
                    if history:
                        history.log(
                            predicted_class=current_class,
                            confidence=current_confidence,
                            category=state_mgr.stable_state,
                            command=command,
                            relay=get_relay_label(state_mgr.stable_state),
                            last_sent_state=state_mgr.last_sent_state,
                        )

            # ── Draw UI ──────────────────────────────────────────────────
            draw_roi_box(frame, roi_coords, color)
            draw_overlay(
                frame=frame,
                mode=mode + (" [PAUSED]" if paused else ""),
                predicted_class=current_class,
                category=current_category,
                confidence=current_confidence,
                stable_frames=state_mgr.candidate_count,
                required_frames=state_mgr.required_frames,
                relay_label=current_relay,
                serial_status=serial_mgr.status_text,
                fps=fps,
                color=color,
            )

            cv2.imshow("Tomato AIoT Relay Control", frame)

            # ── Keyboard Controls ────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == ord("Q"):
                print("[INFO] Keluar dari aplikasi...")
                break

            elif key == ord("r") or key == ord("R"):
                print("[INFO] Reset: semua relay OFF.")
                serial_mgr.send("O")
                state_mgr.reset()
                state_mgr.last_sent_state = ""
                current_relay = "All OFF"

            elif key == ord("s") or key == ord("S"):
                filepath = save_screenshot(frame)
                print(f"[INFO] Screenshot disimpan: {filepath}")

            elif key == ord("p") or key == ord("P"):
                paused = not paused
                status = "PAUSED" if paused else "RESUMED"
                print(f"[INFO] Inferensi {status}.")

            elif key == ord("a") or key == ord("A"):
                mode = "AUTO"
                print("[INFO] Mode: AUTO")
                state_mgr.reset()
                state_mgr.last_sent_state = ""

            elif key == ord("0"):
                mode = "MANUAL"
                serial_mgr.send("O")
                current_relay = "All OFF"
                current_category = "unknown"
                print("[MANUAL] Semua relay OFF.")

            elif key in (ord("1"), ord("2"), ord("3"), ord("4")):
                mode = "MANUAL"
                relay_num = key - ord("0")
                manual_map = {1: "H", 2: "F", 3: "B", 4: "V"}
                cat_map = {1: "healthy", 2: "fungal", 3: "bacterial", 4: "virus"}
                cmd = manual_map[relay_num]
                serial_mgr.send(cmd)
                current_category = cat_map[relay_num]
                current_relay = f"Relay {relay_num} ON"
                color = config.CATEGORY_COLORS.get(current_category, (160, 160, 160))
                print(f"[MANUAL] Relay {relay_num} ON (command: {cmd})")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted oleh pengguna.")

    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        # Fail-safe: coba matikan relay
        try:
            serial_mgr.send("O")
        except Exception:
            pass

    finally:
        # ── Cleanup ──────────────────────────────────────────────────────
        # Fail-safe: kirim O saat keluar
        if serial_mgr.is_connected:
            serial_mgr.send("O")
            time.sleep(0.3)
            print("[INFO] Semua relay OFF (shutdown).")

        serial_mgr.close()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Application closed safely.")


if __name__ == "__main__":
    main()
