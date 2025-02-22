import numpy as np
import pandas as pd
from src.solar import feature_insolation
from src.transformation import convert_solar_energy
from src.plot import encode_plot
from src.optim import get_optim_values, test_parameters, load_monthly_radiation
from tempfile import TemporaryDirectory
from pathlib import Path
import datetime
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
import logging
import logging.config

logging.config.fileConfig(".config/logging.conf", disable_existing_loggers=False)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

#################
# Parameters
#################
r = 100
p = (642202.50, 5163856.06)
crs = 25832
area_select = 20
height = 7
slope = 30
aspect = 180
efficiency = 0.15
system_loss = 0.8
price = 45 #ct/kWh
consumption_tbl = 'data/power_consumption.xlsx'
optim_file = 'data/optim/optim_result_2025_02_22_1443.csv'
#################

logger.info('Starting program at %s', datetime.datetime.now().strftime('%Y_%m_%d_%H%M'))
dem_p = f"data/dem{r}m.tif"

##Parameter optimization
if optim_file is None:
    logger.info('Optimizing parameters')
    import arcpy
    files = list(Path('data/optim').glob('*.csv'))
    observed_srad = load_monthly_radiation(files)

    province_shp = 'data/optim/stations_province.shp'
    features_optim = arcpy.management.Project(
        province_shp,
        out_dataset="data/_thrash/province_shp_re.shp",
        out_coor_system=arcpy.Describe(dem_p).spatialReference,
    )

    optim_tbl = test_parameters(
        dem_p,
        str(features_optim),
        observed_srad,
        step=0.1,
        out=f"data/optim/optim_result_{datetime.datetime.now():%Y_%m_%d_%H%M}.csv",
    )
    t_opt, d_opt = get_optim_values(optim_tbl, metric = 'rmse')
else:
    logger.info(f'Using optimized parameters from {optim_file}')
    t_opt, d_opt = get_optim_values(pd.read_csv(optim_file), metric="rmse")
# optim_lines(optim_tbl, observed_srad, '19300MS', t_opt, d_opt)


out_dir = Path(TemporaryDirectory().name)
out_dir.mkdir(exist_ok = True, parents = True)
insolation = feature_insolation(
    dem=dem_p,
    features=[p],
    crs=crs,
    out_dir=out_dir,
    feature_offset=height,
    feature_slope=slope,
    feature_aspect=aspect,
    transmittivity=t_opt,
    diffuse_proportion=d_opt,
    interval_unit="DAY",
    interval=1
)

insolation_mon = insolation.set_index('date').resample('MS')[['global_ave']].sum()

if consumption_tbl is not None:
    power_cns = pd.read_excel(consumption_tbl, usecols = ['date', 'consumption'])
    power_cns['date'] = pd.to_datetime(power_cns['date'], format = '%Y-%m-%d')
    power_cns.set_index('date', inplace = True)

    energy_tbl = insolation_mon.join(power_cns)

    #Plot results
    fig, ax = plt.subplots(figsize = (12, 6))
    ax.plot(energy_tbl["consumption"], label = "Consumption", color = 'black')
    dict_production = {}
    for area in [5, 10, 15, 20, 25, 30]:

        en_production = convert_solar_energy(
            energy_tbl["global_ave"], efficiency=efficiency, system_loss=system_loss, area=area
        )
        en_diff = (energy_tbl["consumption"] - en_production).sum().round(2)
        ax.plot(en_production, label = f"{area}m² ({en_diff}kWh)")
        dict_production[area] = en_production
        # en_production / energy_tbl["consumption"]

    ax.legend()
    ax.set_ylim(0, 750)

    en_tot_ann = dict_production[area_select].sum().round(1)
    monthly_energy = dict_production[area_select].round(2).to_dict()
    monthly_consumption = energy_tbl["consumption"].round(2).to_dict()
    kWp = area_select * efficiency

    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("report.html")
    content = template.render(
        rep_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        dem_resolution = r,
        point_coordinates = p,
        panel_area = area_select,
        panel_height = height,
        slope = slope,
        aspect = aspect,
        efficiency = efficiency,
        system_loss = system_loss,
        price_per_kwh = price,
        total_annual_energy = en_tot_ann,
        avoided_costs = ((en_tot_ann * price) / 100).round(1),
        payback_time = np.nan,
        kWp = kWp,
        monthly_energy_chart = encode_plot(fig),
        monthly_energy = monthly_energy,
        monthly_consumption = monthly_consumption,
        total_consumption = energy_tbl["consumption"].sum(),
        total_generation = en_tot_ann,
        gen_cons = (en_tot_ann - energy_tbl["consumption"].sum()).round(2),
        gen_cons_div = (en_tot_ann / energy_tbl["consumption"].sum()).round(2),
    )

    report_time = datetime.datetime.now().strftime('%Y_%m_%d_%H%M')
    out_report = Path("data", "results", f'{report_time}.html')
    with open(out_report, mode="w", encoding="utf-8") as report:
        report.write(content)
