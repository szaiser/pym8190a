from __future__ import print_function, absolute_import, division
__metaclass__ = type

import os
from .elements import __BLM__

settings_folder = os.path.join(os.getcwd(), 'hardware_settings')
ch_dict_full = {'2g': [1, 2], '128m': [1, 2]}
awg_instrument_adress = {'2g': 'TCPIP0::localhost::hislip1::INSTR', '128m': 'TCPIP0::localhost::hislip2::INSTR'}
master_awg = '2g'
master_trigger_channel = 1
restore_awg_settings = False


# optional settings
marker_alias = {'memory': ['2g', 1, 'smpl'], 'green': ['2g', 2, 'smpl'], 'gate': ['2g', 2, 'sync'], 'red': ['128m', 1, 'sync'], 'infrared': ['128m', 1, 'smpl']}
max_sine_avg_power = {'2g': {1: None, 2: None}, '128m': {1: 1.0, 2: None}}
amplifier_power = {'2g': {1: 5., 2: 5.}, '128m': {1: 10.0, 2: None}}

####################################################################################################################################
# internal settings
####################################################################################################################################
trigger_delay_length_mus = 27 * __BLM__ # the awg has a fixed trigger delay (sample clock dependent) of ~< 1mus
trigger_length_mus = 27 * __BLM__ # duration of trigger sent to the slave awgs. Must not be longer __TRIGGER_DELAY_LENGTH_MUS__
slave_trigger_safety_length_mus = 32 * __BLM__ # after __MASTER_AWG__ finishes its sequence, it waits this time until it starts over and sends a new trigger


