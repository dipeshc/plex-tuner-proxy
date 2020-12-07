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

## Development
### Setup
```
python3 -m venv env
source env/bin/activate
pip install -e ".[dev]"
```