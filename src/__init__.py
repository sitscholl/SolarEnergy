from .solar import feature_insolation
from .transformation import convert_solar_energy, sample_solar_energy
from .plot import encode_plot, optim_lines
from .optim import get_optim_values, test_parameters, load_monthly_radiation
import logging

logging.getLogger('ipykernel').setLevel(logging.WARNING)
logging.getLogger('positron_ipykernel').setLevel(logging.WARNING)
