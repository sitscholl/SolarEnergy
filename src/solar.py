import arcpy
from arcpy.sa import *
from tempfile import TemporaryFile
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# # Set environment settings
# arcpy.env.workspace = "C:/sapyexamples/solardata.gdb"
# arcpy.env.scratchWorkspace = "C:/sapyexamples/outfile.gdb"

# # Check out the ArcGIS Spatial Analyst extension license
# arcpy.CheckOutExtension("Spatial")


def feature_insolation(
    dem,
    features,
    crs,
    out_dir,
    feature_offset=0.0,
    feature_slope=0.0,
    feature_aspect=180,
    start="1/1/2024",
    end="12/31/2024",
    interval_unit="WEEK",
    diffuse_proportion=0.3,
    transmittivity=0.7,
    **kwargs
):
    """
    Compute solar radiation for each feature in a feature class.

    Parameters
    ----------
    dem : str, path to raster
        The input elevation surface.
    features : list of tuples
        The input feature class. A list of tuples with x,y coordinates
    feature_offset : float, optional
        The height above the DEM surface for which to calculate the solar
        radiation. The default is 0.0.
    feature_slope : float, optional
        The slope of the feature. The default is 0.0.
    feature_aspect : float, optional
        The aspect (compass direction) of the feature. The default is 180.
    out_table : str, path to file, optional
        The output table. The default is a temporary file.
    start : str, optional
        The start date of the time period for which to calculate the solar
        radiation. The default is "1/1/2024".
    end : str, optional
        The end date of the time period for which to calculate the solar
        radiation. The default is "12/31/2024".
    interval_unit : str, optional
        The time interval at which to calculate the solar radiation. The options
        are 'MINUTE', 'HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'. The default is
        'WEEK'.
    diffuse_proportion : float, optional
        The proportion of diffuse radiation. The default is 0.3.
    transmittivity : float, optional
        The transmittivity of the atmosphere. The default is 0.7.
    **kwargs
        Additional keyword arguments to be passed to the ArcGIS
        ``FeatureSolarRadiation`` tool.

    Returns
    -------
    pandas.DataFrame
        A table with the solar radiation values for each feature.
    """

    in_features = coords_to_shp(features, crs = crs, out = Path(out_dir, "features.shp"))

    spatial_ref = arcpy.Describe(dem).spatialReference
    re_name = str(in_features).replace('.shp', '_reprojected.shp')
    in_features_re = arcpy.management.Project(str(in_features), out_dataset=re_name, out_coor_system=spatial_ref)
    logger.debug(f"Feature class reprojected at {in_features_re} to crs {spatial_ref.name}")

    # Run FeatureSolarRadiation
    srad = arcpy.sa.FeatureSolarRadiation(
        in_surface_raster=dem,
        in_features=str(in_features_re),
        out_table=str( Path(out_dir, "solar_radiation.dbf") ),
        unique_id_field="ID",
        time_zone="UTC",
        start_date_time=start,
        end_date_time=end,
        use_time_interval="NO_INTERVAL" if interval_unit is None else "INTERVAL",
        interval_unit=interval_unit,
        feature_offset=feature_offset,
        feature_slope=feature_slope,
        feature_aspect=feature_aspect,
        diffuse_model_type="UNIFORM_SKY",
        diffuse_proportion=diffuse_proportion,
        transmittivity=transmittivity,
        analysis_target_device="GPU_THEN_CPU",
        **kwargs

        # interval={'MINUTE': 60, 'HOUR': 4, 'DAY': 14, 'WEEK': 2}[interval_unit],
        # adjust_DST="ADJUSTED_FOR_DST",
        # feature_area="Area_FLD",
        # neighborhood_distance="",
        # use_adaptive_neighborhood="",
        # out_join_layer=None
        #sunmap_grid_level=5
    )
    logger.debug(f"FeatureSolarRadiation completed at {srad}")

    out_xlsx = Path(out_dir, "solar_radiation.xlsx")
    _ = arcpy.conversion.TableToExcel(srad, str(out_xlsx))

    # Read out the table
    return(pd.read_excel(out_xlsx))

def coords_to_shp(coords, crs, out):

    out_dir, layer_name = str(out.parent), out.name
    # Create a feature class with a spatial reference
    result = arcpy.management.CreateFeatureclass(
        out_dir, layer_name, "POINT", spatial_reference=arcpy.SpatialReference(crs)
    )
    logger.debug(f'Created feature class at {out}')

    feature_class = result[0]
    # Write feature to new feature class
    with arcpy.da.InsertCursor(feature_class, ["SHAPE@"]) as cursor:
        for c in coords:
            cursor.insertRow([c])
            logger.debug(f"\t Feature {c} added")

    return(out)
