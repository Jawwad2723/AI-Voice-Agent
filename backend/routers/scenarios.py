"""
Scenarios router — returns available call scenarios and their configurations.
"""

from fastapi import APIRouter
from typing import List

from models.schemas import ScenarioInfo, ScenarioType
from services.scenario_service import SCENARIO_REGISTRY

router = APIRouter()


@router.get("/", response_model=List[ScenarioInfo])
async def list_scenarios():
    """Return all available call scenarios."""
    return list(SCENARIO_REGISTRY.values())


@router.get("/{scenario_type}", response_model=ScenarioInfo)
async def get_scenario(scenario_type: ScenarioType):
    """Get details for a specific scenario."""
    scenario = SCENARIO_REGISTRY.get(scenario_type)
    if not scenario:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario
