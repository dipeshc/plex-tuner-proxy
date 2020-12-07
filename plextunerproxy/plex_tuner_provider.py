import logging
import threading

from abc import ABC, abstractmethod

logger = logging.getLogger()


class PlexTunerProvider(ABC):
    """
    The Plex Tuner Provider. Abstract class that when implemented can provide TV channels for Plex. Implementation of this provider must
    implement the channels(), epg() and _scan() methods.
    """

    def __init__(self, friendly_name, auto_scan_interval_seconds=None):
        """
        Constructs the Plex Tuner Provider.

        :param str friendly_name: the friendly name associated with the Plex Tuner.
        :param int auto_scan_interval_seconds: the frequency at which to trigger the auto scan. If None, then auto scan is disabled.
        """
        self._friendly_name = friendly_name
        self._auto_scan_interval_seconds = auto_scan_interval_seconds
        self._channels = []
        self._is_scanning = False
        self._epg = None

        # Kick off the auto scanner if enabled. This will also result in the first scan happening before the method returns.
        if self._auto_scan_interval_seconds:
            self._auto_scanner()
        else:
            logging.debug("Auto scanning disabled.")

    def friendly_name(self):
        """
        Gets the friendly name associated with the Plex Tuner.
        """
        return self._friendly_name

    def is_scanning(self):
        """
        Gets if the provider is currently scanning. Return True if it is, otherwise False.
        :rtype: bool
        """
        return self._is_scanning

    def scan(self):
        """
        Triggers a scan on the tuner. This can be triggered either by Plex via a scan call, or via the automatic periodic process.
        """
        self._is_scanning = True
        try:
            self._channels, self._epg = self._scan()
        finally:
            self._is_scanning = False

    def channels(self):
        """
        Gets the channels.
        :rtype: list[object]
        """
        return self._channels

    def epg(self):
        """
        Gets the EPG for the Channels.
        :rtype: str
        """
        return self._epg

    def _auto_scanner(self):
        """
        Internal method that is an infinite loop of scanning the data periodically.
        """
        logger.info("Scanning channels.")
        self.scan()
        logger.info(f"Scanning completed. {self._auto_scan_interval_seconds} seconds until next scan.")
        threading.Timer(self._auto_scan_interval_seconds, self._auto_scanner).start()

    @abstractmethod
    def _scan(self):
        """
        Internal method called when the provider is asked to scan() that should return the channels and epg data. Child classes should use
        this method to perform the equivalent of a scan (e.g. loading data from a remote location). The channels returned from this must be
        in the below format and the EPG data must be a string in xmltv format.
        [
            {
                "GuideNumber":  "<the channel number as a string>",
                "GuideName":    "<the channel name>",
                "HD":           <1 if channel is HD otherwise 0 as an integer>,
                "URL":          "<stream URL>",
            }
        ]
        :rtype: list[object], str
        """
        pass
