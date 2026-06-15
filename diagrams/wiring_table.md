# Tabel Wiring — Tomato AIoT Relay Control

## ⚠️ Peringatan Keselamatan

> **PERINGATAN: Gunakan hanya LED 5V, lampu DC kecil, atau beban tegangan rendah 5–12V untuk demonstrasi.**
>
> **JANGAN menggunakan PLN 220V, stop kontak rumah, atau beban AC bertegangan tinggi.**
>
> Relay pada proyek ini dirancang untuk keperluan demonstrasi akademik dengan beban DC tegangan rendah.

---

## Wiring NodeMCU ESP8266

```text
                    ┌─────────────────────┐
                    │   NodeMCU ESP8266    │
                    │                     │
    Relay IN1 ◄─────┤ D1 (GPIO 5)         │
    Relay IN2 ◄─────┤ D2 (GPIO 4)         │
    Relay IN3 ◄─────┤ D5 (GPIO 14)        │
    Relay IN4 ◄─────┤ D6 (GPIO 12)        │
                    │                     │
    Relay VCC ◄─────┤ VIN (5V)            │
    Relay GND ◄─────┤ GND                 │
                    │                     │
    USB ◄───────────┤ Micro USB           │──── ke Laptop/PC
                    └─────────────────────┘
```

| Modul Relay | NodeMCU ESP8266 | Keterangan |
|:-----------:|:---------------:|:----------:|
| IN1 | D1 / GPIO 5 | Relay 1 — Healthy |
| IN2 | D2 / GPIO 4 | Relay 2 — Fungal |
| IN3 | D5 / GPIO 14 | Relay 3 — Bacterial/Pest |
| IN4 | D6 / GPIO 12 | Relay 4 — Virus |
| VCC | VIN (5V) | Daya relay dari USB 5V |
| GND | GND | Ground bersama |

### Catatan ESP8266
- Pin **D1 (GPIO 5)** dan **D2 (GPIO 4)** adalah pin I2C default. Jika menggunakan I2C, gunakan pin lain.
- Pin **D5 (GPIO 14)** adalah SPI CLK default. Tidak masalah jika SPI tidak digunakan.
- **VIN** menyediakan 5V langsung dari USB. Pastikan kabel USB cukup kuat untuk relay.
- Jangan gunakan **D0 (GPIO 16)** — pin ini terhubung ke WAKE dan bisa menyebabkan masalah saat boot.
- Jangan gunakan **D3 (GPIO 0)** dan **D4 (GPIO 2)** — pin ini mempengaruhi mode boot.

---

## Wiring ESP32

```text
                    ┌─────────────────────┐
                    │       ESP32         │
                    │                     │
    Relay IN1 ◄─────┤ GPIO 14             │
    Relay IN2 ◄─────┤ GPIO 27             │
    Relay IN3 ◄─────┤ GPIO 26             │
    Relay IN4 ◄─────┤ GPIO 25             │
                    │                     │
    Relay VCC ◄─────┤ VIN (5V)            │
    Relay GND ◄─────┤ GND                 │
                    │                     │
    USB ◄───────────┤ Micro USB / USB-C   │──── ke Laptop/PC
                    └─────────────────────┘
```

| Modul Relay | ESP32 | Keterangan |
|:-----------:|:-----:|:----------:|
| IN1 | GPIO 14 | Relay 1 — Healthy |
| IN2 | GPIO 27 | Relay 2 — Fungal |
| IN3 | GPIO 26 | Relay 3 — Bacterial/Pest |
| IN4 | GPIO 25 | Relay 4 — Virus |
| VCC | VIN (5V) | Daya relay dari USB 5V |
| GND | GND | Ground bersama |

### Catatan ESP32
- Pin **GPIO 14, 25, 26, 27** adalah pin aman yang tidak mempengaruhi boot.
- Hindari **GPIO 0, 2, 5, 12, 15** — pin ini mempengaruhi mode boot ESP32.
- Hindari **GPIO 6–11** — pin ini terhubung ke flash SPI internal.
- **GPIO 34–39** hanya input, tidak bisa digunakan untuk relay.

---

## Wiring Relay ke LED (Demonstrasi)

```text
    ┌──────────────┐
    │  4-Ch Relay  │
    │              │
    │  NO ─────────┼──── LED (+) Anoda
    │  COM ────────┼──── Power Supply (+) 5V
    │  NC          │
    │              │
    └──────────────┘
                          LED (-) Katoda ──── Resistor 220Ω ──── GND

    Power Supply: Baterai 5V atau adaptor DC 5V terpisah
```

| Terminal Relay | Koneksi | Keterangan |
|:--------------:|:-------:|:----------:|
| NO (Normally Open) | LED Anoda (+) | Terhubung saat relay ON |
| COM (Common) | Power Supply (+) 5V | Sumber daya LED |
| NC (Normally Closed) | — | Tidak digunakan |
| — | LED Katoda (−) → Resistor → GND | Jalur ground |

### Skema per Relay

```text
Power 5V (+) ──── COM ──┤ RELAY ├── NO ──── LED (+) ──── LED (−) ──── R 220Ω ──── GND
```

**Ulangi skema ini untuk keempat relay dan LED.**

---

## Koneksi Ground

> **PENTING:** Ground NodeMCU/ESP32 dan ground modul relay **HARUS** terhubung bersama.

```text
NodeMCU GND ────┬──── Relay GND
                │
                └──── Power Supply GND (jika menggunakan sumber daya terpisah)
```

Jika relay menggunakan sumber daya 5V terpisah (bukan dari VIN NodeMCU), pastikan semua ground terhubung bersama (common ground).

---

## Diagram Blok Keseluruhan

```text
┌──────────┐     USB      ┌───────────────┐    GPIO    ┌─────────────┐   LED/Lampu
│  Laptop  │◄────────────►│   NodeMCU     │◄──────────►│  4-Ch Relay │──────────►  💡
│  Python  │   Serial     │  ESP8266/32   │   IN1-IN4  │   Module    │   NO/COM
│  OpenCV  │   115200     │               │            │             │
│  CNN     │              │  VIN ─► VCC   │            │  VCC ◄─ 5V  │
│  Webcam  │              │  GND ─► GND   │            │  GND ◄─ GND │
└──────────┘              └───────────────┘            └─────────────┘
```
