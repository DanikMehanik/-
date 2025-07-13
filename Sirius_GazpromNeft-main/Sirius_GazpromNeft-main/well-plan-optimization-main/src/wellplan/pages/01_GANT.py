import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json

# Начальные данные
if "well_data" not in st.session_state:
    st.session_state.well_data = [
        {"id": "w1", "name": "Скважина 1", "start": "2025-05-01", "end": "2025-05-10", "crew": "Бригада A", "fixed": False},
        {"id": "w2", "name": "Скважина 2", "start": "2025-05-05", "end": "2025-05-15", "crew": "Бригада B", "fixed": False},
        {"id": "w3", "name": "Скважина 3", "start": "2025-05-12", "end": "2025-05-20", "crew": "Бригада A", "fixed": False},
    ]

crew_list = sorted(list(set([well["crew"] for well in st.session_state.well_data])))
data = st.session_state.well_data

json_data = json.dumps(data)
json_crews = json.dumps(crew_list)

html_code = f"""
<div id="gantt-container" style="position:relative; width:100%; height:{len(crew_list) * 50}px; border:1px solid #ccc;"></div>
<script>
const data = {json_data};
const crews = {json_crews};
const container = document.getElementById("gantt-container");
const startDate = new Date("2025-05-01");
const dayWidth = 20;
const barHeight = 30;
const barMargin = 10;

function render() {{
    container.innerHTML = '';
    data.forEach((d, i) => {{
        const start = new Date(d.start);
        const end = new Date(d.end);
        const daysFromStart = (start - startDate) / (1000 * 60 * 60 * 24);
        const duration = (end - start) / (1000 * 60 * 60 * 24);
        const x = daysFromStart * dayWidth;
        const y = crews.indexOf(d.crew) * (barHeight + barMargin);

        const bar = document.createElement("div");
        bar.className = "bar";
        bar.style.position = "absolute";
        bar.style.left = x + "px";
        bar.style.top = y + "px";
        bar.style.width = duration * dayWidth + "px";
        bar.style.height = barHeight + "px";
        bar.style.background = d.fixed ? "#888" : "#4CAF50";
        bar.style.border = "1px solid #000";
        bar.style.color = "white";
        bar.style.cursor = d.fixed ? "not-allowed" : "move";
        bar.innerHTML = `<span class="bar-text">${{d.name}}</span>`;
        bar.draggable = !d.fixed;

        bar.addEventListener("dragstart", e => {{
            e.dataTransfer.setData("text/plain", d.id);
            e.dataTransfer.setData("offsetX", e.offsetX);
            e.dataTransfer.setData("offsetY", e.offsetY);
        }});

        bar.addEventListener("dragend", e => {{
            const containerRect = container.getBoundingClientRect();
            const offsetX = parseInt(e.dataTransfer.getData("offsetX"));
            const offsetY = parseInt(e.dataTransfer.getData("offsetY"));
            const newX = e.clientX - containerRect.left - offsetX;
            const newY = e.clientY - containerRect.top - offsetY;

            const newStartDate = new Date(startDate.getTime() + Math.round(newX / dayWidth) * 86400000);
            const newCrewIndex = Math.floor(newY / (barHeight + barMargin));
            const newCrew = crews[Math.max(0, Math.min(newCrewIndex, crews.length - 1))];

            d.start = newStartDate.toISOString().substring(0, 10);
            d.end = new Date(newStartDate.getTime() + duration * 86400000).toISOString().substring(0, 10);
            d.crew = newCrew;

            window.parent.postMessage({ type: 'updateData', data: data }, '*');
            render();
        }});

        container.appendChild(bar);
    }});
}}

render();
</script>
"""

components.html(html_code, height=len(crew_list) * 60 + 100)

st.markdown("### Обновлённые данные")
df = pd.DataFrame(st.session_state.well_data)
st.dataframe(df)

st.markdown("### Зафиксировать/снять фиксацию")
for well in st.session_state.well_data:
    well['fixed'] = st.checkbox(f"{well['name']} ({well['crew']})", value=well['fixed'], key=well['id'])
