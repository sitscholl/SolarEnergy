import numpy as np
import pandas as pd
import src
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
height = 7
slope = 30
aspect = 180
efficiency = (0.15, 0.2)
system_loss = (0.75, 0.9)
price = 45 #ct/kWh
area_optim = None
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
    t_opt, d_opt = src.get_optim_values(optim_tbl, metric = 'rmse')
else:
    logger.info(f'Using optimized parameters from {optim_file}')
    t_opt, d_opt = src.get_optim_values(pd.read_csv(optim_file), metric="rmse")
# optim_lines(optim_tbl, observed_srad, '19300MS', t_opt, d_opt)


out_dir = Path(TemporaryDirectory().name)
out_dir.mkdir(exist_ok = True, parents = True)
insolation = src.feature_insolation(
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

power_cns = pd.read_excel(consumption_tbl, usecols = ['date', 'consumption'])
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
    ax.plot(energy_tbl["consumption"].index, qntl[1], label = f"{area}m² ({en_diff}kWh)")
    ax.fill_between(energy_tbl["consumption"].index, qntl[0], qntl[2], alpha=0.2, color="grey")

    dict_production[area] = qntl[1]
    dict_diff[area] = en_diff

ax.legend()
ax.set_ylim(0, 750)

if area_optim is None:
    area_optim = [i for i in dict_diff.keys() if np.abs(dict_diff[i]) == min(np.abs(list(dict_diff.values())))][0]

en_tot_ann = dict_production[area_optim].sum().round(1)
monthly_energy = dict(zip(energy_tbl["consumption"].index, dict_production[area_optim].round(2)))
monthly_consumption = energy_tbl["consumption"].round(2).to_dict()

environment = Environment(loader=FileSystemLoader("templates/"))
template = environment.get_template("report.html")
content = template.render(
    rep_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    dem_resolution = r,
    point_coordinates = p,
    panel_height = height,
    slope = slope,
    aspect = aspect,
    efficiency = efficiency,
    system_loss = system_loss,
    price_per_kwh = price,

    monthly_energy_chart = src.encode_plot(fig),

    area_optim = area_optim,
    kWp = area_optim * np.mean(efficiency),
    total_annual_energy = en_tot_ann,
    total_annual_consumption = energy_tbl["consumption"].sum(),
    avoided_costs = ((en_tot_ann * price) / 100).round(1),

    monthly_energy = monthly_energy,
    monthly_consumption = monthly_consumption,
    total_consumption = energy_tbl["consumption"].sum(),
    total_generation = en_tot_ann,
    gen_cons = (en_tot_ann - energy_tbl["consumption"].sum()).round(2),
    gen_cons_div = (en_tot_ann / energy_tbl["consumption"].sum()).round(2)*100,
)

report_time = datetime.datetime.now().strftime('%Y_%m_%d_%H%M')
out_report = Path("data", "results", f'{report_time}.html')
with open(out_report, mode="w", encoding="utf-8") as report:
    report.write(content)
