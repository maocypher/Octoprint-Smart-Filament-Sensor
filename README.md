# Octoprint-Smart-Filament-Sensor

[OctoPrint](http://octoprint.org/) plugin that lets integrate Smart Filament Sensors like BigTreeTechs SmartFilamentSensor directly to RaspberryPi GPIO pins. This enables that this sensor can also be used on 3D Printers, that do not have a E0-Stop like e.g. Creality 1.1.4 Mainboard of Ender 3.

Initial work based on the [Octoprint-Filament-Reloaded](https://github.com/kontakt/Octoprint-Filament-Reloaded) plugin by kontakt.
Fork of [Octoprint-Filament-Revolutions]https://github.com/RomRider/Octoprint-Filament-Revolutions plugin by RomRider.

The solution for this plugin is inspired by [Marlin Firmware](https://github.com/MarlinFirmware/Marlin)

## Required sensor

To use this plugin a Filament Sensor is needed that sends a toogling digital signal (0-1-0...) during movement.

This plugin can use the GPIO.BOARD or GPIO.BCM numbering scheme.

## Features

* Configurable GPIO pins.
* Support movement detection sensors, e.g. Smart-Filament-Sensor.
* Detect if filament is not moving anymore (jammed or runout)
    * Detection based on timeout
    * Detection based on filament position sent with G0 or G1 commands (no negative effects on the print quality anymore compared to the previous version)
    * Alternative pausing commands if M600 is not supported by the printer

## Installation

* Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager).
* Manually using this URL: https://github.com/maocypher/Octoprint-Smart-Filament-Sensor/archive/master.zip

After installation a restart of Octoprint is recommended.

## Configuration
### GPIO Pin
* Choose any free GPIO pin you for data usage, but I would recommend to use GPIO pins without special functionalities like e.g. I2C
* Run the sensor only on 3.3V, because GPIO pins don't like 5V for a long time
* In [BigTreeTech SmartFilamentSensor Manual](https://github.com/bigtreetech/smart-filament-detection-module/tree/master/manual) on page 12 you can find the functionality of the pins. Please ensure that there is no undocumented twist in your cable
* My recommended GPIO pins: 11, 13, 15, 17 (such without any special usage). Please check the [documentation](https://www.raspberrypi.org/documentation/usage/gpio/) of your Raspberry Pi version/model. Also other pins could work, if you know how to configure it on the Raspberry, but it might be tricky and not work out of the box.

Note: The BTT Pins are labeled as follows

S for SIN  <--- signal line (i.e. data source--attach to chosen GPIO pin)
G for GND  <--- This is ground 
V for VDD  <---  +3.3v in

**Attention**
There are two different modes for GPIO pins:
* BCM (Broadcom SOC channel) - the numbers after the GPIO label
* Board - the number of the pin on the board

E.g.
* Board Pin **11**
* BCM GPIO **17**

### Detection time
Currently it is necessary to configure a maximum time period no filament movement was detected. This time could be depended on the print speed and maximum print line length. For the beginning - until I figured out how to estimate the best detection time - you can run a test print and messearue your maximum time and configure this value.
The default value 45 seconds was estimated on max. print speed 10mm/s, for faster prints it could be smaller.

### Detection distance
Version 1.1.2 of this plugin detects the movement depending on the moved distance. These distance is calculated from the GCode sent to the printer. Therefore it is necessary to configure a distance without movement being detected. In Marlin Firmware the default value is set to 7mm. I recommend to set it higher than in the firmware, because it could make the detection much too sensitive.

### Octoprint - Firmware & Protocol
Since currently GCode command M600 is used to interrupt the print, it is recommended to add M600 to the setting "Pausing commands".
Since v1.1.3 there are also alternative pausing commands [M0, M1, M25, M226, M600, M601] available, for those whose printer don't support M600.

### Octoprint - GCode Scripts
If you do not want that the print is paused right on your print, I recommend to add a GCode Script for "After print job is paused". Also adding GCode script "Before print job is resumed" might be useful, in the case you hit the heatbed or print head during the change of the filament or removing the blockage.

### Test script
Advice: don't run the test script in this repository durin a print. This leads to failures in the detection of movements of the print and therefore to missbehaviour of the plugin.

## GCode
### Start GCode
Since the sensor is activated with the first G0 or G1 command it is adviced to perform these commands after complete heatup of the printer.

E.g.
```
; Ender 3 Custom Start G-code
M140 S{material_bed_temperature_layer_0} ; Set Heat Bed temperature
M190 S{material_bed_temperature_layer_0} ; Wait for Heat Bed temperature
M104 S160; start warming extruder to 160
G28 ; Home all axes
G29 ; Auto bed-level (BL-Touch)
G92 E0 ; Reset Extruder
M104 S{material_print_temperature_layer_0} ; Set Extruder temperature
M109 S{material_print_temperature_layer_0} ; Wait for Extruder temperature
G1 X0.1 Y20 Z0.3 F5000.0 ; Move to start position
; G1 Z2.0 F3000 ; Move Z Axis up little to prevent scratching of Heat Bed
G1 X0.4 Y200.0 Z0.3 F5000.0 ; Move to side a little
G1 X0.4 Y20 Z0.3 F1500.0 E30 ; Draw the second line
G92 E0 ; Reset Extruder
G1 Z2.0 F3000 ; Move Z Axis up little to prevent scratching of Heat Bed
; End of custom start GCode
```

## Disclaimer
* I as author of this plugin am not responsible for any damages on your print or printer. As user you are responsible for a sensible usage of this plugin.
* Be cautious not to damage your Raspberry Pi, because of wrong voltage. I don't take any responsibility for wrong wiring.

## Outlook
Support of multiple sensors for multiextruders like 4 channel kraken hotend

## Contact
[![PayPal](https://www.paypalobjects.com/en_US/DK/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?hosted_button_id=AHS3MUTFXXMNG "Donate for Octoprint Smart-Filament-Sensor Plugin")
