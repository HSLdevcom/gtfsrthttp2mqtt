# gtfsrthttp2mqtt

Reads GTFS-RT feed from a http(s) source and publishes every entity to MQTT topic as its own differential GTFS-RT feed

## Configuration

You need to configure at least the following env variables that are marked as mandatory

* (mandatory) "MQTT_BROKER_URL" MQTT broker's URL
* (mandatory) "FEED_TYPE" which type of a GTFS RT data is provided (for example vp for vehicle position), used in MQTT topic
* (mandatory) "FEED_NAME" name for the data feed, used in MQTT topic
* (mandatory) "FEED_URL" URL for the HTTP(S) GTFS RT data source
* (optional) "USERNAME" username for publishing to a MQTT broker
* (optional) "PASSWORD" password for publishing to a MQTT broker
* (optional) "DELAY" how long to wait between fetching new data from HTTP(S) data feed
* (optional) "ROUTE_ID_REMOVE_FIRST" remove first n characters from route_id before publishing
* (optional) "ROUTE_ID_REMOVE_LAST" remove last n characters from route_id before publishing
