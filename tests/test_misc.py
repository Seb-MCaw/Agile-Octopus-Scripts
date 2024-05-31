import unittest
import unittest.mock
import datetime
import zoneinfo

import misc


@unittest.mock.patch("misc.config.TIME_ZONE", "Europe/London")
class TestMidnightTonight(unittest.TestCase):
	def test_midnight_tonight(self):
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		now_datetime = datetime.datetime(2000,8,1,9,tzinfo=local_tz) # BST
		now_patch = unittest.mock.patch(
			"misc.datetime.datetime",
			wraps=datetime.datetime
		)
		with now_patch:
			misc.datetime.datetime.now = unittest.mock.Mock(return_value=now_datetime)
			self.assertEqual(
				misc.midnight_tonight(True),
				datetime.datetime(2000,8,2,0,tzinfo=local_tz)
			)
			self.assertEqual(
				misc.midnight_tonight(),
				datetime.datetime(2000,8,1,23,tzinfo=datetime.timezone.utc)
			)


class TestDatetimeSequences(unittest.TestCase):

	def test_datetime_sequence(self):
		self.assertEqual(
			list(misc.datetime_sequence(
				datetime.datetime(2003,4,5,6,7,8), .5, 3
			)),
			[
				datetime.datetime(2003,4,5,6,7,8),
				datetime.datetime(2003,4,5,6,37,8),
				datetime.datetime(2003,4,5,7,7,8)
			]
		)

	def test_datetime_seq_at_DST_switchover(self):
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		self.assertEqual(
			list(misc.datetime_sequence(
				datetime.datetime(2020, 3, 28, 23, tzinfo=local_tz),
				.5,
				7
			)),
			[
				datetime.datetime(2020, 3, 28, 23, 00, tzinfo=local_tz),
				datetime.datetime(2020, 3, 28, 23, 30, tzinfo=local_tz),
				datetime.datetime(2020, 3, 29,  0, 00, tzinfo=local_tz),
				datetime.datetime(2020, 3, 29,  0, 30, tzinfo=local_tz),
				datetime.datetime(2020, 3, 29,  2, 00, tzinfo=local_tz),
				datetime.datetime(2020, 3, 29,  2, 30, tzinfo=local_tz),
				datetime.datetime(2020, 3, 29,  3, 00, tzinfo=local_tz),
			]
		)
		self.assertEqual(
			list(misc.datetime_sequence(
				datetime.datetime(2020, 10, 24, 23, tzinfo=local_tz),
				.5,
				11
			)),
			[
				datetime.datetime(2020, 10, 24, 23, 00, tzinfo=local_tz),
				datetime.datetime(2020, 10, 24, 23, 30, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  0, 00, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  0, 30, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  1, 00, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  1, 30, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  1, 00, fold=1, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  1, 30, fold=1, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  2, 00, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  2, 30, tzinfo=local_tz),
				datetime.datetime(2020, 10, 25,  3, 00, tzinfo=local_tz),
			]
		)

	def test_datetime_str_sequence(self):
		self.assertEqual(
			list(misc.datetime_str_sequence(
				datetime.datetime(2003,4,5,6,7,8),
				.5,
				r"%d/%m/%Y at %H:%M:%S",
				3
			)),
			[
				"05/04/2003 at 06:07:08",
				"05/04/2003 at 06:37:08",
				"05/04/2003 at 07:07:08"
			]
		)
