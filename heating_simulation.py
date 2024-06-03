"""
Simulate the heating and cooling of a building.



Buildings are modelled as three coupled heat reservoirs, representing the air
and other fast-responding contents, slow-responding contents such as the walls,
and a/some storage heater(s). The former is coupled to the ambient outdoor
temperature. The heat from the storage heater(s) is discharged as required to
maintain the air temperature at or above some minimum (which may change over time).


The indoor (air) temperature normally obeys a differential equation of the form:
   C T'(t) = k(A(t)-T(t)) + h(Q(t)-T(t)) + j(S(t)-T(t)) + P(t)          (1)
T(t) is the indoor temperature at time t, A(t) is the outdoor temperature,
Q(t) is the temperature of the slowly responding parts of the property
and S(t) is the internal temperature of the storage heater.
C is the property's fast heat capacity and k its thermal conductance to outside.
h is the thermal conductance between the fast- and slow-responding parts of the
property. j is the storage heater's thermal conductance; due to the leakage
while charging, the value of j may depend on whether I is 0.
P(t) is the total power being dissipated into the indoors at time t.

At the same time, the storage heater's temperature obeys
   C_sh S'(t) = j(T(t) - S(t)) + I(t)                                   (2)
unless/until T <= min_temp.
min_temp is the lowest acceptable temperature at the time t.
C_sh is the storage heater's heat capacity and I(t) is the heater's input
power.

Once T <= min_temp, the regime changes, and T is held at exactly min_temp
while the storage heater's temperature obeys
   C_sh S'(t) = k(A(t) - T(t)) + h(Q(t) - T(t)) + P(t) + I(t)           (3)
(since all heat lost from indoors is replenished by the storage heater)
unless or until either S <= T, or the RHS of eq (1) is positive.

When S == T and T <= min_temp, both S and T follow the equation
   (C_sh + C) T'(t) = k(A(t) - T(t)) + h(Q(t) - T(t)) + P(t) + I(t)     (4)
unless or until the value of T'(t) given by eq (1) is greater than that
given by this equation.


At all times, the slow-responding part of the property obeys
   C_q Q'(t) = h(T(t) - Q(t)).                                          (5)
C_q is the heat capacity of the slow-responding part.

"""



import math
import numpy as np

import config



def building_from_config():
	"""
	Return the Building defined by the config file.
	"""
	# Calculate the relevant heat capacity and conductances for the storage
	# heater. The config file defines the time taken for cooling from
	# STORAGE_HEATER_MAX_TEMP to (MIN_TEMP + cooled_temp_diff).
	cooled_temp_diff = 10
	sh_temp_range = config.STORAGE_HEATER_MAX_TEMP - config.MIN_TEMP
	if sh_temp_range < cooled_temp_diff and config.STORAGE_HEATER_SIZE != 0:
		raise ValueError("STORAGE_HEATER_MAX_TEMP too low")
	C_sh = (
		config.STORAGE_HEATER_SIZE
		/ (sh_temp_range)
	)
	j_passive = (
		(C_sh / config.STORAGE_HEATER_STORE_TIME)
		* math.log(sh_temp_range / cooled_temp_diff)
	)
	# Also calculate the total conductance during charging (use MAX_TEMP
	# for a pessimistic estimate).
	j_charging = j_passive + (
		config.STORAGE_HEATER_CHARGE_LEAKAGE
		/ (config.STORAGE_HEATER_MAX_TEMP - config.MAX_TEMP)
	)
	# Return the resulting Building object
	return Building(
		config.CONDUCTANCE_TO_OUTDOORS,
		config.SLOW_CONDUCTANCE,
		j_passive,
		j_charging,
		config.FAST_HEAT_CAPACITY,
		C_sh,
		config.SLOW_HEAT_CAPACITY,
		config.STORAGE_HEATER_POWER,
		config.STORAGE_HEATER_MAX_TEMP
	)



class Building:
	"""
	A model of the thermal behaviour of a particular building.

	All constants from the differential equations in the module docstring
	are available as attributes. self.j_passive specifies the value j takes
	when I == 0, while self.j_charging gives the value at all other times.

	Also defines the storage heater behaviour with the attributes sh_charge_pwr,
	which gives the power (kW) at which the storage heater stores heat when
	charging, and sh_max_temp, which gives the temperature to which the
	thermostat will limit the internal temperature.
	"""
	# Private attribute _ode_matrices also provided, containing pre-diagonalised
	# forms of the relevant differential equations

	def __init__(self, k, h, j_passive, j_charging, C, C_sh, C_q, sh_charge_pwr, sh_max_temp):
		self.k = k
		self.h = h
		self.j_passive = j_passive
		self.j_charging = j_charging
		self.C = C
		self.C_sh = C_sh
		self.C_q = C_q
		self.sh_charge_pwr = sh_charge_pwr
		self.sh_max_temp = sh_max_temp
		# To solve the equations, we will need diagonalised forms of the matrices
		# relating the derivatives of the simulated temperatures (T,Q,S) to
		# themselves (the inhomogeneous part is dealt with later). In other
		# words, if the system of equations is written in vector form as
		# dA/dt = MA + B + Ct, for vectors A,B,C, we calculate and diagonalise
		# the matrix M. The rows of the vectors are ordered T, Q, S.
		self._ode_matrices = {
			# The free evolution of the system (i.e. the combination of eqs (1)
			# (2) and (5)) when the storage heater is not charging (and hence
			# there is no extra leakage).
			"free" : DiagonalisedMatrix(np.array([
				np.array([-k - h - j_passive, h,    j_passive ]) / C,
				np.array([h,                 -h,    0         ]) / C_q,
				np.array([j_passive,          0,    -j_passive]) / C_sh
			])),
			# When the storage heater is charging
			"charging" : DiagonalisedMatrix(np.array([
				np.array([-k - h - j_charging,  h,  j_charging]) / C,
				np.array([h,                   -h,  0         ]) / C_q,
				np.array([j_charging,           0, -j_charging]) / C_sh
			])),
			# Eqs (3) and (5) (and no change in T)
			# Note that the T row is omitted
			"discharging" : DiagonalisedMatrix(np.array([
				np.array([-h, 0]) / C_q,
				np.array([h,  0]) / C_sh
			])),
			# Eqs (4) and (5)
			# Note that the T and S rows are combined
			"equalised" : DiagonalisedMatrix(np.array([
				np.array([-k - h,  h]) / (C_sh + C),
				np.array([h,      -h]) / C_q
			]))
		}


	def simulate_heat(self, init_vals, storage_heat, direct_heat, other_heat, outdoor_temps, min_temps):
		"""
		Simulate the effect of the specified heat input on the Building's temperatures.

		Time values, t, are measured in hours. The simulation will run for
		the duration of the outdoor temperature forecast.

		Arguments:
		  init_vals         A 4-tuple giving the initial value of (t, T, Q, S)
		                    at the start of the simulation.
		  storage_heat      A list of 2-tuples defining the time periods for
		                    which the storage heaters should charge. Each should
		                    specify non-overlapping (start, end) t values.
		  direct_heat       A list of 3-tuples defining the heating which is
		                    applied directly to the air in the building (via
		                    space heaters etc). The first 2 elements of each
		                    specify a time period over which it is applied as
		                    for storage_heat, while the third gives the power
		                    input in kW.
		                    Alternatively, the string "thermostat", in which
		                    case heat will be applied in real time as required
		                    to maintain the appropriate min_temp.
		  other_heat        Equivalent to direct_heat, except this heating
		                    is not included in the energy consumption (and
		                    "thermostat" is not an option).
		  outdoor_temps     A sequence of forecast hourly outdoor ambient
		                    temperatures. outdoor_temps[0] should give the
		                    temperature at t=init_vals[0].
		  min_temps         A sequence of tuples specifying the minimum
		                    temperatures which the storage heater should strive
		                    to maintain at different times. The first element
		                    of each is a t value and the second is the minimum
		                    temperature to maintain from that t value until the
		                    next one. Further elements of each tuple will be
		                    ignored. min_temp[0][0] should equal init_values[0].

		Returns:
		  - An array of t values
		  - An array of the corresponding T values
		  - An array of the corresponding Q values
		  - An array of the corresponding S values
		  - An array of the total energies (for both storage and direct heating)
		    used in each half-hour period (accounting for the effect of the
		    storage heater's internal thermostat) starting at init_vals[0]
		"""
		start_t = init_vals[0]
		end_t = init_vals[0] + len(outdoor_temps) - 1
		min_temps = sorted(min_temps, key=lambda x: x[0])

		# Create a list of all expected discontinuities and relevant time boundaries.
		# The intervals between these can be solved analytically as a single step.
		#
		# Specifically, this list consists of all direct and storage heating
		# switch-on and switch-off events, all changes in the minimum temperature
		# and all hours and half-hours (since half-hourly usage is returned)
		# between start_t and end_t.
		step_boundaries = set(np.linspace(start_t, end_t, 1+2*(end_t-start_t)))
		step_boundaries.update(np.array(storage_heat).flatten())
		if direct_heat != "thermostat":
			step_boundaries.update(np.array([x[:2] for x in direct_heat]).flatten())
		step_boundaries.update([x[0] for x in min_temps])
		step_boundaries = sorted(step_boundaries)
		step_boundaries = [t for t in step_boundaries if start_t <= t <= end_t]

		# Initialise an array of electricity consumption values with zeros
		elec_use = np.zeros(2 * math.ceil(end_t - start_t))

		# Perform the simulation step-by-step
		t = [start_t]
		T = [init_vals[1]]
		Q = [init_vals[2]]
		S = [init_vals[3]]
		min_temp_idx = 0
		for t_a, t_b in zip(step_boundaries, step_boundaries[1:]):
			# Find the values of P(t) and I(t) for this step
			P_direct = P_other = I = 0
			if any(t_1 <= t_a < t_2 for t_1, t_2 in storage_heat):
				I = self.sh_charge_pwr
			if direct_heat == "thermostat":
				thermostat = True
			else:
				thermostat = False
				for h in direct_heat:
					if h[0] <= t_a < h[1]:
						assert h[0] <= t_b <= h[1]
						P_direct = h[2]
			for h in other_heat:
				if h[0] <= t_a < h[1]:
					assert h[0] <= t_b <= h[1]
					P_other = h[2]
			# Linearly interpolate to find the outdoor temperatures at t_a and t_b
			outdoor_temps_ab = np.interp(
				(t_a, t_b),
				np.linspace(start_t, end_t, len(outdoor_temps)),
				outdoor_temps
			)
			# Determine the min_temp applicable to this step
			while (
				min_temp_idx < len(min_temps) - 1
				and min_temps[min_temp_idx + 1][0] <= t_a
			):
				min_temp_idx += 1
			min_temp = min_temps[min_temp_idx][1]
			# Simulate the step
			new_t, new_T, new_Q, new_S, actual_I, thstat_E = self._simulation_step(
				(t_a, t_b),
				(T[-1], Q[-1], S[-1]),
				outdoor_temps_ab,
				I,
				P_direct + P_other,
				min_temp,
				thermostat
			)
			t.extend(new_t)
			T.extend(new_T)
			Q.extend(new_Q)
			S.extend(new_S)
			# Record the electricity usage for this step
			i = int(2*(t_a-start_t))
			elec_use[i] += thstat_E + (actual_I + P_direct) * (t_b - t_a)

		return t, T, Q, S, elec_use

	def _simulation_step(self, t_interval, init_vals, outdoor_temps, I, P, min_temp, thstat=False):
		"""
		Perform a step of the heat simulation and return the results.

		If temperature starts at, or at any point reaches, <= min_temp, the
		storage	heater's heat is discharged to keep the indoors at that
		temperature for as long as possible.

		I(t) and P(t) are constant, except that I is reduced if necessary to
		keep the storage heater at or below its maximum temperature. A(t) is
		linearly interpolated from the temperatures provided.

		Arguments:
		  t_interval    A 2-tuple containing the time (in hours) at which this
		                simulation step begins and ends.
		  init_vals     The initial value of (T, Q, S).
		  outdoor_temps A 2-tuple containing the outdoor temperatures at t_interval[0]
		                and t_interval[1] respectively. Outdoor temperatures
		                between these times are linearly interpolated from
		                these values.
		  I             The current power input into the storage heater (assumed
		                constant throughout the step).
		  P             The current power input directly into the indoors (space
		                heating and other activity combined; assumed constant
		                throughout the step).
		  min_temp      The temperature the storage heater should maintain.
		  thstat        Bool whether additional themostatic heating should be
		                applied in real time to avoid T falling below min_temp.

		Returns:
		  t             An array of t values, with at least 100 sample points
		                (except if t_start == t_end, in which case only one)
		  T             An array of corresponding T values
		  Q             An array of corresponding Q values
		  S             An array of corresponding S values
		  actual_I      The actual value of I, accounting for any reduction
		                to avoid the storage heater exceeding its maximum
		                temperature.
		  thstat_E      The additional energy required for the heat demanded
		                by thstat == True.
		"""
		# The returned arrays will contain at least this many values
		num_sample_points = 100

		start_t, end_t = t_interval
		initial_T, initial_Q, initial_S = init_vals
		sh_is_charging = (I > 0)
		j = self.j_charging if sh_is_charging else self.j_passive
		t_vals = np.linspace(start_t, end_t, num_sample_points)
		thstat_E = 0

		# Do nothing if the simulation length is 0
		if start_t == end_t:
			return ([start_t], [initial_T], [initial_Q], [initial_S], I, 0)

		# Reduce I if necessary to prevent the storage heater from exceeding
		# its maximum temperature. This uses a fairly rough calculation, but
		# slightly under- or overshooting isn't a big deal.
		if I > 0:
			est_leakage = j * ((self.sh_max_temp + initial_S)/2 - initial_T)
			energy_for_max_temp = (self.sh_max_temp - initial_S) * self.C_sh
			max_I = est_leakage + energy_for_max_temp / (end_t - start_t)
			I = min(I, max_I)
			# Make sure I is not negative.
			I = max(I, 0)

		# Determine the outdoor temperature; since we're linearly interpolating,
		# it takes the form A(t) = U+Vt
		V = (outdoor_temps[1] - outdoor_temps[0]) / (end_t - start_t)
		U = outdoor_temps[0] - V*start_t

		# Perform an instantaneous heat transfer from the storage heater to the
		# rest of the property if necessary and possible.
		if initial_T < min_temp and initial_S > initial_T:
			if self.C_sh * (initial_S - min_temp) >= self.C * (min_temp - initial_T):
				initial_S -= self.C * (min_temp - initial_T) / self.C_sh
				initial_T = min_temp
			else:
				initial_T = initial_S = (
					(self.C*initial_T + self.C_sh*initial_S)
					/ (self.C + self.C_sh)
				)
			init_vals = (initial_T, initial_Q, initial_S)

		# Perform instantaneous direct heating if necessary and thstat is True.
		if thstat and initial_T < min_temp:
			thstat_E += self.C * (min_temp - initial_T)
			initial_T = min_temp

		# Determine which regime we are in
		eq1_initial_RHS = (
			self.k*(outdoor_temps[0] - initial_T)
			+ self.h*(initial_Q - initial_T)
			+ j * (initial_S - initial_T)
			+ P
		)
		eq4_initial_RHS = (
			self.k*(outdoor_temps[0] - initial_T)
			+ self.h*(initial_Q - initial_T)
			+ P + I
		)
		if thstat and initial_S <= initial_T <= min_temp and eq1_initial_RHS <= 0:
			# thstat is True, and T will drop below min_temp if we don't
			# add more heat.
			#
			# Simulate with fixed T = min_temp (i.e. eqns (2) and (5))
			T = min_temp * np.ones(len(t_vals))
			Q = solve_simple_ODE(
				start_t,
				initial_Q,
				-self.h / self.C_q,
				self.h * min_temp / self.C_q,
				0,
				t_vals
			)
			S = solve_simple_ODE(
				start_t,
				initial_S,
				-j / self.C_sh,
				(j * min_temp + I) / self.C_sh,
				0,
				t_vals
			)
			eq1_RHS = (
				self.k*(np.interp(t_vals, t_interval, outdoor_temps) - min_temp)
				+ self.h*(Q - T)
				+ j * (S - T)
				+ P
			)
			# If the storage heater gets charged enough to take over, or other
			# heat sources are sufficient, the thermostatic direct heat should
			# turn off
			termination_condition = np.logical_not(np.logical_and(
				S <= min_temp,
				eq1_RHS <= 0
			))
			# Calculate the energy that the thermostatic heat must deliver
			i = next(
				(i for i, b in enumerate(termination_condition) if b),
				len(termination_condition)
			)
			thstat_E += - np.trapz(eq1_RHS[:i], t_vals[:i])

		elif (
			initial_T <= min_temp
			and initial_S == initial_T
			and eq4_initial_RHS / (self.C_sh+self.C) >= (eq4_initial_RHS-I) / self.C
		):
			# The storage heater is at the same temperature as the property, and
			# keeping it that way is advantageous.
			T, Q, S = self._solve_eqns(t_vals, init_vals, "equalised", U, V, P, I)
			# If T ever rises above min_temp, terminate this step at that time
			# and (recursively) treat the remainder of the t_interval as a new
			# step. Otherwise just return the full simulated temperatures.
			termination_condition = T > min_temp

		elif initial_T <= min_temp and initial_T < initial_S and eq1_initial_RHS <= 0:
			assert initial_T == min_temp
			# Use the storage heater to maintain min_temp for as long as possible.
			T, Q, S = self._solve_eqns(t_vals, init_vals, "discharging", U, V, P, I)
			# If ever S falls below min_temp or the heat flow into the property
			# from sources other than the storage heater becomes sufficient to
			# increase T, terminate this step at that time and (recursively) treat
			# the remainder of the t_interval as a new step.
			# Otherwise just return the full simulated temperatures.
			A = U + V*t_vals
			eq1_RHS = (
				  self.k * (A - min_temp)
				+ self.h * (Q - min_temp)
				+ j * (S - min_temp)
				+ P
			)
			termination_condition = np.logical_or(S <= min_temp, eq1_RHS > 0)

		else:
			# It is either unnecessary or impossible to output heat from the
			# storage heater, so simulate with heat transfer only by conduction
			rgme = "charging" if sh_is_charging else "free"
			T, Q, S = self._solve_eqns(t_vals, init_vals, rgme, U, V, P, I)
			# The step should be terminated early if any of the three above
			# regimes are entered.
			A = U + V*t_vals
			eq1_RHS = (
				  self.k*(A - T)
				+ self.h*(Q - T)
				+ j * (S - T)
				+ P
			)
			eq4_RHS = self.k * ((U + V*t_vals) - T) + self.h * (Q - T) + P + I
			termination_condition = np.logical_or(
				np.logical_and(
					T <= min_temp,
					np.logical_or(
						np.logical_and(T < S, eq1_RHS <= 0),
						np.logical_and(
							eq4_RHS/(self.C_sh+self.C) >= (eq4_RHS-I)/self.C,
							T == S
						)
					)
				),
				np.logical_and(
					np.logical_and(
						thstat,
						S <= T,
					),
					np.logical_and(
						T <= min_temp,
						eq1_RHS <= 0
					)
				)
			)

		# If the regime changes partway through the step, only use the
		# simulation thereto and treat the remainder of the step appropriately
		# with a recursive call
		#
		# Sometimes floating point errors lead to termination_condition[0]
		# being True, so only count subsequent elements.
		i = 1 + np.argmax(termination_condition[1:])
		if termination_condition[i]:  # i.e. if any(termination_condition)
			t_2, T_2, Q_2, S_2, _, thstat_E_2 = self._simulation_step(
				[t_vals[i], end_t],
				(T[i], Q[i], S[i]),
				(U + V*t_vals[i], outdoor_temps[1]),
				I,
				P,
				min_temp,
				thstat
			)
			return (
				np.concatenate((t_vals[:i], t_2)),
				np.concatenate((T[:i], T_2)),
				np.concatenate((Q[:i], Q_2)),
				np.concatenate((S[:i], S_2)),
				I,
				thstat_E + thstat_E_2
			)
		else:
			return t_vals, T, Q, S, I, thstat_E

	def _solve_eqns(self, t_vals, init_vals, regime, U, V, P, I):
		"""
		Return a solution to this Building's ODEs at the specified t_vals.

		A(t) takes the form A(t) = U + Vt.

		Arguments:
		  t_vals        The values of t at which to evaluate the values of
		                T, Q and S.
		  init_vals     The value of (T, Q, S) at t = t_vals[0].
		  regime        A string indicating what regime to solve the equations
		                in. Can take the values "free" or "charging" (both
		                obeying eqns (1), (2) and (5), but with different
		                j values), "discharging" (constant T) or "equalised"
		                (T == S).
		  U             The value of U in A(t) = U + Vt.
		  V             The value of V in A(t) = U + Vt.
		  P             The value of P(t)
		  I             The value of I(t)

		Returns the arrays (T, Q, S) corresponding to t_vals.
		"""
		if regime in ["free", "charging"]:
			# Solve eqs (1), (2) and (5).
			eq1_const_term = (self.k * U + P) / self.C
			eq1_linear_term = (self.k * V) / self.C
			eq2_const_term = I / self.C_sh
			if regime == "free":
				M = self._ode_matrices["free"]
			else:
				M = self._ode_matrices["charging"]
			T, Q, S = solve_simple_vector_ODE(
				t_vals[0],
				init_vals,
				M,
				(eq1_const_term, 0, eq2_const_term),
				(eq1_linear_term, 0, 0),
				t_vals
			)
		elif regime == "equalised":
			# Solve eqs (4) and (5).
			eq4_const = (self.k * U + P + I) / (self.C_sh + self.C)
			eq4_linear = (self.k * V) / (self.C_sh + self.C)
			T, Q = solve_simple_vector_ODE(
				t_vals[0],
				init_vals[:2],
				self._ode_matrices["equalised"],
				(eq4_const, 0),
				(eq4_linear, 0),
				t_vals
			)
			S = T
		elif regime == "discharging":
			# Solve eqs (3) and (5)
			T_held = init_vals[0]
			eq3_const = (U*self.k + P + I - (self.k+self.h) * T_held) / self.C_sh
			eq3_linear = (self.k * V) / self.C_sh
			eq5_const = (self.h * T_held) / self.C_q
			T = T_held * np.ones(len(t_vals))
			Q, S = solve_simple_vector_ODE(
				t_vals[0],
				init_vals[1:],
				self._ode_matrices["discharging"],
				(eq5_const, eq3_const),
				(0, eq3_linear),
				t_vals
			)
		return T, Q, S



def solve_simple_vector_ODE(t0, Y0, M, A, B, t_vals):
	"""
	Return the solution to an ODE of the form Y'(t) = M Y(t) + A + Bt (for
	vector Y(t), constant vectors A, B, and constant matrix M), evaluated at the
	specified t values.

	The initial condition is Y(t0) = Y0.

	M is specified as a DiagonalisedMatrix.

	Returns a list of the solutions for each component of Y.
	"""
	# Defining Z := E_inv @ Y, the equation becomes:
	#   Z'(t) = np.diag(e) @ Z(t) + E_inv @ A + E_inv @ B * t
	# which can be solved component-wise by solve_simple_ODE().
	Z = np.array([
		solve_simple_ODE(t0, f0, e_i, c, d, t_vals)
		for f0, e_i, c, d in zip(M.E_inv @ Y0, M.e, M.E_inv @ A, M.E_inv @ B)
	])
	# Then use Y = E @ Z
	Y = [
		sum(
			E_component * Z_component
			for E_component, Z_component in zip(row, Z)
		)
		for row in M.E
	]
	return Y


def solve_simple_ODE(t0, f0, X, Y, Z, t_vals):
	"""
	Return the solution to an ODE of the form f'(t) = Xf(t) + Y + Zt (for
	constant X, Y, Z), evaluated at the specified t values. The initial
	condition is f(t0) = f0.
	"""
	# Subsitute constants and t_vals into algebraic solution
	if X == 0:
		C = f0 - Y * t0 - Z * (t0 ** 2) / 2
		return C + Y * t_vals + Z * (t_vals ** 2) / 2
	else:
		t_vals = np.array(t_vals)
		exp_part = np.exp(X * (t_vals - t0))
		reciprcl_X = X ** -1
		reciprcl_X_sqrd = reciprcl_X * reciprcl_X
		return (
			exp_part * (
				f0
				+ reciprcl_X * (Z*t0 + Y)
				+ reciprcl_X_sqrd * Z
			)
			- reciprcl_X * (Z * t_vals + Y)
			- reciprcl_X_sqrd * Z
		)



class DiagonalisedMatrix:
	"""
	A square matrix of which the diagonalised form has been pre-calculated.

	Provides as attributes a vector of eigenvalues e and matrices E and E_inv
	such that the original matrix will be given by E @ np.diag(e) @ E_inv,
	and E @ E_inv yields the identity.
	"""

	def __init__(self, M):
		"""
		A square matrix of which the diagonalised form has been pre-calculated.

		Provides as attributes a vector of eigenvalues e and matrices E and E_inv
		such that the original matrix will be given by E @ np.diag(e) @ E_inv,
		and E @ E_inv yields the identity.

		M is the original matrix to be diagonalised.
		"""
		self.e, self.E = np.linalg.eig(M)
		self.E_inv = np.linalg.inv(self.E)
