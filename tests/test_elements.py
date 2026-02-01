"""Tests for elements module"""
import pytest
import numpy as np
from pym8190a.elements import (
    round_length_mus_full_sample,
    valid_length_mus,
    valid_length_smpl,
    length_mus2length_smpl,
    length_smpl2length_mus,
    round_to_amplitude_granularity,
    __SAMPLE_FREQUENCY__,
    __AMPLITUDE_GRANULARITY__,
    list_repeat
)


class TestRoundLengthMusFullSample:
    """Tests for round_length_mus_full_sample function"""

    def test_already_rounded_value(self):
        """Test with value that's already a full sample"""
        length_mus = 1.0 / __SAMPLE_FREQUENCY__
        result = round_length_mus_full_sample(length_mus)
        assert result == length_mus

    def test_rounded_value(self):
        """Test with value that needs rounding"""
        length_mus = 1.5 / __SAMPLE_FREQUENCY__
        result = round_length_mus_full_sample(length_mus)
        expected = 2.0 / __SAMPLE_FREQUENCY__
        assert np.isclose(result, expected)

    def test_array_input(self):
        """Test with numpy array input"""
        length_mus = np.array([1.0, 2.0, 3.0]) / __SAMPLE_FREQUENCY__
        result = round_length_mus_full_sample(length_mus)
        np.testing.assert_array_almost_equal(result, length_mus)


class TestValidLengthMus:
    """Tests for valid_length_mus function"""

    def test_valid_length(self):
        """Test with valid length in microseconds"""
        length_mus = 1.0 / __SAMPLE_FREQUENCY__
        # Should not raise exception
        valid_length_mus(length_mus)

    def test_invalid_length(self):
        """Test with invalid length (not full sample)"""
        length_mus = 0.5 / __SAMPLE_FREQUENCY__ + 1e-5  # Slightly off
        with pytest.raises(Exception) as excinfo:
            valid_length_mus(length_mus)
        assert "is not valid for the current sample_frequency" in str(excinfo.value)


class TestValidLengthSmpl:
    """Tests for valid_length_smpl function"""

    def test_integer_length(self):
        """Test with integer sample length"""
        # Should not raise exception
        valid_length_smpl(10.0)

    def test_non_integer_length(self):
        """Test with non-integer sample length"""
        with pytest.raises(Exception) as excinfo:
            valid_length_smpl(10.5)
        assert "is not valid" in str(excinfo.value)


class TestLengthConversions:
    """Tests for length conversion functions"""

    def test_mus_to_smpl_conversion(self):
        """Test microsecond to sample conversion"""
        length_mus = 10.0 / __SAMPLE_FREQUENCY__
        result = length_mus2length_smpl(length_mus)
        assert result == 10

    def test_smpl_to_mus_conversion(self):
        """Test sample to microsecond conversion"""
        length_smpl = 10.0
        result = length_smpl2length_mus(length_smpl)
        expected = 10.0 / __SAMPLE_FREQUENCY__
        assert result == expected

    def test_round_trip_conversion(self):
        """Test conversion from mus to smpl and back"""
        length_mus = 100.0 / __SAMPLE_FREQUENCY__
        length_smpl = length_mus2length_smpl(length_mus)
        result = length_smpl2length_mus(length_smpl)
        assert np.isclose(result, length_mus)


class TestRoundToAmplitudeGranularity:
    """Tests for round_to_amplitude_granularity function"""

    def test_exact_granularity(self):
        """Test with value at exact granularity"""
        amplitude = __AMPLITUDE_GRANULARITY__
        result = round_to_amplitude_granularity(amplitude)
        assert result == amplitude

    def test_rounded_amplitude(self):
        """Test with value that needs rounding"""
        amplitude = 1.5 * __AMPLITUDE_GRANULARITY__
        result = round_to_amplitude_granularity(amplitude)
        expected = 2.0 * __AMPLITUDE_GRANULARITY__
        assert np.isclose(result, expected)

    def test_array_input(self):
        """Test with array input"""
        amplitudes = np.array([0.1, 0.2, 0.3])
        result = round_to_amplitude_granularity(amplitudes)
        assert len(result) == len(amplitudes)

    def test_negative_amplitude(self):
        """Test with negative amplitude"""
        amplitude = -0.5
        result = round_to_amplitude_granularity(amplitude)
        # Check that rounding works for negative values
        assert result <= 0


class TestListRepeat:
    """Tests for list_repeat class"""

    def test_normal_access(self):
        """Test normal list access"""
        lr = list_repeat([1, 2, 3])
        assert lr[0] == 1
        assert lr[1] == 2
        assert lr[2] == 3

    def test_out_of_bounds_single_element(self):
        """Test out of bounds access with single element"""
        lr = list_repeat([42])
        assert lr[0] == 42
        assert lr[5] == 42  # Should return the first element
        assert lr[100] == 42  # Should return the first element

    def test_out_of_bounds_multiple_elements(self):
        """Test out of bounds with multiple elements (should raise)"""
        lr = list_repeat([1, 2, 3])
        # Access beyond bounds should fall back to first element or raise
        with pytest.raises((IndexError, Exception)):
            _ = lr[10]

    def test_append(self):
        """Test appending to list_repeat"""
        lr = list_repeat([1])
        lr.append(2)
        assert lr[0] == 1
        assert lr[1] == 2


class TestConstants:
    """Tests to verify important constants"""

    def test_sample_frequency_is_positive(self):
        """Test that sample frequency is positive"""
        assert __SAMPLE_FREQUENCY__ > 0

    def test_amplitude_granularity_is_positive(self):
        """Test that amplitude granularity is positive"""
        assert __AMPLITUDE_GRANULARITY__ > 0

    def test_amplitude_granularity_is_small(self):
        """Test that amplitude granularity is reasonable"""
        assert __AMPLITUDE_GRANULARITY__ < 1.0
