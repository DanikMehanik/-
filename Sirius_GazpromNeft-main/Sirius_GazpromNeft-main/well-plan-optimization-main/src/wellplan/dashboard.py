from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
from wellplan.core import TeamPool, Plan
from wellplan.services import (
    TeamManager,
    FileProductionProfile,
    NPV,
    BaseCapex,
    BaseOpex,
    ClusterRandomRiskStrategy,
    DistanceTeamMovement,
    SimpleTeamMovement,
    OilConstraint,
    CapexConstraint,
)
from dateutil.relativedelta import relativedelta
from wellplan.data.file.loader import ExcelWellLoader
from wellplan.data.file.saver import ExcelPlanSaver
from wellplan.builder import PlanBuilder
from wellplan.services.visualization import CapturePlot, GantVisualizer
import plotly.graph_objects as go

cache_profile_folder = Path(".cache_profiles")

cache_profile_folder.mkdir(parents=True, exist_ok=True)


def create_stacked_plot(df_monthly, title):
    months = df_monthly.columns.strftime('%Y-%m')
    base = df_monthly.loc["Добыча нефти база, тыс.т."]
    gtm = df_monthly.loc["Добыча нефти ВНС, тыс.т."]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=months,
            y=base,
            name="База",
            stackgroup="one",
            fill="tozeroy",
            mode="lines",
            line=dict(width=0.5, color="#1f77b4"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=months,
            y=gtm,
            name="ВНС",
            stackgroup="one",
            fill="tonexty",
            mode="lines",
            line=dict(width=0.5, color="#ff7f0e"),
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Месяц",
        yaxis_title="Добыча нефти, тыс.т.",
        hovermode="x unified",
        showlegend=True,
        plot_bgcolor="white",
        xaxis=dict(tickangle=-45)
    )

    return fig


def format_plan(
    plan: Plan,
    plan_name: str = "Бизнес-План",
    add_constraints: bool = False,
):
    yearly_date_range = pd.date_range(
        plan.start_date,
        end=plan.end_date,
        freq="YE",
    )
    yearly_columns = yearly_date_range.year

    df = pd.DataFrame(
        columns=yearly_columns,
        index=[
            "Добыча нефти, тыс.т.",
            "Добыча нефти база, тыс.т.",
            "Добыча нефти ВНС, тыс.т.",
        ],
        dtype=float
    )
    df.index.name = "Показатели"

    vns_df = pd.DataFrame(
        columns=yearly_columns,
        index=[
            "ВНС, шт",
            "ВНС, доб.нефти, тыс.т.",
            "Ср.дебит, т/сут",
            "CAPEX ВНС, млн.руб.",
        ],
        dtype=float
    )

    capex_vns_yearly_dict = plan.get_capex_per_year()
    base_yearly_dict = plan.get_oil_production_per_year_for_existing_wells()
    new_yearly_dict = plan.get_oil_production_per_year_for_new_wells()
    vns_wells_yearly_dict = plan.get_well_start_per_year()

    capex_vns = pd.Series(capex_vns_yearly_dict, index=yearly_columns).fillna(0) / 1e6
    base_yearly = pd.Series(base_yearly_dict, index=yearly_columns).fillna(0) / 1e3
    new_yearly = pd.Series(new_yearly_dict, index=yearly_columns).fillna(0) / 1e3
    vns_wells_yearly = pd.Series(vns_wells_yearly_dict, index=yearly_columns).fillna(0).astype(int)

    df.loc["Добыча нефти база, тыс.т."] = base_yearly
    df.loc["Добыча нефти ВНС, тыс.т."] = new_yearly
    df.loc["Добыча нефти, тыс.т."] = df.loc["Добыча нефти база, тыс.т."].add(df.loc["Добыча нефти ВНС, тыс.т."], fill_value=0)


    if 'constraints' in st.session_state and st.session_state.constraints and add_constraints:
        for constraint in st.session_state.constraints:
            data = {bound.year: bound.value for bound in constraint.bounds if bound.year}
            constraint_series = pd.Series(data)

            if isinstance(constraint, CapexConstraint):
                 df.loc["Ограничение CAPEX, млн.руб."] = constraint_series.reindex(yearly_columns) / 1e6
            if isinstance(constraint, OilConstraint):
                 df.loc["Ограничение по добычи нефти, тыс.т."] = constraint_series.reindex(yearly_columns) / 1e3


    df["Итог"] = df.sum(axis=1)
    
    vns_df.loc["ВНС, шт", :] = vns_wells_yearly
    vns_df.loc["ВНС, доб.нефти, тыс.т.", :] = new_yearly
    
    avg_debit_yearly = (new_yearly * 1e3 / 365).divide(vns_wells_yearly, fill_value=0).fillna(0)
    vns_df.loc["Ср.дебит, т/сут", :] = avg_debit_yearly
    vns_df.loc["CAPEX ВНС, млн.руб.", :] = capex_vns

    
    try:
        
        all_monthly_prod = plan.get_oil_production_per_month()
        if not all_monthly_prod:
             
             min_month = datetime(plan.start_date.year, plan.start_date.month, 1)
             max_month = datetime(plan.end_date.year, plan.end_date.month, 1)
        else:
             min_month = min(all_monthly_prod.keys())
             max_month = max(all_monthly_prod.keys())
    except Exception: 
         min_month = datetime(plan.start_date.year, plan.start_date.month, 1)
         max_month = datetime(plan.end_date.year, plan.end_date.month, 1)


    monthly_date_range = pd.date_range(
        min_month,
        end=max_month,
        freq="MS", 
    )

    monthly_df = pd.DataFrame(
        columns=monthly_date_range,
        index=[
            "Добыча нефти, тыс.т.",
            "Добыча нефти база, тыс.т.",
            "Добыча нефти ВНС, тыс.т.",
        ],
        dtype=float
    )

    
    base_monthly_dict = plan.get_oil_production_per_month_for_existing_wells()
    new_monthly_dict = plan.get_oil_production_per_month_for_new_wells()

    
    base_monthly = pd.Series(base_monthly_dict, index=monthly_date_range).fillna(0) / 1e3
    new_monthly = pd.Series(new_monthly_dict, index=monthly_date_range).fillna(0) / 1e3


    monthly_df.loc["Добыча нефти база, тыс.т."] = base_monthly
    monthly_df.loc["Добыча нефти ВНС, тыс.т."] = new_monthly
    monthly_df.loc["Добыча нефти, тыс.т."] = monthly_df.loc["Добыча нефти база, тыс.т."].add(monthly_df.loc["Добыча нефти ВНС, тыс.т."], fill_value=0)


    st.dataframe(df.fillna(0).style.format("{:,.2f}"))
    st.dataframe(vns_df.fillna(0).style.format("{:,.2f}"))
    st.plotly_chart(create_stacked_plot(monthly_df.fillna(0), plan_name), use_container_width=True)


def add_constraint_ui(constraint_name: str, unit: str = ""):
    if f"{constraint_name}_pairs" not in st.session_state:
        st.session_state[f"{constraint_name}_pairs"] = [
            {"year": datetime.now().year, "value": 0.0}
        ]

    pairs = st.session_state[f"{constraint_name}_pairs"]

    for i, pair in enumerate(pairs):
        cols = st.columns([1, 1, 0.5], vertical_alignment='bottom')
        with cols[0]:
            current_year = pair["year"] if "year" in pair else datetime.now().year
            year = st.number_input(
                "Год",
                min_value=2000,
                max_value=2100,
                value=current_year,
                key=f"{constraint_name}_year_{i}",

            )
        with cols[1]:
            new_value = st.number_input(
                "Значение" + ", " + unit,
                value=pair["value"],
                key=f"{constraint_name}_value_{i}",
            )
        with cols[2]:
            if st.button(
                "✖",
                key=f"{constraint_name}_delete_{i}",
            ):
                pairs.pop(i)
                st.rerun()

        pairs[i] = {
            "year": year,
            "value": new_value,
        }

    if st.button(
        f"➕ Добавить значение для {constraint_name}",
        use_container_width=True,
        type="tertiary",
    ):
        pairs.append({"year": datetime.now().year, "value": 0.0})
        st.rerun()

    return pairs


if "settings" not in st.session_state:
    st.session_state.settings = {}
    st.session_state.plan = None
    st.session_state.base_plan = None
    st.session_state.image = None
    st.session_state.excel = None
    st.session_state.available_clusters = []
    st.session_state.available_wells = []
    st.session_state.cluster_commissioning_dates = []
    st.session_state.dependency_well = None
    st.session_state.dependency_cluster = None
    st.session_state.constraints = []



st.set_page_config(layout="wide", page_title="Бизнес планирование")
st.title("Бизнес планирование")

st.sidebar.header("Настройки")

with st.sidebar.expander("📅 План", expanded=True):
    st.session_state.settings["start_date"] = datetime.combine(
        st.date_input("Начало плана"), datetime.min.time()
    )
    st.session_state.settings["plan_duration"] = st.number_input(
        "Длительность плана в годах (включая год начала плана)", 1, 25, 5, step=1
    )

with st.sidebar.expander("📁 Файлы с данными по скважинам", expanded=True):
    st.session_state.settings["wells_file"] = st.file_uploader(
        "Файл с данными о вводе скважин",
        type="xlsx",
    )
    wells_file =st.session_state.settings["wells_file"]

    if wells_file is not None and wells_file != st.session_state.get("processed_wells_file", None):
        loader = ExcelWellLoader(file_path=wells_file)
        wells = loader.load()
        clusters = sorted(list(set(well.cluster for well in wells if hasattr(well, 'cluster') and well.cluster)))
        well_names = sorted(list(set(well.name for well in wells if hasattr(well, 'name') and well.name)))
        st.session_state.available_clusters = clusters
        st.session_state.available_wells = well_names
        st.session_state.processed_wells_file = wells_file 

    st.session_state.settings["coordinates_file"] = st.file_uploader(
        "Файл с координатами скважин (Опционально)",
        type=["xlsx", "xlsm"],
    )
    st.session_state.settings["production_profiles"] = st.file_uploader(
        "Файлы с профилями добычи по скважинам (Опционально)",
        accept_multiple_files=True,
        type=["xlsx", "xlsm"],
    )

    with st.popover("Список файлов в кеше", use_container_width=True):
        files = [file.name for file in cache_profile_folder.iterdir() if file.is_file()]
        for file in files:
            st.write(file)


    if st.button(
        "Очистить кеш профилей добычи",
        use_container_width=True,
        type="secondary",
        help="Очистит каталог, в котором хранятся все загруженные ранее файлы.",
    ):
        for file_path in cache_profile_folder.iterdir():
            try:
                if file_path.is_file():
                    file_path.unlink()
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")


with st.sidebar.expander("👷 Бригады", expanded=False):
    st.subheader("Буровые бригады")
    st.session_state.settings["drilling_teams"] = st.number_input(
        "Количество буровых бригад", 1, 100, 1, key="drilling_teams_input"
    )
    
    drilling_data = {
        "Бригада": [f"Бригада {i+1}" for i in range(st.session_state.settings["drilling_teams"])],
        "Грузоподъемность, т": [0.0] * st.session_state.settings["drilling_teams"]
    }
    

    if "drilling_teams_data" not in st.session_state:
        st.session_state.drilling_teams_data = drilling_data
    else:
        if len(st.session_state.drilling_teams_data["Бригада"]) != st.session_state.settings["drilling_teams"]:
            st.session_state.drilling_teams_data = drilling_data
    
    st.session_state.settings["drilling_teams_capacity"] = st.data_editor(
        st.session_state.drilling_teams_data,
        key="drilling_teams_editor"
    )
    
    st.subheader("Флоты")
    st.session_state.settings["gtm_teams"] = st.number_input(
        "Количество флотов", 1, 100, 1, key="gtm_teams_input"
    )
    
    gtm_data = {
        "Флот": [f"Флот {i+1}" for i in range(st.session_state.settings["gtm_teams"])],
        "Грузоподъемность, т": [0.0] * st.session_state.settings["gtm_teams"]
    }
    
    if "gtm_teams_data" not in st.session_state:
        st.session_state.gtm_teams_data = gtm_data
    else:
        if len(st.session_state.gtm_teams_data["Флот"]) != st.session_state.settings["gtm_teams"]:
            st.session_state.gtm_teams_data = gtm_data
    
    st.session_state.settings["gtm_teams_capacity"] = st.data_editor(
        st.session_state.gtm_teams_data,
        key="gtm_teams_editor"
    )


with st.sidebar.expander("💰 Затраты", expanded=False):
    st.session_state.settings["oil_cost_per_tone"] = st.number_input(
        "Стоимость добычи тонны нефти, руб", value=109.9
    )
    st.session_state.settings["water_cost_per_tone"] = st.number_input(
        "Стоимость добычи тонны воды, руб", value=48.6
    )
    st.session_state.settings["repair_per_year"] = st.number_input(
        "Стоимость ремонтов в год, руб", value=3093900
    )
    st.session_state.settings["maintain_per_year"] = st.number_input(
        "Стоимость обслуживания в год, руб", value=2336200
    )
    st.session_state.settings["oil_price_per_tone"] = st.number_input(
        "Стоимость тонны нефти, руб", value=13896
    )
    st.session_state.settings["discount_rate"] = st.number_input(
        "Индекс дисконтирования",
        value=0.125,
        step=0.001,
        format="%.3f",
    )
    st.session_state.settings["equipment_cost"] = st.number_input(
        "Стоимость скважинного оборудования, руб",
        value=2500000,
    )

with st.sidebar.expander("🚫 Ограничения"):

    capex_pairs = add_constraint_ui("ограничения по CAPEX", "руб")
    oil_pairs = add_constraint_ui("ограничения по добыче нефти", "т")


    st.subheader("Ограничения по дате ввода кустов скважин")

    if not st.session_state.available_clusters:
        st.warning("Загрузите данные о вводе для выбора кустов")
    else:
        if "cluster_commissioning_dates" not in st.session_state:
            st.session_state.cluster_commissioning_dates = []

        dates_list = st.session_state.cluster_commissioning_dates
        indices_to_remove_dates = []

        for i, entry in enumerate(dates_list):
            cols = st.columns([2, 1, 0.5], vertical_alignment='bottom')
            with cols[0]:
                current_cluster_options = st.session_state.available_clusters
                cluster_index = 0
                if entry["cluster"] in current_cluster_options:
                    cluster_index = current_cluster_options.index(entry["cluster"])

                selected_cluster = st.selectbox(
                    "Куст",
                    options=current_cluster_options,
                    index=cluster_index,
                    key=f"cluster_select_{i}",
                    placeholder="Выберите куст",
                )
            with cols[1]:
                selected_date = st.date_input(
                    "Дата ввода",
                    value=entry["date"],
                    key=f"cluster_date_{i}",
                )
            with cols[2]:
                if st.button("✖", key=f"cluster_delete_{i}", help="Удалить"):
                    indices_to_remove_dates.append(i)

            dates_list[i] = {"cluster": selected_cluster, "date": selected_date}

        if indices_to_remove_dates:
            st.session_state.cluster_commissioning_dates = [
                item for idx, item in enumerate(dates_list) if idx not in indices_to_remove_dates
            ]
            st.rerun()

        if st.button(
            "➕ Добавить дату ввода куста",
            use_container_width=True,
            type="tertiary",
            key="add_cluster_date"
        ):

            default_cluster = st.session_state.available_clusters[0] if st.session_state.available_clusters else None
            if default_cluster: 
                st.session_state.cluster_commissioning_dates.append(
                    {"cluster": default_cluster, "date": datetime.now().date()}
                )
                st.rerun()
            else:
                st.warning("Отсутствуют кусты для выбора")


    st.subheader("Зависимости от кустов")

    if not st.session_state.available_wells or not st.session_state.available_clusters:
        st.warning("Загрузите данные о вводе для выбора зависимостей")
    else:
        if "well_cluster_dependencies" not in st.session_state:
            st.session_state.well_cluster_dependencies = []

        dependencies_list = st.session_state.well_cluster_dependencies
        indices_to_remove_deps = []

        well_options = st.session_state.available_wells
        cluster_options = st.session_state.available_clusters

        for i, entry in enumerate(dependencies_list):
            cols = st.columns([2, 2, 0.5], vertical_alignment='bottom')
            with cols[0]:
                well_index = 0
                if entry["well"] in well_options:
                    well_index = well_options.index(entry["well"])
                selected_well = st.selectbox(
                    "Скважина",
                    options=well_options,
                    index=well_index,
                    key=f"dependency_well_select_{i}",
                    placeholder='Выберите скважину',
                )
            with cols[1]:
                cluster_index = 0
                if entry["cluster"] in cluster_options:
                    cluster_index = cluster_options.index(entry["cluster"])
                selected_cluster_dep = st.selectbox(
                    "Куст",
                    options=cluster_options,
                    index=cluster_index,
                    key=f"dependency_cluster_select_{i}",
                    placeholder='Выберите куст',
                )
            with cols[2]:
                if st.button("✖", key=f"dependency_delete_{i}", help="Удалить зависимость"):
                    indices_to_remove_deps.append(i)

            dependencies_list[i] = {"well": selected_well, "cluster": selected_cluster_dep}


        if indices_to_remove_deps:
            st.session_state.well_cluster_dependencies = [
                item for idx, item in enumerate(dependencies_list) if idx not in indices_to_remove_deps
            ]
            st.rerun()

        if st.button(
            "➕ Добавить зависимость",
            use_container_width=True,
            type="tertiary",
            key="add_dependency"
        ):
            # Add a new default entry
            default_well = well_options[0] if well_options else None
            default_cluster = cluster_options[0] if cluster_options else None
            if default_well and default_cluster: # Only add if options are available
                st.session_state.well_cluster_dependencies.append(
                    {"well": default_well, "cluster": default_cluster}
                )
                st.rerun()
            else:
                st.warning("Отсутствуют кусты и скважины для выбора")

    if st.button(
        "Сохранить ограничения",
        key="save_constraints",
        type="secondary",
        use_container_width=True,
    ):
        st.session_state.constraints = []
        if oil_pairs:
            st.session_state.constraints.append(OilConstraint(oil_pairs))
        if capex_pairs:
            st.session_state.constraints.append(CapexConstraint(capex_pairs))
        st.success("Ограничения сохранены!")

    st.divider()
    st.subheader("Текущие ограничения")
    table_data = []
    for constraint in st.session_state.constraints:
        for bound in constraint.bounds:
            table_data.append(
                {
                    "Тип ограничения": "CAPEX"
                    if isinstance(constraint, CapexConstraint)
                    else "Добыча нефти",
                    "Год": bound.year,
                    "Значение": f"{bound.value:,.0f}".replace(",", " "),
                }
            )

    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )


if st.sidebar.button("Расчет", use_container_width=True, type="primary"):
    import time
    settings = st.session_state.settings
    if settings["wells_file"]:
        loader = ExcelWellLoader(
            file_path=settings["wells_file"],
        )
        wells = loader.load()
        if settings["production_profiles"]:
            for uploaded_file in settings["production_profiles"]:
                file_path = cache_profile_folder / uploaded_file.name

                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())

            st.success(f"Файлы сохранены в кеш")

        with st.spinner("Загрузка профилей добычи началась...", show_time=True):
            production_profile = FileProductionProfile(
                folder_path=cache_profile_folder,
            )

        if settings["coordinates_file"]:
            coordinates = pd.read_excel(
                settings["coordinates_file"],
                header=0,
                names=["cluster", "x", "y", "z"],
            )
            movement = DistanceTeamMovement.from_dicts(
                coordinates.to_dict(orient="records")
            )
        else:
            movement = SimpleTeamMovement()
            st.info(
                "Координаты скважин не предоставлены. Будут использованы дефолтные значения"
            )

        team_pool = TeamPool()
        team_pool.add_teams(
            ["ГС"],
            num_teams=settings["drilling_teams"],
        )
        team_pool.add_teams(["грп"], num_teams=settings["gtm_teams"])

        capex = BaseCapex(
            build_cost_per_metr={
                "ГС+ГРП": 25300,
                "ННС+ГРП": 12900,
                "МЗС": 27300,
                "МЗС+ГРП": 28300,
                "ГС": 23300,
            },
            equipment_cost=settings["equipment_cost"],
        )
        opex = BaseOpex(
            oil_cost_per_tone=settings["oil_cost_per_tone"],
            water_cost_per_tone=settings["water_cost_per_tone"],
            repair_per_year=settings["repair_per_year"],
            maintain_per_year=settings["maintain_per_year"],
        )
        npv = NPV(
            oil_price_per_tone=settings["oil_price_per_tone"],
            project_start_date=settings["start_date"],
            capex_cost=capex,
            opex_cost=opex,
            discount_rate=settings["discount_rate"],
        )
        base_builder = PlanBuilder(
            start=settings["start_date"],
            end=(
                settings["start_date"].replace(month=12, day=31)
                + relativedelta(years=settings["plan_duration"] - 1)
            ),
            cost_function=npv,
            production_profile=production_profile,
        )
        builder = PlanBuilder(
            start=settings["start_date"],
            end=(
                settings["start_date"].replace(month=12, day=31)
                + relativedelta(years=settings["plan_duration"] - 1)
            ),
            cost_function=npv,
            production_profile=production_profile,
            constraints=st.session_state.constraints,
        )
        start_time = time.perf_counter()
        st.session_state.plan = builder.compile(
            wells,
            manager=TeamManager(
                team_pool=team_pool,
                movement=movement,
            ),
            risk_strategy=ClusterRandomRiskStrategy(trigger_chance=0.0),
        )
        elapsed_time = time.perf_counter() - start_time
        iterations = 100
        npv_value = st.session_state.plan.total_profit() if st.session_state.plan else None

        base_start_time = time.perf_counter()
        st.session_state.base_plan = base_builder.compile(
            wells,
            manager=TeamManager(
                team_pool=team_pool,
                movement=movement,
            ),
            risk_strategy=ClusterRandomRiskStrategy(trigger_chance=0.0),
            keep_order=True,
        )
        base_elapsed_time = time.perf_counter() - base_start_time
        
        viz = GantVisualizer(figsize=(30, 5))
        with CapturePlot() as buf:
            viz.render_by_teams(st.session_state.plan)
        buf.seek(0)

        st.session_state.image = buf
        saver = ExcelPlanSaver("dummy_path.xlsx")
        st.session_state.excel = saver.get_excel_bytes(st.session_state.plan)

        import pandas as pd
        results_df = pd.DataFrame([
            {"NPV": npv_value, "Итерации": iterations, "Время (сек)": base_elapsed_time}
        ])
        st.subheader("Результаты оптимизации")
        st.dataframe(results_df, use_container_width=True)

    else:
        st.error("Пожалуйста загрузите файл с данными по вводу скважин")


if st.session_state.plan:
    base_plan = st.session_state.base_plan
    plan = st.session_state.plan
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Базовый план (пирог)", divider="gray")
        format_plan(base_plan)

    with col2:
        st.subheader("Корректировка программы", divider="gray")
        format_plan(plan, "Бизнес-План Адаптированный", add_constraints=True)

        st.download_button(
            label="Скачать план",
            data=st.session_state.excel,
            file_name=f"plan_{plan.id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
        label="Скачать диаграмму",
        data=st.session_state.image,
        file_name=f"Диаграмма_{plan.id}.png",
        mime="image/png"
    )