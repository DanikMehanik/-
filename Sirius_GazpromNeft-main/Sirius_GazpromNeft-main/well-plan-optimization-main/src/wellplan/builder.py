from typing import Optional, Literal
from datetime import datetime
import random
import math
from loguru import logger
from wellplan.core.plan import Plan, WellPlanContext
from wellplan.core.well import Well
from wellplan.services.risk_strategy import RiskStrategy
from wellplan.services.cost import CostFunction
from wellplan.services.infrastructure import Infrastructure, SimpleInfrastructure
from wellplan.services.team_manager import BaseTeamManager
from wellplan.services.production import ProductionProfile, LinearProductionProfile
from wellplan.services.constraint import ConstraintManager, Constraint
from wellplan.services.optimization import SimulatedAnnealingPlanner


class PlanBuilder:
    def compile(
            self,
            wells: list[Well],
            manager: BaseTeamManager,

    ) -> Plan:
        initial_plan = self._create_initial_plan(wells, manager)
        optimizer = SimulatedAnnealingPlanner(
            initial_temp=1000,
            cooling_rate=0.95,
            iterations=100
        )

        optimized_plan = optimizer.optimize(initial_plan, manager)
        return optimized_plan

class PlanBuilder:
    def __init__(
        self,
        start: datetime,
        end: datetime,
        cost_function: CostFunction,
        infrastructure: Infrastructure = SimpleInfrastructure(),
        production_profile: ProductionProfile = LinearProductionProfile(),
        constraints: Optional[list[Constraint]] = None,
        use_drill_team_penalty: bool = True
    ) -> None:
        self.start = start
        self.end = end
        self.infra = infrastructure
        self.profiler = production_profile
        self.cost_function = cost_function
        self.remaining_wells: list[Well]
        self._constraints = ConstraintManager(constraints if constraints is not None else [])
        self.use_drill_team_penalty = use_drill_team_penalty

    def compile(
        self,
        wells: list[Well],
        manager: BaseTeamManager,
        risk_strategy: Optional[RiskStrategy] = None,
        keep_order: bool = False,
        cluster_ordered: bool = True,

    ) -> Plan:
        plan = Plan()
        self.remaining_wells = wells.copy()

        current_start = self.start
        while self.remaining_wells and current_start < self.end:
            candidates = self._build_contexts(manager, current_start)
            if not candidates:
                break

            candidates = self._filter_candidates(candidates, plan, risk_strategy, cluster_ordered)
            
            if not candidates:
                next_year = self._constraints.get_period_end(current_start.year)
                logger.info(f"No candidates for {current_start.year}, moving to {next_year or current_start.year+1}")
                current_start = datetime((next_year or current_start.year+1), 1, 1)
                continue


            best_candidate = self._select_best_candidate(
                candidates, keep_order=keep_order
            )
            logger.debug(f"Best candidate: {best_candidate.well.name}, cost: {best_candidate.cost}")
            manager.assign(best_candidate)

            self.remaining_wells.remove(best_candidate.well)

            if risk_strategy:
                risk_strategy.define_risk(best_candidate)
                self.cost_function.compute(best_candidate)

            plan.add_context(best_candidate)

        return plan

    def _build_contexts(
        self,
        manager: BaseTeamManager,
        start: datetime,
    ) -> list[WellPlanContext]:
        return [
            context
            for well in self.remaining_wells
            if (context := self._build_context(well, manager, start)) is not None
        ]

    def _build_context(
        self,
        well: Well,
        manager: BaseTeamManager,
        start: datetime,
    ) -> Optional[WellPlanContext]:
        if not self._is_cluster_finished(well.depend_from_cluster):
            return None

        context = WellPlanContext(
            well,
            start=max(self.infra.get_ready_date(well=well), start),
            end=self.end,
        )

        manager.get_assignments(context)

        # Remove wells that doesn't fit to plan
        if context.get_next_available_date() > self.end or not context.entries:
            return None

        self.profiler.compute(context)

        return context

    def _select_best_candidate(
        self, candidates: list[WellPlanContext], keep_order: bool = False
    ) -> WellPlanContext:
        if keep_order:
            return min((c for c in candidates), key=lambda x: x.well.init_entry_date)
        
        if not candidates:
            raise ValueError("No candidates provided")
        return self._simulated_annealing_selection(candidates)

    def _simulated_annealing_selection(
        self, 
        candidates: list[WellPlanContext],
        initial_temp: float = 1000.0,
        cooling_rate: float = 0.95,
        min_temp: float = 1.0,
        iterations_per_temp: int = 10
    ) -> WellPlanContext:


        valid_candidates = [c for c in candidates if c.cost is not None]
        if not valid_candidates:
            return candidates[0]

        if len(valid_candidates) <= 3:
            if random.random() < 0.6:
                best_candidate = max(valid_candidates, key=lambda c: self._calculate_candidate_score(c))
                logger.debug(f"SA algorithm (small set) selected best: {best_candidate.well.name}, cost: {best_candidate.cost}")
                return best_candidate
            else:
                random_candidate = random.choice(valid_candidates)
                logger.debug(f"SA algorithm (small set) selected random: {random_candidate.well.name}, cost: {random_candidate.cost}")
                return random_candidate

        current_candidate = random.choice(valid_candidates)
        current_score = self._calculate_candidate_score(current_candidate)

        best_candidate = current_candidate
        best_score = current_score
        
        temp = initial_temp
        
        while temp > min_temp:
            for _ in range(iterations_per_temp):
                neighbor_candidate = self._get_neighbor_candidate(valid_candidates, current_candidate)
                neighbor_score = self._calculate_candidate_score(neighbor_candidate)

                if self._accept_solution(current_score, neighbor_score, temp):
                    current_candidate = neighbor_candidate
                    current_score = neighbor_score

                    if current_score > best_score:
                        best_candidate = current_candidate
                        best_score = current_score

            temp *= cooling_rate
        
        logger.debug(f"SA algorithm selected: {best_candidate.well.name}, cost: {best_candidate.cost}")
        return best_candidate
    
    def _calculate_candidate_score(self, candidate: WellPlanContext) -> float:

        base_score = candidate.cost or 0.0
        penalty = candidate.metadata.get('drill_team_penalty', 0) if self.use_drill_team_penalty else 0
        random_factor = random.uniform(0.95, 1.05)
        time_factor = 1.0
        if candidate.well.init_entry_date:
            days_from_start = (candidate.well.init_entry_date - self.start).days
            time_factor = max(0.8, 1.0 - days_from_start / 365.0)
        return (base_score - penalty) * random_factor * time_factor
    
    def _get_neighbor_candidate(
        self, 
        candidates: list[WellPlanContext], 
        current_candidate: WellPlanContext
    ) -> WellPlanContext:

        if random.random() < 0.7:
            return random.choice(candidates)
        else:
            current_cost = current_candidate.cost or 0
            cost_range = current_cost * 0.2
            
            similar_candidates = [
                c for c in candidates 
                if abs((c.cost or 0) - current_cost) <= cost_range
            ]
            
            if similar_candidates:
                return random.choice(similar_candidates)
            else:
                return random.choice(candidates)
    
    def _accept_solution(self, current_score: float, new_score: float, temp: float) -> bool:
        if new_score > current_score:
            return True

        delta = new_score - current_score
        if temp > 0:
            probability = math.exp(delta / temp)
            return random.random() < probability
        
        return False

    def _is_cluster_finished(self, cluster: Optional[str]) -> bool:
        if cluster is None:
            return True
        return not any(well.cluster == cluster for well in self.remaining_wells)

    def _filter_candidates(
        self,
        candidates: list[WellPlanContext],
        plan: Plan,
        risk_strategy: Optional[RiskStrategy] = None,
        cluster_ordered: bool = True,
    ) -> list[WellPlanContext]:
        
        
        if cluster_ordered and candidates:
            earliest_per_cluster: dict[str, WellPlanContext] = {}
            min_date = datetime.min.replace(tzinfo=None)
            
            for candidate in candidates:
                cluster = candidate.well.cluster
                candidate_date = candidate.well.init_entry_date or min_date
                
                existing = earliest_per_cluster.get(cluster)
                if not existing or (
                    (existing.well.init_entry_date or min_date) > candidate_date
                ):
                    earliest_per_cluster[cluster] = candidate
            
            candidates = list(earliest_per_cluster.values())
        
        
        if risk_strategy:
            candidates = [risk_strategy.apply_risk(c) for c in candidates]

        candidates = [self.cost_function.compute(c) for c in candidates]

        candidates = [
                c for c in candidates if not self._constraints.is_violated(plan, c)
            ]

        return candidates
