import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v3.9", page_icon="🎭", layout="centered")

# --- STYLE CSS ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ padding: 20px; border-radius: 15px; background: #262730; border: 2px solid #ff4b4b; text-align: center; margin-bottom: 10px; }}
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE Z BAZĄ ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_sheet(name, force=False):
    """Pobiera dane z Google Sheets z obsługą limitów (Quota)"""
    # Jeśli nie wymuszamy odświeżenia, używamy cache'u 60 sekund
    ttl_val = "0s" if force else "60s"
    try:
        df = conn.read(worksheet=name, ttl=ttl_val)
        if df is not None and not df.empty:
            return df.dropna(how='all').reset_index(drop=True)
        return pd.DataFrame()
    except Exception as e:
        if "429" in str(e):
            st.warning("⏳ Google Sheets ogranicza dostęp (zbyt dużo zapytań). Czekam na odblokowanie...")
        else:
            st.error(f"Błąd bazy: {e}")
        return pd.DataFrame()


def save_sheet(name, df):
    try:
        conn.update(worksheet=name, data=df)
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_gs():
    p_df = load_sheet("gracze", force=True)
    players = p_df.to_dict('records') if not p_df.empty else []

    if not any(p['login'] == ADMIN_USER for p in players):
        players.append({'login': ADMIN_USER, 'pwd': ADMIN_PASSWORD, 'score': 0})

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
        'reg_counter': 0,
        'loaded_words': pd.DataFrame()
    }


gs = get_gs()

# Zabezpieczenie przed KeyError
if 'loaded_words' not in gs: gs['loaded_words'] = pd.DataFrame()
if 'players' not in gs: gs['players'] = []

# Zwiększony interwał do 5 sekund, żeby nie blokować API
st_autorefresh(interval=5000, key="global_refresh")

# --- LOGIKA LOGOWANIA ---
if 'logged_user' not in st.session_state:
    q_user = st.query_params.get("gracz")
    if q_user:
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
        valid_user = (u == ADMIN_USER and p == ADMIN_PASSWORD) or any(
            x['login'] == u and x['pwd'] == p for x in gs['players'])
        if valid_user:
            st.session_state.logged_user = u
            st.session_state.view = "game_room"
            st.query_params["gracz"] = u
            st.rerun()
        else:
            st.error("Błędne dane!")

# --- EKRAN 2: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    draw_header("ADMIN")
    t1, t2, t3, t4 = st.tabs(["🎮 Sterowanie", "👥 Gracze", "📖 Baza haseł", "📜 Logi"])

    with t1:
        st.subheader("Ustawienia rundy")
        gs['settings']['impostors'] = st.slider("Liczba Impostorów", 1, 3, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Podpowiedzi dla Impostorów", gs['settings']['hints'])

        all_nicks = [p['login'] for p in gs['players']]
        selected = st.multiselect("Gracze w rundzie", all_nicks, default=all_nicks)

        st.divider()

        # Sekcja haseł
        if gs['loaded_words'].empty:
            st.info("📥 Baza nie jest wczytana. Kliknij przycisk poniżej.")
            if st.button("WCZYTAJ HASŁA Z GOOGLE SHEETS"):
                df_h = load_sheet("baza_hasel", force=True)
                if not df_h.empty:
                    gs['loaded_words'] = df_h
                    st.success("Wczytano!")
                    st.rerun()
        else:
            st.success(f"✅ Gotowe: {len(gs['loaded_words'])} haseł.")
            if st.button("🔄 ODŚWIEŻ BAZĘ"):
                gs['loaded_words'] = pd.DataFrame()
                st.rerun()

            if gs['game_state'] == 'WAITING' and st.button("🚀 ROZPOCZNIJ RUNDĘ", type="primary"):
                valid = gs['loaded_words'][gs['loaded_words']["Hasło"].notna()]
                if not valid.empty:
                    row = valid.sample(1).iloc[0]
                    gs.update({
                        'current_word': str(row['Hasło']),
                        'current_hint': str(row['Podpowiedź']) if 'Podpowiedź' in row else "",
                        'participants': selected,
                        'impostors': random.sample(selected, min(len(selected), gs['settings']['impostors'])),
                        'game_state': 'PLAYING', 'votes_again': {}, 'votes_impostor': {}
                    })
                    st.session_state.view = "game_room";
                    st.rerun()

    with t2:
        st.subheader("Gracze")
        if st.button("RESET PUNKTÓW"):
            for p in gs['players']: p['score'] = 0
            save_sheet("gracze", pd.DataFrame(gs['players']));
            st.rerun()

        for i, pl in enumerate(gs['players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"{pl['login']} ({pl.get('score', 0)} pkt)")
            if pl['login'] != ADMIN_USER and c2.button("Usuń", key=f"del_{i}"):
                gs['players'].pop(i);
                save_sheet("gracze", pd.DataFrame(gs['players']));
                st.rerun()

        st.divider()
        nu = st.text_input("Nick")
        np = st.text_input("Hasło", type="password")
        if st.button("DODAJ GRACZA"):
            gs['players'].append({'login': nu.strip(), 'pwd': np, 'score': 0})
            save_sheet("gracze", pd.DataFrame(gs['players']));
            st.rerun()

    with t3:
        st.subheader("Edytuj arkusz bezpośrednio")
        b_df = load_sheet("baza_hasel", force=True)
        new_baza = st.data_editor(b_df, num_rows="dynamic", use_container_width=True)
        if st.button("ZAPISZ DO ARKUSZA"):
            save_sheet("baza_hasel", new_baza)
            gs['loaded_words'] = pd.DataFrame();
            st.rerun()

    with t4:
        st.dataframe(load_sheet("logi", force=True), use_container_width=True)

# --- EKRAN 3: ARENA ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user

    if gs['game_state'] == 'WAITING':
        st.subheader("🏆 RANKING")
        st.table(pd.DataFrame(gs['players'])[['login', 'score']].sort_values(by='score', ascending=False))
        st.info("Czekaj na Admina...")

    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='role-card'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                if gs['settings']['hints']: st.write(f"Podpowiedź: **{gs['current_hint']}**")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Hasło: **{gs['current_word']}**")
            st.markdown("</div>", unsafe_allow_html=True)

        if user == ADMIN_USER and st.button("🔔 GŁOSOWANIE", type="primary"):
            gs['game_state'] = 'VOTING_AGAIN';
            st.rerun()

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Gramy dalej to samo?")
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()
        if user == ADMIN_USER and st.button("PODLICZ"):
            yes = sum(1 for v in gs['votes_again'].values() if v)
            gs['game_state'] = 'PLAYING' if yes > (len(gs['votes_again']) / 2) else 'VOTING_IMPOSTOR'
            gs['votes_again'] = {};
            st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        others = [p for p in gs['participants'] if p != user]
        choice = st.selectbox("Wskaż", others) if others else None
        if st.button("Głosuj") and choice:
            gs['votes_impostor'][user] = choice;
            st.success("Oddano głos!")

        if user == ADMIN_USER and st.button("🏆 WYNIKI"):
            summary = []
            for p in gs['players']:
                if p['login'] in gs['participants']:
                    pts = 0
                    if p['login'] in gs['impostors']:
                        if not any(v == p['login'] for v in gs['votes_impostor'].values()): pts = 2
                    else:
                        if gs['votes_impostor'].get(p['login']) in gs['impostors']: pts = 1
                    p['score'] = int(p.get('score', 0)) + pts
                    summary.append(f"{p['login']}: +{pts}")

            new_l = pd.DataFrame([{"Data": datetime.now().strftime("%H:%M"), "Wynik": " | ".join(summary)}])
            save_sheet("logi", pd.concat([load_sheet("logi", force=True), new_l], ignore_index=True))
            save_sheet("gracze", pd.DataFrame(gs['players']))
            gs['game_state'] = 'WAITING';
            gs['votes_impostor'] = {};
            st.rerun()

    if user == ADMIN_USER:
        st.divider()
        if st.button("⚙️ PANEL ADMINA"): st.session_state.view = "admin_panel"; st.rerun()
    if st.button("Wyloguj"):
        st.session_state.clear();
        st.query_params.clear();
        st.rerun()