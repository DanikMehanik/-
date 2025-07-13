import math
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol, TypeAlias

from wellplan.core import ScheduleEntry, Task, Team, TeamPool, Well, WellPlanContext


class BaseMovement(Protocol):
    def get_move_days(
        self,
        from_cluster: Optional[str | None],
        to_cluster: str,
    ) -> float:
        pass


class SimpleTeamMovement:
    def get_move_days(
        self,
        from_cluster: Optional[str | None],
        to_cluster: str,
    ) -> float:
        if from_cluster == to_cluster:
            return 1
        return 14


@dataclass(frozen=True)
class Coordinate:
    x: float
    y: float
    z: float

    def distance_to(self, other: "Coordinate") -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )


@dataclass
class DistanceTeamMovement:
    cluster_coordinates: dict[str, Coordinate] = field(default_factory=dict)
    min_days_between_clusters: float = 90
    team_speed_kmh: float = 15
    same_cluster_move_days: float = 1

    @classmethod
    def from_dicts(
        cls,
        clusters: list[dict[str, Any]],
        **kwargs,
    ) -> "DistanceTeamMovement":
        required_keys = {"cluster", "x", "y", "z"}
        for entry in clusters:
            if not required_keys.issubset(entry.keys()):
                raise ValueError(
                    "Each dictionary must contain keys: 'cluster', 'x', 'y', 'z'."
                )

        coordinates = {
            str(entry["cluster"]): Coordinate(
                entry["x"],
                entry["y"],
                entry["z"],
            )
            for entry in clusters
        }

        return cls(cluster_coordinates=coordinates, **kwargs)

    def get_move_days(
        self,
        from_cluster: Optional[str | None],
        to_cluster: str,
    ) -> float:
        if from_cluster == to_cluster:
            return self.same_cluster_move_days

        if from_cluster is None:
            return self.min_days_between_clusters
        try:
            from_coor = self.cluster_coordinates[from_cluster]
            to_coor = self.cluster_coordinates[to_cluster]
        except KeyError:
            return self.min_days_between_clusters

        distance_meters = from_coor.distance_to(to_coor)
        travel_days = (distance_meters / (self.team_speed_kmh * 1000)) / 24

        return self.min_days_between_clusters + travel_days


@dataclass
class TeamState:
    available_from: datetime = field(default=datetime.min)
    current_cluster: Optional[str] = None


TaskLimits: TypeAlias = dict[Task, int]
YearlyLimits: TypeAlias = dict[int, TaskLimits]

class BaseTeamManager(ABC):
    def __init__(
        self,
        team_pool: TeamPool,
        movement: BaseMovement = SimpleTeamMovement(),
        enable_team_count: bool = True,
        limits: Optional[YearlyLimits] = None
    ):
        self.team_pool = team_pool
        self.movement = movement
        self._states: dict[Team, TeamState] = {
            team: TeamState() for team in self.team_pool.teams
        }
        self.enable_team_count = enable_team_count
        self._usage_counts: dict[int, dict[Task, set[Team]]] = defaultdict(lambda: defaultdict(set))
        self.limits = limits or {}

    def _check_limit(self, task: Task, year: int, team: Team) -> bool:
        if not self.limits:
            return True
            
        year_limits = self.limits.get(year)
        if not year_limits:
            return True

        max_count = year_limits.get(task)
        if max_count is None:
            return True
        
        if team in self._usage_counts[year][task]:
            return True
        
        return len(self._usage_counts[year][task]) < max_count


    def _record_usage(self, task: Task, assignment_year: int, team: Team) -> None:

        relevant_years = sorted([y for y in self.limits.keys() if y >= assignment_year])

        for year_to_record in relevant_years:
            year_limits = self.limits.get(year_to_record, {})
            year_task_limit = year_limits.get(task) 

            if year_task_limit is None:
                continue 

            current_usage_set = self._usage_counts[year_to_record][task]

            if self._check_limit(task, year_to_record, team):
                current_usage_set.add(team)
                

    @abstractmethod
    def get_assignments(self, context: WellPlanContext) -> WellPlanContext:
        pass

    @abstractmethod
    def assign(self, context: WellPlanContext) -> None:
        pass

    def _count_teams_on_cluster(
        self,
        context: WellPlanContext,
        task: Optional[Task] = None,
        team: Optional[Team] = None,
    ) -> WellPlanContext:
        metadata_key = f"team_count_{task.name.lower()}" if task else "team_count"
        count = self._count_teams_on_cluster_by_task(context.well.cluster, task, team)
        context.metadata[metadata_key] = count
        return context

    def _count_teams_on_cluster_by_task(
        self,
        cluster: str,
        task: Optional[Task] = None,
        team: Optional[Team] = None,
    ) -> int:
        return sum(
            1 for _team, team_state in self._states.items()
            if (team_state.current_cluster == cluster and
                (task is None or task in _team.supported_tasks) and
                _team != team)
        )


class TeamManager(BaseTeamManager):
    def get_assignments(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        tasks = context.well.tasks
        
        for task in tasks:
            if task not in self.team_pool.supported_tasks:
                raise ValueError(f"Task '{task.name}' is not supported by any team")
            
            candidates = []
            for team in self.team_pool.get_teams_for_task(task):
                state = self._states[team]
                travel_time = self._get_travel_time(state, context.well)
                start_time = self._find_available_start_time(
                    task=task,
                    team=team,
                    travel_time=travel_time,
                    context=context
                )
                
                if start_time is None:
                    continue 
                end_time = start_time + task.duration
                candidates.append((start_time, end_time, team, travel_time))
            
            if candidates:
                best_start, best_end, best_team, travel_time = min(
                    candidates, key=lambda x: x[1]
                )
                context.entries.append(
                    ScheduleEntry(
                        team=best_team,
                        task=task,
                        start=best_start,
                        end=best_end,
                        travel_time=travel_time,
                    )
                )
                
                if self.enable_team_count:
                    self._count_teams_on_cluster(context, task, best_team)
        
        return context

    def assign(
        self,
        context: WellPlanContext,
    ):
        for entry in context.entries:
            self._states[entry.team] = TeamState(
                available_from=entry.end,
                current_cluster=context.well.cluster,
            )
            self._record_usage(entry.task, entry.start.year, entry.team) 

    def _get_travel_time(
        self,
        state: TeamState,
        well: Well,
    ) -> timedelta:
        move_days = self.movement.get_move_days(
            from_cluster=state.current_cluster,
            to_cluster=well.cluster,
        )
        travel_time = timedelta(days=move_days)
        return travel_time
    
    def _find_available_start_time(
        self,
        task: Task,
        team: Team,
        travel_time: timedelta,
        context: WellPlanContext,
    ) -> Optional[datetime]:

        base_start = max(
            self._states[team].available_from + travel_time,
            context.get_next_available_date(),
        )
        
        current_start = base_start
        
        while True:
            current_year = current_start.year
            
            if self._check_limit(task, current_year, team):
                return current_start
            else:
                current_start = datetime(current_year + 1, 1, 1)
