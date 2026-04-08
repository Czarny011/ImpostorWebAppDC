import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v2", page_icon="🎭", layout="centered")

# --- STYLE CSS ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -10px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .status-box {{ padding: 15px; border-radius: 10px; background: #262730; border-left: 5px solid #ff4b4b; margin: 10px 0; }}
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE Z GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_sheet(name):
    try:
        df = conn.read(worksheet=name, ttl=0)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()


def save_sheet(name, df):
    conn.update(worksheet=name, data=df)


# --- STAN GLOBALNY ---
@st.cache_resource
def get_global_state():
    # Inicjalizacja danych z chmury
    p_df = load_sheet("gracze")
    players = p_df.to_dict('records') if not p_df.empty else []
    return {
        'players': players,
        'game_state': 'WAITING',
        'current_word': '',
        'current_hint': '',
        'impostors': [],
        'participants': [],
        'reg_counter': random.randint(1, 9999)
    }


gs = get_global_state()
st_autorefresh(interval=3000, key="global_refresh")

# --- LOGIKA AUTOLOGOWANIA ---
if 'logged_user' not in st.session_state:
    q_user = st.query_params.get("gracz")
    if q_user and q_user != ADMIN_USER:
        if any(x['login'] == q_user for x in gs['players']):
            st.session_state.logged_user = q_user
            st.session_state.view = "game_room"

if 'view' not in st.session_state:
    st.session_state.view = "login"


def draw_branding():
    st.markdown("<span class='brand-text'>by D.CZ.</span>", unsafe_allow_html=True)


# --- EKRAN 1: LOGOWANIE ---
if st.session_state.view == "login":
    st.markdown("<h1 class='impostor-title'>IMPOSTOR</h1>", unsafe_allow_html=True)
    draw_branding()

    u = st.text_input("Użytkownik", placeholder="Twój nick")
    p = st.text_input("Hasło", type="password", placeholder="•••••")

    if st.button("ZALOGUJ"):
        if u == ADMIN_USER and p == ADMIN_PASSWORD:
            st.session_state.logged_user = ADMIN_USER
            st.session_state.view = "admin_panel"
            st.rerun()
        else:
            match = next((x for x in gs['players'] if x['login'] == u and x['pwd'] == p), None)
            if match:
                st.session_state.logged_user = u
                st.session_state.view = "game_room"
                st.query_params["gracz"] = u
                st.rerun()
            else:
                st.error("Błędny login lub hasło!")

# --- EKRAN 2: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    st.title("⚙️ Panel Admina")
    draw_branding()

    menu = st.tabs(["🎮 Gra", "👥 Gracze", "📖 Baza haseł", "📜 Logi"])

    with menu[0]:  # GRA
        if gs['game_state'] == 'WAITING':
            all_nicks = [p['login'] for p in gs['players']]
            selected = st.multiselect("Wybierz graczy do rundy", all_nicks, default=all_nicks)
            if st.button("🚀 START"):
                words_df = load_sheet("baza_hasel")
                if not words_df.empty and len(selected) >= 3:
                    row = words_df.sample(1).iloc[0]
                    gs.update({
                        'current_word': row['Hasło'],
                        'current_hint': row['Podpowiedź'],
                        'participants': selected,
                        'impostors': [random.choice(selected)],
                        'game_state': 'PLAYING'
                    })
                    st.rerun()
                else:
                    st.warning("Potrzeba min. 3 graczy i haseł w bazie!")
        else:
            if st.button("🛑 ZAKOŃCZ RUNDĘ"):
                # Zapis do logów
                log_entry = pd.DataFrame([{"Data": datetime.now().strftime("%H:%M"), "Impostor": gs['impostors'][0],
                                           "Hasło": gs['current_word']}])
                save_sheet("logi", pd.concat([load_sheet("logi"), log_entry], ignore_index=True))
                gs['game_state'] = 'WAITING'
                st.rerun()

    with menu[1]:  # GRACZE
        st.subheader("Zarządzaj osobami")
        # Usuwanie pojedyncze
        for i, pl in enumerate(gs['players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {pl['login']}")
            if c2.button("Usuń", key=f"del_{pl['login']}"):
                gs['players'].pop(i)
                save_sheet("gracze", pd.DataFrame(gs['players']))
                st.rerun()

        st.divider()
        st.write("Dodaj nowego gracza")
        new_n = st.text_input("Nick", key=f"n_{gs['reg_counter']}")
        new_p = st.text_input("Hasło", type="password", key=f"p_{gs['reg_counter']}")
        if st.button("➕ DODAJ"):
            if new_n:
                gs['players'].append({'login': new_n, 'pwd': new_p, 'score': 0})
                save_sheet("gracze", pd.DataFrame(gs['players']))
                gs['reg_counter'] += 1
                st.rerun()

    with menu[2]:  # BAZA HASEŁ
        st.subheader("Podgląd haseł z Google Sheets")
        st.dataframe(load_sheet("baza_hasel"), use_container_width=True)

    with menu[3]:  # LOGI
        st.subheader("Historia gier")
        logs = load_sheet("logi")
        st.table(logs)
        if not logs.empty and st.button("Wyczyść logi"):
            save_sheet("logi", pd.DataFrame(columns=["Data", "Impostor", "Hasło"]))
            st.rerun()

    if st.button("WYLOGUJ"):
        st.session_state.clear()
        st.query_params.clear()
        st.session_state.view = "login"
        st.rerun()

# --- EKRAN 3: ARENA GRY (DLA GRACZA) ---
elif st.session_state.view == "game_room":
    st.markdown("<h2 style='text-align:center;'>🎭 ARENA</h2>", unsafe_allow_html=True)
    draw_branding()

    user = st.session_state.logged_user
    st.write(f"Witaj, **{user}**!")

    if gs['game_state'] == 'WAITING':
        st.info("Oczekiwanie na ruch Admina...")
        # Ranking
        st.subheader("🏆 Ranking")
        rdf = pd.DataFrame(gs['players'])
        if not rdf.empty:
            st.table(rdf[['login', 'score']].sort_values(by='score', ascending=False))

    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='status-box'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                st.write(f"Podpowiedź: **{gs['current_hint']}**")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Twoje słowo: **{gs['current_word']}**")
                st.write(f"Podpowiedź: {gs['current_hint']}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Pauzujesz w tej rundzie.")

    if st.button("Wyloguj"):
        st.session_state.clear()
        st.query_params.clear()
        st.session_state.view = "login"
        st.rerun()