import sys
import asyncio
import aiohttp
import websockets
import json
import attr

@attr.s
class DeconzSensor:
    id = attr.ib()
    reachable = attr.ib()
    manufacturername = attr.ib()
    mode = attr.ib()
    modelid = attr.ib()
    name = attr.ib()
    swversion = attr.ib()
    type = attr.ib()
    uniqueid = attr.ib()

@attr.s
class DeconzSensorEvent:
    id = attr.ib()
    event = attr.ib()

class DeconzSession:
    def __init__(self, api_key, api_url, websocket_url):
        if not api_url.endswith('/'):
            api_url += '/'
        api_url += api_key
        self.__session = aiohttp.ClientSession()
        self.__websocket_url = websocket_url
        self.__socket = None
        self.__api_url = api_url

    def close(self):
        if self.__socket is not None:
            self.__socket.close()
        self.__session.close()

    @asyncio.coroutine
    def get_sensors_async(self):
        sensors = []
        response = yield from self.__session.get(self.__api_url + '/sensors')
        sensors_json = yield from response.text()
        sensors_json = json.loads(sensors_json)
        for index, sensor_json in sensors_json.items():
            sensor = DeconzSensor(id = index,
                reachable = sensor_json['config']['reachable'],
                manufacturername = sensor_json['manufacturername'],
                mode = sensor_json['mode'],
                modelid = sensor_json['modelid'],
                name = sensor_json['name'],
                swversion = sensor_json['swversion'],
                type = sensor_json['type'],
                uniqueid = sensor_json['uniqueid'])
            sensors.append(sensor)
        return sensors

    @asyncio.coroutine
    def get_event_async(self):
        if self.__socket is None:
            self.__socket = yield from websockets.connect(self.__websocket_url)
        event_json = yield from self.__socket.recv()
        event_json = json.loads(event_json)
        event = DeconzSensorEvent(event_json['id'], event_json['state']['buttonevent'])
        return event

@asyncio.coroutine
def _main():
    api_key = sys.argv[1]
    rest_url = sys.argv[2]
    ws_url = sys.argv[3]
    session = DeconzSession(api_key, rest_url, ws_url)
    try:
        sensors = yield from session.get_sensors_async()
        print(sensors)
        while True:
            event = yield from session.get_event_async()
            print(event)
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.get_event_loop().set_debug(True)
    asyncio.get_event_loop().run_until_complete(_main())
