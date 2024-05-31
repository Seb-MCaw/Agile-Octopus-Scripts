import unittest
import unittest.mock
import datetime
import os

import numpy as np
import tensorflow as tf

import price_forecasting
import misc


class TestModelConstruction(unittest.TestCase):
	def test_construct_model(self):
		m = price_forecasting.construct_forecast_model()
		self.assertEqual(len(m.inputs), 2)
		self.assertEqual(m.inputs[0].shape, tf.TensorShape([None, 62]))
		self.assertEqual(m.inputs[1].shape, tf.TensorShape([None, 48, 2]))
		self.assertEqual(m.output.shape, tf.TensorShape([None, 48]))


class TestLossFunc(unittest.TestCase):
	def test_loss_func(self):
		true_pred_pairs = [
			(1,2),   # Error = 1
			(3,3),   # Error = 0
			(5,4),   # Error = -1
			(-1,-2), # Error = -0.1 (correctly predicted -ve)
			(-3,-3), # Error = 0
			(-5,-4), # Error = 0.1 (correctly predicted -ve)
			(0,-1),  # Error = -0.1 (correctly predicted <=0)
			(1,-1),  # Error = -2 (incorrectly predicted -ve)
			(-1,1),  # Error = 2 (incorrectly predicted +ve)
		]
		true, pred = zip(*true_pred_pairs)
		self.assertAlmostEqual(
			float(price_forecasting.loss_func(np.array(true), np.array(pred))),
			0.7  # Mean abs() of the above
		)


class TestParallelDenseLayer(unittest.TestCase):
	def test_parallel_dense_layer(self):
		pdl = price_forecasting.ParallelDenseLayer(2, 3, 4)
		self.assertEqual(pdl.kernel.shape, (2,3,4))
		x = np.random.uniform(size=(5,2,3))
		self.assertEqual(pdl(x).shape, (5,2,4))
		self.assertTrue(np.all(np.isclose(
			pdl(x).numpy(),
			np.array([
				[
					np.dot(z, k) + b
					for z,k,b in zip(y, pdl.kernel, pdl.bias)
				]
				for y in x
			]),
			rtol=1e-3
		)))


class TestModelInputOutput(unittest.TestCase):

	def test_get_model_input(self):
		utc = datetime.timezone.utc
		start = datetime.datetime(2020, 1, 1, tzinfo=utc)
		demand_data = {d:v for d,v in zip(
			misc.datetime_sequence(start, 0.5, 144),
			range(0, 144)
		)}
		wind_data = {d:v for d,v in zip(
			misc.datetime_sequence(start, 0.5, 144),
			range(144, 288)
		)}
		price_data = {d:v for d,v in zip(
			misc.datetime_sequence(start, 0.5, 94),
			range(288, 382)
		)}
		input_1, input_2 = price_forecasting.get_model_input(
			datetime.date(2020,1,3), demand_data, wind_data, price_data
		)
		self.assertIs(type(input_1), np.ndarray)
		self.assertIs(type(input_2), np.ndarray)
		self.assertTrue(np.all(np.equal(
			input_1,
			(
				list(np.linspace(47.5, 139.5, 24))
				+ list(np.linspace(191.5, 283.5, 24))
				+ list(np.linspace(335.5, 379.5, 12))
				+ [4, 2]
			)
		)))
		self.assertTrue(np.all(np.equal(
			input_2,
			list(zip(range(94, 142), range(238, 286)))
		)))
		bad_demand = demand_data.copy()
		bad_demand.pop(datetime.datetime(2020, 1, 1, 23, tzinfo=utc))
		self.assertIsNone(price_forecasting.get_model_input(
			datetime.date(2020,1,3), bad_demand, wind_data, price_data
		))
		bad_wind = wind_data.copy()
		bad_wind.pop(datetime.datetime(2020, 1, 3, 22, 30, tzinfo=utc))
		self.assertIsNone(price_forecasting.get_model_input(
			datetime.date(2020,1,3), demand_data, bad_wind, price_data
		))
		bad_prices = price_data.copy()
		bad_prices.pop(datetime.datetime(2020, 1, 2, 9, tzinfo=utc))
		self.assertIsNone(price_forecasting.get_model_input(
			datetime.date(2020,1,3), demand_data, wind_data, bad_prices
		))

	def test_construct_output_array(self):
		utc = datetime.timezone.utc
		start = datetime.datetime(2020, 1, 1, tzinfo=utc)
		price_data = {d:v for d,v in zip(
			misc.datetime_sequence(start, 0.5, 240),
			range(0, 240)
		)}
		output = price_forecasting.construct_output_array(
			datetime.date(2020,1,3), price_data
		)
		self.assertEqual(list(output), list(range(94, 142)))
		bad_prices = price_data.copy()
		bad_prices.pop(datetime.datetime(2020, 1, 3, 18, 30, tzinfo=utc))
		self.assertIsNone(price_forecasting.construct_output_array(
			datetime.date(2020,1,3), bad_prices
		))



class TestGenPriceForecast(unittest.TestCase):

	def setUp(self):
		# Mock config file
		self.config_patch = unittest.mock.patch.multiple(
			price_forecasting.config,
			DATA_DIRECTORY = "dir",
			PRICE_FILE = "price_file",
			NAT_GRID_DEMAND_FILE = "demand_file",
			NAT_GRID_WIND_FILE = "wind_file",
			FILE_DATETIME_FORMAT = "time_format",
			FORECAST_MODEL_FILE = "model_file",
			TIME_ZONE = "Europe/London"
		)
		# Mock reading the csv files (6 days of wind and demand data, only
		# 2 of prices)
		def mock_csv_time_series(file_path, time_col, val_col, time_format):
			self.assertEqual(time_format, "time_format")
			if os.path.normpath(file_path) == os.path.normpath("dir/demand_file"):
				self.assertEqual(time_col, "Time")
				self.assertEqual(val_col, "Demand / GW")
				return {
					k:v for k,v in zip(
						misc.datetime_sequence(self.start, 0.5, 288),
						range(0, 288)
					)
				}
			elif os.path.normpath(file_path) == os.path.normpath("dir/wind_file"):
				self.assertEqual(time_col, "Time")
				self.assertEqual(val_col, "Wind Generation / GW")
				return {
					k:v for k,v in zip(
						misc.datetime_sequence(self.start, 0.5, 288),
						range(288, 576)
					)
				}
			elif os.path.normpath(file_path) == os.path.normpath("dir/price_file"):
				self.assertEqual(time_col, "Start Time")
				self.assertEqual(val_col, "Price (p/kWh)")
				return {
					k:v for k,v in zip(
						misc.datetime_sequence(self.start, 0.5, 96),
						range(576, 672)
					)
				}
			else:
				self.fail("incorrect csv path")
		self.data_patch = unittest.mock.patch(
			"price_forecasting.data.load_csv_time_series",
			mock_csv_time_series
		)
		# Mock loading the model (use a model which just passes demand
		# values straight through, plus 1000 times the settlement period
		# number)
		mock_model = unittest.mock.Mock()
		def mock_model_predict(inputs, *args, **kwargs):
			return np.array(inputs[1])[:,:,0] + np.linspace(0, 47000, 48)
		mock_model.predict = mock_model_predict
		def mock_load_model(path, **kwargs):
			if os.path.normpath(path) != os.path.normpath("dir/model_file"):
				# self.assertEqual() can't be used as it is swallowed by
				# gen_price_forecast()'s error handling
				self.fail(f"incorrect model path: {path} != dir/model_file")
			self.assertIs(
				kwargs["custom_objects"]["loss_func"],
				price_forecasting.loss_func
			)
			self.assertIs(
				kwargs["custom_objects"]["ParallelDenseLayer"],
				price_forecasting.ParallelDenseLayer
			)
			return mock_model
		self.load_model_patch = unittest.mock.patch(
			"price_forecasting.keras.models.load_model",
			mock_load_model
		)

	def test_gen_forecast(self):
		utc = datetime.timezone.utc
		self.start = datetime.datetime(2020, 1, 1, 23, tzinfo=utc)
		forecast_start = datetime.datetime(2020, 1, 3, 23, tzinfo=utc)
		with self.config_patch, self.data_patch, self.load_model_patch:
			self.assertEqual(
				price_forecasting.gen_price_forecast(),
				{k:v for k,v in zip(
					misc.datetime_sequence(forecast_start, 0.5, 192),
					(
						  list(range(96, 48144, 1001))
						+ list(range(144, 48192, 1001))
						+ list(range(192, 48240, 1001))
						+ list(range(240, 48288, 1001))
					)
				)}
			)

	def test_DST_handling(self):
		# Clocks go forward on 2020-03-29, so the forecasts for
		# 2020-03-29T01:00 and 2020-03-29T01:30 are omitted
		utc = datetime.timezone.utc
		self.start = datetime.datetime(2020, 3, 25, 23, tzinfo=utc)
		forecast_start = datetime.datetime(2020, 3, 27, 23, tzinfo=utc)
		with self.config_patch, self.data_patch, self.load_model_patch:
			self.assertEqual(
				price_forecasting.gen_price_forecast(),
				{k:v for k,v in zip(
					misc.datetime_sequence(forecast_start, 0.5, 190),
					(
						  list(range(96, 48144, 1001))
						+ list(range(144, 4148, 1001))
						+ list(range(6150, 48192, 1001))
						+ list(range(190, 48238, 1001)) # Now starts 22:00 UTC
						+ list(range(238, 48286, 1001))
					)
				)}
			)
		# Clocks go backward on 2020-10-25, so the forecasts for
		# 2020-10-25T01:00 and 2020-10-25T01:30 are repeated
		utc = datetime.timezone.utc
		self.start = datetime.datetime(2020, 10, 21, 22, tzinfo=utc)
		forecast_start = datetime.datetime(2020, 10, 23, 22, tzinfo=utc)
		with self.config_patch, self.data_patch, self.load_model_patch:
			self.assertEqual(
				price_forecasting.gen_price_forecast(),
				{k:v for k,v in zip(
					misc.datetime_sequence(forecast_start, 0.5, 146),
					(
						  list(range(96, 48144, 1001))
						+ list(range(144, 6150, 1001))
						+ list(range(4148, 48192, 1001))
						+ list(range(194, 48242, 1001)) # Back to 23:00 UTC
						# The next day only has 23hrs of wind/demand data left,
						# so won't be forecast
					)
				)}
			)

	def test_no_model_found(self):
		utc = datetime.timezone.utc
		self.start = datetime.datetime(2020, 1, 1, 23, tzinfo=utc)
		def mock_load_model(path, **kwargs):
			raise OSError
		load_model_patch = unittest.mock.patch(
			"price_forecasting.keras.models.load_model",
			mock_load_model
		)
		with self.config_patch, self.data_patch, load_model_patch:
			self.assertEqual(price_forecasting.gen_price_forecast(), {})

	def test_model_error(self):
		utc = datetime.timezone.utc
		self.start = datetime.datetime(2020, 1, 1, 23, tzinfo=utc)
		mock_model = unittest.mock.Mock()
		def mock_model_predict(inputs, *args, **kwargs):
			raise ValueError
		mock_model.predict = mock_model_predict
		def mock_load_model(path, **kwargs):
			return mock_model
		load_model_patch = unittest.mock.patch(
			"price_forecasting.keras.models.load_model",
			mock_load_model
		)
		with self.config_patch, self.data_patch, load_model_patch:
			self.assertEqual(price_forecasting.gen_price_forecast(), {})
