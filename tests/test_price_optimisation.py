import unittest
import unittest.mock
import datetime
import zoneinfo
import numpy as np

import price_optimisation
import heating_simulation


class TestCheapestWindow(unittest.TestCase):
	def test_cheapest_window(self):
		dt = datetime.datetime
		utc = datetime.timezone.utc
		prices = {
			dt(2020, 1, 1, 4,      tzinfo=utc): 50,
			dt(2020, 1, 1, 4, 30,  tzinfo=utc): 40,
			dt(2020, 1, 1, 5,      tzinfo=utc): 1,
			dt(2020, 1, 1, 5, 30,  tzinfo=utc): 40,
			dt(2020, 1, 1, 8,      tzinfo=utc): 2,
			dt(2020, 1, 1, 8, 30,  tzinfo=utc): 4,
			dt(2020, 1, 1, 9,      tzinfo=utc): 30,
			dt(2020, 1, 1, 9,30,   tzinfo=utc): 3.5,
			dt(2020, 1, 1, 10,     tzinfo=utc): 3.5,
			dt(2020, 1, 1, 10, 30, tzinfo=utc): 3,
			dt(2020, 1, 1, 11,     tzinfo=utc): 4,
			dt(2020, 1, 1, 11, 30, tzinfo=utc): 30,
			dt(2020, 1, 1, 13, 30, tzinfo=utc): 3,
			dt(2020, 1, 1, 14,     tzinfo=utc): 4,
			dt(2020, 1, 1, 14, 30, tzinfo=utc): 3,
			dt(2020, 1, 1, 15,     tzinfo=utc): 4
		}
		self.assertEqual(
			price_optimisation.cheapest_window(.5, prices),
			(datetime.datetime(2020, 1, 1, 5, tzinfo=utc), 1)
		)
		self.assertEqual(
			price_optimisation.cheapest_window(1, prices),
			(datetime.datetime(2020, 1, 1, 8, tzinfo=utc), 3)
		)
		self.assertEqual(
			price_optimisation.cheapest_window(2, prices),
			(datetime.datetime(2020, 1, 1, 13, 30, tzinfo=utc), 3.5)
		)
		return_val = price_optimisation.cheapest_window(4.5, prices)
		self.assertIsNone(return_val[0])
		self.assertIsNone(return_val[1])


class TestTempRangesFromConfig(unittest.TestCase):
	def test_temp_ranges_from_config(self):
		config_patch = unittest.mock.patch.multiple(
			price_optimisation.config,
			TIME_ZONE = "Europe/London",
			MIN_TEMP = 16,
			MAX_TEMP = 24,
			ABSENT_HOURS = [(0, 8), (9, 17)],
			ABS_MAX_TEMP = 30,
			ABS_MIN_TEMP = 5,
		)
		with config_patch:
			return_val = price_optimisation.temp_ranges_from_config(
				datetime.datetime(2020,1,1,12,tzinfo=datetime.timezone.utc),
				100, 200
			)
		expected_return_val = [
			( 97, 5, 30), (105, 16, 24), (112, 5, 30), (120, 16, 24),
			(121, 5, 30), (129, 16, 24), (136, 5, 30), (144, 16, 24),
			(145, 5, 30), (153, 16, 24), (160, 5, 30), (168, 16, 24),
			(169, 5, 30), (177, 16, 24), (184, 5, 30), (192, 16, 24),
			(193, 5, 30)
		]
		self.assertEqual(
			set(
				x for x in return_val
				if 97 <= x[0] < 200  # (only these values matter)
			),
			set(expected_return_val)
		)
		# Clocks go forward at 2020-03-29T01:00
		with config_patch:
			return_val = price_optimisation.temp_ranges_from_config(
				datetime.datetime(2020,3,27,12,tzinfo=datetime.timezone.utc),
				100, 200
			)
		expected_return_val = [
			( 97, 5, 30), (105, 16, 24), (112, 5, 30), (120, 16, 24),
			(121, 5, 30), (129, 16, 24), (136, 5, 30), (143, 16, 24),
			(144, 5, 30), (152, 16, 24), (159, 5, 30), (167, 16, 24),
			(168, 5, 30), (176, 16, 24), (183, 5, 30), (191, 16, 24),
			(192, 5, 30)
		]
		self.assertEqual(
			set(x for x in return_val if 97 <= x[0] < 200),
			set(expected_return_val)
		)


class TestCheapestHeat(unittest.TestCase):

	def setUp(self):
		self.building = heating_simulation.Building(
			.05, .1, .001, .0075, 1, .025, 4, 3, 100
		)
		local_tz = zoneinfo.ZoneInfo("Europe/London")
		self.config_patch = unittest.mock.patch.multiple(
			price_optimisation.config,
			TIME_ZONE = "Europe/London",
			OTHER_HEAT_OUTPUT = 1,
			MIN_TEMP = 16,
			MAX_TEMP = 24,
			ABSENT_HOURS = [(0, 8), (9, 17)],
			ABS_MAX_TEMP = 30,
			ABS_MIN_TEMP = 5,
			HEATING_PERIOD_PENALTY = 5,
			HEAT_OPTIMISATION_THREADS = 1,
			HEAT_OPTIMISATION_POPSIZE = 16,
		)
		self.start_t = datetime.datetime(2020, 10, 24, 23, 00, tzinfo=local_tz)
		self.init_vals = (100, 16)
		self.prices = [1, 2, 3, 4, 5, 6, 7, 8]
		self.outdoor_temps = [5] * 30
		self.other_heat = [(0, 200, .1)]
		with self.config_patch:
			self.temp_ranges = price_optimisation.temp_ranges_from_config(
				self.start_t, 100, 126
			)

	def test_cheapest_heat(self):
		# Mock the cost_func with a very easy optimisation problem, the
		# solution to which is a sequence of ascending multiples of 1/6
		# starting from 0 (chosen so that the rounding effect of
		# _sim_heat_args() permits the exact solution)
		def mock_cost_func(s, building, *args):
			self.assertIs(building, self.building)
			self.assertEqual(args, (
				sorted(self.temp_ranges),
				(100, 16, 16, 16),
				self.other_heat,
				self.outdoor_temps[:28],  # Truncated to end_t plus 30mins
				self.prices,
				126,
				"penalty_per_heat_placeholder"
			))
			self.assertGreaterEqual(min(s), 0)
			self.assertLessEqual(max(s[6], s[9]), 10)
			if len(s) == 0:
				return 0
			else:
				cost = s[0] ** 2
				for a,b in zip (s, s[1:]):
					cost += (b - (a+1/6)) ** 2
				return cost
		cost_func_patch = unittest.mock.patch(
			"price_optimisation._cheapest_heat_cost_func",
			mock_cost_func
		)
		# Verify that the optimiser finds something close to optimal
		with self.config_patch, cost_func_patch:
			sh, dh, enrgy, cost, act_end, _ = price_optimisation.cheapest_heat(
				self.building, self.temp_ranges, self.init_vals, 10,
				self.other_heat, self.outdoor_temps, self.prices,
				126, 2, "penalty_per_heat_placeholder"
			)
			self.assertEqual(
				(sh, dh),
				price_optimisation._sim_heat_args(np.linspace(0,1.5,10),100,108)
			)
			self.assertAlmostEqual(enrgy, 29/6)
			self.assertAlmostEqual(cost, 239/12)
			# This amount of heat should only just last until the next morning
			self.assertAlmostEqual(act_end, 110.255, 2)

	def test_0_num_heats(self):
		def mock_cost_func(*args):
			self.fail("_cheapest_heat_cost_func() should not be called")
		cost_func_patch = unittest.mock.patch(
			"price_optimisation._cheapest_heat_cost_func",
			mock_cost_func
		)
		with self.config_patch, cost_func_patch:
			sh, dh, enrgy, cost, act_end, _ = price_optimisation.cheapest_heat(
				self.building, self.temp_ranges, self.init_vals, 10,
				self.other_heat, self.outdoor_temps, self.prices,
				126, 0, "penalty_per_heat_placeholder"
			)
			self.assertEqual(sh, [])
			self.assertEqual(dh, [])
			self.assertEqual(enrgy, 0)
			self.assertEqual(cost, 0)
			self.assertAlmostEqual(act_end, 100, 1)


class TestCostFunc(unittest.TestCase):

	def setUp(self):
		# Mock the heating simulation to return self.sim_heat_return.
		self.mock_building = unittest.mock.Mock()
		self.mock_building.simulate_heat = unittest.mock.Mock(
			side_effect = (lambda *args: self.sim_heat_return)
		)

	def test_cost_func(self):
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  19,  18,  22,  21,  20],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 1, 2, 3, 4),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				0
			),
			80
		)
		self.mock_building.simulate_heat.assert_called_once_with(
			(100, 20, 20, 20),
			[(100, 101)],
			[(102, 104.5, 4)],  # Only 4.5hrs of prices, so capped at 104.5
			"other_heat",
			"outdoor_temps",
			[(0, 10, 30)]
		)

	def test_penalty_per_heat(self):
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  19,  18,  22,  21,  20],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 1, 2, 3, 4),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				10
			),
			80 + 20
		)

	def test_time_penalty(self):
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  15,  10,  7,   8,   5],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 1, 2, 3, 4),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				0
			),
			5e10 + 80
		)

	def test_zero_heat_not_last(self):
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  19,  18,  22,  21,  20],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 1, 0, 0, 0, 0, 0, 2, 3, 4),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				0
			),
			1e20
		)
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  19,  18,  22,  21,  20],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 0, 0, 1, 2, 3, 4, 0, 0, 0),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				0
			),
			1e20
		)
		self.sim_heat_return = (
			[100, 105, 110, 115, 120, 125],
			[ 20,  19,  18,  22,  21,  20],
			[20]*6,
			[20]*6,
			[5, 0, 7, 0, 0, 0, 11]
		)
		self.assertEqual(
			price_optimisation._cheapest_heat_cost_func(
				(0, 0, 0, 1, 0, 0, 0, 2, 3, 4),
				self.mock_building,
				[(0, 10, 30)],
				(100, 20, 20, 20),
				"other_heat",
				"outdoor_temps",
				[0, 1, 2, 3, 4, 5, 6, 7, 8],
				120,
				0
			),
			2e20
		)
		# To save time, we shouldn't be running the simulation for any of these
		self.mock_building.simulate_heat.assert_not_called()


class TestEnergyCost(unittest.TestCase):
	def test_energy_cost(self):
		self.assertEqual(
			price_optimisation._energy_cost([0,1,2,3,4,5,6], [1,2,3,5,7,11]),
			106
		)
		self.assertEqual(
			price_optimisation._energy_cost([0,1,2,3,4,5], [1,2,3,5,7,11]),
			106
		)
		self.assertEqual(
			price_optimisation._energy_cost([0,1,2,3,4,5], [1,2,3,5,7,11,0,0]),
			106
		)
		with self.assertRaises(ValueError):
			price_optimisation._energy_cost([0,1,2,3,4,5], [1,2,3,5,7,11,0,1])


class TestUsefulHeatEnergy(unittest.TestCase):

	def test_useful_heat_energy(self):
		mock_building = unittest.mock.Mock()
		mock_usage = 10 * np.random.rand(48)
		sim_heat_return = ("t", "T", "Q", "S", mock_usage)
		mock_building.simulate_heat = unittest.mock.Mock(
			side_effect = (lambda *args: sim_heat_return)
		)
		temp_ranges = [(90,1,2), (100,3,4), (110,5,6), (120,7,8), (130,9,10)]
		outdoor_temps = [0] * 25
		self.assertEqual(
			price_optimisation.useful_heat_energy(
				mock_building,
				temp_ranges,
				(100, 20),
				"other_heat",
				outdoor_temps,
				124
			),
			sum(mock_usage)
		)
		mock_building.simulate_heat.assert_called_once_with(
			(100, 20, 20, 20),
			[],
			"thermostat",
			"other_heat",
			outdoor_temps,
			# Terminated at end_t with low min_temp to disable further heating:
			[(90,1,2), (100,3,4), (110,5,6), (120,7,8), (124,-np.inf,np.inf)]
		)

	def test_insufficient_temperature_data(self):
		with self.assertRaises(ValueError, msg="Insufficient temperature data"):
			price_optimisation.useful_heat_energy(
				"building",
				"temp_ranges",
				(100, 20),
				"other_heat",
				[0] * 24,
				124
			)
