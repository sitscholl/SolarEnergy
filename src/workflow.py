import pandas as pd

import datetime

from .core.solar_calculator import SolarCalculator
from .visualization.report import Report

class Workflow:

    def __init__(self):
        self.workflow_time = datetime.datetime.now()
        self.config = None

    def load_config(self, config):
        ##TODO: implement validation of config file
        self.config = config

    def run(self):

        if self.config is None:
            raise ValueError("Load a config file first before running a workflow.")

        ##TODO: include province_shp into optimizer to optimize against correct points
        ##TODO: get monthly optimized values and not singe value for whole year
        calculator = SolarCalculator(self.config)
        if calculator.error_tbl is None:
            calculator.optimize(dem=self.config['dem'], observation_dir = self.config['optimization']['optim_dir'])
        
        srad = calculator.calculate_radiation(dem = self.config['dem'])

        if self.config.get('consumption_tbl'):
            consumption = pd.read_excel(self.config.get('consumption_tbl'), usecols = ['date', 'consumption'])
            consumption["date"] = pd.to_datetime(consumption['date'], format = '%Y-%m-%d')
        else:
            consumption = None
        data = Report(srad, consumption)