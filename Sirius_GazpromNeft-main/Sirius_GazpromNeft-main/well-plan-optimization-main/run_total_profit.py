#!/usr/bin/env python3
"""
Скрипт для демонстрации вывода total_profit
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime, timedelta
from wellplan.core import TeamPool, Well
from wellplan.services import NPV, BaseCapex, BaseOpex, TeamManager
from wellplan.services.production import LinearProductionProfile
from wellplan.builder import PlanBuilder

def main():
    print("=== ДЕМОНСТРАЦИЯ TOTAL_PROFIT ===\n")
    
    # Создание тестовых скважин
    wells = [
        Well(
            name="Test_Well_1", 
            cluster="Cluster_A", 
            field="Field_A",
            layer="Layer_1",
            purpose="production", 
            well_type="ГС", 
            oil_rate=100.0,
            liq_rate=150.0,
            length=3000
        ),
        Well(
            name="Test_Well_2", 
            cluster="Cluster_B", 
            field="Field_B",
            layer="Layer_2",
            purpose="production", 
            well_type="ГС+ГРП", 
            oil_rate=120.0,
            liq_rate=180.0,
            length=2500
        ),
    ]
    
    print(f"Создано {len(wells)} тестовых скважин")
    
    # Настройка параметров
    team_pool = TeamPool()
    team_pool.add_teams(['ГС'], num_teams=2)
    team_pool.add_teams(['грп'], num_teams=2)  # добавлено для поддержки GTM

    capex = BaseCapex(
        build_cost_per_metr={"ГС": 23300, "ГС+ГРП": 25300},
        equipment_cost=2500000,
    )
    
    opex = BaseOpex(
        oil_cost_per_tone=109.9,
        water_cost_per_tone=48.6,
        repair_per_year=3093900,
        maintain_per_year=2336200,
    )
    
    npv = NPV(
        oil_price_per_tone=13896,
        project_start_date=datetime.now(),
        capex_cost=capex,
        opex_cost=opex,
        discount_rate=0.125,
    )
    
    production_profile = LinearProductionProfile()  # исправлено
    
    builder = PlanBuilder(
        start=datetime.now(),
        end=datetime.now() + timedelta(days=365 * 10),
        cost_function=npv,
        production_profile=production_profile,
    )
    
    print("Создание плана разработки...")
    
    # Создание плана
    plan = builder.compile(
        wells,
        manager=TeamManager(team_pool=team_pool),
    )
    
    # Вывод результатов
    print("\n=== РЕЗУЛЬТАТЫ РАСЧЕТА ===")
    print(f"Total Profit (NPV): {plan.total_profit():,.2f} рублей")
    print(f"Total Profit (NPV): {plan.total_profit() / 1e6:.3f} млн рублей")
    print(f"Total Profit (NPV): {plan.total_profit() / 1e9:.3f} млрд рублей")
    print(f"Количество скважин: {len(plan.well_plans)}")
    print(f"Средняя стоимость скважины: {plan.mean_well_cost():,.2f} рублей")
    
    # Детальная информация по скважинам
    print("\n=== ДЕТАЛИ ПО СКВАЖИНАМ ===")
    for i, wp in enumerate(plan.well_plans):
        print(f"Скважина {i+1}: {wp.well.name}")
        print(f"  - Тип: {wp.well.well_type}")
        print(f"  - NPV: {wp.cost:,.2f} рублей" if wp.cost else "  - NPV: не рассчитан")
        print(f"  - Период: {wp.start.strftime('%Y-%m-%d')} - {wp.end.strftime('%Y-%m-%d')}")
        print()

if __name__ == "__main__":
    main() 