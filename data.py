"""
Fetch, store and retrieve data from various APIs.

Implements the price and consumption APIs from Octopus Energy, temperature
forecasts from the MetOffice, and half-hourly demand and wind generation
forecasts from the National Grid.

Data is stored in csv files in locations defined in the config module.

Where necessary, API keys are taken from the config module.
"""



import time
import datetime
import urllib.request
import json
import csv
import base64
import os

import numpy as np

import config
import misc



def get_hourly_temperatures(start_time):
	"""
	Return hourly forecast temperatures at the location defined in config.

	Returns a list of hourly temperatures for as long as the data in the csv
	file permits, starting with the temperature at the datetime.datetime
	start_time.

	Throws an exception if no forecast is available for start_time.
	"""
	start_time = start_time.astimezone(datetime.timezone.utc)
	# Get the data from the csv
	data_dict = load_csv_time_series(
		os.path.join(config.DATA_DIRECTORY, config.TEMPERATURE_FILE),
		"Time",
		"Temperature (\N{DEGREE SIGN}C)",
		config.FILE_DATETIME_FORMAT
	)
	times, temps = zip(*sorted(
		[(t, float(data_dict[t])) for t in data_dict],
		key=lambda x: x[0]
	))
	if not (times[0] <= start_time <= times[-1]):
		raise RuntimeError("insufficient data in csv file for temperature forecast")
	# Convert into hours after start_time
	times = [(t - start_time)/datetime.timedelta(hours=1) for t in times]
	# Linearly interpolate to get the approx temperatures at the desired hours
	num_hours = int(times[-1])
	return list(np.interp(
		np.linspace(0, num_hours, num_hours+1),
		times,
		temps
	))

def update_temperature_forecast():
	"""
	Fetch and store the hourly temperature forecast from the MetOffice.

	Overwrites any data previously stored in the csv file (since this is
	a more up-to-date forecast).
	"""
	lat, long = config.LATITUDE, config.LONGITUDE
	# Get hourly Met Office forecast.
	request = urllib.request.Request(
		"https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly"
			+ f"?includeLocationName=true&latitude={lat}&longitude={long}",
		headers={
			"apikey" : config.METOFFICE_API_KEY
		}
	)
	with urllib.request.urlopen(request) as f:
		response = json.loads(f.read())
	times = [
		_metoff_dt(d["time"])
		for d in response["features"][0]["properties"]["timeSeries"]
	]
	temps = [
		float(d["screenTemperature"])
		for d in response["features"][0]["properties"]["timeSeries"]
	]
	last_hourly_entry = max(times)
	# Get 3-hourly Met Office forecast and append it to the hourly forecast;
	# this is less detailed but extends further into the future.
	request = urllib.request.Request(
		"https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/three-hourly"
			+ f"?includeLocationName=true&latitude={lat}&longitude={long}",
		headers={
			"apikey" : config.METOFFICE_API_KEY
		}
	)
	with urllib.request.urlopen(request) as f:
		response = json.loads(f.read())
	times.extend([
		_metoff_dt(d["time"])
		for d in response["features"][0]["properties"]["timeSeries"]
		if _metoff_dt(d["time"]) > last_hourly_entry
	])
	temps.extend([
		0.5 * (float(d["maxScreenAirTemp"]) + float(d["minScreenAirTemp"]))
		for d in response["features"][0]["properties"]["timeSeries"]
		if _metoff_dt(d["time"]) > last_hourly_entry
	])
	# Add these values to the csv file
	times = [t.strftime(config.FILE_DATETIME_FORMAT) for t in times]
	append_csv(
		os.path.join(config.DATA_DIRECTORY, config.TEMPERATURE_FILE),
		zip(times, temps),
		["Time", "Temperature (\N{DEGREE SIGN}C)"],
		"Time",
		True
	)

def _metoff_dt(str):
	"""
	Return a datetime.datetime corresponding to a string in the MetOffice format.
	"""
	d = datetime.datetime.strptime(str, r"%Y-%m-%dT%H:%MZ")
	return d.replace(tzinfo=datetime.timezone.utc)


def update_nat_grid_demand_forecast():
	"""
	Fetch and store the national grid's 2-14 day half-hourly national demand forecast.

	Since the national grid only provides instantaneous values, the average
	demand over the course of each half-hour is crudely estimated by averaging
	the demands at the two endpoints.
	"""
	csv_str = urllib.request.urlopen(
		"https://api.nationalgrideso.com/"
		+ "dataset/633daec6-3e70-444a-88b0-c4cef9419d40/"
		+ "resource/7c0411cd-2714-4bb5-a408-adb065edf34d/"
		+ "download/ng-demand-14da-hh.csv"
	).read()
	rows = [row for row in csv.reader(csv_str.decode().split("\r\n"))]
	rows = rows[1:] # (ignore header)
	rows = [row for row in rows if len(row) != 0] # (remove blank lines)
	# Convert to correct formats for appending to the csv
	rows = [
		(
			datetime.datetime.strptime(row_1[2], r"%Y-%m-%dT%H:%M:%S"),
			((float(row_1[3]) + float(row_2[3])) / 2)
		)
		for (row_1, row_2) in zip(rows, rows[1:])
	]
	assert all(
		(r_2[0] - r_1[0] == datetime.timedelta(hours=0.5))
		for (r_1, r_2) in zip(rows, rows[1:])
	)
	rows = [
		(t.strftime(config.FILE_DATETIME_FORMAT), d / 1000) # (convert to GW)
		for t, d in rows
	]
	# Append this data to the csv
	append_csv(
		os.path.join(config.DATA_DIRECTORY, config.NAT_GRID_DEMAND_FILE),
		rows,
		["Time", "Demand / GW"],
		"Time",
		True
	)

def update_nat_grid_wind_forecast():
	"""
	Fetch and store the national grid's 14 days ahead half-hourly wind forecast.
	"""
	csv_str = urllib.request.urlopen(
		"https://api.nationalgrideso.com/"
		+ "dataset/2f134a4e-92e5-43b8-96c3-0dd7d92fcc52/"
		+ "resource/93c3048e-1dab-4057-a2a9-417540583929/"
		+ "download/14dawindforecast.csv"
	).read()
	rows = [row for row in csv.reader(csv_str.decode().split("\r\n"))]
	rows = rows[1:] # (ignore header)
	rows = [row for row in rows if len(row) != 0] # (remove blank lines)
	# Convert to correct formats for appending to the csv
	rows = [
		(
			datetime.datetime.strptime(row[0], r"%Y-%m-%dT%H:%M:%SZ"),
			float(row[4])
		)
		for row in rows
	]
	assert all(
		(r_2[0] - r_1[0] == datetime.timedelta(hours=0.5))
		for (r_1, r_2) in zip(rows, rows[1:])
	)
	rows = [
		(t.strftime(config.FILE_DATETIME_FORMAT), w / 1000) # (convert to GW)
		for t, w in rows
	]
	# Append this data to the csv
	append_csv(
		os.path.join(config.DATA_DIRECTORY, config.NAT_GRID_WIND_FILE),
		rows,
		["Time", "Wind Generation / GW"],
		"Time",
		True
	)


def get_agile_prices():
	"""
	Return a list of half-hourly Agile Octopus prices starting at 23:00 tonight.

	The returned list will normally have length 48, but 46 or 50 at daylight
	savings switch-overs. If update_agile_prices() is not called first, the
	length may be 0.
	"""
	# Get the data from the csv
	data_dict = load_csv_time_series(
		os.path.join(config.DATA_DIRECTORY, config.PRICE_FILE),
		"Start Time",
		"Price (p/kWh)",
		config.FILE_DATETIME_FORMAT
	)
	data = sorted(
		[(t, float(data_dict[t])) for t in data_dict],
		key=lambda x: x[0]
	)
	# Get and return just the prices from 23:00 tonight onwards
	start_time = misc.midnight_tonight() - datetime.timedelta(hours=1)
	data = [d for d in data if d[0] >= start_time]
	# Return the prices
	return [p for _, p in data]

def update_agile_prices(wait=True):
	"""
	Fetch and store tonight's unit prices for Octopus Energy's Agile tariff.

	If wait is True, blocks until the prices are available.
	"""
	start_time = misc.midnight_tonight() - datetime.timedelta(hours=1)
	period_from_str = start_time.strftime(r"%Y-%m-%dT%H:%M:%SZ")
	api_request_url = (
		"https://api.octopus.energy/v1/products/"
		+ f"{config.OCTOPUS_AGILE_PRODUCT_CODE}/electricity-tariffs/"
		+ f"E-1R-{config.OCTOPUS_AGILE_PRODUCT_CODE}-"
		+ f"{config.OCTOPUS_AGILE_REGION_CODE}/"
		+ f"standard-unit-rates?period_from={period_from_str}"
	)
	response = json.loads(urllib.request.urlopen(api_request_url).read())
	while wait and response["count"] == 0:
		# Wait 10mins and try again
		time.sleep(10 * 60)
		response = json.loads(urllib.request.urlopen(api_request_url).read())
	rows = [
		(
			datetime.datetime.strptime(
				d["valid_from"], r"%Y-%m-%dT%H:%M:%SZ"
			),
			d["value_inc_vat"]
		)
		for d in response["results"]
	]
	rows.sort(key=lambda x: x[0])
	rows = [
		(t.strftime(config.FILE_DATETIME_FORMAT), p)
		for t, p in rows
	]
	append_csv(
		os.path.join(config.DATA_DIRECTORY, config.PRICE_FILE),
		rows,
		["Start Time", "Price (p/kWh)"],
		"Start Time"
	)

def get_actual_spend(start, end):
	"""
	Return the amount of energy actually consumed between the two specified
	(timezone aware) datetimes and the cost thereof (in pence).

	Returns (total energy consumption in kWh, total cost in pence) for all
	settlement periods which overlap to any extent with the interval [start, end).

	Meter readings that are not yet available will be treated as zero.
	Doesn't account for standing charges.
	"""
	# TODO: Implement a csv for this

	# Handle timezones
	UTC = datetime.timezone.utc
	start = start.astimezone(UTC)
	end = end.astimezone(UTC)
	# Round start and end to the appropriate half-hours
	start.replace(minute = start.minute - (start.minute % 30))
	start.replace(second = 0, microsecond = 0)
	if not(end.minute % 30 == 0 and end.second == end.microsecond == 0):
		end.replace(minute = end.minute - (end.minute % 30))
		end.replace(second = 0, microsecond = 0)
		end += datetime.timedelta(minutes=30)
	# Get consumption figures (consumption API uses closed time intervals)
	last_settl_period = end - datetime.timedelta(minutes=30)
	basic_auth_str = base64.b64encode((config.OCTOPUS_API_KEY + ':').encode()).decode()
	url = (
		"https://api.octopus.energy/v1/"
		+ f"electricity-meter-points/{config.OCTOPUS_MPAN}/"
		+ f"meters/{config.OCTOPUS_METER_SERIAL_NO}/"
		+  "consumption/?page_size=1500"
		+ f"&period_from={start.strftime(r'%Y-%m-%dT%H:%MZ')}"
		+ f"&period_to={last_settl_period.strftime(r'%Y-%m-%dT%H:%MZ')}"
	)
	consumption = {}
	while url is not None:
		req = urllib.request.Request(
			url,
			headers={"Authorization" : f"Basic {basic_auth_str}"}
		)
		response = json.loads(urllib.request.urlopen(req).read())
		consumption.update({
			datetime.datetime.strptime(
				row["interval_start"], r"%Y-%m-%dT%H:%M:%S%z"
			).astimezone(UTC).strftime(r"%Y-%m-%dT%H:%M:%SZ")
			: row["consumption"]
			for row in response["results"]
		})
		url = response["next"]
	# Get prices for the same period
	url = (
		"https://api.octopus.energy/v1/products/"
		+ f"{config.OCTOPUS_AGILE_PRODUCT_CODE}/electricity-tariffs/"
		+ f"E-1R-{config.OCTOPUS_AGILE_PRODUCT_CODE}-"
		+ f"{config.OCTOPUS_AGILE_REGION_CODE}/standard-unit-rates"
		+ f"?page_size=1500&period_from={start.strftime(r'%Y-%m-%dT%H:%MZ')}"
		+ f"&period_to={end.strftime(r'%Y-%m-%dT%H:%MZ')}"
	)
	prices = {}
	while url is not None:
		response = json.loads(urllib.request.urlopen(url).read())
		prices.update({
			row["valid_from"] : row["value_exc_vat"]
			for row in response["results"]
		})
		url = response["next"]
	# Return total consumption and total cost
	#
	# For some reason Octopus rounds several times when calculating bills.
	# Do all the rounding for each half-hour, but not for the overall total
	# (since the time period probably represents only part of a bill)
	assert set(consumption.keys()).issubset(prices.keys())
	total_consumption = total_cost = 0
	for t in consumption:
		total_consumption += consumption[t]
		rounded_consumption = round(consumption[t], 2)
		rounded_price = round(prices[t], 2)
		total_cost += round(rounded_consumption * rounded_price, 2)
	total_cost = 1.05 * total_cost
	return total_consumption, total_cost



def append_csv(file_path, new_rows, field_names, unique_field=None, overwrite_duplicates=False):
	"""
	Append rows to an existing csv file.

	new_rows is an iterable of lists, each sublist representing a row as a list
	of values. Values will be converted to strings if necessary. Rows will be
	appended in the order they appear in new_rows.

	field_names is an sequence of strings containing headings for each column.
	The order of each row should correspond to the order of field_names. If
	the field_names argument does not match those already present in the file,
	the union of the two sets will be used and additional blank cells will be
	added where appropriate.

	To avoid duplicate data, only new rows for which the value of the field
	unique_field (which should be a string also present in field_names) is not
	the same as that of any row already present in the file will be appended;
	any others are ignored, or will replace the existing row if
	overwrite_duplicates is True. Duplication between rows already present in
	the file, or within new_rows, will be unaffected. If unique_field is not
	specified, all new_rows will be appended.

	If the file does not exist a new one will be created; if the file exists
	but isn't a valid csv, an exception may be thrown.
	"""
	# Convert each new_row to an appropriate dictionary
	new_rows = [{k:v for k,v in zip(field_names, row)} for row in new_rows]
	# Read any data already in the file
	try:
		with open(file_path, "r", newline="", encoding="utf-8") as f:
			csv_reader = csv.DictReader(f, delimiter=",")
			prev_rows = [row for row in csv_reader]
			prev_field_names = csv_reader.fieldnames
	except FileNotFoundError:
		prev_rows = []
		prev_field_names = []
	# Remove any rows with duplicate values of unique_field
	if unique_field is not None:
		if overwrite_duplicates:
			new_unique_values = set([row[unique_field] for row in new_rows])
			prev_rows = [
				row for row in prev_rows
				if row[unique_field] not in new_unique_values
			]
		else:
			unique_values_already_present = set([row[unique_field] for row in prev_rows])
			new_rows = [
				row for row in new_rows
				if row[unique_field] not in unique_values_already_present
			]
	# Construct the full list of rows with the appended data
	new_field_names = [f for f in field_names if (f not in prev_field_names)]
	all_field_names = prev_field_names + new_field_names
	rows = [
		{fn : (row[fn] if fn in row else "") for fn in all_field_names}
		for row in (prev_rows + new_rows)
	]
	# Write the new data to the file
	with open(file_path, "w", newline="", encoding="utf-8") as f:
		csv_writer = csv.DictWriter(f, all_field_names, delimiter=",")
		csv_writer.writeheader()
		csv_writer.writerows(rows)


def load_csv_time_series(file_path, time_col, val_col, time_format=r"%Y-%m-%dT%H:%M:%SZ"):
	"""
	Return the time series data in the specified file as a dictionary.

	The csv file must have a column with the title specified by time_col
	containing UTC timestamps in the specified format and another column
	with the title given by val_col.

	The returned dictionary uses the time_col values (as timezone aware UTC
	datetime.datetimes) for keys and the other column for values (as strings).
	When there are multiple instances of the same time value in the file, the
	returned dictionary will contain only one.
	"""
	time_series = {}
	with open(file_path, "r", newline="", encoding="utf-8") as f:
		csv_reader = csv.DictReader(f, delimiter=",")
		for row in csv_reader:
			t = datetime.datetime.strptime(
				row[time_col], time_format
			).replace(tzinfo=datetime.timezone.utc)
			v = row[val_col]
			time_series[t] = v
	return time_series
