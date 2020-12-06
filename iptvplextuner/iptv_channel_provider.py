import logging
import re
import requests
import threading

from datetime import datetime, timedelta, timezone
from lxml import etree
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


logger = logging.getLogger()

AUTO_RELOAD_SECONDS = 2 * 60 * 60

REGEX_EXTINF_EXTRACTOR = {
    "id": 'tvg-id="(?P<value>[^"]+)"',
    "logo": 'tvg-logo="(?P<value>http[^"]+)"'
}

QUALITY_MAP = {
    "SD": 0, "HD": 1, "FHD": 2, "UHD": 3
}


class IPTVChannelProvider():

    def __init__(self, m3u_url, epg_url):
        """
        Constructor the IPTV Client.
        :param str m3u_url: the m3u playlist url
        :param str epg_url: the epg url
        """
        self.m3u_url = m3u_url
        self.epg_url = epg_url

        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])))
        self.session = session

        self._is_loading = False
        self._channel_data = []

        # Start the automatic reloader
        self._auto_loader()

    def is_loading(self):
        return self._is_loading

    def channels(self):
        channels = []
        for channel in self._channel_data:
            channels.append({
                "GuideNumber": channel["number"],
                "GuideName": channel["m3u_channel"]["name"],
                "HD": 1 if "HD" in channel["m3u_channel"]["name"] else 0,
                "URL": channel["m3u_channel"]["url"]
            })
        return channels

    def epg(self):
        # Compute time info, so all channels have the same time ranges.
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = start + timedelta(days=3)

        root = etree.fromstring("<tv></tv>")

        for cd in self._channel_data:
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

    def load(self):
        self._is_loading = True
        try:
            self._load()
        finally:
            self._is_loading = False

    def _load(self):
        # Get the m3u channels.
        m3u_channels = self._get_m3u(self.m3u_url)
        logger.debug(f"Found {len(m3u_channels)} m3u channels.")
        m3u_channels = self._filter_for_highest_quality_channel(m3u_channels)
        logger.debug(f"Filted to {len(m3u_channels)} by selecting the highest quality ones only.")

        # Use the m3u channels as a base to make the channels.
        channels = [{"m3u_channel": c} for c in m3u_channels]

        # Load the EPG data.
        epg_data = self._get_epg_data(self.epg_url)

        # Assign EGP channels.
        self._assign_epg_channels(epg_data, channels)

        # Assign EPG programmes
        self._assign_epg_programmes(epg_data, channels)

        # The last thing we do is sort and add channel numbers.
        channels.sort(key=lambda c: c["m3u_channel"]["name"])
        i = 1
        for channel in channels:
            channel["number"] = f"{i}"
            i += 1

        self._channel_data = channels

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

    def _filter_for_highest_quality_channel(self, channels):
        # Make a set of all channel names
        highest_quality_channel_map = {}

        for channel in channels:
            name = channel["name"]
            name_parts = name.split("|")
            if len(name_parts) != 2:
                base_name = name
                quality = "SD"
            else:
                base_name, quality = name_parts
            base_name = base_name.strip()
            quality = re.sub("[^a-zA-Z]+", "", quality)
            if base_name in highest_quality_channel_map:
                existing_quality = highest_quality_channel_map[base_name]["quality"]
                if QUALITY_MAP[existing_quality] < QUALITY_MAP[quality]:
                    highest_quality_channel_map[base_name] = {"name": name, "quality": quality}
            else:
                highest_quality_channel_map[base_name] = {"name": name, "quality": quality}

        highest_quality_channel_names = set()
        for k in highest_quality_channel_map:
            name = highest_quality_channel_map[k]["name"]
            highest_quality_channel_names.add(name)

        filtered_channels = []
        for channel in channels:
            if channel["name"] in highest_quality_channel_names:
                filtered_channels.append(channel)

        return filtered_channels

    def _get_epg_data(self, epg_url):
        response = self.session.get(url=epg_url)
        if response.status_code != 200:
            raise Exception(f"Error while getting {epg_url}. API returned status code {response.status_code}, and body: {response.text}")
        return response.content

    def _assign_epg_channels(self, epg_data, channels):
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
        root = etree.fromstring(epg_data)
        for channel in channels:
            if "epg_channel" not in channel:
                continue
            id = channel["epg_channel"].get("id")
            channel["epg_programmes"] = root.findall(f"programme[@channel='{id}']")

    def _auto_loader(self):
        logger.info("Loading channels.")
        self.load()
        logger.info(f"Loading channels completed. Sleeping for {AUTO_RELOAD_SECONDS} seconds until next reload.")
        threading.Timer(AUTO_RELOAD_SECONDS, self._auto_loader).start()
