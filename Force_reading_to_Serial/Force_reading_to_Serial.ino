#include "HX711.h"

HX711 scale;

//  adjust pins if needed
uint8_t dataPin = 18;
uint8_t clockPin = 19;

float mass;
float force;


void setup()
{
  Serial.begin(9600);
  Serial.println("loading");

  scale.begin(dataPin, clockPin);

  scale.set_offset(49611);
  scale.set_scale(141.093994);

  scale.tare();
}


void loop()
{
  //  continuous scale 4x per second
  // Serial.println("start");

  mass = scale.get_units(2);
  force = (mass/1000)*9.81;

  Serial.println(force);
  //Serial.println("reading");
  delay(1);
}


//  -- END OF FILE --

