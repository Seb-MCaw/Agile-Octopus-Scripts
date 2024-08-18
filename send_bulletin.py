"""
Send an email bulletin with tomorrow's unit prices and other useful information.

This is intended to be run once daily by cron or an equivalent.
"""



import datetime
import email
import mimetypes
import smtplib
import io
import zoneinfo

import numpy as np
import matplotlib.pyplot as plt

import config
import misc
import data
import price_forecasting
import price_optimisation



def prices_list(prices):
	"""
	Return a string containing the bulletin's list of tonight's prices.

	Each price is on a new line. A simple ASCII bar chart (with a logarithmic
	scale) is provided to the right of the prices.

	prices should be the list returned by data.get_agile_prices().
	"""
	output_str = ""
	start_time = misc.midnight_tonight(local=True) - datetime.timedelta(hours=1)
	for price, time in zip(prices, misc.datetime_sequence(start_time, 0.5)):
		if price == 0:
			graphical_price = ""
		elif price >= 0:
			graphical_price = '+'*(1 + int(20*np.log(1+0.1*price)))
		else:
			graphical_price = '-'*(1 + int(20*np.log(1-0.1*price)))
		output_str += f"{time.strftime('%H:%M')}    "
		output_str += f"{price:>5.2f}    {graphical_price}\n"
	return output_str

def consumption_paragraph():
	"""
	Return a string containing the bulletin's consumption paragraph.

	Summarises the total energy used, and cost thereof, for yesterday,
	the past week, the past month, the past year and the whole duration of
	the tariff. Includes usage up to midnight this morning, though treats
	unavailable consumption data as zero (if yesterday's data has not yet
	come through).
	"""
	output_string = ""
	one_day = datetime.timedelta(days=1)
	midnight_this_morning = misc.midnight_tonight(local=True) - one_day
	# Calculate the datetimes corresponding to the start of each period.
	yesterday_morning = midnight_this_morning - one_day
	today_weekday = midnight_this_morning.weekday()
	monday_morning = midnight_this_morning - one_day * (1 + (today_weekday-1)%7)
	if midnight_this_morning.day > config.OCTOPUS_BILL_DAY:
		# The current bill started on OCTOPUS_BILL_DAY this month
		bill_start = midnight_this_morning.replace(day=config.OCTOPUS_BILL_DAY)
	else:
		# The current bill started on OCTOPUS_BILL_DAY last month
		bill_start = (
			midnight_this_morning.replace(day=1) - one_day
		).replace(day=config.OCTOPUS_BILL_DAY)
	jan_bill_start = bill_start.replace(month=1)
	tariff_start_date = datetime.datetime.strptime(
		config.OCTOPUS_AGILE_JOIN_DATE,
		r"%Y-%m-%d"
	).replace(tzinfo=zoneinfo.ZoneInfo(config.TIME_ZONE))
	# Handle recently started tariff
	yesterday_morning = max(tariff_start_date, yesterday_morning)
	monday_morning = max(tariff_start_date, monday_morning)
	bill_start = max(tariff_start_date, bill_start)
	jan_bill_start = max(tariff_start_date, jan_bill_start)
	# Calculate the consumption for each time period
	periods = [
		(yesterday_morning, "Yesterday"),
		(monday_morning, "Since Monday"),
		(bill_start, "Since last bill"),
		(jan_bill_start, "Since January bill"),
		(tariff_start_date, "All time")
	]
	for period_start, period_name in periods:
		start = period_start
		end = midnight_this_morning
		energy, cost = data.get_actual_spend(start, end)
		cost_per_kwh = f"{cost/energy:.2f}" if energy != 0 else "-.--"
		output_string += (
			  f"{period_name:<20}{energy:.3f}kWh for £{cost/100:.4f} "
			+ f"({cost_per_kwh}p/kWh)\n"
		)
	return output_string

def cheapest_window_paragraph(prices):
	"""
	Return a string containing the bulletin's cheapest windows paragraph.

	prices should be a chronological list of half-hourly unit prices starting
	at 23:00 tonight.
	"""
	prices_start = misc.midnight_tonight(True) - datetime.timedelta(hours=1)
	paragraph = ""
	for window_length in (.5, 1, 1.5, 2, 2.5, 3, 4, 6):
		start, avg_price = price_optimisation.cheapest_window(
			window_length,
			{t:p for t,p in zip(misc.datetime_sequence(prices_start, 0.5), prices)}
		)
		if start is not None:
			paragraph += (
				  f"The cheapest {window_length} hour window starts at "
				+ f"{start.strftime('%H:%M')} (average {avg_price:.2f}p/kWh)\n"
			)
	return paragraph


def plot_prices(agile_prices, price_forecast=None, tom_min_max=False, format="png"):
	"""
	Return a plot of tomorrows prices and (optionally) the 7-day price forecast.

	The raw file data is returned as bytes.

	agile_prices and (if specified) price_forecast should be the return values
	of data.get_agile_prices() and price_forecasting.gen_price_forecast()
	respectively.

	Horizontal lines showing the minimum and maximum of tomorrow's prices are
	shown if tom_min_max is True.

	format is passed as a keyword argument to the matplotlib.pyplot.Figure.savefig()
	method.
	"""
	one_hour = datetime.timedelta(hours=1)
	zero_hour = misc.midnight_tonight()
	# Create the figure
	fig = plt.figure()
	ax = fig.add_subplot()
	ax.set_xlabel("Time")
	ax.set_ylabel("Price (p / kWh)")
	ax.grid(which="major", axis="x", color="gray")
	ax.grid(which="minor", axis="x", color="lightgray")
	ax.grid(which="major", axis="y", color="lightgray")
	ax.set_xticks(np.linspace(-1, 200, 202), minor=True)
	ax.set_yticks(np.linspace(-100, 100, 41))
	# Plot tomorrow's prices with constant values apart from a discontinuous
	# jump at the boundaries between settlement periods
	times_in_hrs = np.array([n/2 - 1 for n in range(len(agile_prices))])
	times = [zero_hour + x * one_hour for x in times_in_hrs]
	ax.plot(
		np.array(list(zip(times_in_hrs, times_in_hrs + 0.5))).flatten(),
		np.repeat(agile_prices, 2),
		"k-"
	)
	# Plot the forecast
	if price_forecast is None:
		# Plot only tomorrow if price_forecast is not provided
		ax.set_xlim([-1, times_in_hrs[-1] + 0.5])
		ax.set_ylim([min(0, min(agile_prices) - 2), max(agile_prices) + 2])
		max_x = int(times_in_hrs[-1] + 0.5)
		x_tick_interval = 4
		x_tick_format = r"%H:%M"
	else:
		# Ensure times are entirely UTC
		price_forecast = {
			t.astimezone(datetime.timezone.utc) : price_forecast[t]
			for t in price_forecast
		}
		# Plot the price forecast if given
		times = []
		for t in sorted(price_forecast.keys()):
			if len(times) == 0 or t - times[-1] == 0.5 * one_hour:
				times.append(t)
		times_in_hrs = np.array([
			(t-zero_hour) / one_hour for t in times
		])
		ax.plot(
			np.array(list(zip(times_in_hrs, times_in_hrs + 0.5))).flatten(),
			np.repeat([price_forecast[t] for t in times], 2),
			"b--"
		)
		# Adjust width to 8 days
		fig.set_size_inches(15, 4.8)
		max_x = 192
		x_tick_interval = 24
		x_tick_format = 15*" " + r"%Y-%m-%d" # (padded to left-align)
		ax.set_xlim([-1, min(max_x, max(times_in_hrs))])
		y_min = min(0, min(agile_prices) - 2, min(price_forecast.values()) - 2)
		y_min = max(-25, y_min)  # Limit effect of excessively negative forecast
		ax.set_ylim([
			y_min,
			max(max(agile_prices), max(price_forecast.values())) + 2
		])
	# Handle xticks (such that they occur at the same clock hours even when
	# there's a daylight savings switchover)
	local_zero_hour = zero_hour.astimezone(zoneinfo.ZoneInfo(config.TIME_ZONE))
	x_tick_times = [
		t for t in misc.datetime_sequence(local_zero_hour, 1, max_x+1)
		if t.hour % x_tick_interval == 0
	]
	x_tick_hrs = [
		(t.astimezone(datetime.timezone.utc) - zero_hour) / one_hour
		for t in x_tick_times
	]
	x_tick_labels = [
		t.strftime(x_tick_format) for t in x_tick_times
	]
	if price_forecast is not None:
		# Omit last label when plotting 8 days
		x_tick_labels[-1] = ""
	ax.set_xticks(
		x_tick_hrs,
		labels=x_tick_labels
	)
	# Show tomorrows min and max if tom_min_max is True
	if tom_min_max:
		ax.plot([-1, 200], [min(agile_prices)]*2, "g--")
		ax.plot([-1, 200], [max(agile_prices)]*2, "r--")
	# Create and return the file
	with io.BytesIO() as buf:
		fig.savefig(buf, format=format)
		file_bytes = buf.getvalue()
	return file_bytes


def send_email(subj, body, attachments={}):
	"""
	Send an email with the SMTP server and recipient address from config.

	subj is a string containing the email's Subject header.

	body is a string containing the email's message content (which is
	text/plain).

	attachments should be a dictionary where each key is the name of a file
	(as a string) and the corresponding value is a bytes containing the file
	data. MIME types are guessed from the file extension.
	"""
	msg = email.message.EmailMessage()
	msg.set_content(body)
	msg['Subject'] = subj
	msg['From'] = config.SENDER_ADDRESS
	msg['To'] = config.TO_ADDRESS
	for attachment_name in attachments:
		mime_type_str = mimetypes.guess_type(attachment_name)[0]
		mime_type, mime_subtype = mime_type_str.split("/")
		msg.add_attachment(
			attachments[attachment_name],
			mime_type,
			mime_subtype,
			filename=attachment_name
		)
	with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as smtp_server:
		smtp_server.login(config.SENDER_ADDRESS, config.SMTP_AUTH_PASS)
		smtp_server.send_message(msg)




def main():
	"""
	Construct and send the email bulletin
	"""
	# Obtain the raw data from the relevant APIs
	data.update_agile_prices() # This goes first because it may take a while
	data.update_temperature_forecast()
	data.update_nat_grid_demand_forecast()
	data.update_nat_grid_wind_forecast()
	agile_prices = data.get_agile_prices()
	price_forecast = price_forecasting.gen_price_forecast()

	script_start_time = datetime.datetime.now()

	# Construct email body and subject
	today = misc.midnight_tonight(local=True) - datetime.timedelta(days=1)
	today_str = today.strftime(r'%Y-%m-%d')
	subj = f"Agile Octopus Bulletin ({today_str})"
	email_body = f"""Agile Octopus Bulletin {today_str}


Consumption (excluding standing charge) as of 00:00 this morning:
{consumption_paragraph()}

{cheapest_window_paragraph(agile_prices)}

The Agile Octopus electricity rates from 23:00 tonight are as follows:
{prices_list(agile_prices)}


Calculations took {(datetime.datetime.now() - script_start_time).total_seconds():.2f} seconds.
"""

	# Plot tomorrow's prices on their own
	price_plot = plot_prices(agile_prices, format="svg")
	attachments = {"prices_tomorrow.svg" : price_plot}
	# Plot the price forecast for the next 7 days, with tomorrow's prices for
	# comparison
	if len(price_forecast) > 0:
		price_forecast_plot = plot_prices(agile_prices, price_forecast, True, "svg")
		attachments["price_forecast.svg"] = price_forecast_plot

	send_email(subj, email_body, attachments)




if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		# Send an email with an error message in the event of an unhandled
		# exception
		send_email(
			f"Agile Octopus Bulletin Error",
			f"The Agile Octopus send_bulletin script encountered an "
			+ f"unhandled exception:\r\n\r\n\t{e.__class__.__name__}: {e}"
		)
