# An Accessory for the BMP180 sensor.
# This assumes the bmp180 module is in a package called sensors.

import time

from sensors.bmp180 import BMP180

from pyhap.accessory import Accessory, Category
import pyhap.loader as loader

class BMP180_Accessory(Accessory):

   category = Category.SENSOR

   def __init__(self, *args, **kwargs):
      super(BMP180_Accessory, self).__init__(*args, **kwargs)

      self.temp_char = self.get_service("TemperatureSensor")\
                           .get_characteristic("CurrentTemperature")

      self.sensor = BMP180()

   def _set_services(self):
      super(BMP180_Accessory, self)._set_services()
      self.add_service(
         loader.get_serv_loader().get("TemperatureSensor"))

   def __getstate__(self):
      state = super(BMP180_Accessory, self).__getstate__()
      state["sensor"] = None
      return state

   def __setstate__(self, state):
      self.__dict__.update(state)
      self.sensor = BMP180()

   def run(self):
      while True:
         temp, _pressure = self.sensor.read()
         self.temp_char.set_value(temp)
         time.sleep(30)