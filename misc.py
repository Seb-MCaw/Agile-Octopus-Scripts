"""
Useful functions, mostly for handling datetimes.
"""


import datetime
import zoneinfo

import config


def midnight_tonight(local=False):
	"""
	Return midnight tonight in the Agile tariff's time zone.

	Specifically, return the datetime.datetime corresponding to 00:00 tonight
	in config.TIME_ZONE. If local is False (the default), it will be converted
	to UTC before returning.
	"""
	now = datetime.datetime.now(zoneinfo.ZoneInfo(config.TIME_ZONE))
	midnight_this_morning = now.replace(hour=0, minute=0, second=0, microsecond=0)
	midnight_tonight = midnight_this_morning + datetime.timedelta(days=1)
	if not local:
		midnight_tonight = midnight_tonight.astimezone(datetime.timezone.utc)
	return midnight_tonight


def datetime_sequence(start, step, seq_length=None):
	"""
	Return a sequence of datetime.datetimes starting at start and increasing
	by step hours each time.

	The returned iterable will be infinite unless seq_length is specified,
	in which case it will contain seq_length terms.

	If start is an aware datetime, the returned datetimes will have the same
	timezone, but the arithmetic is performed in UTC so the sequence steps
	forward in real time at DST switchovers. For example, a step of 1 will
	result a repeated time when the clocks go back 1 hour and a skipped
	time when they go forward an hour.
	"""
	if start.tzinfo is None:
		current_dt = start
		time_zone = None
	else:
		current_dt = start.astimezone(datetime.timezone.utc)
		time_zone = start.tzinfo
	num_terms = 0
	while seq_length is None or num_terms < seq_length:
		if time_zone is None:
			yield current_dt
		else:
			yield current_dt.astimezone(time_zone)
		current_dt += datetime.timedelta(hours=step)
		num_terms += 1

def datetime_str_sequence(start, step, format=r"%Y-%m-%dT%H:%M:%SZ", seq_length=None):
	"""
	Return a sequence of datetime strings starting at the datetime.datetime
	start and increasing by step hours each time.

	format is the datetime.strftime() format specifier used to create the strings.

	The returned iterable will be infinite unless seq_length is specified,
	in which case it will contain seq_length terms.

	If start is an aware datetime, the returned strings will represent times
	in the same timezone, but the arithmetic is performed in UTC so the sequence
	steps forward in real time at DST switchovers. For example, a step of 1 will
	result a repeated time when the clocks go back 1 hour and a skipped
	time when they go forward an hour.
	"""
	for dt in datetime_sequence(start, step, seq_length):
		yield dt.strftime(format)
