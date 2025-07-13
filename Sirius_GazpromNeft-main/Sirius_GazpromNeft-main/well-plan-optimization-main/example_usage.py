#!/usr/bin/env python3
"""
Пример использования PlanBuilder с разными алгоритмами оптимизации
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
from wellplan.builder import PlanBuilder
from wellplan.services.cost import CostFunction
from wellplan.services.team_manager import BaseTeamManager
from wellplan.services.production import LinearProductionProfile
from wellplan.services.infrastructure import SimpleInfrastructure

def demonstrate_algorithm_difference():
    """
    Демонстрирует разницу между жадным алгоритмом и имитацией отжига
    """
    
    # Настройки
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    # Создаем простую функцию стоимости
    class DemoCostFunction(CostFunction):
        def compute(self, context):
            # Для демонстрации используем простую стоимость
            import random
            context.cost = random.uniform(1000, 5000)
            return context
    
    # Создаем простой менеджер команд
    class DemoTeamManager(BaseTeamManager):
        def __init__(self):
            self.team_pool = None
        
        def get_assignments(self, context):
            # Простая логика
            pass
        
        def assign(self, context):
            # Простая логика
            pass
    
    cost_function = DemoCostFunction()
    team_manager = DemoTeamManager()
    
    print("=== Демонстрация разницы между алгоритмами ===\n")
    
    # Создаем два билдера с разными алгоритмами
    greedy_builder = PlanBuilder(
        start=start_date,
        end=end_date,
        cost_function=cost_function,
        algorithm_type="greedy"
    )
    
    sa_builder = PlanBuilder(
        start=start_date,
        end=end_date,
        cost_function=cost_function,
        algorithm_type="simulated_annealing"
    )
    
    print("Созданы два PlanBuilder:")
    print(f"1. Жадный алгоритм: algorithm_type='greedy'")
    print(f"2. Имитация отжига: algorithm_type='simulated_annealing'")
    
    print("\nОсновные различия:")
    print("• Жадный алгоритм всегда выбирает кандидата с максимальной стоимостью")
    print("• Имитация отжига исследует пространство решений более широко")
    print("• SA может принимать худшие решения на ранних этапах для поиска глобального оптимума")
    print("• SA учитывает временные факторы и добавляет случайность")
    
    print("\nДля использования в вашем коде:")
    print("""
# Жадный алгоритм
builder = PlanBuilder(
    start=start_date,
    end=end_date,
    cost_function=cost_function,
    algorithm_type="greedy"  # ← Ключевой параметр
)

# Имитация отжига
builder = PlanBuilder(
    start=start_date,
    end=end_date,
    cost_function=cost_function,
    algorithm_type="simulated_annealing"  # ← Ключевой параметр
)
    """)

if __name__ == "__main__":
    demonstrate_algorithm_difference() 