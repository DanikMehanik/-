class DQNAgent(PlanBuilder):
    def __init__(
        self,
        start: datetime,
        end: datetime,
        input_size: int,
        qnetwork_cfg: dict,
        learning_rate: float = 0.001,
        epsilon: float = 0.2,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.05,
        weight_decay: float = None,
        **kwargs
    ):
        # Создаем QNetwork как cost_function
        self.q_network = QNetwork(config=qnetwork_cfg)
        self.npv=qnetwork_cfg["NPV"]
        self.optimizer = optim.AdamW(self.q_network.parameters(), lr=learning_rate, weight_decay = weight_decay)
        
        # Параметры для epsilon-жадной стратегии
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Инициализируем базовый класс
        super().__init__(
            start=start,
            end=end,
            cost_function=self.q_network
        )


    def _select_best_candidate(self, candidates: List[WellPlanContext], keep_order: bool = False) -> WellPlanContext:
        """
        Выбор лучшего кандидата с использованием QNetwork и epsilon-жадной стратегии
        """
        if random.random() < self.epsilon:
            return random.choice(candidates)
        
        
        # Оцениваем каждого кандидата
        best_value = float('-inf')
        best_candidate = np.random.choice(candidates)  # TODO: это исправление бага, если value.item() = Nan
        
        for candidate in candidates:
            # Преобразуем кандидата в тензор
            input_tensor = self.q_network._state_and_action_to_tensor(state=self.plan, action=candidate)
            
            # Получаем оценку от QNetwork
            with torch.no_grad():
                value = self.q_network(input_tensor)
            
            if value.item() > best_value:
                best_value = value.item()
                best_candidate = candidate
        # print("random assignment")
        # print(f"{value.item()=}; {best_candidate=}; {best_value=}")
        # print(f"N candidates: {len(candidates)}")
        # print(f"BEST: {best_candidate};")
        # print(f"WELL: {best_candidate.well=}")
        return best_candidate

    def compile(
        self,
        wells: List[Well],
        manager: BaseTeamManager,
        risk_strategy: Optional[RiskStrategy] = None,
        keep_order: bool = False,
    ) -> Plan:
        """
        Генерация плана с обучением QNetwork
        """
        self.plan = Plan()
        self.remaining_wells = wells.copy()
        current_start = self.start

        while self.remaining_wells and current_start < self.end:
            # Получаем кандидатов
            candidates = self._build_contexts(manager, current_start)  # 2050 (self.end у всех)
            # print(f"oil_prod_profiles per candidate :{[candidate.oil_prod_profile for candidate in candidates]=}")  # TODO: пустые oil_prod_profile
            # print(f".compile: {[c.end for c in candidates]}") 
            if not candidates:
                break

            # Фильтруем кандидатов и вычисляем их стоимость
            if risk_strategy:
                candidates = [risk_strategy.apply_risk(c) for c in candidates]
            
            # Вычисляем стоимость для каждого кандидата
            candidates = [self.cost_function.compute(state=self.plan, action=c) for c in candidates]  # Qnetwork
            # costs = [candidate.cost for candidate in candidates]
            # candidate.npv

            # TODO: костыль для расчёта NPV; после возвращаем 
            for candidate in candidates:
                print('------------')
                q_cost = candidate.cost
                print(f"QCOST: {q_cost}")
                self.npv.compute(candidate)
                print(f"NPV: {candidate.cost}")
                npv_value = candidate.cost
                candidate.npv_value = npv_value
                print(f"NPV: {candidate.npv_value}")
                candidate.cost = q_cost  # вернули q_cost как cost
                print(f"QCOST: {candidate.cost}")
                print(f"NPV: {candidate.npv_value}")
                print(f"candidate.cost: {candidate.cost}")
                print('------------')

            

            # Фильтруем по ограничениям
            candidates = [
                c for c in candidates if not self._constraints.is_violated(self.plan, c)
            ]
            
            if not candidates:
                current_start = self._constraints.get_period_end(current_start) or self.end
                continue

            # Выбираем лучшего кандидата
            best_candidate = self._select_best_candidate(candidates, keep_order)
            print(f"{best_candidate.cost=}")
            
            
            # После выбора действия обучаем QNetwork
            if best_candidate is None:
                print(f"{best_candidate=}; {len(candidates)=}")
            print(f"before self.q_network.update {best_candidate.cost=}")
            self.q_network.update(state=self.plan, action=best_candidate)
            print(f"after self.q_network.update {best_candidate.cost=}")
            
            # Уменьшаем epsilon
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay  
            
            # Добавляем в план
            manager.assign(best_candidate)
            # print(f"remaining_wells ДО УДАЛЕНИНИЯ ({len(self.remaining_wells)})")
            self.remaining_wells.remove(best_candidate.well)
            # print(f"ДО add_context: {len(self.plan.well_plans)}; {self.plan.id}")
            self.plan.add_context(best_candidate)
            print(f"{best_candidate.cost=}")
            # print(f"ПОСЛЕ add_context: {len(self.plan.well_plans)}; {self.plan.id}")
            # print(f"remaining_wells ({len(self.remaining_wells)}): {self.remaining_wells}")
            

            # Обновляем время
            # current_start = best_candidate.end
            # print(f"clause 1: {self.remaining_wells}")
            # print(f"clause 2: {current_start < self.end} ({current_start=}); ({self.end=})")
            # print(f"compile: {self.remaining_wells=}") 
            # print(f"compile: {current_start < self.end=};\n({current_start=}; {self.end=})")

        return self.plan


class EarlyStopping:
    def __init__(self, patience=5, min_delta=0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.best_score = None
        self.counter = 0
        self.should_stop = False

    def step(self, current_score):
        if self.best_score is None or current_score > self.best_score + self.min_delta:
            self.best_score = current_score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True

