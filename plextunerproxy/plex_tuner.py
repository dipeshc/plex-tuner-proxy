import logging

from flask import Flask, Response, request
from flask_restful import Resource, Api

logger = logging.getLogger()


class PlexTunerServer:
    """
    A server exposes a TV tuner for Plex.
    """

    def __init__(self, debug, plex_tuner_provider, port):
        """
        Constructs the Plex Tuner Server.
        :param boolean debug:                           flag to enable debugging.
        :param PlexTunerProvider plex_tuner_provider:   the Plex Tuner provider.
        :param int port:                                the webserver port.
        """
        self.app = Flask(__name__)
        self.debug = debug
        self.port = port

        resource_class_kwargs = {"plex_tuner_provider": plex_tuner_provider}
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
        """
        Constructor for the Discover API handler.
        """
        self.plex_tuner_provider = kwargs["plex_tuner_provider"]

    def get(self):
        """
        GET method handler.
        """
        return {
            "FriendlyName": self.plex_tuner_provider.friendly_name(),
            "Manufacturer": "PlexTunerProxy",
            "ModelNumber": "HDHR3-US",
            "FirmwareName": "hdhomerun3_atsc",
            "TunerCount": 2,
            "FirmwareVersion": "20150826",
            "DeviceID": f"{hash(self.plex_tuner_provider.friendly_name())}",
            "DeviceAuth": None,
            "BaseURL": f"http://{request.host}/",
            "LineupURL": f"http://{request.host}/lineup.json"
        }, 200


class EPG(Resource):
    """
    The EPG API resource handler.
    """

    def __init__(self, **kwargs):
        """
        Constructor for the EPG API handler.
        """
        self.plex_tuner_provider = kwargs["plex_tuner_provider"]

    def get(self):
        """
        GET method handler.
        """
        xml = self.plex_tuner_provider.epg()
        return Response(xml, mimetype='application/xml')


class LineUp(Resource):
    """
    The LineUp API resource handler.
    """

    def __init__(self, **kwargs):
        """
        Constructor for the LineUp API handler.
        """
        self.plex_tuner_provider = kwargs["plex_tuner_provider"]

    def get(self):
        """
        GET method handler.
        """
        if request.path.endswith("lineup.json"):
            return self.plex_tuner_provider.channels()

        if request.path.endswith("lineup_status.json"):
            if self.plex_tuner_provider.is_scanning():
                return {"ScanInProgress": True, "Progress": 50, "Found": 0}
            return {"ScanInProgress": False, "ScanPossible": True, "Source": "Cable", "SourceList": ["Cable"]}

    def post(self):
        """
        POST method handler.
        """
        if request.path.endswith("lineup.post"):
            if "scan" in request.args and request.args["scan"] == "start":
                if not self.plex_tuner_provider.is_scanning():
                    self.plex_tuner_provider.scan()
                return None
