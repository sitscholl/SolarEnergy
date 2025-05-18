import pandas as pd
import numpy as np

from tempfile import TemporaryDirectory
from itertools import product
import datetime
import logging

from .solar_calculator import SolarCalculator
from ..utils import load_monthly_radiation

logger = logging.getLogger(__name__)

class ParameterOptimizer:
    def __init__(self, config: dict[str, str]):
        self.config = config

        if config["optimization"].get("optim_file") is None:
            self.error_tbl = None
        else:
            try:
                self.error_tbl = pd.read_csv(pd.read_csv(config["optimization"].get('optim_file')))
            except Exception as e:
                logger.warning(f"Loading error table failed with error: {e}")
                self.error_tbl = None

    def _error_function(self, params):
        transmittivity, diffuse_proportion = params

        optim_config = self.config.copy()
        optim_config['FeatureSolarRadiation']['transmittivity'].update(transmittivity)
        optim_config['FeatureSolarRadiation']['diffuse_proportion'].update(diffuse_proportion)
        optim_config['FeatureSolarRadiation']['unique_id_field'].update("st_id")
        optim_config['FeatureSolarRadiation']['interval_unit'].update("DAY")
        optim_config['FeatureSolarRadiation']['interval'].update(1)

        optim_config['panels'] = {"WeatherStation": {
            "offset": 2,
            "slope": 0,
            "aspect": 180
        }}

        if not (0.1 <= transmittivity <= 1.0 and 0.1 <= diffuse_proportion <= 1.0):
            return np.inf  # Penalize invalid values

        srad = SolarCalculator(optim_config).calculate_radiation(dem = dem)
        modeled_srad = srad.set_index('date').groupby('st_id').resample('MS')['global_ave'].sum()

        rmse = np.sqrt(np.sum((modeled_srad - observed_srad)**2)/len(modeled_srad - observed_srad))
        mae = np.mean(np.abs(modeled_srad - observed_srad))
        logger.debug(
            f"""Error with transmittivity={transmittivity:.2f}, 
            diffuse_proportion={diffuse_proportion:.2f}: 
            RMSE: {rmse:.2f}, MAE: {mae:.2f}
            """
        )

        return modeled_srad, rmse, mae

    def optimize(self, step: float = .1, out: str | Path | None = None):
        trans_vals = np.arange(.3, .9, step)
        diff_vals = np.arange(.1, .7, step)
        
        tbl_error = []
        for params in product(trans_vals, diff_vals):
            modeled_srad, rmse, mae = radiation_error(params, dem, province_shp, out_dir, observed_srad)
            _tbl = modeled_srad.to_frame()
            _tbl['transmittivity'] = params[0]
            _tbl['diffuse_proportion'] = params[1]
            _tbl['rmse'] = rmse
            _tbl['mae'] = mae
            tbl_error.append(_tbl)
        tbl_error = pd.concat(tbl_error)

        if out is not None:
            tbl_error.to_csv(out)
        
        self.error_tbl = tbl_error

    def get_optimized_values(self, metric = 'rmse'):

        if self.error_tbl is None:
            raise ValueError(f"error_tbl is None! Optimize parameters first or load a precreated error_tbl by specifying a valid path in the config file.")

        aggregated_error = self.error_tbl.groupby(['transmittivity', 'diffuse_proportion'])[metric].mean()
        t_opt, d_opt = aggregated_error.sort_values(metric).iloc[0]
        return t_opt, d_opt

