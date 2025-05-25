import pandas as pd
import matplotlib.pyplot as plt
import pandera.pandas as pa
from jinja2 import Environment, FileSystemLoader

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

## Dataframe validation
class ConsumptionSchema(pa.DataFrameModel):
    date: datetime = pa.Field()
    consumption: float = pa.Field(ge=0)

class IncomingRadiationSchema(pa.DataFrameModel):
    date: datetime = pa.Field()
    panel: str = pa.Field()
    srad: float = pa.Field(ge=0)


class Report:

    def __init__(
        self,
        srad: pd.Series,
        panel_config: dict,
        consumption: pd.Series | None = None,
        efficiency=0.15,
        system_loss=0.8,
        area=None,
        kWp=None,
    ):
        IncomingRadiationSchema.validate(srad)
        self.srad = srad.set_index('date')

        if consumption is not None:
            ConsumptionSchema.validate(consumption)
            consumption = consumption.set_index('date')

            consumption_freq = consumption.index.dt.infer_freq()
            production_freq = srad.index.dt.infer_freq()

            if consumption_freq != production_freq:
                logger.warning(f"Datetime frequency in production table does not match frequency in consumption table. Got {production_freq} vs {consumption_freq}. Resampling consumption data")
                consumption = consumption.resample(production_freq).mean()

        self.consumption = consumption
        self.production = self.srad.apply(
            lambda x: self.solar_energy_to_electric_energy(
                x['srad'], efficiency=efficiency, system_loss=system_loss, area=panel_config[x['panel']['area']], kWp=None
            ), axis = 1
        )

        self.panel_config = panel_config

    def solar_energy_to_electric_energy(
        srad, efficiency=0.15, system_loss=0.8, area=None, kWp=None
    ):
        """
        Convert solar radiation input into electricity output.

        Parameters
        ----------
        srad : float
            Total solar radiation (kWh/m²) for the location and time period.
        efficiency : float, optional
            Efficiency of the solar panels. Defaults to 0.15.
            Commercial solar panels typically convert 15–22% of sunlight into electricity
        system_loss : float, optional
            Factor in losses from inverters (3–10%), temperature (5–15%), dust/shading (2–10%), and wiring (1–3%).
            Defaults to 0.8 (20% total losses).
        area : float, optional
            Area covered by solar panels (m²). Must be provided if `kWp` is not.
        kWp : float, optional
            System size (kWp). Must be provided if `area` is not.

        Returns
        -------
        out : float
            The total electricity output (kWh) of the system.

        Notes
        -----
        To calculate the area needed for a system, use the formula:

        Area (m²) = System Size (kWp) / (Irradiance (1 kW/m²) × Efficiency)

        This requires a known efficiency and a known system size. This formula
        explains much area is needed under perfect lab conditions to get that the given kWp.
        The 1 comes from the standard 1kW/m² used in lab conditions to assess kWp

        To calculate the total electricity output the following formula is used:

        Total Electricity Output (kWh) = Solar Radiation (kWh/m²) × Area (m²) × Efficiency × System Loss Factor
        """

        if area is None and kWp is None:
            raise ValueError("Either area or kWp must be provided")
        elif area is not None and kWp is not None:
            raise ValueError("Only one of area or kWp must be provided")

        if kWp is not None:
            area = kWp / (1 * efficiency)

        return srad * area * efficiency * system_loss

    @property
    def total_radiation(self):
        return self.srad.sum()

    @property
    def total_consumption(self):
        return self.consumption.sum()

    @property
    def total_production(self):
        return self.production.sum()

    @property
    def panel_production(self):
        return self.production.groupby('panel').sum().to_dict()

    def energy_efficiency(self, freq = 'M'):
        return self.total_production / self.total_radiation

    def energy_balance(self, freq = 'M'):
        return self.total_production - self.total_consumption

    def plot(self):

        fig, ax = plt.subplots(figsize = (12, 6))

        if self.consumption is not None:
            ax.plot(self.consumption, label = "Consumption", color = 'black')
        ax.plot(self.production, label = "Production", color = 'red')

        ax.legend()
        ax.set_ylim(0, 750)

    def generate_report(self, template):
        
        data = {
            'report_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'location': 'Example Location',

            'panels': self.panel_config,

            'monthly_plot_url': 'images/monthly_energy_plot.png',  # Path to your plot image
            'panel_energy_totals': self.panel_production,
            "energy_metrics": {
                'Total Energy Produced': (self.total_production, 'kWh'),
                'Total Energy Consumed': (self.total_consumption, 'kWh'),
                'Total Radiation': (self.total_radiation, 'kWh'),
                'Energy Balance': (self.energy_balance, 'kWh'),
                'Energy Efficiency': (self.energy_efficiency, ''),
                'Peak Power Output': (2.5, 'kW'),
            }
        }

        # Configure Jinja2 environment
        env = Environment(loader=FileSystemLoader('templates/'))  # Assumes templates are in the same directory
        template = env.get_template('main_template.html')

        # Render the template with the data
        output = template.render(data)

        # Save the output to an HTML file
        with open(f'data/reports/report_{datetime.datetime.now():%Y_%m_%d_%H%M%S}.html', 'w', encoding='utf-8') as f:
            f.write(output)
