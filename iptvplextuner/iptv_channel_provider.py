import logging
import re
import requests

from datetime import datetime, timedelta, timezone
from lxml import etree
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


logger = logging.getLogger()

REGEX_EXTINF_EXTRACTOR = {
    "id": 'tvg-id="(?P<value>[^"]+)"',
    "logo": 'tvg-logo="(?P<value>http[^"]+)"'
}


class IPTVChannelProvider():

    def __init__(self, m3u_url):
        """
        Constructor the IPTV Client.
        :param str m3u_url: the m3u playlist url
        """
        self.m3u_url = m3u_url

        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])))
        self.session = session

        self._is_loading = False
        self._channel_data = []

    def is_loading(self):
        return self._is_loading

    def channels(self):
        channels = []
        for channel in self._channel_data:
            channels.append({
                "GuideNumber": channel["number"],
                "GuideName": channel["name"],
                "HD": 1 if "HD" in channel["name"] else 0,
                "URL": channel["url"]
            })
        return channels

    def epg(self):
        # Compute time info, so all channels have the same time ranges.
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = start + timedelta(days=3)

        root = etree.fromstring("<tv></tv>")

        for channel_data in self._channel_data:
            id = channel_data["number"]
            channel = etree.SubElement(root, "channel", {"id": id})
            display_name = etree.SubElement(channel, "display-name")
            display_name.text = channel_data["name"]

            if "logo" in channel_data:
                etree.SubElement(channel, "icon", {"src": channel_data["logo"]})

            current = start
            while current < end:
                programme_start = current.strftime("%Y%m%d%H%M%S") + " -0000"
                programme_stop = (current + timedelta(hours=1)).strftime("%Y%m%d%H%M%S") + " -0000"
                programme = etree.SubElement(root, "programme", {"start": programme_start, "stop": programme_stop, "channel": id})

                title = etree.SubElement(programme, "title")
                title.text = f"{channel_data['name']}"

                desc = etree.SubElement(programme, "desc")
                desc.text = f"{channel_data['name']} - {current}"

                current += timedelta(hours=1)

        return etree.tostring(root, encoding="UTF-8",
                              xml_declaration=True,
                              pretty_print=True,
                              doctype='<!DOCTYPE tv SYSTEM "xmltv.dtd">')

    def load(self):
        logger.info("Loading channels")
        self._is_loading = True
        try:
            self._load()
        finally:
            self._is_loading = False

    def _load(self):
        # Get the m3u playlist
        m3u_channels = self._get_m3u(self.m3u_url)

        # Sort the m3u_channels by their name.
        m3u_channels.sort(key=lambda c: c["name"])

        # Set the channel numbers.
        i = 0
        for m3u_channel in m3u_channels:
            i += 1
            m3u_channel["number"] = f"{i}"

        self._channel_data = m3u_channels

    def _get_m3u(self, m3u_url):
        response = self.session.get(url=m3u_url)
        if response.status_code != 200:
            raise Exception(f"Error while getting {m3u_url}. API returned status code {response.status_code}, and body: {response.text}")

        channels = []
        current_channel = None
        first = True
        for line in iter(response.text.splitlines()):
            # Sanity check the file starts correctly.
            if first:
                if line == "#EXTM3U":
                    first = False
                    continue
                raise Exception(f"Expected {m3u_url} to begin with #EXTM3U. Instead it was {line}.")

            # #EXTINF are our channel markers. When we see one, we create a new channel.
            if line.startswith("#EXTINF:"):
                # Make sure we are messing up an exisiting channel that is being parsed.
                if current_channel is not None:
                    raise Exception(f"Expected current_channel to be None, instead it was {current_channel}.")

                # Make the current channel object.
                current_channel = {}

                # The #EXTINF lines contains attributes and then the name at the end of the line. Below is an example.
                # #EXTINF:0 group-title="NEWS" tvg-id="niews.example.com" tvg-logo="https://example.com/news.png" ,<Title String>
                attributes, name = line.split(",")

                current_channel["name"] = name

                for extractor_id in REGEX_EXTINF_EXTRACTOR:
                    extactor = REGEX_EXTINF_EXTRACTOR[extractor_id]
                    match = re.search(extactor, attributes)
                    if match and match.group("value"):
                        current_channel[extractor_id] = match.group("value")

            # Lines that don't start with a # are URLs to the channel. They also act as a way to close the current open channel.
            if not line.startswith("#"):
                if current_channel is None:
                    raise Exception(f"Expected current_channel to exist None.")
                current_channel["url"] = line
                channels.append(current_channel)
                current_channel = None

        return channels
