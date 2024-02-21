Agile Octopus Scripts
=====================

A couple of scripts which have gradually developed over the time I have been
on Octopus Energy's [*Agile Octopus*](https://octopus.energy/smart/agile/)
electricity tariff.

`config.py` should be populated before using either of them.


`send_bulletin`
---------------

This script is intended to be run daily (when each batch of prices is
published). It sends an email containing tomorrow's prices, a few quantities
derived therefrom, and a summary of the cost of recent usage.

It also includes a rough TensorFlow-based forecast of the prices for the
following seven days, based on the National Grid's demand and wind generation
forecasts. This must first be trained with the `train_price_forecast` script.


`plan_heating`
--------------

This script implements a simple simulation of the heating and cooling of
a building (as defined in the config), and uses it to determine the cheapest
combination of heating for the next few days. This is non-trivial, as it
often works out cheaper to heat the property to a higher temperature on a
day with low prices so no heating is needed on more expensive subsequent days.
