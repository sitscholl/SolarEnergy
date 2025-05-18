import pandas as pd

import logging

logger = logging.getLogger(__name__)

class EnergyTable:

    def __init__(self, production: pd.DataFrame, consumption: pd.DataFrame | None = None):
        self.validate_df(production)
        self.production = production

        if consumption is not None:
            self.validate_df(consumption)

            consumption_freq = consumption['date'].dt.infer_freq()
            production_freq = production['date'].dt.infer_freq()

            if consumption_freq != production_freq:
                logger.warning(f"Datetime frequency in production table does not match frequency in consumption table. Got {production_freq} vs {consumption_freq}. Resampling consumption data")
                consumption = consumption.set_index('date').resample(production_freq).mean()
                consumption.reset_index(inplace = True)

        self.consumption = consumption

    def validate_df(self):
        "Make sure input data has correct columns and dtypes"
        #Maybe also transform date to datetime dtype if necessary
        pass

