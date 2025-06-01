import pandas as pd
import yaml

import datetime
from pathlib import Path
import logging
import logging.config

from .core.solar_calculator import SolarCalculator
from .visualization.report import Report

logger = logging.getLogger(__name__)

class Workflow:

    def __init__(self):
        self.workflow_time = datetime.datetime.now()
        self.config = None

    def load_config(self, config):
        ##TODO: implement validation of config file
        try:
            with open("config.yaml", 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f'Error loading config file: {e}')
        self.config = config

    def start_logging(self):
        if self.config is None:
            raise ValueError("Load a config file first before initializing logging.")

        logging_config = self.config.get('logging')
        if logging_config:
            logging.config.dictConfig(logging_config)

        logging.getLogger('ipykernel').setLevel(logging.WARNING)
        logging.getLogger('positron_ipykernel').setLevel(logging.WARNING)

        logger.info('Appliction started and logging initialized!')

    def run(self):

        if self.config is None:
            raise ValueError("Load a config file first before running a workflow.")

        ##TODO: include province_shp into optimizer to optimize against correct points
        ##TODO: get monthly optimized values and not singe value for whole year
        loc_suffix = "_".join([str(i) for i in self.config["location"]]).replace(".", "_")
        out_radiation_table = Path(
            self.config['FeatureSolarRadiation']['out_table_dir'], 
            f'radiation_{loc_suffix}.csv'
        )
        out_radiation_table.parent.mkdir(parents=True, exist_ok=True)

        if not out_radiation_table.exists():
            logger.info("Starting to calculate radiation...")
            calculator = SolarCalculator(self.config)
            if calculator.error_tbl is None:
                calculator.optimize(
                    dem=self.config["dem"],
                    observation_dir=self.config["optimization"]["optim_dir"],
                    observation_locs=self.config["optimization"]["optim_coords"],
                    out=self.config['optimization'].get('out')
                )

            srad = calculator.calculate_radiation(dem = self.config['dem'])
            srad.to_csv(out_radiation_table)
        else:
            logger.info(f"Radiation data already exists. Loading from file {out_radiation_table}")
            srad = pd.read_csv(out_radiation_table)

        consumption_file = self.config['consumption'].get('consumption_tbl')
        if consumption_file is not None:
            logger.info(f'Consumption data available. Loading from {consumption_file}')
            consumption = pd.read_excel(consumption_file, usecols = ['date', 'consumption'])
            consumption["date"] = pd.to_datetime(consumption['date'], format = '%Y-%m-%d')
        else:
            consumption = None

        ## Generate Report
        report = Report(srad, panel_config = self.config['panels'], consumption = consumption)
        report.generate_report(self.config['template_dir'], self.config['report_out'])
