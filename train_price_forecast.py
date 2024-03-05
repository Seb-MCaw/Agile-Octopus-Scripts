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



class TrainingCallback(keras.callbacks.Callback):
	"""
	A callback for the training process.

	Prints the epoch number (as a percentage of num_epochs) and the current
	validation loss to stdout. This printout is preceeded by the static string
	specified by pre_str.

	Maintains the attributes best_val_loss and best_weights which store,
	respectively, the smallest value of the validation loss achieved so far
	and the weights which achieved it. Before the first training epoch is
	complete, they will both be None.
	"""

	def __init__(self, num_epochs, pre_str=""):
		self.num_epochs, self.pre_str = num_epochs, pre_str
		self.best_val_loss = None
		self.best_weights = None

	def on_epoch_end(self, epoch, logs=None):
		progress_percent = 100 * (epoch+1) / self.num_epochs
		print(f"\r{self.pre_str}{progress_percent:>6.2f}%", end="")
		if logs is not None and "val_loss" in logs:
			val_loss = logs['val_loss']
			print(
				f"    validation loss (mean abs error): {val_loss:>6.2f}",
				end=""
			)
			# Update best weights if appropriate
			if self.best_val_loss is None or val_loss < self.best_val_loss:
				self.best_weights = self.model.get_weights()
				self.best_val_loss = val_loss



if __name__ == "__main__":
	# User input
	num_runs = int(input("Enter number of training runs: "))
	num_epochs = int(input("Enter number of training epochs per run: "))

	# Update the csv files if necessary
	data.update_agile_prices(wait=False)
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
	print(f"\r{1}/{num_runs}:   0.00%", end="")
	results = []
	for i in range(num_runs):
		model_for_this_run = keras.models.clone_model(model)
		model_for_this_run.compile(
			optimizer=keras.optimizers.Adam(),
			loss=price_forecasting.loss_func,
			metrics=[price_forecasting.loss_func]
		)
		training_callback = TrainingCallback(
				num_epochs, f"{i+1}/{num_runs}: "
		)
		h = model_for_this_run.fit(
			[input_data_0, input_data_1],
			true_prices,
			epochs=num_epochs,
			validation_split=.05,
			verbose=0,
			callbacks=[training_callback]
		)
		if training_callback.best_weights is not None:
			model_for_this_run.set_weights(training_callback.best_weights)
			val_loss = training_callback.best_val_loss
		else:
			val_loss = h.history['val_loss'][-1]
		results.append((model_for_this_run, val_loss))
	print()
	model, val_loss = min(results, key=lambda x: x[1])

	# Print a summary of the trained model's performance
	model_pred = np.array(model.predict(
		[input_data_0, input_data_1], verbose=0
	))
	mean_err = price_forecasting.loss_func(true_prices, model_pred)
	max_err = np.max(np.abs(model_pred - true_prices))
	print(f"\nOverall loss (mean abs error): {mean_err}")
	print(f"Validation loss (mean abs error): {val_loss}")
	print(f"Overall maximum absolute error: {max_err}")

	# If there is already a previously trained model, present the user with a
	# choice of which to use going forward. Otherwise, just save the newly
	# trained model.
	save_requested = False
	try:
		prev_model = keras.models.load_model(
			os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
			custom_objects={
				"loss_func": price_forecasting.loss_func,
				"ParallelDenseLayer" : price_forecasting.ParallelDenseLayer
			}
		)
	except OSError:
		save_requested = True
	else:
		try:
			prev_model_loss = price_forecasting.loss_func(
				true_prices,
				np.array(prev_model.predict(
					[input_data_0, input_data_1],
					verbose=0
				))
			)
			print(
				  f"\nFor the same dataset, the previous model gives an overall "
				+ f"mean abs error of {prev_model_loss}."
			)
		except ValueError:
			print(
				  "\nA previous model was found but could not be evaluated "
				+ "(perhaps the model architecture has changed?)."
			)
		rsp = input("Overwrite with the new model [y/n]?  ")
		if rsp.lower() in ["y", "yes"]:
			save_requested = True
	if save_requested:
		model.save(
			os.path.join(config.DATA_DIRECTORY, config.FORECAST_MODEL_FILE),
			save_format="keras"
		)
		print("Model saved\n")
	else:
		print("Model not saved\n")
