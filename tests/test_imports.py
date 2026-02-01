"""Basic import tests for pym8190a package"""
import pytest


class TestImports:
    """Tests to verify package structure and imports"""

    def test_import_main_package(self):
        """Test that main package can be imported"""
        import pym8190a
        assert pym8190a is not None

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

    def test_sample_frequency_constant(self):
        """Test that sample frequency constant is accessible"""
        from pym8190a.elements import __SAMPLE_FREQUENCY__
        assert __SAMPLE_FREQUENCY__ > 0

    def test_amplitude_granularity_constant(self):
        """Test that amplitude granularity constant is accessible"""
        from pym8190a.elements import __AMPLITUDE_GRANULARITY__
        assert __AMPLITUDE_GRANULARITY__ > 0


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
