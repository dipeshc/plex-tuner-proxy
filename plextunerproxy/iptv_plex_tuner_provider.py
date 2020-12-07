import logging
import re
import requests

from datetime import datetime, timedelta, timezone
from plextunerproxy.plex_tuner_provider import PlexTunerProvider
from lxml import etree
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

REGEX_EXTINF_EXTRACTOR = {
    "id": 'tvg-id="(?P<value>[^"]+)"',
    "logo": 'tvg-logo="(?P<value>http[^"]+)"'
}

QUALITY_MAP = {
    "SD": 0, "HD": 1, "FHD": 2, "UHD": 3
}

logger = logging.getLogger()


class IPTVPlexTunerProvider(PlexTunerProvider):
    """
    The IPTV Plex Tuner Provider. This class loads and provides the IPTV channels and EPG data.
    """

    def __init__(self, m3u_url, epg_url=None, auto_scan_interval_seconds=None):
        """
        Constructor the IPTV Plex Tuner Provider.
        :param str m3u_url: the m3u playlist url
        :param str epg_url: the epg url
        """
        self.m3u_url = m3u_url
        self.epg_url = epg_url

        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[427, 502, 503, 504])))
        self.session = session

        # Base class initialization needs to happen at the end, as it can trigger a scan which requires all the other arguments to be set.
        PlexTunerProvider.__init__(self, "IPTV", auto_scan_interval_seconds)

    def _scan(self):
        """
        Internal method that actually does the loading of the channel data. The channel data is a combination of m3u and epg sources. The
        m3u data is used as the base with the epg sourced data being overlayed. The matching of the two sources is done first by trying the
        channel id and then falling back to the channel name.
        """
        # Get the m3u channels.
        m3u_channels = self._get_m3u_channels()
        logger.debug(f"Found {len(m3u_channels)} m3u channels.")

        # Use the m3u channels as a base to make the channels.
        channels = [{"m3u_channel": c} for c in m3u_channels]

        # Overlay the EPG data if it has been provided.
        if self.epg_url:
            epg_data = self._get_epg_data()

            # Assign EGP channels.
            self._assign_epg_channels(epg_data, channels)

            # Assign EPG programmes
            self._assign_epg_programmes(epg_data, channels)

        # Sort and add channel numbers.
        channels.sort(key=lambda c: c["m3u_channel"]["name"])
        i = 1
        for channel in channels:
            channel["number"] = f"{i}"
            i += 1

        # Make the channels data.
        return_channels = []
        for channel in channels:
            return_channels.append({
                "GuideNumber": channel["number"],
                "GuideName": channel["m3u_channel"]["name"],
                "HD": 1 if "HD" in channel["m3u_channel"]["name"] else 0,
                "URL": channel["m3u_channel"]["url"]
            })

        # Make the EPG data.
        return_epg = self._to_epg(channels)

        return return_channels, return_epg

    def _to_epg(self, channels):
        """
        Converts channels to EPG data.
        :rtype: str
        """
        # Compute time info, so all channels have the same time ranges.
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = start + timedelta(days=3)

        root = etree.fromstring("<tv></tv>")

        for cd in channels:
            id = cd["number"]
            channel = etree.SubElement(root, "channel", {"id": id})
            display_name = etree.SubElement(channel, "display-name")
            display_name.text = cd["m3u_channel"]["name"]

            if "epg_channel" in cd:
                etree.SubElement(channel, "icon", {"src": cd["epg_channel"].findall("icon")[0].get("src")})
            elif "logo" in cd:
                etree.SubElement(channel, "icon", {"src": cd["m3u_channel"]["logo"]})

            if "epg_programmes" in cd and len(cd["epg_programmes"]) > 0:
                for programme in cd["epg_programmes"]:
                    programme.set("channel", id)
                    root.append(programme)
            else:
                current = start
                while current < end:
                    programme_start = current.strftime("%Y%m%d%H%M%S") + " -0000"
                    programme_stop = (current + timedelta(days=1)).strftime("%Y%m%d%H%M%S") + " -0000"
                    programme = etree.SubElement(root, "programme", {"start": programme_start, "stop": programme_stop, "channel": id})

                    title = etree.SubElement(programme, "title")
                    title.text = f"{cd['m3u_channel']['name']}"

                    desc = etree.SubElement(programme, "desc")
                    desc.text = f"{cd['m3u_channel']['name']} - {current}"

                    current += timedelta(hours=1)

        return etree.tostring(root, encoding="UTF-8",
                              xml_declaration=True,
                              pretty_print=True,
                              doctype='<!DOCTYPE tv SYSTEM "xmltv.dtd">')

    def _get_m3u_channels(self):
        """
        Interal method for getting the m3u chanels. Loads the m3u data from the provided URL and parses it. The parsing logic is not very
        robust and is a good candidate to be swapped out for an external library that does this well.
        :rtype: list
        """
        response = self.session.get(url=self.m3u_url)
        if response.status_code != 200:
            raise Exception(f"GET {self.m3u_url} failed. API returned status code {response.status_code}, and body: {response.text}")

        channels = []
        current_channel = None
        first = True
        for line in iter(response.text.splitlines()):
            # Sanity check the file starts correctly.
            if first:
                if line == "#EXTM3U":
                    first = False
                    continue
                raise Exception(f"Expected {self.m3u_url} to begin with #EXTM3U. Instead it was {line}.")

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
                    raise Exception("Expected current_channel to exist None.")
                current_channel["url"] = line
                channels.append(current_channel)
                current_channel = None

        return channels

    def _get_epg_data(self):
        """
        Gets the EPG data from the URL.
        :rtype: str
        """
        response = self.session.get(url=self.epg_url)
        if response.status_code != 200:
            raise Exception(f"GET {self.epg_url} failed. API returned status code {response.status_code}, and body: {response.text}")
        return response.content

    def _assign_epg_channels(self, epg_data, channels):
        """
        Assigns the EPG channel to the appropriate m3u channel. The channel matching process first tries to match by ID and then falls back
        to display name. This updates the passed in channel object by adding the matched EPG channel as a new key called "epg_channel".
        :param str epg_data:    the epg data
        :param array channels:  the channels
        """
        m3u_channels_by_id = {c["m3u_channel"]["id"]: c for c in channels if "id" in c["m3u_channel"]}
        m3u_channels_by_name = {c["m3u_channel"]["name"]: c for c in channels if "name" in c["m3u_channel"]}

        root = etree.fromstring(epg_data)
        for channel in root.findall("channel"):
            id = channel.get("id")
            matched_channel = None
            if id in m3u_channels_by_id:
                matched_channel = m3u_channels_by_id[id]
            if not matched_channel:
                display_name = channel.findall("display-name")[0].text
                if display_name in m3u_channels_by_name:
                    matched_channel = m3u_channels_by_name[display_name]

            if not matched_channel:
                continue

            if "epg_channel" in matched_channel:
                continue

            matched_channel["epg_channel"] = channel

    def _assign_epg_programmes(self, epg_data, channels):
        """
        Assigns the EPG programmes to the appropriate channel. This updates the passed in channel object by adding the programmes data as a
        new key called "epg_programmes".
        :param str epg_data:    the epg data
        :param array channels:  the channels
        """
        root = etree.fromstring(epg_data)
        for channel in channels:
            if "epg_channel" not in channel:
                continue
            id = channel["epg_channel"].get("id")
            channel["epg_programmes"] = root.findall(f"programme[@channel='{id}']")
