import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v3", page_icon="🎭", layout="centered")

# --- STYLE CSS (Branding by D.CZ.) ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ padding: 20px; border-radius: 15px; background: #262730; border: 2px solid #ff4b4b; text-align: center; }}
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE Z GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_sheet(name):
    # ttl=0 wymusza pobieranie świeżych danych za każdym razem
    try:
        return conn.read(worksheet=name, ttl=0).dropna(how='all')
    except:
        return pd.DataFrame()


def save_sheet(name, df):
    conn.update(worksheet=name, data=df)


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_gs():
    p_df = load_sheet("gracze")
    players = p_df.to_dict('records') if not p_df.empty else []
    return {
        'players': players,
        'game_state': 'WAITING',
        'current_word': '',
        'current_hint': '',
        'impostors': [],
        'participants': [],
        'votes_again': {},
        'votes_impostor': {},
        'settings': {"impostors": 1, "hints": True},
        'reg_counter': 0
    }


gs = get_gs()
st_autorefresh(interval=2000, key="global_refresh")

# --- LOGIKA TRWAŁEGO LOGOWANIA ---
if 'logged_user' not in st.session_state:
    q_user = st.query_params.get("gracz")
    if q_user:
        if q_user == ADMIN_USER or any(x['login'] == q_user for x in gs['players']):
            st.session_state.logged_user = q_user
            st.session_state.view = "game_room"

if 'view' not in st.session_state:
    st.session_state.view = "login"


def draw_header(title="IMPOSTOR"):
    st.markdown(f"<h1 class='impostor-title'>{title}</h1>", unsafe_allow_html=True)
    st.markdown("<span class='brand-text'>by D.CZ.</span>", unsafe_allow_html=True)


# --- EKRAN 1: LOGOWANIE ---
if st.session_state.view == "login":
    draw_header()
    u = st.text_input("Login")
    p = st.text_input("Hasło", type="password")
    if st.button("Zaloguj"):
        if u == ADMIN_USER and p == ADMIN_PASSWORD:
            st.session_state.logged_user = ADMIN_USER
            st.session_state.view = "game_room"
            st.query_params["gracz"] = u
            st.rerun()
        else:
            match = next((x for x in gs['players'] if x['login'] == u and x['pwd'] == p), None)
            if match:
                st.session_state.logged_user = u
                st.session_state.view = "game_room"
                st.query_params["gracz"] = u
                st.rerun()
            else:
                st.error("Błędne dane!")

# --- EKRAN 2: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    draw_header("ADMIN")

    t1, t2, t3, t4 = st.tabs(["🎮 Sterowanie", "👥 Gracze", "📖 Baza Haseł", "📜 Logi"])

    with t1:
        st.subheader("Ustawienia rundy")
        gs['settings']['impostors'] = st.slider("Liczba Impostorów", 1, 3, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Włącz podpowiedzi dla Impostorów", gs['settings']['hints'])

        all_nicks = [p['login'] for p in gs['players']] + [ADMIN_USER]
        selected = st.multiselect("Gracze w rundzie", all_nicks, default=all_nicks)

        if gs['game_state'] == 'WAITING':
            if st.button("🚀 ROZPOCZNIJ RUNDĘ"):
                # Pobieramy bazę bezpośrednio przed startem
                words_df = load_sheet("baza_hasel")
                if not words_df.empty:
                    row = words_df.sample(1).iloc[0]
                    gs.update({
                        'current_word': row['Hasło'],
                        'current_hint': row['Podpowiedź'],
                        'participants': selected,
                        'impostors': random.sample(selected, min(len(selected), gs['settings']['impostors'])),
                        'game_state': 'PLAYING', 'votes_again': {}, 'votes_impostor': {}
                    })
                    st.session_state.view = "game_room"
                    st.rerun()
                else:
                    st.error("Baza haseł jest pusta w arkuszu! Dodaj hasła w zakładce obok.")
        else:
            if st.button("🛑 ZAKOŃCZ I GŁOSOWANIE"):
                gs['game_state'] = 'VOTING_AGAIN';
                st.rerun()

        if st.button("🏠 POWRÓT DO GRY"):
            st.session_state.view = "game_room";
            st.rerun()

    with t2:
        st.subheader("Zarządzaj graczami")
        for i, pl in enumerate(gs['players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {pl['login']}")
            if c2.button("Usuń", key=f"del_{pl['login']}"):
                gs['players'].pop(i)
                save_sheet("gracze", pd.DataFrame(gs['players']))
                st.rerun()
        st.divider()
        n_nick = st.text_input("Nowy Nick", key=f"n_{gs['reg_counter']}")
        n_pwd = st.text_input("Hasło", type="password", key=f"p_{gs['reg_counter']}")
        if st.button("Dodaj"):
            if n_nick:
                gs['players'].append({'login': n_nick.strip(), 'pwd': n_pwd, 'score': 0})
                save_sheet("gracze", pd.DataFrame(gs['players']))
                gs['reg_counter'] += 1;
                st.rerun()

    with t3:  # EDYCJA BAZY HASEŁ
        st.subheader("Edytuj bazę haseł")
        # Załaduj świeże dane przy każdym wejściu w zakładkę
        baza_df = load_sheet("baza_hasel")
        if baza_df.empty:
            baza_df = pd.DataFrame(columns=["Hasło", "Podpowiedź"])

        edited_baza = st.data_editor(baza_df, num_rows="dynamic", use_container_width=True, key="editor_baza")
        if st.button("ZAPISZ ZMIANY W BAZIE"):
            save_sheet("baza_hasel", edited_baza)
            st.success("Baza zaktualizowana!")
            st.rerun()

    with t4:  # EDYCJA LOGÓW
        st.subheader("Edytuj logi")
        logi_df = load_sheet("logi")
        if logi_df.empty:
            logi_df = pd.DataFrame(columns=["Data", "Impostor", "Hasło"])

        edited_logi = st.data_editor(logi_df, num_rows="dynamic", use_container_width=True, key="editor_logi")
        if st.button("ZAPISZ ZMIANY W LOGACH"):
            save_sheet("logi", edited_logi)
            st.success("Logi zaktualizowane!")
            st.rerun()

# --- EKRAN 3: ARENA GRY ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user
    st.write(f"Zalogowany: **{user}**")

    if gs['game_state'] == 'WAITING':
        st.info("Czekamy na start...")
        # Połącz admina z resztą do wyświetlania listy
        temp_players = gs['players'] + [{'login': ADMIN_USER, 'score': 'N/A'}]
        rdf = pd.DataFrame(temp_players)
        st.table(rdf[['login', 'score']])

    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='role-card'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                if gs['settings']['hints']: st.write(f"Podpowiedź: {gs['current_hint']}")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Hasło: **{gs['current_word']}**")
                st.write(f"Podpowiedź: {gs['current_hint']}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Nie bierzesz udziału w tej rundzie.")

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Gramy to samo jeszcze raz?")
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()
        if user == ADMIN_USER:
            if st.button("Podlicz głosy (Admin)"):
                yes = sum(1 for v in gs['votes_again'].values() if v)
                no = len(gs['votes_again']) - yes
                gs['game_state'] = 'PLAYING' if yes > no else 'VOTING_IMPOSTOR'
                gs['votes_again'] = {};
                st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        others = [p for p in gs['participants'] if p != user]
        choice = st.selectbox("Wybierz", others)
        if st.button("Głosuj"):
            gs['votes_impostor'][user] = choice
            st.success(f"Głos oddany na {choice}!")

        if user == ADMIN_USER and st.button("Zakończ rundę (Admin)"):
            gs['game_state'] = 'WAITING'
            st.rerun()

    if user == ADMIN_USER:
        if st.button("⚙️ PANEL STEROWANIA"):
            st.session_state.view = "admin_panel"
            st.rerun()

    if st.button("Wyloguj"):
        st.session_state.clear()
        st.query_params.clear()
        st.session_state.view = "login"
        st.rerun()