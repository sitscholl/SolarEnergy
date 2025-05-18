import arcpy
import pandas as pd

import datetime
import logging

logger = logging.getLogger(__name__)

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

def aggregate_srad(tbl, p_len = 7, ts_start = datetime.datetime(2024, 1, 1), ts_end = datetime.datetime(2024, 12, 31)):
    # TODO: make this more robust and dynamic for different frequencies
    tbl_diss = tbl.set_index('date').resample('D')[tbl.select_dtypes("number").columns].ffill() / p_len
    tbl_diss = tbl_diss.reindex(pd.date_range(ts_start, ts_end)).ffill()
    return(tbl_diss.resample('MS').sum())

def load_monthly_radiation(files):

    tbl_rad = pd.concat([pd.read_csv(i) for i in files], keys = [i.stem for i in files], names = ['st_id'])
    tbl_rad['date'] = pd.to_datetime(tbl_rad['date'], format = '%Y-%m-%d')

    tbl_rad = tbl_rad.reset_index(level = 0).set_index('date')
    tbl_rad['insol'] = tbl_rad['insol'].interpolate(method = 'time', limit = 3)

    tbl_rad = tbl_rad.groupby("st_id").resample('MS')['insol'].sum(min_count = 27).dropna().reset_index()
    tbl_rad = tbl_rad.groupby(['st_id', tbl_rad.date.dt.month])['insol'].mean().reset_index()

    tbl_rad['date'] = tbl_rad['date'].map(lambda x: pd.to_datetime(f"2024-{x}-01", format = "%Y-%m-%d"))
    tbl_rad.rename(columns = {'insol': "global_ave"}, inplace = True)
    tbl_rad = tbl_rad.set_index(['st_id', 'date']).squeeze()
    return tbl_rad