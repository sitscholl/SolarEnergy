import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

from tempfile import TemporaryDirectory
from pathlib import Path
import datetime
import logging
import logging.config
import yaml

import src
from src.optim import OptimizationResults

## Open Config 
with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

## Setup logging
logging.config.dictConfig(config['logging'])
logger = logging.getLogger(__name__)

logger.info('Starting program at %s', datetime.datetime.now().strftime('%Y%m%d %H:%M'))

dem_resolution = config.get("dem_resolution", 100)
dem_p = f"data/dem{dem_resolution}m.tif"

##Parameter optimization
if config.get('optim_file') is None:
    logger.info('Optimizing parameters')

    import arcpy
    files = list(Path('data/optim').glob('*.csv'))
    observed_srad = src.load_monthly_radiation(files)

    province_shp = 'data/optim/stations_province.shp'
    features_optim = arcpy.management.Project(
        province_shp,
        out_dataset="data/_thrash/province_shp_re.shp",
        out_coor_system=arcpy.Describe(dem_p).spatialReference,
    )

    optim_tbl = src.test_parameters(
        dem_p,
        str(features_optim),
        observed_srad,
        step=0.1,
        out=f"data/optim/optim_result_{datetime.datetime.now():%Y_%m_%d_%H%M}.csv",
    )
    optim_results = OptimizationResults(optim_tbl)
else:
    logger.info(f'Using optimized parameters from {config.get("optim_file")}')
    optim_results = OptimizationResults(config.get('optim_file'))
# optim_lines(optim_tbl, observed_srad, '19300MS', t_opt, d_opt)

out_dir = Path(TemporaryDirectory().name)
out_dir.mkdir(exist_ok = True, parents = True)
insolation = src.feature_insolation(
    dem=dem_p,
    features=[config['location']],
    crs=config['crs'],
    out_dir=out_dir,
    feature_offset=config['panels']['south']['height'],
    feature_slope=config['panels']['south']['slope'],
    feature_aspect=config['panels']['south']['aspect'],
    optimization_results = optim_results,
    interval_unit="DAY",
    interval=1
)

insolation_mon = insolation.set_index('date').resample('MS')[['global_ave']].sum()

power_cns = pd.read_excel(config.get('consumption_tbl'), usecols = ['date', 'consumption'])
power_cns['date'] = pd.to_datetime(power_cns['date'], format = '%Y-%m-%d')
power_cns.set_index('date', inplace = True)

energy_tbl = insolation_mon.join(power_cns)

# Plot results
fig, ax = plt.subplots(figsize = (12, 6))
ax.plot(energy_tbl["consumption"], label = "Consumption", color = 'black')
dict_production = {}
dict_diff = {}
for area in [5, 10, 15, 20, 25, 30]:

    # en_production = src.convert_solar_energy(
    #     energy_tbl["global_ave"], efficiency=efficiency, system_loss=system_loss, area=area
    # )
    qntl = src.sample_solar_energy(
        srad = energy_tbl["global_ave"],
        eff_low=0.15,
        eff_high=0.20,
        loss_low=0.75,
        loss_high=0.9,
        area=area,
        n=10000,
    )

    en_diff = (energy_tbl["consumption"] - qntl[1]).sum().round(2)
    ln = ax.plot(energy_tbl["consumption"].index, qntl[1], label = f"{area}m² ({en_diff}kWh)")
    #ax.fill_between(energy_tbl["consumption"].index, qntl[0], qntl[2], alpha=0.2, color="grey")
    ax.plot(energy_tbl["consumption"].index, qntl[0], ls = '--', color = ln[-1].get_color(), alpha = .5, lw = .7)
    ax.plot(energy_tbl["consumption"].index, qntl[2], ls = '--', color = ln[-1].get_color(), alpha = .5, lw = .7)

    dict_production[area] = qntl[1]
    dict_diff[area] = en_diff

ax.legend()
ax.set_ylim(0, 750)

area_optim = config.get('area_optim')
if area_optim is None:
    area_optim = [i for i in dict_diff.keys() if np.abs(dict_diff[i]) == min(np.abs(list(dict_diff.values())))][0]

en_tot_ann = dict_production[area_optim].sum().round(1)
monthly_energy = dict(zip(energy_tbl["consumption"].index, dict_production[area_optim].round(2)))
monthly_consumption = energy_tbl["consumption"].round(2).to_dict()

environment = Environment(loader=FileSystemLoader("templates/"))
template = environment.get_template("report.html")
content = template.render(
    rep_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    dem_resolution = dem_resolution,
    point_coordinates = config['location'],
    panel_height = config['panels']['south']['height'],
    slope = config['panels']['south']['slope'],
    aspect = config['panels']['south']['aspect'],
    efficiency = config['panels']['south']['efficiency'],
    system_loss = config['panels']['south']['system_loss'],
    price_per_kwh = config.get('price', 45),

    monthly_energy_chart = src.encode_plot(fig),

    area_optim = area_optim,
    kWp = f"{area_optim * config['panels']['south']['efficiency'][0]:.2f} - {area_optim * config['panels']['south']['efficiency'][1]:.2f}",
    total_annual_energy = en_tot_ann,
    total_annual_consumption = energy_tbl["consumption"].sum(),
    avoided_costs = ((en_tot_ann * config.get('price', 45)) / 100).round(1),

    monthly_energy = monthly_energy,
    monthly_consumption = monthly_consumption,
    total_consumption = energy_tbl["consumption"].sum(),
    total_generation = en_tot_ann,
    gen_cons = (en_tot_ann - energy_tbl["consumption"].sum()).round(2),
    gen_cons_div = ((en_tot_ann / energy_tbl["consumption"].sum())*100).round(2),
)

report_time = datetime.datetime.now().strftime('%Y_%m_%d_%H%M%S')
out_report = Path("data", "results", f'{report_time}.html')
with open(out_report, mode="w", encoding="utf-8") as report:
    report.write(content)
