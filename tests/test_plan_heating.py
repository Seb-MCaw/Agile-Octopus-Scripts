import unittest
import unittest.mock
import datetime
import zoneinfo

import numpy as np

import plan_heating
import tests.mock_cli


class TestHeatingOptions(unittest.TestCase):
	def test_heating_options(self):
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		utc = datetime.timezone.utc
		start_t = datetime.datetime(2020, 10, 24, 23, 00, tzinfo=local_tz)
		end_t_1 = datetime.datetime(2020, 10, 26, 00, 00, tzinfo=local_tz)
		end_t_2 = datetime.datetime(2020, 10, 26, 10, 00, tzinfo=local_tz)
		# Mock config values
		config_patch = unittest.mock.patch.multiple(
			plan_heating.config,
			TIME_ZONE = "Europe/London",
			DIRECT_HEATING_POWER = 5,
			OTHER_HEAT_OUTPUT = 1,
			HEATING_PERIOD_PENALTY = 10,
			IGNORE_INITIAL_TEMP_HOURS = 2,
		)
		# Mock print()
		mock_print = unittest.mock.Mock()
		print_patch = unittest.mock.patch("builtins.print", mock_print)
		# Mock the Building object
		mock_building = unittest.mock.Mock()
		build_from_conf_patch = unittest.mock.patch(
			"plan_heating.heating_simulation.building_from_config",
			lambda: mock_building
		)
		# Mock relevant price_optimisation functions
		def mock_chpst_heat_se(*args):
			if args[7] == 26:
				return (
					[(0,1), (1,1)],                # storage_heat
					[(3,3,1), (4,5,0), (6,7,2)],   # direct_heat
					1,                             # tot_energy
					3,                             # cost
					26,                            # actual_end_t
					("t_1", "T_1", "Q_1", "S_1")   # sim_temps
				)
			else:
				self.assertEqual(args[7], 36)
				return (
					[(0,1), (3,5)],
					[(3,3.5,1), (4,5,0), (6,7,2)],
					2,
					5,
					36,
					("t_2", "T_2", "Q_2", "S_2")
				)
		mock_cheapest_heat = unittest.mock.Mock(side_effect=mock_chpst_heat_se)
		def mock_useful_heat_se(*args):
			if args[5] == 26:
				return .5
			else:
				self.assertEqual(args[5], 36)
				return 1.5
		mock_useful_heat = unittest.mock.Mock(side_effect=mock_useful_heat_se)
		mock_temp_ranges_from_config = unittest.mock.Mock(
			return_value=[(10,0,30), (-10,0,30), (-5,15,25)]
		)
		price_opt_patch = unittest.mock.patch.multiple(
			plan_heating.price_optimisation,
			cheapest_heat=mock_cheapest_heat,
			useful_heat_energy=mock_useful_heat,
			temp_ranges_from_config=mock_temp_ranges_from_config,
		)
		# (note that temp_ranges should be sorted by time, and an initial
		# entry should be prepended to reflect IGNORE_INITIAL_TEMP_HOURS)
		expected_temp_ranges = [(0, -np.inf, np.inf), (2,15,25), (10,0,30)]
		# Call heating_options()
		with config_patch, print_patch, price_opt_patch, build_from_conf_patch:
			options = plan_heating.heating_options(
				[10]*100,
				start_t,
				"start_indoor_temp",
				[end_t_1, end_t_2],
				"prices",
				2
			)
		# Check returned options are correct (should be sorted on "lasts_until")
		self.assertEqual(
			options[0],
			{
				"lasts_until": end_t_1,
				"storage_heat": [
					(
						datetime.datetime(2020,10,24,22,00, tzinfo=utc),
						datetime.datetime(2020,10,24,23,00, tzinfo=utc),
					)
				],
				"direct_heat": [
					(
						datetime.datetime(2020,10,25, 4,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 5,00, tzinfo=utc),
						2
					)
				],
				"total_price": 3,
				"marginal_price": 3,
				"total_energy": 1,
				"marg_tot_energy": 1,
				"useful_energy": .5,
				"marg_usfl_enrgy": .5,
				"t": "t_1",
				"T": "T_1"
			}
		)
		self.assertEqual(
			options[1],
			{
				"lasts_until": end_t_2,
				"storage_heat": [
					(
						datetime.datetime(2020,10,24,22,00, tzinfo=utc),
						datetime.datetime(2020,10,24,23,00, tzinfo=utc),
					),
					(
						datetime.datetime(2020,10,25, 1,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 3,00, tzinfo=utc),
					)
				],
				"direct_heat": [
					(
						datetime.datetime(2020,10,25, 1,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 1,30, tzinfo=utc),
						1
					),
					(
						datetime.datetime(2020,10,25, 4,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 5,00, tzinfo=utc),
						2
					)
				],
				"total_price": 5,
				"marginal_price": 2,
				"total_energy": 2,
				"marg_tot_energy": 1,
				"useful_energy": 1.5,
				"marg_usfl_enrgy": 1,
				"t": "t_2",
				"T": "T_2"
			}
		)
		# Check calls to price_optimisation
		mock_cheapest_heat.assert_has_calls([
			unittest.mock.call(
				mock_building,
				expected_temp_ranges,
				(0, "start_indoor_temp"),
				5,
				[(0, np.inf, 1/24)],
				[10]*100,
				"prices",
				26,
				2,
				10
			),
			unittest.mock.call(
				mock_building,
				expected_temp_ranges,
				(0, "start_indoor_temp"),
				5,
				[(0, np.inf, 1/24)],
				[10]*100,
				"prices",
				36,
				2,
				10
			),
		])
		mock_useful_heat.assert_has_calls([
			unittest.mock.call(
				mock_building,
				expected_temp_ranges,
				(0, "start_indoor_temp"),
				[(0, np.inf, 1/24)],
				[10]*100,
				26,
			),
			unittest.mock.call(
				mock_building,
				expected_temp_ranges,
				(0, "start_indoor_temp"),
				[(0, np.inf, 1/24)],
				[10]*100,
				36,
			),
		])
		mock_temp_ranges_from_config.assert_called_once_with(
			start_t.astimezone(utc), 0, 36
		)
		# Verify that it "Prints its progress to stdout on the current line."
		mock_print.assert_has_calls([
			unittest.mock.call("\r0/2", end=""),
			unittest.mock.call("\r1/2", end=""),
			unittest.mock.call("\r2/2", end=""),
			unittest.mock.call()
		])

	def test_error_on_insufficient_forecast(self):
		with self.assertRaises(ValueError, msg="Insufficient temperature data"):
			plan_heating.heating_options(
				[10]*24,
				datetime.datetime(2000,1,1),
				16,
				[datetime.datetime(2000,1,2)],
				[1]*48,
				1
			)


class TestMain(unittest.TestCase):

	def setUp(self):
		# Mock data (except get_agile_prices())
		self.mock_update_temps = unittest.mock.Mock()
		self.mock_get_temps = unittest.mock.Mock(return_value=list(range(48)))
		self.mock_update_prices = unittest.mock.Mock()
		self.data_patch = unittest.mock.patch.multiple(
			plan_heating.data,
			update_temperature_forecast=self.mock_update_temps,
			get_hourly_temperatures=self.mock_get_temps,
			update_agile_prices=self.mock_update_prices,
		)
		# Mock misc.midnight_tonight()
		utc = datetime.timezone.utc
		self.mock_midnight_tonight = unittest.mock.Mock(
			return_value=datetime.datetime(2020,10,24,23, tzinfo=utc)
		)
		self.time_patch = unittest.mock.patch(
			"plan_heating.misc.midnight_tonight",
			self.mock_midnight_tonight
		)
		# Mock matplotlib
		self.mock_plt = unittest.mock.Mock()
		self.plt_patch = unittest.mock.patch(
			"plan_heating.plt",
			self.mock_plt
		)
		# Mock heating_options()
		self.mock_heat_opts = unittest.mock.Mock(return_value=[
			{
				"lasts_until": datetime.datetime(2020,10,26, tzinfo=utc),
				"storage_heat": [
					(
						datetime.datetime(2020,10,24,22,00, tzinfo=utc),
						datetime.datetime(2020,10,24,23,00, tzinfo=utc),
					)
				],
				"direct_heat": [
					(
						datetime.datetime(2020,10,25, 4,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 5,00, tzinfo=utc),
						2
					)
				],
				"total_price": 3,
				"marginal_price": 3,
				"total_energy": 1,
				"marg_tot_energy": 1,
				"useful_energy": .5,
				"marg_usfl_enrgy": .5,
				"t": np.array([0,1]),
				"T": np.array([2,3])
			},
			{
				"lasts_until": datetime.datetime(2020,10,26,10, tzinfo=utc),
				"storage_heat": [
					(
						datetime.datetime(2020,10,24,22,00, tzinfo=utc),
						datetime.datetime(2020,10,24,23,00, tzinfo=utc),
					),
					(
						datetime.datetime(2020,10,25, 1,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 3,00, tzinfo=utc),
					)
				],
				"direct_heat": [
					(
						datetime.datetime(2020,10,25, 1,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 1,30, tzinfo=utc),
						1
					),
					(
						datetime.datetime(2020,10,25, 4,00, tzinfo=utc),
						datetime.datetime(2020,10,25, 5,00, tzinfo=utc),
						2
					)
				],
				"total_price": 5,
				"marginal_price": 2,
				"total_energy": 2,
				"marg_tot_energy": 1,
				"useful_energy": 1.5,
				"marg_usfl_enrgy": 1,
				"t": np.array([0,1]),
				"T": np.array([2,3])
			}
		])
		self.heat_opts_patch = unittest.mock.patch(
			"plan_heating.heating_options",
			self.mock_heat_opts
		)

	def test_main(self):
		mock_get_prices = unittest.mock.Mock(return_value=list(range(48, 96)))
		prices_patch = unittest.mock.patch(
			"plan_heating.data.get_agile_prices",
			mock_get_prices
		)
		cli_session = tests.mock_cli.MockCLI(
			self,
			[
				"Enter initial indoor temperature (°C):                      ",
				"Times to heat until (days after 00:00 tonight):             ",
				"Enter maximum number of times to run each type of heating:  ",
				(
					"\nFetching prices...\n\nCalculating options:\n\n"
					# "2/2" is not printed because we mocked heating_options()
					"Heating until 00:00 on Monday (1.08 days):\n"
					"    Costs £0.03 (6.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00\n"
					"    Run direct heating at: 2kW for 04:00--05:00\n"
					"    Total energy: 1.0kWh\n"
					"\n"
					"Heating until 10:00 on Monday (1.50 days):\n"
					"    Costs an additional £0.02 (2.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00, 01:00--03:00\n"
					"    Run direct heating at: 1kW for 01:00--01:30, 2kW for 04:00--05:00\n"
					"    Total energy: 2.0kWh\n"
					"\n"
				)
			],
			["20", "1.041666666666, 1.458333333333", "2"]
		)
		with (
			self.data_patch, self.time_patch, self.plt_patch,
			self.heat_opts_patch, prices_patch, cli_session
		):
			plan_heating.main()
		self.mock_update_temps.assert_called_once_with()
		self.mock_get_temps.assert_called_once_with(
			datetime.datetime(2020,10,24,22, tzinfo=datetime.timezone.utc)
		)
		self.mock_update_prices.assert_called_once_with()
		self.mock_update_prices.assert_called_once_with()
		for c in self.mock_midnight_tonight.call_args_list:
			# Verify returning the UTC time is correct
			self.assertTrue(c.args in [(), (False)])
		self.assertEqual(len(self.mock_plt.plot.call_args_list), 2)
		self.assertEqual(
			[
				[[-1,0], [2,3]],
				[[-1,0], [2,3]]
			],
			[
				[list(x) for x in self.mock_plt.plot.call_args_list[0].args],
				[list(x) for x in self.mock_plt.plot.call_args_list[1].args]
			]
		)
		self.assertEqual(
			[
				{"label":f"1.08 days"},
				{"label":f"1.50 days"}
			],
			[
				self.mock_plt.plot.call_args_list[0].kwargs,
				self.mock_plt.plot.call_args_list[1].kwargs
			]
		)
		self.mock_plt.xlabel.assert_called_once()
		self.mock_plt.ylabel.assert_called_once()
		self.mock_plt.legend.assert_called_once()
		self.mock_plt.show.assert_called_once()
		self.mock_heat_opts.assert_called_once_with(
			list(range(48)),
			datetime.datetime(2020,10,24,22,00, tzinfo=datetime.timezone.utc),
			20,
			[
				datetime.datetime(2020,10,26,00, tzinfo=datetime.timezone.utc),
				datetime.datetime(2020,10,26,10, tzinfo=datetime.timezone.utc),
			],
			list(range(48,96)),
			2
		)

	def test_insufficient_temps(self):
		mock_get_prices = unittest.mock.Mock(return_value=list(range(48, 96)))
		prices_patch = unittest.mock.patch(
			"plan_heating.data.get_agile_prices",
			mock_get_prices
		)
		cli_session = tests.mock_cli.MockCLI(
			self,
			[
				"Enter initial indoor temperature (°C):                      ",
				"Times to heat until (days after 00:00 tonight):             ",
				"Enter maximum number of times to run each type of heating:  ",
				(
					"\nThe temperature forecast does not last long enough to "
					"simulate for this many days.\nEnter a constant outdoor "
					"temperature (Celsius) to assume for the remainder of the "
					"simulation:  "
				),
				(
					"\nFetching prices...\n\nCalculating options:\n\n"
					"Heating until 00:00 on Monday (1.08 days):\n"
					"    Costs £0.03 (6.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00\n"
					"    Run direct heating at: 2kW for 04:00--05:00\n"
					"    Total energy: 1.0kWh\n"
					"\n"
					"Heating until 10:00 on Monday (1.50 days):\n"
					"    Costs an additional £0.02 (2.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00, 01:00--03:00\n"
					"    Run direct heating at: 1kW for 01:00--01:30, 2kW for 04:00--05:00\n"
					"    Total energy: 2.0kWh\n"
					"\n"
				)
			],
			["20", "3", "2", "10"]
		)
		with (
			self.data_patch, self.time_patch, self.plt_patch,
			self.heat_opts_patch, prices_patch, cli_session
		):
			plan_heating.main()
		self.mock_heat_opts.assert_called_once_with(
			list(range(48)) + [10.]*26, # 73hrs with fencepost effect
			datetime.datetime(2020,10,24,22,00, tzinfo=datetime.timezone.utc),
			20,
			[
				datetime.datetime(2020,10,27,23, tzinfo=datetime.timezone.utc),
			],
			list(range(48,96)),
			2
		)

	def test_DST_warning(self):
		mock_get_prices = unittest.mock.Mock(return_value=list(range(48, 98)))
		prices_patch = unittest.mock.patch(
			"plan_heating.data.get_agile_prices",
			mock_get_prices
		)
		cli_session = tests.mock_cli.MockCLI(
			self,
			[
				"Enter initial indoor temperature (°C):                      ",
				"Times to heat until (days after 00:00 tonight):             ",
				"Enter maximum number of times to run each type of heating:  ",
				(
					"\nFetching prices...\nWarning: tomorrow appears to "
					"feature a daylight savings switchover.\nAnalogue timers "
					"may need the times below to be adjusted accordingly.\n\n"
					"Calculating options:\n\n"
					"Heating until 00:00 on Monday (1.08 days):\n"
					"    Costs £0.03 (6.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00\n"
					"    Run direct heating at: 2kW for 04:00--05:00\n"
					"    Total energy: 1.0kWh\n"
					"\n"
					"Heating until 10:00 on Monday (1.50 days):\n"
					"    Costs an additional £0.02 (2.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00, 01:00--03:00\n"
					"    Run direct heating at: 1kW for 01:00--01:30, 2kW for 04:00--05:00\n"
					"    Total energy: 2.0kWh\n"
					"\n"
				)
			],
			["20", "1.041666666666, 1.458333333333", "2"]
		)
		with (
			self.data_patch, self.time_patch, self.plt_patch,
			self.heat_opts_patch, prices_patch, cli_session
		):
			plan_heating.main()
		self.mock_heat_opts.assert_called_once_with(
			list(range(48)),
			datetime.datetime(2020,10,24,22,00, tzinfo=datetime.timezone.utc),
			20,
			[
				datetime.datetime(2020,10,26,00, tzinfo=datetime.timezone.utc),
				datetime.datetime(2020,10,26,10, tzinfo=datetime.timezone.utc),
			],
			list(range(48,98)),
			2
		)

	def test_no_prices(self):
		mock_get_prices = unittest.mock.Mock(return_value=[])
		prices_patch = unittest.mock.patch(
			"plan_heating.data.get_agile_prices",
			mock_get_prices
		)
		cli_session = tests.mock_cli.MockCLI(
			self,
			[
				"Enter initial indoor temperature (°C):                      ",
				"Times to heat until (days after 00:00 tonight):             ",
				"Enter maximum number of times to run each type of heating:  ",
				"\nFetching prices...\n"
			],
			["20", "1.041666666666, 1.458333333333", "2"]
		)
		with (
			self.data_patch, self.time_patch, self.plt_patch,
			self.heat_opts_patch, prices_patch, cli_session,
			self.assertRaises(RuntimeError, msg="could not obtain prices")
		):
			plan_heating.main()

	def test_0_marginal_useful_energy(self):
		self.mock_heat_opts.return_value[1]["useful_energy"] = .5
		self.mock_heat_opts.return_value[1]["marg_usfl_enrgy"] = 0
		mock_get_prices = unittest.mock.Mock(return_value=list(range(48, 96)))
		prices_patch = unittest.mock.patch(
			"plan_heating.data.get_agile_prices",
			mock_get_prices
		)
		cli_session = tests.mock_cli.MockCLI(
			self,
			[
				"Enter initial indoor temperature (°C):                      ",
				"Times to heat until (days after 00:00 tonight):             ",
				"Enter maximum number of times to run each type of heating:  ",
				(
					"\nFetching prices...\n\nCalculating options:\n\n"
					"Heating until 00:00 on Monday (1.08 days):\n"
					"    Costs £0.03 (6.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00\n"
					"    Run direct heating at: 2kW for 04:00--05:00\n"
					"    Total energy: 1.0kWh\n"
					"\n"
					"Heating until 10:00 on Monday (1.50 days):\n"
					"    Costs an additional £0.02 (20000000000000000.00p per useful kWh).\n"
					"    Charge the storage heater for: 23:00--00:00, 01:00--03:00\n"
					"    Run direct heating at: 1kW for 01:00--01:30, 2kW for 04:00--05:00\n"
					"    Total energy: 2.0kWh\n"
					"\n"
				)
			],
			["20", "1.041666666666, 1.458333333333", "2"]
		)
		with (
			self.data_patch, self.time_patch, self.plt_patch,
			self.heat_opts_patch, prices_patch, cli_session
		):
			plan_heating.main()
