FROM python:3.12-slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY gtfsrthttp2mqtt.py /usr/src/app/
COPY utils.py /usr/src/app/

CMD ["python", "-u", "gtfsrthttp2mqtt.py" ]
