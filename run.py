#!/usr/bin/env python

import argparse
import logging
import os
import sys

from iptvplextuner.iptv_channel_provider import IPTVChannelProvider
from iptvplextuner.plex_tuner import PlexTunerServer

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
    parser.add_argument("--m3u", help="Path to the m3u playlist.", required=True)
    parser.add_argument("--port", help="The tuner port Plex will connect too.", default=5004, type=int)
    parser.add_argument("--debug", action="store_true", help="Enables a debug mode.")
    args = parser.parse_args()
    logging.debug("Args: %s.", args)

    # Enable debug logging to the console if debug mode enabled.
    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    # Setup IPTV channel provider and trigger the first load.
    iptv_channel_provider = IPTVChannelProvider(args.m3u)
    iptv_channel_provider.load()

    # Setup Plex Tuner Server
    PlexTunerServer(args.debug, iptv_channel_provider, args.port).run()


if __name__ == "__main__":
    main()
