import pandas as pd
import numpy as np
from pandas import Series

from itertools import product
from pathlib import Path
from typing import Optional, Union
import logging
import tempfile

from ..utils import coords_to_shp, load_monthly_radiation

logger = logging.getLogger(__name__)

# # Set environment settings
# arcpy.env.workspace = "C:/sapyexamples/solardata.gdb"
# arcpy.env.scratchWorkspace = "C:/sapyexamples/outfile.gdb"

# # Check out the ArcGIS Spatial Analyst extension license
# arcpy.CheckOutExtension("Spatial")

class SolarCalculator:

    def __init__(self, config):
        self.config = config['FeatureSolarRadiation']
        self.panel_config = config["panels"]
        self.location = config['location']
        self.output_directory = config.get("output_directory", tempfile.TemporaryDirectory().name)
        self.crs = config['crs']
        Path(self.output_directory).mkdir(exist_ok = True, parents = True)

        optim_file = config["optimization"]["optim_file"]       
        if optim_file is not None:
            try:
                self.error_tbl = pd.read_csv(optim_file)
                logger.info(f'Loaded optimized parameters from : {optim_file}')
            except Exception as e:
                logger.warning(f"Loading error table failed with error: {e}")
                self.error_tbl = None
        else:
            self.error_tbl = None

    def calculate_radiation(self, dem: str, features: Optional[list[tuple]] = None):
        """
        Compute solar radiation for each feature in a feature class.

        Parameters
        ----------
        dem : str, path to raster
            The input elevation surface.
        features : list of tuples
            The input feature class. A list of tuples with x,y coordinates

        Returns
        -------
        pandas.DataFrame
            A table with the solar radiation values for each feature.
        """

        try:
            import arcpy
            #from arcpy.sa import *
        except Exception as e:
            raise ImportError("Error importing arcpy library. Make sure it is available in the current environment.")

        if features is None:
            features = self.location
        if isinstance(features, list):
            features = coords_to_shp([features], crs = self.crs, out = Path(self.output_directory, "features.shp"))

        spatial_ref = arcpy.Describe(dem).spatialReference

        if spatial_ref.name != arcpy.Describe(str(features)).spatialReference.name:
            re_name = Path(self.output_directory, "features_reprojected.shp")
            features = arcpy.management.Project(str(features), out_dataset=str(re_name), out_coor_system=spatial_ref)
            logger.debug(f"Feature class reprojected at {features} to crs {spatial_ref.name}")

        if self.error_tbl is not None:
            transmittivity, diffuse_proportion = self.get_optimized_values()
            logger.info(f'Using optimized transmittivity and diffuse_proportion values of {transmittivity:.2f} and {diffuse_proportion:.2f}')
        else:
            diffuse_proportion=self.config.get("diffuse_proportion", 0.3),
            transmittivity=self.config.get("transmittivity", 0.5),
            logger.warning(f'Using default transmittivity and diffuse_proportion values of {transmittivity:.2f} and {diffuse_proportion:.2f}')

        # Run FeatureSolarRadiation
        tbl = []
        unique_id_field = self.config.get('unique_id_field', 'ID')
        for panel_name, panel_attrs in self.panel_config.items():
            srad = arcpy.sa.FeatureSolarRadiation(
                in_surface_raster=dem,
                in_features=str(features),
                out_table=str( Path(self.output_directory, f"solar_radiation_{panel_name}.dbf") ),
                unique_id_field=unique_id_field,
                time_zone=self.config.get('time_zone', "UTC"),
                start_date_time=self.config.get('start_date', "1/1/2024"),
                end_date_time=self.config.get('end_date', "12/31/2024"),
                use_time_interval="NO_INTERVAL" if self.config.get("interval_unit") is None else "INTERVAL",
                interval_unit=self.config.get("interval_unit"),
                interval=self.config.get("interval", 1),

                feature_area=panel_attrs.get('area', 0),
                feature_offset=panel_attrs.get("offset", 0),
                feature_slope=panel_attrs.get("slope", 0),
                feature_aspect=panel_attrs.get("aspect", 0),

                diffuse_model_type=self.config.get("diffuse_model_type", "UNIFORM_SKY"),
                diffuse_proportion=diffuse_proportion,
                transmittivity=transmittivity,
                analysis_target_device=self.config.get("analysis_target_device", "GPU_THEN_CPU"),
            )
            logger.debug(
                f"""FeatureSolarRadiation saved at {srad} with 
                    diffuse_proportion={diffuse_proportion:.2f} and 
                    transmittivity={transmittivity:.2f}
                    """
                    )

            out_xlsx = Path(Path().cwd(), self.output_directory, f"solar_radiation_{panel_name}.xlsx")
            _ = arcpy.conversion.TableToExcel(srad, str(out_xlsx))

            # Read out the table
            _tbl = pd.read_excel(out_xlsx)
            if unique_id_field == 'ID':
                unique_id_field = 'Id'
            _tbl = _tbl[[unique_id_field, "str_time", "global_ave", "direct_ave", "diff_ave", "dir_dur"]].copy()
            _tbl.rename(columns={"str_time": "date", 'global_ave': 'srad'}, inplace = True)
            _tbl['date'] = pd.to_datetime(_tbl['date'], format = '%Y-%m-%d')
            _tbl["panel"] = panel_name

            tbl.append(_tbl)
        return(pd.concat(tbl))

    def _error_function(self, params: tuple[float,float], dem: str, observed_srad: Series, observation_coords: Union[str, Path]):
        transmittivity, diffuse_proportion = params

        if not (0.1 <= transmittivity <= 1.0 and 0.1 <= diffuse_proportion <= 1.0):
            return np.inf  # Penalize invalid values

        optim_config['Location'] = observation_coords

        optim_config = self.config.copy()
        optim_config["optimization"]["optim_file"] = None
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

    def optimize(
        self,
        dem: str,
        observation_dir: Union[str, Path],
        observation_coords: Union[str, Path],
        step: float = 0.1,
        out: Optional[str] = None,
    ):
        trans_vals = np.arange(0.3, 0.9, step)
        diff_vals = np.arange(.1, .7, step)

        observations = load_monthly_radiation(list(Path(observation_dir).glob('*.csv')))

        tbl_error = []
        for params in product(trans_vals, diff_vals):
            modeled_srad, rmse, mae = self._error_function(params, dem, observations)
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
        t_opt, d_opt = aggregated_error.sort_values().index[0]
        return t_opt, d_opt
