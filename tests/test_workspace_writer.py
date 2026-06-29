import unittest
from app.services.workspace_writer import WorkspaceWriterService

class TestWorkspaceWriterService(unittest.TestCase):

    def setUp(self):
        self.service = WorkspaceWriterService()

    def test_is_test_file(self):
        # Directly test the _is_test_file method with a valid test file
        result = self.service._is_test_file('tests/example_file.py')
        self.assertTrue(result)
        result2 = self.service._is_test_file('some/other/file.py')
        self.assertFalse(result2)

if __name__ == '__main__':
    unittest.main()