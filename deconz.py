REQUIREMENTS = ['websockets==3.3', 'aiohttp==2.2.3', 'attrs==16.3.0']

import voluptuous as vol
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, STATE_ON,
    STATE_OFF, CONF_API_KEY, CONF_HOST, CONF_PORT)
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import asyncio

_LOGGER = logging.getLogger('deconz')

CONF_WS_PORT = 'websocket_port'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=80):
        vol.All(int, vol.Range(1, 65535)),
    vol.Optional(CONF_WS_PORT, default=443):
        vol.All(int, vol.Range(1, 65535))
})

def lookup_device(devices, id):
    for device in devices:
        if device.id == id:
            return device
    return None

def normalize_name(name):
    return '_'.join(name.split()).lower()

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info):
    import libdeconz
    rest_url = 'http://%s:%d/api/' % (config[CONF_HOST], config[CONF_PORT])
    ws_url = 'ws://%s:%d' % (config[CONF_HOST], config[CONF_WS_PORT])
    api_key = config[CONF_API_KEY]
    session = libdeconz.DeconzSession(api_key, rest_url, ws_url)
    sensors = yield from session.get_sensors_async()
    devices = []
    for sensor in sensors:
        devices.append(DeconzSensor(sensor))

    add_devices(devices)

    @asyncio.coroutine
    def listen_events():
        _LOGGER.debug('listen_events()')
        while True:
            _LOGGER.debug('get_event_async()')
            event = yield from session.get_event_async()
            device = lookup_device(devices, event.id)
            if device is None:
                _LOGGER.debug('device not found')
                continue
            _LOGGER.debug('fire event')
            _LOGGER.debug(str(device))
            hass.bus.async_fire('deconz_buttonevent', {
                'id': event.id,
                'manufacturername': device.manufacturername,
                'mode': device.mode,
                'modelid': device.modelid,
                'name': normalize_name(device.name),
                'swversion': device.swversion,
                'type': device.type,
                'uniqueid': device.uniqueid,
                'buttonevent': event.event
            })

    def on_hass_stop(event):
        del event
        hass.async_add_job(session.close())

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    hass.loop.create_task(listen_events())


# TODO how do friendly_name etc come into play? Are those parsed by
# Entity somehow or do we need to fetch them ourselves?
#
# TODO update(), read from REST API again
class DeconzSensor(Entity):
    def __init__(self, sensor):
        self.__sensor = sensor
        self.__attributes = {
            'reachable': sensor.reachable,
            'manufacturername': sensor.manufacturername,
            'modelid': sensor.modelid,
            'name': normalize_name(sensor.name),
            'swversion': sensor.swversion,
            'type': sensor.type,
            'uniqueid': sensor.uniqueid
        }

    @property
    def id(self):
        return self.__sensor.id

    @property
    def reachable(self):
        return self.__sensor.reachable

    @property
    def manufacturername(self):
        return self.__sensor.manufacturername

    @property
    def mode(self):
        return self.__sensor.mode

    @property
    def modelid(self):
        return self.__sensor.modelid

    @property
    def name(self):
        return normalize_name(self.__sensor.name)

    @property
    def swversion(self):
        return self.__sensor.swversion

    @property
    def type(self):
        return self.__sensor.type

    @property
    def uniqueid(self):
        return self.__sensor.uniqueid

    @property
    def state_attributes(self):
        return self.__attributes
