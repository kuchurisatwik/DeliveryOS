import unittest
from unittest.mock import patch, MagicMock


class TestKnowledge(unittest.TestCase):
    @patch('app.schemas.knowledge')
    def test_some_knowledge_feature(self, mock_knowledge):
        mock_knowledge.SomeClass = MagicMock(return_value='mocked')
        instance = mock_knowledge.SomeClass()
        self.assertEqual(instance.method(), 'mocked')


class TestAnotherFeature(unittest.TestCase):
    @patch('app.schemas.knowledge')
    def test_another_feature(self, mock_knowledge):
        mock_knowledge.AnotherClass = MagicMock()
        instance = mock_knowledge.AnotherClass()
        instance.method = MagicMock(return_value='mocked again')
        self.assertEqual(instance.method(), 'mocked again')


if __name__ == '__main__':
    unittest.main()