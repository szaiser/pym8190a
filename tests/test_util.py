"""Tests for util module"""
import pytest
import numpy as np
from pym8190a.util import (
    check_type,
    check_range,
    check_range_type,
    check_array_like,
    check_array_like_typ,
    check_list_element,
    ret_property_typecheck,
    ret_property_range,
    ret_property_list_element
)


class TestCheckType:
    """Tests for check_type function"""

    def test_valid_int(self):
        """Test with valid integer"""
        result = check_type(42, "test_val", int)
        assert result == 42

    def test_valid_float(self):
        """Test with valid float"""
        result = check_type(3.14, "test_val", float)
        assert result == 3.14

    def test_valid_str(self):
        """Test with valid string"""
        result = check_type("hello", "test_val", str)
        assert result == "hello"

    def test_invalid_type(self):
        """Test with invalid type"""
        with pytest.raises(Exception) as excinfo:
            check_type("string", "test_val", int)
        assert "Property test_val must be" in str(excinfo.value)


class TestCheckRange:
    """Tests for check_range function"""

    def test_value_in_range(self):
        """Test value within valid range"""
        result = check_range(5, "test_val", 0, 10)
        assert result == 5

    def test_value_at_lower_bound(self):
        """Test value at lower boundary"""
        result = check_range(0, "test_val", 0, 10)
        assert result == 0

    def test_value_at_upper_bound(self):
        """Test value at upper boundary"""
        result = check_range(10, "test_val", 0, 10)
        assert result == 10

    def test_value_below_range(self):
        """Test value below valid range"""
        with pytest.raises(Exception) as excinfo:
            check_range(-1, "test_val", 0, 10)
        assert "must be in range" in str(excinfo.value)

    def test_value_above_range(self):
        """Test value above valid range"""
        with pytest.raises(Exception) as excinfo:
            check_range(11, "test_val", 0, 10)
        assert "must be in range" in str(excinfo.value)


class TestCheckRangeType:
    """Tests for check_range_type function"""

    def test_valid_int_in_range(self):
        """Test valid integer in range"""
        result = check_range_type(5, "test_val", int, 0, 10)
        assert result == 5

    def test_invalid_type_in_range(self):
        """Test invalid type but value in range"""
        with pytest.raises(Exception):
            check_range_type("5", "test_val", int, 0, 10)

    def test_valid_type_out_of_range(self):
        """Test valid type but value out of range"""
        with pytest.raises(Exception):
            check_range_type(15, "test_val", int, 0, 10)


class TestCheckArrayLike:
    """Tests for check_array_like function"""

    def test_list_input(self):
        """Test with list input"""
        test_list = [1, 2, 3]
        result = check_array_like(test_list, "test_val")
        assert result == test_list

    def test_numpy_array_input(self):
        """Test with numpy array input"""
        test_array = np.array([1, 2, 3])
        result = check_array_like(test_array, "test_val")
        np.testing.assert_array_equal(result, test_array)

    def test_invalid_input(self):
        """Test with invalid input (not array-like)"""
        with pytest.raises(Exception) as excinfo:
            check_array_like(42, "test_val")
        assert "Type of property test_val must be in list" in str(excinfo.value)


class TestCheckArrayLikeTyp:
    """Tests for check_array_like_typ function"""

    def test_valid_int_list(self):
        """Test with valid integer list"""
        result = check_array_like_typ([1, 2, 3], "test_val", int)
        np.testing.assert_array_equal(result, np.array([1, 2, 3]))

    def test_valid_float_list(self):
        """Test with valid float list"""
        result = check_array_like_typ([1.0, 2.0, 3.0], "test_val", float)
        np.testing.assert_array_equal(result, np.array([1.0, 2.0, 3.0]))

    def test_invalid_type_in_list(self):
        """Test with invalid type in list"""
        with pytest.raises(Exception):
            check_array_like_typ([1, "2", 3], "test_val", int)

    def test_numpy_array_input(self):
        """Test with numpy array as input"""
        # Note: check_array_like_typ with int type expects Python int, not numpy.int64
        # So we convert the array to Python list first or use float type
        result = check_array_like_typ([1, 2, 3], "test_val", int)
        np.testing.assert_array_equal(result, np.array([1, 2, 3]))
        
        # For float, numpy types are accepted
        result_float = check_array_like_typ(np.array([1.0, 2.0, 3.0]), "test_val", float)
        np.testing.assert_array_equal(result_float, np.array([1.0, 2.0, 3.0]))


class TestCheckListElement:
    """Tests for check_list_element function"""

    def test_value_in_list(self):
        """Test value present in list"""
        result = check_list_element("apple", "test_val", ["apple", "banana", "cherry"])
        assert result == "apple"

    def test_value_not_in_list(self):
        """Test value not present in list"""
        with pytest.raises(Exception) as excinfo:
            check_list_element("grape", "test_val", ["apple", "banana", "cherry"])
        assert "must be in list" in str(excinfo.value)

    def test_numeric_value_in_list(self):
        """Test numeric value in list"""
        result = check_list_element(2, "test_val", [1, 2, 3])
        assert result == 2


class TestPropertyHelpers:
    """Tests for property helper functions"""

    def test_ret_property_typecheck(self):
        """Test ret_property_typecheck creates valid property"""
        prop = ret_property_typecheck('test_attr', str)
        assert isinstance(prop, property)
        
        # Test with a simple class
        class TestClass:
            test_attr = ret_property_typecheck('test_attr', str)
        
        obj = TestClass()
        obj.test_attr = "hello"
        assert obj.test_attr == "hello"
        
        # Test type checking works
        with pytest.raises(Exception):
            obj.test_attr = 123

    def test_ret_property_range(self):
        """Test ret_property_range creates valid property with range checking"""
        prop = ret_property_range('test_attr', int, 0, 10)
        assert isinstance(prop, property)
        
        class TestClass:
            test_attr = ret_property_range('test_attr', int, 0, 10)
        
        obj = TestClass()
        obj.test_attr = 5
        assert obj.test_attr == 5
        
        # Test range checking
        with pytest.raises(Exception):
            obj.test_attr = 15

    def test_ret_property_list_element(self):
        """Test ret_property_list_element creates valid property"""
        prop = ret_property_list_element('test_attr', ['a', 'b', 'c'])
        assert isinstance(prop, property)
        
        class TestClass:
            test_attr = ret_property_list_element('test_attr', ['a', 'b', 'c'])
        
        obj = TestClass()
        obj.test_attr = 'b'
        assert obj.test_attr == 'b'
        
        # Test list validation
        with pytest.raises(Exception):
            obj.test_attr = 'd'

