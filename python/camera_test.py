"""
camera_test.py — Pengujian webcam sederhana.

Membuka webcam, menampilkan resolusi dan FPS real-time.
Tekan Q untuk keluar.
"""

import sys
import time

import cv2

import config


def main() -> None:
    """Jalankan pengujian webcam."""
    print(f"[INFO] Membuka webcam index {config.CAMERA_INDEX}...")

    cap = cv2.VideoCapture(config.CAMERA_INDEX)

    if not cap.isOpened():
        print("[ERROR] Gagal membuka webcam. Pastikan webcam terhubung.")
        sys.exit(1)

    # Set resolusi
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

    # Baca resolusi aktual
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Resolusi webcam: {actual_w} x {actual_h}")

    prev_time = time.perf_counter()
    frame_count = 0
    fps_display = 0.0

    print("[INFO] Tekan Q untuk keluar.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Gagal membaca frame.")
                continue

            frame_count += 1
            current_time = time.perf_counter()
            elapsed = current_time - prev_time

            if elapsed >= 1.0:
                fps_display = frame_count / elapsed
                frame_count = 0
                prev_time = current_time

            # Overlay info
            info_text = f"Resolusi: {actual_w}x{actual_h} | FPS: {fps_display:.1f}"
            cv2.putText(
                frame, info_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA,
            )
            cv2.putText(
                frame, "Tekan Q untuk keluar", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA,
            )

            cv2.imshow("Camera Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted oleh pengguna.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Webcam ditutup.")


if __name__ == "__main__":
    main()
