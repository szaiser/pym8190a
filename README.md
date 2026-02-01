# pym8190a

[![Python application](https://github.com/szaiser/pym8190a/actions/workflows/python-app.yml/badge.svg)](https://github.com/szaiser/pym8190a/actions/workflows/python-app.yml)
[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/szaiser/pym8190a)](LICENSE)

pym8190a is a python package providing fast and convenient sequence creation on Keysight M8190A Arbitrary Waveform Generators (AWG). Synchronization of multiple channels is provided by design. 

## Features

* Convenient sequence creation with multiple AWG M8190A and multiple channels
* Synchronization of separate channels 
* Optimized for high writing speed
* Multiple sequences can be written into the AWG memory and remain there for immediate access until the user instructs their deletion to free the memory.
* View details of your created sequence via built-in print-to-console funcionality.
* Set limitations on the average power of sine-like signals output by the AWG, i.e. setting an upper bound on the duty cycle for each channel individually.
* All durations can either be given in samples (`length_smpl` or in µs (`length_mus`).
* Automatically fills up segments which do not fulfill the requirement for a length of  320 + 64*n samples with zeros.

## Missing Features

* Full Software Documentation
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
```
git clone https://github.com/szaiser/pym8190a.git
cd pym8190a
python setup.py install
```

## Configuration

All user specific settings can be found in settings.py. The present settings are a tested working example.

### Essential settings

##### `settings_folder` and `restore_awg_settings`
The settings folder is used for storage and loading of awg settings (command `:SYST:SET[?]`, see user manual). For each AWG device a separate configuration file is loaded and must be present in `settings_folder`. Two exemplary settings files for two AWGs '2g' and '128m' are stored in the default folder /.hardware_settings. For generation of settings files see below.  
The boolean variable `restore_awg_settings` determines, if settings from `settings_folder` are loaded. Set to False, if no settings files were generated.

##### `ch_dict_full`

Channels are specified for each AWG according to naming convention in AWG manual, i.e. the channel count starts at 1 (unlike pythons convention where counting starts at 0). 

##### `awg_instrument_adress`

This adress is given in the instrument driver instance of each of your AWGs.

### Settings for multiple, connected AWGs

##### `master_awg` and `master_trigger_channel`

There always exists one master AWG which triggers n=0..N slave AWGs. If n=0, you do not need these settings. The syncmarker of channel `master_trigger_channel` of the master AWG `master_awg` gives the trigger for the slave AWGs.  

### Optional settings

##### `marker_alias`

For convenience, the markers can be given special names, e.g. samplemarker of channel 2 of AWG '2g' is given the alias 'green' via `{'green': ['2g', 2, 'smpl']`

##### `max_sine_avg_power` and `amplifier_power`

Only necessary, when the duty cycle limiting feature is used. The `amplifier_power` gives the maximum power of the amplifier connected to the channel, while the `max_sine_avg_power` gives the maximum allowed average power. When the average sine wave power is higher than this value, waiting times are appended to the sequence to limit the average power.

## Basic usage

The package is imported via 

`>>> import pym8190a`

As a basic example, write a basic, two segment long sequence. The necessary steps are:

* create an empty sequence with name `sequence0`
* append the first segment and fill it with data. This first segment consists of one user generated step and is supposed to turn sample marker on.
* append the second segment and fill it with data. The second segment will consist of one user generated step and addresses two separate channels. This second segments plays actual arbiatrary waveform data.
* create an instance `md` of MultiChSeqDict
* store our sequence in `md`
* start `sequence0`

The full example is found after a step by step description.

### Create empty sequence  sequence0


Every sequence is an instance of `pym8190a.MultiChSeq` and has `name`as required argument. In the example, it is assumed, that `ch_dict_full = {'2g': [1, 2], '128m': [1, 2]}` but that AWG '128m' is not for the sequence. The channels required for the sequence can be specified by `ch_dict_full`. All channels given in `ch_dict` must also be present in `settings.ch_dict_full`. Using only a subset of the available channels reduces the time needed for sequence compiliation and writing into the AWG memory.

```
>>> s = pym8190a.MultiChSeq(name='sequence0', ch_dict={'2g': [1, 2]})
```

#### Add an empty segment to the sequence

To add an empty sequence, use method `start_new_segment`. A segment name (`basic_segment`) must be specified. The new segment, which later will be written to the AWG memory and, when sequencing is used, also represents one step in the sequencer memory. The parameter `loop_count` specifies, how often the segment is repeated in the sequence, before the next segment is played. 

```
>>>  s.start_new_segment('basic_segment', loop_count=5)
```

Note: This segment so far is empty, but segments can only be written with a waveform granularity of 320 + 64*n samples (see AWG manual). To fulfill this requirement, pym8190a writes 320 zero-valued samples to the segment. 

#### Fill the segment with data

* The segment `basic_segment`so far has no functionality. Hence, a wave_step is added to the segment, which is given the name 'segment_step0'. Its duration is 123 samples, at a sampling freuquency of 12Gs/s this corresponds to 0.01025µs. This duration again does not fulfill the requirement for the waveform granularity. To have a duration of 320 + 64*n samples, the software pym8190a adds 197 zero-valued samples to the segment.
* For the duration of segment 'segment_step0' (123 samples) the sample_marker of AWG '2g', channel 2 shall be set to On. Conveniently, in `pym8190a.settings`, we set the marker_alias `'memory': ['2g', 1, 'smpl']` and hence only have to type `memory=True`.  

`>>> s.add_step_complete(name='segment_step0', length_mus=123/12e3, memory=True)`

#### Add a second empty segment to the sequence

`>>>  s.start_new_segment('advanced_segment')`

Note: The segment `advanced_segment` is looped only once, hence the parameter `loop_count` does not need to be set.

#### Sine wave creation

This more advanced segment sets the sample marker of channel 1 of AWG '2g' and on channel 2 it outputs the superposition of two sine waves. The frequencies of the sines will be 1 MHz and 2 MHz, their amplitudes will be 0.1 and 0.2 and their phases 30° and 90°. The step has a duration of 9.6µs, which corresponds to `length_smpl=320+1795*64`. Consequentially, no empty samples have to be appended to the segment. 

```
pd2g1 = dict(smpl_marker=True)
pd2g2 = dict(type='sine', frequencies=[1.0, 2.0], amplitudes=[0.1, 0.2], phases=[30, 90])
s.add_step_complete(name='segment_step0', length_mus=9.6, pd2g1=pd2g1, pd2g2=pd2g2)
```

#### Writing to and deleting from AWG memory

A special dictionary-like object, the sequence dictionary, keeps track of all AWG sequences which are written onto the AWG memory. Adding a sequence to the sequence dictionary will write it to the AWG memory, deleting it from the dictionary will also delete it from the AWG memory and additionally cause a a defragmentation of the AWG memory. Defragmentation in this context means, that all sequences written to the AWG memory are written in consecutive parts of the memory, gaps are filled.

```
>>> md = pym8190a.MultiChSeqDict()
>>> md['sequence0'] = s
```

To delete the sequence from the AWG memory it has to be removed from the dictionary.

```
>>> del md['sequence0']
``` 

### Running and stopping a sequence

A sequence can be started via 

````
>>> md['sequence0'].run()
````

The sequence can be stopped via

````
>>> md.stop_awgs()
````

### Full example 

````
import pym8190a
s = pym8190a.MultiChSeq(name='sequence0', ch_dict={'2g': [1, 2]})
s.start_new_segment('basic_segment', loop_count=5)
s.add_step_complete(name='segment_step0', length_mus=123/12e3, memory=True)
s.start_new_segment('advanced_segment')
pd2g1 = dict(smpl_marker=True)
pd2g2 = dict(type='sine', frequencies=[1.0, 2.0], amplitudes=[0.1, 0.2], phases=[30, 90])
s.add_step_complete(name='segment_step0', length_mus=9.6, pd2g1=pd2g1, pd2g2=pd2g2)
md = pym8190a.MultiChSeqDict()
md['sequence0'] = s
md['sequence0'].run()
````

### Access a sequence and print its details to the console

The sequence can be accessed from the sequence dictionary

```
>>> s = md['sequence_0']
```

Information about the sequence can be printed for each channel individually, when the name of the AWG and the channel number are given:

Channel 1:
```
>>> s.dl('2g', 1).print_info()
0     sequence0         9.733333  1       
   0     basic_segment     0.133333  5       
      0     segment_step0     0.010250  wait    1       0       
      1     _missing_smpls_   0.016417  wait    0       0       
   1     advanced_segment  9.600000  1       
      0     segment_step0     9.600000  wait    1       0       
      1     _missing_smpls_   0.000000  wait    0       0        
```
Channel 2:
```
>>> s.dl('2g', 2).print_info()
0     sequence0         9.733333  1       
   0     basic_segment     0.133333  5       
      0     segment_step0     0.010250  wait    0       0       
      1     _missing_smpls_   0.016417  wait    0       0       
   1     advanced_segment  9.600000  1       
      0     segment_step0     9.600000  sine    [ 1.  2.][ 0.1  0.2][ 30.  90.]0       0       
      1     _missing_smpls_   0.000000  wait    0       0           
```

In a similar way, for very long sequences it can be convenient to access information about individual segments or steps, which can be printed to console via


Single segment: 
```
>>> s.dl('2g', 2, 1).print_info() 
0     advanced_segment  9.600000  1       
   0     segment_step0     9.600000  sine    [ 1.  2.][ 0.1  0.2][ 30.  90.]0       0       
   1     _missing_smpls_   0.000000  wait    0       0     
```

Single step of a segment:


````
>>> s.dl('2g', 2, 1, 0).print_info()
 0     segment_step0     9.600000  sine    [ 1.  2.][ 0.1  0.2][ 30.  90.]0       0  
````

## Accessing the awg hardware and writing settings files

Given an instance `md` of class pym8190a.MultiChSeqDict, the hardware class of an AWG can be accessed by its name `awg_name` via `md.awgs[awg_name]`. To dump the current AWG settings of an AWG with `awg_name` '2g' to a file, use command

````
>>> md.awgs['2g'].dump_current_settings_to_file()
````

The file is stored with current date and time in the settings folder given by pym8190a.settings.settings_folder.

## Authors

* **Sebastian Zaiser**

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details
