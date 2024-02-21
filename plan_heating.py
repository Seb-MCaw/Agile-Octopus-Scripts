"""
Run simulations of the heating and cooling of a building to determine the
cheapest heating which will last for different lengths of time.

The building and optimisation parameters are speecified in config.py.
"""


import datetime
import warnings

import numpy as np
import matplotlib.pyplot as plt

import config
import misc
import data
import heating_simulation
import price_optimisation



warnings.filterwarnings("ignore", message="delta_grad == 0.0. Check if the approximated function is linear.")



def heating_options(
	outdoor_temps, start_time, start_indoor_temp, end_times, prices, num_heats
):
	"""
	Find the optimal heating settings to maintain acceptable temperatures
	until each time in end_times.

	The parameters of the heating simulation and the acceptable temperature
	range(s) are taken from the config module.

	Prints its progress to stdout on the current line.

	Arguments:
	  outdoor_temps     A sequence of forecast hourly outdoor ambient
	                    temperatures. outdoor_temps[0] should give the
	                    temperature at start_time.
	  start_time        The time at which to start the heating simulation
	                    (as a datetime.datetime).
	  start_indoor_temp The value of all components of the building (i.e.
	                    T==Q==S==start_indoor_temp) at start_time.
	  end_times         A collection of different times up to which acceptable
	                    temperatures are to be maintained. The returned list
	                    will contain one element corresponding to each.
	  prices            A sequence of the half-hourly unit prices (p/kWh) on
	                    the Agile tariff. prices[0] should give the price
	                    at t=init_vals[0].
	                    Heating will only be used during the time for which
	                    prices are available.
	  num_heats         The maximum length of the returned "storage_heat" and
	                    "direct_heat" lists.

	Returns a list containing, for each possibility, dictionaries with the
	key-value pairs:
	  "lasts_until"     The time when the temperature first actually becomes
	                    unacceptable (as datetime.datetime).
	                    The returned list is sorted ascending on this value.
	  "storage_heat"    A list of 2-tuples defining the time periods for which
	                    the storage heaters should charge. Each specifies
	                    non-overlapping (start, end) times as datetime.datetimes.
	  "direct_heat"     A list of 3-tuples defining the heating which should be
	                    applied directly to the air in the building (via space
	                    heaters etc). The first 2 elements of each specify a
	                    time period over which it is applied as for
	                    "storage_heat", while the third gives the power input
	                    in kW.
	  "total_price"     The total cost in pence of implementing this heating
	  "marginal_price"  The marginal cost in pence of implementing this heating
	                    (i.e. the difference between the cost of this option and
	                    the previous one, when sorted by end_time ascending).
	  "total_energy"    The total energy in kWh used in implementing this heating.
	  "marg_tot_energy" The marginal value of "total_energy".
	  "useful_energy"   The minimum amount of energy required to maintain
	                    acceptable temperatures for this time span, as
	                    calculated by price_optimisation.useful_heat_energy().
	  "marg_usfl_enrgy" The marginal value of "useful_energy".
	  "t"               An array of time values (as hours after start_time).
	  "T"               An array of the simulated indoor temperatures
	                    corresponding to "t".
	"""
	end_times = sorted(end_times)
	num_hours = (max(end_times) - start_time) / datetime.timedelta(hours=1)
	if len(outdoor_temps) < num_hours + 1:
		raise ValueError("Insufficient temperature data")
	building = heating_simulation.building_from_config()
	temp_ranges = price_optimisation.temp_ranges_from_config(start_time, 0, num_hours)
	temp_ranges.sort(key=lambda x: x[0])

	# Adjust temp_ranges in line with the configured IGNORE_INITIAL_TEMP_HOURS
	num_hours_to_ignore = config.IGNORE_INITIAL_TEMP_HOURS
	if num_hours_to_ignore > 0:
		while len(temp_ranges) > 1 and temp_ranges[1][0] <= num_hours_to_ignore:
			temp_ranges = temp_ranges[1:]
		if temp_ranges[0][0] < num_hours_to_ignore:
			temp_ranges[0] = (num_hours_to_ignore,) + temp_ranges[0][1:]
		temp_ranges = [(0, -np.inf, np.inf)] + temp_ranges

	output = []
	print(f"\r0/{len(end_times)}", end="")
	for i, end_time in enumerate(end_times):
		end_t = (end_time - start_time) / datetime.timedelta(hours=1)
		# Perform the optimisation
		s_heat, d_heat, cost, act_end_t, sim_temps = price_optimisation.cheapest_heat(
			building,
			temp_ranges,
			(0, start_indoor_temp),
			config.DIRECT_HEATING_POWER,
			[(0, num_hours, config.OTHER_HEAT_OUTPUT/24)],
			outdoor_temps,
			prices,
			end_t,
			num_heats,
			config.HEATING_PERIOD_PENALTY
		)
		t, T, Q, S = sim_temps
		# Calculate total energy
		tot_energy = 0
		for s, e in s_heat:
			tot_energy += building.sh_charge_pwr * (e - s)
		for s, e, p in d_heat:
			tot_energy += p * (e - s)
		# Calculate useful energy
		useful_energy = price_optimisation.useful_heat_energy(
			building,
			temp_ranges,
			(0, start_indoor_temp),
			[(0, num_hours, config.OTHER_HEAT_OUTPUT/24)],
			outdoor_temps,
			end_t
		)
		# Remove zero heat inputs and convert t values back into datetimes
		s_heat = [
			(
				start_time + datetime.timedelta(hours=s),
				start_time + datetime.timedelta(hours=e)
			)
			for (s, e) in s_heat
			if e - s > 0
		]
		d_heat = [
			(
				start_time + datetime.timedelta(hours=s),
				start_time + datetime.timedelta(hours=e),
				p
			)
			for (s, e, p) in d_heat
			if p * (e - s) > 0
		]
		act_end_t = start_time + datetime.timedelta(hours=act_end_t)
		# Populate dictionary
		out_dict = {}
		out_dict["lasts_until"] = act_end_t
		out_dict["storage_heat"] = s_heat
		out_dict["direct_heat"] = d_heat
		out_dict["total_price"] = cost
		out_dict["total_energy"] = tot_energy
		out_dict["useful_energy"] = useful_energy
		out_dict["t"] = t
		out_dict["T"] = T
		if len(output) == 0:
			out_dict["marginal_price"] = cost
			out_dict["marg_tot_energy"] = tot_energy
			out_dict["marg_usfl_enrgy"] = useful_energy
		else:
			out_dict["marginal_price"] = cost - output[-1]["total_price"]
			out_dict["marg_tot_energy"] = tot_energy - output[-1]["total_energy"]
			out_dict["marg_usfl_enrgy"] = useful_energy - output[-1]["useful_energy"]
		output.append(out_dict)
		# Print progress
		print(f"\r{i+1}/{len(end_times)}", end="")
	print()
	output.sort(key=lambda x: x["lasts_until"])
	return output



if __name__ == "__main__":
	initial_indoor_temp = float(input(
		"Enter initial indoor temperature (\N{DEGREE SIGN}C):" + 22 * " "
	))
	max_days_to_last = int(input(
		"Enter maximum number of days heating should last for:       "
	))
	max_num_heats = int(input(
		"Enter maximum number of times to run each type of heating:  "
	))
	start_time = misc.midnight_tonight() - datetime.timedelta(hours=1) # 23:00

	# Get temperature forecast
	data.update_temperature_forecast()
	outdoor_temps = list(data.get_hourly_temperatures(start_time))
	# Prompt if temperature forecast isn't long enough
	num_missing_temps = 24*max_days_to_last - len(outdoor_temps)
	num_missing_temps += 1  # (fencepost)
	num_missing_temps += 1  # (start at 23:00, finish at 00:00)
	if num_missing_temps > 0:
		print(
			  "\nThe temperature forecast does not last long enough to simulate "
			+ "for this many days."
		)
		assumed_temp = float(input(
			  "Enter a constant outdoor temperature (Celsius) to assume for "
			+ "the remainder of the simulation:  "
		))
		outdoor_temps += [assumed_temp] * num_missing_temps

	# Get prices
	print("\nFetching prices...")
	data.update_agile_prices()
	agile_prices = data.get_agile_prices()
	# Warn the user to be aware of DST switchover if appropriate
	if len(agile_prices) == 0:
		raise RuntimeError("could not obtain prices")
	elif len(agile_prices) != 48:
		print("Warning: tomorrow appears to feature a daylight savings switchover.")
		print("Analogue timers may need the times below to be adjusted accordingly.")
	
	# Perform the optimisation
	print("\nCalculating options:")
	end_times = [
		misc.midnight_tonight() + datetime.timedelta(days=n)
		for n in range(1, 1 + max_days_to_last)
	]
	options = heating_options(
		outdoor_temps, start_time, initial_indoor_temp,
		end_times, agile_prices, max_num_heats
	)
	
	# Print the summary and populate the plot
	for i, opt in enumerate(options):
		lasts_in_days = (opt['lasts_until']-start_time) / datetime.timedelta(days=1)
		costs_str = "" if i == 0 else "an additional "
		sh_string = ", ".join([
			f"{start.strftime('%H:%M')}--{end.strftime('%H:%M')}"
			for start, end in opt["storage_heat"]
		])
		dh_string = ", ".join([
			f"{pwr}kW for {start.strftime('%H:%M')}--{end.strftime('%H:%M')}"
			for start, end, pwr in opt["direct_heat"]
		])
		if opt['marg_usfl_enrgy'] == 0:
			marg_usfl_enrgy = 1e-16 # (avoid div by 0)
		else:
			marg_usfl_enrgy = opt['marg_usfl_enrgy']
		print(
			  f"\nHeating until {opt['lasts_until'].strftime('%H:%M on %A')} "
			+ f"({lasts_in_days:.2f} days):"
			+ f"\n    Costs {costs_str}£{opt['marginal_price']/100:.2f} "
			+ f"({opt['marginal_price'] / marg_usfl_enrgy:.2f}p "
			+ f"per useful kWh)."
			+ f"\n    Run the storage heater for: {sh_string}"
			+ f"\n    Run direct heating at: {dh_string}"
			+ f"\n    Total energy: {opt['total_energy']:.1f}kWh"
		)
		plt.plot(
			np.array(opt["t"]) - 1, # (convert to hours after midnight)
			opt["T"],
			label=f"{lasts_in_days:.2f} days"
		)

	# Finish and show the plot
	plt.xlabel("Time (hrs after midnight tonight)")
	plt.ylabel("Temperature (\N{DEGREE SIGN}C)")
	plt.legend()
	plt.show()
