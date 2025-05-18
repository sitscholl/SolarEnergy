import pandas as pd

import logging

logger = logging.getLogger(__name__)

class EnergyTable:

    def __init__(self, srad: pd.Series, consumption: pd.Series | None = None):
        self._validate_df(srad)
        self.srad = srad

        if consumption is not None:
            self._validate_df(consumption)

            consumption_freq = consumption['date'].dt.infer_freq()
            production_freq = srad['date'].dt.infer_freq()

            if consumption_freq != production_freq:
                logger.warning(f"Datetime frequency in production table does not match frequency in consumption table. Got {production_freq} vs {consumption_freq}. Resampling consumption data")
                consumption = consumption.set_index('date').resample(production_freq).mean()
                consumption.reset_index(inplace = True)

        self.consumption = consumption

    def _validate_df(self):
        "Make sure input data has correct columns and dtypes"
        # Maybe also transform date to datetime dtype if necessary
        pass

    def convert_solar_energy(
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

    def calculate_energy_efficiency(self):
        pass

    def calculate_energy_surplus(self):
        pass

    def calculate_energy_savings(self):
        pass

    def plot(self):

        fig, ax = plt.subplots(figsize = (12, 6))

        if self.consumption is not None:
            ax.plot(self.consumption, label = "Consumption", color = 'black')
        ax.plot(self.production, label = "Production", color = 'red')

        ax.legend()
        ax.set_ylim(0, 750)
