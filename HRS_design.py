"""
H2READY TOOLKIT - Tool 2.8: Dimensionamento e design tecno-economico HRS
Progetto Interreg Italia-Slovenia H2READY - APE FVG

Struttura della pagina:
  1. SCENARIO   - dai transiti alla domanda, per orizzonte 2030 / 2040 / 2050
  2. IMPIANTO   - dimensionamento di compressione, stoccaggio ed erogazione
  3. ECONOMIA   - CAPEX, OPEX e prezzo minimo alla pompa
  4. EXPORT     - trasmissione all'excelone

I risultati vivono in st.session_state: il blocco di esportazione deve
sopravvivere ai rerun, altrimenti sparisce al primo tasto premuto.
"""

import streamlit as st
import pandas as pd
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

import h2ready as H

comune = H.blocco_accesso("Tool 2.8 — Dimensionamento HRS",
                          percorso="C", avanzato=True, lingua=LANG)
if comune is None:
    st.stop()

T = {
    "it": {
        "title": "🚀 H2READY TOOLKIT - Tool 2.8: Dimensionamento e Design Tecno-Economico HRS",
        "credits": "Sviluppato all'interno del progetto [INTERREG H2Ready](https://www.ita-slo.eu/en/h2ready) da **Matteo De Piccoli - [APE FVG](https://www.ape.fvg.it/)**",
        "instr_title": "📖 GUIDA OPERATIVA (Leggi prima di iniziare)",
        "logic_title": "🧠 Analisi Metodologica e Standard di Progettazione",
        "instructions_md": """
### 🎯 Qual è il tuo obiettivo?
Dimensionare l'architettura tecnica e stimare l'impatto economico di una
**Stazione di Rifornimento a Idrogeno (HRS)** per mezzi pesanti.

**Istruzioni:**
1. Scegli la **configurazione obiettivo**: determina quali pressioni la stazione deve
   erogare e quanto margine di stoccaggio serve.
2. Imposta la domanda. Puoi inserire i mezzi a mano, oppure derivarli da uno
   **scenario di penetrazione** partendo dal traffico che transita sul nodo.
3. Clicca su **Avvia Dimensionamento**: il report resta a schermo e in fondo puoi
   esportarlo nel database centrale.
        """,
        "sb_scen": "🎯 Scenario di penetrazione",
        "sb_config": "🏗️ Configurazione Strategica",
        "sb_tech": "⚡ Parametri Tecnici HRS",
        "sb_econ": "💸 Parametri Economici",
        "lbl_conf_type": "Configurazione Impianto Obiettivo",
        "scen_on": "Deriva i camion da uno scenario di penetrazione",
        "scen_help": "Invece di indicare quanti camion servi, parti dal traffico che passa sul nodo e applica una quota di mezzi a idrogeno e una quota di cattura della stazione.",
        "scen_year": "Orizzonte temporale",
        "scen_tgm": "TGM camion a lungo raggio (mezzi/giorno)",
        "scen_tgm_help": "Traffico giornaliero medio di mezzi pesanti sul nodo. È il dato raccolto dal tool 2.7.",
        "scen_share": "Quota FCEV sul circolante pesante (%)",
        "scen_capture": "Quota di cattura della stazione (%)",
        "scen_capture_help": "Dei mezzi a idrogeno che transitano, quanti si riforniscono proprio qui. Dipende da quante altre stazioni ci sono sulla tratta.",
        "scen_result": "**{tgm:,.0f}** camion/giorno × **{s:.1f}%** FCEV × **{c:.0f}%** cattura = **{n}** camion serviti al giorno",
        "scen_zero": "⚠️ Con questi parametri la stazione non servirebbe nessun camion. Alza la quota di cattura o il traffico.",
        "scen_traj": "📈 Traiettoria a parametri costanti",
        "scen_traj_note": "Stessa quota di cattura, quota FCEV secondo lo scenario di riferimento di ciascun orizzonte. Serve al cronoprogramma dell'action plan: dice quando la stazione va ampliata.",
        "scen_src": "**Riferimenti.** Reg. UE 2024/1610: −45% CO₂ sui veicoli pesanti nuovi entro il 2030, −65% entro il 2035, −90% entro il 2040 (base 2019); bus urbani nuovi a zero emissioni dal 2030. Roland Berger, *Camion a idrogeno* (2021): nel 2023 il parco pesante europeo è diesel al 99,5%, FCEV allo 0,4%; ricambio di flotta 10-15 anni. Strategia Nazionale Idrogeno (2024), orizzonte 2040-2050: l'idrogeno può coprire il 30% dei consumi finali nei trasporti. Le quote predefinite sono scenari, non obiettivi vincolanti: vanno discusse, non prese per buone.",
        "lbl_cars": "Auto private / flotta leggera (4,5 kg/pieno)",
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
# 2. SCENARI E CONFIGURAZIONI
# ==========================================
# Quote FCEV sul circolante pesante per orizzonte. Sono scenari costruiti sui
# riferimenti citati in _t["scen_src"], non target vincolanti:
#  2030 - la riduzione richiesta dal Reg. 2024/1610 sara' coperta in prevalenza
#         dai BEV; l'idrogeno resta una nicchia sul lungo raggio
#  2040 - obbligo -90% sui nuovi immatricolati, con ricambio di flotta in corso
#  2050 - quota della Strategia Nazionale sui consumi finali nei trasporti
SCENARI = {"2030": 3.0, "2040": 15.0, "2050": 30.0}

CONFIGURAZIONI = {
    "HRS di Transito Puro (Flussi autostradali)": {
        "chiave": "transito", "pressioni": [700], "overcap": 1.9,
        "fonte_suggerita": "Carro Bombolaio (200 bar)",
        "nota": "Erogazione a 700 bar per il solo trasporto pesante a lungo raggio. "
                "Autobus e mezzi di piazzale non sono serviti da questa configurazione.",
    },
    "HRS Hub Intermodale Multi-Mezzo": {
        "chiave": "hub", "pressioni": [350, 700], "overcap": 2.1,
        "fonte_suggerita": "Pipeline Snam (30 bar)",
        "nota": "Due linee di erogazione: 350 bar per autobus e mezzi di piazzale, "
                "700 bar per camion e auto. Raddoppia dispenser e chiller.",
    },
    "HRS Valley Strategica Integrata": {
        "chiave": "valley", "pressioni": [350, 700], "overcap": 2.5,
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

KG_AUTO, KG_BUS, KG_CAMION = 4.5, 30.0, 50.0

# ==========================================
# 3. INTESTAZIONE
# ==========================================
st.title(_t["title"])
st.markdown(_t["credits"])
st.markdown("""
    <p style='font-size: 0.8rem; color: gray;'>
        🌐 Progetto: <a href='https://www.ita-slo.eu/en/h2ready' target='_blank'>Interreg H2Ready</a> |
        🏠 Sito Ente: <a href='https://www.ape.fvg.it/' target='_blank'>APE FVG</a> |
        📧 Contatto: <a href='mailto:matteo.depiccoli@ape.fvg.it'>matteo.depiccoli@ape.fvg.it</a>
    </p>
""", unsafe_allow_html=True)
st.divider()

# --- Comune e dati ereditati dal questionario 2.7 -------------------------
H.intestazione_comune(comune, "Tool 2.8 · Dimensionamento della stazione di rifornimento")

_tgm = H.valore(comune, "T27_TGM_CAMION", 0) or 0
_snam = H.valore(comune, "T27_DISTANZA_SNAM_KM", None)
_voci, _avvisi = [], []

if _tgm > 0:
    _voci.append(("Traffico pesante", f"{_tgm:,.0f} mezzi/giorno", "questionario 2.7"))
else:
    _avvisi.append(("warning", "Il questionario 2.7 non riporta un traffico pesante: "
                               "il valore va inserito a mano nella barra laterale."))
if _snam is not None:
    _voci.append(("Distanza dalla dorsale H2", f"{_snam:,.1f} km", "questionario 2.7"))

for _col, _et in (("T27_FLAG_AFIR_GAP", "Colma un vuoto della rete AFIR"),
                  ("T27_FLAG_HUB_MERCI", "Hub merci o interporti entro 5 km"),
                  ("T27_FLAG_SINERGIA_HTA", "Distretto Hard-to-Abate confinante"),
                  ("T27_FLAG_ACCORDI_FILIERA", "Accordi di filiera già attivi"),
                  ("T27_FLAG_PUMS", "Idrogeno già nel PUMS")):
    if not H.vuoto(comune.get(_col)):
        _voci.append((_et, "Sì" if H.vero(comune[_col]) else "No", "questionario 2.7"))

_prod_b = H.valore(comune, "T26_PRODUZIONE_H2_TON_ANNO", 0) or 0
if _prod_b > 0:
    _voci.append(("Produzione locale prevista", f"{_prod_b:,.1f} t/anno", "tool 2.6"))

if not H.vero(comune.get("T27_FLAG_AREE_700BAR")) and not H.vuoto(comune.get("T27_FLAG_AREE_700BAR")):
    _avvisi.append(("warning", "Dal 2.7 non risultano aree a piano regolatore compatibili "
                               "con lo stoccaggio a 700 bar: verificare con l'ufficio "
                               "urbanistica prima di dimensionare la stazione."))

H.scheda_dati("📥 Dati ereditati dai questionari precedenti", _voci, _avvisi)

# --- Configurazione suggerita dai dati -----------------------------------
_modo_sugg, _perche = H.modalita_2_8(comune)
_CHIAVI = {c["chiave"]: nome for nome, c in CONFIGURAZIONI.items()}
_config_default = _CHIAVI.get(_modo_sugg, list(CONFIGURAZIONI.keys())[0])
st.info(f"**Configurazione suggerita: {_config_default}**\n\n{_perche}")

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
        _opz = list(CONFIGURAZIONI.keys())
        config_scelta = st.selectbox(_t["lbl_conf_type"], _opz,
                                     index=_opz.index(_config_default))
        CFG = CONFIGURAZIONI[config_scelta]
        st.caption(CFG["nota"])

    with st.expander(_t["sb_scen"], expanded=True):
        scen_on = st.checkbox(_t["scen_on"], value=_tgm > 0, help=_t["scen_help"])
        if scen_on:
            orizzonte = st.selectbox(_t["scen_year"], list(SCENARI.keys()))
            tgm_camion = st.number_input(_t["scen_tgm"], 0, 50000,
                                         int(min(_tgm, 50000)) if _tgm > 0 else 5000,
                                         step=100, help=_t["scen_tgm_help"])
            quota_fcev = st.slider(_t["scen_share"], 0.0, 60.0, SCENARI[orizzonte], step=0.5)
            # con un hub merci o accordi di filiera i mezzi rientrano in deposito:
            # la stazione ne cattura una quota molto più alta che sul solo transito
            _cattura_def = 25 if (H.vero(comune.get("T27_FLAG_HUB_MERCI")) or
                                  H.vero(comune.get("T27_FLAG_ACCORDI_FILIERA"))) else 10
            quota_cattura = st.slider(_t["scen_capture"], 1, 100, _cattura_def,
                                      help=_t["scen_capture_help"])
            n_camion = int(round(tgm_camion * quota_fcev / 100.0 * quota_cattura / 100.0))
            st.markdown(_t["scen_result"].format(tgm=tgm_camion, s=quota_fcev,
                                                 c=quota_cattura, n=n_camion))
            if n_camion == 0:
                st.warning(_t["scen_zero"])
        else:
            orizzonte, tgm_camion, quota_fcev, quota_cattura = "-", 0, 0.0, 0
            n_camion = None

    with st.expander(_t["sb_tech"], expanded=True):
        n_auto = st.slider(_t["lbl_cars"], 0, 100, 10, step=5)
        n_bus = st.slider(_t["lbl_buses"], 0, 50, 5, step=1)
        if n_camion is None:
            n_camion = st.slider(_t["lbl_trucks"], 0, 150, 30, step=5)
        else:
            st.caption(f"🎯 {_t['lbl_trucks']}: **{n_camion}** (dallo scenario {orizzonte})")
        finestra_ore = st.slider(_t["lbl_window"], 1, 24, 8)
        capacity_factor = st.slider(_t["lbl_cf"], 10, 100, 75) / 100.0

        fonte_h2 = st.selectbox(
            _t["lbl_source"], list(PRESSIONI_INGRESSO.keys()),
            index=list(PRESSIONI_INGRESSO.keys()).index(CFG["fonte_suggerita"]),
            help=f"Suggerita per questa configurazione: {CFG['fonte_suggerita']}")

        if st.session_state.prev_fonte != fonte_h2:
            if "Pipeline" in fonte_h2:
                st.session_state.costo_molecola_in = 6.0
            elif "Carro" in fonte_h2:
                st.session_state.costo_molecola_in = 10.0
            else:
                st.session_state.costo_molecola_in = 8.0
            st.session_state.prev_fonte = fonte_h2

        routing_logic = st.selectbox(
            _t["lbl_routing"], ["Magazzino a Cascata (3 banchi)", "Booster Compressor (Diretta)"])

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
MINUTI_MANOVRA = 6.0   # accosto, aggancio, pagamento, ripartenza


def dimensiona_linea(kg_giorno, n_erogazioni, p_inlet, p_disp, routing, finestra, overcap):
    """Dimensiona una singola linea di compressione, stoccaggio ed erogazione.

    n_erogazioni serve a contare i punti di erogazione necessari: un dispenser
    non e' illimitato. Lo standard SAE J2601 fissa la velocita' massima di
    riempimento, quindi il numero di mezzi che una colonnina serve in un giorno
    dipende solo dalla finestra di apertura e dal tempo del singolo pieno."""
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

    # --- Punti di erogazione necessari ---
    velocita = 60 if p_disp == 700 else 120          # g/s, limite SAE J2601
    kg_medio = kg_giorno / n_erogazioni if n_erogazioni > 0 else 0.0
    minuti_pieno = (kg_medio * 1000 / velocita) / 60 + MINUTI_MANOVRA
    per_dispenser = (finestra * 60) / minuti_pieno if minuti_pieno > 0 else 0.0
    n_disp = max(1, int(-(-n_erogazioni // per_dispenser))) if per_dispenser > 0 else 1

    costo_disp = 200000 * (1.3 if p_disp == 700 else 1.0)
    costo_chiller = 120000 if p_disp == 700 else 60000
    capex = (stoccaggio_kg * costo_storage_kg
             + potenza_kW * 2500
             + n_disp * (costo_disp + costo_chiller))

    return {"p_disp": p_disp, "kg_giorno": kg_giorno, "stoccaggio_kg": stoccaggio_kg,
            "potenza_kW": potenza_kW, "consumo_kwh_kg": consumo_kwh_kg, "capex": capex,
            "velocita_g_s": velocita, "n_disp": n_disp, "kg_medio": kg_medio,
            "minuti_pieno": minuti_pieno, "per_dispenser": per_dispenser,
            "n_erogazioni": n_erogazioni}


def dimensiona(camion, auto, bus):
    """Dimensionamento completo per un dato numero di mezzi.
    Restituisce None se la domanda e' nulla."""
    kg_auto = auto * KG_AUTO * capacity_factor
    kg_bus = bus * KG_BUS * capacity_factor
    kg_camion = camion * KG_CAMION * capacity_factor
    kg_totale = kg_auto + kg_bus + kg_camion
    if kg_totale <= 0:
        return None

    p_inlet = PRESSIONI_INGRESSO[fonte_h2]
    # Per ogni linea servono i kg e il numero di rifornimenti: il primo
    # dimensiona compressione e stoccaggio, il secondo i punti di erogazione.
    if CFG["pressioni"] == [700]:
        domanda = {700: (kg_totale, camion + auto + bus)}
    else:
        # 350 bar: autobus e mezzi di piazzale. 700 bar: camion e auto.
        domanda = {350: (kg_bus, bus), 700: (kg_camion + kg_auto, camion + auto)}

    linee = [dimensiona_linea(kg, n_erog, p_inlet, p, routing_logic, finestra_ore, CFG["overcap"])
             for p, (kg, n_erog) in domanda.items() if kg > 0]

    capex_tot = sum(l["capex"] for l in linee) * 1.25          # +25% opere civili
    potenza_tot = sum(l["potenza_kW"] for l in linee)
    stoccaggio_tot = sum(l["stoccaggio_kg"] for l in linee)

    energia_giorno = sum(l["consumo_kwh_kg"] * l["kg_giorno"] for l in linee)
    consumo_medio = energia_giorno / kg_totale

    opex_fisso = capex_tot * 0.04
    opex_energia = energia_giorno * 365 * costo_energia
    opex_totale = opex_fisso + opex_energia

    crf = (wacc * (1 + wacc) ** anni_vita) / (((1 + wacc) ** anni_vita) - 1)
    costo_specifico_hrs = (capex_tot * crf + opex_totale) / (kg_totale * 365)
    break_even = st.session_state.costo_molecola_in + costo_specifico_hrs

    area_netta = (stoccaggio_tot * 0.15) + (potenza_tot * 0.5)

    if kg_totale >= 1000:
        taglia = "Large (≥ 1 t/giorno, conforme AFIR)"
    elif kg_totale >= 500:
        taglia = "Medium (0,5 - 1 t/giorno)"
    else:
        taglia = "Small (< 0,5 t/giorno)"

    return {"config": config_scelta, "linee": linee, "kg_totale": kg_totale,
            "stoccaggio_tot": stoccaggio_tot, "potenza_tot": potenza_tot,
            "consumo_medio": consumo_medio, "capex_tot": capex_tot,
            "opex_fisso": opex_fisso, "opex_energia": opex_energia, "opex_totale": opex_totale,
            "costo_specifico_hrs": costo_specifico_hrs, "break_even": break_even,
            "area_minima": area_netta * 9.5, "taglia": taglia, "fonte": fonte_h2,
            "costo_molecola": st.session_state.costo_molecola_in,
            "n_disp_tot": sum(l["n_disp"] for l in linee),
            "n_camion": camion, "n_auto": auto, "n_bus": bus}


def calcola():
    R = dimensiona(n_camion, n_auto, n_bus)
    if R is None:
        return None
    R.update(scen_on=scen_on, orizzonte=orizzonte, tgm=tgm_camion,
             quota_fcev=quota_fcev, quota_cattura=quota_cattura)

    # Traiettoria: stessa stazione, stessi parametri, quota FCEV che cresce.
    # Dice quando la capacita' andra' ampliata, che e' cio' che serve al
    # cronoprogramma dell'action plan.
    if scen_on and tgm_camion > 0:
        traj = []
        for anno, quota in SCENARI.items():
            n = int(round(tgm_camion * quota / 100.0 * quota_cattura / 100.0))
            r = dimensiona(n, n_auto, n_bus)
            traj.append({"anno": anno, "quota": quota, "camion": n,
                         "kg": r["kg_totale"] if r else 0.0,
                         "taglia": r["taglia"] if r else "-",
                         "capex": r["capex_tot"] if r else 0.0,
                         "disp": r["n_disp_tot"] if r else 0,
                         "be": r["break_even"] if r else 0.0})
        R["traiettoria"] = traj
    return R


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

    if R.get("scen_on"):
        st.header(f"🎯 Scenario {R['orizzonte']}")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("TGM camion", f"{R['tgm']:,.0f} /giorno")
        s2.metric("Quota FCEV", f"{R['quota_fcev']:.1f}%")
        s3.metric("Quota di cattura", f"{R['quota_cattura']}%")
        s4.metric("Camion serviti", f"{R['n_camion']} /giorno")

        if R.get("traiettoria"):
            st.subheader(_t["scen_traj"])
            st.caption(_t["scen_traj_note"])
            st.table(pd.DataFrame([{
                "Orizzonte": r["anno"],
                "Quota FCEV": f"{r['quota']:.0f}%",
                "Camion/giorno": r["camion"],
                "Domanda [kg/giorno]": f"{r['kg']:,.0f}",
                "Taglia AFIR": r["taglia"],
                "Colonnine": r["disp"],
                "CAPEX [€]": f"{r['capex']:,.0f}",
                "Prezzo minimo [€/kg]": f"{r['be']:.2f}",
            } for r in R["traiettoria"]]))
        st.caption(_t["scen_src"])
        st.divider()

    st.header("⚙️ Dimensionamento Impianto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Domanda Nominale", f"{R['kg_totale']:,.1f} kg/giorno", R["taglia"])
    c2.metric("Stoccaggio Fisico", f"{R['stoccaggio_tot']:,.0f} kg")
    c3.metric("Potenza Compressore", f"{R['potenza_tot']:,.1f} kW")
    c4.metric("Punti di erogazione", f"{R['n_disp_tot']}",
              f"{R['consumo_medio']:,.2f} kWh/kg di compressione")

    st.subheader("Linee di erogazione")
    for l in R["linee"]:
        st.markdown(
            f"- **{l['p_disp']} bar** — {l['kg_giorno']:,.1f} kg/giorno · "
            f"**{l['n_disp']} punti di erogazione** · stoccaggio {l['stoccaggio_kg']:,.0f} kg · "
            f"compressore {l['potenza_kW']:,.1f} kW · CAPEX {l['capex']:,.0f} €")

    for l in R["linee"]:
        st.info(f"⏱️ **Standard SAE J2601 — linea {l['p_disp']} bar:** velocità limitata a "
                f"**{l['velocita_g_s']} g/s**. Un pieno medio da {l['kg_medio']:,.1f} kg richiede "
                f"**{l['minuti_pieno']:.1f} minuti** manovra compresa, quindi un dispenser serve "
                f"al massimo **{l['per_dispenser']:.0f} mezzi** nella finestra di apertura. "
                f"Per {l['n_erogazioni']:,.0f} rifornimenti al giorno servono "
                f"**{l['n_disp']} colonnine**.")

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

    id_comune = H.testo(comune, H.COL_ID)
    st.caption(f"I dati verranno associati a {H.testo(comune, H.COL_NOME)} "
               f"(ID {id_comune}).")

    if st.button("💾 Esporta Report nel Database Centrale"):
        if True:
            payload = {
                "ID_ISTAT": id_comune,
                "T28_CONFIGURAZIONE": R["config"],
                "T28_CAPACITA_KG_GIORNO": round(R["kg_totale"], 1),
                "T28_TAGLIA_HRS": R["taglia"],
                "T28_STRATEGIA_SUPPLY": R["fonte"],
                "T28_POTENZA_COMPRESSORE_KW": round(R["potenza_tot"], 1),
                "T28_N_DISPENSER": R["n_disp_tot"],
                "T28_AREA_MINIMA_MQ": round(R["area_minima"], 0),
                "T28_CAPEX_COMPLESSIVO_EURO": round(R["capex_tot"], 0),
                "T28_BREAK_EVEN_EURO_KG": round(R["break_even"], 2),
            }
            # l'orizzonte serve al cronoprogramma dell'action plan: si esporta
            # sempre, anche quando i mezzi sono stati inseriti a mano
            payload["T28_ORIZZONTE"] = R["orizzonte"] if R.get("scen_on") else "attuale"
            payload["T28_QUOTA_FCEV_PERC"] = round(R["quota_fcev"], 1) if R.get("scen_on") else 0.0

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
                st.warning("⏳ Il server non ha risposto entro il tempo massimo. Quasi sempre "
                           "significa che i dati **sono stati scritti** e solo la conferma è "
                           "andata persa: controlla la riga del Comune sul foglio prima di "
                           "ripetere l'invio.")
            except Exception as e:
                st.error(f"Errore di connessione: {e}")

st.divider()
st.subheader("Prosegui il percorso")
H.mostra_prossimi_tool(comune, lingua=LANG)
