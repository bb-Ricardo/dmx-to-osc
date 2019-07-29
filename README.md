# sound_light_and_skamrahl_stuff
its like it sounds ..

## Install
```
virtualenv -p python2.7 .pyenv
. .pyenv/bin/activate
pip install oscpy
```

Also works with python 3.6 but without OLA support

# Input methods
* Only one of the two should be enabled in the [dmx_to_osc.ini](dmx_to_osc.ini) config file

## OLA
To work with OLA the OLA python modules need to be installed and OLA needs to run as a daemon

## Art-Net support
This script supports receiving Art-Net packages as well but has quite some limitations in the current version:
* receives only ArtDmx packages
* does not answer to ArtPoll Packages
* only 1 universe is supported
* receives unicast packages on the default Art-Net port 6454
* Never tested with real live equipment
