from __future__ import print_function, absolute_import, division

__metaclass__ = type

import numpy as np
import collections
import sys
import itertools
import traceback
import logging
import time
import threading

from . import hardware
from .elements import Sequence, SequenceStep, SequenceStepReuseSegment, WaveStep, __BLM__
from . import util

__CH_DICT_FULL__ = {'2g': [1, 2], '128m': [1, 2]}
__AWG_INSTRUMENT_ADDRESS__ = {'2g': 'TCPIP0::localhost::hislip1::INSTR', '128m': 'TCPIP0::localhost::hislip2::INSTR'}
__MASTER_AWG__ = '2g'
__MASTER_TRIGGER_CHANNEL__ = 1
__TRIGGER_DELAY_LENGTH_MUS__ = 27 * __BLM__ # the awg has a fixed trigger delay (sample clock dependent) of ~< 1mus
__TRIGGER_LENGTH_MUS__ = 27 * __BLM__ # duration of trigger sent to the slave awgs. Must not be longer __TRIGGER_DELAY_LENGTH_MUS__
__SLAVE_TRIGGER_SAFETY_LENGTH_MUS__ = 5 * __BLM__ # after __MASTER_AWG__ finishes its sequence, it waits this time until it starts over and sends a new trigger
__MAX_SINE_AVG_POWER__ = {'2g': {1: None, 2: None}, '128m': {1: 1.0, 2: None}}
__AMPLIFIER_POWER__ = {'2g': {1: 5., 2: 5.}, '128m': {1: 10.0, 2: None}}
__MARKER_ALIAS__ = {'green': ['2g', 2, 'smpl'], 'gate': ['2g', 2, 'sync'], 'red': ['128m', 1, 'sync'], 'infrared': ['128m', 1, 'smpl']}

class MultiChSeqDict(collections.OrderedDict):

    def __init__(self, debug_mode=False, restore_awg_settings=True):
        super(MultiChSeqDict, self).__init__()
        self.debug_mode = debug_mode  # completely stops interaction with the awg
        self.connect_to_awgs(restore_awg_settings=restore_awg_settings)
        self.set_wait()

    @property
    def debug_mode(self):
        return self._debug_mode

    @debug_mode.setter
    def debug_mode(self, val):
        if not hasattr(self, '_debug_mode') or self._debug_mode != util.check_type(val, 'debug_mode', bool):
            self._debug_mode = val
            if val is True:
                logging.getLogger().info("mcas_dict set to debug_mode {}".format(self.debug_mode))
            written_list = [val.written for val in self.values()]
            if val is True and not all(written_list):
                self.rewrite_keys_awg_memory(keys=[k for k in self.keys()[written_list.index(False):]])

    def connect_to_awgs(self, notify=True, restore_awg_settings=True):
        if not self.debug_mode:
            t0 = time.time()
            def get_awg(awgs, name):
                out = hardware.AWG(__AWG_INSTRUMENT_ADDRESS__[name], name, channel_numbers=__CH_DICT_FULL__[name])
                out.run = False
                if restore_awg_settings:
                    out.restore_settings_from_file()
                out.clear_memories()
                awgs[name] = out

            tl = []
            self.awgs = collections.OrderedDict()
            for name in __CH_DICT_FULL__.keys():
                tl.append(threading.Thread(target=get_awg, args=(self.awgs, name)))
                tl[-1].start()
            for t in tl:
                t.join()
            if notify:
                logging.getLogger().info("Connected to awgs {} in {}s".format(__CH_DICT_FULL__.keys(), time.time()-t0))
        elif notify:
            logging.getLogger().info("Debug mode! Did not connect to awgs {}".format(__CH_DICT_FULL__.keys()))

    def stop_awgs(self):
        if not self.debug_mode:
            stop_awgs(self.awgs)

    def set_wait(self):
        mcas = MultiChSeq(name='wait', ch_dict=__CH_DICT_FULL__)
        mcas.start_new_segment('wait')
        mcas.status = 1
        self['wait'] = mcas

    def __setitem__(self, key, value, dict_setitem=dict.__setitem__):
        if not isinstance(key, str):
            raise TypeError("key must be type str but is {} ({})".format(key, type(key)))
        if key != value.name:
            raise TypeError("Not allowed: {}, {}".format(key, MultiChSeq, type(value)))
        if key in self:
            del self[key]
        if value.written:
            raise Exception('Error: Sequence has already been written and can not be added.')
        value.mcas_dict = self
        if value.status == 0:
            value.finalize()
        if not self.debug_mode:
            value.write_to_awg_memory(notify=True)
        collections.OrderedDict.__setitem__(self, key=key, value=value)

    def __delitem__(self, key, dict_delitem=dict.__delitem__):
        didx = self.keys().index(key)
        delete_keys = [k for k in self.keys()[didx:]]
        self.delete_keys_from_awg_memory(delete_keys)
        del self[key].mcas_dict
        collections.OrderedDict.__delitem__(self, key=key)
        self.write_keys_to_awg_memory(delete_keys[1:])

    def rewrite_keys_awg_memory(self, keys):
        self.delete_keys_from_awg_memory(keys)
        self.write_keys_to_awg_memory(keys)

    def delete_keys_from_awg_memory(self, keys):
        for key in keys[::-1]:
            if self[key].written:
                self[key].delete_from_awg_memory()

    def write_keys_to_awg_memory(self, keys):
        if not self.debug_mode:
            for key in keys:
                self[key].write_to_awg_memory(notify=True)

    def dl(self, key, *args, **kwargs):
        return self[key].dl(*args, **kwargs)

    @property
    def info(self):
        return "\n".join(["{}, {}".format(key, val.ch_dict) for key, val in self.items()])

    def __repr__(self):
        return self.info

    def __str__(self):
        return self.info

    def print_info(self):
        print(self.info)

class MultiChSeq:
    def __init__(self, ch_dict=None, **kwargs):
        self.name = kwargs.get('name', kwargs.get('seq_name'))
        self.ch_dict = valid_ch_dict(__CH_DICT_FULL__ if ch_dict is None else ch_dict)
        self.init_sequences()
        self.status = 0

    name = util.ret_property_typecheck('name', str)

    def init_sequences(self):
        self.sequences = {}
        for awg_str, chl in self.ch_dict.items():
            self.sequences[awg_str] = dict([[ch, Sequence(name=self.name)] for ch in chl])

    def dl(self, awg, ch, sequence_step_num=None, wave_step_num=None):
        out = self.sequences[awg][ch]
        if sequence_step_num is not None:
            out = out.dl(sequence_step_num, wave_step_num)
        return out

    @property
    def written(self):
        return getattr(self, '_written', False)

    @written.setter
    def written(self, val):
        self._written = val

    @property
    def length_mus(self):
        return self.sequences.values()[0].values()[0].length_mus

    def asc(self, **kwargs):
        self.add_step_complete(**kwargs)

    def add_step_complete(self, **kwargs):
        pd = {}
        for awg_str, chl in self.ch_dict.items():
            pd[awg_str] = {}
            for ch in chl:
                pd[awg_str][ch] = kwargs.pop('pd' + awg_str + str(ch), {})
        for key in [k for k in kwargs if k in __MARKER_ALIAS__]:
            awg_str, ch, marker_name = __MARKER_ALIAS__[key]
            pd[awg_str][ch][marker_name + '_marker'] = kwargs.pop(key)
        self.add_step(pd=pd, **kwargs)

    def step_length_mus(self, pd, length_mus):
        lml = []
        if length_mus is not None:
            lml.append(length_mus)
        for awg_str in pd.keys():
            for ch in pd[awg_str].keys():
                if pd[awg_str][ch].get('type', 'wait') in ['robust']:
                    lml.append(WaveStep(**pd[awg_str][ch]).length_mus)
                elif 'length_mus' in pd[awg_str][ch]:
                    lml.append(pd[awg_str][ch]['length_mus'])
        if len(lml) == 0:
            return 0.0
        else:
            for i in lml:
                if abs(i - lml[0]) > 0.1 * (1e-9 * 1e6):
                    raise Exception('The steps for different channels must have same length')
            else:
                return lml[0]

    def add_step(self, pd=None, name='', length_mus=None, ssi=None, wsi=None, **kwargs):
        if self.status != 0:
            raise Exception('Error: MCAS {} is in state {} and can not be changed anmyore.'.format(self.name, self.status))
        if pd is None:
            pd = {}
        length_mus = self.step_length_mus(pd, length_mus=length_mus)
        for awg_str, chl in self.ch_dict.items():
            if awg_str not in pd:
                pd[awg_str] = {}
            for ch in chl:
                if ch not in pd[awg_str]:
                    pd[awg_str][ch] = {}
                if not pd[awg_str].get('type', 'wait') in ['robust']:
                    pd[awg_str][ch].update(length_mus=length_mus)
                if 'name' not in pd[awg_str][ch]:
                    pd[awg_str][ch].update(name=name)
                pd[awg_str][ch].update(**kwargs)
                if len(self.sequences[awg_str][ch].data_list) == 0:
                    raise Exception('There is no segment to append to. Start a new one first.')
                elif ssi is None:
                    ssi = len(self.sequences[awg_str][ch].data_list) - 1
                elif ssi > len(self.sequences[awg_str][ch].data_list) - 1:
                    raise Exception('Error: selected SequenceStep too big ({}, {}). '.format(ssi, len(self.sequences[awg_str][ch].data_list)))
                wsi = len(self.sequences[awg_str][ch].data_list[ssi].data_list) if wsi is None else wsi
                if wsi > (len(self.sequences[awg_str][ch].data_list[ssi].data_list)):
                    raise Exception('THIS PROBABLY IS NOT GOOD, PLEASE CHECK!')
                self.sequences[awg_str][ch].data_list[ssi].data_list.insert(wsi, WaveStep(**pd[awg_str][ch]))

    def start_new_segment(self, name='', reuse_segment=False, **kwargs):
        for awg_str, chl in self.ch_dict.items():
            for ch in chl:
                if reuse_segment:
                    for idx, step in enumerate(self.sequences[awg_str][ch].data_list):
                        if step.name == name:
                            self.sequences[awg_str][ch].data_list.append(SequenceStepReuseSegment(name=name, reused_sequence_step=step, **kwargs))
                            break
                    else:
                        self.sequences[awg_str][ch].data_list.append(SequenceStep(name=name, **kwargs))
                        print('Warning: reuse_segment was set for {} but no previously defined segment was found. reuse_segment was set to False'.format(name))
                else:
                    self.sequences[awg_str][ch].data_list.append(SequenceStep(name=name, **kwargs))

    def set_master_trigger_settings(self):
        for awg_str, chl in self.ch_dict.items():
            if awg_str == __MASTER_AWG__:
                for ch in chl:
                    trigger_sync_marker = True if ch == __MASTER_TRIGGER_CHANNEL__ else False
                    trigger_step = SequenceStep(name='triggerwait')
                    trigger_step.data_list.append(WaveStep(name='trigger', length_mus=__TRIGGER_LENGTH_MUS__, sync_marker=trigger_sync_marker))
                    trigger_step.data_list.append(WaveStep(name='waittrigger', length_mus=__TRIGGER_DELAY_LENGTH_MUS__ - __TRIGGER_LENGTH_MUS__))
                    w_trig_safety_step = SequenceStep(name='w_trig_safety', data_list=[WaveStep(name='w_trig_safety', length_mus=__SLAVE_TRIGGER_SAFETY_LENGTH_MUS__)])
                    self.sequences[awg_str][ch].data_list = [trigger_step] + self.sequences[awg_str][ch].data_list + [w_trig_safety_step]

    def set_slave_trigger_settings(self):
        for awg_str, chl in self.ch_dict.items():
            if awg_str != __MASTER_AWG__:
                for ch in chl:
                    wait_trigger_step = SequenceStep(data_list=[WaveStep(length_mus=0.0, name='w_trig_step')], advance_mode='SING')
                    self.sequences[awg_str][ch].data_list = self.sequences[awg_str][ch].data_list + [wait_trigger_step]

    def finalize(self, ignore_max_avg_power=False, notify=True):
        if self.status != 0:
            raise Exception('Error: MCAS {} has already been finalized'.format(self.name))
        t0 = time.time()
        self.fix_avg_rf_power(ignore_max_avg_power=ignore_max_avg_power)
        if __MASTER_AWG__ is not None and __MASTER_AWG__ in self.ch_dict and len(self.ch_dict) > 1:
            self.set_master_trigger_settings()
            self.set_slave_trigger_settings()
        self.status = 1
        if notify:
            logging.getLogger().info("MCAS '{}' finalized ({} s).".format(self.name, time.time() - t0))

    def fix_avg_rf_power(self, ignore_max_avg_power=False):
        awtd = {}
        for awg_str, l in __MAX_SINE_AVG_POWER__.items():
            awtd[awg_str] = {}
            for ch, max_avg_power in l.items():
                if max_avg_power is not None and ch in self.ch_dict.get(awg_str, []):
                    awtd[awg_str][ch] = self.additional_wait_time(awg_str, ch, max_avg_power, ignore_max_avg_power=ignore_max_avg_power)

            if all([i == 0 for i in flatten_dict_dict(awtd)]):
                return
            self.start_new_segment(name='rf_power_safety', loop_count=int(np.ceil(max(flatten_dict_dict(awtd)) / __BLM__)))
            self.asc(length_mus=__BLM__)
            for awg_str, l in __MAX_SINE_AVG_POWER__.items():
                for ch, max_avg_power in l.items():
                    if max_avg_power is not None and ch in self.ch_dict.get(awg_str, []):
                        if __AMPLIFIER_POWER__[awg_str][ch] * self.sequences[awg_str][ch].normalized_avg_sine_power / max_avg_power > 1.1 and not ignore_max_avg_power:
                            raise Exception(' Additional wait time added, but power still too high on awg {} ch {}! Sequence {} is {} mus long '
                                            'and has an average rf-power of {} W (maximally allowed: {} W) after adding an additional '
                                            'waiting time of {} mus'.format(awg_str, ch, self.name,
                                                                            self.sequences[awg_str][ch].length_mus,
                                                                            __AMPLIFIER_POWER__[awg_str][ch] * self.sequences[awg_str][ch].normalized_avg_sine_power,
                                                                            self.max_avg_power,
                                                                            awtd[awg_str][ch]))

    def additional_wait_time(self, awg_str, ch, max_avg_power, ignore_max_avg_power=False):
        if ignore_max_avg_power:
            return 0
        else:
            return check_avg_rf_power(self.sequences[awg_str][ch], awg_str=awg_str, ch=ch, max_avg_power=max_avg_power)

    def precompile_samples_waveform(self, notify=True):
        if self.status != 1:
            raise Exception('Error: MCAS {} has already been precompiled'.format(self.name))
        t0 = time.time()
        for awg_str, chl in self.ch_dict.items():
            for ch in chl:
                self.sequences[awg_str][ch].precompile_samples_waveform(0, notify=False)
        self.status = 2
        if notify:
            logging.getLogger().info("MCAS '{}' precompiled ({} s).".format(self.name, time.time() - t0))

    def write_seq(self, notify=True):
        self.finalize(notify=notify)
        self.precompile_samples_waveform(notify=notify)

    def write_to_awg_memory(self, ignore_max_avg_power=False, abort=None, notify=True):
        if not ignore_max_avg_power:
            for awg_str, l in __MAX_SINE_AVG_POWER__.items():
                for ch, max_avg_power in l.items():
                    if max_avg_power is not None and ch in self.ch_dict.get(awg_str, []):
                        if check_avg_rf_power(self.dl(awg_str, ch), awg_str, ch, max_avg_power, notify=True) != 0:
                            raise Exception('Average rf power too high')
        time_dict = {}
        for awg_str in self.ch_dict.keys():
            for ch, sequence in self.sequences[awg_str].items():
                if abort is not None and abort.is_set(): break
                try:
                    t0 = time.time()
                    self.mcas_dict.awgs[awg_str].ch[ch].write_sequence(sequence=sequence, sample_offset=0)
                    time_dict[awg_str + str(ch)] = float("{:.4f}".format(time.time() - t0))
                except:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_tb)
                    raise Exception('awg {} ch {} could not write sequence {} to memory.'.format(awg_str, ch, self.name))
        if notify:
            logging.getLogger().info('mcas {} has been written: {}'.format(self.name, time_dict))
        self.written = True

    def delete_from_awg_memory(self):
        for awg_str in self.ch_dict.keys():
            for ch, sequence in self.sequences[awg_str].items():
                self.mcas_dict.awgs[awg_str].ch[ch].delete_sequence(sequence=sequence)
        self.written = False

    def initialize(self):
        for awg_str, chl in __CH_DICT_FULL__.items():
            for ch in chl:
                if ch in self.ch_dict.get(awg_str, []):
                    sequence = self.sequences[awg_str][ch]
                else:
                    sequence = self.mcas_dict['wait'].sequences[awg_str][ch]
                self.mcas_dict.awgs[awg_str].ch[ch].initialize_sequence(sequence)

    def start_awgs(self, trigger=True):
        start_awgs(awgs=self.mcas_dict.awgs, ch_dict=self.ch_dict, trigger=trigger)

    def run(self, trigger=True):
        self.initialize()
        self.start_awgs(trigger=trigger)

def valid_ch_dict(ch_dict):
    if len(ch_dict) > 1:
        if __MASTER_AWG__ is None or __MASTER_TRIGGER_CHANNEL__ is None:
            raise Exception('No __MASTER_AWG__ and __MASTER_TRIGGER_CHANNEL__ must be given when multiple awgs are used. If you own the synchronization module, changes to the code need to be made.')
        if not __MASTER_AWG__ in ch_dict or not __MASTER_TRIGGER_CHANNEL__ in ch_dict[__MASTER_AWG__]:
            raise Exception('No __MASTER_AWG__ and __MASTER_TRIGGER_CHANNEL__ must be in ch_dict when multiple awgs are used.')
    return ch_dict

def check_avg_rf_power(sequence, awg_str, ch, max_avg_power=None, notify=True):
    avg_power = __AMPLIFIER_POWER__[awg_str][ch] * sequence.normalized_avg_sine_power
    additional_wait_time = max(0, sequence.length_mus * (avg_power / max_avg_power - 1))
    if notify:
        logging.getLogger().info("avg_power {:.2f} W,max_avg_power: {} W, additional_wait_time: {} mus".format(avg_power, max_avg_power, additional_wait_time))
    return additional_wait_time

def send_trigger(awgs, ch_dict=None):
    ch_dict = __CH_DICT_FULL__ if ch_dict is None else ch_dict
    awg_str = ch_dict.keys()[0] if len(ch_dict) == 1 else __MASTER_AWG__
    awgs[awg_str].send_begin()

def set_outputs(awgs, ch_dict=None):
    ch_dict = __CH_DICT_FULL__ if ch_dict is None else ch_dict
    for awg_str, chl in __CH_DICT_FULL__.items():
        for ch in chl:
            awgs[awg_str].ch[ch].output = 1 if ch in ch_dict.get(awg_str, []) else 0

def start_awgs(awgs, ch_dict=None, trigger=True):
    ch_dict = __CH_DICT_FULL__ if ch_dict is None else ch_dict
    for awg_str, channels in ch_dict.items():
            awgs[awg_str].run = True
    set_outputs(awgs, ch_dict=ch_dict)
    if trigger:
        send_trigger(ch_dict=ch_dict, awgs=awgs)

def stop_awgs(awgs, ch_dict=None):
    ch_dict = __CH_DICT_FULL__ if ch_dict is None else ch_dict
    for awg_str, channels in ch_dict.items():
        awgs[awg_str].run = False

def update(d, u):
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d

def flatten_dict_dict(dd):
    return list(itertools.chain(*[i.values() for i in dd.values()]))