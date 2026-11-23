import hashlib
import time
import os
import json
import traceback
from threading import Event, Thread

import paho.mqtt.client as mqtt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2
import utils


## https://stackoverflow.com/questions/22498038/improve-current-implementation-of-a-setinterval-python/22498708#22498708
def call_repeatedly(interval, func, *args):
    stopped = Event()

    def loop():
        while not stopped.wait(interval):  # the first call is in `interval` secs
            try:
                func(*args)
            except Exception:
                # an uncaught error would end the polling thread for good
                traceback.print_exc()
        print("Polling stopped")

    Thread(target=loop, daemon=False).start()
    return stopped.set


class GTFSRTHTTP2MQTTTransformer:
    def __init__(self, mqttConnect, mqttCredentials, baseMqttTopic, gtfsrtFeedURL, gtfsrtFeedHeaders, feedName):
        self.mqttConnect = mqttConnect
        self.mqttCredentials = mqttCredentials
        self.baseMqttTopic = baseMqttTopic
        self.gtfsrtFeedURL = gtfsrtFeedURL
        self.feedName = feedName
        self.mqttConnected = False
        self.session = requests.Session()
        # the feed server sometimes answers with a 5xx error, try again soon instead of waiting for the next poll
        retry = Retry(connect=60, backoff_factor=1.5, status=2, status_forcelist=(500, 502, 503, 504),
                      allowed_methods=frozenset(['GET']), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount(gtfsrtFeedURL, adapter)
        self.session.headers.update(json.loads(gtfsrtFeedHeaders))
        self.OTPData = None
        self.lastFeedTimestamp = None
        self.lastFeedDigest = None


    def onMQTTConnected(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        if rc != 0:
            return False
        if self.mqttConnected is True:
            print("Reconnecting and restarting poller")
            self.GTFSRTPoller()
        self.mqttConnected = True
        self.doOTPPolling() #first round of polling otp data
        self.startGTFSRTPolling()
        self.startOTPPolling()

    def connectMQTT(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.onMQTTConnected
        self.client.connect(**self.mqttConnect)
        if self.mqttCredentials and self.mqttCredentials['username'] and self.mqttCredentials['password']:
            self.client.username_pw_set(**self.mqttCredentials)
        self.client.loop_forever()

    def startGTFSRTPolling(self):
        print("Starting GTFS RT poller")
        polling_interval = int(os.environ.get('INTERVAL', 5))
        self.GTFSRTPoller = call_repeatedly(polling_interval, self.doGTFSRTPolling)

    def doGTFSRTPolling(self):
        print("doGTFSRTPolling", time.ctime())
        started = time.time()
        try:
            r = self.session.get(self.gtfsrtFeedURL, timeout=(10, 60))
        except requests.RequestException as err:
            print("GTFS RT feed request failed: " + repr(err))
            return
        fetched = time.time()

        if r.status_code != 200:
            print("GTFS RT feed returned with " + str(r.status_code) + " after {:.1f} s: ".format(fetched - started) + r.text[:200])
            return
        feedmsg = gtfs_realtime_pb2.FeedMessage()
        try:
            feedmsg.ParseFromString(r.content)
        except DecodeError as err:
            print("GTFS RT feed could not be parsed ({} bytes): {}".format(len(r.content), err))
            return
        parsed = time.time()

        # Do not send messages for feeds older than already sent or for a feed identical to the previous one
        feedTimestamp = feedmsg.header.timestamp
        digest = hashlib.md5(r.content, usedforsecurity=False).digest()
        if self.lastFeedTimestamp is not None:
            if feedTimestamp < self.lastFeedTimestamp:
                print(f"Received a feed with timestamp earlier ({feedTimestamp}) than seen before ({self.lastFeedTimestamp}), skipping this update")
                return
            if feedTimestamp == self.lastFeedTimestamp and digest == self.lastFeedDigest:
                print("Feed has not changed, skipping this update")
                return
        self.lastFeedTimestamp = feedTimestamp
        self.lastFeedDigest = digest

        published = 0
        for entity in feedmsg.entity:
            if not entity.HasField('vehicle'):
                continue

            nfeedmsg = gtfs_realtime_pb2.FeedMessage()
            nfeedmsg.header.gtfs_realtime_version = "1.0"
            nfeedmsg.header.incrementality = nfeedmsg.header.DIFFERENTIAL
            nfeedmsg.header.timestamp = int(time.time())
            nent = nfeedmsg.entity.add()

            nent.CopyFrom(entity)

            trip_id = entity.vehicle.trip.trip_id
            route_id = utils.parse_route_id(self.feedName, entity.vehicle.trip.route_id, trip_id, self.OTPData)
            direction_id = entity.vehicle.trip.direction_id
            trip_headsign = entity.vehicle.vehicle.label
            # headsigns with / cause problems in topics
            if '/' in trip_headsign:
                trip_headsign = ''
            latitude = "{:.6f}".format(entity.vehicle.position.latitude) # Force coordinates to have 6 numbers
            latitude_head = latitude[:2]
            longitude = "{:.6f}".format(entity.vehicle.position.longitude)
            longitude_head = longitude[:2]
            geohash_head = latitude_head + ";" + longitude_head
            geohash_firstdeg = latitude[3] + "" + longitude[3]
            geohash_seconddeg = latitude[4] + "" + longitude[4]
            geohash_thirddeg = latitude[5] + "" + longitude[5]
            stop_id = entity.vehicle.stop_id
            start_time = entity.vehicle.trip.start_time[0:5] # hh:mm
            vehicle_id = entity.vehicle.vehicle.id
            short_name = utils.parse_short_name(self.feedName, trip_id, route_id, self.OTPData)
            color = utils.parse_color(self.feedName, trip_id, route_id, self.OTPData)
            mode = utils.parse_mode(self.feedName, trip_id, route_id, self.OTPData)

            # gtfsrt/vp/<feed_name>/<agency_id>/<agency_name>/<mode>/<route_id>/<direction_id>/<trip_headsign>/<trip_id>/<next_stop>/<start_time>/<vehicle_id>/<geohash_head>/<geohash_firstdeg>/<geohash_seconddeg>/<geohash_thirddeg>/<short_name>/<color>/
            # GTFS RT feed used for testing was missing some information so those are empty
            full_topic = '{0}/{1}///{2}/{3}/{4}/{5}/{6}/{7}/{8}/{9}/{10}/{11}/{12}/{13}/{14}/{15}/'.format(
                self.baseMqttTopic, self.feedName, mode, route_id, direction_id,
                trip_headsign, trip_id, stop_id, start_time, vehicle_id, geohash_head, geohash_firstdeg,
                geohash_seconddeg, geohash_thirddeg, short_name, color).replace("+","").replace("#", "")

            sernmesg = nfeedmsg.SerializeToString()
            self.client.publish(full_topic, sernmesg)
            published += 1

        print("Published {} vehicles: fetch {:.1f} s ({:.1f} MB), parse {:.2f} s, publish {:.2f} s".format(
            published, fetched - started, len(r.content) / 1e6, parsed - fetched, time.time() - parsed))

    def startOTPPolling(self):
        print("Starting OTP poller")
        polling_interval = int(os.environ.get('OTP_INTERVAL', 60 * 60)) # default 1 hour
        self.OTPPoller = call_repeatedly(polling_interval, self.doOTPPolling)

    def doOTPPolling(self):
        OTP_URL = os.environ.get('OTP_URL', 'https://dev-api.digitransit.fi/routing/v1/routers/waltti/index/graphql')
        otp_polling_session = requests.Session()
        retry = Retry(
            total=30,
            read=30,
            connect=30,
            backoff_factor=10,
            allowed_methods=frozenset(['GET', 'OPTIONS', 'POST'])
        )
        adapter = HTTPAdapter(max_retries=retry)
        otp_polling_session.mount(OTP_URL, adapter)
        query = utils.get_OTP_query(self.feedName)
        headers = {}
        if "AUTHENTICATION_HEADER" in os.environ and "AUTHENTICATION_TOKEN" in os.environ:
            headers[os.environ["AUTHENTICATION_HEADER"]] = os.environ["AUTHENTICATION_TOKEN"]

        try:
            response = otp_polling_session.post(OTP_URL, headers=headers, json={'query': query})
        except Exception as x:
            print('Failed to fetch OTP data :(', x.__class__.__name__)
        else:
            print('Fetched new OTP data')
            data_dictionary = {}
            data_type = 'routes' if 'routes' in response.json()['data'] else 'trips'
            for element in response.json()['data'][data_type]:
                gtfsId = element['gtfsId']
                del element['gtfsId']
                data_dictionary[gtfsId] = element
            self.OTPData = data_dictionary

if __name__ == '__main__':
    gh2mt = GTFSRTHTTP2MQTTTransformer(
        {'host': os.environ['MQTT_BROKER_URL']},
        {'username': os.environ['USERNAME'], 'password': os.environ['PASSWORD']},
        '/gtfsrt/{0}'.format(os.environ['FEED_TYPE']),
        os.environ['FEED_URL'],
        os.environ.get('FEED_HEADERS', '{}'),
        os.environ['FEED_NAME']
    )

    try:
        gh2mt.connectMQTT()
    finally:
        gh2mt.OTPPoller()
        gh2mt.GTFSRTPoller()
