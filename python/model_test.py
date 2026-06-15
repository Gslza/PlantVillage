"""
model_test.py — Pengujian model CNN.

Memuat model Keras, menampilkan shape input/output,
dan (opsional) menguji inferensi pada satu gambar.

Gunakan:
    python model_test.py
    python model_test.py --image "../test_images/sample.jpg"
    python model_test.py --model "../models/best_scratch.keras"
"""

import argparse
import sys

import numpy as np

import config


def parse_args() -> argparse.Namespace:
    """Parse argumen command line."""
    parser = argparse.ArgumentParser(description="Model CNN Test")
    parser.add_argument("--model", type=str, default=config.MODEL_PATH,
                        help=f"Path ke model Keras (default: {config.MODEL_PATH})")
    parser.add_argument("--image", type=str, default=None,
                        help="Path gambar untuk diuji inferensi (opsional)")
    return parser.parse_args()


def main() -> None:
    """Jalankan pengujian model."""
    args = parse_args()

    # ── 1. Muat TensorFlow ──────────────────────────────────────────────
    print("[INFO] Loading TensorFlow...")
    try:
        import tensorflow as tf
        print(f"[INFO] TensorFlow version: {tf.__version__}")
    except ImportError:
        print("[ERROR] TensorFlow belum terinstal.")
        print("        Jalankan: pip install tensorflow")
        sys.exit(1)

    # ── 2. Muat Model ───────────────────────────────────────────────────
    print(f"[INFO] Loading model: {args.model}")
    try:
        model = tf.keras.models.load_model(args.model)
        print("[INFO] Model loaded successfully!")
    except Exception as e:
        print(f"[ERROR] Gagal memuat model: {e}")
        sys.exit(1)

    # ── 3. Tampilkan Info Model ──────────────────────────────────────────
    input_shape = model.input_shape
    output_shape = model.output_shape
    num_classes = output_shape[-1]

    print(f"\n{'=' * 50}")
    print(f"  Input Shape  : {input_shape}")
    print(f"  Output Shape : {output_shape}")
    print(f"  Num Classes  : {num_classes}")
    print(f"{'=' * 50}")

    # Validasi jumlah kelas
    expected_classes = len(config.CLASS_NAMES)
    if num_classes == expected_classes:
        print(f"[OK] Jumlah output ({num_classes}) sesuai dengan "
              f"{expected_classes} kelas yang didefinisikan.")
    else:
        print(f"[WARNING] Jumlah output ({num_classes}) TIDAK sesuai "
              f"dengan {expected_classes} kelas yang didefinisikan!")

    # Validasi input shape
    expected_h, expected_w = config.IMAGE_HEIGHT, config.IMAGE_WIDTH
    if input_shape[1:3] == (expected_h, expected_w):
        print(f"[OK] Input shape ({expected_h}x{expected_w}) sesuai konfigurasi.")
    else:
        print(f"[WARNING] Input shape model {input_shape[1:3]} TIDAK sesuai "
              f"konfigurasi ({expected_h}x{expected_w})!")

    # Tampilkan daftar kelas
    print(f"\n{'=' * 50}")
    print("  Daftar Kelas:")
    for i, name in enumerate(config.CLASS_NAMES):
        print(f"    [{i:2d}] {name}")
    print(f"{'=' * 50}")

    # ── 4. Tes Inferensi Dummy ───────────────────────────────────────────
    print("\n[INFO] Menjalankan inferensi dummy (random noise)...")
    dummy_input = np.random.rand(1, expected_h, expected_w, 3).astype(np.float32)
    dummy_pred = model.predict(dummy_input, verbose=0)
    dummy_class_idx = int(np.argmax(dummy_pred[0]))
    dummy_conf = float(dummy_pred[0][dummy_class_idx])
    print(f"[INFO] Dummy prediction: {config.CLASS_NAMES[dummy_class_idx]} "
          f"({dummy_conf * 100:.2f}%)")
    print("[OK] Model dapat menjalankan inferensi.")

    # ── 5. Tes Inferensi Gambar (Opsional) ───────────────────────────────
    if args.image:
        print(f"\n[INFO] Menguji inferensi pada: {args.image}")
        try:
            import cv2
            img = cv2.imread(args.image)
            if img is None:
                print(f"[ERROR] Gagal membaca gambar: {args.image}")
                sys.exit(1)

            # Preprocessing sesuai pipeline CNN scratch
            from utils import preprocess_frame
            processed = preprocess_frame(img)

            predictions = model.predict(processed, verbose=0)
            class_idx = int(np.argmax(predictions[0]))
            confidence = float(predictions[0][class_idx])
            class_name = config.CLASS_NAMES[class_idx]

            from utils import get_category, get_serial_command, get_relay_label
            category = get_category(class_name)
            command = get_serial_command(category)
            relay = get_relay_label(category)

            print(f"\n{'=' * 50}")
            print(f"  File       : {args.image}")
            print(f"  Prediction : {class_name}")
            print(f"  Confidence : {confidence * 100:.2f}%")
            print(f"  Category   : {category}")
            print(f"  Command    : {command}")
            print(f"  Relay      : {relay}")
            print(f"{'=' * 50}")

            # Tampilkan top-5 prediksi
            top5_idx = np.argsort(predictions[0])[::-1][:5]
            print("\n  Top-5 Predictions:")
            for rank, idx in enumerate(top5_idx, 1):
                name = config.CLASS_NAMES[idx]
                conf = predictions[0][idx]
                marker = " ◄" if idx == class_idx else ""
                print(f"    {rank}. {name:<40} {conf * 100:6.2f}%{marker}")

        except Exception as e:
            print(f"[ERROR] Gagal menguji gambar: {e}")
            sys.exit(1)

    print("\n[SUCCESS] Pengujian model selesai!")


if __name__ == "__main__":
    main()
