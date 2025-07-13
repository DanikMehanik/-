#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации разницы между жадным алгоритмом и имитацией отжига
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import random
from datetime import datetime, timedelta
from wellplan.builder import PlanBuilder
from wellplan.core.well import Well
from wellplan.services.cost import CostFunction
from wellplan.services.team_manager import BaseTeamManager
from wellplan.services.production import LinearProductionProfile
from wellplan.services.infrastructure import SimpleInfrastructure

class SimpleCostFunction(CostFunction):
    def compute(self, context):
        # Простая функция стоимости - случайная стоимость для демонстрации
        context.cost = random.uniform(1000, 10000)
        return context

class SimpleTeamManager(BaseTeamManager):
    def __init__(self):
        self.team_pool = None
    
    def get_assignments(self, context):
        # Простая логика назначения команд
        pass
    
    def assign(self, context):
        # Простая логика назначения
        pass

def create_test_wells():
    """Создает тестовые скважины"""
    wells = []
    start_date = datetime(2024, 1, 1)
    
    for i in range(10):
        well = Well(
            name=f"Well_{i+1}",
            cluster=f"Cluster_{i//3 + 1}",
            init_entry_date=start_date + timedelta(days=i*30),
            depend_from_cluster=None
        )
        wells.append(well)
    
    return wells

def test_algorithms():
    """Тестирует оба алгоритма и показывает разницу в результатах"""
    
    # Создаем тестовые данные
    wells = create_test_wells()
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    cost_function = SimpleCostFunction()
    team_manager = SimpleTeamManager()
    
    print("=== Тестирование алгоритмов оптимизации ===\n")
    
    # Тест 1: Жадный алгоритм
    print("1. Жадный алгоритм:")
    greedy_builder = PlanBuilder(
        start=start_date,
        end=end_date,
        cost_function=cost_function,
        algorithm_type="greedy"
    )
    
    # Устанавливаем seed для воспроизводимости
    random.seed(42)
    greedy_plan = greedy_builder.compile(wells.copy(), team_manager)
    
    print(f"   Количество скважин в плане: {len(greedy_plan.well_plans)}")
    if greedy_plan.well_plans:
        print(f"   Первая скважина: {greedy_plan.well_plans[0].well.name}")
        print(f"   Стоимость первой скважины: {greedy_plan.well_plans[0].cost:.2f}")
    
    # Тест 2: Имитация отжига
    print("\n2. Имитация отжига:")
    sa_builder = PlanBuilder(
        start=start_date,
        end=end_date,
        cost_function=cost_function,
        algorithm_type="simulated_annealing"
    )
    
    # Устанавливаем seed для воспроизводимости
    random.seed(42)
    sa_plan = sa_builder.compile(wells.copy(), team_manager)
    
    print(f"   Количество скважин в плане: {len(sa_plan.well_plans)}")
    if sa_plan.well_plans:
        print(f"   Первая скважина: {sa_plan.well_plans[0].well.name}")
        print(f"   Стоимость первой скважины: {sa_plan.well_plans[0].cost:.2f}")
    
    # Сравнение результатов
    print("\n=== Сравнение результатов ===")
    
    greedy_wells = [wp.well.name for wp in greedy_plan.well_plans]
    sa_wells = [wp.well.name for wp in sa_plan.well_plans]
    
    print(f"Жадный алгоритм выбрал скважины: {greedy_wells}")
    print(f"Имитация отжига выбрала скважины: {sa_wells}")
    
    # Проверяем, отличаются ли результаты
    if greedy_wells != sa_wells:
        print("\n✅ Результаты отличаются! Алгоритмы работают по-разному.")
        
        # Показываем различия
        greedy_set = set(greedy_wells)
        sa_set = set(sa_wells)
        
        only_greedy = greedy_set - sa_set
        only_sa = sa_set - greedy_set
        
        if only_greedy:
            print(f"   Только жадный алгоритм выбрал: {list(only_greedy)}")
        if only_sa:
            print(f"   Только имитация отжига выбрала: {list(only_sa)}")
    else:
        print("\n❌ Результаты одинаковые. Попробуйте запустить еще раз для получения разных результатов.")
    
    # Анализ характеристик алгоритмов
    print("\n=== Характеристики алгоритмов ===")
    print("Жадный алгоритм:")
    print("  - Всегда выбирает кандидата с максимальной стоимостью")
    print("  - Быстрый и предсказуемый")
    print("  - Может застревать в локальных оптимумах")
    
    print("\nИмитация отжига:")
    print("  - Исследует пространство решений более широко")
    print("  - Может принимать худшие решения на ранних этапах")
    print("  - Учитывает временные факторы и случайность")
    print("  - Более разнообразные результаты")

if __name__ == "__main__":
    test_algorithms() 