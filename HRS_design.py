"""
H2READY TOOLKIT - Tool 2.8: Dimensionamento e design tecno-economico HRS
Progetto Interreg Italia-Slovenia H2READY - APE FVG

COSA CAMBIA rispetto alla versione precedente
 1. I risultati vivono in st.session_state. Prima il blocco di export era annidato
    dentro l'if del bottone di calcolo: al primo rerun spariva tutto, compreso il
    campo dove digitare l'identificativo, e non si riusciva a esportare.
 2. La configurazione strategica entra nei calcoli. Prima era una tendina decorativa.
    Ora governa le pressioni di erogazione, il sovradimensionamento dello stoccaggio
    e la sorgente suggerita.
 3. L'Hub Intermodale eroga a 350 e 700 bar insieme: due linee, due dispenser,
    due chiller, compressione dimensionata su ciascuna.
 4. Il payload esporta otto variabili invece di tre.
"""

import streamlit as st
import numpy as np
import os
import requests
import json

# ==========================================
# 1. CONFIGURAZIONE PAGINA E LINGUA
# ==========================================
st.set_page_config(page_title="H2READY TOOLKIT - Tool 2.8", layout="wide")

LANG_OPTIONS = {"Italiano": "it", "English": "en", "Slovenščina": "sl"}
lang_choice = st.sidebar.selectbox("🌐 Lingua / Language / Jezik", list(LANG_OPTIONS.keys()))
LANG = LANG_OPTIONS[lang_choice]

T = {
    "it": {
        "title": "🚀 H2READY TOOLKIT - Tool 2.8: Dimensionamento e Design Tecno-Economico HRS",
        "credits": "Sviluppato all'interno del progetto [INTERREG H2Ready](https://www.ita-slo.eu/en/h2ready) da **Matteo De Piccoli - [APE FVG](https://www.ape.fvg.it/)**",
        "instr_title": "📖 GUIDA OPERATIVA (Leggi prima di iniziare)",
        "logic_title": "🧠 Analisi Metodologica e Standard di Progettazione",
        "instructions_md": """
### 🎯 Qual è il tuo obiettivo?
Questo strumento serve a dimensionare l'architettura tecnica e a stimare l'impatto economico
di una **Stazione di Rifornimento a Idrogeno (HRS)** per mezzi pesanti.

**Istruzioni:**
1. Scegli la **configurazione obiettivo**: determina quali pressioni la stazione deve erogare
   e quanto margine di stoccaggio serve.
2. Configura i **parametri tecnici ed economici** nella barra laterale.
3. Clicca su **'Avvia Dimensionamento'** per generare il report tecno-economico.
4. Il report resta a schermo: puoi esportarlo nel database centrale in fondo alla pagina.
        """,
        "sb_config": "🏗️ Configurazione Strategica",
        "sb_tech": "⚡ Parametri Tecnici HRS",
        "sb_econ": "💸 Parametri Economici",
        "lbl_conf_type": "Configurazione Impianto Obiettivo",
        "lbl_cars": "Auto private / flotta leggera (4.5 kg/pieno)",
        "lbl_buses": "Autobus TPL / Mezzi Speciali (30 kg/pieno)",
        "lbl_trucks": "Camion Pesanti a lungo raggio (50 kg/pieno)",
        "lbl_window": "Finestra di Rifornimento (ore/giorno)",
        "lbl_cf": "Fattore di Carico Stazione (Capacity Factor %)",
        "lbl_source": "Sorgente e Pressione di Ingresso H2",
        "lbl_routing": "Architettura di Compressione/Storage",
        "lbl_dispenser": "Pressione di Erogazione Finale",
        "btn_calc": "🚀 Avvia Dimensionamento Impiantistico HRS",
        "input_id": "Codice Identificativo per esportazione (es. 030043):",
    }
}
_t = T.get(LANG, T["it"])

# ==========================================
# 2. CONFIGURAZIONI STRATEGICHE
# ==========================================
# overcap = sovradimensionamento dello stoccaggio rispetto alla domanda giornaliera.
#   Transito puro: arrivi concentrati ma prevedibili sul corridoio.
#   Hub intermodale: tipologie di mezzo diverse, picchi meno correlati fra loro.
#   Valley integrata: lo stoccaggio fa anche da polmone sulla produzione rinnovabile,
#   che è variabile, quindi serve più margine.
CONFIGURAZIONI = {
    "HRS di Transito Puro (Flussi autostradali)": {
        "chiave": "transito",
        "pressioni": [700],
        "overcap": 1.9,
        "fonte_suggerita": "Carro Bombolaio (200 bar)",
        "nota": "Erogazione a 700 bar per il solo trasporto pesante a lungo raggio. "
                "Autobus e mezzi di piazzale non sono serviti da questa configurazione.",
    },
    "HRS Hub Intermodale Multi-Mezzo": {
        "chiave": "hub",
        "pressioni": [350, 700],
        "overcap": 2.1,
        "fonte_suggerita": "Pipeline Snam (30 bar)",
        "nota": "Due linee di erogazione: 350 bar per autobus e mezzi di piazzale, "
                "700 bar per camion e auto. Raddoppia dispenser e chiller.",
    },
    "HRS Valley Strategica Integrata": {
        "chiave": "valley",
        "pressioni": [350, 700],
        "overcap": 2.5,
        "fonte_suggerita": "Elettrolizzatore (20 bar)",
        "nota": "Stazione integrata con produzione locale. Lo stoccaggio assorbe la "
                "variabilità della fonte rinnovabile: margine più ampio.",
    },
}

PRESSIONI_INGRESSO = {
    "Elettrolizzatore (20 bar)": 20,
    "Pipeline Snam (30 bar)": 30,
    "Carro Bombolaio (200 bar)": 200,
}

# Consumi per pieno [kg]
KG_AUTO, KG_BUS, KG_CAMION = 4.5, 30.0, 50.0

# ==========================================
# 3. INTESTAZIONE
# ==========================================
st.title(_t["title"])
st.markdown(_t["credits"])
st.divider()

with st.expander(_t["instr_title"], expanded=True):
    st.markdown(_t["instructions_md"])

with st.expander(_t["logic_title"], expanded=False):
    nome_file_logica = f"logic_logistica_{LANG}.md"
    if os.path.exists(nome_file_logica):
        with open(nome_file_logica, "r", encoding="utf-8") as f:
            st.markdown(f.read())
    else:
        st.caption("ℹ️ File di analisi metodologica estesa caricato esternamente.")

st.markdown("---")

# ==========================================
# 4. SIDEBAR
# ==========================================
if "prev_fonte" not in st.session_state:
    st.session_state.prev_fonte = "Elettrolizzatore (20 bar)"
    st.session_state.costo_molecola_in = 8.0

with st.sidebar:
    with st.expander(_t["sb_config"], expanded=True):
        config_scelta = st.selectbox(_t["lbl_conf_type"], list(CONFIGURAZIONI.keys()))
        CFG = CONFIGURAZIONI[config_scelta]
        st.caption(CFG["nota"])

    with st.expander(_t["sb_tech"], expanded=True):
        n_auto = st.slider(_t["lbl_cars"], 0, 100, 10, step=5)
        n_bus = st.slider(_t["lbl_buses"], 0, 50, 5, step=1)
        n_camion = st.slider(_t["lbl_trucks"], 0, 150, 30, step=5)
        finestra_ore = st.slider(_t["lbl_window"], 1, 24, 8)
        capacity_factor = st.slider(_t["lbl_cf"], 10, 100, 75) / 100.0

        fonte_h2 = st.selectbox(
            _t["lbl_source"], list(PRESSIONI_INGRESSO.keys()),
            index=list(PRESSIONI_INGRESSO.keys()).index(CFG["fonte_suggerita"]),
            help=f"Suggerita per questa configurazione: {CFG['fonte_suggerita']}",
        )

        if st.session_state.prev_fonte != fonte_h2:
            if "Pipeline" in fonte_h2:
                st.session_state.costo_molecola_in = 6.0
            elif "Carro" in fonte_h2:
                st.session_state.costo_molecola_in = 10.0
            else:
                st.session_state.costo_molecola_in = 8.0
            st.session_state.prev_fonte = fonte_h2

        routing_logic = st.selectbox(
            _t["lbl_routing"],
            ["Magazzino a Cascata (3 banchi)", "Booster Compressor (Diretta)"])

        # La pressione di erogazione non si sceglie più: la impone la configurazione.
        etichette = " + ".join(f"{p} bar" for p in CFG["pressioni"])
        st.info(f"**{_t['lbl_dispenser']}:** {etichette}\n\nDeterminata dalla configurazione.")

    with st.expander(_t["sb_econ"], expanded=True):
        costo_energia = st.number_input("Costo Elettricità (€/kWh)", 0.05, 0.50, 0.15, step=0.01)
        costo_molecola_in = st.number_input("Costo Acquisto/Produzione H2 (€/kg)",
                                            1.0, 20.0, step=0.5, key="costo_molecola_in")
        wacc = st.slider("Costo del Capitale (WACC %)", 1, 15, 6) / 100.0
        anni_vita = st.slider("Vita Utile Impianto (Anni)", 5, 30, 15)


# ==========================================
# 5. MOTORE DI CALCOLO
# ==========================================
def dimensiona_linea(kg_giorno, p_inlet, p_disp, routing, finestra, overcap):
    """Dimensiona una singola linea di compressione, stoccaggio ed erogazione."""
    Cp, k_ad, eta_is, T_in, stadi = 14.5, 1.41, 0.60, 293.15, 3

    if "Cascata" in routing:
        eta_el, fat_usabilita, costo_storage_kg, ore_lavoro = 0.88, 0.91, 1092, 20
    else:
        eta_el, fat_usabilita, costo_storage_kg, ore_lavoro = 0.92, 0.95, 968, finestra

    p_stoccaggio = p_disp + 150
    portata_kg_s = kg_giorno / (ore_lavoro * 3600) if kg_giorno > 0 else 0.0
    stoccaggio_kg = (kg_giorno * overcap) / fat_usabilita

    beta_st = (p_stoccaggio / p_inlet) ** (1 / stadi)
    T_out = T_in * (beta_st ** ((k_ad - 1) / k_ad))
    lav_reale = (Cp * (T_out - T_in) / eta_is) * stadi

    potenza_kW = (lav_reale * portata_kg_s) / eta_el
    consumo_kwh_kg = lav_reale / 3600 / eta_el

    capex = (stoccaggio_kg * costo_storage_kg          # stoccaggio
             + potenza_kW * 2500                        # compressione
             + 200000 * (1.3 if p_disp == 700 else 1.0) # dispenser
             + (120000 if p_disp == 700 else 60000))    # chiller

    return {
        "p_disp": p_disp, "kg_giorno": kg_giorno, "stoccaggio_kg": stoccaggio_kg,
        "potenza_kW": potenza_kW, "consumo_kwh_kg": consumo_kwh_kg, "capex": capex,
        "velocita_g_s": 60 if p_disp == 700 else 120,
    }


def calcola():
    """Esegue il dimensionamento completo e restituisce il dizionario dei risultati."""
    kg_auto = n_auto * KG_AUTO * capacity_factor
    kg_bus = n_bus * KG_BUS * capacity_factor
    kg_camion = n_camion * KG_CAMION * capacity_factor
    kg_totale = kg_auto + kg_bus + kg_camion

    if kg_totale == 0:
        return None

    p_inlet = PRESSIONI_INGRESSO[fonte_h2]

    # Ripartizione della domanda fra le linee di pressione.
    if CFG["pressioni"] == [700]:
        domanda = {700: kg_totale}
    else:
        # 350 bar: autobus e mezzi di piazzale. 700 bar: camion e auto.
        domanda = {350: kg_bus, 700: kg_camion + kg_auto}

    linee = [dimensiona_linea(kg, p_inlet, p, routing_logic, finestra_ore, CFG["overcap"])
             for p, kg in domanda.items() if kg > 0]

    capex_tot = sum(l["capex"] for l in linee) * 1.25          # +25% opere civili
    potenza_tot = sum(l["potenza_kW"] for l in linee)
    stoccaggio_tot = sum(l["stoccaggio_kg"] for l in linee)

    # Consumo medio ponderato sui kg effettivamente compressi da ciascuna linea
    energia_giorno = sum(l["consumo_kwh_kg"] * l["kg_giorno"] for l in linee)
    consumo_medio = energia_giorno / kg_totale

    opex_fisso = capex_tot * 0.04
    opex_energia = energia_giorno * 365 * costo_energia
    opex_totale = opex_fisso + opex_energia

    crf = (wacc * (1 + wacc) ** anni_vita) / (((1 + wacc) ** anni_vita) - 1)
    costo_specifico_hrs = (capex_tot * crf + opex_totale) / (kg_totale * 365)
    break_even = st.session_state.costo_molecola_in + costo_specifico_hrs

    area_netta = (stoccaggio_tot * 0.15) + (potenza_tot * 0.5)

    # Classificazione AFIR sulla capacità giornaliera
    if kg_totale >= 1000:
        taglia = "Large (≥ 1 t/giorno, conforme AFIR)"
    elif kg_totale >= 500:
        taglia = "Medium (0,5 - 1 t/giorno)"
    else:
        taglia = "Small (< 0,5 t/giorno)"

    return {
        "config": config_scelta, "linee": linee, "kg_totale": kg_totale,
        "stoccaggio_tot": stoccaggio_tot, "potenza_tot": potenza_tot,
        "consumo_medio": consumo_medio, "capex_tot": capex_tot,
        "opex_fisso": opex_fisso, "opex_energia": opex_energia, "opex_totale": opex_totale,
        "costo_specifico_hrs": costo_specifico_hrs, "break_even": break_even,
        "area_minima": area_netta * 9.5, "taglia": taglia, "fonte": fonte_h2,
        "costo_molecola": st.session_state.costo_molecola_in,
    }


# Il calcolo scrive in session_state: i risultati sopravvivono ai rerun
# provocati dal campo di testo e dal bottone di export.
if st.button(_t["btn_calc"], type="primary", use_container_width=True):
    R = calcola()
    if R is None:
        st.error("Inserisci almeno un veicolo per effettuare il dimensionamento.")
        st.session_state.pop("hrs", None)
    else:
        st.session_state["hrs"] = R

# ==========================================
# 6. REPORT
# ==========================================
if "hrs" in st.session_state:
    R = st.session_state["hrs"]

    st.success(f"**Configurazione:** {R['config']}")

    st.header("⚙️ Dimensionamento Impianto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Domanda Nominale", f"{R['kg_totale']:,.1f} kg/giorno", R["taglia"])
    c2.metric("Stoccaggio Fisico", f"{R['stoccaggio_tot']:,.0f} kg")
    c3.metric("Potenza Compressore", f"{R['potenza_tot']:,.1f} kW")
    c4.metric("Consumo Compressione", f"{R['consumo_medio']:,.2f} kWh/kg")

    if len(R["linee"]) > 1:
        st.subheader("Linee di erogazione")
        for l in R["linee"]:
            st.markdown(
                f"- **{l['p_disp']} bar** — {l['kg_giorno']:,.1f} kg/giorno · "
                f"stoccaggio {l['stoccaggio_kg']:,.0f} kg · "
                f"compressore {l['potenza_kW']:,.1f} kW · "
                f"CAPEX {l['capex']:,.0f} €"
            )

    for l in R["linee"]:
        tempo = (50 * 1000) / l["velocita_g_s"] / 60
        st.info(f"⏱️ **Standard SAE J2601 — linea {l['p_disp']} bar:** velocità limitata a "
                f"**{l['velocita_g_s']} g/s**. Un pieno da 50 kg richiede circa "
                f"**{tempo:.1f} minuti**, indipendentemente dalla taglia del compressore.")

    st.header("💶 Analisi Finanziaria")
    co1, co2, co3 = st.columns(3)
    co1.metric("CAPEX Totale (Chiavi in Mano)", f"€ {R['capex_tot']:,.0f}")
    co2.metric("OPEX Fisso (O&M, 4% CAPEX)", f"€ {R['opex_fisso']:,.0f} / anno")
    co3.metric("OPEX Elettrico", f"€ {R['opex_energia']:,.0f} / anno")

    st.header("🎯 Break-Even Point (Prezzo minimo alla pompa)")
    st.success(f"Per coprire il rientro dell'investimento e i costi operativi, il prezzo "
               f"minimo di vendita alla pompa deve essere di **{R['break_even']:.2f} €/kg**.")

    b1, b2, b3 = st.columns(3)
    b1.metric("Costo Molecola in Ingresso", f"€ {R['costo_molecola']:.2f} / kg")
    b2.metric("Sovrapprezzo HRS", f"+ € {R['costo_specifico_hrs']:.2f} / kg")
    b3.metric("Prezzo Minimo di Vendita", f"€ {R['break_even']:.2f} / kg")

    st.caption("ℹ️ Il *sovrapprezzo HRS* è il margine necessario alla stazione per ripagare "
               "compressori, manutenzione ed energia. Se la domanda è troppo bassa il "
               "sovrapprezzo schizza, rendendo il carburante fuori mercato.")

    st.header("📐 Vincoli Spaziali")
    st.warning(f"**Vincolo DM 23/10/2018:** per garantire le distanze di sicurezza, il lotto "
               f"deve avere una superficie minima di **{R['area_minima']:,.0f} m²**.")

    # ==========================================
    # 7. ESPORTAZIONE
    # ==========================================
    st.divider()
    st.subheader("💾 Esportazione")

    GOOGLE_URL = "https://script.google.com/macros/s/AKfycbwpP0x0hBnhOadXA43IieWg9EusAuhaafpyeXpyaStssDd7Qo-jwnuOttAllzz8r5JS/exec"

    id_comune = st.text_input(_t["input_id"], key="id_log")

    if st.button("💾 Esporta Report nel Database Centrale"):
        if not id_comune:
            st.error("Inserisci il codice identificativo comunale prima di procedere.")
        else:
            payload = {
                "ID_ISTAT": id_comune,
                "T28_CONFIGURAZIONE": R["config"],
                "T28_CAPACITA_KG_GIORNO": round(R["kg_totale"], 1),
                "T28_TAGLIA_HRS": R["taglia"],
                "T28_STRATEGIA_SUPPLY": R["fonte"],
                "T28_POTENZA_COMPRESSORE_KW": round(R["potenza_tot"], 1),
                "T28_AREA_MINIMA_MQ": round(R["area_minima"], 0),
                "T28_CAPEX_COMPLESSIVO_EURO": round(R["capex_tot"], 0),
                "T28_BREAK_EVEN_EURO_KG": round(R["break_even"], 2),
            }
            try:
                resp = requests.post(GOOGLE_URL, data=json.dumps(payload),
                                     headers={"Content-Type": "application/json"},
                                     allow_redirects=True, timeout=60)
                if resp.status_code in (200, 201):
                    st.success("✅ Dati del design impiantistico trasmessi con successo!")
                    st.caption(f"Risposta del server: {resp.text}")
                    st.balloons()
                else:
                    st.error(f"Errore di sincronizzazione (codice {resp.status_code})")
            except requests.exceptions.ReadTimeout:
                st.warning("⏳ Il server non ha risposto entro il tempo massimo. "
                           "Quasi sempre significa che i dati **sono stati scritti** "
                           "e solo la conferma è andata persa: controlla la riga del "
                           "Comune sul foglio prima di ripetere l'invio.")
            except Exception as e:
                st.error(f"Errore di connessione: {e}")
