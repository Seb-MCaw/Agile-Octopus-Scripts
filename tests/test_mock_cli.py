import unittest

import tests.mock_cli


class TestMockCLI(unittest.TestCase):
	def test_MockCli(self):
		mock_cli = tests.mock_cli.MockCLI(
			self,
			[
				"print 1\ninput prompt 1: ",
				"print 2\nprint 3\ninput prompt 2: ",
				"print 4\n"
			],
			["input 1", "input 2"]
		)
		with mock_cli:
			print("print 1")
			self.assertEqual(input("input prompt 1: "), "input 1")
			print("print 2")
			print("print 3")
			self.assertEqual(input("input prompt 2: "), "input 2")
			print("print 4")
