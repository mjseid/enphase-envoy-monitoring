#pip3 install ijson requests

import os
import time
import json
import ijson
import requests
import threading
import datetime
import pytz
from requests.auth import HTTPDigestAuth
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

# set install specific global variables
iuser = 'installer'
ipassword = 'Abc123De'
user = 'envoy'
password = '012345'
auth = HTTPDigestAuth(iuser, ipassword)
marker = 'data: '


def scrape_stream(influx,envoy_hostname):
    url = 'http://%s/stream/meter' % envoy_hostname
    while True:
        try:
            session = requests.Session()
            stream = session.get(url, auth=auth, stream=True, timeout=10)
            points = []
            for line in stream.iter_lines(decode_unicode=True):
                if line.startswith(marker):
                    data = json.loads(line.replace(marker, ''))

                    now = datetime.datetime.now(pytz.timezone('America/Chicago'))
                    prod=data['production']['ph-a']['p']+data['production']['ph-b']['p']
                    cons=data['total-consumption']['ph-a']['p']+data['total-consumption']['ph-b']['p']
                    production = {
                        "measurement": "Production",
			            "time": now,
			            "fields": {
			                "value": float(prod)
			            }
		            }
                    consumption = {
			            "measurement": "Consumption",
			            "time": now,
			            "fields": {
			                "value": float(cons)
                        }
                    }
                    points.append(production)
                    points.append(consumption)
                    if (len(points) >= 120):
                        influx.write_points(points, time_precision='s', batch_size=200)
                        #print("writing %d points to influxdb" % len(points))
                        points.clear()
                    
                    #print("prod was %s, cons was %s, net was %s" % (float(prod), float(cons), float(net)))


        except requests.exceptions.RequestException as e:
            print('Exception fetching stream data: %s' % e)


def main():
    INFLUX_HOSTNAME = os.getenv('INFLUX_HOSTNAME', 'influxdb')
    ENVOY_HOSTNAME = os.getenv('ENVOY_HOSTNAME', '192.168.1.1')
    INFLUX_DB = os.getenv('INFLUX_DB', 'verbosedata')
  
    influx = InfluxDBClient(host=INFLUX_HOSTNAME, port=8086, database=INFLUX_DB)
    scrape_stream(influx,ENVOY_HOSTNAME)

if __name__ == '__main__':
    main()

