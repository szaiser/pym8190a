"""Basic import tests for pym8190a package"""
import pytest


def _can_import_visa():
    """Check if pyvisa is available"""
    try:
        import visa
        return True
    except ImportError:
        return False


class TestImports:
    """Tests to verify package structure and imports"""

    def test_import_elements(self):
        """Test that elements module can be imported"""
        from pym8190a import elements
        assert elements is not None

    def test_import_util(self):
        """Test that util module can be imported"""
        from pym8190a import util
        assert util is not None

    def test_import_settings(self):
        """Test that settings module can be imported"""
        from pym8190a import settings
        assert settings is not None

    @pytest.mark.skipif(
        not _can_import_visa(),
        reason="pyvisa not available (expected in test environment without hardware)"
    )
    def test_import_hardware_module(self):
        """Test that hardware module exists (but don't instantiate without real hardware)"""
        from pym8190a import hardware
        assert hardware is not None
        # Verify key classes exist but don't instantiate
        assert hasattr(hardware, 'SequencerTable')

    @pytest.mark.skipif(
        not _can_import_visa(),
        reason="pyvisa not available (expected in test environment without hardware)"
    )
    def test_import_pym8190a_module(self):
        """Test that pym8190a main module can be imported"""
        from pym8190a import pym8190a
        assert pym8190a is not None
        # Verify MultiChSeqDict exists but don't instantiate (needs real hardware)
        assert hasattr(pym8190a, 'MultiChSeqDict')

    def test_sample_frequency_constant(self):
        """Test that sample frequency constant is accessible"""
        from pym8190a.elements import __SAMPLE_FREQUENCY__
        assert __SAMPLE_FREQUENCY__ > 0

    def test_amplitude_granularity_constant(self):
        """Test that amplitude granularity constant is accessible"""
        from pym8190a.elements import __AMPLITUDE_GRANULARITY__
        assert __AMPLITUDE_GRANULARITY__ > 0

    def test_advance_mode_map_constant(self):
        """Test that advance mode map is accessible"""
        from pym8190a.elements import __ADVANCE_MODE_MAP__
        assert isinstance(__ADVANCE_MODE_MAP__, dict)
        assert 'AUTO' in __ADVANCE_MODE_MAP__


class TestPackageVersion:
    """Tests for package metadata"""

    def test_package_has_init(self):
        """Test that package has __init__.py"""
        import pym8190a
        assert hasattr(pym8190a, '__file__')

    def test_numpy_available(self):
        """Test that numpy dependency is available"""
        import numpy as np
        assert np is not None

    def test_numpy_version(self):
        """Test numpy version can be accessed"""
        import numpy as np
        assert hasattr(np, '__version__')
