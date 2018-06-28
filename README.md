# pym8190a

pym8190a is a python package providing fast and convenient sequence creation on Keysight M8190A Arbitrary Waveform Generators (AWG). Synchronization of multiple channels is provided by design and is ensured with minimum user interaction and thus maximum error-proneness. 

## Features

* Convenient sequence creation with multiple AWG M8190A and multiple channels
* Synchronization of separate channels 
* Timebase can either be given in samples (1 sample = 1/12e3 µs) or in µs.
* Automatically fills up segments which do not fulfill the requirement for a length of  320 + 64*n samples with zeros.
* Optimized for high writing speed
* Multiple sequences can be written into the AWG memory and remain there for immediate access until the user instructs their deletion to free the memory.
* Set limitations on the average power of sine-like signals output by the AWG, i.e. setting an upper bound on the duty cycle for each channel individually.


## Missing Features

* Support for Scenarios

## Prerequisites

### Software 

* numpy (>= 1.12) 
* pyvisa (>= 1.5)
* [M8190A 12 GSa/s Arbitrary Waveform Generator Instrument Drivers](https://www.keysight.com/main/software.jspx?ckey=2759704)

### Hardware

When multiple AWGs work together, two options for synchronization are available

* One of the sync marker outputs needs to be connected to the other AWGs trigger inputs
* If available, use the Keysight M8192A Synchronization Module 

## Installing

git clone https://github.com/szaiser/pym8190a.git
cd pym8190a
python setup.py install

## Configuration

pym8190a.py is the main-file and -for now- also is the place for user specific settings. For historical reasons, the default values are '2g' for one AWG and '128m' for another one with two channels each.

### Essential settings

##### `__AWG_INSTRUMENT_ADDRESS__`

This adress is given in the instrument driver instance of the AWG.

##### `__CH_DICT_FULL__`

Channels are specified for each AWG according to naming convention in AWG manual, i.e. the channel count starts at 1 (unlike pythons convention where counting starts at 0)

##### `__MASTER_AWG__` and `__MASTER_TRIGGER_CHANNEL__`

When multiple AWGs need to work together, the syncmarker of channel `__MASTER_TRIGGER_CHANNEL__` of the master AWG `__MASTER_AWG__` awg gives the trigger for the slave AWGs.  

### Optional settings

##### `__MARKER_ALIAS__`

For convenience, the markers can be given special names, e.g. samplemarker of channel 2 of AWG '2g' is given the alias 'green' via `{'green': ['2g', 2, 'smpl']`

##### `__MAX_SINE_AVG_POWER__` and `__AMPLIFIER_POWER__`

Only necessary, when duty cycle limiting is used. The `__AMPLIFIER_POWER__` gives the maximum power of the amplifier connected to the channel, while the `__MAX_SINE_AVG_POWER__` gives the maximum average power. For higher average powers, waiting times are appended to the sequence.

## Usage

First of all, a dictionary-like object is created, into which all sequences are written.

```import pym8190a
md = pym8190a.MultiChSeqDict()
```

### Sequence creation

First of all, the sequence must be created. It needs to be given a name, and if not all channels from `__CH_DICT_FULL` are supposed to be used (and written to, which costs time), ch_dict gives the channels required for the sequence.

`s = MCAS.MultiChSeq(name='sequence_name, ch_dict={'2g': [2]})`

### Adding a segment to the sequence

A new segment needs to be appended to the sequence, which later will be written to the AWG memory and when sequencing is used, also represent one step in the sequencer memory. The loop_count specifies, how often the segment is repeated in the sequence, before the next segment is played.

's.start_new_segment('segment_name', loop_count=100)' 

### Adding a segment step to the last added segment.

* The name of the newly added segment step is 'segment_step0' and its duration is 123 samples, i.e. 0.01025µs. As this does not fulfill the requirement for a sample to have a duration of 320 + 64*n samples, pym8190a automatically adds 197 samples to the segment.
* The samplemarker of the segment will be on for the duration of 'segment_step0' (123 samples), but not during the automatically added samples at the end of the segment (the other 197 samples).

' add_step_complete(name='segment_step0', length_mus=123/12e3, smpl_marker=True)' 

## Authors

* **Sebastian Zaiser**

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details
