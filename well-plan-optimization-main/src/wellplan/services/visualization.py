from io import BytesIO
from typing import Protocol, Optional
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter
from wellplan.core import Plan
import numpy as np

class Visualizer(Protocol):
    def render(self, plan: Plan) -> None:
        pass


class GantVisualizer:
    def __init__(
        self,
        figsize: tuple[float, float] = (30, 8),
        date_format: str = "%m.%Y",
        bar_height: float = 0.7,
        title: str = "Расписание",
        color_map: str = "hsv",
    ):
        self.figsize = figsize
        self.date_format = date_format
        self.bar_height = bar_height
        self.title = title
        self.color_map = color_map

    def render(self, plan: Plan) -> None:
        plt.figure(figsize=self.figsize)
        ax = plt.gca()

        for wp in plan.well_plans:
            for entry in wp.entries:
                ax.barh(
                    y=wp.well.name,
                    width=entry.end - entry.start,
                    left=entry.start,
                    height=self.bar_height,
                    label=entry.task.name,
                    edgecolor="black",
                    linewidth=0.5,
                )

        ax.xaxis.set_major_formatter(DateFormatter(self.date_format))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        plt.title(self.title)
        plt.tight_layout()
        plt.show()

    def _team_names(self, teams):
        
        flot_counter = 1
        brigada_counter = 1

        team_names = []

        for i, team in enumerate(teams, start=1):
            aliases = []
            for task in team.supported_tasks:
                if isinstance(task.aliases, (tuple, list)):
                    aliases.extend(task.aliases) 
                else:
                    aliases.append(task.aliases) 
            if "ГС" in aliases:
                team_name = f"Буровая бригада {brigada_counter}"
                brigada_counter += 1
            elif "ГРП" in aliases:
                team_name = f"Флот ГРП {flot_counter}"
                flot_counter += 1
            else:
                team_name = f"Team {i}"
            
            team_names.append(team_name)
        
        return team_names
    
    def render_by_teams(self, plan: Plan) -> None:
        plt.figure(figsize=self.figsize)
        ax = plt.gca()

        all_clusters = {wp.well.cluster for wp in plan.well_plans}
        cluster_colors = plt.get_cmap(self.color_map)
        num_clusters = len(all_clusters)
        indices = np.linspace(0, 1, num_clusters)
        colors = [cluster_colors(index) for index in indices]
        cluster_color_map = {cluster: colors[i] for i, cluster in enumerate(all_clusters)}

        all_teams = {entry.team for wp in plan.well_plans for entry in wp.entries}
        team_to_index = {team: i for i, team in enumerate(all_teams, start=1)}
        team_names = self._team_names(all_teams)

        for wp in plan.well_plans:
            for entry in wp.entries:
                container = ax.barh(
                    y=team_to_index[entry.team],
                    width=entry.end - entry.start,
                    left=entry.start,
                    height=self.bar_height,
                    color=cluster_color_map.get(wp.well.cluster),
                    edgecolor="black",
                    linewidth=0.5,
                )
                ax.bar_label(container, label_type="center", labels=[wp.well.cluster])

        legend_handles = [
            plt.Rectangle(
                (0, 0), 1, 1, color=cluster_color_map.get(cluster), label=f"{cluster}"
            )
            for cluster in cluster_color_map
        ]
        ax.legend(
            handles=legend_handles,
            title="Куст",
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
            fontsize=8,
        )

        ax.set_yticks(range(1, len(all_teams) + 1))
        ax.set_yticklabels(team_names)

        ax.xaxis.set_major_formatter(DateFormatter(self.date_format))
        ax.set_axisbelow(True)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        plt.title(self.title)
        plt.tight_layout()
        plt.grid()
        plt.show()


class GraphVisualizer:
    def __init__(
        self,
        figsize: tuple[int, int] = (12, 8),
        marker_size: int = 100,
        line_style: str = "--",
        date_format: str = "%m.%Y",
        title: str = "Profit Accumulation Timeline",
    ):
        self.figsize = figsize
        self.marker_size = marker_size
        self.line_style = line_style
        self.date_format = date_format
        self.title = title

    def _process_plan(self, plan: Plan):
        well_data = []
        for well_plan in plan.well_plans:
            entries = well_plan.entries
            if not entries or well_plan.cost is None:
                continue
            completion_date = max(entry.end for entry in entries)
            cost = well_plan.cost
            well_data.append((completion_date, cost, well_plan.well.name))

        well_data.sort(key=lambda x: x[0])

        dates = []
        accumulated = []
        current_total = 0.0
        annotations = []

        for date, cost, name in well_data:
            current_total += cost
            dates.append(date)
            accumulated.append(current_total)
            annotations.append(name)

        return dates, accumulated, annotations

    def render(
        self,
        plan: Plan,
    ) -> None:
        dates, accumulated, annotations = self._process_plan(plan)
        if not dates:
            print("No valid well data to plot.")
            return

        plt.figure(figsize=self.figsize)
        plt.plot(
            dates,
            accumulated,
            self.line_style,
            color="blue",
            alpha=0.5,
        )
        plt.scatter(
            dates,
            accumulated,
            s=self.marker_size,
            edgecolors="black",
            zorder=10,
            color="blue",
        )

        for date, value, name in zip(dates, accumulated, annotations):
            plt.annotate(
                name,
                (date, value),
                textcoords="offset points",
                xytext=(0, 5),
                ha="center",
            )

        plt.gca().xaxis.set_major_formatter(DateFormatter(self.date_format))
        plt.xticks(rotation=45)
        plt.ylabel("Accumulated Profit")
        plt.title(self.title)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def render_multiple(
        self,
        plans: list[Plan],
        labels: Optional[list[str]] = None,
    ) -> None:
        if labels is None:
            labels = [f"Plan {i + 1}" for i in range(len(plans))]
        elif len(labels) != len(plans):
            raise ValueError("Length of labels must match length of plans")

        plt.figure(figsize=self.figsize)
        colors = plt.cm.get_cmap("tab10", len(plans))

        for i, (plan, label) in enumerate(zip(plans, labels)):
            dates, accumulated, annotations = self._process_plan(plan)
            if not dates:
                continue

            color = colors(i)
            plt.plot(
                dates,
                accumulated,
                self.line_style,
                color=color,
                alpha=0.5,
                label=label,
            )
            plt.scatter(
                dates,
                accumulated,
                s=self.marker_size,
                edgecolors="black",
                zorder=10,
                color=color,
            )

            for date, value, name in zip(dates, accumulated, annotations):
                plt.annotate(
                    name,
                    (date, value),
                    textcoords="offset points",
                    xytext=(0, 5),
                    ha="center",
                    color=color,
                )

        plt.gca().xaxis.set_major_formatter(DateFormatter(self.date_format))
        plt.xticks(rotation=45)
        plt.ylabel("Accumulated Profit")
        plt.title(self.title)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()



class CapturePlot:
    def __init__(self):
        self.buffer = BytesIO()

    def __enter__(self):
        self.original_show = plt.show
        def custom_show(*args, **kwargs):
            plt.savefig(self.buffer, format='png')
            plt.close()
        plt.show = custom_show
        return self.buffer

    def __exit__(self, exc_type, exc_val, exc_tb):
        plt.show = self.original_show