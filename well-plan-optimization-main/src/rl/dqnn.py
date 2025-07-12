# Нейронка, используемая как Q-функция, костфункция для оценивания действия (кандидата-скважины)
class QNetwork(nn.Module, CostFunction):
    def __init__(self, 
        config,
        input_size = 5, 
        # tau = 0.99,  # как много задела делаем на след шаг (одношаговый подход)
    ):
        super(QNetwork, self).__init__()
        """Архитектура Q-сетки"""
        self.config = config
        self.input_size = input_size
        self.NPV = config["NPV"]

        layers = []
        input_size += self.config["water_cut"] + self.config["interaction_rate_length"]\
            + self.config["start_day"] + self.config["profit_per_well"] + self.config["log_profit"]\
            + self.config.get("use_time_features", False) * 2 + self.config["use_purpose"]
        in_dim = input_size
        activation_fn =  self.config["activation_fn"]

        for hidden_dim in self.config["hidden_layers"]:
            layers.append(nn.Linear(in_dim, hidden_dim))
            # if self.config.use_batchnorm:
                # layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(activation_fn())
            if self.config["dropout_rate"] > 0.0:
                layers.append(nn.Dropout(self.config["dropout_rate"]))
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, 1))
        self.model = nn.Sequential(*layers)

        # Разделение state и action encoderов
        # if self.config.get("use_separate_encoders", False):  # Улучшение 2
        #     self.state_encoder = nn.Sequential(
        #         nn.Linear(self.config["state_dim"], 64),
        #         activation_fn(),
        #     )
        #     self.action_encoder = nn.Sequential(
        #         nn.Linear(self.config["action_dim"], 64),
        #         activation_fn(),
        #     )
        #     self.merged = nn.Sequential(
        #         nn.Linear(128, 64),
        #         activation_fn(),
        #         nn.Linear(64, 1),
        #     )

        # Инициализация весов
        if self.config.get("weight_init_method", False):  # Улучшение 1
            self.model.apply(lambda m: init_weights(m, method=self.config["weight_init_method"]))


        # self.tau = tau
        
        loss_fn =  self.config["loss_fn"]
        if self.config["optimizer"]:
            self.optimizer = self.config["optimizer"](self.parameters(), lr=self.config["learning_rate"]) 
        else:
            self.optimizer = optim.AdamW(self.parameters(), lr=self.config["learning_rate"], weight_decay = self.config.get("weight_decay"))
        self.criterion = loss_fn()
        # self.gamma = gamma  # Коэффициент дисконтирования  # не реализовано

    def forward(self, x):
        x = self.model(x)
        return x

    def compute(self, state: Plan, action: WellPlanContext) -> WellPlanContext:
        """Оценка стоимости действия (контекста) при текущем состоянии state"""
        x = self._state_and_action_to_tensor(state = state, action = action)
        x = x.unsqueeze(0)
        
        print(f"before forward {action.cost}")
        with torch.no_grad():          
            cost = self.forward(x)
        action.cost = cost.item()  # обновление коста - перезатирка
        print(f"after forward {action.cost}")
        return action

    def _state_and_action_to_tensor(self, state: Plan, action: WellPlanContext) -> torch.Tensor:
        """Векторизация фичей для агента, для оценки действия action, при текущем состоянии state"""
        
        features = [
            action.well.oil_rate,
            action.well.liq_rate,
            action.well.length,
            # len(action.entries),
            # action.start.timestamp() / 86400,
            # state
        ]

        # Engineered features
        if self.config["water_cut"]:
            water_cut = action.well.oil_rate / (action.well.liq_rate + 1e-8)
            features.append(water_cut)

        if self.config["interaction_rate_length"]:
            features.append(action.well.oil_rate * action.well.length)

        if self.config["start_day"]:
            features.append(action.start.timestamp() / 86400)

        # State-based features
        features += [len(state.well_plans), state.total_npv(self.NPV)]
        if self.config["profit_per_well"]:
            features.append(state.total_npv(self.NPV) / (len(state.well_plans) + 1e-6))

        if self.config["log_profit"]:
            features.append(np.log1p(state.total_npv(self.NPV)))

        if self.config.get("use_time_features", False):
            day = action.start.timetuple().tm_yday
            features += [
                math.sin(2 * math.pi * day / 365),
                math.cos(2 * math.pi * day / 365),
            ]

        if self.config["use_purpose"]:
            purpose = action.well.purpose
            feature = 1 if purpose == "Добывающая" else 0
            features.append(feature)
        return torch.FloatTensor(features)

    def update(self, state: Plan, action: WellPlanContext) -> None:
        """Действие, Обучение Q-сети, настройка весов на награде за этой действие"""
        # 1. Преобразуем входные данные в тензоры
        # print(f"update: {state=}")
        state_tensor = self._state_and_action_to_tensor(state=state, action=action).unsqueeze(0)
        
        # 2. Вычисляем награду (убедитесь, что total_npv() возвращает float)
        prev_npv = state.total_npv(self.NPV)
        new_state = copy.deepcopy(state)
        # print(f"update: {new_state=}")
        new_state.add_context(action)
        # print(f"{new_state.total_npv(self.NPV)=}")
        reward = new_state.total_npv(self.NPV) - prev_npv
        
        # 3. Преобразуем reward в тензор с правильной размерностью
        # if self.config["reward_smoothing_alpha"]:
        #     # 2 
        #     alpha = self.config["reward_smoothing_alpha"]
        #     if not hasattr(self, "_smoothed_reward"):
        #         self._smoothed_reward = reward
        #     reward = (1 - alpha) * self._smoothed_reward + alpha * reward
        # if self.config["reward_tahn_norm"]:
        #     reward = np.tanh(reward / self.config["reward_tahn_norm"])
        reward_tensor = torch.tensor([[reward]], dtype=torch.float32)
        
        # 4. Получаем Q-значение для текущего состояния и действия
        q_value = self.forward(state_tensor)  # Размерность: [1, 1]
        
        # 5. Вычисляем loss (теперь оба параметра - тензоры)
        loss = self.criterion(q_value, reward_tensor)  # Добавляем размерность
        
        # 6. Оптимизация
        self.optimizer.zero_grad()
        loss.backward()
        if self.config["gradient_clipping"]:
            torch.nn.utils.clip_grad_norm_(self.parameters(), self.config["gradient_clipping"])
        self.optimizer.step()