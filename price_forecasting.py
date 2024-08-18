"""
Produce a rough forecast for the unit prices on Octopus Energy's Agile tariff.

The forecast is based only on the previous day's prices and the National
Grid's forecast for national demand and wind generation.

The model must be trained on past data with the train_price_forecast script
before any new forecasts are generated. This package currently provides no
facility to fetch past data automatically, so this will likely need to be
obtained manually.
"""


import os
import datetime
import zoneinfo

import numpy as np
import keras, keras.layers, keras.optimizers, keras.callbacks
import tensorflow as tf

import config
import misc
import data


def construct_forecast_model():
	"""
	Return an uncompiled and untrained keras model for price forecasting.

	It is structured on the basis that prices will depend primarily on the
	demand and wind generation at the time, but will also be affected by
	wider factors that operate on day-long timescales (or longer).

	It takes two separate inputs as provided by get_model_input(), and outputs
	the prices for the 48 settlement periods of the day being forecast.
	"""
	# Prices should depend strongly on the contemporaneous demand and wind
	# generation, and only weakly on all other inputs. As such, to reduce the
	# number of weights to train, there are two branches to the model; one
	# mixes all inputs together, and the other treats each forecast settlement
	# period entirely separately.

	# The branch which mixes all values together:
	mixed_branch_inp = keras.Input((62,))
	# Dense layers with final output duplicated to give shape (48, 4)
	mixed_branch_0 = keras.layers.Dense(32)(mixed_branch_inp)
	mixed_branch_0_act = keras.layers.PReLU()(mixed_branch_0)
	mixed_branch_1 = keras.layers.Dense(16)(mixed_branch_0_act)
	mixed_branch_1_act = keras.layers.PReLU()(mixed_branch_1)
	mixed_branch_2 = keras.layers.Dense(8)(mixed_branch_1_act)
	mixed_branch_2_act = keras.layers.PReLU()(mixed_branch_2)
	mixed_branch_3 = keras.layers.RepeatVector(48)(mixed_branch_2_act)

	# The branch which keeps times separate (matrix multiplication only on
	# second axis):
	unmxd_branch_inp = keras.Input((48, 2))
	unmxd_branch_0 = keras.layers.Dense(8)(unmxd_branch_inp)
	unmxd_branch_1 = keras.layers.PReLU()(unmxd_branch_0)
	unmxd_branch_2 = keras.layers.Dense(4)(unmxd_branch_1)
	unmxd_branch_3 = keras.layers.PReLU()(unmxd_branch_2)

	# Combine the two branches to produce the output
	cmbnd_0 = keras.layers.Concatenate()([mixed_branch_3, unmxd_branch_3])
	cmbnd_1 = ParallelDenseLayer(48, 12, 8)(cmbnd_0)
	cmbnd_2 = keras.layers.PReLU()(cmbnd_1)
	cmbnd_3 = ParallelDenseLayer(48, 8, 8)(cmbnd_2)
	cmbnd_4 = keras.layers.PReLU()(cmbnd_3)
	cmbnd_5 = ParallelDenseLayer(48, 8, 1)(cmbnd_4)
	output = keras.layers.Flatten()(cmbnd_5)

	return keras.Model(inputs=[mixed_branch_inp, unmxd_branch_inp], outputs=output)

def loss_func(true_val, pred_val):
	"""
	A custom loss function for training the model.

	Returns the mean absolute error in the prices (in pence) except that the
	error in prices correctly forecast as <= 0 is reduced by a factor of 10.
	Such prices are more erratic, and the exact value rarely matters, only
	the fact that they are <= 0 (and thus one can never use too much).
	"""
	negative_err_factor = 0.1
	return tf.reduce_mean(tf.abs(tf.where(
		tf.logical_and(true_val <= 0, pred_val <= 0),
		(true_val - pred_val) * negative_err_factor,
		true_val - pred_val,
	)))

class ParallelDenseLayer(keras.layers.Layer):
	"""
	A layer which acts like a Dense layer, except with a separate kernel for
	each element of the penultimate axis.

	Input shape is (..., n, m) and output is (..., n, q)

	With an input A of shape (..., n, m), a Dense layer generates a kernel
	of shape (m, q) and returns activation(np.dot(input, kernel) + bias).
	This layer instead generates a kernel of shape (n, m, q) (and has no
	in-built activation), but is otherwise equivalent.
	"""

	def __init__(self, n, m, q, **kwargs):
		super().__init__(**kwargs)
		self.kernel = self.add_weight(
			shape=(n, m, q), initializer="glorot_uniform", trainable=True
		)
		self.bias = self.add_weight(
			shape=(n, q), initializer="zeros", trainable=True
		)

	def call(self, inputs):
		return tf.reduce_sum(tf.multiply(tf.expand_dims(inputs, -1), self.kernel), -2) + self.bias


def get_model_input(date, demand_data, wind_data, price_data):
	"""
	Construct the appropriate inputs for the model to forecast a price.

	Returns the two inputs (as arrays) which should be used for the model to
	forecast the price for the given date (a datetime.date). Specifically, it
	will forecast from 23:00 (local time) the day before date until 23:00 on
	date.

	The first input array is the concatenation of:
	  - The national grid demand values (in GW) averaged over consecutive
	    2-hour periods from 24 hours before the start of the forecast to
	    the end of the forecast.
	  - The national grid wind generation values averaged over the same periods
	  - The Agile Octopus prices averaged over the same periods up to the
	    start of the forecast (i.e. just for the preceeding day)
	  - The value of date.weekday()
	  - date as the number of days since 2020-01-01

	The second input array has shape (48, 2), and gives the demand and wind
	generation for each of the settlement periods for which the price is to be
	forecast.

	demand_data and wind_data should be dictionaries mapping UTC datetime.datetimes
	to the corresponding national grid forecast values for national demand and
	wind generation	respectively (in GW). price_data should likewise map
	the datetimes of the start of settlement periods to the prices therefor
	(in p/kWh).

	Returns None if demand_data, wind_data and/or price_data lack the necessary
	data to construct the requested array.
	"""
	local_tz = zoneinfo.ZoneInfo(config.TIME_ZONE)
	one_day = datetime.timedelta(days=1)
	forecast_start = datetime.datetime.combine(
		date - one_day,
		datetime.time(23, 00, 00, tzinfo=local_tz)
	)
	prev_day_start = forecast_start.astimezone(datetime.timezone.utc) - one_day
	all_settlmnt_prds = list(misc.datetime_sequence(prev_day_start, 0.5, 96))

	# Assemble demand data
	demand_vals = []
	for ts in all_settlmnt_prds:
		if ts in demand_data:
			demand_vals.append(demand_data[ts])
	if len(demand_vals) < 96:
		# demand_data doesn't contain all of the necessary data to forecast this
		# settlement period
		return None
	# Assemble wind generation data
	wind_vals = []
	for ts in all_settlmnt_prds:
		if ts in wind_data:
			wind_vals.append(wind_data[ts])
	if len(wind_vals) < 96:
		# wind_data doesn't contain all of the necessary data to forecast this
		# settlement period
		return None
	# Assemble prior price data
	prior_prices = []
	for ts in all_settlmnt_prds[:48]:
		if ts in price_data:
			prior_prices.append(price_data[ts])
	if len(prior_prices) < 48:
		# prior_prices doesn't contain all of the necessary data to forecast this
		# settlement period
		return None
	# Calculate the date as a number of days since 2020-01-01
	day_num = int(
		(date - datetime.date(2020, 1, 1))
		/ datetime.timedelta(days=1)
	)

	# Create and return the actual input arrays
	input_0 = np.array(
		  [np.mean( demand_vals[4*i : 4*(i+1)]) for i in range(24)]
		+ [np.mean(   wind_vals[4*i : 4*(i+1)]) for i in range(24)]
		+ [np.mean(prior_prices[4*i : 4*(i+1)]) for i in range(12)]
		+ [date.weekday(), day_num]
	)
	input_1 = np.transpose([demand_vals[48:96], wind_vals[48:96]])
	return input_0, input_1

def construct_output_array(date, price_data):
	"""
	Construct the appropriate output array the model should produce.

	Returns a list of the prices which the model should forecast for the given
	date (a datetime.date); i.e. return the prices from 23:00 (local time) the
	day before date until 23:00 on date.

	price_data should be a dictionary mapping UTC datetime.datetimes of the
	start of settlement periods to the prices therefor (in p/kWh).

	Returns None if price_data lacks the necessary data to construct the
	requested array.
	"""
	local_tz = zoneinfo.ZoneInfo(config.TIME_ZONE)
	forecast_start = datetime.datetime.combine(
		date - datetime.timedelta(days=1),
		datetime.time(23, 00, 00, tzinfo=local_tz)
	)
	forecast_start = forecast_start.astimezone(datetime.timezone.utc)
	all_settlmnt_prds = misc.datetime_sequence(forecast_start, 0.5, 48)
	prices = []
	for ts in all_settlmnt_prds:
		if ts in price_data:
			prices.append(float(price_data[ts]))
	if len(prices) < 48:
		return None
	else:
		return prices

def _get_data_from_csvs():
	"""
	Return the price, demand and wind_generation data found in the csv files
	defined in config.

	The dictionaries are as returned by data.load_csv_time_series(), except
	with values converted to floats.
	"""
	prices = data.load_csv_time_series(
		os.path.join(config.DATA_DIRECTORY, config.PRICE_FILE),
		"Start Time",
		"Price (p/kWh)",
		config.FILE_DATETIME_FORMAT
	)
	prices = {t:float(prices[t]) for t in prices}
	demand = data.load_csv_time_series(
		os.path.join(config.DATA_DIRECTORY, config.NAT_GRID_DEMAND_FILE),
		"Time",
		"Demand / GW",
		config.FILE_DATETIME_FORMAT
	)
	demand = {t:float(demand[t]) for t in demand}
	wind_gen = data.load_csv_time_series(
		os.path.join(config.DATA_DIRECTORY, config.NAT_GRID_WIND_FILE),
		"Time",
		"Wind Generation / GW",
		config.FILE_DATETIME_FORMAT
	)
	wind_gen = {t:float(wind_gen[t]) for t in wind_gen}
	return prices, demand, wind_gen



def gen_price_forecast():
	"""
	Forecast the price for as many settlement periods as possible.

	Returns a dictionary with UTC datetimes as keys and the forecast prices
	thereat as values. The forecast begins immediately after the last price
	published.

	The necessary data is obtained from the CSV files containing the national
	grid demand and wind generation forecasts, and that containing the Agile
	Octopus prices.
	"""
	try:
		model = keras.models.load_model(
			os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
			custom_objects={
				"loss_func": loss_func,
				"ParallelDenseLayer": ParallelDenseLayer
			}
		)
	except (FileNotFoundError, OSError):
		# No model file, so we can't produce any forecast
		return {}
	prices, demand, wind_gen = _get_data_from_csvs()
	local_tz = zoneinfo.ZoneInfo(config.TIME_ZONE)
	last_known_price_time = max(prices.keys()).astimezone(local_tz)
	start = last_known_price_time.date()
	end = min(max(demand.keys()), max(wind_gen.keys())).date()

	# Generate the forecast for each day, using the prices produced by the
	# previous day's forecast if required.
	t = start
	while t <= end:
		t += datetime.timedelta(days=1)
		# Use the model to generate a forecast for the date t
		inputs = get_model_input(t, demand, wind_gen, prices)
		if inputs is None:
			# We don't have enough data to produce a forecast for this day
			# (and therefore won't for any subsequent days)
			break
		try:
			frcst_prices = list(model.predict(
				[np.array([inputs[0]]), np.array([inputs[1]])],
				verbose=0
			)[0])
		except ValueError:
			# The model encountered an error (e.g. get_model_input() has
			# changed since the model was trained), so terminate and return
			# any forecast we've already managed to generate.
			break
		frcst_start_time = datetime.datetime.combine(
			t - datetime.timedelta(days=1),
			datetime.time(23, 00, tzinfo=local_tz)
		).astimezone(datetime.timezone.utc)
		frcst_times = list(misc.datetime_sequence(frcst_start_time, 0.5, 48))
		# Handle daylight savings switchover
		frcst_end_time = frcst_times[-1] + datetime.timedelta(minutes=30)
		frcst_end_local_time = frcst_end_time.astimezone(local_tz)
		if frcst_end_local_time.hour == 22:
			# The clocks have gone back, so we need an extra hour of
			# prices. There isn't enough data to train the model to handle
			# this properly, so make a crude approximation by repeating
			# the prices the model produced for the first instances of
			# 01:00 and 01:30 at their second occurences.
			frcst_prices.insert(6, frcst_prices[4])
			frcst_prices.insert(7, frcst_prices[5])
			frcst_times.extend([
				frcst_end_time,                                 # 22:00
				frcst_end_time + datetime.timedelta(hours=0.5)  # 22:30
			])
		elif frcst_end_local_time.hour == 00:
			# The clocks have gone forward, so 01:00 and 01:30 didn't happen.
			# There isn't enough data to train the model to handle this
			# properly, so make a crude approximation by simply removing
			# the prices forecast for these times.
			frcst_prices = frcst_prices[:4] + frcst_prices[6:]
			frcst_times = frcst_times[:46]
		elif frcst_end_local_time.hour != 23:
			# This shouldn't happen during a normal DST switchover
			raise RuntimeError("Unexpected timezone behaviour")
		# Then actually record the forecast
		for time, price in zip(frcst_times, frcst_prices):
			prices[time] = price
	return {t:prices[t] for t in prices if t > last_known_price_time}
