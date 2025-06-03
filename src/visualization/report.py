import pandas as pd
import matplotlib.pyplot as plt
# import pandera.pandas as pa
from jinja2 import Environment, FileSystemLoader

import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from .plot import encode_plot

logger = logging.getLogger(__name__)

## Dataframe validation
# class ConsumptionSchema(pa.DataFrameModel):
#     date: datetime = pa.Field()
#     consumption: float = pa.Field(ge=0)

# class IncomingRadiationSchema(pa.DataFrameModel):
#     date: datetime = pa.Field()
#     panel: str = pa.Field()
#     srad: float = pa.Field(ge=0)


class Report:

    def __init__(
        self,
        srad: pd.Series,
        panel_config: dict,
        consumption: Optional[pd.Series] = None
    ):
        # IncomingRadiationSchema.validate(srad)
        self.srad = (
            srad
            .set_index('date')
            .groupby('panel')
            .resample('MS')['srad']
            .sum()
            .reset_index(level = 0)
        )
        if consumption is not None:
            # ConsumptionSchema.validate(consumption)
            consumption = consumption.set_index('date')

        self.consumption = consumption
        
        production_tbls = []
        for panel_name, panel_data in self.srad.groupby('panel'):
            panel_data['production'] = self.solar_energy_to_electric_energy(
                panel_data['srad'],
                efficiency=panel_config[panel_name]['efficiency'],
                system_loss=panel_config[panel_name]['system_loss']
            )
            production_tbls.append(panel_data[['panel', 'production']])
        self.production = pd.concat(production_tbls)

        self.panel_config = panel_config

    def solar_energy_to_electric_energy(
        self, srad, efficiency=0.15, system_loss=0.8
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

        return srad * efficiency * system_loss

    @property
    def total_radiation(self):
        return self.srad['srad'].sum()

    @property
    def total_consumption(self):
        return self.consumption['consumption'].sum()

    @property
    def total_production(self):
        return self.production['production'].sum()

    @property
    def panel_production(self):
        return (
            self.production
            .pivot_table(
                index=self.production.index.month,
                columns='panel',
                values='production',
                fill_value=0
            )
            .round()
            )

    @property
    def energy_efficiency(self, freq = 'M'):
        return self.total_production / self.total_radiation

    @property
    def energy_balance(self, freq = 'M'):
        return self.total_production - self.total_consumption

    def plot(self, encode: bool = False):

        fig, ax = plt.subplots(figsize = (12, 7))

        # Define distinct colors for panels
        panel_colors = plt.cm.tab10
        
        # Prepare data for stacked area plot
        panel_names = self.production['panel'].unique()
        
        # Create a pivot table to get production values for each panel by date
        production_pivot = self.production.pivot_table(
            index=self.production.index, 
            columns='panel', 
            values='production', 
            fill_value=0
        )
        
        # Create stacked area plot
        ax.stackplot(
            production_pivot.index,
            *[production_pivot[panel] for panel in panel_names],
            labels=panel_names,
            colors=[panel_colors(i) for i in range(len(panel_names))],
            alpha=0.8
        )

        # Plot consumption line with a distinct color (red)
        if self.consumption is not None:
            ax.plot(
                self.consumption.index,
                self.consumption['consumption'],
                color='red',
                marker='s',
                linewidth=3,
                linestyle='--',
                label='Consumption'
            )

        ax.legend()
        ax.set_ylim(0, 750)
        ax.set_xlabel('Date')
        ax.set_ylabel('Energy (kWh)')
        ax.grid(True, alpha=0.3)

        if encode:
            return encode_plot(fig)
        return fig, ax

    def generate_report(self, template_dir: str, report_dir: str):
        
        report_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        data = {
            'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

            'panels': self.panel_config,

            'monthly_plot': self.plot(encode = True),
            'panel_energy_totals': self.panel_production,
            "energy_metrics": {
                'Total Energy Produced': (self.total_production, 'kWh'),
                'Total Energy Consumed': (self.total_consumption, 'kWh'),
                'Total Radiation': (self.total_radiation, 'kWh'),
                'Energy Balance': (self.energy_balance, 'kWh'),
            }
        }

        # Configure Jinja2 environment
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('main_template.html')

        # Render the template with the data
        output = template.render(data)

        # Save the output to an HTML file
        out_report = Path(report_dir, f'report_{report_time}.html')
        Path(out_report.parent).mkdir(exist_ok = True, parents = True)
        with open(out_report, mode="w", encoding='utf-8') as f:
            f.write(output)

        logger.info('Report sucessfully generated!')
