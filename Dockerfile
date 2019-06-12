FROM python:3.7-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt
COPY gtfs_realtime_pb2.py /usr/src/app/
COPY gtfsrthttp2mqtt.py /usr/src/app/
COPY route_utils.py /usr/src/app/

CMD ["python", "gtfsrthttp2mqtt.py" ]
