# Plex Tuner Proxy
## What is it?
A proxy for exposing a Plex Tuner. Currently the only supported proxy is to IPTV.

## What does it do?
Hosts a Plex Tuner webserver that can be added to Plex as a Live TV option. The Tuner is a proxy where the channels it
provides come from source like IPTV.

## How do I run it?
1. Download the appropriate latest release:
    * [Linux](https://github.com/dipeshc/plex-tuner-proxy/releases/latest/download/plex-tuner-proxy-ubuntu-latest)
    * [MacOS](https://github.com/dipeshc/plex-tuner-proxy/releases/latest/download/plex-tuner-proxy-macOS-latest)
2. Run it
    ```
    ./plex-tuner-proxy-macOS-latest --iptv.m3u <insert link to your M3U source> --iptv.epg <insert link to your EPG source>
    ```

### Help Output
```
usage: plex-tuner-proxy [-h] --iptv.m3u IPTV.M3U [--iptv.epg IPTV.EPG] [--auto-scan-interval-seconds AUTO_SCAN_INTERVAL_SECONDS] [--port PORT] [--debug]

optional arguments:
  -h, --help            show this help message and exit
  --iptv.m3u IPTV.M3U   Path to the m3u playlist.
  --iptv.epg IPTV.EPG   Path to the EPG.
  --auto-scan-interval-seconds AUTO_SCAN_INTERVAL_SECONDS
                        The frequency in seconds at which to trigger the auto scanning. To disable auto scanning set to 0 or a negative number.
  --port PORT           The tuner port Plex will connect too.
  --debug               Enables debug mode.
```

## Development
### Setup
```
python3 -m venv env
source env/bin/activate
pip install -e ".[dev]"
```