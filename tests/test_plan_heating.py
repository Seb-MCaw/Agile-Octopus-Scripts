import unittest
import unittest.mock
import datetime
import zoneinfo

import numpy as np

import plan_heating


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
