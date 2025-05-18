import datetime
import uuid

from .core.solar_optimization import ParameterOptimizer
from .core.solar_calculator import SolarCalculator
from .core.energy_table import EnergyTable

class Workflow:

    def __init__(self):
        self.workflow_time = datetime.datetime.now()
        self.workflow_id = uuid.uuid4()
        self.config = None

    def load_config(self, config):
        ##TODO: implement validation of config file
        self.config = config

    def run(self):

        if self.config is None:
            raise ValueError("Load a config file first before running a workflow.")

        ##TODO: include province_shp into optimizer to optimize against correct points
        ##TODO: get monthly optimized values and not singe value for whole year
        optimizer = ParameterOptimizer(self.config)
        if optimizer.error_tbl is None:
            optimizer.optimize(dem=self.config['dem'], observation_dir = self.config['optimization']['optim_dir'])
        
        calculator = SolarCalculator(self.config)
        srad = calculator.calculate_radiation(dem = self.config['dem'], optimizer=optimizer)

        data = EnergyTable(srad, consumption)