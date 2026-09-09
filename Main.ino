#include <U8g2lib.h>
#include <Servo.h>

// OLED (ตามที่คุณเทสผ่าน)
U8G2_SSD1306_128X64_NONAME_F_SW_I2C 
u8g2(U8G2_R0, 12, 14, U8X8_PIN_NONE);

#define SERVO_PIN 5   // D1 = GPIO5

#ifndef LED_BUILTIN
#define LED_BUILTIN 2 // Onboard LED (Active LOW on ESP8266)
#endif

Servo gateServo;

const unsigned long AUTO_CLOSE_DELAY_MS = 24000; // 24 วินาที
unsigned long openTimestamp = 0;
bool isGateOpen = false;

void blinkLed(int durationMs = 80) {
  digitalWrite(LED_BUILTIN, LOW);   // ไฟ LED ติด
  delay(durationMs);
  digitalWrite(LED_BUILTIN, HIGH);  // ไฟ LED ดับ
}

void showText(const String& a, const String& b="") {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawUTF8(0, 16, a.c_str());
  u8g2.drawUTF8(0, 36, b.c_str());
  u8g2.sendBuffer();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // เริ่มต้นปิดไฟ LED

  Serial.begin(115200);
  u8g2.begin();

  gateServo.attach(SERVO_PIN);
  gateServo.write(0); // ตั้งตำแหน่งเริ่มต้นที่ 0 องศา (PWM ทำงานตลอด ไม่ตัด)
  isGateOpen = false;

  blinkLed(200); // กะพริบแจ้งเตือนเมื่อเปิดเครื่องสำเร็จ
  showText("IDLE", "NO VEHICLE");
}

void loop() {
  // ตรวจสอบ Auto-Close เมื่อครบ 24 วินาที
  if (isGateOpen && (millis() - openTimestamp >= AUTO_CLOSE_DELAY_MS)) {
    gateServo.write(0);
    isGateOpen = false;
    showText("IDLE", "NO VEHICLE");
    blinkLed(100);
  }

  if (Serial.available()) {
    blinkLed(80); // กระพริบไฟทุกครั้งที่ได้รับคำสั่ง
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    // Handshake Verification
    if (cmd == "PING:OCR_CONTROLLER") {
      Serial.println("PONG:OCR_GATE");
      return;
    }

    // Status Query
    if (cmd == "STATUS") {
      if (isGateOpen) {
        unsigned long elapsed = millis() - openTimestamp;
        long remaining = (AUTO_CLOSE_DELAY_MS > elapsed) ? (AUTO_CLOSE_DELAY_MS - elapsed) / 1000 : 0;
        Serial.print("STATUS:OPEN:80:");
        Serial.println(remaining);
      } else {
        Serial.println("STATUS:CLOSED:0:0");
      }
      return;
    }

    if (cmd == "OPEN" || cmd == "80" || cmd == "90") {
      gateServo.write(80);
      isGateOpen = true;
      openTimestamp = millis();
      showText("GATE: OPEN", "Angle: 80 (24s)");
    }
    else if (cmd == "CLOSE" || cmd == "0") {
      gateServo.write(0);
      isGateOpen = false;
      showText("GATE: CLOSED", "Angle: 0");
    }
    else if (cmd.startsWith("OPEN:")) {
      String plate = cmd.substring(5);
      gateServo.write(80);
      isGateOpen = true;
      openTimestamp = millis();
      showText("ACCESS ALLOWED", plate);
    }
    else if (cmd.startsWith("DENIED:")) {
      String plate = cmd.substring(7);
      gateServo.write(0);
      isGateOpen = false;
      showText("ACCESS DENIED", plate);
    }
    else if (cmd == "IDLE" || cmd == "NOT_FOUND") {
      gateServo.write(0);
      isGateOpen = false;
      showText("IDLE", "NO VEHICLE");
    }
    else if (cmd.length() > 0) {
      int val = cmd.toInt();
      if (val >= 0 && val <= 180) {
        gateServo.write(val);
        if (val > 0) {
          isGateOpen = true;
          openTimestamp = millis();
        } else {
          isGateOpen = false;
        }
        showText("SERVO GOTO", String(val));
      }
    }
  }
}