#!/usr/bin/env python2.7

#################
#   imports

# standard modules
from socket import (socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, SO_BROADCAST)
from struct import pack, unpack
import array
try:
    import configparser as configparser
except ImportError:
    import ConfigParser as configparser

import argparse
import logging
import time

# 3rd party modules
from oscpy.client import send_message as send_osc_message

ola_module_present = True
try:
    from ola.ClientWrapper import ClientWrapper
except ImportError:
    ola_module_present = False


__version__ = "0.0.3"
__version_date__ = "2019-07-26"
__license__ = "GPLv3"
__description__ = "script to receive dmx and send out osc commands to osc server"


#################
#   default and internal vars

artnet_udp_port = 6454
ArtDmxPackage = 0x0050

dmx_num_channels = 512

default_config_file_path = "./dmx_to_osc.ini"
default_dmx_universe = 0

last_dmx_block = [0] * dmx_num_channels
last_run_ts = None
osc_handle = None


class ArtnetPacket:

    ARTNET_HEADER = b'Art-Net\x00'

    def __init__(self):
        self.op_code = None
        self.ver = None
        self.sequence = None
        self.physical = None
        self.universe = None
        self.net = None
        self.subuni = None
        self.length = None
        self.data = None

    def __str__(self):
        return ("ArtNet package:\n - op_code: 0x{0}\n - version: {1}\n - "
                "sequence: {2}\n - physical: {3}\n - net: {4}\n - subuni: {5}\n -"
                "length: {6}\n - data : {7}").format(
            '{:02x}'.format(self.op_code), self.ver, self.sequence, self.physical,
            self.net, self.subuni, self.length, self.data)

    @staticmethod
    def unpack_raw_artnet_packet(raw_data):

        if unpack('!8s', raw_data[:8])[0] != ArtnetPacket.ARTNET_HEADER:
            print("Received a non Art-Net packet")
            return None

        packet = ArtnetPacket()
        try:
            (packet.op_code, packet.ver, packet.sequence, packet.physical,
                packet.subuni, packet.net, packet.length) = unpack('!HHBBBBH', raw_data[8:18])
        except Exception:
            return None

        try:
            packet.data = unpack(
                '{0}s'.format(int(packet.length)),
                raw_data[18:18+int(packet.length)])[0]
        except Exception:
            return None

        return packet


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
    parser.add_argument("--profile", action='store_true',
                        help="display current FPS of DMX frames")

    return parser.parse_args()


def parse_config_inputs_section(handler, section):

    this_config_dict = dict()

    config_items = ["enabled", "universe"]

    if section == "art-net":
        config_items.append("listen_address")

    if section not in handler.sections():
        logging.warning("Section '%s' not found in config file" % section)
        this_config_dict["%s.universe" % section] = default_dmx_universe
        this_config_dict["%s.enabled" % section] = "0"
    else:
        for item in config_items:
            config_dict_name = "%s.%s" % (section, item)
            if item in list(dict(handler.items(section))):
                this_config_dict[config_dict_name] = handler.get(section, item).strip()
                logging.debug("Config: %s = %s" % (config_dict_name, this_config_dict[config_dict_name]))

            if item == "universe" and (this_config_dict.get(config_dict_name) is None
                                       or len(this_config_dict.get(config_dict_name)) == 0):
                this_config_dict[config_dict_name] = default_dmx_universe
                logging.debug("Config: option %s not set. Using default value: %s" %
                              (config_dict_name, str(default_dmx_universe)))

            if item == "enabled" and (this_config_dict.get(config_dict_name) is None
                                      or len(this_config_dict.get(config_dict_name)) == 0):
                this_config_dict[config_dict_name] = "1"

    return this_config_dict


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

    config_problem = False

    logging.debug("Parsing config file: %s" % config_file)

    if config_file is None or config_file == "":
        do_error_exit("Config file not defined.")

    # setup config parser and read config
    config_handler = configparser.SafeConfigParser()

    try:
        config_handler.read(config_file)
    except configparser.Error as e:
        do_error_exit("Error during config file parsing: %s" % e)
    except Exception as e:
        do_error_exit("Unable to open file '%s': %s" % (config_file, str(e)))

    config_dict.update(parse_config_inputs_section(config_handler, "art-net"))
    config_dict.update(parse_config_inputs_section(config_handler, "ola-dmx"))

    if config_dict["art-net.enabled"] == "1" and \
            (config_dict.get("art-net.listen_address") is None or
             len(config_dict["art-net.listen_address"]) == 0):
        config_problem = True
        logging.error("art-net option 'listen_address' not configured.")

    # initialize empty mapping array
    mapping = dict.fromkeys(range(dmx_num_channels), None)

    channel_prefix = "channel"

    # get osc sections
    for config_section in config_handler.sections():

        if config_section not in ["ola-dmx", "art-net"] and not config_section.startswith("osc/"):
            logging.warning("ignoring invalid section '%s' in config file." % config_section)
            continue

        if config_section.startswith("osc/"):
            osc_destination = dict()
            osc_destination["name"] = config_section.split("/")[1]

            section_config_options = list(dict(config_handler.items(config_section)))

            if "enabled" in section_config_options:
                if config_handler.get(config_section, "enabled").strip() == "0":
                    logging.info("config section '%s' is disabled and will be skipped" % config_section)
                    continue

            config_option_name = "server"
            if config_option_name in section_config_options:
                osc_destination[config_option_name] = config_handler.get(config_section, config_option_name).strip()
                if len(osc_destination[config_option_name]) == 0:
                    config_problem = True
                    logging.error("option '%s' empty for OSC destination '%s'"
                                  % (config_option_name, osc_destination["name"]))
                logging.debug("Config: %s = %s" %
                              ("%s.%s" % (config_section, config_option_name), osc_destination[config_option_name]))
            else:
                config_problem = True
                logging.error("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            config_option_name = "port"
            if config_option_name in section_config_options:
                osc_destination[config_option_name] = config_handler.get(config_section, config_option_name).strip()
                if len(osc_destination[config_option_name]) == 0:
                    config_problem = True
                    logging.error("option '%s' empty for OSC destination '%s'"
                                  % (config_option_name, osc_destination["name"]))
                logging.debug("Config: %s = %s" %
                              ("%s.%s" % (config_section, config_option_name), osc_destination[config_option_name]))
            else:
                config_problem = True
                logging.error("Option '%s' missing in config section '%s'" % (config_option_name, config_section))

            # store port as int to save type casting on every message sent
            osc_destination[config_option_name] = int(osc_destination[config_option_name])

            for key, channel_osc_command in dict(config_handler.items(config_section)).items():

                channel_osc_command = channel_osc_command.strip()

                # skip expected config options
                if key in ["server", "port", "enabled"]:
                    continue

                if key.split("_")[0] != channel_prefix:
                    config_problem = True
                    logging.warning("config item '%s' starts with wrong prefix, expected: '%s'" % (key, channel_prefix))
                    continue

                try:
                    channel_name = int(key.split("_")[1])
                except ValueError:
                    config_problem = True
                    logging.warning(
                        "config item '%s' channel must be int but '%s' given" % (key, str(key.split("_")[1])))
                    continue

                # i.e. channel 1 is represented with id 0 in DMX data and so on
                channel_id = channel_name - 1

                if channel_name == 0:
                    config_problem = True
                    logging.warning("channels in section '%s' need to start with 1" % config_section)
                    continue

                if channel_name > dmx_num_channels:
                    config_problem = True
                    logging.warning("config item '%s' exceeds the maximum number of valid DMX channels: %d" %
                                    (key, dmx_num_channels))
                    continue

                # check command and type
                command_and_type = channel_osc_command.split(":")

                if len(command_and_type) == 1:
                    config_problem = True
                    logging.warning("missing OSC command type for command '%s' for channel '%s'"
                                    % (command_and_type[0], channel_name))
                    continue

                command_type = command_and_type[1]
                if command_type not in ["value", "trigger", "toggle", "range"]:
                    config_problem = True
                    logging.warning("invalid OSC command type '%s' for command '%s' for channel '%s'"
                                    % (command_and_type[0], command_and_type[0], channel_name))
                    continue

                if command_type == "range":
                    if len(command_and_type) != 4:
                        config_problem = True
                        logging.warning(
                            "wrong format '%s' for OSC command type 'range' for command '%s' for channel '%s'"
                            % (channel_osc_command, command_and_type[0], channel_name))
                        continue
                    try:
                        int(command_and_type[2])
                        int(command_and_type[3])
                    except ValueError:
                        config_problem = True
                        logging.warning(
                            "command type 'range' start and end for channel '%s' must be int, got '%s:%s'" %
                            (channel_name, str(command_and_type[2]), str(command_and_type[3])))
                        continue

                # add command to mapping
                if mapping.get(channel_id) is None:
                    channel_destinations = [osc_destination]
                else:
                    if mapping.get(channel_id).get("command") != channel_osc_command:
                        config_problem = True
                        logging.error("channel definition mismatch between '%s' and '%s' for channel '%s'" %
                                      (mapping.get(channel_id).get("destinations")[0].get("name"),
                                       osc_destination.get("name"), channel_name))

                    channel_destinations = mapping.get(channel_id).get("destinations")
                    channel_destinations.append(osc_destination)

                mapping[channel_id] = {"command": channel_osc_command, "destinations": channel_destinations}

    if config_problem is True:
        do_error_exit("found config problems during parsing. Exit")

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

    global last_dmx_block, last_run_ts

    if args.profile is True and last_run_ts is not None:
        print("FPS: %0.2f" % (1.0 / (time.time() - last_run_ts)))

    last_run_ts = time.time()

    # truncate DMX packet if it contains more then 512 values
    data = data[:(dmx_num_channels - 1)]
    # pad DMX packet if it is truncated
    data.extend([0] * (dmx_num_channels - len(data)))

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
                    send_osc_message(b'%s' % osc_command_name.encode(),
                                     [value_to_send], destination.get("server"), destination.get("port"))
                except Exception as e:
                    logging.warning("Sending command to '%s' failed: %s" % (destination.get("name"), str(e)))

    last_dmx_block = data

    return


def start_artnet_listener():
    """
        listen for Art-Net packages and send to OSC destination
    """
    logging.info("Art-Net server listening on {0}:{1}".format(
        config["art-net.listen_address"], artnet_udp_port))

    sock = socket(AF_INET, SOCK_DGRAM)  # UDP
    sock.bind((config["art-net.listen_address"], artnet_udp_port))

#    sock_broadcast = socket(AF_INET, SOCK_DGRAM)
#    sock_broadcast.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
#    sock_broadcast.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    last_sequence = 0
    package_source_ip = None
    listening_universe = int(config["art-net.universe"])

    while True:
        try:
            data, address = sock.recvfrom(1024)

            if package_source_ip is None:
                logging.debug("accepting packages from: %s", address[0])
                package_source_ip = address[0]
            elif address[0] != package_source_ip:
                continue

            packet = ArtnetPacket.unpack_raw_artnet_packet(data)

            # only accept "ArtDmx" packages
            if packet is None or \
                    packet.op_code != ArtDmxPackage or \
                    packet.ver < 14:
                continue

            if packet.sequence != last_sequence:
                last_sequence = packet.sequence
            else:
                continue

            # check package for the correct universe
            if packet.subuni != listening_universe:
                continue

            # convert byte data to list of ints
            # works for python2 and python3
            data_array = array.array("B")
            data_array.fromstring(packet.data)
            send_dmx_to_osc(list(data_array))

        except KeyboardInterrupt:
            sock.close()
#            sock_broadcast.close()
            exit(0)


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

    if config["ola-dmx.enabled"] == "1" and ola_module_present is False:
        logging.warning("OLA python libs not found.")
        config["ola-dmx.enabled"] = "0"

    # register and run ola DMX client
    if config["ola-dmx.enabled"] == "1":
        logging.info("Starting DMX to OSC with OLA client")
        wrapper = ClientWrapper()
        client = wrapper.Client()
        client.RegisterUniverse(int(config["ola-dmx.universe"]), client.REGISTER, send_dmx_to_osc)
        wrapper.Run()
    elif config["art-net.enabled"] == "1":
        start_artnet_listener()
    else:
        do_error_exit("No input method in config file defined/enabled.")

exit(0)

# EOF
