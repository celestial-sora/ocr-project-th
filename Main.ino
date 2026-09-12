#include <U8g2lib.h>
#include <Servo.h>
#include <math.h>  // สำหรับ sin() ใช้ทำ Sine Easing

// OLED (ตามที่คุณเทสผ่าน)
U8G2_SSD1306_128X64_NONAME_F_SW_I2C 
u8g2(U8G2_R0, 12, 14, U8X8_PIN_NONE);

#define SERVO_PIN 5    // D1 = GPIO5
#define CLOSE_ANGLE 5  // หยุดที่ 5° แทน 0° เพื่อไม่ให้ไม้กระแทก hard stop

#ifndef LED_BUILTIN
#define LED_BUILTIN 2 // Onboard LED (Active LOW on ESP8266)
#endif

Servo gateServo;

const unsigned long AUTO_CLOSE_DELAY_MS = 18000; // 18 วินาที
unsigned long openTimestamp = 0;
bool isGateOpen = false;
int lastRemainingSec = -1;
int currentAngle = 0; // จำตำแหน่งมุมปัจจุบันของเซอร์โว
String currentTitle = "IDLE";
String currentSubtitle = "NO VEHICLE";

void blinkLed(int durationMs = 80) {
  digitalWrite(LED_BUILTIN, LOW);   // ไฟ LED ติด
  delay(durationMs);
  digitalWrite(LED_BUILTIN, HIGH);  // ไฟ LED ดับ
}

void showText(const String& a, const String& b="") {
  currentTitle = a;
  currentSubtitle = b;
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawUTF8(0, 16, a.c_str());
  u8g2.drawUTF8(0, 36, b.c_str());
  u8g2.sendBuffer();
}

void showOpenWithCountdown(int sec) {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawUTF8(0, 16, currentTitle.c_str());
  u8g2.drawUTF8(0, 36, currentSubtitle.c_str());
  
  // แถบแสดงเวลานับถอยหลังด้านล่างจอ
  String timeStr = "Close in: " + String(sec) + "s";
  u8g2.drawUTF8(0, 56, timeStr.c_str());
  u8g2.sendBuffer();
}

// ฟังก์ชันหมุนความเร็วสูงแบบมี Soft-Start / Heavy Soft-Stop
// โซนเบรก 50 step สุดท้าย ค่อยๆ ชะลอหนักขึ้นเรื่อยๆ ป้องกันไม้กระแทก hard stop
void smoothMoveTo(int targetAngle) {
  if (targetAngle < 0) targetAngle = 0;
  if (targetAngle > 180) targetAngle = 180;
  if (currentAngle == targetAngle) return;

  int step = (targetAngle > currentAngle) ? 1 : -1;
  int totalSteps = abs(targetAngle - currentAngle);

  for (int count = 1; count <= totalSteps; count++) {
    currentAngle += step;
    gateServo.write(currentAngle);

    int remaining = totalSteps - count;
    int delayMs;

    if (count <= 10) {
      // Soft-Start: 10 step แรก ออกตัวนุ่มๆ
      delayMs = 12;
    } else if (remaining < 50) {
      // Heavy Soft-Stop: 50 step สุดท้าย เบรกหนักแบบ progressive
      // remaining 49→0  →  delay 5→35ms (ยิ่งใกล้จุดหยุด ยิ่งช้ามาก)
      delayMs = 5 + ((50 - remaining) * 30) / 50;
    } else {
      // ช่วงกลาง: วิ่งเต็มสปีด
      delayMs = 3;
    }

    delay(delayMs);
    yield();
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // เริ่มต้นปิดไฟ LED

  Serial.begin(115200);
  u8g2.begin();

  gateServo.attach(SERVO_PIN);
  currentAngle = CLOSE_ANGLE;
  gateServo.write(CLOSE_ANGLE); // ตั้งตำแหน่งปิด 5° (ไม่กระแทก hard stop)
  isGateOpen = false;

  blinkLed(200); // กะพริบแจ้งเตือนเมื่อเปิดเครื่องสำเร็จ
  showText("IDLE", "NO VEHICLE");
}

void loop() {
  // ตรวจสอบ Auto-Close และอัปเดตเวลานับถอยหลังบนจอ OLED แบบ Real-time
  if (isGateOpen) {
    unsigned long elapsed = millis() - openTimestamp;
    if (elapsed >= AUTO_CLOSE_DELAY_MS) {
      smoothMoveTo(CLOSE_ANGLE);
      isGateOpen = false;
      lastRemainingSec = -1;
      showText("IDLE", "NO VEHICLE");
      blinkLed(100);
    } else {
      int remaining = (AUTO_CLOSE_DELAY_MS - elapsed + 999) / 1000;
      if (remaining != lastRemainingSec) {
        lastRemainingSec = remaining;
        showOpenWithCountdown(remaining);
      }
    }
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
        Serial.print("STATUS:OPEN:180:");
        Serial.println(remaining);
      } else {
        Serial.println("STATUS:CLOSED:0:0");
      }
      return;
    }

    if (cmd == "OPEN" || cmd == "180") {
      isGateOpen = true;
      openTimestamp = millis();
      showText("GATE: OPEN", "Angle: 180 (18s)");
      smoothMoveTo(180);
    }
    else if (cmd == "CLOSE" || cmd == "0") {
      isGateOpen = false;
      showText("GATE: CLOSED", "Angle: 0");
      smoothMoveTo(CLOSE_ANGLE);
    }
    else if (cmd.startsWith("OPEN:")) {
      String plate = cmd.substring(5);
      isGateOpen = true;
      openTimestamp = millis();
      showText("ACCESS ALLOWED", plate);
      smoothMoveTo(180);
    }
    else if (cmd.startsWith("DENIED:")) {
      String plate = cmd.substring(7);
      isGateOpen = false;
      showText("ACCESS DENIED", plate);
      smoothMoveTo(CLOSE_ANGLE);
    }
    else if (cmd == "IDLE" || cmd == "NOT_FOUND") {
      isGateOpen = false;
      showText("IDLE", "NO VEHICLE");
      smoothMoveTo(CLOSE_ANGLE);
    }
    else if (cmd.length() > 0) {
      int val = cmd.toInt();
      if (val >= 0 && val <= 180) {
        if (val > 0) {
          isGateOpen = true;
          openTimestamp = millis();
        } else {
          isGateOpen = false;
        }
        showText("SERVO GOTO", String(val));
        smoothMoveTo(val);
      }
    }
  }
}