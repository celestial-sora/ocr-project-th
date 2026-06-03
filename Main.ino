#include <U8g2lib.h>
#include <Servo.h>

// OLED (ตามที่คุณเทสผ่าน)
U8G2_SSD1306_128X64_NONAME_F_SW_I2C 
u8g2(U8G2_R0, 12, 14, U8X8_PIN_NONE);

#define SERVO_PIN 5   // D1 = GPIO5

Servo gateServo;

void showText(const String& a, const String& b="") {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawUTF8(0, 16, a.c_str());
  u8g2.drawUTF8(0, 36, b.c_str());
  u8g2.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  u8g2.begin();

  gateServo.attach(SERVO_PIN);
  gateServo.write(0);   // ปิดไม้กั้น

  showText("Femboy is Here", "Servo COOKED!!");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "OPEN" || cmd == "90") {
      gateServo.write(90);
      showText("GATE: OPEN", "Angle: 90");
    }
    else if (cmd == "CLOSE" || cmd == "0") {
      gateServo.write(0);
      showText("GATE: CLOSED", "Angle: 0");
    }
    else if (cmd.startsWith("OPEN:")) {
      String plate = cmd.substring(5);
      gateServo.write(90);
      showText("ACCESS ALLOWED", plate);
    }
    else if (cmd.startsWith("DENIED:")) {
      String plate = cmd.substring(7);
      gateServo.write(0);
      showText("ACCESS DENIED", plate);
    }
    else if (cmd.length() > 0) {
      int val = cmd.toInt();
      if (val > 0 && val <= 180) {
        gateServo.write(val);
        showText("SERVO GOTO", String(val));
      }
    }
  }
}