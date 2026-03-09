import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="kalkulator ściany i gazu", layout="wide")

# ---------- stałe i słowniki ----------
# opory przejmowania (kierunek poziomy, ściana zewnętrzna)
DEFAULT_RSI = 0.13
DEFAULT_RSE = 0.04

# domyślne lambdy (orientacyjne; najlepiej podmienić na wartości z karty produktu)
# źródła typowych wartości są różne; w praktyce lambdy zależą od konkretnego wyrobu i wilgotności.
insulation_lambdas = {
    "eps biały (typowo ~0,038)": 0.038,
    "eps grafit (typowo ~0,031)": 0.031,
    "wełna mineralna (typowo ~0,039)": 0.039,
    "xps (typowo ~0,034)": 0.034,
    "pir/pur (typowo ~0,022)": 0.022,
    "celuloza (typowo ~0,040)": 0.040,
    "inna (wpiszę ręcznie)": None,
}

masonry_lambdas = {
    "cegła pełna (przykładowo ~0,77)": 0.77,
    "pustak ceramiczny (przykładowo ~0,25)": 0.25,
    "beton komórkowy (przykładowo ~0,12)": 0.12,
    "beton (przykładowo ~1,40)": 1.40,
    "kamień (przykładowo ~1,70)": 1.70,
    "inna (wpiszę ręcznie)": None,
}

# myorlen – paliwo gazowe na cele opałowe (netto) i abonament (netto)
# (dla prostoty przyjmujemy jedną cenę paliwa dla ogrzewania w grupach w; realnie zależy od taryfy i warunków)
myorlen_supply = {
    "w-3.6": {"fuel_gr_per_kwh": 20.119, "abon_zl_per_month": 6.40},
    "w-3.9": {"fuel_gr_per_kwh": 20.119, "abon_zl_per_month": 8.02},
}

# psg – taryfa nr 14 (netto): stawka stała [zł/m-c] i zmienna [gr/kwh] dla przykładowych obszarów
psg_distribution = {
    "po": {  # poznański
        "label": "poznański (po)",
        "w-3.6": {"fixed_zl_per_month": 49.78, "var_gr_per_kwh": 5.388},
        "w-3.9": {"fixed_zl_per_month": 50.58, "var_gr_per_kwh": 5.388},
    },
    "ta": {  # tarnowski
        "label": "tarnowski (ta)",
        "w-3.6": {"fixed_zl_per_month": 55.20, "var_gr_per_kwh": 4.506},
        "w-3.9": {"fixed_zl_per_month": 59.29, "var_gr_per_kwh": 4.506},
    },
    "wa": {  # warszawski
        "label": "warszawski (wa)",
        "w-3.6": {"fixed_zl_per_month": 63.57, "var_gr_per_kwh": 3.919},
        "w-3.9": {"fixed_zl_per_month": 67.25, "var_gr_per_kwh": 3.919},
    },
    "wr": {  # wrocławski
        "label": "wrocławski (wr)",
        "w-3.6": {"fixed_zl_per_month": 51.80, "var_gr_per_kwh": 5.399},
        "w-3.9": {"fixed_zl_per_month": 55.71, "var_gr_per_kwh": 5.399},
    },
}


# ---------- funkcje ----------
def safe_float(x, default=None):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default


def calc_r_layers(layers_df: pd.DataFrame) -> float:
    """
    suma oporów warstw: R = sum(d/lambda)
    grubość w cm, lambda w w/(m*k)
    """
    if layers_df is None or layers_df.empty:
        return 0.0

    r_sum = 0.0
    for _, row in layers_df.iterrows():
        d_cm = safe_float(row.get("grubość [cm]"), 0.0) or 0.0
        lam = safe_float(row.get("lambda [w/(m*k)]"), None)
        if d_cm <= 0:
            continue
        if lam is None or lam <= 0:
            continue
        r_sum += (d_cm / 100.0) / lam
    return r_sum


def calc_u_value(rsi: float, rse: float, r_layers: float) -> float:
    r_total = (rsi or 0.0) + (r_layers or 0.0) + (rse or 0.0)
    if r_total <= 0:
        return float("nan")
    return 1.0 / r_total


def annual_transmission_kwh(u_value: float, area_m2: float, hdd_k_day: float) -> float:
    """
    q = u * a * hdd * 24 / 1000
    u [w/m2k], a [m2], hdd [k*day] => wh => kwh
    """
    if any(v is None for v in [u_value, area_m2, hdd_k_day]):
        return float("nan")
    if u_value <= 0 or area_m2 <= 0 or hdd_k_day <= 0:
        return 0.0
    return u_value * area_m2 * hdd_k_day * 24.0 / 1000.0


def heat_loss_w(u_value: float, area_m2: float, delta_t_k: float) -> float:
    if u_value <= 0 or area_m2 <= 0 or delta_t_k <= 0:
        return 0.0
    return u_value * area_m2 * delta_t_k


def gas_cost_pln(
    heat_kwh: float,
    boiler_eff: float,
    fuel_gr_per_kwh: float,
    dist_var_gr_per_kwh: float,
    abon_zl_per_month: float,
    dist_fixed_zl_per_month: float,
    vat_rate: float,
) -> dict:
    """
    liczymy koszt roczny dla energii użytecznej heat_kwh:
    - gaz_kwh = heat_kwh / sprawność
    - koszt zmienny = gaz_kwh * ( (fuel + dist_var) * (1+vat) )
    - koszt stały = 12 * (abon + dist_fixed) * (1+vat)
    """
    heat_kwh = max(0.0, heat_kwh or 0.0)
    boiler_eff = boiler_eff if boiler_eff and boiler_eff > 0 else 1.0

    gas_kwh = heat_kwh / boiler_eff

    fuel_pln_per_kwh_net = (fuel_gr_per_kwh or 0.0) / 100.0
    dist_var_pln_per_kwh_net = (dist_var_gr_per_kwh or 0.0) / 100.0

    vat_mult = 1.0 + (vat_rate or 0.0)

    var_cost = gas_kwh * (fuel_pln_per_kwh_net + dist_var_pln_per_kwh_net) * vat_mult
    fixed_cost = 12.0 * ((abon_zl_per_month or 0.0) + (dist_fixed_zl_per_month or 0.0)) * vat_mult

    total = var_cost + fixed_cost

    return {
        "gaz_kwh": gas_kwh,
        "koszt_zmienny_pln": var_cost,
        "koszt_staly_pln": fixed_cost,
        "koszt_razem_pln": total,
    }


# ---------- ui ----------
st.title("kalkulator docieplenia ściany i kosztów ogrzewania gazem")
st.caption("model uproszczony: przenikanie przez przegrodę (bez mostków cieplnych, wentylacji i zysków).")

col_a, col_b = st.columns([1.1, 1.0], gap="large")

with col_a:
    st.subheader("1) przegroda: warstwy ściany + docieplenie")

    area_m2 = st.number_input("powierzchnia ściany [m²]", min_value=0.0, value=50.0, step=1.0)

    st.markdown("**warstwy bazowe (mur + ewentualne tynki itp.)**")
    default_df = pd.DataFrame(
        [
            {"warstwa": "mur (45 cm)", "grubość [cm]": 45.0, "lambda [w/(m*k)]": 0.77},
            {"warstwa": "tynk wewnętrzny", "grubość [cm]": 1.5, "lambda [w/(m*k)]": 0.70},
            {"warstwa": "tynk zewnętrzny", "grubość [cm]": 1.5, "lambda [w/(m*k)]": 0.70},
        ]
    )

    if "base_layers" not in st.session_state:
        st.session_state["base_layers"] = default_df

    base_layers = st.data_editor(
        st.session_state["base_layers"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "warstwa": st.column_config.TextColumn("warstwa"),
            "grubość [cm]": st.column_config.NumberColumn("grubość [cm]", min_value=0.0, step=0.1),
            "lambda [w/(m*k)]": st.column_config.NumberColumn("lambda [w/(m*k)]", min_value=0.0, step=0.001),
        },
    )
    st.session_state["base_layers"] = base_layers

    st.divider()
    st.markdown("**docieplenie**")

    ins_mat = st.selectbox("materiał docieplenia", list(insulation_lambdas.keys()), index=2)
    ins_thickness_cm = st.number_input("grubość docieplenia [cm]", min_value=0.0, value=15.0, step=1.0)

    if insulation_lambdas[ins_mat] is None:
        ins_lambda = st.number_input("lambda docieplenia [w/(m*k)]", min_value=0.001, value=0.036, step=0.001)
    else:
        ins_lambda = insulation_lambdas[ins_mat]

    # opory przejmowania (można zmienić, jeśli przegroda nie jest typową ścianą zewnętrzną)
    with st.expander("ustawienia zaawansowane (rsi/rse)"):
        rsi = st.number_input("rsi [m²k/w]", min_value=0.0, value=DEFAULT_RSI, step=0.01)
        rse = st.number_input("rse [m²k/w]", min_value=0.0, value=DEFAULT_RSE, step=0.01)

    # obliczenia u
    r_base = calc_r_layers(base_layers)
    u_base = calc_u_value(rsi, rse, r_base)

    r_ins = r_base + ((ins_thickness_cm / 100.0) / ins_lambda if ins_thickness_cm > 0 and ins_lambda > 0 else 0.0)
    u_ins = calc_u_value(rsi, rse, r_ins)

    st.markdown("**wynik u-value**")
    c1, c2, c3 = st.columns(3)
    c1.metric("u bazowe [w/m²k]", f"{u_base:.3f}" if math.isfinite(u_base) else "—")
    c2.metric("u po dociepleniu [w/m²k]", f"{u_ins:.3f}" if math.isfinite(u_ins) else "—")
    if math.isfinite(u_base) and math.isfinite(u_ins) and u_base > 0:
        c3.metric("zmiana u", f"{(u_ins/u_base):.2%}")
    else:
        c3.metric("zmiana u", "—")

with col_b:
    st.subheader("2) energia i koszt gazu (domyślne, aktualne taryfy)")

    # klimat / hdd
    hdd = st.number_input("stopniodni grzania hdd [k*dzień/rok]", min_value=0.0, value=3500.0, step=50.0)
    delta_t = st.number_input("różnica temperatur do mocy chwilowej Δt [k]", min_value=0.0, value=40.0, step=1.0)

    q_base_kwh = annual_transmission_kwh(u_base, area_m2, hdd) if math.isfinite(u_base) else float("nan")
    q_ins_kwh = annual_transmission_kwh(u_ins, area_m2, hdd) if math.isfinite(u_ins) else float("nan")

    p_base_w = heat_loss_w(u_base, area_m2, delta_t) if math.isfinite(u_base) else float("nan")
    p_ins_w = heat_loss_w(u_ins, area_m2, delta_t) if math.isfinite(u_ins) else float("nan")

    st.markdown("**energia przez tę ścianę (orientacyjnie)**")
    cc1, cc2 = st.columns(2)
    cc1.metric("rocznie bazowo [kwh]", f"{q_base_kwh:,.0f}".replace(",", " ") if math.isfinite(q_base_kwh) else "—")
    cc2.metric("rocznie po dociepleniu [kwh]", f"{q_ins_kwh:,.0f}".replace(",", " ") if math.isfinite(q_ins_kwh) else "—")

    st.markdown("**moc strat przez tę ścianę przy Δt**")
    cc3, cc4 = st.columns(2)
    cc3.metric("bazowo [w]", f"{p_base_w:,.0f}".replace(",", " ") if math.isfinite(p_base_w) else "—")
    cc4.metric("po dociepleniu [w]", f"{p_ins_w:,.0f}".replace(",", " ") if math.isfinite(p_ins_w) else "—")

    st.divider()
    st.markdown("**parametry gazu (możesz dopasować do rachunku)**")

    tariff_group = st.selectbox("grupa taryfowa (sprzedaż)", ["w-3.6", "w-3.9"], index=0)
    dist_area = st.selectbox(
        "obszar taryfowy psg (dystrybucja)",
        list(psg_distribution.keys()),
        format_func=lambda k: psg_distribution[k]["label"],
        index=2,  # domyślnie wa
    )

    vat = st.number_input("vat (ułamek, np. 0.23)", min_value=0.0, max_value=1.0, value=0.23, step=0.01)
    boiler_eff = st.number_input("sprawność kotła (np. 0.92)", min_value=0.1, max_value=1.0, value=0.92, step=0.01)

    # domyślne z taryf
    fuel_gr = myorlen_supply[tariff_group]["fuel_gr_per_kwh"]
    abon = myorlen_supply[tariff_group]["abon_zl_per_month"]

    dist_fixed = psg_distribution[dist_area][tariff_group]["fixed_zl_per_month"]
    dist_var_gr = psg_distribution[dist_area][tariff_group]["var_gr_per_kwh"]

    with st.expander("pokaż/zmień stawki (netto)"):
        fuel_gr = st.number_input("paliwo gazowe myorlen [gr/kwh] netto", min_value=0.0, value=float(fuel_gr), step=0.001)
        abon = st.number_input("abonament myorlen [zł/m-c] netto", min_value=0.0, value=float(abon), step=0.01)
        dist_var_gr = st.number_input("dystrybucja zmienna psg [gr/kwh] netto", min_value=0.0, value=float(dist_var_gr), step=0.001)
        dist_fixed = st.number_input("dystrybucja stała psg [zł/m-c] netto", min_value=0.0, value=float(dist_fixed), step=0.01)

    # koszt
    cost_base = gas_cost_pln(q_base_kwh if math.isfinite(q_base_kwh) else 0.0, boiler_eff, fuel_gr, dist_var_gr, abon, dist_fixed, vat)
    cost_ins = gas_cost_pln(q_ins_kwh if math.isfinite(q_ins_kwh) else 0.0, boiler_eff, fuel_gr, dist_var_gr, abon, dist_fixed, vat)

    st.markdown("**koszt roczny ogrzewania (dla energii przez tę ścianę)**")
    k1, k2, k3 = st.columns(3)
    k1.metric("bazowo [pln/rok]", f"{cost_base['koszt_razem_pln']:,.0f}".replace(",", " "))
    k2.metric("po dociepleniu [pln/rok]", f"{cost_ins['koszt_razem_pln']:,.0f}".replace(",", " "))
    k3.metric("oszczędność [pln/rok]", f"{(cost_base['koszt_razem_pln'] - cost_ins['koszt_razem_pln']):,.0f}".replace(",", " "))

    st.caption("uwaga: to koszt przypisany do strat przez tę ścianę. żeby policzyć cały budynek, dodaj kolejne przegrody (albo uogólnij model).")

    st.divider()
    st.subheader("3) szybkie porównanie kilku grubości docieplenia")
    t_min = st.number_input("min [cm]", min_value=0.0, value=0.0, step=1.0)
    t_max = st.number_input("max [cm]", min_value=0.0, value=30.0, step=1.0)
    t_step = st.number_input("krok [cm]", min_value=1.0, value=5.0, step=1.0)

    rows = []
    thickness = t_min
    while thickness <= t_max + 1e-9:
        r_tmp = r_base + ((thickness / 100.0) / ins_lambda if thickness > 0 and ins_lambda > 0 else 0.0)
        u_tmp = calc_u_value(rsi, rse, r_tmp)
        q_tmp = annual_transmission_kwh(u_tmp, area_m2, hdd) if math.isfinite(u_tmp) else 0.0
        c_tmp = gas_cost_pln(q_tmp, boiler_eff, fuel_gr, dist_var_gr, abon, dist_fixed, vat)
        rows.append(
            {
                "docieplenie [cm]": round(thickness, 1),
                "u [w/m²k]": round(u_tmp, 3) if math.isfinite(u_tmp) else None,
                "kwh/rok": round(q_tmp, 0),
                "pln/rok": round(c_tmp["koszt_razem_pln"], 0),
            }
        )
        thickness += t_step

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)