# 🚗 SafeRide - Smart Vehicle Safety & Telemetry System

An integrated embedded systems & desktop telemetry project designed to enhance vehicle safety using **Arduino Uno** and a real-time **Python Dashboard**.

## 🌟 Key Features
- **RFID Access Control:** Engine remains locked until an authorized RFID card is scanned.
- **Real-Time Cabin Monitoring:** Continuously tracks cabin temperature (**DHT11**) and hazardous gas/smoke levels (**MQ-2**).
- **Multi-Stage Safety Alerts:**
  - 🟢 **Safe:** Normal driving operation.
  - 🟡 **Early Warning:** Visual alert when temperature (35°C–40°C) or gas (350–500) rises moderately.
  - 🔴 **Emergency Stop:** Automatically cuts engine power, triggers buzzer alarm, and locks the system if temperature > 40°C or gas > 500.
- **Live Python Desktop Dashboard:** Built with `CustomTkinter` & `Matplotlib` featuring live graphs, thermal surge prediction, real-time event logging, and CSV export.

## 🔌 Hardware Pinout (Arduino Uno)

| Component | Arduino Pin |
| :--- | :--- |
| **RFID MFRC522** | SDA: `10`, SCK: `13`, MOSI: `11`, MISO: `12`, RST: `9` |
| **LCD 16x2 (I2C)** | SDA: `A4`, SCL: `A5` (Address: `0x27`) |
| **DHT11 Temp Sensor** | DATA: `2` |
| **MQ-2 Gas Sensor** | A0: `A0` |
| **L298N Motor Driver** | IN1: `3`, IN2: `4` |
| **Active Buzzer** | `+`: `5` |
| **Status LEDs** | Green: `6`, Red: `7`, Yellow: `8` |

## 🚀 How to Run
1. Upload `SafeRide_Arduino.ino` to your Arduino Uno board.
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the dashboard:
   ```bash
   python test.py
   ```
