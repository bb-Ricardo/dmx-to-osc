#!/usr/bin/env python2.7

#################
#   imports

# standard modules
import argparse
import ConfigParser
import logging

# 3rd party modules
from oscpy.client import OSCClient
from ola.ClientWrapper import ClientWrapper

__version__ = "0.0.1"
__version_date__ = "2019-07-23"
__license__ = "MIT"
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

    # read osc section
    this_section = "osc"
    if this_section not in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file))
    else:
        # read universe if present
        if "server" in list(dict(config_handler.items(this_section))):
            config_dict["osc.server"] = config_handler.get(this_section, "server")
            logging.debug("Config: %s = %s" % ("osc.server", config_dict["osc.server"]))
        else:
            do_error_exit("Option '%s' missing in config section '%s'" % ("server", this_section))

        if "port" in list(dict(config_handler.items(this_section))):
            config_dict["osc.port"] = config_handler.get(this_section, "port")
            logging.debug("Config: %s = %s" % ("osc.port", config_dict["osc.port"]))

        if config_dict.get("osc.port") is None:
            config_dict["osc.port"] = default_osc_port
            logging.debug("Config: option %s not set. Using default value: %s" % ("osc.port", str(default_osc_port)))

    mapping = dict.fromkeys(range(dmx_num_channels), None)

    # read dmx_to_osc section
    channel_prefix = "channel"
    this_section = "dmx_to_osc"
    if this_section not in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file))
    else:
        for key, value in dict(config_handler.items(this_section)).items():

            if key.split("_")[0] != channel_prefix:
                logging.warning("config item '%s' starts with wrong prefix, expected: '%s'" % (key, channel_prefix))
                continue

            try:
                channel = int(key.split("_")[1])
            except ValueError:
                logging.warning("config item '%s' channel must be int but '%s' given" % (key, str(key.split("_")[1])))
                continue

            mapping[channel] = value

    config_dict[this_section] = mapping

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

    global last_dmx_block

    if osc_handle is None:
        do_error_exit("OSC connection not initialized. Exit")

    for channel, val in enumerate(data):

        # if value for channel is different from last blocks value then send an OSC message
        if val != last_dmx_block[channel]:
            if config["dmx_to_osc"][channel] is None:
                logging.error("Received value '%d' for undefined DMX channel '%d'" % (val, channel))
                continue

            if val >= 256:
                val = 256

            if val > 2:
                val = val / 2

            logging.debug("Sending OSC command: %s => %d" % (config["dmx_to_osc"][channel], val))
            osc_handle.send_message(b'/%s' % config["dmx_to_osc"][channel], [val])

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

    # start OSC connection
    try:
        osc_handle = OSCClient(config["osc.server"], int(config["osc.port"]))
    except Exception as error:
        do_error_exit("Unable to connect to OSC server '%s': %s" % (config["osc.server"], str(error)))

    # register and run ola DMX client
    wrapper = ClientWrapper()
    client = wrapper.Client()
    client.RegisterUniverse(int(config["dmx.universe"]), client.REGISTER, send_dmx_to_osc)
    wrapper.Run()

exit(0)

# EOF
