"""
Optimise electricity usage to minimise cost on Octopus Energy's agile tariff.
"""


import datetime
import zoneinfo

import numpy as np
import scipy.optimize

import config


def cheapest_window(length, prices):
	"""
	Find the time window of the specified length with the lowest average unit price.

	Returns the start datetime of the window and its average price.

	length must be a positive integer multiple of 0.5, specifying the length
	of the window in hours.

	prices should be a dictionary with the start of each settlement period
	(timezone aware datetime.datetime) as keys and the corresponding unit
	prices as values.

	Returns None if prices contains no valid windows of the required length.

	Later windows are preferred in the event of a tie.
	"""
	# Convert all times to UTC
	arg_times = {t.astimezone(datetime.timezone.utc) : t for t in prices}
	prices = {t.astimezone(datetime.timezone.utc) : prices[t] for t in prices}
	# Convert length to units of half-hours
	length = int(2*length)
	# Try every start time to find the cheapest
	best_average_price = None
	best_start_time = None
	times = sorted(prices.keys())
	for start_idx, start_time in enumerate(times[: -length]):
		window_times = times[start_idx : start_idx + length]
		no_gaps = all(
			t_1 + datetime.timedelta(hours=0.5) == t_2
			for t_1, t_2 in zip(window_times, window_times[1:])
		)
		if no_gaps:
			avg_price = sum(prices[t] for t in window_times) / length
			if best_average_price is None or avg_price <= best_average_price:
				best_average_price = avg_price
				best_start_time = start_time
	return arg_times[best_start_time], best_average_price





def temp_ranges_from_config(start_datetime, start_t, end_t):
	"""
	Generate a temp_ranges for the cheapest_heat() function from the config.

	The simulation should start at t=start_t and run until t=end_t.

	start_datetime specifies the time (timezone aware datetime.datetime) to
	which t=start_t in the simulation corresponds.
	"""
	hr = datetime.timedelta(hours=1)
	UTC = datetime.timezone.utc
	local_tz = zoneinfo.ZoneInfo(config.TIME_ZONE)
	start_datetime_UTC = start_datetime.astimezone(UTC)
	start_datetime_lcl = start_datetime.astimezone(local_tz)
	start_date_mdnght = start_datetime_lcl.replace(hour=0, minute=0, second=0)
	temp_ranges = []
	for a, b in config.ABSENT_HOURS:
		# Start from the day before the start of the simulation so we know
		# what temperatures apply at t=0.
		for day_num in range(-1, 2+int((end_t - start_t) / 24)):
			time_a = start_date_mdnght + datetime.timedelta(days=day_num, hours=a)
			time_b = start_date_mdnght + datetime.timedelta(days=day_num, hours=b)
			t_a = (time_a.astimezone(UTC) - start_datetime_UTC) / hr
			t_b = (time_b.astimezone(UTC) - start_datetime_UTC) / hr
			temp_ranges.append((t_a, config.ABS_MIN_TEMP, config.ABS_MAX_TEMP))
			temp_ranges.append((t_b, config.MIN_TEMP, config.MAX_TEMP))
	return temp_ranges


def cheapest_heat(building, temp_ranges, init_vals, dh_max_pow, other_heat,
                  outdoor_temps, prices, end_t, num_heats, penalty_per_heat):
	"""
	Return the cheapest heating which maintains acceptable temperatures for
	the specified time.

	The t values at which the heating starts/ends will be multiples of 10
	minutes and the powers used will be multiples of 0.5kW.

	The parameters of the optimisation process are specified in the config
	module.

	Arguments:
	  building          The heating_simulation.Building for which the heating
	                    should be optimised.
	  temp_ranges       A collection of 3-tuples specifying the range of
	                    temperatures which are considered acceptable at
	                    different times. The first element of each is a t
	                    value, while the second and third are minimum and
	                    maximum temperatures respectively which apply from
	                    that t value until the next one. temp_ranges[0][0]
	                    should equal init_values[0].
	  init_vals         The initial value of either (t, T) or (t, T, Q, S).
	                    In the former case, assumes Q == S == T initially.
	  dh_max_pow        The maximum power that can be provided by direct
	                    heating; i.e. the maximum value of the third element
	                    of any tuple in the returned direct_heat list.
	  other_heat        A list of 3-tuples defining incidental or unavoidable
	                    heating (e.g. from residents' metabolism or cooking)
	                    which is applied directly to the air in the building
	                    but which shouldn't factor into cost calculation.
	                    The first 2 elements of each specify a time period
	                    over which it is applied as non-overlapping (start, end)
	                    t values, while the third gives the power input in kW.
	  outdoor_temps     A sequence of forecast hourly outdoor ambient
	                    temperatures. outdoor_temps[0] should give the
	                    temperature at t=init_vals[0].
	  prices            A sequence of the half-hourly unit prices (p/kWh) on
	                    the Agile tariff. prices[0] should give the price
	                    at t=init_vals[0].
	                    Heating will only be used during the time for which
	                    prices are available.
	  end_t             The t value until which acceptable temperatures
	                    should be maintained. If insufficient outdoor_temps
	                    are provided to simulate up to this time, the end of
	                    the simulation will be used instead.
	  num_heats         The maximum length of the returned storage_heat and
	                    direct_heat sequences.
	  penalty_per_heat  An amount by which to penalise any non-zero element
	                    of the returned storage_heat and direct_heat sequences
	                    (in pence), e.g. to represent the inconvenience of
	                    setting timers manually.
	                    The penalty is added during the optimisation process,
	                    but will not be included in the returned cost value.

	For the cheapest heating scheme found, returns:
	  storage_heat      The storage_heat argument to building.simulate_heat()
	  direct_heat       The direct_heat argument to building.simulate_heat()
	  tot_energy        The total energy actually used by storage_heat and
	                    direct_heat
	  cost              The cost of this energy in pence
	  actual_end_t      The t value until which acceptable temperatures are
	                    actually maintained.
	  sim_temps         A tuple of (t, T, Q, S) arrays containing the results
	                    of the simulation.
	"""
	start_t = init_vals[0]
	if len(init_vals) == 2:
		init_vals = (start_t, init_vals[1], init_vals[1], init_vals[1])
	temp_ranges = sorted(temp_ranges, key=lambda x: x[0])

	if num_heats > 0:
		# Heating times must be between the start of the simulation and the end
		# of the prices, while power values must be <= dh_max_pow. See
		# _sim_heat_args() for an explanation of the ordering of the array.
		total_prices_time = 0.5 * len(prices)
		bounds = (
			num_heats * [
				(0,total_prices_time), (0,total_prices_time)
			]
			+ num_heats * [
				(0,total_prices_time), (0,total_prices_time), (0,dh_max_pow)
			]
		)
		# We only need to know whether temps are maintained until end_t, so
		# truncate the simulation just thereafter for performance reasons.
		od_temps = outdoor_temps[: 2 + int(end_t - start_t)]
		# Use differential evolution to find the optimum argument for the cost
		# function.
		s = scipy.optimize.differential_evolution(
			_cheapest_heat_cost_func,
			bounds,
			args=(
				building, temp_ranges, init_vals, other_heat,
				od_temps, prices, end_t, penalty_per_heat
			),
			popsize=config.HEAT_OPTIMISATION_POPSIZE,
			atol=.5, # i.e. half a penny
			polish=True,
			workers=config.HEAT_OPTIMISATION_THREADS,
			updating="deferred"
		).x
	else:
		# No need to perform optimisation if no heating is allowed
		s = []
	# Convert that argument into the desired format, and re-perform the
	# simulation to derive the remaining return values.
	prices_end_t = start_t + 0.5 * len(prices)
	storage_heat, direct_heat = _sim_heat_args(s, start_t, prices_end_t, True)
	t, T,Q,S, usage = building.simulate_heat(
		init_vals, storage_heat, direct_heat, other_heat, outdoor_temps, temp_ranges
	)
	cost = _energy_cost(prices, usage)
	actual_end_t = _first_deviation_from_acceptable(t, T, temp_ranges)

	return storage_heat, direct_heat, sum(usage), cost, actual_end_t, (t, T, Q, S)

def _cheapest_heat_cost_func(s, building, temp_ranges, init_vals, other_heat,
                             outdoor_temps, prices, end_t, penalty_per_heat):
	"""
	The objective function for the optimisation in cheapest_heat()

	temp_ranges must be pre-sorted by t value ascending.
	"""
	start_t = init_vals[0]
	# Construct the (rounded) heat arguments for the simulation.
	# The heating should end at the end of the available prices.
	prices_end_t = start_t + 0.5 * len(prices)
	storage_heat, direct_heat = _sim_heat_args(s, start_t, prices_end_t, True)
	# Require (by penalising otherwise) that zero-length (or zero-energy)
	# heating periods should be after non-zero heating periods in the
	# storage_heat and direct_heat lists, so that the optimiser need not
	# explore redundant parts of the search space.
	cost = 0
	sh_lengths = [(end - start) for (start, end) in storage_heat]
	for a, b in zip(sh_lengths, sh_lengths[1:]):
		if a == 0 and b != 0:
			cost += 1e20
	dh_energies = [pwr * (end - start) for (start, end, pwr) in direct_heat]
	for a, b in zip(dh_energies, dh_energies[1:]):
		if a == 0 and b != 0:
			cost += 1e20
	if cost != 0:
		return cost
	# Perform the simulation
	t, T,Q,S, usage = building.simulate_heat(
		init_vals, storage_heat, direct_heat, other_heat, outdoor_temps, temp_ranges
	)
	# We wish to minimise the cost in pence
	cost = _energy_cost(prices, usage)
	# Add a heavy penalty if the heat doesn't last long enough
	first_dev = _first_deviation_from_acceptable(t, T, temp_ranges)
	if first_dev < end_t:
		cost += 1e10 * (end_t - first_dev)
	# Add penalty for each non-zero bit of heat
	num_penalties = len([t for t in sh_lengths if t > 0])
	num_penalties += len([E for E in dh_energies if E > 0])
	cost += num_penalties * penalty_per_heat
	return cost

def _first_deviation_from_acceptable(t, T, temp_ranges):
	"""
	Helper function for _cheapest_heat_cost_func(); return the t value at
	which T first deviates outside of the acceptable range.

	Returns last t value if all T values are acceptable.

	temp_ranges must be sorted by t value ascending.
	"""
	min_temp, max_temp = temp_ranges[0][1:]
	next_temp_range_idx = 1
	for t_val, T_val in zip(t, T):
		# Determine what temp_range applies to this t value
		while (
			next_temp_range_idx < len(temp_ranges)
			and temp_ranges[next_temp_range_idx][0] < t_val
		):
			min_temp, max_temp = temp_ranges[next_temp_range_idx][1:]
			next_temp_range_idx += 1
		# Use the more permissive of the two limits for t values
		# exactly at the changeover between different time periods.
		if (
			next_temp_range_idx < len(temp_ranges)
			and temp_ranges[next_temp_range_idx][0] == t_val
		):
			min_temp = min(
				temp_ranges[next_temp_range_idx - 1][1],
				temp_ranges[next_temp_range_idx][1]
			)
			max_temp = max(
				temp_ranges[next_temp_range_idx - 1][2],
				temp_ranges[next_temp_range_idx][2]
			)
		# Check if the T value is acceptable
		if not (min_temp <= T_val <= max_temp):
			# This T value is unacceptable
			return t_val
	# All T values are acceptable
	return t[-1]

def _energy_cost(prices, usage):
	"""
	Calculate the cost in pence of the given half-hourly usage with the given
	half-hourly prices.

	Throws exception if prices are unavailable for periods with non-zero
	usage.
	"""
	l = min(len(prices), len(usage))
	if np.max(usage[l:]) > 0:
		raise ValueError("prices not available for all electricity use")
	return np.dot(prices[:l], usage[:l])

def _sim_heat_args(arr, start_t, max_t, rounded=False):
	"""
	Map a sequence of floats to the heat arguments for Building.simulate_heat().

	Returns (storage_heat, direct_heat).

	The returned t values will never exceed max_t.

	If rounded is True, all returned times will be rounded to the nearest
	10mins and all power values will be rounded to the nearest 0.5kW.

	The length of arr should be a multiple of 5. If this length is 5*n, the
	returned lists will each contain n heating periods.

	start_t specifies the value of t at the start of the simulation.

	The first 2*n elements are pairs of start and end times for the storage
	heater: it will turn on at arr[0] hours after the start of the simulation,
	then off arr[1] hours later, then on again arr[2] after that, etc.

	Likewise, the remaining elements are triplets of direct heating settings.
	The times (the first two elements of each triplet) are similarly cumulative,
	while the third element of each triplet is the power in kW.
	"""
	n = int(len(arr) / 5)
	last_t = start_t
	storage_heat = []
	for i in range(n):
		start = last_t + arr[2*i]
		end = start + arr[2*i + 1]
		if rounded:
			start = round(6 * start) / 6
			end = round(6 * end) / 6
		start = min(max_t, start)
		end = min(max_t, end)
		storage_heat.append((start, end))
		last_t = end
	last_t = start_t
	direct_heat = []
	for i in range(n):
		start = last_t + arr[2*n + 3*i]
		end = start + arr[2*n + 3*i + 1]
		power = arr[2*n + 3*i + 2]
		if rounded:
			start = round(6 * start) / 6
			end = round(6 * end) / 6
			power = round(2 * power) / 2
		start = min(max_t, start)
		end = min(max_t, end)
		direct_heat.append((start, end, power))
		last_t = end
	return storage_heat, direct_heat


def useful_heat_energy(building, temp_ranges, init_vals, other_heat,
                       outdoor_temps, end_t):
	"""
	Return the minimum heating (kWh) required to maintain acceptable temperatures.

	A perfect heating system is assumed, with no power limitation or timing
	constraints.

	Arguments:
	  building          The heating_simulation.Building for which the energy
	                    should be calculated.
	  temp_ranges       A collection of 3-tuples specifying the range of
	                    temperatures which are considered acceptable at
	                    different times. The first element of each is a t
	                    value, while the second and third are minimum and
	                    maximum temperatures respectively which apply from
	                    that t value until the next one. temp_ranges[0][0]
	                    should equal init_values[0].
	  init_vals         The initial value of either (t, T) or (t, T, Q, S).
	                    In the former case, assumes Q == S == T initially.
	  other_heat        A list of 3-tuples defining incidental or unavoidable
	                    heating (e.g. from residents' metabolism or cooking)
	                    which is applied directly to the air in the building
	                    but which shouldn't factor into cost calculation.
	                    The first 2 elements of each specify a time period
	                    over which it is applied as non-overlapping (start, end)
	                    t values, while the third gives the power input in kW.
	  outdoor_temps     A sequence of forecast hourly outdoor ambient
	                    temperatures. outdoor_temps[0] should give the
	                    temperature at t=init_vals[0].
	  end_t             The t value until which acceptable temperatures
	                    should be maintained.
	"""
	start_t = init_vals[0]
	if len(init_vals) == 2:
		init_vals = (start_t, init_vals[1], init_vals[1], init_vals[1])
	if len(outdoor_temps) < end_t - start_t + 1:
		raise ValueError("Insufficient temperature data")
	# Adjust temp_ranges so that no heat is used after end_t
	temp_ranges = [
		x for x in sorted(temp_ranges, key=lambda x: x[0]) if x[0] < end_t
	]
	temp_ranges.append((end_t, -np.inf, np.inf))
	# Run a simulation with the "perfect heating system" (and nothing else).
	outdoor_temps = outdoor_temps[:1+int(end_t-start_t)]
	t, T,Q,S, usage = building.simulate_heat(
		init_vals, [], "thermostat", other_heat, outdoor_temps, temp_ranges
	)
	return sum(usage)
