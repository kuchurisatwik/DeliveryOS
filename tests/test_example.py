import pytest
from deliveryos import some_function

@pytest.fixture
def sample_data():
    return [1, 2, 3, 4, 5]


def test_some_function_with_data(sample_data):
    result = some_function(sample_data)
    expected_result = 15  # Assuming the function sums the numbers
    assert result == expected_result, f'Expected {expected_result}, but got {result}'


def test_some_function_empty():
    result = some_function([])
    expected_result = 0  # Assuming the function returns 0 for an empty input
    assert result == expected_result, f'Expected {expected_result}, but got {result}'


def test_some_function_with_negative(sample_data):
    sample_data.append(-1)
    result = some_function(sample_data)
    expected_result = 14  # Adjusted expected result with negative value included
    assert result == expected_result, f'Expected {expected_result}, but got {result}'
