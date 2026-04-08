import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Game Cloud", page_icon="🎭", layout="centered")

# --- STYLE CSS ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 15px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.75rem; color: #777; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3.5rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ background: #262730; padding: 20px; border-radius: 15px; border: 2px solid #ff4b4b; text-align: center; margin: 20px 0; }}
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE Z BAZĄ ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_sheet(name):
    try:
        return conn.read(worksheet=name, ttl=0).dropna(how='all')
    except:
        return pd.DataFrame()


def save_sheet(name, df):
    conn.update(worksheet=name, data=df)


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_gs():
    return {
        'players': load_sheet("gracze").to_dict('records'),
        'game_state': 'WAITING',  # WAITING, PLAYING, RESULTS
        'current_word': '',
        'current_hint': '',
        'impostors': [],
        'participants': [],
        'reg_counter': random.randint(1, 999)
    }


gs = get_gs()
st_autorefresh(interval=3000, key="global_refresh")

# --- AUTOLOGOWANIE ---
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


# --- EKRAN: LOGOWANIE ---
if st.session_state.view == "login":
    st.markdown("<h1 class='impostor-title'>IMPOSTOR</h1>", unsafe_allow_html=True)
    draw_branding()
    u = st.text_input("Użytkownik")
    p = st.text_input("Hasło", type="password")
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
                st.error("Błąd logowania")

# --- EKRAN: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    st.title("⚙️ Zarządzanie")
    draw_branding()

    c1, c2 = st.columns(2)
    if c1.button("👥 GRACZE"): st.session_state.view = "manage_players"; st.rerun()
    if c2.button("🎮 ARENA"): st.session_state.view = "game_room"; st.rerun()

    st.divider()
    st.subheader("🚀 Kontrola Gry")

    if gs['game_state'] == 'WAITING':
        # Wybór graczy do rundy
        all_nicks = [p['login'] for p in gs['players']]
        selected = st.multiselect("Wybierz graczy do rundy:", all_nicks, default=all_nicks)

        if st.button("LOSUJ HASŁO I START"):
            if len(selected) >= 3:
                # 1. Pobierz hasła z Arkusza
                words_df = load_sheet("baza_hasel")
                if not words_df.empty:
                    row = words_df.sample(1).iloc[0]
                    gs['current_word'] = row['Hasło']
                    gs['current_hint'] = row['Podpowiedź']
                    gs['participants'] = selected
                    # 2. Losuj Impostora
                    gs['impostors'] = [random.choice(selected)]
                    gs['game_state'] = 'PLAYING'
                    st.success("Gra wystartowała!")
                    st.rerun()
                else:
                    st.error("Baza haseł w arkuszu jest pusta!")
            else:
                st.warning("Potrzeba min. 3 graczy")

    else:
        if st.button("ZAKOŃCZ RUNDĘ I ZAPISZ LOGI"):
            # Zapis logów do Arkusza
            new_log = pd.DataFrame([{
                "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Impostorzy": ", ".join(gs['impostors']),
                "Słowo": gs['current_word']
            }])
            old_logs = load_sheet("logi")
            save_sheet("logi", pd.concat([old_logs, new_log]))

            gs['game_state'] = 'WAITING'
            st.rerun()

# --- EKRAN: ARENA GRY ---
elif st.session_state.view == "game_room":
    st.markdown("<h2 style='text-align:center;'>🎭 ARENA</h2>", unsafe_allow_html=True)
    draw_branding()

    user = st.session_state.logged_user

    if gs['game_state'] == 'WAITING':
        st.info("Czekamy na start rundy...")
        st.write("Obecnie w bazie:", len(gs['players']), "graczy.")

    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='role-card'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                st.write(f"Podpowiedź dla wszystkich: **{gs['current_hint']}**")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Twoje hasło: **{gs['current_word']}**")
                st.write(f"Podpowiedź: {gs['current_hint']}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Nie bierzesz udziału w tej rundzie. Obserwuj!")

    if st.button("WYLOGUJ"):
        st.session_state.clear()
        st.query_params.clear()
        st.session_state.view = "login"
        st.rerun()

# --- EKRAN: ZARZĄDZANIE GRACZAMI (Kod jak wcześniej...) ---
elif st.session_state.view == "manage_players":
    st.title("👥 Zarządzanie")
    # ... (tutaj kod dodawania/usuwania graczy z poprzedniej wiadomości)
    if st.button("POWRÓT"): st.session_state.view = "admin_panel"; st.rerun()