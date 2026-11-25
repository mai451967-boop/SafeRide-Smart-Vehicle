#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// تعريف منافذ قارئ RFID
#define SS_PIN 10
#define RST_PIN 9
MFRC522 mfrc522(SS_PIN, RST_PIN);

// تعريف شاشة LCD I2C بالعنوان 0x27
LiquidCrystal_I2C lcd(0x27, 16, 2);

// تعريف حساس الحرارة DHT11
#define DHTPIN 2
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// تعريف باقي المنافذ
#define MQ2_PIN A0
#define START_BTN_PIN A1  // سلك بديل لتشغيل السيارة بلمسة مع GND
#define MOTOR_IN1 3
#define MOTOR_IN2 4
#define BUZZER_PIN 5
#define GREEN_LED 6
#define RED_LED 7
#define YELLOW_LED 8

// حدود الأمان المعدلة للتجربة السريعة والآمنة
const float WARN_TEMP = 29.0;
const float DANGER_TEMP = 30.5;
const int WARN_GAS = 260;
const int DANGER_GAS = 300;

bool isSystemUnlocked = false;
String currentCardID = "NONE";
String systemStatus = "LOCKED";

unsigned long previousMillis = 0;
const long interval = 500;

float currentTemp = 0.0;
int currentGas = 0;

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  
  lcd.init();
  lcd.backlight();
  dht.begin();
  
  pinMode(START_BTN_PIN, INPUT_PULLUP);
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  
  lockSystem("System Locked", "Swipe RFID Card");
}

void loop() {
  checkRFID();
  
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    readSensors();
    evaluateSafety();
    updateLCD();
    sendSerialData();
  }
}

void unlockVehicle(String id) {
  if (!isSystemUnlocked) {
    readSensors();
    if (currentTemp > DANGER_TEMP || currentGas > DANGER_GAS) {
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("DANGER! Cannot");
      lcd.setCursor(0, 1);
      lcd.print("Unlock System!");
      tone(BUZZER_PIN, 1000, 300);
      delay(1000);
      return;
    }
    
    currentCardID = id;
    isSystemUnlocked = true;
    systemStatus = "SAFE";
    
    digitalWrite(RED_LED, LOW);
    digitalWrite(YELLOW_LED, LOW);
    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
    
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Access Granted!");
    lcd.setCursor(0, 1);
    lcd.print("ID: " + currentCardID);
    delay(1000);
    lcd.clear();
  }
}

void checkRFID() {
  // 1. التشغيل بلمس سلك A1 بالخط الأزرق (-)
  if (digitalRead(START_BTN_PIN) == LOW) {
    unlockVehicle("A4F92B1C");
    return;
  }

  // 2. التشغيل بكارت RFID
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }
  
  String uidStr = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();
  
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  unlockVehicle(uidStr);
}

void readSensors() {
  float t = dht.readTemperature();
  if (!isnan(t)) {
    currentTemp = t;
  }
  currentGas = analogRead(MQ2_PIN);
}

void evaluateSafety() {
  if (!isSystemUnlocked) return;
  
  // حالة الخطر الشديد
  if (currentTemp > DANGER_TEMP || currentGas > DANGER_GAS) {
    systemStatus = (currentTemp > DANGER_TEMP) ? "DANGER_TEMP" : "DANGER_GAS";
    isSystemUnlocked = false;
    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, LOW);
    digitalWrite(GREEN_LED, LOW);
    digitalWrite(YELLOW_LED, LOW);
    digitalWrite(RED_LED, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("EMERGENCY STOP!");
    lcd.setCursor(0, 1);
    if (systemStatus == "DANGER_TEMP") {
      lcd.print("HIGH TEMP: " + String(currentTemp, 1) + "C");
    } else {
      lcd.print("GAS LEAK: " + String(currentGas));
    }
    return;
  }
  
  // حالة التحذير المبدئي
  if ((currentTemp >= WARN_TEMP && currentTemp <= DANGER_TEMP) || (currentGas >= WARN_GAS && currentGas <= DANGER_GAS)) {
    systemStatus = "WARNING";
    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(YELLOW_LED, HIGH);
    digitalWrite(RED_LED, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
  } else {
    systemStatus = "SAFE";
    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(YELLOW_LED, LOW);
    digitalWrite(RED_LED, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
  }
}

void updateLCD() {
  if (!isSystemUnlocked) {
    if (systemStatus == "LOCKED") {
      lcd.setCursor(0, 0);
      lcd.print("System Locked   ");
      lcd.setCursor(0, 1);
      lcd.print("Swipe RFID Card ");
    }
    return;
  }
  
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(currentTemp, 1);
  lcd.print("C ");
  lcd.print("G:");
  lcd.print(currentGas);
  lcd.print("   ");
  
  lcd.setCursor(0, 1);
  if (systemStatus == "WARNING") {
    lcd.print("Status: WARNING!");
  } else {
    lcd.print("Status: SAFE    ");
  }
}

void sendSerialData() {
  Serial.print("DATA,");
  Serial.print(currentTemp, 1);
  Serial.print(",");
  Serial.print(currentGas);
  Serial.print(",");
  Serial.print(systemStatus);
  Serial.print(",");
  Serial.println(currentCardID);
}

void lockSystem(String line1, String line2) {
  isSystemUnlocked = false;
  systemStatus = "LOCKED";
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, HIGH);
  digitalWrite(BUZZER_PIN, LOW);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}
