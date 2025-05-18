import arcpy
from arcpy.sa import *
import pandas as pd

from pathlib import Path
import logging
import tempfile

from .solar_optimization import ParameterOptimizer
from ..utils import coords_to_shp

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
        Path(self.output_directory).mkdir(exist_ok = True, parents = True)

    def calculate_radiation(self, dem: str, features: list[tuple] | None = None, optimizer: ParameterOptimizer | None = None):
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

        if features is None:
            features = self.location
        if isinstance(features, list):
            features = coords_to_shp(features, crs = self.config["crs"], out = Path(self.output_directory, "features.shp"))

        spatial_ref = arcpy.Describe(dem).spatialReference

        if spatial_ref.name != arcpy.Describe(str(features)).spatialReference.name:
            re_name = Path(self.output_directory, "features_reprojected.shp")
            features = arcpy.management.Project(str(features), out_dataset=str(re_name), out_coor_system=spatial_ref)
            logger.debug(f"Feature class reprojected at {features} to crs {spatial_ref.name}")

        if optimizer is not None:
            transmittivity, diffuse_proportion = optimizer.get_optimized_values()
        else:
            diffuse_proportion=self.config.get("diffuse_proportion", 0.3),
            transmittivity=self.config.get("transmittivity", 0.5),

        # Run FeatureSolarRadiation
        tbl = []
        for panel_name, panel_attrs in self.panel_config.items():
            srad = arcpy.sa.FeatureSolarRadiation(
                in_surface_raster=dem,
                in_features=str(features),
                out_table=str( Path(self.output_directory, f"solar_radiation_{panel_name}.dbf") ),
                unique_id_field=self.config.get('unique_id_field', 'ID'),
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
                    diffuse_proportion={diffuse_proportion} and 
                    transmittivity={transmittivity}
                    """
                    )

            out_xlsx = Path(self.output_directory, f"solar_radiation_{panel_name}.xlsx")
            _ = arcpy.conversion.TableToExcel(srad, str(out_xlsx))

            # Read out the table
            _tbl = pd.read_excel(out_xlsx)
            if unique_id_field == 'ID':
                unique_id_field = 'Id'
            _tbl = _tbl[[unique_id_field, "str_time", "global_ave", "direct_ave", "diff_ave", "dir_dur"]].copy()
            _tbl.rename(columns={"str_time": "date"}, inplace = True)
            _tbl['date'] = pd.to_datetime(_tbl['date'], format = '%Y-%m-%d')
            _tbl["panel"] = panel_name

            tbl.append(_tbl)
        return(pd.concat(tbl))
