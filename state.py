# Sectores
# - Necesida de agua en cm de altura
# - Metros cuadrados del inundacion de cultivo
# - Bomba, con consumo energetico y suministro de agua (encendido/apagado)

# Estado del Sistema
# - Arreglo de necesidad de cada sector Necesidad
# - Volumen de agua disponible(por sector)
# - Estado de bomba de agua (por sector)
# - Consumo total de electricidad en kWh
# - Intervalo de tiempo actual

from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class Pump:
    power_kW: float
    caudal_m3h: float

@dataclass(frozen=True)
class Sector:
    area_m2: int
    obj_lvl_m: float
    min_lvl_m: float
    max_lvl_m: float

    pump: Pump

@dataclass(frozen=True)
class Action:
    pumps_active: tuple[int, ...]
    power_kW: float
    water_m3: float 

    def __repr__(self) -> str:
        return f"-Bombas: {', '.join("activa" if p == 1 else "inactiva" for p in self.pumps_active)}\n-Uso Kilowatt: {self.power_kW:,.2f}kW\n-Agua bombeada: {self.water_m3:,.2f}m^3"

@dataclass(frozen=True)
class State:
    """
    Representa estado del sistema en un intervalo de tiempo dado
    """
    t: int
    water_lvls: list[float]
    watertank_m3: float
    cost_acc_gs: float

    def __repr__(self):
        return f"Intervalo: {self.t}\n-lvls(mm): {', '.join(f'{l*1000:.1f}' for l in self.water_lvls)}\n-tank: {self.watertank_m3:,.2f} m^3\n-acc_cost: {self.cost_acc_gs:,.2f}Gs"

@dataclass
class Data:
    start_watertank: int
    max_instant_kW: int
    kWh_cost_gs: Callable[[int], float]
    max_energy_cost: float
    water_loss: float

    sectors: list[Sector]

# Pruebas formulas 
def water_loss_liters(area_m2: int, loss_c: float = 0.15, time_h: int = 1)-> float:
    return area_m2 * loss_c * time_h

def water_level_m(area_m2: float, water_m3: float)-> float:
    return water_m3 / area_m2


if __name__ == "__main__":

    area = 10000
    volume = 120
    print(f"Nivel del algua para {area:,} m2 al verter {volume*1000:,} l es de {water_level_m(area, volume)*1000:,.1f} mm")
    