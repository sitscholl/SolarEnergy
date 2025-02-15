import numpy as np
import pandas as pd
from src.solar import feature_insolation
from src.transformation import convert_solar_energy
from tempfile import TemporaryDirectory
from pathlib import Path
import datetime
import matplotlib.pyplot as plt
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
slope = 15
aspect = 270
efficiency = 0.15
system_loss = 0.8
consumption_tbl = 'data/power_consumption.xlsx'
#################

dem_p = f"data/dem{r}m.tif"

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
    interval_unit="WEEK",
    interval=1
)
insolation = insolation[["str_time", "global_ave", "direct_ave", "diff_ave", "dir_dur"]].rename(columns={"str_time": "date"})
insolation['date'] = pd.to_datetime(insolation['date'], format = '%Y-%m-%d')

## Disaggregate to daily values
# TODO: make this more robust and dynamic for different frequencies
p_len = 7
ts_start, ts_end = datetime.datetime(2024, 1, 1), datetime.datetime(2024, 12, 31)
insolation_diss = insolation.set_index('date').resample('D').ffill() / p_len
insolation_diss = insolation_diss.reindex(pd.date_range(ts_start, ts_end)).ffill()

if consumption_tbl is not None:
    power_cns = pd.read_excel(consumption_tbl, usecols = ['date', 'consumption'])
    power_cns['date'] = pd.to_datetime(power_cns['date'], format = '%Y-%m-%d')
    power_cns.set_index('date', inplace = True)

    ##Assumes a frequency of monthly data in power_cns
    insolation_agg = insolation_diss.resample('MS').sum()

    energy_tbl = insolation_agg.join(power_cns)

    #Plot results
    fig, ax = plt.subplots()
    ax.plot(energy_tbl["consumption"], label = "Consumption", color = 'black')
    
    for area in [5, 10, 15, 20]:

        en_production = convert_solar_energy(
            energy_tbl["global_ave"], efficiency=efficiency, system_loss=system_loss, area=area
        )
        en_diff = (energy_tbl["consumption"] - en_production).sum().round(2)
        ax.plot(en_production, label = f"{area}m² ({en_diff}kWh)")

    ax.legend()
    ax.set_ylim(0, 750)
    plt.savefig(f'data/results/comparison_lines_r{r}_h{height}_s{slope}_a{aspect}_e{efficiency}_sl{system_loss}.png', dpi = 300)


