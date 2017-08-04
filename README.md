# deCONZ and IKEA TRÅDFRI remote components for Home Assistant
This project was created to satisfy my need for controlling Home Assistant using IKEA's TRÅDFRI remotes. It uses the [deCONZ](https://www.dresden-elektronik.de/funktechnik/products/software/pc-software/deconz/) software by Dresden Elektronik to communicate with the remote, and consists of two components:
* deconz.py: a sensor platform for sending events on the Home Assistant event bus when buttons are pressed. This is entirely independent of IKEA specifics, and should work with any sensor that is recognized by deCONZ. You can use it to build any automations you like.
* deconz_tradfri_remote.py: a component that listens for events from IKEA remotes (as produced by deconz.py) and uses them to control scenes or individual lights in a sensible way. You can think of this as a pre-packaged set of automations implemented in Python.

## Prerequisites
To use this you need, at a minimum:
* The ConBee or RaspBee device used for ZigBee communication.
* [deCONZ](https://www.dresden-elektronik.de/funktechnik/products/software/pc-software/deconz/) set up and installed on a device, paired with at least one remote.
* Home Assistant installed and set up.

To use it fully with deconz_tradfri_remote you also need:
* At least one [IKEA TRÅDFRI remote control](http://www.ikea.com/us/en/catalog/products/20303317/), paired with deCONZ.
* At least one dimmable light that can be controlled by Home Assistant, for example a Philips Hue bulb or an IKEA TRÅDFRI wireless led bulb.
* At least two scenes configured to control the lights.

## Installing
In your home assistant configuration directory (~/.homeassistant, or wherever configuration.yaml lives), create these directories
* `custom_components`
* `custom_components/sensor`

Put libdeconz.py in `deps`, deconz.py in `custom_components/sensor`, and deconz_tradfri_remote.py in `custom_components`.

## Configuration
To connect to deCONZ you need to enable its web service plugin and create an API key as described in the deCONZ documentation. A (relatively) simple way of doing this is to use [Postman](https://chrome.google.com/webstore/detail/postman/fhbjgbiflinjbdggehcddcbncdddomop) to post the appropriate request. I realize this isn't very user-friendly but I'm not exactly sure how it can be made simpler either. Any suggestions are welcome.

Then you can configure the deCONZ platform by adding the following lines to your configuration.yaml file:

```yaml
sensor:
  - platform: deconz
    host: <host name or IP address>
    api_key: <API key that you created>
    port: <port for REST API, defaults to 80>
    websocket_port: <port for websocket, defaults to 443>
```

To get automations for TRÅDFRI remotes, you can add the following lines:
```yaml
deconz_tradfri_remote:
  - remote: <uniqueid of remote>
    scenes:
    - <scene 1>
    - <scene 2>
    lights:
    - <light 1>
    - <light 2>
```

Multiple remotes can be handled like this. The uniqueid can be obtained by looking at the Home Assistant events produced by the deconz sensor platform (or you can use the deCONZ REST API). Both the scenes and the lights sections are optional. If you specify a set of scenes, then you can use the < > buttons on the remote to cycle between scenes. The power button will toggle all of the lights that are controlled by any of the scenes. Holding down the dimming buttons will brighten or darken those same lights.

If you want to manually specify which lights should be controlled by the power and dimming buttons (or if you don't want to use scenes) then you can specify the light section, which simply enumerates all the lights.

The power button is not just a dumb toggle since I find it silly to just flip every light to its opposite state. Instead, if any of the lights are turned on then they will all be turned off. Otherwise, all of the lights are turned on by activating the current scene (or just requesting that they all turn on if there are no scenes).

### Example
Here's what my configuration for controlling my living room looks like at the time of writing:
```yaml
sensor:
  - platform: deconz
    api_key: <MY SECRET API KEY>
    host: localhost

deconz_tradfri_remote:
  - remote: "00:0b:57:ff:fe:0e:0f:e0-01-1000"
    scenes:
    - scene.livingroom_evening
    - scene.livingroom_cleaning
  - remote: "00:0b:57:ff:fe:4b:22:7f-01-1000"
    scenes:
    - scene.bedroom_night
    - scene.bedroom_reading
    - scene.bedroom_cleaning
```

## Events
Whenever deCONZ receives an event from a sensor, it is picked up by deconz.py and published on the Home Assistant event bus with the name "deconz_buttonevent", containing these attributes:

| Name             | Description                                              |
|------------------|----------------------------------------------------------|
| id               | Sequential ID assigned to the remote by deCONZ.          |
| manufacturername | Name of the manufacturer.                                |
| modelid          | Model name of the sensor.                                |
| name             | Name of the sensor.                                      |
| swversion        | Software version of the sensor.                          |
| type             | Sensor type (ZHASwitch, ZHALight or ZHAPresence).        |
| uniqueid         | Unique ID of sensor, normally the MAC address.           |
| buttonevent      | Event identifier for a button event (depends on device). |
| mode             | Unknown.                                                 |

For example, a Home Assistant log entry for pressing the on/off switch may look like this:

```
INFO (MainThread) [homeassistant.core] Bus:Handling <Event deconz_buttonevent[L]: id=2, type=ZHASwitch, name=tradfri_remote_control_2, manufacturername=IKEA of Sweden, uniqueid=00:0b:57:ff:fe:0e:0f:e0-01-1000, buttonevent=1002, modelid=TRADFRI remote control, swversion=1.0, mode=3>
```

## Contributing
I have limited time to work on this, and limited resources for testing it on devices I don't own. But I welcome any patches you submit and will try to integrate them promptly. Examples of things I'm looking for are:
* Improved or alternative ways of controlling lights
* Tailored support for other ZigBee sensors (Hue switches for example)
* Better dimming support, perhaps by using transitions instead of flooding the device with HTTP requests.

## License
The code is licensed under the MIT License. See [LICENSE.md](LICENSE.md) for details

## Acknowledgements
This project wouldn't have seen the light of day if it wasn't for these guys:
* Maija Vilkina and her blog [Snillevilla](https://snillevilla.se/) has been a huge help in getting deCONZ up and running with the IKEA devices.
* [Svenska hemautomatiseringsgruppen](https://www.facebook.com/groups/SHgruppen/) is an amazing group of knowledgeable, helpful and inspiring people.
* The people on Home Assistant's Discord chat server for helping me understand the Home Assistant architecture.
