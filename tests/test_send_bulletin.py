import unittest
import unittest.mock
import datetime
import zoneinfo
import contextlib

import send_bulletin
import misc


class TestMain(unittest.TestCase):
	def test_main(self):
		# Mock the current time
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		def mock_midnight_tonight(local=False):
			if local:
				return datetime.datetime(2020,6,1, tzinfo=local_tz)
			else:
				return datetime.datetime(2020,5,31,23,tzinfo=datetime.timezone.utc)
		time_patch = unittest.mock.patch(
			"send_bulletin.misc.midnight_tonight",
			mock_midnight_tonight
		)
		mock_datetime = unittest.mock.Mock(wraps=datetime.datetime)
		mock_datetime.now = lambda: datetime.datetime(2020,5,31,12)
		now_patch = unittest.mock.patch(
			"send_bulletin.datetime.datetime",
			mock_datetime
		)
		# Mock the relevant config values
		config_patch = unittest.mock.patch.multiple(
			send_bulletin.config,
			SENDER_ADDRESS = "sender@gmail.com",
			SMTP_AUTH_PASS = "password1234",
			TO_ADDRESS = "recipient@example.com",
			SMTP_SERVER = "smtp.gmail.com",
			SMTP_PORT = 465,
			TIME_ZONE = "Europe/London",
			OCTOPUS_BILL_DAY = 1,
			OCTOPUS_AGILE_JOIN_DATE = "2018-02-21",
		)
		# Mock the relevant functions in data
		def mock_get_spend(start, end):
			self.assertEqual(end, datetime.datetime(2020,5,31, tzinfo=local_tz))
			if start == datetime.datetime(2020,5,30, tzinfo=local_tz):
				return 1, 2
			elif start == datetime.datetime(2020,5,25, tzinfo=local_tz):
				return 3, 4
			elif start == datetime.datetime(2020,5,1, tzinfo=local_tz):
				return 5, 6
			elif start == datetime.datetime(2020,1,1, tzinfo=local_tz):
				return 7, 8
			elif start == datetime.datetime(2018,2,21, tzinfo=local_tz):
				return 9, 10
			else:
				self.fail("unexpected time span for data.get_actual_spend()")
		mock_update_prices = unittest.mock.Mock()
		mock_update_temps = unittest.mock.Mock()
		mock_update_demand = unittest.mock.Mock()
		mock_update_wind = unittest.mock.Mock()
		mock_get_prices = unittest.mock.Mock(return_value=[
			5.985, 4.1055, 4.1055, -1, 4.347, 4.5885, 4.9245, 0,
			3.9585, 3.7695, 4.347, 4.2, 3.6225, 4.4415, 6.0585, 6.426,
			6.279, 7.245, 7.9695, 7.9695, 7.728, 7.3395, 7.245, 6.762,
			6.573, 7.056, 7.728, 7.539, 7.245, 5.796, 5.313, 4.641, 4.2525,
			4.8825, 16.2855, 17.808, 18.606, 19.278, 20.433, 20.4855,
			9.177, 8.9355, 8.694, 8.568, 8.694, 8.4525, 7.9695, 7.245,
		])
		data_patch = unittest.mock.patch.multiple(
			send_bulletin.data,
			get_actual_spend=mock_get_spend,
			get_agile_prices=mock_get_prices,
			update_agile_prices=mock_update_prices,
			update_temperature_forecast=mock_update_temps,
			update_nat_grid_demand_forecast=mock_update_demand,
			update_nat_grid_wind_forecast=mock_update_wind,
		)
		# Mock the price forecast
		mock_gen_price_forecast = unittest.mock.Mock(return_value={
			k: v
			for k,v in zip(
				misc.datetime_sequence(
					datetime.datetime(2020,6,1,22,tzinfo=datetime.timezone.utc),
					.5
				),
				[
					7.245, 7.245, 5.7015, 5.313, 5.439, 5.439, 4.9245, 4.83,
					5.0715, 4.83, 5.019, 4.83, 6.111, 5.8905, 7.3395, 6.636,
					5.796, 7.0035, 6.762, 6.762, 7.0035, 6.279, 5.922, 5.124,
					5.5545, 5.796, 6.468, 6.09, 5.796, 4.83, 4.662, 4.4415,
					4.536, 4.83, 17.01, 19.0365, 19.467, 21.042, 20.916,
					21.4515, 10.143, 9.4185, 8.7675, 7.6335, 8.4525, 8.043,
					7.728, 6.0375, 7.245, 7.392, 7.1925, 6.468, 5.985, 5.0505,
					5.796, 4.2525, 4.536, 3.864, 4.7355, 3.864, 4.2525, 5.166,
					6.762, 6.279, 6.762, 8.1165, 6.5205, 7.3395, 6.762, 6.6675,
					6.762, 6.468, 6.0375, 6.5205, 7.245, 7.266, 7.056, 5.4075,
					5.817, 5.2185, 5.3655, 5.796, 16.884, 17.703, 18.2175,
					19.7085, 19.761, 19.761, 7.9695, 7.4865, 6.8145, 6.468,
					6.5205, 6.279, 6.279, 6.279, 6.762, 6.279, 5.5335, 4.704,
					4.704, 4.704, 4.5885, 4.2945, 4.5675, 3.9585, 4.347, 3.717,
					4.704, 4.704, 6.8565, 6.762, 5.502, 7.245, 6.762, 7.0245,
					6.5205, 6.5205, 6.8565, 6.279, 6.0375, 7.1505, 7.0035,
					7.245, 7.0035, 5.166, 5.796, 5.166, 4.9035, 5.5545, 16.716,
					17.997, 18.2175, 19.8555, 20.0025, 20.0025, 8.505, 8.1165,
					7.539, 7.056, 7.245, 7.245, 8.022, 7.4865, 7.4865, 7.3395,
					7.728, 5.985, 4.83, 3.675, 5.313, 2.898, 4.83, 3.381,
					3.9375, 2.604, 2.0265, 2.3205, 3.087, 5.502, 5.439, 7.4865,
					6.6675, 7.0035, 6.573, 5.4075, 6.5205, 5.67, 5.313, 4.83,
					5.5545, 5.0715, 5.0715, 3.381, 3.57, 1.932, 1.932, 3.192,
					14.931, 16.863, 16.863, 18.5535, 18.795, 17.829, 7.245,
					5.9745, 7.0035, 5.502, 7.0035, 6.0375, 6.0375, 3.6225,
					4.83, 2.898, 2.898, 1.449, 0.483, 0.2625, 0.483, -0.483,
					0.3885, -2.1, -0.189, -2.121, -1.911, -2.289, -1.8375,
					0.483, -1.2075, 1.6695, -0.483, 1.8375, 0.5775, 1.932,
					1.0185, 1.092, 1.155, 2.3205, 4.4205, 3.99, 5.0715, 4.053,
					4.4415, 3.864, 4.347, 5.796, 17.199, 19.761, 19.761,
					21.231, 20.9685, 21.399, 9.366, 8.862, 8.694, 8.4525,
					8.4525, 8.4525, 9.0825, 8.4525, 8.505, 7.245, 6.0375,
					3.843, 4.158, 3.99, 3.6225, 2.8035, 2.8035, 2.6565, 2.898,
					2.6565, 2.6565, 2.898, 2.6565, 3.57, 2.6565, 4.158, 2.6565,
					4.83, 5.796, 6.762, 7.434, 7.4865, 6.741, 6.762, 7.728,
					7.728, 7.4865, 6.447, 6.6675, 5.46, 5.46, 6.762, 18.501,
					20.244, 19.278, 20.601, 20.244, 20.244, 9.051, 8.211,
					8.694, 8.211, 9.051, 8.9355, 8.9355, 7.728, 7.245, 5.5545,
					6.468, 4.83, 4.83, 5.313, 5.649, 4.83, 5.649, 4.83, 5.7015,
					4.956, 6.0375, 6.0375, 7.728, 6.5205, 7.119, 8.211, 6.6675,
					7.728, 6.5205, 6.741, 6.762, 6.909, 6.5415, 7.728, 7.245,
					7.245, 7.3395, 5.922, 6.3735, 5.7225, 5.0715, 6.0375,
					16.863, 19.0365, 20.244, 20.727, 20.9685, 20.727, 8.19,
					8.19, 6.8565, 6.8565, 6.573, 6.573, 6.426, 6.279, 6.279,
					5.607, 5.8485, 5.67, 5.7015, 5.67, 5.67, 5.67, 5.67, 5.67,
					5.67, 5.67, 6.5205, 6.279, 6.279, 5.985, 6.279, 7.728,
					7.728, 8.211, 8.211, 7.8225, 7.8225, 7.6335, 7.245, 7.245,
					7.4865, 7.245, 7.4865, 6.279, 6.279, 6.279, 5.607, 6.279,
					17.64, 20.244, 19.278, 21.21, 21.399, 21.21, 9.66, 8.211,
					7.9695, 6.5205, 8.022, 6.762, 6.762, 5.796, 6.762, 6.888,
					6.6675, 5.796, 5.8485, 5.985, 6.2265, 5.0505, 5.124,
					4.9035, 6.279, 5.019, 6.6885, 6.09, 6.573, 6.762, 6.762,
					9.177, 8.547, 9.303, 8.694, 9.1035, 8.6415, 7.917, 7.917,
					8.211, 7.728, 7.728, 7.854, 6.762, 7.6335, 7.1715, 6.5415,
					6.615, 17.703, 20.0025, 18.795, 19.761, 20.1495, 20.0025,
					6.8145, 7.3395, 8.211, 7.0035, 7.119, 6.762, 7.707, 5.2185
				]
			)
		})
		forecast_patch = unittest.mock.patch(
			"send_bulletin.price_forecasting.gen_price_forecast",
			mock_gen_price_forecast
		)
		# Mock the smtp library
		mock_smtp_server = unittest.mock.Mock()
		mock_smtp_ssl = unittest.mock.Mock(
			return_value=contextlib.nullcontext(mock_smtp_server)
		)
		smtp_patch = unittest.mock.patch(
			"send_bulletin.smtplib.SMTP_SSL",
			mock_smtp_ssl
		)
		# Run main()
		with (
			time_patch, now_patch, config_patch,
			data_patch, forecast_patch, smtp_patch
		):
			send_bulletin.main()
		# Check email content
		mock_smtp_server.send_message.assert_called_once()
		self.assertEqual(len(mock_smtp_server.send_message.call_args.args), 1)
		msg = mock_smtp_server.send_message.call_args.args[0]
		self.assertTrue(msg.get_all("To"), ["recipient@example.com"])
		self.assertEqual(msg.get_all("From"), ["sender@gmail.com"])
		self.assertEqual(
			msg.get_all("Subject"),
			["Agile Octopus Bulletin (2020-05-31)"]
		)
		self.assertEqual(
			msg.get_body().get_payload(),
			"Agile Octopus Bulletin 2020-05-31\n"
			"\n"
			"\n"
			"Consumption (excluding standing charge) as of 00:00 this morning:\n"
			"Yesterday           1.000kWh for £0.0200 (2.00p/kWh)\n"
			"Since Monday        3.000kWh for £0.0400 (1.33p/kWh)\n"
			"Since last bill     5.000kWh for £0.0600 (1.20p/kWh)\n"
			"Since January bill  7.000kWh for £0.0800 (1.14p/kWh)\n"
			"All time            9.000kWh for £0.1000 (1.11p/kWh)\n"
			"\n"
			"\n"
			"The cheapest 0.5 hour window starts at 00:30 (average -1.00p/kWh)\n"
			"The cheapest 1 hour window starts at 00:00 (average 1.55p/kWh)\n"
			"The cheapest 1.5 hour window starts at 23:30 (average 2.40p/kWh)\n"
			"The cheapest 2 hour window starts at 23:30 (average 2.89p/kWh)\n"
			"The cheapest 2.5 hour window starts at 00:30 (average 2.57p/kWh)\n"
			"The cheapest 3 hour window starts at 00:30 (average 2.80p/kWh)\n"
			"The cheapest 4 hour window starts at 00:00 (average 3.09p/kWh)\n"
			"The cheapest 6 hour window starts at 23:30 (average 3.41p/kWh)\n"
			"\n"
			"\n"
			"The Agile Octopus electricity rates from 23:00 tonight are as follows:\n"
			"23:00     5.99    ++++++++++\n"
			"23:30     4.11    +++++++\n"
			"00:00     4.11    +++++++\n"
			"00:30    -1.00    --\n"
			"01:00     4.35    ++++++++\n"
			"01:30     4.59    ++++++++\n"
			"02:00     4.92    +++++++++\n"
			"02:30     0.00    \n"
			"03:00     3.96    +++++++\n"
			"03:30     3.77    +++++++\n"
			"04:00     4.35    ++++++++\n"
			"04:30     4.20    ++++++++\n"
			"05:00     3.62    +++++++\n"
			"05:30     4.44    ++++++++\n"
			"06:00     6.06    ++++++++++\n"
			"06:30     6.43    ++++++++++\n"
			"07:00     6.28    ++++++++++\n"
			"07:30     7.25    +++++++++++\n"
			"08:00     7.97    ++++++++++++\n"
			"08:30     7.97    ++++++++++++\n"
			"09:00     7.73    ++++++++++++\n"
			"09:30     7.34    ++++++++++++\n"
			"10:00     7.25    +++++++++++\n"
			"10:30     6.76    +++++++++++\n"
			"11:00     6.57    +++++++++++\n"
			"11:30     7.06    +++++++++++\n"
			"12:00     7.73    ++++++++++++\n"
			"12:30     7.54    ++++++++++++\n"
			"13:00     7.25    +++++++++++\n"
			"13:30     5.80    ++++++++++\n"
			"14:00     5.31    +++++++++\n"
			"14:30     4.64    ++++++++\n"
			"15:00     4.25    ++++++++\n"
			"15:30     4.88    ++++++++\n"
			"16:00    16.29    ++++++++++++++++++++\n"
			"16:30    17.81    +++++++++++++++++++++\n"
			"17:00    18.61    ++++++++++++++++++++++\n"
			"17:30    19.28    ++++++++++++++++++++++\n"
			"18:00    20.43    +++++++++++++++++++++++\n"
			"18:30    20.49    +++++++++++++++++++++++\n"
			"19:00     9.18    ++++++++++++++\n"
			"19:30     8.94    +++++++++++++\n"
			"20:00     8.69    +++++++++++++\n"
			"20:30     8.57    +++++++++++++\n"
			"21:00     8.69    +++++++++++++\n"
			"21:30     8.45    +++++++++++++\n"
			"22:00     7.97    ++++++++++++\n"
			"22:30     7.25    +++++++++++\n"
			"\n"
			"\n"
			"\n"
			"Calculations took 0.00 seconds.\n"
		)
		# We won't check the attachments in full, just that they exist
		# and are of a sensible size
		attachments = list(msg.iter_attachments())
		self.assertEqual(len(attachments), 2)
		self.assertGreater(len(attachments[0].get_payload()), 30000)
		self.assertGreater(len(attachments[1].get_payload()), 10000)
		# Check smtplib calls
		mock_smtp_server.login.assert_called_once_with(
			"sender@gmail.com", "password1234"
		)
		mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
