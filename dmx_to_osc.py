#!/usr/bin/env python2.7

#################
#   imports

# standard modules
import argparse
import ConfigParser
import logging

# 3rd party modules
from oscpy.client import send_message as send_osc_message
from ola.ClientWrapper import ClientWrapper

__version__ = "0.0.2"
__version_date__ = "2019-07-24"
__license__ = "GPLv3"
__description__ = "script to receive dmx and send out osc commands to osc server"


#################
#   default and internal vars

dmx_num_channels = 512

default_config_file_path = "./dmx_to_osc.ini"
default_dmx_universe = 1
default_osc_port = 7000

last_dmx_block = [0] * dmx_num_channels
osc_handle = None

valid_osc_commands = {
    "/SelectGroup": {
        "type": "int/value",
        "description": "Select group in (n)th position from the bottom of the layer list"
    },
    "/SelectGroup1": {
        "type": "bool/trigger",
        "description": "Select the group at the bottom of the layer list"
    },
    "/SelectGroup2": {
        "type": "bool/trigger",
        "description": "Select the group in second position from the bottom of the layer list"
    },
    "/SelectGroup3": {
        "type": "bool/trigger",
        "description": "Select the group in third position from the bottom of the layer list"
    },
    "/SelectGroup4": {
        "type": "bool/trigger",
        "description": "Select the group in fourth position from the bottom of the layer list"
    },
    "/SelectGroup5": {
        "type": "bool/trigger",
        "description": "Select the group in fifth position from the bottom of the layer list"
    },
    "/SelectGroup6": {
        "type": "bool/trigger",
        "description": "Select the group in sixth position from the bottom of the layer list"
    },
    "/SelectGroup7": {
        "type": "bool/trigger",
        "description": "Select the group in seventh position from the bottom of the layer list"
    },
    "/SelectGroup8": {
        "type": "bool/trigger",
        "description": "Select the group in eighth position from the bottom of the layer list"
    },
    "/SelectGroup9": {
        "type": "bool/trigger",
        "description": "Select the group in ninth position from the bottom of the layer list"
    },
    "/SelectGroup10": {
        "type": "bool/trigger",
        "description": "Select the group in tenth position from the bottom of the layer list"
    },
    "/changeSeq": {
        "type": "int/value",
        "description": "Select sequence"
    },
    "/SeqControlPlay": {
        "type": "bool/trigger",
        "description": "Play/Pause timeline"
    },
    "/SeqControlPrevious": {
        "type": "bool/trigger",
        "description": "Select previous sequence / Restart current sequence if playback is on"
    },
    "/SeqControlNext": {
        "type": "bool/trigger",
        "description": "Next sequence"
    },
    "/SeqControlStop": {
        "type": "bool/trigger",
        "description": "Stop playback"
    },
    "/SeqControlShuffle": {
        "type": "bool/toggle",
        "description": "Toggle random sequence playback"
    },
    "/SeqControlAdd": {
        "type": "bool/trigger",
        "description": "Add sequence"
    },
    "/SeqControlDelete": {
        "type": "bool/trigger",
        "description": "Delete selected sequence"
    },
    "/Tempo": {
        "type": "int/value",
        "description": "Change BPM value"
    },
    "/TapTempo": {
        "type": "bool/trigger",
        "description": "Trigger TAP module"
    },
    "/PlayerPlayPause/idPlayer": {
        "type": "int/value",
        "description": "Play/Pause player"
    },
    "/PlayAllPlayers": {
        "type": "bool/trigger",
        "description": "Play all players in sequence"
    },
    "/PauseAllPlayers": {
        "type": "bool/trigger",
        "description": "Pause all players in sequence"
    },
    "/StopAllPlayers": {
        "type": "bool/trigger",
        "description": "Stop all players in sequence"
    },
    "/BorderActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/BorderMode": {
        "type": "bool/trigger",
        "description": "Switch mode"
    },
    "/BorderColor": {
        "type": "range_0_127",
        "description": "Change color"
    },
    "/BorderWidth": {
        "type": "range_0_127",
        "description": "Change thickness value"
    },
    "/BorderSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/BorderPhase": {
        "type": "range_0_127",
        "description": "Change phase value"
    },
    "/LineActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/LineMode": {
        "type": "bool/trigger",
        "description": "Switch mode"
    },
    "/LineColor": {
        "type": "range_0_127",
        "description": "Change color"
    },
    "/LineWidth": {
        "type": "range_0_127",
        "description": "Change thickness value"
    },
    "/LineLength": {
        "type": "range_0_127",
        "description": "Change length value"
    },
    "/LineNumber": {
        "type": "range_0_127",
        "description": "Change number of dashes"
    },
    "/LineSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/LinePhase": {
        "type": "range_0_127",
        "description": "Change phase value"
    },
    "/LineDirection": {
        "type": "bool/trigger",
        "description": "Switch direction"
    },
    "/RepeatActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/RepeatNumber": {
        "type": "range_0_127",
        "description": "Change number of duplications"
    },
    "/RepeatDepth": {
        "type": "range_0_127",
        "description": "Change depth value"
    },
    "/RepeatCenter": {
        "type": "bool/custom",
        "description": "Toggle origin"
    },
    "/FillColorActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/FillColorNormalActivated": {
        "type": "bool/trigger",
        "description": "Select Plain Color mode"
    },
    "/FillColorNormal": {
        "type": "range_0_127",
        "description": "Change Plain color"
    },
    "/FillColorGradientActivated": {
        "type": "bool/trigger",
        "description": "Select Gradient mode"
    },
    "/FillColorGradient1": {
        "type": "range_0_127",
        "description": "Change Gradient color 1"
    },
    "/FillColorGradient2": {
        "type": "range_0_127",
        "description": "Change Gradient color 2"
    },
    "/FillColorGradientMode": {
        "type": "bool/trigger",
        "description": "Switch Gradient motion mode"
    },
    "/FillColorGradientDirection": {
        "type": "range_0_127",
        "description": "Change angle for Gradient direction 1"
    },
    "/FillColorGradientDirection2": {
        "type": "range_0_127",
        "description": "Change angle for Gradient direction 2"
    },
    "/FillColorGradientSpeed": {
        "type": "range_0_127",
        "description": "Change Gradient speed value"
    },
    "/FillColorGradientPhase": {
        "type": "range_0_127",
        "description": "Change Gradient phase value"
    },
    "/FillColorRandomActivated": {
        "type": "bool/trigger",
        "description": "Select Random mode"
    },
    "/FillColorRandom1": {
        "type": "range_0_127",
        "description": "Change Random color 1"
    },
    "/FillColorRandom2": {
        "type": "range_0_127",
        "description": "Change Random color 2"
    },
    "/FillColorRandom3": {
        "type": "range_0_127",
        "description": "Change Random color 3"
    },
    "/FillColorRandom4": {
        "type": "range_0_127",
        "description": "Change Random color 4"
    },
    "/FillColorRandom5": {
        "type": "range_0_127",
        "description": "Change Random color 5"
    },
    "/FillColorRandomWeight1": {
        "type": "range_0_127",
        "description": "Change weight of Random color 1"
    },
    "/FillColorRandomWeight2": {
        "type": "range_0_127",
        "description": "Change weight of Random color 2"
    },
    "/FillColorRandomWeight3": {
        "type": "range_0_127",
        "description": "Change weight of Random color 3"
    },
    "/FillColorRandomWeight4": {
        "type": "range_0_127",
        "description": "Change weight of Random color 4"
    },
    "/FillColorRandomWeight5": {
        "type": "range_0_127",
        "description": "Change weight of Random color 5"
    },
    "/FillColorRandomMode": {
        "type": "bool/trigger",
        "description": "Switch Random shuffle mode"
    },
    "/FillColorRandomTempo": {
        "type": "range_0_127",
        "description": "Change Random speed/tempo value"
    },
    "/FillColorRandomTransition": {
        "type": "bool/none_smooth",
        "description": "Toggle Random transition mode"
    },
    "/FillSpecialActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/FillSpecialSwipeSolo": {
        "type": "bool/trigger",
        "description": "Select Swipe (solo) mode"
    },
    "/FillSpecialInside": {
        "type": "bool/trigger",
        "description": "Select Inside mode"
    },
    "/FillSpecialOutside": {
        "type": "bool/trigger",
        "description": "Select Outside mode"
    },
    "/FillSpecialCorner": {
        "type": "bool/trigger",
        "description": "Select Corner mode"
    },
    "/FillSpecialStairs": {
        "type": "bool/trigger",
        "description": "Select Stairs mode"
    },
    "/FillSpecialSwipeGlobal": {
        "type": "bool/trigger",
        "description": "Select Swipe (global) mode"
    },
    "/FillSpecialHypnotic": {
        "type": "bool/trigger",
        "description": "Select Hypnotic mode"
    },
    "/FillSpecialStripes": {
        "type": "bool/trigger",
        "description": "Select Stripes mode"
    },
    "/FillSpecialDoubleStripes": {
        "type": "bool/trigger",
        "description": "Select Double Stripes mode"
    },
    "/FillSpecialMosaic": {
        "type": "bool/trigger",
        "description": "Select Mosaic mode"
    },
    "/FillSpecialColor": {
        "type": "range_0_127",
        "description": "Change color"
    },
    "/FillSpecialValue": {
        "type": "range_0_127",
        "description": "Change fill percentage"
    },
    "/FillSpecialSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/FillSpecialPhase": {
        "type": "range_0_127",
        "description": "Change phase value"
    },
    "/FillSpecialSizeStripes": {
        "type": "range_0_127",
        "description": "Change stripes width"
    },
    "/FillSpecialSizeStripes2": {
        "type": "range_0_127",
        "description": "Change second stripes width"
    },
    "/FillSpecialDirection": {
        "type": "range_0_127",
        "description": "Change direction 1 angle"
    },
    "/FillSpecialDirection2": {
        "type": "range_0_127",
        "description": "Change direction 2 angle"
    },
    "/FillSpecialCenter": {
        "type": "bool/custom",
        "description": "Toggle origin"
    },
    "/FillSnakeActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/FillSnakeApplyColor": {
        "type": "bool/toggle",
        "description": "Apply/don't apply Snake on Color"
    },
    "/FillSnakeApplySpecial": {
        "type": "bool/toggle",
        "description": "Apply/don't apply Snake on Special"
    },
    "/FillSnakeDirection": {
        "type": "bool/trigger",
        "description": "Switch direction"
    },
    "/FillSnakeSize": {
        "type": "range_0_127",
        "description": "Change number of parts"
    },
    "/FillSnakeSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/RotationActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/RotationX": {
        "type": "bool/toggle",
        "description": "Check/uncheck X axis"
    },
    "/RotationY": {
        "type": "bool/toggle",
        "description": "Check/uncheck Y axis"
    },
    "/RotationZ": {
        "type": "bool/toggle",
        "description": "Check/uncheck Z axis"
    },
    "/RotationCenter": {
        "type": "bool/custom",
        "description": "Toggle origin"
    },
    "/RotationDirection": {
        "type": "bool/trigger",
        "description": "Switch direction"
    },
    "/RotationSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/RotationPhase": {
        "type": "range_0_127",
        "description": "Change phase value"
    },
    "/StructureActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/StructureRadialGlow": {
        "type": "bool/trigger",
        "description": "Select Radial Glow mode"
    },
    "/StructureWireframe": {
        "type": "bool/trigger",
        "description": "Select Wire Frame mode"
    },
    "/StructureOrigami": {
        "type": "bool/trigger",
        "description": "Select Origami mode"
    },
    "/StructureRoundTrip": {
        "type": "bool/trigger",
        "description": "Select Round Trip mode"
    },
    "/StructureElasticPosition": {
        "type": "bool/trigger",
        "description": "Select Elastic Position mode"
    },
    "/StructureElasticRotation": {
        "type": "bool/trigger",
        "description": "Select Elastic Rotation mode"
    },
    "/StructureElasticScale": {
        "type": "bool/trigger",
        "description": "Select Elastic Scale mode"
    },
    "/StructureStrokes": {
        "type": "bool/trigger",
        "description": "Select Strokes mode"
    },
    "/StructureColor": {
        "type": "range_0_127",
        "description": "Change color"
    },
    "/StructureWidth": {
        "type": "range_0_127",
        "description": "Change thickness value"
    },
    "/StructureDepth": {
        "type": "range_0_127",
        "description": "Change depth value"
    },
    "/StructureSpeed": {
        "type": "range_0_127",
        "description": "Change speed value"
    },
    "/StructurePhase": {
        "type": "range_0_127",
        "description": "Change phase value"
    },
    "/StructureNumber": {
        "type": "range_0_127",
        "description": "Change instances number"
    },
    "/StructureMultiplier": {
        "type": "range_0_127",
        "description": "Change instances multiplier"
    },
    "/StructureInsidePhase": {
        "type": "range_0_127",
        "description": "Change inner offset value"
    },
    "/StructureCenter": {
        "type": "bool/custom",
        "description": "Toggle origin"
    },
    "/StructureDirection": {
        "type": "bool/trigger",
        "description": "Switch direction"
    },
    "/StructureSplitEllipse": {
        "type": "range_0_127",
        "description": "Number of segments for ellipses"
    },
    "/StartTActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/StartTSwipe": {
        "type": "bool/trigger",
        "description": "Select Swipe mode"
    },
    "/StartTInside": {
        "type": "bool/trigger",
        "description": "Select Inside mode"
    },
    "/StartTOutside": {
        "type": "bool/trigger",
        "description": "Select Outside mode"
    },
    "/StartTCorner": {
        "type": "bool/trigger",
        "description": "Select Corner mode"
    },
    "/StartTStairs": {
        "type": "bool/trigger",
        "description": "Select Stairs mode"
    },
    "/StartTFade": {
        "type": "bool/trigger",
        "description": "Select Fade mode"
    },
    "/StartTBlinds": {
        "type": "bool/trigger",
        "description": "Select Blinds mode"
    },
    "/StartTFalls": {
        "type": "bool/trigger",
        "description": "Select Falls mode"
    },
    "/StartTDirection": {
        "type": "range_0_127",
        "description": "Change direction angle"
    },
    "/StartTOrientation": {
        "type": "bool/trigger",
        "description": "Switch direction (left-right)"
    },
    "/StartTUpperLeft": {
        "type": "bool/trigger",
        "description": "Select upper left origin"
    },
    "/StartTUpperRight": {
        "type": "bool/trigger",
        "description": "Select upper right origin"
    },
    "/StartTCenter": {
        "type": "bool/trigger",
        "description": "Select center origin"
    },
    "/StartTBottomLeft": {
        "type": "bool/trigger",
        "description": "Select bottom left origin"
    },
    "/StartTBottomRight": {
        "type": "bool/trigger",
        "description": "Select bottom right origin"
    },
    "/EndTActivated": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF"
    },
    "/EndTSwipe": {
        "type": "bool/trigger",
        "description": "Select Swipe mode"
    },
    "/EndTInside": {
        "type": "bool/trigger",
        "description": "Select Inside mode"
    },
    "/EndTOutside": {
        "type": "bool/trigger",
        "description": "Select Outside mode"
    },
    "/EndTCorner": {
        "type": "bool/trigger",
        "description": "Select Corner mode"
    },
    "/EndTStairs": {
        "type": "bool/trigger",
        "description": "Select Stairs mode"
    },
    "/EndTFade": {
        "type": "bool/trigger",
        "description": "Select Fade mode"
    },
    "/EndTBlinds": {
        "type": "bool/trigger",
        "description": "Select Blinds mode"
    },
    "/EndTFalls": {
        "type": "bool/trigger",
        "description": "Select Falls mode"
    },
    "/EndTDirection": {
        "type": "range_0_127",
        "description": "Change direction angle"
    },
    "/EndTOrientation": {
        "type": "bool/trigger",
        "description": "Switch direction (left-right)"
    },
    "/EndTUpperLeft": {
        "type": "bool/trigger",
        "description": "Select upper left origin"
    },
    "/EndTUpperRight": {
        "type": "bool/trigger",
        "description": "Select upper right origin"
    },
    "/EndTCenter": {
        "type": "bool/trigger",
        "description": "Select center origin"
    },
    "/EndTBottomLeft": {
        "type": "bool/trigger",
        "description": "Select bottom left origin"
    },
    "/EndTBottomRight": {
        "type": "bool/trigger",
        "description": "Select bottom right origin"
    },
    "/ShaderBlackWhiteActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Black & White)"
    },
    "/ShaderBlackWhite": {
        "type": "range_0_127",
        "description": "Change value (Black & White)"
    },
    "/ShaderBlueActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Blue)"
    },
    "/ShaderBlue": {
        "type": "range_0_127",
        "description": "Change value (Blue)"
    },
    "/ShaderBlurActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Blur)"
    },
    "/ShaderBlur": {
        "type": "range_0_127",
        "description": "Change value (Blur)"
    },
    "/ShaderContrasteActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Contrast)"
    },
    "/ShaderContraste": {
        "type": "range_0_127",
        "description": "Change value (Contrast)"
    },
    "/ShaderConvergenceActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Convergence)"
    },
    "/ShaderConvergence": {
        "type": "range_0_127",
        "description": "Change value (Convergence)"
    },
    "/ShaderCutSliderActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Cut Slider)"
    },
    "/ShaderCutSlider": {
        "type": "range_0_127",
        "description": "Change value (Cut Slider)"
    },
    "/ShaderGlowActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Glow)"
    },
    "/ShaderGlow": {
        "type": "range_0_127",
        "description": "Change value (Glow)"
    },
    "/ShaderGreenActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Green)"
    },
    "/ShaderGreen": {
        "type": "range_0_127",
        "description": "Change value (Green)"
    },
    "/ShaderNoiseActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Noise)"
    },
    "/ShaderNoise": {
        "type": "range_0_127",
        "description": "Change value (Noise)"
    },
    "/ShaderOldTVActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Old TV)"
    },
    "/ShaderOldTV": {
        "type": "range_0_127",
        "description": "Change value (Old TV)"
    },
    "/ShaderRedActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Red)"
    },
    "/ShaderRed": {
        "type": "range_0_127",
        "description": "Change value (Red)"
    },
    "/ShaderShakerActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Shaker)"
    },
    "/ShaderShaker": {
        "type": "range_0_127",
        "description": "Change value (Shaker)"
    },
    "/ShaderStrobeActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Strobe)"
    },
    "/ShaderStrobe": {
        "type": "range_0_127",
        "description": "Change value (Strobe)"
    },
    "/ShaderSlitScanActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (SlitScan)"
    },
    "/ShaderSlitScan": {
        "type": "range_0_127",
        "description": "Change value (SlitScan)"
    },
    "/ShaderSwellActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Swell)"
    },
    "/ShaderSwell": {
        "type": "range_0_127",
        "description": "Change value (Swell)"
    },
    "/ShaderTwistActivate": {
        "type": "bool/toggle",
        "description": "Toggle ON/OFF (Twist)"
    },
    "/ShaderTwist": {
        "type": "range_0_127",
        "description": "Change value (Twist)"
    }
}


def parse_command_line():
    """parse command line arguments
    Also add current version and version date to description
    """

    # define command line options
    parser = argparse.ArgumentParser(
        description=__description__ + "\nVersion: " + __version__ + " (" + __version_date__ + ")",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-c", "--config", default=default_config_file_path, dest="config_file",
                        help="points to the config file to read config data from " +
                             "which is not installed under the default path '" +
                             default_config_file_path + "'",
                        metavar="dmx_to_osc.ini")
    parser.add_argument("-v", "--verbose",  action='store_true',
                        help="be verbose and print debug information")

    return parser.parse_args()


def parse_own_config(config_file):
    """parsing and basic validation of own config file
    Parameters
    ----------
    config_file : str
        The file location of the config file
    Returns
    -------
    dict
        a dictionary with all config options parsed from the config file
    """

    config_dict = dict()

    logging.debug("Parsing config file: %s" % config_file)

    if config_file is None or config_file == "":
        do_error_exit("Config file not defined.")

    # setup config parser and read config
    config_handler = ConfigParser.SafeConfigParser()

    try:
        config_handler.read(config_file)
    except ConfigParser.Error as e:
        do_error_exit("Error during config file parsing: %s" % e)
    except Exception as e:
        do_error_exit("Unable to open file '%s': %s" % (config_file, str(e)))

    # read logging section
    this_section = "dmx"
    if this_section not in config_handler.sections():
        logging.warning("Section '%s' not found in '%s'" % (this_section, config_file))
    else:
        # read universe if present
        if "universe" in list(dict(config_handler.items(this_section))):
            config_dict["dmx.universe"] = config_handler.get(this_section, "universe")
            logging.debug("Config: %s = %s" % ("dmx.universe", config_dict["dmx.universe"]))

    if config_dict.get("dmx.universe") is None:
        config_dict["dmx.universe"] = default_dmx_universe
        logging.debug("Config: option %s not set. Using default value: %s" %
                      ("dmx.universe", str(default_dmx_universe)))

    # initialize empty mapping array
    mapping = dict.fromkeys(range(dmx_num_channels), None)

    channel_prefix = "channel"

    # get osc sections
    for config_section in config_handler.sections():

        if config_section != "dmx" and not config_section.startswith("osc/"):
            logging.warning("ignoring invalid section '%s' in config file." % config_section)
            continue

        if config_section.startswith("osc/"):
            osc_destination = dict()
            osc_destination["name"] = config_section.split("/")[1]

            config_option_name = "server"
            if config_option_name in list(dict(config_handler.items(config_section))):
                osc_destination["server"] = config_handler.get(config_section, config_option_name)
                logging.debug("Config: %s = %s" % ("%s.%s" %
                                                   (config_section, config_option_name), osc_destination["server"]))
            else:
                do_error_exit("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            config_option_name = "port"
            if config_option_name in list(dict(config_handler.items(config_section))):
                osc_destination["port"] = config_handler.get(config_section, config_option_name)
                logging.debug("Config: %s = %s" % ("%s.%s" %
                                                   (config_section, config_option_name), osc_destination["port"]))
            else:
                do_error_exit("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            for key, channel_osc_command in dict(config_handler.items(config_section)).items():

                # skip expected config options
                if key in ["server", "port"]:
                    continue

                if key.split("_")[0] != channel_prefix:
                    logging.warning("config item '%s' starts with wrong prefix, expected: '%s'" % (key, channel_prefix))
                    continue

                try:
                    channel_name = int(key.split("_")[1])
                except ValueError:
                    logging.warning(
                        "config item '%s' channel must be int but '%s' given" % (key, str(key.split("_")[1])))
                    continue

                # i.e. channel 1 is represented with id 0 in DMX data and so on
                channel_id = channel_name - 1

                if channel_name == 0:
                    logging.warning("channels in section '%s' need to start with 1" % config_section)
                    continue

                if channel_name > dmx_num_channels:
                    logging.warning("config item '%s' exceeds the maximum number of valid DMX channels: %d" %
                                    (key, dmx_num_channels))
                    continue

                if valid_osc_commands.get(channel_osc_command) is None:
                    logging.warning("invalid OSC command '%s' for channel '%s'" % (channel_osc_command, channel_name))
                    continue

                # take care of id 0 = channel 1
                if mapping.get(channel_id) is None:
                    channel_destinations = [osc_destination]
                else:
                    if mapping.get(channel_id).get("command") != channel_osc_command:
                        do_error_exit("channel definition mismatch between '%s' and '%s' for channel '%s'" %
                                      (mapping.get(channel_id).get("destinations")[0].get("name"),
                                       osc_destination.get("name"), channel_name))

                    channel_destinations = mapping.get(channel_id).get("destinations")
                    channel_destinations.append(osc_destination)

                mapping[channel_id] = {"command": channel_osc_command, "destinations": channel_destinations}

    for key, val in mapping.items():

        if val is not None:
            logging.debug("Config: channel %d, command: %s, destinations: %s"
                          % (key + 1, val.get("command"), str([d['name'] for d in val.get("destinations")])))

    config_dict["osc"] = mapping

    return config_dict


def do_error_exit(log_text):
    """log an error and exit with return code 1
    Parameters
    ----------
    log_text : str
        the text to log as error
    """

    logging.error(log_text)
    exit(1)


def send_dmx_to_osc(data):
    """
    send DMX data array to OSC receiver

    Parameters
    ----------
    data : list
        data array with a length of 512 items
    """

    global last_dmx_block

    for dmx_channel_id, value in enumerate(data):

        # if value for channel is different from last blocks value then send an OSC message
        if value != last_dmx_block[dmx_channel_id]:

            osc_command_data = config["osc"][dmx_channel_id]
            dmx_channel_num = dmx_channel_id + 1

            if osc_command_data is None:
                logging.error("Received value '%d' for undefined DMX channel '%d'" % (value, dmx_channel_num))
                continue

            osc_command = osc_command_data.get("command")
            osc_command_destinations = osc_command_data.get("destinations")

            command_type = valid_osc_commands.get(osc_command).get("type")

            if command_type is None:
                logging.warning("missing index type in 'valid_osc_commands' for '%s'" % osc_command)
                continue

            if osc_command_destinations is None:
                logging.warning("missing destinations for '%s' on channel '%d'" % (osc_command, dmx_channel_num))
                continue

            sent_value = value

            command_translated = None

            if command_type == "range_0_127":
                if value > 255:
                    logging.warning("submitted DMX value for channel '%s' out of range: %d " % (dmx_channel_num, value))
                    sent_value = 127
                else:
                    sent_value = value / 2

            elif command_type == "bool/custom":
                command_translated = "None" if sent_value == 0 else "Custom"
            elif command_type == "bool/none_smooth":
                command_translated = "None" if sent_value == 0 else "Smooth"
            elif command_type == "bool/toggle":
                command_translated = "Off" if sent_value == 0 else "On"
            elif command_type == "bool/trigger":
                command_translated = "None" if sent_value == 0 else "Triggered"
            elif command_type == "int/value":
                pass
            else:
                logging.warning("invalid OSC command type: %s" % command_type)
                continue

            if command_type.startswith("bool"):
                if value > 1:
                    sent_value = 1

            log_text = "%s => %d" % (osc_command, sent_value)
            if command_translated is not None:
                log_text += " (%s)" % command_translated
            log_text += " (type: %s) (DMX input: %d on %d)" % (command_type, value, dmx_channel_num)

            # send osc message to all destinations
            for destination in osc_command_destinations:
                logging.debug("Sending OSC command: %s to %s" % (log_text, destination.get("name")))

                try:
                    send_osc_message(b'/%s' % osc_command,
                                     [sent_value], destination.get("server"), int(destination.get("port")))
                except Exception as e:
                    logging.warning("Sending command to '%s' failed: %s" % (destination.get("name"), str(e)))

    last_dmx_block = data

    return


if __name__ == "__main__":

    # parse command line
    args = parse_command_line()

    # set log level
    if args.verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s: %(message)s')

    # parse config data
    config = parse_own_config(args.config_file)

    # register and run ola DMX client
    wrapper = ClientWrapper()
    client = wrapper.Client()
    client.RegisterUniverse(int(config["dmx.universe"]), client.REGISTER, send_dmx_to_osc)
    wrapper.Run()

exit(0)

# EOF
