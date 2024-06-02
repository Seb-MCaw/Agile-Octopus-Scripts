import io
import unittest.mock


class MockCLI:
	"""
	A MockCLI is a context manager which mocks a command line session

	It patches sys.stdout() and builtins.input() to test an alternating
	cycle of prompts and inputs, failing its parent unittest.TestCase if
	the output is unexpected.

	The expected behaviour is specified by the prompts and inputs iterables:
	prompts[0] should be written to stdout, then inputs[0] will be returned
	by input(); this repeats with prompts[1] and inputs[1] etc.

	prompts should be one element longer than inputs to specify what is
	written to stdout after the final input.
	"""

	def __init__(self, parent_testcase, prompts, inputs):
		if len(prompts) < len(inputs):
			raise ValueError("insufficient prompts for number of inputs")
		if len(prompts) > len(inputs) + 1:
			raise ValueError("too many prompts for number of inputs")
		self.prompts, self.inputs = prompts, inputs
		self._test_case = parent_testcase
		self._current_prompt = io.StringIO()
		self._input_patch = unittest.mock.patch(
			"builtins.input", self._mock_input
		)
		self._stdout_patch = unittest.mock.patch(
			"sys.stdout", self._current_prompt
		)

	def __enter__(self):
		self._input_patch.__enter__()
		self._stdout_patch.__enter__()

	def __exit__(self, *args):
		if len(self.prompts) == 1:
			# Check final prompt
			if self._current_prompt.getvalue() != self.prompts[0]:
				self._test_case.fail(
					f"Incorrect stdout output. Expected:\n\n"
					f"{self.prompts[0]}\n\n"
					f"Received:\n\n"
					f"{self._current_prompt.getvalue()}\n\n"
				)
		else:
			assert len(self.prompts) == 0
		self._input_patch.__exit__(*args)
		self._stdout_patch.__exit__(*args)

	def _mock_input(self, prompt=""):
		self._current_prompt.write(prompt)
		if self._current_prompt.getvalue() != self.prompts[0]:
			self._test_case.fail(
				f"Incorrect stdout output. Expected:\n\n"
				f"{self.prompts[0]}\n\n"
				f"Received:\n\n"
				f"{self._current_prompt.getvalue()}\n\n"
			)
		elif len(self.inputs) == 0:
			self._test_case.fail("input() called too many times")
		else:
			self._current_prompt.truncate(0)
			self._current_prompt.seek(0)
			next_input = self.inputs[0]
			self.prompts = self.prompts[1:]
			self.inputs = self.inputs[1:]
			return next_input
