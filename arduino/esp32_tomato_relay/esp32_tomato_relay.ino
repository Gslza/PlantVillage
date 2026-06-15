/*
 * esp32_tomato_relay.ino
 * 
 * Sketch ESP32 untuk Tomato AIoT Relay Control.
 * Menerima perintah serial 1 karakter dari Python untuk
 * mengaktifkan salah satu dari 4 relay.
 * 
 * Perintah:
 *   H = Relay 1 ON (Healthy)
 *   F = Relay 2 ON (Fungal)
 *   B = Relay 3 ON (Bacterial/Pest)
 *   V = Relay 4 ON (Virus)
 *   O = Semua relay OFF
 * 
 * Wiring ESP32:
 *   Relay IN1 → GPIO 14
 *   Relay IN2 → GPIO 27
 *   Relay IN3 → GPIO 26
 *   Relay IN4 → GPIO 25
 *   Relay VCC → VIN (5V)
 *   Relay GND → GND
 * 
 * Baud rate: 115200
 */

// ═══════════════════════════════════════════════════════════════
// Konfigurasi Pin Relay
// ═══════════════════════════════════════════════════════════════
#define RELAY_1  14   // GPIO 14
#define RELAY_2  27   // GPIO 27
#define RELAY_3  26   // GPIO 26
#define RELAY_4  25   // GPIO 25

// ═══════════════════════════════════════════════════════════════
// Konfigurasi Active-Low
// ═══════════════════════════════════════════════════════════════
// Sebagian besar modul relay bersifat active-low:
//   LOW  = relay ON
//   HIGH = relay OFF
// Ubah ke false jika modul relay Anda active-high.
#define RELAY_ACTIVE_LOW true

// ═══════════════════════════════════════════════════════════════
// Baud Rate
// ═══════════════════════════════════════════════════════════════
#define SERIAL_BAUD 115200

// ═══════════════════════════════════════════════════════════════
// Array pin relay untuk iterasi
// ═══════════════════════════════════════════════════════════════
const uint8_t relayPins[] = { RELAY_1, RELAY_2, RELAY_3, RELAY_4 };
const uint8_t NUM_RELAYS = sizeof(relayPins) / sizeof(relayPins[0]);

// ═══════════════════════════════════════════════════════════════
// Fungsi Abstraksi Relay
// ═══════════════════════════════════════════════════════════════

/**
 * Mengatur state relay dengan abstraksi active-low/active-high.
 * 
 * @param pin   Pin GPIO relay.
 * @param active  true = relay ON, false = relay OFF.
 */
void setRelay(uint8_t pin, bool active) {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(pin, active ? LOW : HIGH);
  } else {
    digitalWrite(pin, active ? HIGH : LOW);
  }
}

/**
 * Matikan semua relay.
 */
void allRelaysOff() {
  for (uint8_t i = 0; i < NUM_RELAYS; i++) {
    setRelay(relayPins[i], false);
  }
}

/**
 * Aktifkan satu relay dan matikan yang lain.
 * 
 * @param relayNumber  Nomor relay (1-4).
 */
void activateRelay(int relayNumber) {
  allRelaysOff();
  
  if (relayNumber >= 1 && relayNumber <= (int)NUM_RELAYS) {
    setRelay(relayPins[relayNumber - 1], true);
  }
}

// ═══════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════
void setup() {
  // Inisialisasi serial
  Serial.begin(SERIAL_BAUD);
  
  // Inisialisasi pin relay sebagai OUTPUT
  for (uint8_t i = 0; i < NUM_RELAYS; i++) {
    pinMode(relayPins[i], OUTPUT);
  }
  
  // Pastikan semua relay OFF saat boot
  allRelaysOff();
  
  // Pesan boot
  Serial.println("BOOT:ESP32_TOMATO_RELAY");
  Serial.println("STATUS:READY");
}

// ═══════════════════════════════════════════════════════════════
// Loop
// ═══════════════════════════════════════════════════════════════
void loop() {
  // Cek apakah ada data serial masuk
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    // Abaikan newline dan carriage return
    if (command == '\n' || command == '\r') {
      return;
    }
    
    // Proses perintah
    switch (command) {
      case 'H':
        activateRelay(1);
        Serial.println("ACK:H");
        break;
        
      case 'F':
        activateRelay(2);
        Serial.println("ACK:F");
        break;
        
      case 'B':
        activateRelay(3);
        Serial.println("ACK:B");
        break;
        
      case 'V':
        activateRelay(4);
        Serial.println("ACK:V");
        break;
        
      case 'O':
        allRelaysOff();
        Serial.println("ACK:O");
        break;
        
      default:
        allRelaysOff();
        Serial.println("ERR:UNKNOWN_COMMAND");
        break;
    }
  }
}
