import streamlit as st
import pandas as pd
import random
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ADMINA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

# --- POŁĄCZENIE Z GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_gsheet_data(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl=0)
    except:
        return pd.DataFrame()


def save_gsheet_data(sheet_name, df):
    conn.update(worksheet=sheet_name, data=df)


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_global_state():
    # Próba wczytania graczy z chmury na start
    try:
        saved_players = load_gsheet_data("gracze").to_dict('records')
    except:
        saved_players = []

    return {
        'players': saved_players,
        'game_state': 'WAITING',  # WAITING, PLAYING, VOTING_IMPOSTOR, SHOWING_RESULTS
        'current_game_data': {},
        'scores': {},
        'votes_impostor': {},
        'reg_counter': random.randint(1, 9999),
        'last_error': None
    }


gs = get_global_state()

# Autoodświeżanie co 3 sekundy, żeby gracze widzieli zmiany
st_autorefresh(interval=3000, key="global_sync")

# --- STYLE UI ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 20px; }
    .stMetric { background: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- NAWIGACJA ---
if 'view' not in st.session_state:
    st.session_state.view = "login"

# --- WIDOK: LOGOWANIE ---
if st.session_state.view == "login":
    st.title("🎭 Impostor Cloud")
    u = st.text_input("Użytkownik")
    p = st.text_input("Hasło", type="password")

    if st.button("Zaloguj"):
        if u == ADMIN_USER and p == ADMIN_PASSWORD:
            st.session_state.logged_user = "ADMIN"
            st.session_state.view = "admin_panel"
            st.rerun()
        else:
            # Szukanie w graczach z Google Sheets
            user_match = next((x for x in gs['players'] if x['login'] == u and x['pwd'] == p), None)
            if user_match:
                st.session_state.logged_user = u
                st.session_state.view = "player_screen"
                st.rerun()
            else:
                st.error("Błędny login lub hasło!")

# --- WIDOK: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    st.title("⚙️ Panel Zarządzania")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("👥 Zarządzaj Graczami"):
            st.session_state.view = "manage_players"
            st.rerun()
    with col2:
        if st.button("🚀 Arena Gry"):
            st.session_state.view = "game_room"
            st.rerun()

    st.divider()
    st.write("### Statystyki Chmury")
    st.write(f"Zarejestrowanych graczy w Google Sheets: **{len(gs['players'])}**")

    if st.button("Wyloguj"):
        st.session_state.view = "login"
        st.rerun()

# --- WIDOK: ZARZĄDZANIE GRACZAMI (Z FIXEM NA GABI) ---
elif st.session_state.view == "manage_players":
    st.title("👥 Lista Graczy")

    # Wyświetlanie obecnych
    if gs['players']:
        df_show = pd.DataFrame(gs['players'])
        st.table(df_show[['login']])
        if st.button("CZYŚĆ WSZYSTKICH (Google Sheets)"):
            gs['players'] = []
            save_gsheet_data("gracze", pd.DataFrame(columns=['login', 'pwd']))
            st.rerun()

    st.divider()
    st.subheader(f"Dodaj gracza nr {len(gs['players']) + 1}")

    # KEY z reg_counter wymusza reset pola po dodaniu
    new_nick = st.text_input("Nick", key=f"n_{gs['reg_counter']}")
    new_pass = st.text_input("Hasło gracza", type="password", key=f"p_{gs['reg_counter']}")

    if st.button("Zapisz w Google Sheets"):
        if new_nick:
            gs['players'].append({'login': new_nick, 'pwd': new_pass})
            save_gsheet_data("gracze", pd.DataFrame(gs['players']))
            gs['reg_counter'] += 1  # TO CZYŚCI POLA
            st.success(f"Dodano {new_nick}!")
            st.rerun()

    if st.button("Powrót"):
        st.session_state.view = "admin_panel"
        st.rerun()

# --- WIDOK: ARENA GRY ---
elif st.session_state.view == "game_room":
    st.title("🎭 Arena")

    if st.session_state.get('logged_user') == "ADMIN":
        st.write("--- TRYB ADMINA ---")
        if gs['game_state'] == 'WAITING':
            if st.button("ROZPOCZNIJ RUNDĘ"):
                # Tutaj logika losowania haseł (do rozbudowy)
                gs['game_state'] = 'PLAYING'
                st.rerun()

        if st.button("RESETUJ GRĘ"):
            gs['game_state'] = 'WAITING'
            st.rerun()

    # Logika dla graczy (podpowiedzi haseł itp.)
    st.write(f"Status gry: **{gs['game_state']}**")

    if st.button("Powrót do menu"):
        st.session_state.view = "admin_panel" if st.session_state.logged_user == "ADMIN" else "login"
        st.rerun()

# --- STOPKA ---
st.markdown(f"""
    <div style='position: fixed; bottom: 10px; width: 100%; text-align: center; color: gray;'>
    Zalogowany: {st.session_state.get('logged_user', 'Gość')} | © 2026 Dawid Czarnota
    </div>
    """, unsafe_allow_html=True)