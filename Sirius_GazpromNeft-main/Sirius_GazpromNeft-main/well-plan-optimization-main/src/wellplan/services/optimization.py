import random
import math
from copy import deepcopy
from datetime import timedelta
from wellplan.core import Plan
from wellplan.services.team_manager import TeamManager


class SimulatedAnnealingPlanner:
    def __init__(self,
                 initial_temp: float = 1000,
                 cooling_rate: float = 0.95,
                 min_temp: float = 1,
                 iterations: int = 100):
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.min_temp = min_temp
        self.iterations = iterations

    def optimize(self, plan: Plan, manager: TeamManager) -> Plan:
        current_plan = deepcopy(plan)
        best_plan = deepcopy(plan)
        current_cost = self._calculate_cost(current_plan)
        best_cost = current_cost

        temp = self.initial_temp

        while temp > self.min_temp:
            for _ in range(self.iterations):
                neighbor = self._get_neighbor(current_plan, manager)
                neighbor_cost = self._calculate_cost(neighbor)

                if self._accept_solution(current_cost, neighbor_cost, temp):
                    current_plan = neighbor
                    current_cost = neighbor_cost

                    if current_cost > best_cost:
                        best_plan = deepcopy(current_plan)
                        best_cost = current_cost

            temp *= self.cooling_rate

        return best_plan

    def _calculate_cost(self, plan: Plan) -> float:
        return plan.total_profit()

    def _get_neighbor(self, plan: Plan, manager: TeamManager) -> Plan:
        neighbor = deepcopy(plan)

        mutation_type = random.choice([
            'swap_wells',
            'shift_well',
            'reassign_team'
        ])

        if mutation_type == 'swap_wells' and len(neighbor.well_plans) > 1:
            idx1, idx2 = random.sample(range(len(neighbor.well_plans)), 2)
            neighbor.well_plans[idx1], neighbor.well_plans[idx2] = \
                neighbor.well_plans[idx2], neighbor.well_plans[idx1]

        elif mutation_type == 'shift_well':
            idx = random.randint(0, len(neighbor.well_plans) - 1)
            days_shift = random.randint(-30, 30)
            for entry in neighbor.well_plans[idx].entries:
                entry.start += timedelta(days=days_shift)
                entry.end += timedelta(days=days_shift)

        elif mutation_type == 'reassign_team':
            idx = random.randint(0, len(neighbor.well_plans) - 1)
            wp = neighbor.well_plans[idx]
            if wp.entries:
                entry = random.choice(wp.entries)
                new_team = random.choice(manager.team_pool.get_teams_for_task(entry.task))
                entry.team = new_team

        for wp in neighbor.well_plans:
            manager.assign(wp)

        return neighbor

    def _accept_solution(self, current_cost: float, new_cost: float, temp: float) -> bool:
        """Критерий Метрополиса для принятия решений"""
        if new_cost > current_cost:
            return True
        return math.exp((new_cost - current_cost) / temp) > random.random()