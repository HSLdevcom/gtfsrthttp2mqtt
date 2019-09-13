import time
import os
from threading import Event, Thread

import paho.mqtt.client as mqtt
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import gtfs_realtime_pb2
import route_utils


## https://stackoverflow.com/questions/22498038/improve-current-implementation-of-a-setinterval-python/22498708#22498708
def call_repeatedly(interval, func, *args):
    stopped = Event()

    def loop():
        while not stopped.wait(interval):  # the first call is in `interval` secs
            func(*args)
        print("Polling stopped")

    Thread(target=loop, daemon=False).start()
    return stopped.set


class GTFSRTHTTP2MQTTTransformer:
    def __init__(self, mqttConnect, mqttCredentials, baseMqttTopic, gtfsrtFeedURL, feedName):
        self.mqttConnect = mqttConnect
        self.mqttCredentials = mqttCredentials
        self.baseMqttTopic = baseMqttTopic
        self.gtfsrtFeedURL = gtfsrtFeedURL
        self.feedName = feedName
        self.mqttConnected = False
        self.session = requests.Session()
        retry = Retry(connect=60, backoff_factor=1.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount(gtfsrtFeedURL, adapter)



    def onMQTTConnected(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        if rc != 0:
            return False
        if self.mqttConnected is True:
            print("Reconnecting and restarting poller")
            self.cancelPoller.cancel()
        self.mqttConnected = True

        self.startGTFSRTPolling()

    def connectMQTT(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.onMQTTConnected
        self.client.connect(**self.mqttConnect)
        if self.mqttCredentials and self.mqttCredentials['username'] and self.mqttCredentials['password']:
            self.client.username_pw_set(**self.mqttCredentials)
        self.client.loop_forever()

    def startGTFSRTPolling(self):
        print("Starting poller")
        polling_interval = int(os.environ.get('INTERVAL', 5))
        self.cancelPoller = call_repeatedly(polling_interval, self.doGTFSRTPolling)

    def doGTFSRTPolling(self):
        print("doGTFSRTPolling", time.ctime())
        r = self.session.get(self.gtfsrtFeedURL)

        if r.status_code != 200:
            print("GTFS RT feed returned with " + str(r.status_code))
            return
        feedmsg = gtfs_realtime_pb2.FeedMessage()
        try:
            feedmsg.ParseFromString(r.content)
            for entity in feedmsg.entity:
                # Don't send message if route_id is missing from entity
                # HasField() function does not work as expected, therefore we need check it like this
                if "route_id" not in map(lambda x: x.name, entity.vehicle.trip.DESCRIPTOR.fields):
                    continue

                nfeedmsg = gtfs_realtime_pb2.FeedMessage()
                nfeedmsg.header.gtfs_realtime_version = "1.0"
                nfeedmsg.header.incrementality = nfeedmsg.header.DIFFERENTIAL
                nfeedmsg.header.timestamp = int(time.time())
                nent = nfeedmsg.entity.add()

                nent.CopyFrom(entity)

                route_id = route_utils.parse_route_id(self.feedName, entity.vehicle.trip.route_id)
                direction_id = entity.vehicle.trip.direction_id
                trip_headsign = entity.vehicle.vehicle.label
                trip_id = entity.vehicle.trip.trip_id
                latitude = "{:.6f}".format(entity.vehicle.position.latitude) # Force coordinates to have 6 numbers
                latitude_head = latitude[:2]
                longitude = "{:.6f}".format(entity.vehicle.position.longitude)
                longitude_head = longitude[:2]
                geohash_head = latitude_head + ";" + longitude_head
                geohash_firstdeg = latitude[3] + "" + longitude[3]
                geohash_seconddeg = latitude[4] + "" + longitude[4]
                geohash_thirddeg = latitude[5] + "" + longitude[5]
                start_time = entity.vehicle.trip.start_time[0:5] # hh:mm
                vehicle_id = entity.vehicle.vehicle.id

                # gtfsrt/vp/<feed_name>/<agency_id>/<agency_name>/<mode>/<route_id>/<direction_id>/<trip_headsign>/<trip_id>/<next_stop>/<start_time>/<vehicle_id>/<geohash_head>/<geohash_firstdeg>/<geohash_seconddeg>/<geohash_thirddeg>
                # GTFS RT feed used for testing was missing some information so those are empty
                full_topic = '{0}/{1}////{2}/{3}/{4}/{5}//{6}/{7}/{8}/{9}/{10}/{11}/'.format(
                    self.baseMqttTopic, self.feedName, route_id, direction_id,
                    trip_headsign, trip_id, start_time, vehicle_id, geohash_head, geohash_firstdeg,
                    geohash_seconddeg, geohash_thirddeg)

                sernmesg = nfeedmsg.SerializeToString()
                self.client.publish(full_topic, sernmesg)
        except:
            print(r.content)
            raise


if __name__ == '__main__':
    gh2mt = GTFSRTHTTP2MQTTTransformer(
        {'host': os.environ['MQTT_BROKER_URL']},
        {'username': os.environ['USERNAME'], 'password': os.environ['PASSWORD']},
        '/gtfsrt/{0}'.format(os.environ['FEED_TYPE']),
        os.environ['FEED_URL'],
        os.environ['FEED_NAME']
    )

    try:
        gh2mt.connectMQTT()
    finally:
        gh2mt.cancelPoller()
