# =========================================================
# FLEXIBLE JOB SHOP SCHEDULING PROBLEM (FJSP)
# McDonalds Logistics Production Project
# STREAMLIT VERSION
# =========================================================

import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

# =========================================================
# CONFIGURACIÓN STREAMLIT
# =========================================================

st.set_page_config(
    page_title="FJSP McDonalds",
    layout="wide"
)

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

INSTANCIAS = {
    1: "Instancia 1",
    2: "Instancia 2",
    3: "Instancia 3",
    4: ["Instancia 4", "4 Instancia"],
    5: "Instancia 5",
    7: "Instancia 7"
}

REGLAS = [
    "FIFO",
    "EDD",
    "SPT"
]

ESTACIONES = [
    "Parrilla",
    "Freidora",
    "Bebidas/Postres",
    "Ensamble",
    "Staging/Bolseo"
]

# =========================================================
# COLUMNAS DE TIEMPO
# =========================================================

PROCESS_COLUMNS = {
    "Parrilla": "p Parrilla seg",
    "Freidora": "p Freidora seg",
    "Bebidas/Postres": "p BebidaPostre seg",
    "Ensamble": "p Ensamble seg",
    "Staging/Bolseo": "p Staging seg"
}

REQ_COLUMNS = {
    "Parrilla": "Req Parrilla",
    "Freidora": "Req Freidora",
    "Bebidas/Postres": "Req BebidaPostre",
    "Ensamble": "Req Ensamble",
    "Staging/Bolseo": "Req Staging"
}

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def normalize_yes(value):

    if pd.isna(value):
        return False

    text = str(value).strip().lower()

    return text in [
        "sí",
        "si",
        "s",
        "yes",
        "y",
        "1",
        "true",
        "x"
    ]

# =========================================================
# RECURSO FLEXIBLE
# =========================================================

class FlexibleResource:

    def __init__(self, name, capacity=1):

        self.name = name

        self.capacity = int(capacity)

        self.available_times = [0.0] * self.capacity

        self.history = []

        self.capacity_history = [
            (0.0, self.capacity)
        ]

    # =====================================================
    # ACTUALIZAR CAPACIDAD
    # =====================================================

    def update_capacity(
        self,
        new_capacity,
        event_time
    ):

        new_capacity = max(
            1,
            int(new_capacity)
        )

        event_time = float(event_time)

        if new_capacity > self.capacity:

            extra = new_capacity - self.capacity

            # NUEVOS SERVIDORES DISPONIBLES
            # DESDE EL MOMENTO DEL EVENTO
            self.available_times.extend(
                [event_time] * extra
            )

        elif new_capacity < self.capacity:

            # CONSERVAR LOS SERVIDORES
            # MÁS PRONTO DISPONIBLES
            self.available_times = sorted(
                self.available_times
            )[:new_capacity]

        self.capacity = new_capacity

        self.capacity_history.append(
            (event_time, new_capacity)
        )

    # =====================================================
    # ASIGNAR TRABAJO
    # =====================================================

    def allocate(
        self,
        ready_time,
        duration,
        job_id
    ):

        server = int(
            np.argmin(self.available_times)
        )

        start_time = max(
            ready_time,
            self.available_times[server]
        )

        finish_time = start_time + duration

        self.available_times[server] = finish_time

        self.history.append({

            "Job": job_id,

            "Server": server + 1,

            "Start": start_time,

            "Finish": finish_time,

            "Duration": duration

        })

        return start_time, finish_time

# =========================================================
# LEER CAPACIDADES
# =========================================================

def read_capacities(cap_df, instancia):

    cap_inst = cap_df[
        cap_df["Instancia"] == instancia
    ]

    capacities = {}

    for _, row in cap_inst.iterrows():

        capacities[
            row["Estacion"]
        ] = int(
            row["Capacidad Inicial"]
        )

    return capacities

# =========================================================
# LEER EVENTOS
# =========================================================

def read_events(events_df, instancia):

    ev_inst = events_df[
        events_df["Instancia"] == instancia
    ]

    events = []

    for _, row in ev_inst.iterrows():

        txt = str(
            row["Efecto Cuantitativo"]
        )

        nums = re.findall(
            r"\d+",
            txt
        )

        if len(nums) >= 2:

            events.append({

                "time": float(
                    row["Inicio seg"]
                ),

                "station": row[
                    "Estacion Afectada"
                ],

                "new_capacity": int(
                    nums[-1]
                )

            })

    return sorted(
        events,
        key=lambda x: x["time"]
    )

# =========================================================
# EVENTOS DINÁMICOS
# =========================================================

def apply_events_until(
    current_time,
    events,
    resources,
    applied_events
):

    for idx, ev in enumerate(events):

        if idx in applied_events:
            continue

        if ev["time"] <= current_time:

            station = ev["station"]

            if station in resources:

                resources[
                    station
                ].update_capacity(

                    ev["new_capacity"],

                    ev["time"]

                )

            applied_events.add(idx)

# =========================================================
# CALCULAR TIEMPO TOTAL
# SOLO OPERACIONES REQUERIDAS
# =========================================================

def calculate_total_processing(job):

    total = 0.0

    for station in ESTACIONES:

        req_col = REQ_COLUMNS[station]

        proc_col = PROCESS_COLUMNS[station]

        # STAGING OPCIONAL
        if station == "Staging/Bolseo":

            if req_col in job.index:

                if normalize_yes(job[req_col]):

                    total += float(
                        job[proc_col]
                    )

            else:

                total += float(
                    job[proc_col]
                )

        else:

            if normalize_yes(job[req_col]):

                total += float(
                    job[proc_col]
                )

    return total

# =========================================================
# SELECCIONAR PEDIDO
# =========================================================

def select_job(
    queue_df,
    rule
):

    df = queue_df.copy()

    if len(df) == 1:
        return df.iloc[0]

    if rule == "FIFO":

        df = df.sort_values(
            by=[
                "queue_time",
                "ID Pedido"
            ]
        )

    elif rule == "EDD":

        df = df.sort_values(
            by=[
                "d j seg",
                "queue_time"
            ]
        )

    elif rule == "SPT":

        df["SPT_TIME"] = df.apply(
            processing_time_spt,
            axis=1
        )

        df = df.sort_values(
            by=[
                "SPT_TIME",
                "queue_time"
            ]
        )

    return df.iloc[0]
def schedule_instance(

    instancia,

    instance_df,

    capacities_df,

    events_df,

    rule
):

    jobs = instance_df.copy()

    jobs["r j seg"] = pd.to_numeric(
        jobs["r j seg"],
        errors="coerce"
    )

    jobs["d j seg"] = pd.to_numeric(
        jobs["d j seg"],
        errors="coerce"
    )

    capacities = read_capacities(
        capacities_df,
        instancia
    )

    resources = {

        est: FlexibleResource(

            est,

            capacities.get(est, 1)

        )

        for est in ESTACIONES
    }

    results = []

    jobs["queue_time"] = jobs["r j seg"]

    pending_jobs = jobs.copy()

    while len(pending_jobs) > 0:

        selected = select_job(
            pending_jobs,
            rule
        )

        idx = selected.name

        pending_jobs = pending_jobs.drop(idx)

        job_id = selected["ID Pedido"]

        release = float(
            selected["r j seg"]
        )

        due = float(
            selected["d j seg"]
        )

        operation_finish = []

        row = {

            "ID Pedido": job_id,

            "r_j": release,

            "d_j": due

        }

        # =================================================
        # OPERACIONES PARALELAS
        # =================================================

        for station in [

            "Parrilla",

            "Freidora",

            "Bebidas/Postres"

        ]:

            req_col = REQ_COLUMNS[station]

            proc_col = PROCESS_COLUMNS[station]

            if normalize_yes(
                selected[req_col]
            ):

                duration = float(
                    selected[proc_col]
                )

                start, finish = resources[
                    station
                ].allocate(

                    release,

                    duration,

                    job_id
                )

                operation_finish.append(
                    finish
                )

                row[
                    f"Inicio {station}"
                ] = start

                row[
                    f"Fin {station}"
                ] = finish

        ready_assembly = max(
            operation_finish
        ) if len(
            operation_finish
        ) > 0 else release

        duration_ens = float(
            selected["p Ensamble seg"]
        )

        start_ens, finish_ens = resources[
            "Ensamble"
        ].allocate(

            ready_assembly,

            duration_ens,

            job_id
        )

        row[
            "Inicio Ensamble"
        ] = start_ens

        row[
            "Fin Ensamble"
        ] = finish_ens

        duration_stg = float(
            selected["p Staging seg"]
        )

        start_stg, finish_stg = resources[
            "Staging/Bolseo"
        ].allocate(

            finish_ens,

            duration_stg,

            job_id
        )

        row[
            "Inicio Staging"
        ] = start_stg

        row[
            "Fin Staging"
        ] = finish_stg

        Cj = finish_stg

        Fj = Cj - release

        Tj = max(
            0,
            Cj - due
        )
        Uj = 1 if Tj > 0 else 0

        row["Cj"] = Cj
        row["Fj"] = Fj
        row["Tj"] = Tj
        row["Uj"] = Uj

        results.append(row)

    result_df = pd.DataFrame(
        results
    )

    makespan = result_df[
        "Cj"
    ].max()

    flow_avg = result_df[
        "Fj"
    ].mean()

    tard_avg = result_df[
        "Tj"
    ].mean()

    late_jobs = result_df[
    "Uj"
    ].sum()

    sla = (
        result_df["Tj"] == 0
    ).mean()

    indicators = []

    for st_name, res in resources.items():

        hist = pd.DataFrame(
            res.history
        )

        if len(hist) == 0:
            continue

        busy = hist[
            "Duration"
        ].sum()

        util = busy / (
            makespan *
            res.capacity
        )

        indicators.append({

            "Estacion":
            st_name,

            "Capacidad Final":
            res.capacity,

            "Tiempo Ocupado":
            busy,

            "Tiempo Ocioso":
            makespan *
            res.capacity
            - busy,

            "Utilizacion":
            util,

            "Carga":
            len(hist)

        })

    indicators_df = pd.DataFrame(
        indicators
    )

    bottleneck = indicators_df.sort_values(
        "Utilizacion",
        ascending=False
    ).iloc[0]["Estacion"]

    summary = {

    "Instancia":
    instancia,

    "Regla":
    rule,

    "Makespan":
    makespan,

    "Flujo Promedio":
    flow_avg,

    "Tardanza Promedio":
    tard_avg,

    "Trabajos Tardíos":
    late_jobs,

    "% Cumplimiento SLA":
    sla,

    "Cuello Botella":
    bottleneck

    }

    return (

        result_df,

        summary,

        indicators_df,

        resources

    )

# =========================================================
# GANTT INTERACTIVO
# =========================================================

def create_interactive_gantt(
    resources,
    title
):

    gantt_rows = []

    base_time = pd.Timestamp(
        "2024-01-01"
    )

    for station_name, resource in resources.items():

        hist = pd.DataFrame(
            resource.history
        )

        if len(hist) == 0:
            continue

        for _, row in hist.iterrows():

            gantt_rows.append({

                "Pedido": str(
                    row["Job"]
                ),

                "Recurso":
                f"{station_name} - Servidor {row['Server']}",

                "Inicio":
                base_time + pd.to_timedelta(
                    row["Start"],
                    unit="s"
                ),

                "Fin":
                base_time + pd.to_timedelta(
                    row["Finish"],
                    unit="s"
                ),

                "Duracion":
                row["Duration"],

                "StartSec":
                row["Start"],

                "FinishSec":
                row["Finish"]

            })

    gantt_df = pd.DataFrame(
        gantt_rows
    )

    if len(gantt_df) == 0:
        return None

    fig = px.timeline(

        gantt_df,

        x_start="Inicio",

        x_end="Fin",

        y="Recurso",

        color="Pedido",

        hover_data=[

            "Pedido",

            "Duracion",

            "StartSec",

            "FinishSec"

        ],

        title=title
    )

    fig.update_yaxes(
        autorange="reversed"
    )

    fig.update_layout(

        height=900,

        xaxis_title="Tiempo",

        yaxis_title="Recursos",

        legend_title="Pedido",

        hovermode="closest"
    )

    return fig

# =========================================================
# PROGRAMADOR FJSP
# =========================================================

def processing_time_spt(job):

    p_parrilla = float(job["p Parrilla seg"])
    p_freidora = float(job["p Freidora seg"])
    p_bebidas = float(job["p BebidaPostre seg"])
    p_ensamble = float(job["p Ensamble seg"])
    p_staging = float(job["p Staging seg"])

    return (
        max(
            p_parrilla,
            p_freidora,
            p_bebidas
        )
        + p_ensamble
        + p_staging
    )

# =========================================================
# STREAMLIT UI
# =========================================================

st.title(
    "Flexible Job Shop Scheduling Problem (FJSP)"
)

st.subheader(
    "McDonalds Logistics Production"
)

uploaded_file = st.file_uploader(

    "Cargar archivo Excel",

    type=["xlsx"]

)

if uploaded_file is not None:

    capacities_df = pd.read_excel(

        uploaded_file,

        sheet_name="Capacidades"

    )

    events_df = pd.read_excel(

        uploaded_file,

        sheet_name="Eventos"

    )

    instancia = st.selectbox(

    "Seleccionar Instancia",

    list(INSTANCIAS.keys())

    )

    execution_mode = st.selectbox(

    "Modo de Ejecución",

    [

        "Una heurística",

        "Comparar todas"

    ]

    )

    if execution_mode == "Una heurística":

        rule = st.selectbox(

        "Seleccionar Regla",

        REGLAS

    )

    else:

        rule = None

    if st.button("Ejecutar Modelo"):

    # =================================================
    # MODO UNA HEURISTICA
    # =================================================

        if execution_mode == "Una heurística":

            sheet_name = INSTANCIAS[instancia]

            instance_df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet_name
            )

            result_df, summary, indicators_df, resources = schedule_instance(

                instancia,
                instance_df,
                capacities_df,
                events_df,
                rule

            )

            # =================================================
            # KPIs
            # =================================================

            st.header("KPIs Globales")

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric(
                "Makespan",
                round(summary["Makespan"], 2)
            )

            col2.metric(
                "Flujo Promedio",
                round(summary["Flujo Promedio"], 2)
            )

            col3.metric(
                "Tardanza Promedio",
                round(summary["Tardanza Promedio"], 2)
            )

            col4.metric(
                "Trabajos Tardíos",
                int(summary["Trabajos Tardíos"])
            )

            col5.metric(
                "SLA",
                f"{round(summary['% Cumplimiento SLA'] * 100, 2)} %"
            )

            st.warning(
                f"Cuello de botella detectado: {summary['Cuello Botella']}"
            )

            # =================================================
            # RESULTADOS
            # =================================================

            st.header("Resultados Programación")

            st.dataframe(
                result_df,
                use_container_width=True
            )

            csv = result_df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(

                label="Descargar Resultados CSV",

                data=csv,

                file_name=f"Resultados_I{instancia}_{rule}.csv",

                mime="text/csv"

            )

            # =================================================
            # INDICADORES
            # =================================================

            st.header("Indicadores de Recursos")

            st.dataframe(
                indicators_df,
                use_container_width=True
            )

            fig_util = px.bar(

                indicators_df,

                x="Estacion",

                y="Utilizacion",

                title="Utilización por Estación"

            )

            st.plotly_chart(
                fig_util,
                use_container_width=True
            )

            # =================================================
            # GANTT
            # =================================================

            st.header("Diagrama Gantt Global")

            fig = create_interactive_gantt(

                resources,

                f"Gantt Global - Instancia {instancia} - {rule}"

            )

            if fig is not None:

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

                html = fig.to_html().encode("utf-8")

                st.download_button(

                    label="Descargar Gantt Global",

                    data=html,

                    file_name=f"Gantt_Global_I{instancia}_{rule}.html",

                    mime="text/html"

                )

        # =================================================
        # MODO COMPARAR TODAS
        # =================================================

        else:

            sheet_name = INSTANCIAS[instancia]

            instance_df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet_name
            )

            comparison_results = []

            for current_rule in REGLAS:

                _, summary, _, _ = schedule_instance(

                    instancia,
                    instance_df,
                    capacities_df,
                    events_df,
                    current_rule

                )

                comparison_results.append({

                    "Regla": current_rule,

                    "Makespan":
                    round(summary["Makespan"], 2),

                    "Flujo Promedio":
                    round(summary["Flujo Promedio"], 2),

                    "Tardanza Promedio":
                    round(summary["Tardanza Promedio"], 2),

                    "Trabajos Tardíos":
                    summary["Trabajos Tardíos"],

                    "% SLA":
                    round(
                        summary["% Cumplimiento SLA"] * 100,
                        2
                    ),

                    "Cuello Botella":
                    summary["Cuello Botella"]

                })

            comparison_df = pd.DataFrame(
                comparison_results
            )

            st.header(
                "Comparación de Heurísticas"
            )

            st.dataframe(
                comparison_df,
                use_container_width=True
            )

            best_rule = comparison_df.sort_values(

                by=[
                    "% SLA",
                    "Trabajos Tardíos",
                    "Makespan"
                ],

                ascending=[
                    False,
                    True,
                    True
                ]

            ).iloc[0]

            st.success(
                f"Mejor heurística detectada: {best_rule['Regla']}"
            )

            fig_compare = px.bar(

                comparison_df,

                x="Regla",

                y="% SLA",

                title="Comparación SLA"

            )

            st.plotly_chart(
                fig_compare,
                use_container_width=True
            )