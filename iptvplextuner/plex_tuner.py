import logging
import uuid

from flask import Flask, Response, request
from flask_restful import Resource, Api

logger = logging.getLogger()


class PlexTunerServer:
    """
    This server allows Plex to connect to IPTV by translating between the HDHomeRunner format Plex expect to the IPTV spec.
    """

    def __init__(self, debug, channel_provider, port):
        """
        Constructs the Plex Tuner Server.

        :param boolean debug:   flag to enable debugging.
        :param ChannelProvider: channel_provider:  the IPTV client.
        :param int port:        the webserver port.
        """
        self.app = Flask(__name__)
        self.debug = debug
        self.port = port

        resource_class_kwargs = {"id": str(uuid.uuid1()), "channel_provider": channel_provider}
        api = Api(self.app)
        api.add_resource(Discover, "/discover.json", resource_class_kwargs=resource_class_kwargs)
        api.add_resource(EPG, "/epg.xml", resource_class_kwargs=resource_class_kwargs)
        api.add_resource(LineUp, "/lineup.json", "/lineup_status.json", "/lineup.post", resource_class_kwargs=resource_class_kwargs)

    def run(self):
        """
        Runs the webserver.
        """
        self.app.run(host="127.0.0.1", port=self.port, debug=self.debug)


class Discover(Resource):
    """
    The Discover API resource handler.
    """

    def __init__(self, **kwargs):
        """"
        Constructor for the Discover API handler.
        """
        super().__init__()
        self.id = kwargs["id"]

    def get(self):
        """
        GET method handler.
        """
        return {
            "FriendlyName": "IPTV",
            "Manufacturer": "IPTVPlexTuner",
            "ModelNumber": "HDHR3-US",
            "FirmwareName": "hdhomerun3_atsc",
            "TunerCount": 2,
            "FirmwareVersion": "20150826",
            "DeviceID": self.id,
            "DeviceAuth": "IPTVPlexTuner",
            "BaseURL": f"http://{request.host}/",
            "LineupURL": f"http://{request.host}/lineup.json"
        }, 200


class EPG(Resource):
    def __init__(self, **kwargs):
        self.channel_provider = kwargs["channel_provider"]

    def get(self):
        xml = self.channel_provider.epg()
        return Response(xml, mimetype='application/xml')


class LineUp(Resource):
    def __init__(self, **kwargs):
        self.channel_provider = kwargs["channel_provider"]

    def get(self):
        if request.path.endswith("lineup.json"):
            if len(self.channel_provider.channels()) == 0:
                self.channel_provider.load()
            return self.channel_provider.channels(), 200

        if request.path.endswith("lineup_status.json"):
            if self.channel_provider.is_loading():
                return {"ScanInProgress": True, "Progress": 50, "Found": 5}, 200
            return {"ScanInProgress": False, "ScanPossible": True, "Source": "Cable", "SourceList": ["Cable"]}, 200

    def post(self):
        if request.path.endswith("lineup.post"):
            if "scan" in request.args and request.args["scan"] == "start":
                if not self.channel_provider.is_loading():
                    self.channel_provider.load()
                return None, 200
            elif "scan" in request.args and request.args["scan"] == "abort":
                return {}, 200
            else:
                return {}, 400
