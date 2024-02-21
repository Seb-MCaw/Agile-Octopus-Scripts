"""
Useful functions, mostly for handling datetimes.
"""


import datetime
import zoneinfo

import config


def midnight_tonight():
	"""
	Return midnight tonight in the Agile tariff's time zone as datetime.datetime.
	"""
	now = datetime.datetime.now(zoneinfo.ZoneInfo(config.TIME_ZONE))
	midnight_this_morning = now.replace(hour=0, minute=0, second=0, microsecond=0)
	return midnight_this_morning + datetime.timedelta(days=1)


def datetime_sequence(start, step, seq_length=None):
	"""
	Return a sequence of datetime.datetimes starting at start and increasing
	by step hours each time.

	The returned iterable will be infinite unless seq_length is specified,
	in which case it will contain seq_length terms.
	"""
	current_dt = start
	num_terms = 0
	while seq_length is None or num_terms < seq_length:
		yield current_dt
		current_dt += datetime.timedelta(hours=step)
		num_terms += 1

def datetime_str_sequence(start, step, format=r"%Y-%m-%dT%H:%M:%SZ", seq_length=None):
	"""
	Return a sequence of datetime strings starting at the datetime.datetime
	start and increasing by step hours each time.

	format is the datetime.strftime() format specifier used to create the strings.

	The returned iterable will be infinite unless seq_length is specified,
	in which case it will contain seq_length terms.
	"""
	for dt in datetime_sequence(start, step, seq_length):
		yield dt.strftime(format)
