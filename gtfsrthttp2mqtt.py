import time
from threading import Event, Thread

import paho.mqtt.client as mqtt
import requests

import gtfs_realtime_pb2


## https://stackoverflow.com/questions/22498038/improve-current-implementation-of-a-setinterval-python/22498708#22498708
def call_repeatedly(interval, func, *args):
    stopped = Event()

    def loop():
        while not stopped.wait(interval):  # the first call is in `interval` secs
            func(*args)

    Thread(target=loop, daemon=True).start()
    return stopped.set


class GTFSRTHTTP2MQTTTransformer:
    def __init__(self, mqttConnect, mqttCredentials, mqttTopic, gtfsrtFeedURL):
        self.mqttConnect = mqttConnect
        self.mqttCredentials = mqttCredentials
        self.mqttTopic = mqttTopic
        self.gtfsrtFeedURL = gtfsrtFeedURL
        self.mqttConnected = False

    def onMQTTConnected(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        if rc != 0:
            return False
        self.mqttConnected = True

        self.startGTFSRTPolling()

    def connectMQTT(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.onMQTTConnected
        self.client.connect(**self.mqttConnect)
        if self.mqttCredentials:
            self.client.username_pw_set(**self.mqttCredentials)
        self.client.loop_forever()

    def startGTFSRTPolling(self):
        print("Starting poller")
        self.cancelPoller = call_repeatedly(15, self.doGTFSRTPolling)

    def doGTFSRTPolling(self):
        print("doGTFSRTPolling", time.ctime())
        r = requests.get(self.gtfsrtFeedURL)

        feedmsg = gtfs_realtime_pb2.FeedMessage()
        try:
            feedmsg.ParseFromString(r.content)
            for e in feedmsg.entity:
                nfeedmsg = gtfs_realtime_pb2.FeedMessage()
                nfeedmsg.header.gtfs_realtime_version = "1.0"
                nfeedmsg.header.incrementality = nfeedmsg.header.DIFFERENTIAL
                nfeedmsg.header.timestamp = int(time.time())
                nent = nfeedmsg.entity.add()

                nent.CopyFrom(e)

                sernmesg = nfeedmsg.SerializeToString()
                self.client.publish("gtfsrt/tre/vp", sernmesg)

        except:
            print(r.content)
            raise


if __name__ == '__main__':
    gh2mt = GTFSRTHTTP2MQTTTransformer(
        {'host': None},
        {'username': None, 'password': None},
        '/gtfsrt/tre/vp',
        None
    )

    try:
        gh2mt.connectMQTT()
    finally:
        gh2mt.cancelPoller()
