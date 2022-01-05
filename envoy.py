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


def scrape_stream(envoy_hostname):
    url = 'http://%s/stream/meter' % envoy_hostname
    while True:
        try:
            session = requests.Session()
            stream = session.get(url, auth=auth, stream=True, timeout=10)
            for line in stream.iter_lines(decode_unicode=True):
                if line.startswith(marker):
                    data = json.loads(line.replace(marker, ''))
                    prod=data['production']['ph-a']['p']+data['production']['ph-b']['p']
                    cons=data['total-consumption']['ph-a']['p']+data['total-consumption']['ph-b']['p']
                    net=data['net-consumption']['ph-a']['p']+data['net-consumption']['ph-b']['p']

                    #print("prod was %s, cons was %s, net was %s" % (float(prod), float(cons), float(net)))
                    #time.sleep(30)

        except requests.exceptions.RequestException as e:
            print('Exception fetching stream data: %s' % e)

def call_api(influx_client, envoy_hostname):
    url = 'http://%s/production.json' % envoy_hostname
    while True:
        try:
            now = datetime.datetime.now(pytz.timezone('America/Chicago'))
            session = requests.Session()
            response = session.get(url, timeout=10)
            data = json.loads(response.text)
            prod=data['production'][1]['wNow']
            prod_daily=data['production'][1]['whToday']
            cons=data['consumption'][0]['wNow']
            net=data['consumption'][1]['wNow']
            
            # envoy seems to lag behind a couple minutes on resetting these values at midnight, do it forcefully
            if (now.hour == 0 and now.minute <= 3):
                data['production'][1]['whToday'] = 0
                data['consumption'][0]['whToday'] = 0
            post_to_influx(influx_client,data)

        except requests.exceptions.RequestException as e:
            print('Exception fetching data: %s' % e)

 
        time.sleep(60)


def post_to_influx(influx_client,data):
    points = []
    
    try:
        readingTime = datetime.datetime.utcfromtimestamp(int(data['production'][1]['readingTime']))
        production = {
            "measurement": "Production",
            "time": readingTime,
            "fields": {
                "value": float(data['production'][1]['wNow'])
            }
        }
        production_daily = {
            "measurement": "DailyProduction",
            "time": readingTime,
            "fields": {
                "value": float(data['production'][1]['whToday'])
            }
        }
        consumption = {
            "measurement": "Consumption",
            "time": readingTime,
            "fields": {
                "value": float(data['consumption'][0]['wNow'])
            }
        }
        consumption_daily = {
	    "measurement": "DailyConsumption",
	    "time": readingTime,
	    "fields": {
		"value": float(data['consumption'][0]['whToday'])
	    }
        }
        net = {
            "measurement": "Net",
            "time": readingTime,
            "fields": {
                "value": float(data['consumption'][1]['wNow'])
            }
        }
        net_daily = {
            "measurement": "DailyNet",
            "time": readingTime,
            "fields": {
                "value": float(data['consumption'][0]['whToday'] - data['production'][1]['whToday'])
            }
        }

        points.append(production)
        points.append(production_daily)
        points.append(consumption)
        points.append(consumption_daily)
        points.append(net)
        points.append(net_daily)
        
        #print((json.dumps(points, indent=4, default=str)))
        #print("writing %d points to influxdb" % len(points))
 
        influx_client.write_points(points, time_precision='s', batch_size=100)
    except InfluxDBClientError as error:
        print('ERROR: Unable to post points to influxdb, error text is\n%s' % error)

def main():
    INFLUX_HOSTNAME = os.getenv('INFLUX_HOSTNAME', 'influxdb')
    ENVOY_HOSTNAME = os.getenv('ENVOY_HOSTNAME', '192.168.1.1')
    INFLUX_DB = os.getenv('INFLUX_DB', 'metrics')
  
    influx = InfluxDBClient(host=INFLUX_HOSTNAME, port=8086, database=INFLUX_DB)
    call_api(influx,ENVOY_HOSTNAME)

if __name__ == '__main__':
    main()

