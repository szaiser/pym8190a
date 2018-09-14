from __future__ import print_function, absolute_import, division

__metaclass__ = type
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
import numpy as np

import datetime
import time
import numpy as np
import struct
import collections
import itertools
import logging
import sys, traceback
from numbers import Number
import types

from . import util

# TODO: Add type 'key' to SequenceStep(). Length sample then ideally could be read out from AWG by key number,
# TODO: or it would be 0. Then however also checks for the fulfillment of the linear playtime requirement would have to
# TODO: be included.

__SAMPLE_FREQUENCY__ = 12e3
__ADVANCE_MODE_MAP__ = {'AUTO': 0, 'COND': 1, 'REP': 2, 'SING': 3}
__AMPLITUDE_GRANULARITY__ = 1 / 2. ** 11
__MAX_LENGTH_SMPL__ = 2e9  # most probably wrong, but a reasonable estimate
__BLM__ = 384. / __SAMPLE_FREQUENCY__
__SAMPLE_DURATION_TOLERANCE__ = 1e-2 / __SAMPLE_FREQUENCY__
__MIN_SEGMENT_LENGTH_MUS__ = 320 / __SAMPLE_FREQUENCY__


# def round_to_segment_length_mus(length_mus):
#     step = 320/__SAMPLE_FREQUENCY__ if length_mus <= 320/__SAMPLE_FREQUENCY__ else 64/__SAMPLE_FREQUENCY__
#     return np.around(np.array(length_mus)/step) * step

def round_length_mus_full_sample(length_mus):
    return np.around(np.array(length_mus) * __SAMPLE_FREQUENCY__) / __SAMPLE_FREQUENCY__


def valid_length_mus(length_mus):
    if not np.allclose(length_mus, round_length_mus_full_sample(length_mus=length_mus), __SAMPLE_DURATION_TOLERANCE__):
        raise Exception(
            'length mus {} is not valid for the current sample_frequency {}'.format(length_mus, __SAMPLE_FREQUENCY__))


def valid_length_smpl(length_smpl):
    if not length_smpl.is_integer():
        raise Exception(
            'length mus {} is not valid'.format(length_smpl))


def length_mus2length_smpl(length_mus):
    valid_length_mus(length_mus=length_mus)
    return np.around(length_mus * __SAMPLE_FREQUENCY__).astype(np.int64)


def length_smpl2length_mus(length_smpl):
    valid_length_smpl(length_smpl)
    return length_smpl / __SAMPLE_FREQUENCY__


def round_to_amplitude_granularity(amplitude):
    return np.around(np.array(amplitude) / __AMPLITUDE_GRANULARITY__) * __AMPLITUDE_GRANULARITY__


class list_repeat(list):
    """
    Allows one wavefile to be used for driving at multiple frequencies without copying it.
    """

    def __getitem__(self, i):
        try:
            return super(list_repeat, self).__getitem__(i)
        except Exception:
            if len(self) != 1:
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
        return super(list_repeat, self).__getitem__(0)


class DataList(collections.MutableSequence):
    def __init__(self, oktypes, list_owner, *args, **kwargs):
        self.oktypes = oktypes
        self.list_owner = list_owner
        self.list = list()
        self.extend(list(args))

    def check(self, v):
        if not isinstance(v, self.oktypes):
            raise TypeError("list item {} is not allowed, as it can not be found in {}".format(v, self.oktypes))

    def set_parent(self, v):
        v.parent = self.list_owner

    @property
    def missing_smpl(self):
        ls = sum([step.length_smpl for step in self.list])
        return max(5 * 64 - ls, (-ls) % 64)

    @property
    def missing_smpl_step(self):
        return WaveStep(length_smpl=self.missing_smpl, name='_missing_smpls_')

    def __len__(self):
        l = len(self.list)
        if type(self.list_owner) == SequenceStep:
            l += 1
        return l

    def __getitem__(self, i):
        if type(self.list_owner) == SequenceStep and i == len(self.list):
            return self.missing_smpl_step
        else:
            return self.list[i]

    def __delitem__(self, i):
        del self.list[i]

    def __setitem__(self, i, v):
        self.check(v)
        self.set_parent(v)
        self.list[i] = v
        if type(self.list_owner) == SequenceStep:
            self.list_owner.set_write_awg(idx=i, val=v, action='set')

    def insert(self, i, v):
        self.check(v)
        self.set_parent(v)
        self.list.insert(i, v)
        self.list_owner.set_write_awg(idx=i, val=v, action='insert')

    def __str__(self):
        return str(self.list)

    def __iadd__(self, other):
        self.extend(list(other))
        return self.list

    def __radd__(self, other):
        for v in other[::-1]:
            self.insert(0, v)
        return self.list

    def __add__(self, other):
        self.extend(list(other))
        return self.list

    def __imul__(self, other):
        raise NotImplementedError

    def __rmul__(self, other):
        raise NotImplementedError

    def __mul__(self, other):
        raise NotImplementedError

class Root:
    def __init__(self, **kwargs): pass


class Base(Root):
    def __init__(self, name='', comment='', parent=None, **kwargs):  # sample_frequency=12.,
        super(Base, self).__init__(**kwargs)
        self.name = name
        self.comment = comment
        self.parent = parent

    name = util.ret_property_typecheck('name', str)
    comment = util.ret_property_typecheck('comment', str)

    @property
    def parent(self):
        return getattr(self, '_parent', None)

    @parent.setter
    def parent(self, val):
        self._parent = val

    @property
    def repeated_length_mus(self):
        return self.length_mus * getattr(self, 'loop_count', 1)

    @property
    def repeated_length_smpl(self):
        return self.length_smpl * getattr(self, 'loop_count', 1)

    def ret_list(self, l, row=0, prefix=''):
        return ("{}{:<6}{:<18}{:<10.6f}" + (len(l) - 2) * "{:<8}").format(prefix, row, *l)

    def print_list(self, *args, **kwargs):
        print(self.ret_list(*args, **kwargs))

class WaveFile(Base):
    __doc__ = "Nothing"

    def __init__(self, rp=None, tni=None, filepath=None, filedata=None,
                 scaling_factor=None, part=None, frequency_scaling_factor=None, **kwargs):
        super(WaveFile, self).__init__(**kwargs)
        self.set_part(part)
        self.set_rp(rp)
        self.set_tni(tni)
        self.set_scaling_factor(scaling_factor)
        self.set_frequency_scaling_factor(frequency_scaling_factor)
        self.read_filedata(filepath=filepath, filedata=filedata)
        self.update_data()

    @Base.parent.setter
    def parent(self, val):
        if val is not None:
            Base.parent.fset(self, val)
            if val.type == 'robust':
                self.parent.length_mus = self.length_mus

    @property
    def part(self):
        return getattr(self, '_part', [0, None])

    def set_part(self, val):
        if val is not None:
            if not float(val[0]).is_integer() and (float(val[1]).is_integer() or val[1] is None):
                raise Exception("Error: {}".format(val))
            self._part = val

    @property
    def filepath(self):
        return self._filepath

    def read_filedata(self, filepath=None, filedata=None):
        if (filepath is not None) ^ (filedata is not None):
            if filepath is not None:
                self._filepath = filepath
                filedata = np.loadtxt(self.filepath)
            self.process_filedata(filedata)
        else:
            raise Exception("Error!")

    def process_filedata(self, filedata):
        if filedata is not None:
            dr = filedata[self.part[0]:self.part[1]]
            self.step_length_mus_raw = dr[:, 0]
            self.data_raw = dr[:, 1:]

    @property
    def rp(self):
        return self._rp

    def set_rp(self, val):
        if val is None:
            raise Exception('Error!')
        self._rp = val

    @property
    def tni(self):
        return self._tni

    def set_tni(self, val):
        self._tni = val

    @property
    def scaling_factor(self):
        return self._scaling_factor

    def set_scaling_factor(self, val):
        if val is None:
            self._scaling_factor = 1.0
        elif type(val) in [float, int]:
            self._scaling_factor = val
        else:
            raise ValueError

    @property
    def frequency_scaling_factor(self):
        return self._frequency_scaling_factor

    def set_frequency_scaling_factor(self, val):
        if val is None:
            self._frequency_scaling_factor = 1.0
        elif type(val) in [float, int]:
            self._frequency_scaling_factor = val
        else:
            raise ValueError('Error: {}'.format(val))

    @property
    def number_of_frequencies(self):
        nc = np.size(self.data_raw, 1)
        if nc % 3 == 0 or nc >= 6:  # assumes, that for 7 columns, two frequencies with [amplitudes, phase, detuning] are given in the file
            return int(nc / 3.0)
        elif nc % 2 == 0:
            return int(nc / 2.0)
        else:
            raise Exception("Wave file does not have correct number of columns")

    @property
    def detuning_given(self):
        nc = np.size(self.data_raw, 1)
        if nc % 3 == 0 or nc >= 6:  # assumes, that for 7 columns, two frequencies with [amplitudes, phase, detuning] are given in the file
            return True
        elif nc % 2 == 0:
            return False
        else:
            raise Exception("Wave file does not have correct number of columns")

    @property
    def data_raw_extended(self):
        wfd = self.data_raw
        if not self.detuning_given:
            for i in range(self.number_of_frequencies):
                wfd = np.insert(wfd, 3 * (i + 1) - 1, 0, axis=1)
        return wfd

    @property
    def number_of_steps(self):
        return np.size(self.data_raw, 0)

    @property
    def rabi_frequencies_raw(self):
        return self.data_raw_extended[:, ::3]

    @property
    def rabi_frequencies(self):
        return self.rabi_frequencies_raw * self.scaling_factor * self.frequency_scaling_factor

    @property
    def amplitudes(self):
        return self._amplitudes

    @amplitudes.setter
    def amplitudes(self, val):
        val = np.around(val / __AMPLITUDE_GRANULARITY__) * __AMPLITUDE_GRANULARITY__
        if np.any(val < 0.0):
            raise Exception('The rabi frequencies given in the robust pulse file result \n '
                            'in awg amplitudes smaller than 0 which indicates, \n '
                            'that the given nonlinear_params or the interoplation algorithm are chosen badly.')
        elif np.any(np.sum(val, axis=1) > 1.0):
            raise Exception('The rabi frequencies given in the robust pulse file result \n '
                            'in awg amplitudes larger than 1.\n Probably the rabi frequencies in the robust '
                            'pulse file are too high for the current experimental conditions.')
        else:
            self._amplitudes = val

    def rabi_frequency(self, n_step, n_freq):
        if n_step > self.number_of_steps:
            raise Exception('No parameters given for n_step {}'.format(n_step))
        elif self.number_of_frequencies == 1:
            return self.rabi_frequencies[n_step, 0]
        elif n_freq > self.number_of_frequencies:
            raise Exception('No parameters given for frequency {}'.format(n_freq))
        else:
            return self.rabi_frequencies[n_step, n_freq]

    def set_amplitudes(self):
        self.amplitudes = self.rp.amplitude(tni=self.tni, omega=self.rabi_frequencies)

    def set_phases(self):
        self.phases = self.data_raw_extended[:, 1::3]

    def set_detunings(self):
        self.detunings = self.data_raw_extended[:, 2::3]

    def amplitude(self, n_step, n_freq):
        return self.get_val('amplitudes', n_step, n_freq)

    def phase(self, n_step, n_freq):
        return self.get_val('phases', n_step, n_freq)

    def detuning(self, n_step, n_freq):
        return self.get_val('detunings', n_step, n_freq)

    def get_val(self, name, n_step, n_freq):
        if n_step > self.number_of_steps:
            raise Exception('No parameters given for n_step {}'.format(n_step))
        elif self.number_of_frequencies == 1:
            return getattr(self, name)[n_step, 0]
        elif n_freq > self.number_of_frequencies:
            raise Exception('No parameters given for frequency {}'.format(n_freq))
        else:
            return getattr(self, name)[n_step, n_freq]

    def update_data(self):
        self.set_amplitudes()
        self.set_phases()
        self.set_detunings()
        self.set_length_mus()
        self.precompile_amplitudes_phases()

    def set_length_mus(self):
        self.length_mus = np.sum(self.step_length_mus)
        self.length_smpl = length_mus2length_smpl(self.length_mus)
        if hasattr(self, '_parent') and self.parent.type == 'robust':
            self.parent.length_mus = self.length_mus

    @property
    def step_length_mus(self):
        val = self.step_length_mus_raw / self.scaling_factor
        valid_length_mus(val)
        return val

    @property
    def step_length_smpl(self):
        return length_mus2length_smpl(self.step_length_mus)

    def ret_part(self, start_duration, end_duration):
        if self.part != [0, None] and self.part != [0, self.number_of_steps]:
            raise Exception('Part has already been set, operation not allowed.')
        csd = np.concatenate([[0.0], np.cumsum(self.step_length_mus)])
        part = []
        for key, val in [('start_duration', start_duration), ('end_duration', end_duration)]:
            delta = csd - val
            i = np.where(np.abs(delta) < __SAMPLE_DURATION_TOLERANCE__)
            if len(i) == 1:
                part.append(i[0][0])
            else:
                raise Exception('No more than one element should be found. Found elements: {}'.format(i))
        return part

    def precompile_amplitudes_phases(self):
        self.amplitudes_samples = list_repeat()
        self.phases_samples = list_repeat()
        csls = np.concatenate([np.array([0]), np.cumsum(self.step_length_smpl)])
        for n_freq in range(self.number_of_frequencies):
            self.amplitudes_samples.append(np.empty(self.length_smpl))
            self.phases_samples.append(np.empty(self.length_smpl))
            for n_step in range(self.number_of_steps):
                self.phases_samples[n_freq][csls[n_step]:csls[n_step + 1]] = np.degrees(self.phase(n_step, n_freq))
                self.amplitudes_samples[n_freq][csls[n_step]:csls[n_step + 1]] = self.amplitude(n_step, n_freq)

    def ret_info(self, prefix=''):
        return str(type(self))

    def print_info(self, *args, **kwargs):
        print(self.ret_info(*args, **kwargs))

class BaseWave(Base):

    def __init__(self, **kwargs):
        super(BaseWave, self).__init__(**kwargs)

    def samples_amp(self, coherent_offset):
        """
        This is the real value the awg will output, rounded to 12 bit resolution
        """
        return (self.samples_dac(coherent_offset) >> 4) / 2047.

    def samples_dac(self, coherent_offset):
        return self.samples_waveform(coherent_offset) - self.samples_marker


class WaveStep(BaseWave):
    def __init__(self, type='wait', phase_offset_type='coherent', frequencies=None, amplitudes=None, constant_value=None,
                 phases=None, smpl_marker=False, sync_marker=False, wave_file=None, length_mus=None, length_smpl=None, **kwargs):
        super(WaveStep, self).__init__(**kwargs)
        self.length_mus = length_mus
        self.length_smpl = length_smpl
        self.wave_file = wave_file
        self.type = type
        self.phase_offset_type = phase_offset_type
        self.frequencies = np.array([0]) if frequencies is None else frequencies
        self.amplitudes = np.array([0]) if amplitudes is None else amplitudes
        self.constant_value = 0 if constant_value is None else constant_value
        self.phases = np.array([0]) if phases is None else phases
        self.smpl_marker = smpl_marker
        self.sync_marker = sync_marker

    phase_offset_type = util.ret_property_list_element('phase_offset_type', ['coherent', 'absolute'])
    smpl_marker = util.ret_property_typecheck('smpl_marker', bool)
    sync_marker = util.ret_property_typecheck('sync_marker', bool)

    @property
    def length_mus(self):
        return self._length_mus

    @property
    def length_smpl(self):
        return self._length_smpl

    @length_mus.setter
    def length_mus(self, val):
        if val is not None:
            valid_length_mus(val)
            self._length_mus = util.check_range(util.check_type(val, 'length_mus', Number), 'length_mus', 0, (__MAX_LENGTH_SMPL__-1) / __SAMPLE_FREQUENCY__)
            self._length_smpl = length_mus2length_smpl(self._length_mus)

    @length_smpl.setter
    def length_smpl(self, val):
        if val is not None:
            self._length_mus = util.check_range(util.check_type(val, 'length_smpl', Number), 'length_smpl', 0, __MAX_LENGTH_SMPL__-1) / __SAMPLE_FREQUENCY__
            self._length_smpl = length_mus2length_smpl(self._length_mus)

    @property
    def wave_file(self):
        return getattr(self, '_wave_file', None)

    @wave_file.setter
    def wave_file(self, val):
        if val is not None:
            if isinstance(val, WaveFile):
                val.parent = self
                self._wave_file = val
            else:
                raise Exception('wave_file can be None or of type WaveFile but is {}'.format(val))

    @property
    def type(self):
        return getattr(self, '_type', None)

    @type.setter
    def type(self, val):
        self._type = util.check_list_element(val, 'type', ['wait', 'constant', 'sine', 'robust'])
        if self.type == 'robust' and hasattr(self, '_wave_file'):
            self.length_mus = self.wave_file.length_mus

    @property
    def frequencies(self):
        return self._frequencies

    @frequencies.setter
    def frequencies(self, val):
        self._frequencies = np.array(util.check_array_like_typ(val, 'frequencies', Number), dtype=float)
        self._frequencies.setflags(write=False)

    @property
    def amplitudes(self):
        amps = self._amplitudes
        if len(amps) == 1:
            amps = np.zeros(len(self.frequencies)) + amps[0]
        if sum(amps) - 1.0 > 10 * np.finfo(np.float64).eps:  # larger than 10 times machine precision
            raise Exception("Wavestep {} has amplitudes {} whose sum is larger than one (delta = {}, frequencies {})".format(self.name, self._amplitudes, sum(amps) - 1.0, self.frequencies))
        return amps

    @amplitudes.setter
    def amplitudes(self, val):
        self._amplitudes = np.array(util.check_array_like_typ(val, 'amplitudes', Number), dtype=float)
        self._amplitudes.setflags(write=False)

    @property
    def constant_value(self):
        return self._constant_value

    @constant_value.setter
    def constant_value(self, val):
        self._constant_value = util.check_range_type(val, 'constant_value', Number, -(1 + 10 * np.finfo(np.float64).eps), 1 + 10 * np.finfo(np.float64).eps)

    @property
    def phases(self):
        phases = self._phases
        if len(phases) == 1:
            phases = np.zeros(len(self.frequencies)) + phases[0]
        return phases

    @phases.setter
    def phases(self, val):
        self._phases = np.array(util.check_array_like_typ(val, 'phases', Number), dtype=float)
        self._phases.setflags(write=False)

    def effective_offset(self, coherent_offset):
        if self.phase_offset_type == 'coherent':
            return coherent_offset
        elif self.phase_offset_type == 'absolute':
            return 0

    def sin(self, samples, start, amps, freqs, phases, length_smpl, coherent_offset):
        for i, freq in enumerate(freqs):
            arg = np.arange(coherent_offset, length_smpl + coherent_offset, dtype=np.float)
            arg *= 2 * np.pi * freq / __SAMPLE_FREQUENCY__
            arg += np.radians(phases[i] + self.phases[i])
            np.sin(arg, out=arg)
            arg *= amps[i] * 2047
            samples[start:start + length_smpl] += np.int16(arg)

    def constant(self, samples, start, constant_value, length_smpl):
        samples[start:start + length_smpl] += np.int16(constant_value * 2047)

    def samples_waveform(self, coherent_offset, start=0, samples=None):
        samples = np.zeros(self.length_smpl, dtype=np.int16) if samples is None else samples
        effective_coherent_offset = self.effective_offset(coherent_offset)
        if self.type in ['sine', 'robust']:
            if self.type == 'sine':
                amplitudes = self.amplitudes
                phases = list_repeat([0.0])  # self.phases is added automatically
            elif self.type == 'robust':
                amplitudes = self.wave_file.amplitudes_samples
                phases = self.wave_file.phases_samples  # self.phases is added automatically
            self.sin(samples=samples,
                     start=start,
                     amps=amplitudes,
                     freqs=self.frequencies,
                     phases=phases,
                     length_smpl=self.length_smpl,
                     coherent_offset=effective_coherent_offset)
        elif self.type == 'constant':
            self.constant(samples=samples,
                          start=start,
                          constant_value=self.constant_value,
                          length_smpl=self.length_smpl)
        samples[start:start + self.length_smpl] *= 2 ** 4
        samples[start:start + self.length_smpl] += self.marker
        return samples

    @property
    def samples_smpl_marker(self):
        return np.full(self.length_smpl, self.smpl_marker, dtype=np.int8)

    @property
    def samples_sync_marker(self):
        return np.full(self.length_smpl, self.sync_marker, dtype=np.int8)

    @property
    def marker(self):
        return self.smpl_marker + 2 * self.sync_marker

    @property
    def samples_marker(self):
        return np.full(self.length_smpl, self.smpl_marker + 2 * self.sync_marker, dtype=np.int8)

    @property
    def normalized_avg_sine_power(self):
        if self.type == 'sine':
            return sum(self.amplitudes ** 2)
        elif self.type == 'robust':
            return sum([self.wave_file.amplitude(i[0], i[1]) ** 2 for i in itertools.product(range(self.wave_file.number_of_steps), range(len(self.frequencies)))]) / self.wave_file.number_of_steps
        elif self.type == 'wait':
            return 0
        elif self.type == 'constant':
            return 0
        else:
            raise Exception('Neither sine nor robust do apply here...{}'.format(self.type))

    def ret_info(self, row=0, prefix=''):
        if self.type == 'wait':
            l = [self.name, self.length_mus, self.type, int(self.smpl_marker), int(self.sync_marker)]
        if self.type == 'constant':
            l = [self.name, self.length_mus, self.type, self.constant_value, int(self.smpl_marker), int(self.sync_marker)]
        elif self.type == 'sine':
            l = [self.name, self.length_mus, self.type, self.frequencies, self.amplitudes, self.phases, int(self.smpl_marker), int(self.sync_marker)]
        elif self.type == 'robust':
            l = [self.name, self.length_mus, self.type, self.frequencies, 'wave_file', self.phases, int(self.smpl_marker), int(self.sync_marker)]
        return self.ret_list(l, row=row, prefix=prefix)

    def print_info(self, *args, **kwargs):
        print(self.ret_info(*args, **kwargs))



class BaseLoopAdvance(Root):

    def __init__(self, loop_count=1, **kwargs):
        super(BaseLoopAdvance, self).__init__(**kwargs)
        self.loop_count = loop_count
        self.advance_mode = kwargs['advance_mode']

    loop_count = util.ret_property_range('loop_count', int, 0, 2 ** 32 - 1)
    advance_mode = util.ret_property_list_element('advance_mode', ['AUTO', 'COND', 'REP', 'SING'])


class BaseDataList(Root):

    def __init__(self, data_list=None, **kwargs):
        super(BaseDataList, self).__init__(**kwargs)
        self.data_list = [] if data_list is None else data_list

    @property
    def length_mus(self):
        return np.sum(step.repeated_length_mus for step in self.data_list)

    @property
    def length_smpl(self):
        return length_mus2length_smpl(self.length_mus)

    @property
    def data_list(self):
        return self._data_list

    @data_list.setter
    def data_list(self, val):
        for i in util.check_type(val, 'data_list', (list, DataList)):
            if not isinstance(i, self.__DATA_LIST_ITEM_TYPE__):
                raise Exception("Elements of property data_list of a {} - instance must be of type {} but is of type {}".format(type(self), self.__DATA_LIST_ITEM_TYPE__, type(i)))
        self._data_list = DataList(self.__DATA_LIST_ITEM_TYPE__, self, *val)

    def samples_waveform(self, coherent_offset, start=0, samples=None):
        samples = np.zeros(self.length_smpl, dtype=np.int16) if samples is None else samples
        idx = start
        for i, step in enumerate(self.data_list):
            loop_count = 1 if not hasattr(step, '_loop_count') else step.loop_count
            for _ in range(loop_count):
                step.samples_waveform(coherent_offset + idx, start=idx, samples=samples)  # , loop_count #samples[: idx + rls] =
                idx += step.length_smpl
        return samples

    @property
    def samples_smpl_marker(self):
        return np.concatenate([step.samples_smpl_marker for step in self.data_list])

    @property
    def samples_sync_marker(self):
        return np.concatenate([step.samples_sync_marker for step in self.data_list])

    @property
    def samples_marker(self):
        return np.concatenate([step.samples_marker for step in self.data_list])

    @property
    def sample_offsets(self):
        return np.cumsum([step.length_smpl for step in self.data_list])

    @property
    def number_of_steps(self):
        return len(self.data_list)

    @property
    def step_name_list(self):
        return [step.name for step in self.data_list]

    def ret_step(self, name):
        snl = self.step_name_list
        if snl.count(name) == 1:
            return self.data_list[snl.index(name)]
        elif snl.count(name) == 0:
            return None
        elif snl.count(name) > 1:
            raise Exception('name {} occured more than once'.format(name))

    @property
    def normalized_avg_sine_power(self):
        return sum([step.repeated_length_mus * step.normalized_avg_sine_power for step in self.data_list]) / self.repeated_length_mus

    def ret_info(self, row=0, prefix=''):
        out = []
        if hasattr(self, 'loop_count'):
            out.append(self.ret_list([self.name, self.repeated_length_mus, self.loop_count], row=row, prefix=prefix))
        else:
            print('does not have loop count')
            out.append(self.ret_list([self.name, self.repeated_length_mus], row=row, prefix=prefix))
        for i, step in enumerate(self.data_list):
            out.append(step.ret_info(row=i, prefix="   " + prefix))
        return "\n".join(out)

    def print_info(self, *args, **kwargs):
        print(self.ret_info(*args, **kwargs))

    def pi(self, *args, **kwargs):
        self.print_info(*args, **kwargs)


class BaseSequenceStep(BaseWave, BaseLoopAdvance):

    def __init__(self, marker_enable=True, advance_mode='AUTO', **kwargs):
        super(BaseSequenceStep, self).__init__(advance_mode=advance_mode, **kwargs)
        self.marker_enable = marker_enable
        self.set_segment_offsets(**kwargs)

    @property
    def sequence_id(self):
        return self._sequence_id

    @BaseLoopAdvance.loop_count.setter
    def loop_count(self, val):
        BaseLoopAdvance.loop_count.fset(self, val)
        self.write_sequence_memory = True

    @BaseLoopAdvance.advance_mode.setter
    def advance_mode(self, val):
        BaseLoopAdvance.advance_mode.fset(self, val)
        self.write_sequence_memory = True

    @property
    def marker_enable(self):
        return self._marker_enable

    @marker_enable.setter
    def marker_enable(self, val):
        if val is False:
            print('Warning: ONLY SET TO FALSE IF YOU KNOW WHAT YOU ARE DOING')
        self._marker_enable = util.check_type(val, 'marker_enable', bool)
        self.write_sequence_memory = True

    def set_segment_offsets(self, **kwargs):
        default = {'segment_start_offset': 0, 'segment_end_offset': 2 ** 32 - 1}
        for s in ['segment_start_offset', 'segment_end_offset']:
            if s not in kwargs and s+'_mus' not in kwargs:
                setattr(self, s, default[s])
            elif s in kwargs and s+'_mus' in kwargs:
                raise Exception('Error: overdetermination. {}'.format(kwargs))
            elif s in kwargs:
                setattr(self, s, kwargs[s])
            else:
                setattr(self, s, kwargs[s+'_mus'])

    @property
    def segment_start_offset_mus(self):
        return self._segment_start_offset_mus

    @property
    def segment_start_offset(self):
        return self._segment_start_offset

    @segment_start_offset_mus.setter
    def segment_start_offset_mus(self, val):
        if val is not None:
            valid_length_mus(val)
            self._segment_start_offset_mus = util.check_range(util.check_type(val, 'segment_start_offset_mus', Number), 'segment_start_offset_mus', 0, __MAX_LENGTH_SMPL__ / __SAMPLE_FREQUENCY__)
            self._segment_start_offset = length_mus2length_smpl(self._segment_start_offset_mus)

    @segment_start_offset.setter
    def segment_start_offset(self, val):
        if val is not None:
            self._segment_start_offset_mus = util.check_range(util.check_type(val, 'segment_start_offset_mus', Number), 'segment_start_offset_mus', 0, __MAX_LENGTH_SMPL__) / __SAMPLE_FREQUENCY__
            self._segment_start_offset = length_mus2length_smpl(self._segment_start_offset_mus)

    @property
    def segment_end_offset_mus(self):
        return self._segment_end_offset_mus

    @property
    def segment_end_offset(self):
        return self._segment_end_offset

    @segment_end_offset_mus.setter
    def segment_end_offset_mus(self, val):
        if val is not None:
            valid_length_mus(val)
            self._segment_end_offset_mus = util.check_range(util.check_type(val, 'segment_end_offset_mus', Number), 'segment_end_offset_mus', 0, __MAX_LENGTH_SMPL__ / __SAMPLE_FREQUENCY__)
            self._segment_end_offset = length_mus2length_smpl(self._segment_end_offset_mus)

    @segment_end_offset.setter
    def segment_end_offset(self, val):
        if val is not None:
            if val == 2 ** 32 - 1:
                self._segment_end_offset_mus = np.inf
                self._segment_end_offset = val
            else:
                self._segment_end_offset_mus = util.check_range(util.check_type(val, 'segment_end_offset_mus', Number), 'segment_end_offset_mus', 0, __MAX_LENGTH_SMPL__) / __SAMPLE_FREQUENCY__
                self._segment_end_offset = length_mus2length_smpl(self._segment_end_offset_mus)


class SequenceStepReuseSegment(BaseSequenceStep):
    def __init__(self, reused_sequence_step=None, **kwargs):
        super(SequenceStepReuseSegment, self).__init__(**kwargs)
        if reused_sequence_step is not None:
            self.reused_sequence_step = reused_sequence_step
        else:
            raise Exception('Error!')
        self.write_sequence_memory = True

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except:
            return self.reused_sequence_step.__getattribute__(name)


class SequenceStep(BaseDataList, BaseSequenceStep):

    # def __init__(self, **kwargs):
    #     super(SequenceStep, self).__init__(**kwargs)

    __DATA_LIST_ITEM_TYPE__ = WaveStep

    @property
    def segment_size_bytes(self):
        return 2 * self.length_smpl

    def segment_block_data(self, coherent_offset):
        return self.samples_waveform(coherent_offset)

    @property
    def wavestep_list(self):
        return list(itertools.chain(*itertools.repeat(self.data_list, self.loop_count)))

    @property
    def segment_id(self):
        return self._segment_id

    def precompile_samples_waveform(self, coherent_offset, start=0, samples=None, notify=True):
        t0 = time.time()
        self._samples_waveform = self.samples_waveform(coherent_offset, start=0, samples=None)

        def samples_waveform(self, *args, **kwargs):
            return self._samples_waveform

        self.samples_waveform = types.MethodType(samples_waveform, self)
        if notify:
            logging.getLogger().debug("type {} {} precompiled ({} s).".format(self.name, type(self), time.time() - t0))

    def set_write_awg(self, **kwargs):
        self.write_segment_memory = True


class Sequence(BaseWave, BaseLoopAdvance, BaseDataList):
    def __init__(self, name, advance_mode='COND', **kwargs):
        super(Sequence, self).__init__(name=name, advance_mode=advance_mode, **kwargs)
        self.date = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    __DATA_LIST_ITEM_TYPE__ = BaseSequenceStep

    date = util.ret_property_typecheck('date', str)

    @property
    def missing_smpl(self):
        return self.data_list.missing_smpl

    @property
    def wavestep_list(self):
        return list(itertools.chain(*[step.wavestep_list for step in self.data_list]))

    @property
    def step_list(self):
        step_list = []
        for seq_step in self.data_list:
            step_list.append(seq_step)
            step_list += seq_step.data_list
        return step_list

    def precompile_samples_waveform(self, coherent_offset, start=0, samples=None, notify=True):
        t0 = time.time()
        idx = start
        for i, step in enumerate(self.data_list):
            if isinstance(step, SequenceStepReuseSegment):
                continue
            step.precompile_samples_waveform(coherent_offset + idx, start=idx, samples=samples)  # , loop_count #samples[: idx + rls] =
            idx += step.length_smpl * step.loop_count
        if notify:
            logging.getLogger().debug("type {} {} precompiled ({} s).".format(self.name, type(self), time.time() - t0))

    @BaseLoopAdvance.loop_count.setter
    def loop_count(self, val):
        BaseLoopAdvance.loop_count.fset(self, val)
        if hasattr(self, '_data_list') and len(self.data_list) > 0:
            self.data_list[0].write_sequence_memory = True

    @BaseLoopAdvance.advance_mode.setter
    def advance_mode(self, val):
        BaseLoopAdvance.advance_mode.fset(self, val)
        if hasattr(self, '_data_list') and len(self.data_list) > 0:
            self.data_list[0].write_sequence_memory = True

    def sequence_table_data_block(self, segment_ids, sequence_id_offset=0):
        if self.number_of_steps != len(segment_ids):
            raise Exception('What happened?')

        nbytes = bytes(24 * self.number_of_steps)
        bytes_length = str(len(nbytes))
        cmd = bytes('{},{}'.format(sequence_id_offset, '#' + bytes_length + nbytes))
        seq_loop_count = struct.pack('I', self.loop_count)
        advance_map = {'AUTO': 0, 'COND': 1, 'REP': 2, 'SING': 3}
        for i, step in enumerate(self.data_list):
            control = 0
            # init and end sequence markers
            if i == 0:
                control += 2 ** 28
            if i == self.number_of_steps - 1:
                control += 2 ** 30
            # marker enable:
            control += step.marker_enable * 2 ** 24
            # sequence advance
            control += advance_map[self.advance_mode] * 2 ** 20
            # wave advance
            control += advance_map[step.advance_mode] * 2 ** 16
            control = struct.pack('I', control)
            wave_id = struct.pack('I', segment_ids[i])
            wave_lc = struct.pack('I', step.loop_count)
            wave_start_offset = struct.pack('I', step.segment_start_offset)
            wave_end_offset = struct.pack('I', step.segment_end_offset)
            data = (control + seq_loop_count + wave_lc
                    + wave_id + wave_start_offset + wave_end_offset)
            cmd += data
            step._sequence_id = sequence_id_offset + i
        return cmd

    def dl(self, sequence_step_num, wave_step_num=None):
        if wave_step_num is None:
            return self.data_list[sequence_step_num]
        else:
            return self.data_list[sequence_step_num].data_list[wave_step_num]

    def set_write_awg(self, idx=None, val=None, action=None):
        if idx == 0:  # the first step in a sequence must be marked
            val.write_sequence_memory = True
            if action == 'insert' and hasattr(self, '_data_list') and len(self.data_list) > 1:  # the now second step no more is start of the sequence and must be unmarked
                self.data_list[1].write_sequence_memory = True