"""
serial_test.py — Pengujian relay melalui komunikasi serial.

Mengirim urutan perintah H → F → B → V → O ke NodeMCU
untuk menguji keempat relay tanpa model AI.

Gunakan: python serial_test.py --port COM5 --baud 115200
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("[ERROR] Module 'pyserial' belum terinstal.")
    print("        Jalankan: pip install pyserial")
    sys.exit(1)

import config


def parse_args() -> argparse.Namespace:
    """Parse argumen command line."""
    parser = argparse.ArgumentParser(description="Serial Relay Test")
    parser.add_argument("--port", type=str, default=config.SERIAL_PORT,
                        help=f"COM port (default: {config.SERIAL_PORT})")
    parser.add_argument("--baud", type=int, default=config.BAUD_RATE,
                        help=f"Baud rate (default: {config.BAUD_RATE})")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Delay antar perintah dalam detik (default: 2.0)")
    return parser.parse_args()


def main() -> None:
    """Jalankan pengujian relay secara berurutan."""
    args = parse_args()

    test_sequence = [
        ("H", "Relay 1 — Healthy"),
        ("F", "Relay 2 — Fungal"),
        ("B", "Relay 3 — Bacterial/Pest"),
        ("V", "Relay 4 — Virus"),
        ("O", "All Relays OFF"),
    ]

    print(f"[INFO] Menghubungkan ke {args.port} @ {args.baud} baud...")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
        time.sleep(2)  # Tunggu NodeMCU boot
        print(f"[INFO] Terhubung ke {args.port}")
    except serial.SerialException as e:
        print(f"[ERROR] Gagal membuka {args.port}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"[ERROR] Port {args.port} tidak ditemukan.")
        print("        Periksa Device Manager untuk COM port yang benar.")
        sys.exit(1)

    try:
        # Kirim O dulu untuk memastikan semua relay OFF
        ser.write(b"O")
        ser.flush()
        time.sleep(1)

        for command, description in test_sequence:
            print(f"\n[TEST] {description}")
            print(f"[SERIAL] Mengirim: {command}")

            ser.write(command.encode("utf-8"))
            ser.flush()

            # Baca acknowledgement
            time.sleep(0.5)
            while ser.in_waiting:
                response = ser.readline().decode(errors="ignore").strip()
                if response:
                    print(f"[ESP] {response}")

            print(f"[INFO] Menunggu {args.delay} detik...")
            time.sleep(args.delay)

        print("\n" + "=" * 50)
        print("[SUCCESS] Pengujian relay selesai!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n[INFO] Pengujian dibatalkan oleh pengguna.")
        ser.write(b"O")
        ser.flush()

    except serial.SerialException as e:
        print(f"[ERROR] Kesalahan serial: {e}")

    finally:
        if ser.is_open:
            ser.write(b"O")
            ser.flush()
            time.sleep(0.5)
            ser.close()
            print("[INFO] Port serial ditutup. Semua relay OFF.")


if __name__ == "__main__":
    main()
