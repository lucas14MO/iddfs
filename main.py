from state import State, Action, Data, Sector, Pump
from nodes import iddfs
from succesors import get_successors, ActionStrategy

import time
from datetime import timedelta

def table_tariff(hour: int):
    if 9 <= hour <= 14: return 450
    if 15 <= hour <= 19: return 800
    if hour >= 20: return 390

    return 365

def is_goal(state: State) -> bool:

    if state.t < 15: return False

    return state.watertank_m3 > 0

def main():

    sectors = [
        Sector(
            area_m2=5000, 
            min_lvl_m=0.08, obj_lvl_m=0.10, max_lvl_m=0.12, 
            pump=Pump(power_kW=20, caudal_m3h=85)
        ),
        Sector(
            area_m2=10000, 
            min_lvl_m=0.09, obj_lvl_m=0.10, max_lvl_m=0.13, 
            pump=Pump(power_kW=30, caudal_m3h=100)
        ),
        Sector(
            area_m2=10000, 
            min_lvl_m=0.09, obj_lvl_m=0.10, max_lvl_m=0.13, 
            pump=Pump(power_kW=35, caudal_m3h=120)
        )
    ]

    data = Data(
        max_t = 15,
        start_watertank = 3000,
        max_instant_kW = 55,
        kWh_cost_gs = table_tariff,
        max_energy_cost=380000,
        water_loss = 0.002,
        sectors = sectors
    )

    base = State(
        t=0,
        water_lvls=[0.1, 0.12, 0.11],
        watertank_m3=data.start_watertank,
        cost_acc_gs=0
    )

    start = time.time()
    
    result = iddfs(
        initial_state=base, 
        is_goal=is_goal,
        get_successors=lambda s: get_successors(s, data, ActionStrategy.PROACTIVE),
        max_depth=data.max_t
    )

    total_secs = time.time() - start

    if not result:
        print("No se encontro un resultado satisfactorio")
        
    else:
        path = result.get_path()

        for node in path:
            print(f"{node.state}")

            if isinstance(node.action, Action):
                print(f"{node.action}")

            print("")

    print(f"Tiempo: {timedelta(seconds=total_secs)}")

if __name__ == "__main__":
    main()