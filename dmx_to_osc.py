#!/usr/bin/env python2.7

#################
#   imports

# standard modules
import argparse
import ConfigParser
import logging

# 3rd party modules
from oscpy.client import send_message as send_osc_message

ola_present = True
try:
    from ola.ClientWrapper import ClientWrapper
except ImportError:
    ola_present = False

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
                osc_destination[config_option_name] = config_handler.get(config_section, config_option_name).strip()
                if len(osc_destination[config_option_name]) == 0:
                    do_error_exit("option '%s' empty for OSC destination '%s'"
                                  % (config_option_name, osc_destination["name"]))
                logging.debug("Config: %s = %s" % ("%s.%s" %
                                    (config_section, config_option_name), osc_destination[config_option_name]))
            else:
                do_error_exit("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            config_option_name = "port"
            if config_option_name in list(dict(config_handler.items(config_section))):
                osc_destination[config_option_name] = config_handler.get(config_section, config_option_name).strip()
                if len(osc_destination[config_option_name]) == 0:
                    do_error_exit("option '%s' empty for OSC destination '%s'"
                                  % (config_option_name, osc_destination["name"]))
                logging.debug("Config: %s = %s" % ("%s.%s" %
                                    (config_section, config_option_name), osc_destination[config_option_name]))
            else:
                do_error_exit("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            for key, channel_osc_command in dict(config_handler.items(config_section)).items():

                channel_osc_command = channel_osc_command.strip()

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

                # check command and type
                command_and_type = channel_osc_command.split(":")

                if len(command_and_type) == 1:
                    logging.warning("missing OSC command type for command '%s' for channel '%s'"
                                    % (command_and_type[0], channel_name))
                    continue

                command_type = command_and_type[1]
                if command_type not in ["value", "trigger", "toggle", "range"]:
                    logging.warning("invalid OSC command type '%s' for command '%s' for channel '%s'"
                                    % (command_and_type[0], command_and_type[0], channel_name))
                    continue

                if command_type == "range":
                    if len(command_and_type) != 4:
                        logging.warning(
                            "wrong format '%s' for OSC command type 'range' for command '%s' for channel '%s'"
                            % (channel_osc_command, command_and_type[0], channel_name))
                        continue
                    try:
                        int(command_and_type[2])
                        int(command_and_type[3])
                    except ValueError:
                        logging.warning(
                            "command type 'range' start and end for channel '%s' must be int, got '%s:%s'" %
                            (channel_name, str(command_and_type[2]), str(command_and_type[3])))
                        continue

                # add command to mapping
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

            osc_command_destinations = osc_command_data.get("destinations")

            if osc_command_destinations is None:
                logging.warning("missing destinations for '%s' on channel '%d'" % (osc_command, dmx_channel_num))
                continue

            # check command and type
            osc_command_and_type = osc_command_data.get("command").split(":")
            osc_command_name = osc_command_and_type[0]
            osc_command_type = osc_command_and_type[1]

            value_to_send = value

            if value > 255:
                logging.warning("submitted DMX value for channel '%s' out of range: %d " % (dmx_channel_num, value))
                value_to_send = 255

            if value < 0:
                logging.warning("submitted DMX value for channel '%s' out of range: %d " % (dmx_channel_num, value))
                value_to_send = 0

            command_translated = None

            # calculate value to send according range span
            if osc_command_type == "range":
                dmx_span = 256
                range_min = int(osc_command_and_type[2])
                range_max = int(osc_command_and_type[3])
                range_span = range_max - range_min + 1

                value_to_send = int(range_min + (float(float(range_span) / float(dmx_span)) * float(value_to_send)))

            elif osc_command_type == "toggle":
                command_translated = "Off" if value_to_send == 0 else "On"
            elif osc_command_type == "trigger":
                command_translated = "None" if value_to_send == 0 else "Triggered"
            elif osc_command_type == "value":
                pass
            else:
                logging.warning("invalid OSC command type: %s" % osc_command_type)
                continue

            # take care of bool types
            if osc_command_type in ["trigger", "toggle"]:
                if value > 1:
                    value_to_send = 1

            # assemble log text
            log_text = "%s => %d" % (osc_command_name, value_to_send)
            if command_translated is not None:
                log_text += " (%s)" % command_translated
            log_text += " (type: %s) (DMX input: %d on %d)" % (osc_command_type, value, dmx_channel_num)

            # send osc message to all destinations
            for destination in osc_command_destinations:
                logging.debug("Sending OSC command: %s to %s" % (log_text, destination.get("name")))

                try:
                    send_osc_message(b'%s' % osc_command_name,
                                     [value_to_send], destination.get("server"), int(destination.get("port")))
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
    if ola_present is True:
        logging.info("starting DMX to OSC with OLA client")
        wrapper = ClientWrapper()
        client = wrapper.Client()
        client.RegisterUniverse(int(config["dmx.universe"]), client.REGISTER, send_dmx_to_osc)
        wrapper.Run()
    else:
        logging.warning("OLA python libs not found.")

exit(0)

# EOF
