# coding=utf-8
from __future__ import absolute_import
import octoprint.plugin
from octoprint.events import Events
import RPi.GPIO as GPIO
from time import sleep
from flask import jsonify
import json
from octoprint_smart_filament_sensor.filament_motion_sensor_timeout_detection import FilamentMotionSensorTimeoutDetection

class SmartFilamentSensor(octoprint.plugin.StartupPlugin,
                                 octoprint.plugin.EventHandlerPlugin,
                                 octoprint.plugin.TemplatePlugin,
                                 octoprint.plugin.SettingsPlugin):

    def initialize(self):
        self._logger.info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
        if GPIO.VERSION < "0.6":       # Need at least 0.6 for edge detection
            raise Exception("RPi.GPIO must be greater than 0.6")
        GPIO.setwarnings(False)        # Disable GPIO warnings

        self.print_started = False
        self.remaining_distance = self.motion_sensor_detection_distance
        self.lastE = -1
        self.currentE = -1
        self.START_DISTANCE_OFFSET = 7
        self.send_code = False
        self.absolut_extrusion = True

#Properties
    @property
    def motion_sensor_pin(self):
        return int(self._settings.get(["motion_sensor_pin"]))

    @property
    def motion_sensor_pause_print(self):
        return self._settings.get_boolean(["motion_sensor_pause_print"])

    @property
    def detection_method(self):
        return int(self._settings.get(["detection_method"]))

    @property
    def motion_sensor_enabled(self):
        return self._settings.get_boolean(["motion_sensor_enabled"])

    @property
    def pause_command(self):
        return self._settings.get(["pause_command"])

#Distance detection
    @property
    def motion_sensor_detection_distance(self):
        return int(self._settings.get(["motion_sensor_detection_distance"]))

#Timeout detection
    @property
    def motion_sensor_max_not_moving(self):
        return int(self._settings.get(["motion_sensor_max_not_moving"]))

#General Properties
    @property
    def mode(self):
        return int(self._settings.get(["mode"]))

    #@property
    #def send_gcode_only_once(self):
    #    return self._settings.get_boolean(["send_gcode_only_once"])

# Initialization methods
    def _setup_sensor(self):
        if(self.mode == 0):
            self._logger.info("Using Board Mode")
            GPIO.setmode(GPIO.BOARD)
        else:
            self._logger.info("Using BCM Mode")
            GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.motion_sensor_pin, GPIO.IN)

        # Add reset_distance if detection_method is distance_detection
        if (self.detection_method == 1):
            # Remove event first, because it might been in use already
            GPIO.remove_event_detect(self.motion_sensor_pin)
            GPIO.add_event_detect(self.motion_sensor_pin, GPIO.BOTH, callback=self.reset_distance)

        if self.motion_sensor_enabled == False:
            self._logger.info("Motion sensor is deactivated")

        self.motion_sensor_filament_moving = True
        self.motion_sensor_thread = None

    def on_after_startup(self):
        self._logger.info("Smart Filament Sensor started")
        self._setup_sensor()

    def get_settings_defaults(self):
        return dict(
            #Motion sensor
            mode=0,    # Board Mode
            motion_sensor_enabled = True, #Sensor detection is enabled by default
            motion_sensor_pin=-1,  # Default is no pin
            detection_method = 0, # 0 = timeout detection, 1 = distance detection

            # Distance detection
            motion_sensor_detection_distance = 15, # Recommended detection distance from Marlin would be 7

            # Timeout detection
            motion_sensor_max_not_moving=45,  # Maximum time no movement is detected - default continously
            pause_command="M600",
            #send_gcode_only_once=False,  # Default set to False for backward compatibility
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._setup_sensor()

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

# Sensor methods
    # Starts the motion sensor if the sensors are enabled
    def motion_sensor_start(self):
        self._logger.debug("Sensor enabled: " + str(self.motion_sensor_enabled))
        
        if self.motion_sensor_enabled:
            if (self.mode == 0):
                self._logger.debug("GPIO mode: Board Mode")
            else:
                self._logger.debug("GPIO mode: BCM Mode")
            self._logger.debug("GPIO pin: " + str(self.motion_sensor_pin))

            # Distance detection            
            if (self.detection_method == 1):
                self._logger.info("Motion sensor started: Distance detection")
                self._logger.debug("Detection Mode: Distance detection")
                self._logger.debug("Distance: " + str(self.motion_sensor_detection_distance))

            # Timeout detection
            elif (self.detection_method == 0):
                if self.motion_sensor_thread == None:
                    self._logger.debug("Detection Mode: Timeout detection")
                    self._logger.debug("Timeout: " + str(self.motion_sensor_max_not_moving))

                    # Start Timeout_Detection thread
                    self.motion_sensor_thread = FilamentMotionSensorTimeoutDetection(1, "MotionSensorTimeoutDetectionThread", self.motion_sensor_pin, 
                        self.motion_sensor_max_not_moving, self._logger, pCallback=self.printer_change_filament)
                    self.motion_sensor_thread.start()
                    self._logger.info("Motion sensor started: Timeout detection")

            self.send_code = False

    # Stop the motion_sensor thread
    def motion_sensor_stop_thread(self):
        if(self.motion_sensor_thread != None):
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._logger.info("Motion sensor stopped")

# Sensor callbacks
    # Send configured pause command to the printer to interrupt the print
    def printer_change_filament (self):
        # Check if stop signal was already sent
        if(not self.send_code):
            self._logger.debug("Motion sensor detected no movement")
            self._logger.info("Pause command: " + self.pause_command)   
            self._printer.commands(self.pause_command)
            self.send_code = True

    # Reset the distance, if the remaining distance is smaller than the new value
    def reset_distance (self, pPin):
        self._logger.debug("Motion sensor detected movement")
        self.send_code = False
        if(self.remaining_distance < self.motion_sensor_detection_distance):
            self.remaining_distance = self.motion_sensor_detection_distance

    # Initialize the distance detection values
    def init_distance_detection(self):
        self.lastE = float(-1)
        self.currentE = float(0)
        self.reset_remainin_distance()

    # Reset the remaining distance on start or resume
    # START_DISTANCE_OFFSET is used for the (re-)start sequence
    def reset_remainin_distance(self):
        self.remaining_distance = float(self.motion_sensor_detection_distance) + self.START_DISTANCE_OFFSET

    # Calculate the remaining distance
    def calc_distance(self, pE):
        if (self.detection_method == 1):
            # Only with absolute extrusion the delta distance must be calculated
            if (self.absolut_extrusion):
                # LastE is not used and set to the same value as currentE
                if (self.lastE == -1):
                    self.lastE = pE
                else:
                    self.lastE = self.currentE
                self.currentE = pE

                self._logger.debug("LastE: " + str(self.lastE) + "; CurrentE: " + str(self.currentE))

            self._logger.debug("Remaining Distance: " + str(self.remaining_distance))

            if(self.remaining_distance > 0):
                # Calculate the remaining distance from detection distance
                # currentE - lastE is the delta distance
                if(self.absolut_extrusion):
                    deltaDistance = self.currentE - self.lastE
                # With relative extrusion the current extrusion value is the delta distance
                else:
                    deltaDistance = float(pE)
                if(deltaDistance > self.motion_sensor_detection_distance):
                    # Calculate the deltaDistance modulo the motion_sensor_detection_distance
                    # Sometimes the polling of M114 is inaccurate so that with the next poll
                    # very high distances are put back followed by zero distance changes
                    deltaDistance = deltaDistance % self.motion_sensor_detection_distance

                self._logger.debug("Delta Distance: " + str(deltaDistance))
                self.remaining_distance = (self.remaining_distance - deltaDistance)
            else:
                self.printer_change_filament()

    # Remove motion sensor thread if the print is paused
    def print_paused(self, pEvent=""):
        self.print_started = False
        self._logger.info("%s: Pausing filament sensors." % (pEvent=""))
        if self.motion_sensor_enabled and self.detection_method == 0:
            self.motion_sensor_stop_thread()

# Events
    def on_event(self, event, payload):     
        if event is Events.PRINT_STARTED:
            self.print_started = True
            if(self.detection_method == 1):
                self.init_distance_detection()

        elif event is Events.PRINT_RESUMED:
            self.print_started = True

            # If distance detection is used reset the remaining distance, because otherwise the print is not resuming anymore
            if(self.detection_method == 1):
                self.reset_remainin_distance()

            self.motion_sensor_start()

        # Start motion sensor on first G1 command
        elif event is Events.Z_CHANGE:
            if(self.print_started):
                self.motion_sensor_start()

                # Set print_started to False to prevent that the starting command is called multiple times
                self.print_started = False         

        # Disable sensor
        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR
        ):
            self._logger.info("%s: Disabling filament sensors." % (event))
            self.print_started = False
            if self.motion_sensor_enabled and self.detection_method == 0:
                self.motion_sensor_stop_thread()

        # Disable motion sensor if paused
        elif event is Events.PRINT_PAUSED:
            self.print_paused(event)

# Plugin update methods
    def get_update_information(self):
        return dict(
            smartfilamentsensor=dict(
                displayName="Smart Filament Sensor",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="maocypher",
                repo="Octoprint-Smart-Filament-Sensor",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/maocypher/Octoprint-Smart-Filament-Sensor/archive/master.zip"
            )
        )

    # Interprete the GCode commands that are sent to the printer to print the 3D object
    # G92: Reset the distance detection values
    # G0 or G1: Caluclate the remaining distance
    def distance_detection(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        # Only performed if distance detection is used
        if(self.detection_method == 1 and self.motion_sensor_enabled):
            if(gcode == "G0" or gcode == "G1"):
                commands = cmd.split(" ")

                for command in commands:
                    if command.startswith("E"):
                        extruder = command[1:]
                        self.calc_distance(float(extruder))
                        self._logger.debug("E: " + extruder)

            elif(gcode == "G92"):
                if(self.detection_method == 1):
                    self.init_distance_detection()
                self._logger.debug("G92: Reset Extruders")

            elif(gcode == "M82"):
                self.absolut_extrusion = True
                self._logger.info("M82: Absolut extrusion")

            elif(gcode == "M83"):
                self.absolut_extrusion = False
                self._logger.info("M83: Relative extrusion")

        return cmd


__plugin_name__ = "Smart Filament Sensor"
__plugin_version__ = "1.1.3"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SmartFilamentSensor()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.distance_detection
    }



def __plugin_check__():
    try:
        import RPi.GPIO
    except ImportError:
        return False

    return True
