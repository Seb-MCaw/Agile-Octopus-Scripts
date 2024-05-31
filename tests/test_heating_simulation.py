import unittest
import unittest.mock

import numpy as np

import heating_simulation


class TestDiagonalisedMatrix(unittest.TestCase):
	def test_DiagonalisedMatrix(self):
		m = [[1,2,3], [4,5,6], [7,8,9]]
		dm = heating_simulation.DiagonalisedMatrix(m)
		self.assertEqual(dm.e.shape, (3,))
		self.assertEqual(dm.E.shape, (3, 3))
		self.assertEqual(dm.E_inv.shape, (3, 3))
		self.assertTrue(np.all(np.isclose(
			dm.E @ dm.E_inv,
			np.diag([1,1,1])
		)))
		self.assertTrue(np.all(np.isclose(
			dm.E @ np.diag(dm.e) @ dm.E_inv,
			m
		)))


class TestDifferentialEqns(unittest.TestCase):

	def test_simple_ODE(self):
		soln = heating_simulation.solve_simple_ODE(1, 2, 3, 4, 5, [0, 7])
		self.assertAlmostEqual(soln[0], -1.612294065)
		self.assertAlmostEqual(soln[1], 364777592.8, 1)

	def test_simple_vector_ODE(self):
		soln = heating_simulation.solve_simple_vector_ODE(
			0,
			[2,3,4],
			heating_simulation.DiagonalisedMatrix([[5,6,7],[8,9,10],[11,12,13]]),
			[14,15,16],
			[17,18,19],
			[1, 20]
		)
		self.assertAlmostEqual(soln[0][0], 2.44780845e012, -6)
		self.assertAlmostEqual(soln[0][1], 3.57603331e240, -234)
		self.assertAlmostEqual(soln[1][0], 3.62899495e012, -6)
		self.assertAlmostEqual(soln[1][1], 5.30164313e240, -234)
		self.assertAlmostEqual(soln[2][0], 4.81018145e012, -6)
		self.assertAlmostEqual(soln[2][1], 7.02725295e240, -234)


class TestSimulation(unittest.TestCase):

	def setUp(self):
		self.b = heating_simulation.Building(
			k=.1, h=.5, j_passive=.005, j_charging=.03,
			C=1, C_sh=.2, C_q=5,
			sh_charge_pwr=3,
			sh_max_temp=50
		)

	def test_steady_state(self):
		"""
		Everything at the same temperature with no heating.
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[20]*11,
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 10)
		self.assertAlmostEqual(T[-1], 20)
		self.assertAlmostEqual(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 20)
		self.assertEqual(sum(usage), 0)

	def test_direct_heat(self):
		"""
		Indoors at 20C and direct heat to exactly counteract losses.
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[],
			direct_heat=[(0, 10, 1)],
			other_heat=[],
			outdoor_temps=[10]*11,
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 10)
		self.assertAlmostEqual(T[-1], 20)
		self.assertAlmostEqual(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 20)
		self.assertAlmostEqual(sum(usage), 10)

	def test_thermostat(self):
		"""
		Maintain indoors at 20C with thermostatic direct heat
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[],
			direct_heat="thermostat",
			other_heat=[],
			outdoor_temps=[0]*11,
			min_temps=[(0, 20)]
		)
		self.assertEqual(t[-1], 10)
		self.assertAlmostEqual(T[-1], 20)
		self.assertAlmostEqual(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 20)
		self.assertAlmostEqual(sum(usage), 20)

	def test_other_heat(self):
		"""
		Indoors at 20C and other heat to exactly counteract losses.
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[],
			direct_heat=[],
			other_heat=[(0, 10, 1)],
			outdoor_temps=[10]*11,
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 10)
		self.assertAlmostEqual(T[-1], 20)
		self.assertAlmostEqual(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 20)
		self.assertEqual(sum(usage), 0)
		with self.assertRaises((ValueError, TypeError)):
			self.b.simulate_heat(
				init_vals=(0, 20, 20, 20),
				storage_heat=[],
				direct_heat=[],
				other_heat="thermostat",
				outdoor_temps=[10]*11,
				min_temps=[(0, 0)]
			)

	def test_storage_heat(self):
		"""
		Indoors at 20C and storage heat slightly exceeding losses.
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[(0, 1), (5, 6)],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[15]*11,
			min_temps=[(0, 20)]
		)
		self.assertEqual(t[-1], 10)
		self.assertAlmostEqual(T[-1], 20, 4)
		self.assertAlmostEqual(Q[-1], 20, 4)
		self.assertAlmostEqual(S[-1], 25, 3)
		self.assertAlmostEqual(sum(usage), 6)

	def test_conduction(self):
		"""
		Constant T=20C, Q and S cooling from higher temps.
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 22, 50),
			storage_heat=[],
			direct_heat="thermostat",
			other_heat=[],
			outdoor_temps=[0]*21,
			min_temps=[(0, 20)]
		)
		Q_f = 20 + 2 * np.exp(-20 * self.b.h / self.b.C_q)
		self.assertEqual(t[-1], 20)
		self.assertAlmostEqual(T[-1], 20)
		self.assertAlmostEqual(Q[-1], Q_f, 5)
		self.assertAlmostEqual(S[-1], 20, 1) # Discharge termination inexact
		delta_E_q = self.b.C_q * (22 - Q_f)
		delta_E_sh = self.b.C_sh * (50 - 20)
		self.assertAlmostEqual(sum(usage), 40 - delta_E_q - delta_E_sh, 2)

	def test_storage_heat_leakage(self):
		"""
		Check that storage heater leaks more while charging.
		"""
		# Passive:
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 50),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[20]*2,
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 1)
		self.assertLess(T[-1], 20.2)
		self.assertLess(Q[-1], 20.01)
		self.assertAlmostEqual(S[-1], 49.26, 2)
		self.assertAlmostEqual(sum(usage), 0)
		# Charging:
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 50),
			storage_heat=[(0, 1)],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[20]*2,
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 1)
		self.assertLess(T[-1], 20.7)
		self.assertLess(Q[-1], 20.05)
		self.assertAlmostEqual(S[-1], 50, 1)
		self.assertAlmostEqual(sum(usage), .89, 2)

	def test_min_temp_changes(self):
		"""
		Check storage heater discharge responds to changes in min_temp
		"""
		# Decrease:
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 50),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[10]*3,
			min_temps=[(0, 20), (1, 10)]
		)
		self.assertEqual(t[-1], 2)
		self.assertLess(T[-1], 19.5)
		self.assertLess(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 44.375, 2)
		self.assertEqual(sum(usage), 0)
		# Increase:
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 50),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[10]*3,
			min_temps=[(0, 20), (1, 21)]
		)
		Q_f = 21 - np.exp(-1 * self.b.h / self.b.C_q)
		stored_heat_used = 2.1 + (21-20)*self.b.C + (Q_f-20)*self.b.C_q
		self.assertEqual(t[-1], 2)
		self.assertEqual(T[-1], 21)
		self.assertAlmostEqual(Q[-1], Q_f)
		self.assertAlmostEqual(S[-1], 50 - stored_heat_used/self.b.C_sh)
		self.assertEqual(sum(usage), 0)

	def test_extra_elements_in_min_temp_tuples(self):
		"""
		Check that "Further elements of each tuple will be ignored"
		"""
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 50),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[10]*3,
			min_temps=[(0, 20, object()), (1, 10, [1,2,3], None)]
		)
		self.assertEqual(t[-1], 2)
		self.assertLess(T[-1], 19.5)
		self.assertLess(Q[-1], 20)
		self.assertAlmostEqual(S[-1], 44.375, 2)
		self.assertEqual(sum(usage), 0)

	def test_energy_conservation(self):
		"""
		Simulate several days and check energy is conserved
		"""
		# 12 hour nights with outdoor temp 0C and min_temp=10
		# 12 hour days with outdoor temp 10C and min_temp=20
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[(0, 2), (24, 26), (48, 50), (72, 74)],
			direct_heat="thermostat",
			other_heat=[],
			outdoor_temps=([0]*12 + [10]*12) * 4 + [0],
			min_temps=[(00, 10), (12, 20), (24, 10), (36, 20),
			           (48, 10), (60, 20), (72, 10), (84, 20)]
		)
		self.assertEqual(t[-1], 96)
		self.assertLess(np.min(T), 15) # Make sure it cooled overnight
		self.assertGreater(np.min(T), 10) # but not too much
		loss_to_outdoors = (np.trapz(np.array(T) - 5, t)) * self.b.k
		delta_E =  (T[-1]-20) * self.b.C
		delta_E += (Q[-1]-20) * self.b.C_q
		delta_E += (S[-1]-20) * self.b.C_sh
		self.assertAlmostEqual(sum(usage), loss_to_outdoors + delta_E, 5)

	def test_zero_length_sim(self):
		t, T, Q, S, usage = self.b.simulate_heat(
			init_vals=(0, 20, 20, 20),
			storage_heat=[],
			direct_heat=[],
			other_heat=[],
			outdoor_temps=[20],
			min_temps=[(0, 0)]
		)
		self.assertEqual(t[-1], 0)
		self.assertEqual(T[-1], 20)
		self.assertEqual(Q[-1], 20)
		self.assertEqual(S[-1], 20)
		self.assertEqual(sum(usage), 0)


class TestBuildingFromConfig(unittest.TestCase):

	def test_from_config(self):
		config_patch = unittest.mock.patch.multiple(
			heating_simulation.config,
			FAST_HEAT_CAPACITY = 1,
			CONDUCTANCE_TO_OUTDOORS = .01,
			SLOW_HEAT_CAPACITY = 4,
			SLOW_CONDUCTANCE = .1,
			STORAGE_HEATER_SIZE = 2,
			STORAGE_HEATER_POWER = 3,
			STORAGE_HEATER_MAX_TEMP = 100,
			STORAGE_HEATER_CHARGE_LEAKAGE = .5,
			STORAGE_HEATER_STORE_TIME = 48,
			MIN_TEMP = 10,
			MAX_TEMP = 20
		)
		with config_patch:
			b = heating_simulation.building_from_config()
		self.assertEqual(b.C, 1)
		self.assertEqual(b.k, .01)
		self.assertEqual(b.C_q, 4)
		self.assertEqual(b.h, .1)
		self.assertEqual(b.C_sh, 2/90)
		self.assertEqual(b.sh_charge_pwr, 3)
		self.assertEqual(b.sh_max_temp, 100)
		self.assertAlmostEqual(b.j_passive, .0010172)
		self.assertAlmostEqual(b.j_charging, .0010172 + .5/80) # (uses MAX_TEMP)

	def test_error_on_max_sh_temp_too_low(self):
		config_patch = unittest.mock.patch.multiple(
			heating_simulation.config,
			STORAGE_HEATER_MAX_TEMP = 9,
			MIN_TEMP = 10
		)
		a = self.assertRaises(ValueError, msg="STORAGE_HEATER_MAX_TEMP too low")
		with config_patch, a:
			heating_simulation.building_from_config()
