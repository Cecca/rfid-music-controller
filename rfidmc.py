import logging
import os
import sys
from configparser import ConfigParser

from select import select
import musicpd
import spotipy
from dotenv import load_dotenv
from evdev import InputDevice, ecodes, list_devices
from spotipy.oauth2 import SpotifyClientCredentials

logging.basicConfig(level=logging.INFO)

pid = "/tmp/rfidmc.pid"

# Important: run, as root, the following command
#   usermod -a -G input
def get_input_devices():
    return [InputDevice(fn) for fn in list_devices()]


class Reader:

    def __init__(self, devname):
        #self.reader = self
        path = os.path.dirname(os.path.realpath(__file__))
        self.keys = "X^1234567890XXXXqwertzuiopXXXXasdfghjklXXXXXyxcvbnmXXXXXXXXXXXXXXXXXXXXXXX"
        devices = get_input_devices()
        logging.info("looking among " + str(list_devices()))
        for device in devices:
            if device.name == devname:
                self.dev = device
                break
        try:
            self.dev
        except:
            logging.error("no device found: " + str(devices))
            sys.exit('Could not find the device %s\n. Make sure is connected' % deviceName)

    def readCard(self):
        stri = ''
        key = ''
        while key != 'KEY_ENTER':
            r, w, x = select([self.dev], [], [])
            for event in self.dev.read():
                if event.type == 1 and event.value == 1:
                    stri += self.keys[event.code]
                    # print( keys[ event.code ] )
                    key = ecodes.KEY[event.code]
        return stri[:-1]


class SpotifyController(object):
    def __init__(self, device):
        load_dotenv()
        self.connection = None
        self.device_name = device.strip('"')
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.connection = self.get_connection()
        # Check if the device is available
        self.get_device()

    def get_connection(self):
        if self.connection is None:
            logging.info("connecting to Spotify")
            token = spotipy.util.prompt_for_user_token(
                "ceccarellom", 
                "user-read-recently-played user-read-playback-state user-modify-playback-state",
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri='http://localhost:8888/callback'
            )
            self.connection = spotipy.Spotify(auth=token)
            logging.info("successfully connected")
        return self.connection

    def reset(self):
        self.connection = None

    def get_device(self):
        conn = self.get_connection()
        devices = conn.devices()["devices"]
        for dev in devices:
            if dev['name'] == self.device_name:
                logging.info("successfully found device %s", self.device_name)
                return dev
        logging.error("device %s not found, available devices %s", self.device_name, devices)
        return None

    def get_currently_playing(self):
        conn = self.get_connection()
        return conn.currently_playback()

    def play_or_next(self, uri):
        uri = uri.strip('"')
        conn = self.get_connection()
        device = self.get_device()["id"]
        skip = False
        try:
            current_playback = conn.current_playback()
            current = current_playback["context"]["uri"]
            skip = current == uri and current_playback["is_playing"]
        except:
            # Do nothing, keep `skip` to the default of False
            pass
        if skip:
            logging.info("skipping to next track")
            conn.next_track()
        else:
            logging.info("playing %s", uri)
            uris = [uri] if "track" in uri else None
            context_uri = uri if "track" not in uri else None
            conn.start_playback(device_id=device, context_uri=context_uri, uris=uris)

    def stop(self):
        logging.info("asking for connection and device id")
        conn = self.get_connection()
        device = self.get_device()["id"]
        logging.info("got connection and device id, no problems")
        conn.pause_playback(device)


def load_config(path):
    parser = ConfigParser()
    parser.read(path)
    return parser


def main():
    config_path = sys.argv[1]
    config = load_config(config_path)

    rfid = Reader(config["general"]["rfid_device"].strip('"'))

    spotify_controller = SpotifyController(config["general"]["spotify_device"])
    mpd_controller = musicpd.MPDClient()
    mpd_controller.connect(config["general"]["mpd_host"].strip('"'))


    while True:
        tag = rfid.readCard()
        logging.info("read tag %s", tag)
        config = load_config(config_path)
        max_retries = config.getint("general", "retry")
        retry_count = 0
        should_try = True

        while should_try:
            if retry_count > 0:
                logging.warning("tentative %d", retry_count)
            try:
                if tag == config["controls"]["stop"].strip('"'):
                    logging.info("stopping spotify")
                    spotify_controller.stop()
                    logging.info("stopping mpd")
                    mpd_controller.stop()
                elif tag in config["spotify"]:
                    uri = config["spotify"][tag]
                    mpd_controller.stop()
                    spotify_controller.play_or_next(uri)
                elif tag in config["mpd"]:
                    spotify_controller.stop()
                    uri = config["mpd"][tag].strip('"')
                    logging.info("playing %s", uri)
                    mpd_controller.clear()
                    mpd_controller.load(uri)
                    mpd_controller.play()
                else:
                    logging.info("unknown tag %s", tag)
                should_try = False
            except Exception as e:
                logging.error("error %s", e)
                spotify_controller.reset()
                try:
                    mpd_controller.disconnect()
                except:
                    # Was already disconnected, do nothing
                    pass
                retry_count += 1
                if retry_count >= max_retries:
                    logging.error("too many retries, exiting")
                    sys.exit(1)


if __name__ == "__main__":
    main()

