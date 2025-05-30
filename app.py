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

def intervalli_compatibili(a_start, a_end, b_start, b_end):
    return a_end <= b_start or b_end <= a_start

def risolvi_sovrapposizioni(commesse):
    risorse = defaultdict(list)
    log = []
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

    # Verifica sovrapposizioni tra commesse per la stessa risorsa
    for risorsa, attività in risorse.items():
        for i in range(len(attività)):
            for j in range(i+1, len(attività)):
                a = attività[i]
                b = attività[j]
                if a["commessa"] != b["commessa"]:
                    if not intervalli_compatibili(a["inizio"], a["fine"], b["inizio"], b["fine"]):
                        old_start = b["inizio"].strftime("%d/%m")
                        new_start = prossimo_lavorativo(a["fine"] + timedelta(days=1))
                        new_end = aggiungi_lavorativi(new_start, b["durata"])
                        commesse[b["commessa"]][b["codice"]]["inizio"] = new_start
                        commesse[b["commessa"]][b["codice"]]["fine"] = new_end
                        log.append(f"🔄 Risorsa '{risorsa}': spostata attività '{b['codice']}' della commessa '{b['commessa']}' da {old_start} a {new_start.strftime('%d/%m')}")

    if log:
        st.warning("\\n".join(log))

# === Streamlit UI ===
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

# === Filtri ===
with st.sidebar:
    st.subheader("📌 Filtri")
    commesse_disponibili = list(st.session_state.commesse.keys())
    filtro_commessa = st.selectbox("Filtra per commessa", ["Tutte"] + commesse_disponibili)
    mese_selezionato = st.selectbox("Filtra per mese", ["Tutti"] + [datetime(ANNO, m, 1).strftime('%B') for m in range(1, 13)])

# === Inserimento attività ===
with st.sidebar:
    st.subheader("➕ Aggiungi o modifica attività")
    with st.form("inserimento_attivita"):
        comm = st.text_input("Commessa")
        cod = st.text_input("Codice attività")
        nome = st.text_input("Nome attività")
        risorsa = st.text_input("Risorsa")
        durata = st.number_input("Durata (gg lavorativi)", 1, 60, 5)
        inizio = st.date_input("Data inizio", datetime(ANNO, 1, 2))
        submitted = st.form_submit_button("Salva o aggiorna")

        if submitted:
            dt_inizio = datetime.combine(inizio, datetime.min.time())
            dt_inizio = prossimo_lavorativo(dt_inizio)
            dt_fine = aggiungi_lavorativi(dt_inizio, durata)
            if comm not in st.session_state.commesse:
                st.session_state.commesse[comm] = {}
            st.session_state.commesse[comm][cod] = {
                "nome": nome,
                "risorsa": risorsa,
                "durata": durata,
                "inizio": dt_inizio,
                "fine": dt_fine
            }
            st.success(f"Attività '{cod}' salvata in '{comm}'")
            st.rerun()

    st.subheader("🗑️ Elimina attività")
    if commesse_disponibili:
        selez_comm = st.selectbox("Commessa da cui eliminare", commesse_disponibili)
        attività_lista = list(st.session_state.commesse[selez_comm].keys())
        selez_att = st.selectbox("Attività da eliminare", attività_lista)
        if st.button("Elimina"):
            del st.session_state.commesse[selez_comm][selez_att]
            if not st.session_state.commesse[selez_comm]:
                del st.session_state.commesse[selez_comm]
            st.rerun()

# === Gantt ===
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
    i = 0
    for comm in sorted(commesse):
        if filtro_commessa != "Tutte" and filtro_commessa != comm:
            continue
        for cod, dati in commesse[comm].items():
            mese_attivita = dati["inizio"].strftime("%B")
            if mese_selezionato != "Tutti" and mese_attivita != mese_selezionato:
                continue
            curr = dati["inizio"]
            col = colori.get(dati["nome"].lower(), "#ffd92f")
            while curr <= dati["fine"]:
                if giorno_lavorativo(curr):
                    ax.barh(i, 1, left=curr, height=0.5, color=col)
                curr += timedelta(days=1)
            ax.text(dati["inizio"], i, f"{cod}: {dati['nome']}", va='center', fontsize=7)
        yticks.append(i)
        ylabels.append(comm)
        i += 1
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.set_title("📊 Gantt con filtri e giorni non lavorativi evidenziati")
    ax.grid(True)
    giorno = min(d["inizio"] for att in commesse.values() for d in att.values())
    fine = max(d["fine"] for att in commesse.values() for d in att.values())
    while giorno <= fine:
        if not giorno_lavorativo(giorno):
            ax.axvspan(giorno, giorno + timedelta(days=1), color='lightgray', alpha=0.3)
        giorno += timedelta(days=1)
    plt.xticks(rotation=45)
    st.pyplot(fig)
    st.download_button("💾 Esporta JSON", json.dumps({k: {kk: {**vv, 'inizio': vv['inizio'].strftime('%Y-%m-%d'), 'fine': vv['fine'].strftime('%Y-%m-%d')} for kk, vv in v.items()} for k, v in commesse.items()}, indent=2), file_name="commesse.json")

