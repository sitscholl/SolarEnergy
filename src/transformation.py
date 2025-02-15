import numpy as np

def convert_solar_energy(srad, efficiency = 0.15, system_loss = 0.8, area = None, kWp = None):
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

    out = srad * area * efficiency * system_loss

    return(out)

def _solar_to_el_2(srad, system_size, performance_ratio=0.8):
    """
    Simplified Method Using "Performance Ratio". NOT NEEDED; EQUIVALENT TO `solar_to_el` WITH kWp AS INPUT AND NOT AREA:

    If you know the system size (kWp) and performance ratio (PR), use:
    Energy (kWh) = Solar Radiation (kWh/m²) × System Size (kWp) × Performance Ratio

    Parameters
    ----------
    srad : float
        Solar radiation in kWh/m².
    system_size : float
        System size in kWp.
    performance_ratio : float, optional
        Performance Ratio (PR), typically 0.75–0.85 for well-maintained systems.
        The default is 0.8.

    Returns
    -------
    float
        The electricity output in kWh.

    Example
    -------
    For a 5 kWp system with PR = 0.80 and solar radiation = 1,500 kWh/m²/year:
    Annual Energy = 1,500 × 5 × 0.80 = 6,000 kWh
    """
    return srad * system_size * performance_ratio
