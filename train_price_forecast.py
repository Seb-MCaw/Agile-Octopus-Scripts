"""
Train the price forecasting model on the data currently in config.DATA_DIRECTORY
"""


import os
import sys
import zoneinfo

import numpy as np
import keras

import config
import data
import price_forecasting


if __name__ == "__main__":
	# User input
	num_runs = int(input("Enter number of training runs: "))
	num_epochs = int(input("Enter number of training epochs per run: "))

	# Update the csv files if necessary
	data.update_agile_prices()
	data.update_nat_grid_demand_forecast()
	data.update_nat_grid_wind_forecast()

	# Load the data currently contained by the csv files and construct
	# the necessary input and output arrays
	print("\nLoading training data...")
	prices, demand, wind_gen = price_forecasting._get_data_from_csvs()
	input_data_0 = []
	input_data_1 = []
	true_prices = []
	local_tz = zoneinfo.ZoneInfo(config.TIME_ZONE)
	for date in set(t.astimezone(local_tz).date() for t in prices):
		input_arrays = price_forecasting.get_model_input(
			date, demand, wind_gen, prices
		)
		output_array = price_forecasting.construct_output_array(date, prices)
		if input_arrays is not None and output_array is not None:
			input_data_0.append(input_arrays[0])
			input_data_1.append(input_arrays[1])
			true_prices.append(output_array)
	input_data_0 = np.array(input_data_0)
	input_data_1 = np.array(input_data_1)
	true_prices = np.array(true_prices)

	if len(input_data_0) < 100:
		print("Insufficient data for training.")
		sys.exit()

	# Construct and train the model (multiple times if requested)
	model = price_forecasting.construct_forecast_model()
	print("\nTraining model...")
	print(f"\r{1}/{num_runs}: 0.00%")
	results = []
	for i in range(num_runs):
		model_for_this_run = keras.models.clone_model(model)
		model_for_this_run.compile(
			optimizer=keras.optimizers.Adam(),
			loss=price_forecasting.loss_func,
			metrics=[price_forecasting.loss_func]
		)
		h = model_for_this_run.fit(
			[input_data_0, input_data_1],
			true_prices,
			epochs=num_epochs,
			validation_split=.05,
			verbose=0,
			callbacks=[price_forecasting.ProgressPrintCallback(
				num_epochs, f"{i+1}/{num_runs}: "
			)]
		)
		results.append((model_for_this_run, h.history['val_loss'][-1]))
	print()
	model, val_loss = min(results, key=lambda x: x[1])

	# Print a summary of the trained model's performance
	model_pred = np.array(model.predict(
		[input_data_0, input_data_1], verbose=0
	))
	rms_err = np.sqrt(price_forecasting.loss_func(true_prices, model_pred))
	max_err = np.max(np.abs(model_pred - true_prices))
	print(f"\nOverall loss (rms error): {rms_err}")
	print(f"Validation loss (rms error): {np.sqrt(val_loss)}")
	print(f"Overall maximum absolute error: {max_err}")

	# If there is already a previously trained model, present the user with a
	# choice of which to use going forward. Otherwise, just save the newly
	# trained model.
	try:
		prev_model = keras.models.load_model(
			os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
			custom_objects={
				"loss_func": price_forecasting.loss_func,
				"ParallelDenseLayer" : price_forecasting.ParallelDenseLayer
			}
		)
		prev_model_loss = price_forecasting.loss_func(
			true_prices,
			np.array(prev_model.predict([input_data_0, input_data_1], verbose=0))
		)
		print(
			  f"\nFor the same dataset, the previous model gives an overall "
			+ f"rms error of {np.sqrt(prev_model_loss)}."
		)
		rsp = input("Save the new model [y/n]?  ")
		if rsp.lower() in ["y", "yes"]:
			model.save(
				os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
				save_format="keras"
			)
	except OSError:
		model.save(
			os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
			save_format="keras"
		)
