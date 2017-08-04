DEPENDENCIES = ['group', 'light', 'sensor', 'scene']
import asyncio
import logging
import voluptuous as vol
import homeassistant.components.light
from homeassistant.const import STATE_ON
import time

DOMAIN = 'deconz_tradfri_remote'
_LOGGER = logging.getLogger(DOMAIN)

CONF_REMOTE = 'remote'
CONF_SCENES = 'scenes'
CONF_LIGHTS = 'lights'

CONFIG_SCHEMA = vol.Schema({
    vol.Required(DOMAIN): [{
        vol.Required(CONF_REMOTE): str,
        vol.Optional(CONF_SCENES): [str],
        vol.Optional(CONF_LIGHTS): [str]
        }]
    }, extra = vol.ALLOW_EXTRA)

# TODO
# - Support for groups in scenes.
# - Preserve on/off lamps when toggling on/off, don't use scenes so we can
#   save the state
# - Do all changes / service calls asynchronously in parallel
# - Single press brighter / darker
# - Double click?
# - cleanup debug output

g_remotes = {}

BUTTON_TOGGLE = 1002
BUTTON_DARKER_HOLD = 3001
BUTTON_DARKER_RELEASE = 3003
BUTTON_BRIGHTER_HOLD = 2001
BUTTON_BRIGHTER_RELEASE = 2003
BUTTON_RIGHT = 5002
BUTTON_LEFT = 4002

DIMMING_STATE_INACTIVE = 0
DIMMING_STATE_RUNNING = 1
DIMMING_STATE_STOP = 2

class Remote:
    def __init__(self, hass, uniqueid, scenes, lights):
        self.hass = hass
        self.uniqueid = uniqueid
        self.scenes = scenes
        self.lights = lights
        self.dimming_state = DIMMING_STATE_INACTIVE
        self.current_scene = 0

    def on_buttonevent(self, buttonevent):
        if buttonevent == BUTTON_TOGGLE:
            self.on_toggle()
        elif buttonevent == BUTTON_LEFT or buttonevent == BUTTON_RIGHT:
            self.change_scene(buttonevent)
        elif buttonevent == BUTTON_DARKER_HOLD or buttonevent == BUTTON_BRIGHTER_HOLD:
            self.on_dim(buttonevent)
        elif buttonevent == BUTTON_DARKER_RELEASE or buttonevent == BUTTON_BRIGHTER_RELEASE:
            self.stop_dim()

    def change_scene(self, buttonevent):
        if not any(self.scenes):
            return
        cs = self.current_scene
        if buttonevent == BUTTON_RIGHT:
            cs = cs + 1
            if cs >= len(self.scenes):
                cs -= len(self.scenes)
        elif buttonevent == BUTTON_LEFT:
            cs = cs - 1
            if cs < 0:
                cs += len(self.scenes)

        _LOGGER.info('Enable scene %s', self.scenes[cs])
        self.current_scene = cs
        self.hass.services.call('scene', 'turn_on', service_data={
            'entity_id': self.scenes[cs]
        })

    def on_dim(self, buttonevent):
        if self.dimming_state != DIMMING_STATE_INACTIVE:
            _LOGGER.warn("Cannot start dimming now; already in progress")
            return
        count = 0
        brightness = 0
        for light in self.lights:
            state = self.hass.states.get(light)
            if state is None:
                _LOGGER.warning('Light %s not found', light)
                continue
            if state.state != STATE_ON:
                _LOGGER.debug('%s: off', light)
            else:
                _LOGGER.debug('%s: %s', light, repr(state.attributes))
                _LOGGER.debug('%s: %s', light, state.attributes['brightness'])
                brightness += state.attributes['brightness']
            count += 1

        start_brightness = brightness/count
        if buttonevent == BUTTON_BRIGHTER_HOLD:
            target_brightness = 255.0
        else:
            target_brightness = 1.0
        self.dimming_state = DIMMING_STATE_RUNNING
        self.hass.loop.create_task(self.dimmer_loop(start_brightness, target_brightness))

    def stop_dim(self):
        if self.dimming_state == DIMMING_STATE_RUNNING:
            self.dimming_state = DIMMING_STATE_STOP

    @asyncio.coroutine
    def dimmer_loop(self, start_brightness, target_brightness):
        TOTAL_DIMMER_TIME = 7 # time from zero to max
        UPDATE_DELAY = 0.15
        FINAL_DELAY = 3*UPDATE_DELAY
        DIMMING_SPEED = 255.0/TOTAL_DIMMER_TIME

        distance = abs(target_brightness - start_brightness)
        total_time = distance/DIMMING_SPEED

        _LOGGER.debug('DIMMING_SPEED = %s', DIMMING_SPEED)
        _LOGGER.debug('start_brightness = %s', start_brightness)
        _LOGGER.debug('brightness_end = %s', target_brightness)
        _LOGGER.debug('distance = %s', distance)
        _LOGGER.debug('total_time = %s', total_time)

        start_time = time.time()
        end_time = start_time + total_time
        now = start_time
        _LOGGER.debug('start_time = %s', start_time)
        _LOGGER.debug('end_time = %s', end_time)
        _LOGGER.debug('now = %s', now)

        while now < end_time and self.dimming_state == DIMMING_STATE_RUNNING:
            dt = (now - start_time)/total_time
            brightness = int(start_brightness + dt*(target_brightness - start_brightness))
            #_LOGGER.info('brightness %s', brightness)
            for light in self.lights:
                homeassistant.components.light.turn_on(self.hass, light, brightness=brightness)
            yield from asyncio.sleep(UPDATE_DELAY)
            now = time.time()

        # When we call turn_on a lot, the call often fails because the light
        # is busy. To ensure we can reach maximum/minimum brightness we
        # do one final call after waiting a while longer.
        yield from asyncio.sleep(FINAL_DELAY)
        for light in self.lights:
            dt = (now - start_time)/total_time
            brightness = int(start_brightness + dt*(target_brightness - start_brightness))
            homeassistant.components.light.turn_on(self.hass, light, brightness=brightness)

        self.dimming_state = DIMMING_STATE_INACTIVE

    def on_toggle(self):
        any_on = False
        for light in self.lights:
            state = self.hass.states.get(light)
            if state is None:
                _LOGGER.warning('Light %s not found', light)
                continue
            _LOGGER.debug('%s: %s', light, state.state)
            if state.state == STATE_ON:
                any_on = True
                break

        turn_on = not any_on
        if turn_on and any(self.scenes):
            self.hass.services.call('scene', 'turn_on', service_data={
                'entity_id': self.scenes[self.current_scene]
            })
        else:
            for light in self.lights:
                if turn_on:
                    homeassistant.components.light.turn_on(self.hass, light)
                else:
                    homeassistant.components.light.turn_off(self.hass, light)

def on_buttonevent(event):
    _LOGGER.debug(repr(event.data))
    remote = g_remotes.get(event.data['uniqueid'])
    if remote is None:
        _LOGGER.info('No match for uniqueid %s', event.data['uniqueid'])
        return
    buttonevent = event.data['buttonevent']
    remote.on_buttonevent(buttonevent)

def setup_remote(hass, remote):
    uniqueid = remote[CONF_REMOTE]
    scenes_yaml = remote.get(CONF_SCENES, [])
    scenes = []
    lights = set()
    for scene in scenes_yaml:
        entities = hass.states.get(scene)
        if entities is None:
            continue
        entities = entities.attributes.get('entity_id', [])
        _LOGGER.debug('scene %s: %s', scene, entities)
        scenes.append(scene)
        for entity in entities:
            if entity.startswith('light.'):
                lights.add(entity)
    lights_yaml = remote.get(CONF_LIGHTS)
    if lights_yaml is not None:
        lights = set()
        for light in lights_yaml:
            lights.add(light)
    lights = list(lights)
    g_remotes[uniqueid] = Remote(hass, uniqueid, scenes, lights)


@asyncio.coroutine
def async_setup(hass, config):
    _LOGGER.debug('async_setup')
    ids = hass.states.async_entity_ids()
    _LOGGER.debug('Entity IDs:')
    for i in ids:
        _LOGGER.debug(i)

    _LOGGER.debug(repr(config[DOMAIN]))
    remotes_yaml = config[DOMAIN]
    if len(remotes_yaml) == 0:
        remotes_yaml = []    # Hass represents empty config as dict

    for remote in remotes_yaml:
        setup_remote(hass, remote)

    hass.bus.async_listen('deconz_buttonevent', on_buttonevent)
    return True
