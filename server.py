from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Annotated, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nodes import Node, iddfs
from state import Action, Data, Pump, Sector, State
from succesors import ActionStrategy, get_successors


StrictInt = Annotated[int, Field(strict=True)]
StrictFloat = Annotated[float, Field(strict=True)]
PositiveFloat = Annotated[float, Field(strict=True, gt=0)]
NonNegativeFloat = Annotated[float, Field(strict=True, ge=0)]


class StrategyName(str, Enum):
	LAZY = "lazy"
	PROACTIVE = "proactive"
	COST_AWARE = "cost_aware"


class PumpRequest(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	caudal_m3h: PositiveFloat
	power_kw: PositiveFloat


class SectorRequest(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	area_m2: Annotated[int, Field(strict=True, gt=0)]
	l_min: NonNegativeFloat
	l_max: PositiveFloat
	pump: PumpRequest
	obj_level_m: NonNegativeFloat | None = None

	@model_validator(mode="after")
	def validate_levels(self) -> SectorRequest:
		if self.l_min > self.l_max:
			raise ValueError("l_min debe ser menor o igual que l_max")
		if self.obj_level_m is not None and not self.l_min <= self.obj_level_m <= self.l_max:
			raise ValueError("obj_level_m debe estar entre l_min y l_max")
		return self


def _default_tariff_table() -> list[float]:
	return [365.0] * 9 + [450.0] * 6 + [800.0] * 5 + [390.0] * 4


class SystemConfigRequest(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	sectors: list[SectorRequest] = Field(min_length=1)
	p_max_kw: PositiveFloat
	tariff_table: list[PositiveFloat] = Field(
		default_factory=_default_tariff_table, min_length=24, max_length=24
	)
	max_energy_cost: PositiveFloat = 380000.0
	water_loss_m: NonNegativeFloat = 0.002
	start_reservoir_v: PositiveFloat = 3000.0


class InitialStateRequest(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	t: StrictInt = Field(default=0, ge=0)
	water_levels_m: list[NonNegativeFloat] = Field(min_length=1)
	reservoir_v: NonNegativeFloat
	accumulated_cost: NonNegativeFloat = 0.0


class IrrigationRequest(BaseModel):
	"""Parámetros de una búsqueda IDDFS de secuenciación de riego."""

	model_config = ConfigDict(extra="forbid", strict=True)

	horizon_t: Annotated[int, Field(strict=True, ge=1, le=24)]
	system: SystemConfigRequest
	initial_state: InitialStateRequest
	strategy: StrategyName = Field(default=StrategyName.PROACTIVE, strict=False)

	@model_validator(mode="after")
	def validate_request(self) -> IrrigationRequest:
		if len(self.initial_state.water_levels_m) != len(self.system.sectors):
			raise ValueError("water_levels_m debe tener un nivel por cada sector")
		if self.initial_state.t != 0:
			raise ValueError("El estado inicial debe comenzar en t=0")
		for sector, level in zip(self.system.sectors, self.initial_state.water_levels_m):
			if not sector.l_min <= level <= sector.l_max:
				raise ValueError("Cada nivel inicial debe respetar los límites de su sector")
		return self


class SearchStep(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	interval: StrictInt
	pumps_active: tuple[StrictInt, ...]
	power_kw: StrictFloat
	water_pumped_m3: StrictFloat
	resulting_water_levels: list[StrictFloat]
	remaining_reservoir_v: StrictFloat
	accumulated_cost: StrictFloat


class IrrigationResponse(BaseModel):
	"""Resultado serializable de una búsqueda de secuenciación de riego."""

	model_config = ConfigDict(extra="forbid", strict=True)

	status: str
	execution_time_seconds: StrictFloat
	total_cost: StrictFloat
	final_depth: StrictInt
	sequence: list[SearchStep]


class NoSolutionError(Exception):
	"""Indica que el espacio de estados no contiene una solución válida."""


def _tariff(table: Sequence[float], hour: int) -> float:
	return table[hour] if hour < len(table) else table[-1]


def _to_data(request: IrrigationRequest) -> Data:
	tariff_table = tuple(request.system.tariff_table)
	sectors = [
		Sector(
			area_m2=sector.area_m2,
			min_lvl_m=sector.l_min,
			obj_lvl_m=sector.obj_level_m if sector.obj_level_m is not None else sector.l_min,
			max_lvl_m=sector.l_max,
			pump=Pump(power_kW=sector.pump.power_kw, caudal_m3h=sector.pump.caudal_m3h),
		)
		for sector in request.system.sectors
	]
	return Data(
		max_t=request.horizon_t,
		start_watertank=request.system.start_reservoir_v,
		max_instant_kW=request.system.p_max_kw,
		kWh_cost_gs=lambda hour: _tariff(tariff_table, hour),
		max_energy_cost=request.system.max_energy_cost,
		water_loss=request.system.water_loss_m,
		sectors=sectors,
	)


def _is_goal(horizon: int) -> Callable[[State], bool]:
	def goal(state: State) -> bool:
		return state.t >= horizon and state.watertank_m3 > 0

	return goal


def _response_from_result(result: Node[State], elapsed: float) -> IrrigationResponse:
	path = result.get_path()
	initial = path[0].state
	steps: list[SearchStep] = [
		SearchStep(
			interval=initial.t,
			pumps_active=tuple(0 for _ in initial.water_lvls),
			power_kw=0.0,
			water_pumped_m3=0.0,
			resulting_water_levels=initial.water_lvls,
			remaining_reservoir_v=initial.watertank_m3,
			accumulated_cost=initial.cost_acc_gs,
		)
	]
	for node in path[1:]:
		action = node.action
		if not isinstance(action, Action):
			continue
		steps.append(
			SearchStep(
				interval=node.state.t,
				pumps_active=action.pumps_active,
				power_kw=action.power_kW,
				water_pumped_m3=action.water_m3,
				resulting_water_levels=node.state.water_lvls,
				remaining_reservoir_v=node.state.watertank_m3,
				accumulated_cost=node.state.cost_acc_gs,
			)
		)
	return IrrigationResponse(
		status="SUCCESS",
		execution_time_seconds=elapsed,
		total_cost=path[-1].state.cost_acc_gs,
		final_depth=path[-1].state.t,
		sequence=steps,
	)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Irrigation IDDFS API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def read_index() -> FileResponse:
	"""Sirve la aplicación web de configuración y resultados."""
	return FileResponse(STATIC_DIR / "index.html")


@app.exception_handler(NoSolutionError)
async def no_solution_handler(_: Request, exc: NoSolutionError) -> JSONResponse:
	return JSONResponse(status_code=404, content={"status": "NO_SOLUTION_FOUND", "detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
	return JSONResponse(
		status_code=422,
		content={
			"status": "NO_SOLUTION_FOUND",
			"detail": "La solicitud es inviable o inválida: "
			+ "; ".join(error["msg"] for error in exc.errors()),
		},
	)


@app.post("/api/v1/irrigation/search", response_model=IrrigationResponse, status_code=200)
async def search_irrigation(request: IrrigationRequest) -> JSONResponse:
	"""Ejecuta IDDFS para hallar una secuencia válida durante el horizonte solicitado."""
	data = _to_data(request)
	initial_state = State(
		t=request.initial_state.t,
		water_lvls=request.initial_state.water_levels_m,
		watertank_m3=request.initial_state.reservoir_v,
		cost_acc_gs=request.initial_state.accumulated_cost,
	)
	strategy = ActionStrategy[request.strategy.name]
	start = time.perf_counter()
	result = await asyncio.to_thread(
		iddfs,
		initial_state=initial_state,
		is_goal=_is_goal(request.horizon_t),
		get_successors=lambda state: get_successors(state, data, strategy),
		max_depth=request.horizon_t,
	)
	elapsed = time.perf_counter() - start
	if result is None:
		raise NoSolutionError(
			"No existe una secuencia válida bajo el presupuesto o los límites físicos especificados para T."
		)
	response = _response_from_result(result, elapsed)
	return JSONResponse(status_code=200, content=response.model_dump(mode="json"))
