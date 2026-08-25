# Planificacion de riego de arrozales de misiones

from itertools import product
from enum import Enum

from state import State, Action, Data, water_level_m

type ActionSuccessorLs = list[tuple[Action, State]]

class ActionStrategy(Enum):
    LAZY = 0
    PROACTIVE = 1
    COST_AWARE = 2

def pump_actions(pumps_count: int) -> list[tuple[int, ...]]:
    return list(product([0, 1], repeat=pumps_count))

def filter_actions_by_power(
        actions: list[tuple[int, ...]], 
        pump_powers: list[float], 
        data: Data
    ) -> list[tuple[int, ...]]:
    "Filtra las combinaciones de acciones que superan la potencia máxima permitida."

    real_actions: list[tuple[int, ...]] = []
    for ac in actions:
        total_power = sum(v * p for v, p in zip(ac, pump_powers))
        if total_power <= data.max_instant_kW:
            real_actions.append(ac)

    return real_actions


def sort_successors(order: ActionStrategy, act_successors: ActionSuccessorLs, data: Data):
    if order == ActionStrategy.LAZY:
        return sorted(act_successors, key=lambda p: p[0].power_kW)

    elif order == ActionStrategy.PROACTIVE:
        return sorted(act_successors, key=lambda pair: pair[0].water_m3, reverse=True)

    elif order == ActionStrategy.COST_AWARE:
        return sorted(act_successors, key=lambda pair: pair[0].power_kW * data.kWh_cost_gs(pair[1].t))

    return act_successors

def get_successors(state: State, data: Data, order: ActionStrategy = ActionStrategy.LAZY)-> ActionSuccessorLs:
    pump_powers = [s.pump.power_kW for s in data.sectors]

    actions = filter_actions_by_power(
        actions=pump_actions(len(data.sectors)),
        pump_powers=pump_powers,
        data=data
    ) 

    succesors: ActionSuccessorLs = []
    
    for i in range(len(actions)):
        water_lvls: list[float] = []
        water_used = 0.0
        kW_used = 0.0

        # Ignora la iteracion si el algun nivel de agua lvl[i] no cumple min <= lvl[i] <= max
        undone = False
        for j in range(len(data.sectors)):
            q = actions[i][j] * water_level_m(data.sectors[j].area_m2, data.sectors[j].pump.caudal_m3h)

            w_lvl = state.water_lvls[j] - data.water_loss + q
            if data.sectors[j].min_lvl_m <= w_lvl <= data.sectors[j].max_lvl_m:
                water_lvls.append(w_lvl)
                
            else:
                undone = True
                break

            water_used += actions[i][j] * data.sectors[j].pump.caudal_m3h
            kW_used += actions[i][j] * data.sectors[j].pump.power_kW

        if (undone or 
            # Evita acciones con tanque con m3 de agua negativos
            (state.watertank_m3 - water_used < 0) or
            # Evita exceder el coste maximo en electricidad
            (state.cost_acc_gs + kW_used * data.kWh_cost_gs(state.t) > data.max_energy_cost)
        ):
            continue

        succesors.append(
            (
                Action(
                    pumps_active=actions[i],
                    power_kW=kW_used,
                    water_m3=water_used
                ),
                State(
                    t=state.t + 1,
                    water_lvls=water_lvls,
                    watertank_m3=state.watertank_m3 - water_used,
                    cost_acc_gs=state.cost_acc_gs + kW_used * data.kWh_cost_gs(state.t)
                )
            )
        )

    return sort_successors(order, succesors, data)