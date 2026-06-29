import unittest
from unittest.mock import patch, MagicMock

class TestBase(unittest.TestCase):

    @patch('app.services.extractors.base')
    def test_example(self, mock_base):
        mock_base.SomeFunction = MagicMock(return_value='mocked value')
        result = mock_base.SomeFunction()
        self.assertEqual(result, 'mocked value')

if __name__ == '__main__':
    unittest.main()
