
# ------------------------------ Email Bulletin ------------------------------ #

# SMTP info for sending the alert email
SENDER_ADDRESS = "sender@gmail.com"
SMTP_AUTH_PASS = "password1234"
TO_ADDRESS = "recipient@example.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465





# ------------------------------- Data & APIs  ------------------------------- #

# The directory in which to keep a record of past data.
# Leave blank to use the current working directory.
DATA_DIRECTORY = ""
# The names of each of the data files that are saved in DATA_DIRECTORY
TEMPERATURE_FILE = "temperatures.csv"
PRICE_FILE = "prices.csv"
NAT_GRID_DEMAND_FILE = "national_grid_demand_forecast.csv"
NAT_GRID_WIND_FILE = "national_grid_wind_forecast.csv"
# The file in which to save the model & weights for price forecasting
FORECAST_MODEL_FILE = "forecast_model.keras"

# The datetime format to use in these csv files
FILE_DATETIME_FORMAT = r"%Y-%m-%dT%H:%M:%SZ"

# API key for the Site Specific Global Spot subscription on MetOffice DataHub
# (the free plan is sufficient)
METOFFICE_API_KEY = "<insert key>"





# --------------------------- Agile Octopus Tariff --------------------------- #

# The time zone according to which the Agile tariff operates
TIME_ZONE = "Europe/London"

# The day of the month on which bills are sent (such that the next bill starts
# from 00:00 that morning; this is the day before the Bill Reference date)
#
# Note that if this is the 29th, 30th or 31st, months with fewer days will not
# behave as expected.
OCTOPUS_BILL_DAY = 1
# The date on which the agile tariff started (for the "all time" total cost
# calculation)
OCTOPUS_AGILE_JOIN_DATE = "2018-02-21"

# The product code for the tariff which should be used
OCTOPUS_AGILE_PRODUCT_CODE = "AGILE-FLEX-22-11-25"
# The letter code for the region whose tariff should be used
OCTOPUS_AGILE_REGION_CODE = "A"

# API information
OCTOPUS_API_KEY = "<insert key>"
OCTOPUS_METER_SERIAL_NO = "<insert meter serial number>"
OCTOPUS_MPAN = "<insert meter point admin number>"





# ---------------------------- Heating Simulation ---------------------------- #

# All values in kW, hours, degrees Celsius and appropriate combinations thereof


# The property is modelled as three components, each at their own temperatures,
# with a thermally conductive connection to the outdoors.

# The first component consists of the air and any highly thermally conductive
# contents, and represents the actual/useful temperature experienced by
# occupants. The other two components and the outdoors are connected to this
# component, each with their own thermal conductance, and not to each other.
FAST_HEAT_CAPACITY = 0.1
CONDUCTANCE_TO_OUTDOORS = 0.1

# The second component consists of any contents of the property (other than
# the storage heater) with low conductance and/or high heat capacity, which will
# take a long time to respond to temperature changes.
SLOW_HEAT_CAPACITY = 5
SLOW_CONDUCTANCE = 1

# The third component is a storage heater, which can store heat internally
# during user-determined hours and release it on demand.
# Its behaviour is parametrised as follows:
#
# Total capacity of fully charged storage heater in kWh
STORAGE_HEATER_SIZE = 3
# The power at which the storage heater charges
STORAGE_HEATER_POWER = 3
# The internal temperature (celsius) when the heater is fully charged (this will
# generally be of little consequence, so a reasonable guess is probably fine)
STORAGE_HEATER_MAX_TEMP = 50
# This script models an old and primitive design of storage heater which can't
# charge without also running the output fans. This is assumed to result in
# heat leakage (in addition to normal conductance) during charging at a rate
# proportional to the internal temperature above ambient. The figure here
# specifies the power leaked when the heater is at its full temperature.
# Set this to zero for a more conventional storage heater.
STORAGE_HEATER_CHARGE_LEAKAGE = 1
# The storage heater will gradually leak heat to the rest of the property over
# time. If the storage heater is fully charged and then both input and output
# are set to 0 (and the indoor air is held at approximately MIN_TEMP), this
# figure is the approximate time in hrs for which it will remain noticably
# warm (~10C above MIN_TEMP).
STORAGE_HEATER_STORE_TIME = 48

# If there is any direct heating which can be (safely) run on a timer, this
# figure specifies the maximum power output thereof
DIRECT_HEATING_POWER = 3

# Approximate daily heat output of other activity in kWh.
# This includes heat both from living occupants, and from other electricity use
# (food preparation etc). For simplicity, assumed to be dissapated at a
# constant rate 24/7.
OTHER_HEAT_OUTPUT = 6

# The approximate latitude and longitude of the property for weather forecasting
LATITUDE = 51.508
LONGITUDE = -0.128


# The heating planner will attempt to maintain an indoor temperature within
# a certain range, except during specified hours when another range applies.
# The intention is that the latter is for times when the residents are absent,
# asleep or similar.
#
# Temperature range in celsius considered acceptable for the interior of the property
MAX_TEMP = 24
MIN_TEMP = 16
# Ranges of hours (24hr clock) for which a different range should apply.
# These ranges should not overlap.
ABSENT_HOURS = [(0, 8)]
# Temperature range in celsius considered acceptable during the times specified
# by ABSENT_HOURS
ABS_MAX_TEMP = 30
ABS_MIN_TEMP = 5





# --------------------------- Heating Optimisation --------------------------- #

# Multiple heating periods may be inconvenient, e.g. if timers must be set
# manually. This value specifies the minimum saving (in pence) for an additional
# heating period to be considered worthwhile when optimising heating settings.
HEATING_PERIOD_PENALTY = 5
# The optimiser may fail to achieve acceptable temperatures at the very start
# of the simulation (e.g. if the initial starting temperature is already below
# the minimum, finite power limits will preclude reaching it instantaneously),
# and give up on heating altogether as a result.
# To avoid this, it can be set to ignore unacceptable temperatures for the first
# few hours, specified here, of the simulation to give the heating a chance.
IGNORE_INITIAL_TEMP_HOURS = 2

# The number of threads to use for running simulations in parallel when
# optimising heating settings. Increase if CPU utilisation is low and decrease
# if MemoryErrors occur frequently.
HEAT_OPTIMISATION_THREADS = 6
# The popsize for the differential evolution process by which heating settings
# are optimised. Larger values give a more thorough search, but longer run
# times.
HEAT_OPTIMISATION_POPSIZE = 64
