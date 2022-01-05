FROM python:3.8.3-alpine3.11

RUN pip --no-cache-dir install ijson requests influxdb

COPY envoy.py ./

CMD [ "python", "./envoy.py" ]
