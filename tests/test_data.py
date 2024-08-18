import unittest
import unittest.mock
import datetime
import zoneinfo
import os
import urllib
import urllib.request
import io
import contextlib

import data
import misc


CONFIG_PATCH = unittest.mock.patch.multiple(
	data.config,
	DATA_DIRECTORY = "dir",
	TEMPERATURE_FILE = "temp_filename",
	PRICE_FILE = "price_filename",
	NAT_GRID_DEMAND_FILE = "demand_filename",
	NAT_GRID_WIND_FILE = "wind_filename",
	FILE_DATETIME_FORMAT = r"%Y-%m-%dT%H:%M:%S",
	METOFFICE_API_KEY = "METOFF_API_KEY",
	LATITUDE = "LATITUDE",
	LONGITUDE = "LONGITUDE",
	OCTOPUS_AGILE_PRODUCT_CODE = "AGILE-FLEX-22-11-25",
	OCTOPUS_AGILE_REGION_CODE = "A",
	OCTOPUS_API_KEY = "OCTOPUS_API_KEY",
	OCTOPUS_METER_SERIAL_NO = "OCTOPUS_METER_SERIAL_NO",
	OCTOPUS_MPAN = "OCTOPUS_MPAN",
)


class TestGetTemperatures(unittest.TestCase):
	def test_get_hourly_temperatures(self):
		utc = datetime.timezone.utc
		start_time = datetime.datetime(2020,1,1,tzinfo=utc)
		mock_load_csv_ts = unittest.mock.Mock(return_value={
			k:str(v)
			for k,v in zip(misc.datetime_sequence(start_time, 1), range(48))
		})
		csv_time_series_patch = unittest.mock.patch(
			"data.load_csv_time_series",
			mock_load_csv_ts
		)
		with CONFIG_PATCH, csv_time_series_patch:
			self.assertEqual(
				data.get_hourly_temperatures(start_time),
				list(range(48))
			)
			mock_load_csv_ts.assert_called_once_with(
				os.path.normpath("dir/temp_filename"),
				"Time", "Temperature (°C)", r"%Y-%m-%dT%H:%M:%S"
			)
			self.assertEqual(
				data.get_hourly_temperatures(
					datetime.datetime(2020,1,2,tzinfo=utc)
				),
				list(range(24, 48))
			)
			self.assertEqual(
				data.get_hourly_temperatures(
					datetime.datetime(2020,1,2,23,tzinfo=utc)
				),
				[47]
			)
			with self.assertRaises(RuntimeError):
				data.get_hourly_temperatures(
					datetime.datetime(2020,1,3,tzinfo=utc)
				)
			with self.assertRaises(RuntimeError):
				data.get_hourly_temperatures(
					datetime.datetime(2019,12,31,23,tzinfo=utc)
				)


METOFF_HOURLY_TEMP_API_RESPONSE = b"""{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [
          -0.12480000000000001,
          51.5081,
          11
        ]
      },
      "properties": {
        "location": {
          "name": "London"
        },
        "requestPointDistance": 221.7751,
        "modelRunDate": "2020-01-01T14:00Z",
        "timeSeries": [
          {
            "time": "2020-01-01T14:00Z",
            "screenTemperature": 10,
            "maxScreenAirTemp": 10.1,
            "minScreenAirTemp": 9.9,
            "screenDewPointTemperature": 5,
            "feelsLikeTemperature": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "max10mWindGust": 0,
            "visibility": 10000,
            "screenRelativeHumidity": 50,
            "mslp": 100000,
            "uvIndex": 0,
            "significantWeatherCode": 0,
            "precipitationRate": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "probOfPrecipitation": 0
          },
          {
            "time": "2020-01-01T15:00Z",
            "screenTemperature": 11,
            "maxScreenAirTemp": 11.1,
            "minScreenAirTemp": 10.9,
            "screenDewPointTemperature": 5,
            "feelsLikeTemperature": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "max10mWindGust": 0,
            "visibility": 10000,
            "screenRelativeHumidity": 50,
            "mslp": 100000,
            "uvIndex": 0,
            "significantWeatherCode": 0,
            "precipitationRate": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "probOfPrecipitation": 0
          },
          {
            "time": "2020-01-01T16:00Z",
            "screenTemperature": 12,
            "maxScreenAirTemp": 12.1,
            "minScreenAirTemp": 11.9,
            "screenDewPointTemperature": 5,
            "feelsLikeTemperature": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "max10mWindGust": 0,
            "visibility": 10000,
            "screenRelativeHumidity": 50,
            "mslp": 100000,
            "uvIndex": 0,
            "significantWeatherCode": 0,
            "precipitationRate": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "probOfPrecipitation": 0
          },
          {
            "time": "2020-01-01T17:00Z",
            "screenTemperature": 13,
            "maxScreenAirTemp": 13.1,
            "minScreenAirTemp": 12.9,
            "screenDewPointTemperature": 5,
            "feelsLikeTemperature": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "max10mWindGust": 0,
            "visibility": 10000,
            "screenRelativeHumidity": 50,
            "mslp": 100000,
            "uvIndex": 0,
            "significantWeatherCode": 0,
            "precipitationRate": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "probOfPrecipitation": 0
          }
        ]
      }
    }
  ],
  "parameters": "<parameters_placeholder>"
}"""
METOFF_3_HOURLY_TEMP_API_RESPONSE = b"""{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [
          -0.12480000000000001,
          51.5081,
          11
        ]
      },
      "properties": {
        "location": {
          "name": "London"
        },
        "requestPointDistance": 221.7751,
        "modelRunDate": "2020-01-01T14:00Z",
        "timeSeries": [
          {
            "time": "2020-01-01T12:00Z",
            "maxScreenAirTemp": 8.1,
            "minScreenAirTemp": 7.9,
            "max10mWindGust": 0,
            "significantWeatherCode": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "visibility": 10000,
            "mslp": 100000,
            "screenRelativeHumidity": 50,
            "feelsLikeTemp": 0,
            "uvIndex": 0,
            "probOfPrecipitation": 0,
            "probOfSnow": 0,
            "probOfHeavySnow": 0,
            "probOfRain": 0,
            "probOfHeavyRain": 0,
            "probOfHail": 0,
            "probOfSferics": 0
          },
          {
            "time": "2020-01-01T15:00Z",
            "maxScreenAirTemp": 11.1,
            "minScreenAirTemp": 10.9,
            "max10mWindGust": 0,
            "significantWeatherCode": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "visibility": 10000,
            "mslp": 100000,
            "screenRelativeHumidity": 50,
            "feelsLikeTemp": 0,
            "uvIndex": 0,
            "probOfPrecipitation": 0,
            "probOfSnow": 0,
            "probOfHeavySnow": 0,
            "probOfRain": 0,
            "probOfHeavyRain": 0,
            "probOfHail": 0,
            "probOfSferics": 0
          },
          {
            "time": "2020-01-01T18:00Z",
            "maxScreenAirTemp": 14.1,
            "minScreenAirTemp": 13.9,
            "max10mWindGust": 0,
            "significantWeatherCode": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "visibility": 10000,
            "mslp": 100000,
            "screenRelativeHumidity": 50,
            "feelsLikeTemp": 0,
            "uvIndex": 0,
            "probOfPrecipitation": 0,
            "probOfSnow": 0,
            "probOfHeavySnow": 0,
            "probOfRain": 0,
            "probOfHeavyRain": 0,
            "probOfHail": 0,
            "probOfSferics": 0
          },
          {
            "time": "2020-01-01T21:00Z",
            "maxScreenAirTemp": 17.1,
            "minScreenAirTemp": 16.9,
            "max10mWindGust": 0,
            "significantWeatherCode": 0,
            "totalPrecipAmount": 0,
            "totalSnowAmount": 0,
            "windSpeed10m": 0,
            "windDirectionFrom10m": 0,
            "windGustSpeed10m": 0,
            "visibility": 10000,
            "mslp": 100000,
            "screenRelativeHumidity": 50,
            "feelsLikeTemp": 0,
            "uvIndex": 0,
            "probOfPrecipitation": 0,
            "probOfSnow": 0,
            "probOfHeavySnow": 0,
            "probOfRain": 0,
            "probOfHeavyRain": 0,
            "probOfHail": 0,
            "probOfSferics": 0
          }
        ]
      }
    }
  ],
  "parameters": "<parameters_placeholder>"
}"""

class TestUpdateTemperatures(unittest.TestCase):

	def setUp(self):
		mock_response_1 = unittest.mock.mock_open(
			read_data=METOFF_HOURLY_TEMP_API_RESPONSE
		)
		mock_response_2 = unittest.mock.mock_open(
			read_data=METOFF_3_HOURLY_TEMP_API_RESPONSE
		)
		self.mock_urlopen = unittest.mock.Mock(
			side_effect=[mock_response_1(), mock_response_2()]
		)
		self.urlopen_patch = unittest.mock.patch(
			"data.urllib.request.urlopen",
			self.mock_urlopen
		)
		self.mock_append_csv = unittest.mock.Mock()
		self.append_csv_patch = unittest.mock.patch(
			"data.append_csv",
			self.mock_append_csv
		)

	def test_update_temperature_forecast(self):
		with CONFIG_PATCH, self.urlopen_patch, self.append_csv_patch:
			data.update_temperature_forecast()
		# Check urlopen() calls
		self.assertEqual(len(self.mock_urlopen.call_args_list), 2)
		self.assertEqual(len(self.mock_urlopen.call_args_list[0].args), 1)
		self.assertIs(
			type(self.mock_urlopen.call_args_list[0].args[0]),
			urllib.request.Request
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[0].args[0].get_full_url(),
			"https://data.hub.api.metoffice.gov.uk/sitespecific/"
			"v0/point/hourly?includeLocationName=true&"
			"latitude=LATITUDE&longitude=LONGITUDE"
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[0].args[0].get_header("Apikey"),
			"METOFF_API_KEY"
		)
		self.assertEqual(len(self.mock_urlopen.call_args_list[1].args), 1)
		self.assertIs(
			type(self.mock_urlopen.call_args_list[1].args[0]),
			urllib.request.Request
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[1].args[0].get_full_url(),
			"https://data.hub.api.metoffice.gov.uk/sitespecific/"
			"v0/point/three-hourly?includeLocationName=true&"
			"latitude=LATITUDE&longitude=LONGITUDE"
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[1].args[0].get_header("Apikey"),
			"METOFF_API_KEY"
		)
		# Check append_csv() call
		self.mock_append_csv.assert_called_once()
		self.assertEqual(
			self.mock_append_csv.call_args.args[0],
			os.path.normpath("dir/temp_filename")
		)
		self.assertEqual(
			list(self.mock_append_csv.call_args.args[1]),
			[
				("2020-01-01T14:00:00", 10),
				("2020-01-01T15:00:00", 11),
				("2020-01-01T16:00:00", 12),
				("2020-01-01T17:00:00", 13),
				("2020-01-01T18:00:00", 14),
				("2020-01-01T21:00:00", 17),
			]
		)
		self.assertEqual(
			self.mock_append_csv.call_args.args[2:],
			(
				["Time", "Temperature (°C)"],
				"Time",
				True
			)
		)


NAT_GRID_DEMAND_API_RESPONSE = (
	b'"DATE","CTIME","GDATETIME","NATIONALDEMAND"\r\n'
	b'"2024-06-01",30,"2024-05-31T23:30:00",20000\r\n'
	b'"2024-06-01",100,"2024-06-01T00:00:00",21000\r\n'
	b'"2024-06-01",130,"2024-06-01T00:30:00",22000\r\n'
	b'"2024-06-01",200,"2024-06-01T01:00:00",23000\r\n'
	b'"2024-06-01",230,"2024-06-01T01:30:00",24000\r\n'
	b'\r\n'
)

class TestUpdateDemandForecast(unittest.TestCase):

	def setUp(self):
		self.mock_urlopen = unittest.mock.mock_open(
			read_data=NAT_GRID_DEMAND_API_RESPONSE
		)
		self.urlopen_patch = unittest.mock.patch(
			"data.urllib.request.urlopen",
			self.mock_urlopen
		)
		self.mock_append_csv = unittest.mock.Mock()
		self.append_csv_patch = unittest.mock.patch(
			"data.append_csv",
			self.mock_append_csv
		)

	def test_update_nat_grid_demand_forecast(self):
		with CONFIG_PATCH, self.urlopen_patch, self.append_csv_patch:
			data.update_nat_grid_demand_forecast()
		# Check urlopen() call
		self.mock_urlopen.assert_called_once_with(
			"https://api.nationalgrideso.com/dataset/"
			"633daec6-3e70-444a-88b0-c4cef9419d40/resource/"
			"7c0411cd-2714-4bb5-a408-adb065edf34d/download/"
			"ng-demand-14da-hh.csv"
		)
		# Check append_csv() call
		self.mock_append_csv.assert_called_once()
		self.assertEqual(
			self.mock_append_csv.call_args.args[0],
			os.path.normpath("dir/demand_filename")
		)
		self.assertEqual(
			list(self.mock_append_csv.call_args.args[1]),
			[
				("2024-05-31T23:30:00", 20.5),
				("2024-06-01T00:00:00", 21.5),
				("2024-06-01T00:30:00", 22.5),
				("2024-06-01T01:00:00", 23.5),
			]
		)
		self.assertEqual(
			self.mock_append_csv.call_args.args[2:],
			(
				["Time", "Demand / GW"],
				"Time",
				True
			)
		)


NAT_GRID_WIND_API_RESPONSE = (
	b'"Datetime","Date","Settlement_period","Capacity","Wind_Forecast","ForecastDatetime"\r\n'
	b'"2024-06-01T12:00:00Z","2024-06-01",26,20000,1000,"2024-05-31T17:09:00Z"\r\n'
	b'"2024-06-01T12:30:00Z","2024-06-01",27,20000,2000,"2024-05-31T17:09:00Z"\r\n'
	b'"2024-06-01T13:00:00Z","2024-06-01",28,20000,3000,"2024-05-31T17:09:00Z"\r\n'
	b'"2024-06-01T13:30:00Z","2024-06-01",29,20000,4000,"2024-05-31T17:09:00Z"\r\n'
	b'"2024-06-01T14:00:00Z","2024-06-01",30,20000,5000,"2024-05-31T17:09:00Z"\r\n'
	b'\r\n'
)

class TestUpdateWindForecast(unittest.TestCase):

	def setUp(self):
		self.mock_urlopen = unittest.mock.mock_open(
			read_data=NAT_GRID_WIND_API_RESPONSE
		)
		self.urlopen_patch = unittest.mock.patch(
			"data.urllib.request.urlopen",
			self.mock_urlopen
		)
		self.mock_append_csv = unittest.mock.Mock()
		self.append_csv_patch = unittest.mock.patch(
			"data.append_csv",
			self.mock_append_csv
		)

	def test_update_nat_grid_wind_forecast(self):
		with CONFIG_PATCH, self.urlopen_patch, self.append_csv_patch:
			data.update_nat_grid_wind_forecast()
		# Check urlopen() call
		self.mock_urlopen.assert_called_once_with(
			"https://api.nationalgrideso.com/dataset/"
			"2f134a4e-92e5-43b8-96c3-0dd7d92fcc52/resource/"
			"93c3048e-1dab-4057-a2a9-417540583929/download/"
			"14dawindforecast.csv"
		)
		# Check append_csv() call
		self.mock_append_csv.assert_called_once()
		self.assertEqual(
			self.mock_append_csv.call_args.args[0],
			os.path.normpath("dir/wind_filename")
		)
		self.assertEqual(
			list(self.mock_append_csv.call_args.args[1]),
			[
				("2024-06-01T12:00:00", 1),
				("2024-06-01T12:30:00", 2),
				("2024-06-01T13:00:00", 3),
				("2024-06-01T13:30:00", 4),
				("2024-06-01T14:00:00", 5),
			]
		)
		self.assertEqual(
			self.mock_append_csv.call_args.args[2:],
			(
				["Time", "Wind Generation / GW"],
				"Time",
				True
			)
		)


class TestGetPrices(unittest.TestCase):
	def test_get_agile_prices(self):
		utc = datetime.timezone.utc
		start_time = datetime.datetime(2020,1,1,tzinfo=utc)
		mock_midnight_tonight = lambda *args: start_time
		time_patch = unittest.mock.patch(
			"data.misc.midnight_tonight",
			mock_midnight_tonight
		)
		mock_load_csv_ts = unittest.mock.Mock(return_value={
			k:str(v)
			for k,v in zip(misc.datetime_sequence(start_time, .5), range(48))
		})
		csv_time_series_patch = unittest.mock.patch(
			"data.load_csv_time_series",
			mock_load_csv_ts
		)
		with CONFIG_PATCH, time_patch, csv_time_series_patch:
			self.assertEqual(data.get_agile_prices(), list(range(48)))
			mock_load_csv_ts.assert_called_once_with(
				os.path.normpath("dir/price_filename"),
				"Start Time", "Price (p/kWh)", r"%Y-%m-%dT%H:%M:%S"
			)


OCTOPUS_PRICES_API_RESPONSE_0 = """{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}"""
OCTOPUS_PRICES_API_RESPONSE_1 = """{
  "count": 4,
  "next": "https://example.com/next_page",
  "previous": null,
  "results": [
    {
      "value_exc_vat": 10,
      "value_inc_vat": 10.5,
      "valid_from": "2020-06-01T10:30:00Z",
      "valid_to": "2020-06-01T11:00:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 11,
      "value_inc_vat": 11.55,
      "valid_from": "2020-06-01T10:00:00Z",
      "valid_to": "2020-06-01T10:30:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 12,
      "value_inc_vat": 12.6,
      "valid_from": "2020-06-01T09:30:00Z",
      "valid_to": "2020-06-01T10:00:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 13,
      "value_inc_vat": 13.65,
      "valid_from": "2020-06-01T09:00:00Z",
      "valid_to": "2020-06-01T09:30:00Z",
      "payment_method": null
    }
  ]
}"""
OCTOPUS_PRICES_API_RESPONSE_2 = """{
  "count": 4,
  "next": null,
  "previous": null,
  "results": [
    {
      "value_exc_vat": 14,
      "value_inc_vat": 14.7,
      "valid_from": "2020-06-01T08:30:00Z",
      "valid_to": "2020-06-01T09:00:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 15,
      "value_inc_vat": 15.75,
      "valid_from": "2020-06-01T08:00:00Z",
      "valid_to": "2020-06-01T08:30:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 16,
      "value_inc_vat": 16.8,
      "valid_from": "2020-06-01T07:30:00Z",
      "valid_to": "2020-06-01T08:00:00Z",
      "payment_method": null
    },
    {
      "value_exc_vat": 17,
      "value_inc_vat": 17.85,
      "valid_from": "2020-06-01T07:00:00Z",
      "valid_to": "2020-06-01T07:30:00Z",
      "payment_method": null
    }
  ]
}"""

class TestUpdatePrices(unittest.TestCase):

	def setUp(self):
		mock_response_1 = unittest.mock.mock_open(
			read_data=OCTOPUS_PRICES_API_RESPONSE_0
		)
		mock_response_2 = unittest.mock.mock_open(
			read_data=OCTOPUS_PRICES_API_RESPONSE_2
		)
		self.mock_urlopen = unittest.mock.Mock(
			side_effect=[mock_response_1(), mock_response_2()]
		)
		self.urlopen_patch = unittest.mock.patch(
			"data.urllib.request.urlopen",
			self.mock_urlopen
		)
		self.mock_append_csv = unittest.mock.Mock()
		self.append_csv_patch = unittest.mock.patch(
			"data.append_csv",
			self.mock_append_csv
		)
		self.mock_sleep = unittest.mock.Mock()
		self.sleep_patch = unittest.mock.patch(
			"data.time.sleep",
			self.mock_sleep
		)
		tonight = datetime.datetime(2020,1,1,tzinfo=datetime.timezone.utc)
		self.tonight_patch = unittest.mock.patch(
			"data.misc.midnight_tonight",
			lambda *args: tonight
		)

	def test_update_agile_prices(self):
		with (
			CONFIG_PATCH, self.urlopen_patch, self.append_csv_patch,
			self.tonight_patch, self.sleep_patch
		):
			data.update_agile_prices(wait=True)
		# Check urlopen() calls
		self.assertEqual(len(self.mock_urlopen.call_args_list), 2)
		self.assertEqual(
			self.mock_urlopen.call_args_list[0].args,
			(
				"https://api.octopus.energy/v1/products/"
				"AGILE-FLEX-22-11-25/electricity-tariffs/"
				"E-1R-AGILE-FLEX-22-11-25-A/standard-unit-rates"
				"?period_from=2019-12-31T23:00:00Z",
			)
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[1].args,
			(
				"https://api.octopus.energy/v1/products/"
				"AGILE-FLEX-22-11-25/electricity-tariffs/"
				"E-1R-AGILE-FLEX-22-11-25-A/standard-unit-rates"
				"?period_from=2019-12-31T23:00:00Z",
			)
		)
		# Check append_csv() call
		self.mock_append_csv.assert_called_once()
		self.assertEqual(
			self.mock_append_csv.call_args.args[0],
			os.path.normpath("dir/price_filename")
		)
		self.assertEqual(
			list(self.mock_append_csv.call_args.args[1]),
			[
				("2020-06-01T07:00:00", 17.85),
				("2020-06-01T07:30:00", 16.8),
				("2020-06-01T08:00:00", 15.75),
				("2020-06-01T08:30:00", 14.7),
			]
		)
		self.assertEqual(
			self.mock_append_csv.call_args.args[2:],
			(
				["Start Time", "Price (p/kWh)"],
				"Start Time"
			)
		)
		# Check time.sleep() calls
		self.mock_sleep.assert_called_once_with(600)


OCTOPUS_CONSUMPTION_API_RESPONSE_1 = """{
  "count": 4,
  "next": "https://example.com/next_page",
  "previous": null,
  "results": [
    {
      "consumption": 0.1,
      "interval_start": "2020-06-01T11:30:00+01:00",
      "interval_end": "2020-06-01T12:00:00+01:00"
    },
    {
      "consumption": 0.2,
      "interval_start": "2020-06-01T11:00:00+01:00",
      "interval_end": "2020-06-01T11:30:00+01:00"
    },
    {
      "consumption": 0.3,
      "interval_start": "2020-06-01T10:30:00+01:00",
      "interval_end": "2020-06-01T11:00:00+01:00"
    },
    {
      "consumption": 0.4,
      "interval_start": "2020-06-01T10:00:00+01:00",
      "interval_end": "2020-06-01T10:30:00+01:00"
    }
  ]
}"""
OCTOPUS_CONSUMPTION_API_RESPONSE_2 = """{
  "count": 4,
  "next": null,
  "previous": null,
  "results": [
    {
      "consumption": 0.5,
      "interval_start": "2020-06-01T09:30:00+01:00",
      "interval_end": "2020-06-01T10:00:00+01:00"
    },
    {
      "consumption": 0.6,
      "interval_start": "2020-06-01T09:00:00+01:00",
      "interval_end": "2020-06-01T09:30:00+01:00"
    },
    {
      "consumption": 0.7,
      "interval_start": "2020-06-01T08:30:00+01:00",
      "interval_end": "2020-06-01T09:00:00+01:00"
    },
    {
      "consumption": 0.8,
      "interval_start": "2020-06-01T08:00:00+01:00",
      "interval_end": "2020-06-01T08:30:00+01:00"
    }
  ]
}"""

class TestGetSpend(unittest.TestCase):

	def setUp(self):
		mock_response_1 = unittest.mock.mock_open(
			read_data=OCTOPUS_CONSUMPTION_API_RESPONSE_1
		)
		mock_response_2 = unittest.mock.mock_open(
			read_data=OCTOPUS_CONSUMPTION_API_RESPONSE_2
		)
		mock_response_3 = unittest.mock.mock_open(
			read_data=OCTOPUS_PRICES_API_RESPONSE_1
		)
		mock_response_4 = unittest.mock.mock_open(
			read_data=OCTOPUS_PRICES_API_RESPONSE_2
		)
		self.mock_urlopen = unittest.mock.Mock(side_effect=[
			mock_response_1(), mock_response_2(),
			mock_response_3(), mock_response_4()
		])
		self.urlopen_patch = unittest.mock.patch(
			"data.urllib.request.urlopen",
			self.mock_urlopen
		)

	def test_get_actual_spend(self):
		# Get spend from 08:00 to 13:00 (the last hour of which will have
		# no consumption data)
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		start = datetime.datetime(2020, 6, 1, 8, tzinfo=local_tz)
		end = datetime.datetime(2020, 6, 1, 12, 30, 1, tzinfo=local_tz)
		with CONFIG_PATCH, self.urlopen_patch:
			energy, cost = data.get_actual_spend(start, end)
		# Check return values
		self.assertAlmostEqual(energy, 3.6)
		self.assertAlmostEqual(cost, 55.44)
		# Check urlopen() calls
		self.assertEqual(len(self.mock_urlopen.call_args_list), 4)
		call_0_args = self.mock_urlopen.call_args_list[0].args
		self.assertEqual(len(call_0_args), 1)
		self.assertIs(
			type(call_0_args[0]),
			urllib.request.Request
		)
		self.assertEqual(
			call_0_args[0].get_full_url(),
			"https://api.octopus.energy/v1/electricity-meter-points/"
			"OCTOPUS_MPAN/meters/OCTOPUS_METER_SERIAL_NO/consumption/"
			"?page_size=1500&period_from=2020-06-01T07:00Z"
			"&period_to=2020-06-01T11:30Z"
		)
		self.assertEqual(
			call_0_args[0].get_header("Authorization"),
			"Basic T0NUT1BVU19BUElfS0VZOg=="
		)
		call_1_args = self.mock_urlopen.call_args_list[1].args
		self.assertEqual(len(call_1_args), 1)
		self.assertIs(
			type(call_1_args[0]),
			urllib.request.Request
		)
		self.assertEqual(
			call_1_args[0].get_full_url(),
			"https://example.com/next_page"
		)
		self.assertEqual(
			call_1_args[0].get_header("Authorization"),
			"Basic T0NUT1BVU19BUElfS0VZOg=="
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[2].args,
			(
				"https://api.octopus.energy/v1/products/"
				"AGILE-FLEX-22-11-25/electricity-tariffs/"
				"E-1R-AGILE-FLEX-22-11-25-A/standard-unit-rates"
				"?page_size=1500&period_from=2020-06-01T07:00Z"
				"&period_to=2020-06-01T12:00Z",
			)
		)
		self.assertEqual(
			self.mock_urlopen.call_args_list[3].args,
			("https://example.com/next_page",)
		)


EXAMPLE_CSV = (
	"Header_1,Header_2,Header_3,Header_4\r\n"
	"2020-01-01T00:00:00,1,2,3\r\n"
	"2020-01-01T00:00:00,100,0,0\r\n"
	"2020-01-01T00:30:00,4,5,6\r\n"
	"2020-01-01T01:00:00,7,8,9\r\n"
	"2020-01-01T01:30:00,10,11,12\r\n"
)

class TestAppendCSV(unittest.TestCase):

	def setUp(self):
		self.mock_reader = io.StringIO(EXAMPLE_CSV)
		self.mock_writer = io.StringIO(EXAMPLE_CSV)
		self.mock_open = unittest.mock.Mock(side_effect=[
			contextlib.nullcontext(self.mock_reader),
			contextlib.nullcontext(self.mock_writer)
		])
		self.open_patch = unittest.mock.patch("builtins.open", self.mock_open)
		self.new_rows_arg = [
			["2020-01-01T01:30:00",13,14,{15}],
			["2020-01-01T02:30:00",16,17,{18}],
			["2020-01-01T02:00:00",19,20,{21}],
		]

	def test_append_csv(self):
		with self.open_patch:
			data.append_csv(
				"file_path",
				self.new_rows_arg,
				["Header_1", "Header_2", "Header_4", "Header_5"],
			)
		self.assertEqual(len(self.mock_open.call_args_list), 2)
		self.assertEqual(
			self.mock_open.call_args_list[0],
			unittest.mock.call("file_path", "r", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_open.call_args_list[1],
			unittest.mock.call("file_path", "w", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_writer.getvalue(),
			"Header_1,Header_2,Header_3,Header_4,Header_5\r\n"
			"2020-01-01T00:00:00,1,2,3,\r\n"
			"2020-01-01T00:00:00,100,0,0,\r\n"
			"2020-01-01T00:30:00,4,5,6,\r\n"
			"2020-01-01T01:00:00,7,8,9,\r\n"
			"2020-01-01T01:30:00,10,11,12,\r\n"
			"2020-01-01T01:30:00,13,,14,{15}\r\n"
			"2020-01-01T02:30:00,16,,17,{18}\r\n"
			"2020-01-01T02:00:00,19,,20,{21}\r\n"
		)

	def test_ignore_duplicates(self):
		with self.open_patch:
			data.append_csv(
				"file_path",
				self.new_rows_arg,
				["Header_1", "Header_2", "Header_4", "Header_5"],
				"Header_1"
			)
		self.assertEqual(len(self.mock_open.call_args_list), 2)
		self.assertEqual(
			self.mock_open.call_args_list[0],
			unittest.mock.call("file_path", "r", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_open.call_args_list[1],
			unittest.mock.call("file_path", "w", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_writer.getvalue(),
			"Header_1,Header_2,Header_3,Header_4,Header_5\r\n"
			"2020-01-01T00:00:00,1,2,3,\r\n"
			"2020-01-01T00:00:00,100,0,0,\r\n"
			"2020-01-01T00:30:00,4,5,6,\r\n"
			"2020-01-01T01:00:00,7,8,9,\r\n"
			"2020-01-01T01:30:00,10,11,12,\r\n"
			"2020-01-01T02:30:00,16,,17,{18}\r\n"
			"2020-01-01T02:00:00,19,,20,{21}\r\n"
		)

	def test_overwrite_duplicates(self):
		with self.open_patch:
			data.append_csv(
				"file_path",
				self.new_rows_arg,
				["Header_1", "Header_2", "Header_4", "Header_5"],
				"Header_1",
				True
			)
		self.assertEqual(len(self.mock_open.call_args_list), 2)
		self.assertEqual(
			self.mock_open.call_args_list[0],
			unittest.mock.call("file_path", "r", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_open.call_args_list[1],
			unittest.mock.call("file_path", "w", newline="", encoding="utf-8")
		)
		self.assertEqual(
			self.mock_writer.getvalue(),
			"Header_1,Header_2,Header_3,Header_4,Header_5\r\n"
			"2020-01-01T00:00:00,1,2,3,\r\n"
			"2020-01-01T00:00:00,100,0,0,\r\n"
			"2020-01-01T00:30:00,4,5,6,\r\n"
			"2020-01-01T01:00:00,7,8,9,\r\n"
			"2020-01-01T01:30:00,13,,14,{15}\r\n"
			"2020-01-01T02:30:00,16,,17,{18}\r\n"
			"2020-01-01T02:00:00,19,,20,{21}\r\n"
		)

	def test_file_not_found(self):
		mock_writer = io.StringIO()
		mock_open = unittest.mock.Mock(side_effect=[
			FileNotFoundError,
			contextlib.nullcontext(mock_writer)
		])
		open_patch = unittest.mock.patch("builtins.open", mock_open)
		with open_patch:
			data.append_csv(
				"file_path",
				self.new_rows_arg,
				["Header_1", "Header_2", "Header_4", "Header_5"],
			)
		self.assertEqual(len(mock_open.call_args_list), 2)
		self.assertEqual(
			mock_open.call_args_list[0],
			unittest.mock.call("file_path", "r", newline="", encoding="utf-8")
		)
		self.assertEqual(
			mock_open.call_args_list[1],
			unittest.mock.call("file_path", "w", newline="", encoding="utf-8")
		)
		self.assertEqual(
			mock_writer.getvalue(),
			"Header_1,Header_2,Header_4,Header_5\r\n"
			"2020-01-01T01:30:00,13,14,{15}\r\n"
			"2020-01-01T02:30:00,16,17,{18}\r\n"
			"2020-01-01T02:00:00,19,20,{21}\r\n"
		)


class TestCSVTimeSeries(unittest.TestCase):
	def test_load_csv_time_series(self):
		utc = datetime.timezone.utc
		mock_open = unittest.mock.mock_open(read_data=EXAMPLE_CSV)
		open_patch = unittest.mock.patch("builtins.open", mock_open)
		with open_patch:
			self.assertEqual(
				data.load_csv_time_series(
					"file_path",
					"Header_1",
					"Header_2",
					r"%Y-%m-%dT%H:%M:%S"
				),
				{
					datetime.datetime(2020,1,1,0, 0,tzinfo=utc): "100",
					datetime.datetime(2020,1,1,0,30,tzinfo=utc): "4",
					datetime.datetime(2020,1,1,1, 0,tzinfo=utc): "7",
					datetime.datetime(2020,1,1,1,30,tzinfo=utc): "10",
				}
			)
		mock_open.assert_called_once_with(
			"file_path", "r", newline="", encoding="utf-8"
		)
