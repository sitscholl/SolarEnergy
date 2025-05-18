


from .core.solar_optimization import ParameterOptimizer
from .core.solar_calculator import SolarCalculator

class Workflow:

    def __init__(self, config):
        self.config = config

    def run(self):
        ##TODO: include province_shp into optimizer to optimize against correct points
        ##TODO: get monthly optimized values and not singe value for whole year
        optimizer = ParameterOptimizer(self.config)
        if optimizer.error_tbl is None:
            optimizer.optimize(dem=dem, observation_dir = self.config['optimization']['optim_dir'])
        
        calculator = SolarCalculator(self.config)
        calculator.calculate_radiation(dem = dem, optimizer=optimizer)