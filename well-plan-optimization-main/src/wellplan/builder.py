from typing import Optional
from datetime import datetime
from loguru import logger
from wellplan.core.plan import Plan, WellPlanContext
from wellplan.core.well import Well
from wellplan.services.risk_strategy import RiskStrategy
from wellplan.services.cost import CostFunction
from wellplan.services.infrastructure import Infrastructure, SimpleInfrastructure
from wellplan.services.team_manager import BaseTeamManager
from wellplan.services.production import ProductionProfile, LinearProductionProfile
from wellplan.services.constraint import ConstraintManager, Constraint


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
        
        return max(
            (c for c in candidates if c.cost is not None),
            key=lambda x: x.cost - (x.metadata.get('drill_team_penalty', 0) if self.use_drill_team_penalty else 0)
        )

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
