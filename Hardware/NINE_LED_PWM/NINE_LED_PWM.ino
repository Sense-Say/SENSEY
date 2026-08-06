// NINE_LED_PWM

// Arduino Code
const int LED_1 = 2; 
const int LED_2 = 3; 
const int LED_3 = 4; 
const int LED_4 = 5; 
const int LED_5 = 6; 
const int LED_6 = 7; 
const int LED_7 = 8; 
const int LED_8 = 9; 
const int LED_9 = 10; 

void setup() {
  pinMode(LED_1, OUTPUT); 
  pinMode(LED_2, OUTPUT);
  pinMode(LED_3, OUTPUT);
  pinMode(LED_4, OUTPUT);
  pinMode(LED_5, OUTPUT);
  pinMode(LED_6, OUTPUT);
  pinMode(LED_7, OUTPUT);
  pinMode(LED_8, OUTPUT);
  pinMode(LED_9, OUTPUT);

  Serial.begin(9600);
}

void loop() {

  // --------------------------------------------------------------------
  // Read full packet "region,brightness"
  // --------------------------------------------------------------------
  if (Serial.available()) {

    String data = Serial.readStringUntil('\n');  // reads "5,180"
    int commaIndex = data.indexOf(',');

    if (commaIndex > 0) {
      String regionStr = data.substring(0, commaIndex);
      String brightnessStr = data.substring(commaIndex + 1);

      int region = regionStr.toInt();        // 1–9
      int brightness = brightnessStr.toInt(); // 0–255

      // ----------------------------------------------------------------
      // Turn all LEDs OFF first
      // ----------------------------------------------------------------
      analogWrite(LED_1, 0);
      analogWrite(LED_2, 0);
      analogWrite(LED_3, 0);
      analogWrite(LED_4, 0);
      analogWrite(LED_5, 0);
      analogWrite(LED_6, 0);
      analogWrite(LED_7, 0);
      analogWrite(LED_8, 0);
      analogWrite(LED_9, 0);

      // ----------------------------------------------------------------
      // Turn ONLY the selected LED ON with PWM brightness
      // ----------------------------------------------------------------
      if (region == 1) analogWrite(LED_1, brightness);
      else if (region == 2) analogWrite(LED_2, brightness);
      else if (region == 3) analogWrite(LED_3, brightness);
      else if (region == 4) analogWrite(LED_4, brightness);
      else if (region == 5) analogWrite(LED_5, brightness);
      else if (region == 6) analogWrite(LED_6, brightness);
      else if (region == 7) analogWrite(LED_7, brightness);
      else if (region == 8) analogWrite(LED_8, brightness);
      else if (region == 9) analogWrite(LED_9, brightness);

      // If region is not 1–9, all LEDs remain OFF
    }
  }
}
