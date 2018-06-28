from setuptools import setup

setup(name='pym8190a',
      version='1.0',
      description='Sequence creation and driver HAL for the Keysight M8190A Arbitrary Waveform Generator',
      url='http://github.com/szaiser/pym8190a',
      author='Sebastian Zaiser',
      author_email='s.zaiser@gmail.com',
      license='GNU General Public License v3.0',
      packages=['pym8190a'],
      install_requires=[
          'pyvisa',
          'numpy',
      ],
      zip_safe=False)
