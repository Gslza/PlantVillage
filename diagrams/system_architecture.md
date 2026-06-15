# Arsitektur Sistem — Tomato AIoT Relay Control

## Diagram Aliran Data

```mermaid
flowchart TD
    subgraph INPUT ["📷 Input"]
        CAM["USB Webcam\n640×480"]
    end

    subgraph PYTHON ["🐍 Python Application"]
        CV["OpenCV\nCapture Frame"]
        ROI["Extract ROI\nCenter Crop"]
        PRE["Preprocessing\nResize 224×224\nBGR→RGB\nfloat32 / 255.0\nBatch Dimension"]
        CNN["CNN Model\nbest_scratch.keras\nSoftmax 10 Kelas"]
        CONF["Confidence Filter\n≥ 60%"]
        DEB["Consecutive Frame\nDebounce\n5 Frame Stabil"]
        SCD["State Change\nDetection"]
        SER["PySerial\nUSB Serial"]
        LOG["CSV Logger\ndetection_history.csv"]
        UI["OpenCV UI\nOverlay Info"]
    end

    subgraph MCU ["🔌 Mikrokontroler"]
        ESP["NodeMCU\nESP8266 / ESP32\nSerial.read()"]
        SW["Switch-Case\nH / F / B / V / O"]
        ACK["Serial.println\nACK Response"]
    end

    subgraph OUTPUT ["💡 Output"]
        R1["Relay 1\nHealthy\n🟢"]
        R2["Relay 2\nFungal\n🟡"]
        R3["Relay 3\nBacterial\n🟠"]
        R4["Relay 4\nVirus\n🔴"]
        LED["LED / Lampu DC\n5-12V"]
    end

    CAM --> CV
    CV --> ROI
    ROI --> PRE
    PRE --> CNN
    CNN --> CONF
    CONF --> DEB
    DEB --> SCD
    SCD -->|"State berubah"| SER
    SCD -->|"State berubah"| LOG
    SER -->|"USB Serial\n115200 baud"| ESP
    ESP --> SW
    SW --> R1
    SW --> R2
    SW --> R3
    SW --> R4
    R1 --> LED
    R2 --> LED
    R3 --> LED
    R4 --> LED
    ESP --> ACK
    ACK -->|"ACK:H / ACK:F\nACK:B / ACK:V"| SER
    CV --> UI
    CNN --> UI
```

---

## Diagram State Machine

```mermaid
stateDiagram-v2
    [*] --> STARTUP
    STARTUP --> UNKNOWN: Kirim O\nSemua relay OFF

    UNKNOWN --> HEALTHY: 5 frame stabil\nconfidence ≥ 60%
    UNKNOWN --> FUNGAL: 5 frame stabil\nconfidence ≥ 60%
    UNKNOWN --> BACTERIAL: 5 frame stabil\nconfidence ≥ 60%
    UNKNOWN --> VIRUS: 5 frame stabil\nconfidence ≥ 60%

    HEALTHY --> FUNGAL: State berubah
    HEALTHY --> BACTERIAL: State berubah
    HEALTHY --> VIRUS: State berubah
    HEALTHY --> UNKNOWN: Confidence rendah

    FUNGAL --> HEALTHY: State berubah
    FUNGAL --> BACTERIAL: State berubah
    FUNGAL --> VIRUS: State berubah
    FUNGAL --> UNKNOWN: Confidence rendah

    BACTERIAL --> HEALTHY: State berubah
    BACTERIAL --> FUNGAL: State berubah
    BACTERIAL --> VIRUS: State berubah
    BACTERIAL --> UNKNOWN: Confidence rendah

    VIRUS --> HEALTHY: State berubah
    VIRUS --> FUNGAL: State berubah
    VIRUS --> BACTERIAL: State berubah
    VIRUS --> UNKNOWN: Confidence rendah

    UNKNOWN --> SHUTDOWN: Tekan Q
    HEALTHY --> SHUTDOWN: Tekan Q
    FUNGAL --> SHUTDOWN: Tekan Q
    BACTERIAL --> SHUTDOWN: Tekan Q
    VIRUS --> SHUTDOWN: Tekan Q

    SHUTDOWN --> [*]: Kirim O\nSemua relay OFF
```

---

## Diagram Sequence — Alur Perintah Serial

```mermaid
sequenceDiagram
    participant W as Webcam
    participant P as Python
    participant M as CNN Model
    participant S as Serial USB
    participant E as NodeMCU
    participant R as Relay

    P->>W: Capture frame
    W-->>P: BGR frame 640×480
    P->>P: Extract ROI (center crop)
    P->>P: Preprocess (resize, RGB, /255)
    P->>M: predict(batch)
    M-->>P: softmax [10 kelas]
    P->>P: Confidence ≥ 60%?
    
    alt Confidence OK
        P->>P: Debounce (5 frame stabil?)
        alt Stabil & State berubah
            P->>S: write("F")
            S->>E: Serial byte 'F'
            E->>E: switch(command)
            E->>R: activateRelay(2)
            R-->>R: Relay 2 ON, lainnya OFF
            E-->>S: "ACK:F"
            S-->>P: readline() → "ACK:F"
            P->>P: Log ke CSV
        else Belum stabil
            P->>P: Increment counter
        end
    else Confidence rendah
        P->>P: category = unknown
    end
```

---

## Pemetaan Perintah Serial

| Karakter | Kategori | Relay | Aksi |
|:---:|---|---|---|
| `H` | Healthy | Relay 1 ON | R2, R3, R4 OFF |
| `F` | Fungal | Relay 2 ON | R1, R3, R4 OFF |
| `B` | Bacterial/Pest | Relay 3 ON | R1, R2, R4 OFF |
| `V` | Virus | Relay 4 ON | R1, R2, R3 OFF |
| `O` | Unknown/OFF | Semua OFF | R1, R2, R3, R4 OFF |

---

## Mode Operasi

```mermaid
flowchart LR
    AUTO["🤖 AUTO Mode\nInferensi otomatis\nKontrol relay otomatis"]
    MANUAL["🔧 MANUAL Mode\nKontrol relay manual\nTombol 1-4, 0"]
    
    AUTO -->|"Tekan 1-4 atau 0"| MANUAL
    MANUAL -->|"Tekan A"| AUTO
```
