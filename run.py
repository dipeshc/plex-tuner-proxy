#!/usr/bin/env python

import argparse
import logging
import os
import sys

from plextunerproxy.iptv_plex_tuner_provider import IPTVPlexTunerProvider
from plextunerproxy.plex_tuner import PlexTunerServer

# Setup the logger.
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(os.path.splitext(sys.argv[0])[0] + ".log")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(filename)s:%(lineno)d] [%(levelname)-5.5s]  %(message)s"))
file_handler.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)


def main():
    logging.debug("Raw args: %s.", sys.argv)

    # Parse the arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument("--iptv.m3u", help="Path to the m3u playlist.", required=True)
    parser.add_argument("--iptv.epg", help="Path to the EPG.")
    parser.add_argument("--auto-scan-interval-seconds", default=(3 * 60 * 60), type=int,
                        help="The frequency in seconds at which to trigger the auto scanning."
                        + " To disable auto scanning set to 0 or a negative number.")
    parser.add_argument("--port", help="The tuner port Plex will connect too.", default=5004, type=int)
    parser.add_argument("--debug", action="store_true", help="Enables debug mode.")
    args = vars(parser.parse_args())

    # Enable debug logging to the console if debug mode enabled.
    if args["debug"]:
        console_handler.setLevel(logging.DEBUG)
    logging.debug("Args: %s.", args)

    # Setup IPTV channel provider and trigger the first load.
    auto_scan_interval_seconds = (args["auto_scan_interval_seconds"] if args["auto_scan_interval_seconds"] > 0 else None)
    iptv_plex_tuner_provider = IPTVPlexTunerProvider(args["iptv.m3u"], args["iptv.epg"], auto_scan_interval_seconds)

    # Setup Plex Tuner Server
    PlexTunerServer(args["debug"], iptv_plex_tuner_provider, args["port"]).run()


if __name__ == "__main__":
    main()
