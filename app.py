# app.py
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import json
from collections import defaultdict

# === Festività italiane 2025 ===
festivita = {
    "01/01", "06/01", "31/03", "01/04", "25/04", "01/05", "02/06",
    "15/08", "01/11", "08/12", "25/12", "26/12"
}

# === Funzioni calendario ===
def giorno_lavorativo(data):
    return data.weekday() < 5 and data.strftime("%d/%m") not in festivita

def prossimo_lavorativo(data):
    while not giorno_lavorativo(data):
        data += timedelta(days=1)
    return data

def aggiungi_lavorativi(inizio, giorni):
    count = 0
    corrente = inizio
    while count < giorni:
        if giorno_lavorativo(corrente):
            count += 1
            if count == giorni:
                return corrente
        corrente += timedelta(days=1)
    return corrente

def risolvi_sovrapposizioni(commesse):
    risorse = defaultdict(list)
    for nome, att in commesse.items():
        for codice, dati in att.items():
            risorse[dati["risorsa"]].append({
                "commessa": nome,
                "codice": codice,
                "inizio": dati["inizio"],
                "fine": dati["fine"],
                "durata": dati["durata"]
            })
    for risorsa, attività in risorse.items():
        attività.sort(key=lambda x: x["inizio"])
        for i in range(1, len(attività)):
            prec = attività[i-1]
            curr = attività[i]
            if curr["inizio"] < prec["fine"]:
                new_start = prossimo_lavorativo(prec["fine"] + timedelta(days=1))
                new_end = aggiungi_lavorativi(new_start, curr["durata"])
                commesse[curr["commessa"]][curr["codice"]]["inizio"] = new_start
                commesse[curr["commessa"]][curr["codice"]]["fine"] = new_end

# === Streamlit App ===
st.set_page_config(layout="wide")
st.title("📅 Gantt Interattivo – Commesse Fotovoltaiche")

ANNO = 2025
if "commesse" not in st.session_state:
    st.session_state.commesse = {}

file = st.sidebar.file_uploader("📂 Carica file JSON", type="json")
if file:
    st.session_state.commesse = json.load(file)
    for att in st.session_state.commesse.values():
        for d in att.values():
            d["inizio"] = datetime.strptime(d["inizio"], "%Y-%m-%d")
            d["fine"] = datetime.strptime(d["fine"], "%Y-%m-%d")

with st.sidebar:
    st.subheader("➕ Aggiungi attività")
    with st.form("inserimento_attivita"):
        comm = st.text_input("Commessa")
        cod = st.text_input("Codice attività")
        nome = st.text_input("Nome attività")
        risorsa = st.text_input("Risorsa")
        durata = st.number_input("Durata (gg lavorativi)", 1, 60, 5)
        inizio = st.date_input("Data inizio", datetime(ANNO, 1, 2))
        submitted = st.form_submit_button("Aggiungi")

        if submitted:
            dt_inizio = datetime.combine(inizio, datetime.min.time())
            dt_inizio = prossimo_lavorativo(dt_inizio)
            dt_fine = aggiungi_lavorativi(dt_inizio, durata)
            if comm not in st.session_state.commesse:
                st.session_state.commesse[comm] = {}
            if cod in st.session_state.commesse[comm]:
                st.warning(f"⚠️ Il codice '{cod}' esiste già in '{comm}'")
            else:
                st.session_state.commesse[comm][cod] = {
                    "nome": nome,
                    "risorsa": risorsa,
                    "durata": durata,
                    "inizio": dt_inizio,
                    "fine": dt_fine
                }
                st.success(f"✅ Attività '{cod}' aggiunta con successo!")

commesse = st.session_state.commesse

if commesse:
    risolvi_sovrapposizioni(commesse)
    fig, ax = plt.subplots(figsize=(14, max(5, len(commesse))))
    yticks, ylabels = [], []
    colori = {
        "sopralluogo": "#66c2a5", "pullout": "#fc8d62",
        "montaggio": "#8da0cb", "impianto pali": "#e78ac3",
        "montaggio pannelli": "#a6d854"
    }
    for i, comm in enumerate(commesse):
        for cod, dati in commesse[comm].items():
            curr = dati["inizio"]
            col = colori.get(dati["nome"].lower(), "#ffd92f")
            while curr <= dati["fine"]:
                if giorno_lavorativo(curr):
                    ax.barh(i, 1, left=curr, height=0.5, color=col)
                curr += timedelta(days=1)
            ax.text(dati["inizio"], i, f"{cod}: {dati['nome']}", va='center', fontsize=7)
        yticks.append(i)
        ylabels.append(comm)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.set_title("📊 Gantt con giorni lavorativi e festività escluse")
    ax.grid(True)
    giorno = min(d["inizio"] for att in commesse.values() for d in att.values())
    fine = max(d["fine"] for att in commesse.values() for d in att.values())
    while giorno <= fine:
        if not giorno_lavorativo(giorno):
            ax.axvspan(giorno, giorno + timedelta(days=1), color='lightgray', alpha=0.3)
        giorno += timedelta(days=1)
    plt.xticks(rotation=45)
    st.pyplot(fig)
    if st.download_button("💾 Esporta JSON", json.dumps({k: {kk: {**vv, 'inizio': vv['inizio'].strftime('%Y-%m-%d'), 'fine': vv['fine'].strftime('%Y-%m-%d')} for kk, vv in v.items()} for k, v in commesse.items()}, indent=2), file_name="commesse.json"):
        st.success("✔️ Esportazione completata")
