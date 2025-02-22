import pandas as pd
import numpy as np
from tempfile import TemporaryDirectory
from itertools import product
from src.solar import feature_insolation
from src.plot import optim_lines
import datetime
import logging

logger = logging.getLogger(__name__)

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

# Function to calculate error between modeled and observed radiation
def radiation_error(params, dem, province_shp, out_dir, observed_srad):
    transmittivity, diffuse_proportion = params
    if not (0.1 <= transmittivity <= 1.0 and 0.1 <= diffuse_proportion <= 1.0):
        return np.inf  # Penalize invalid values

    # modeled_srad = run_solar_radiation(transmittivity, diffuse_proportion, dem, province_shp, out_dir)
    srad = feature_insolation(
        dem=dem,
        features=province_shp,
        crs=None,
        out_dir=out_dir,
        feature_offset=2,
        feature_slope=0.0,
        feature_aspect=180,
        start="1/1/2024",
        end="12/31/2024",
        interval_unit="DAY",
        interval = 1,
        diffuse_proportion=diffuse_proportion,
        transmittivity=transmittivity,
        unique_id_field="st_id",
    )

    modeled_srad = srad.set_index('date').groupby('st_id').resample('MS')['global_ave'].sum()

    rmse = np.sqrt(np.sum((modeled_srad - observed_srad)**2)/len(modeled_srad - observed_srad))
    mae = np.mean(np.abs(modeled_srad - observed_srad))
    logger.debug(
        f"Error with transmittivity={transmittivity:.2f}, diffuse_proportion={diffuse_proportion:.2f}: RMSE: {rmse:.2f}, MAE: {mae:.2f}"
    )

    return modeled_srad, rmse, mae

# Main optimization process
def test_parameters(dem, province_shp, observed_srad, step = .1, out = None):
    with TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        
        # initial_guess = [0.7, 0.3]  # Initial transmittivity and diffuse proportion
        # bounds = [(0.1, 1.0), (0.1, 1.0)]  # Reasonable bounds
        
        # result = minimize(
        #     radiation_error, initial_guess, args=(dem, province_shp, out_dir, observed_srad),
        #     bounds=bounds, method='L-BFGS-B'
        # )

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
        
        return tbl_error

def get_optim_values(optim_tbl, metric = 'rmse'):
    error_tbl = optim_tbl[['transmittivity', 'diffuse_proportion', metric]].drop_duplicates().reset_index(drop = True)
    t_opt, d_opt = error_tbl.sort_values(metric)[['transmittivity', 'diffuse_proportion']].iloc[0]
    return t_opt, d_opt

if __name__ == '__main__':
    from pathlib import Path
    import logging
    import logging.config
    import arcpy
    arcpy.env.overwriteOutput = True

    logging.config.fileConfig(".config/logging.conf", disable_existing_loggers=False)

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    files = list(Path('data/optim').glob('*.csv'))
    observed_srad = load_monthly_radiation(files)

    dem = 'data/dem100m.tif'
    province_shp = 'data/optim/stations_province.shp'
    features = arcpy.management.Project(
        province_shp,
        out_dataset="data/_thrash/province_shp_re.shp",
        out_coor_system=arcpy.Describe(dem).spatialReference,
    )

    out_dir = Path(TemporaryDirectory().name)
    out_dir.mkdir(exist_ok = True, parents = True)

    # Run optimization
    optim_tbl = test_parameters(dem, str(features), observed_srad, step = .1, out = f"data/optim/optim_result_{datetime.datetime.now():%Y_%m_%d_%H%M}.csv")
    t_opt, d_opt = get_optim_values(optim_tbl, metric = 'rmse')

