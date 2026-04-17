import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="IMPOSTOR NEON", page_icon="🎭", layout="centered")

# --- STYLE CSS (Cyberpunk Neon Edition) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');

    .stApp { 
        background: radial-gradient(circle, #1a1a2e 0%, #0f0f1b 100%); 
        color: #e0e0e0; 
    }

    .impostor-title { 
        font-family: 'Orbitron', sans-serif; 
        font-size: 3.5rem; 
        font-weight: 700; 
        text-align: center; 
        text-transform: uppercase; 
        letter-spacing: 5px; 
        color: #fff; 
        text-shadow: 0 0 10px #ff4b4b, 0 0 20px #ff4b4b; 
        margin-bottom: 0px; 
        animation: pulsate 2.5s infinite alternate; 
    }

    @keyframes pulsate { 100% { text-shadow: 0 0 20px #ff4b4b, 0 0 40px #ff4b4b; } }

    .brand-text { 
        font-family: 'Orbitron', sans-serif; 
        font-size: 0.8rem; 
        color: #00d4ff; 
        text-align: center; 
        display: block; 
        margin-top: -10px; 
        margin-bottom: 30px; 
        letter-spacing: 2px; 
    }

    .role-card { 
        padding: 30px; 
        border-radius: 20px; 
        background: rgba(255, 255, 255, 0.05); 
        backdrop-filter: blur(10px); 
        text-align: center; 
        margin: 20px 0; 
        border: 2px solid #444; 
        animation: fadeIn 0.8s ease-out; 
    }

    .impostor-card { border-color: #ff4b4b; box-shadow: 0 0 15px rgba(255, 75, 75, 0.3); }
    .player-card { border-color: #00d4ff; box-shadow: 0 0 15px rgba(0, 212, 255, 0.3); }

    @keyframes fadeIn { 
        from { opacity: 0; transform: translateY(10px); } 
        to { opacity: 1; transform: translateY(0); } 
    }

    .stButton>button { 
        width: 100%; 
        border-radius: 10px; 
        height: 3.5em; 
        background: linear-gradient(45deg, #ff4b4b, #ff7675); 
        color: white; 
        font-weight: bold; 
        border: none; 
        text-transform: uppercase; 
        transition: all 0.2s ease; 
        letter-spacing: 1px;
    }

    .stButton>button:hover { 
        transform: translateY(-2px); 
        box-shadow: 0 6px 20px rgba(255, 75, 75, 0.4); 
    }

    .stButton>button:active { transform: translateY(2px); }

    .footer { 
        position: fixed; 
        left: 0; 
        bottom: 0; 
        width: 100%; 
        background: rgba(0,0,0,0.5); 
        color: #444; 
        text-align: center; 
        font-size: 0.7rem; 
        padding: 5px; 
    }

    .stProgress > div > div > div > div { background-color: #00d4ff; }

    [data-testid="stTable"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE ---
conn = st.connection("gsheets", type=GSheetsConnection)


@st.cache_data(ttl=60)
def get_players_from_sheet():
    try:
        df = conn.read(worksheet="gracze", ttl=0)
        return df.dropna(how='all').reset_index(drop=True) if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()


def get_words_from_sheet():
    try:
        df = conn.read(worksheet="baza_hasel", ttl=0)
        return df.dropna(how='all').reset_index(drop=True) if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()


def save_data(name, df):
    try:
        df = df.fillna("")
        conn.update(worksheet=name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Błąd zapisu {name}: {e}")


# --- STAN GRY ---
@st.cache_resource
def init_game_state():
    return {
        'game_state': 'WAITING', 'current_word': '', 'current_hint': '', 'impostors': [],
        'last_impostors': [],  # Nowe pole do przechowywania info o poprz. rundzie
        'participants': [], 'votes_again': {}, 'votes_impostor': {},
        'settings': {"impostors": 1, "hints": True}, 'cached_players': []
    }


gs = init_game_state()

if not gs['cached_players']:
    p_df = get_players_from_sheet()
    if not p_df.empty:
        gs['cached_players'] = p_df.to_dict('records')
    if not any(p['login'] == ADMIN_USER for p in gs['cached_players']):
        gs['cached_players'].append({'login': ADMIN_USER, 'pwd': ADMIN_PASSWORD, 'score': 0})

st_autorefresh(interval=5000, key="global_refresh")


def start_new_round():
    w_df = get_words_from_sheet()
    if not w_df.empty:
        if 'Użyte' not in w_df.columns:
            w_df['Użyte'] = 0
        w_df['Użyte'] = pd.to_numeric(w_df['Użyte'], errors='coerce').fillna(0)
        available_words = w_df[w_df['Użyte'] != 1]
        if available_words.empty:
            w_df['Użyte'] = 0
            save_data("baza_hasel", w_df)
            available_words = w_df
        if not available_words.empty:
            active_list = gs['participants'] if gs['participants'] else [p['login'] for p in gs['cached_players']]
            idx = available_words.sample(1).index[0]
            row = w_df.loc[idx]
            w_df.at[idx, 'Użyte'] = 1
            save_data("baza_hasel", w_df)
            gs.update({
                'current_word': str(row['Hasło']),
                'current_hint': str(row['Podpowiedź']) if 'Podpowiedź' in row else "",
                'participants': active_list,
                'impostors': random.sample(active_list, min(len(active_list), gs['settings']['impostors'])),
                'game_state': 'PLAYING', 'votes_again': {}, 'votes_impostor': {}
            })
            return True
    return False


# --- LOGIKA WIDOKÓW ---
if 'logged_user' not in st.session_state:
    q_user = st.query_params.get("gracz")
    if q_user:
        st.session_state.logged_user = q_user
        st.session_state.view = "game_room"

if 'view' not in st.session_state:
    st.session_state.view = "login"


def draw_header(title="IMPOSTOR"):
    st.markdown(f"<h1 class='impostor-title'>{title}</h1>", unsafe_allow_html=True)
    st.markdown("<span class='brand-text'>BY D.CZ.</span>", unsafe_allow_html=True)


# --- 1. LOGOWANIE ---
if st.session_state.view == "login":
    draw_header()
    u = st.text_input("👤 LOGIN")
    p = st.text_input("🔑 HASŁO", type="password")
    if st.button("ZALOGUJ DO SYSTEMU"):
        if (u == ADMIN_USER and p == ADMIN_PASSWORD) or any(
                x['login'] == u and x['pwd'] == p for x in gs['cached_players']):
            st.session_state.logged_user = u
            st.session_state.view = "game_room"
            st.query_params["gracz"] = u
            st.rerun()
        else:
            st.error("Błąd autoryzacji!")

# --- 2. PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    draw_header("ADMIN")
    t1, t2, t3 = st.tabs(["🎮 Sterowanie", "👥 Gracze", "📖 Baza"])
    with t1:
        gs['settings']['impostors'] = st.slider("Liczba Impostorów", 1, 3, gs['settings']['impostors'])
        gs['participants'] = st.multiselect("Gracze w rundzie", [p['login'] for p in gs['cached_players']],
                                            default=[p['login'] for p in gs['cached_players']])
        if gs['game_state'] == 'PLAYING':
            if st.button("🔙 POWRÓT DO ARENY"): st.session_state.view = "game_room"; st.rerun()
            if st.button("🔄 WYMUSZ NOWĄ RUNDĘ"):
                if start_new_round(): st.session_state.view = "game_room"; st.rerun()
        else:
            if st.button("🚀 URUCHOM RUNDĘ", type="primary"):
                if start_new_round(): st.session_state.view = "game_room"; st.rerun()
        st.divider()
        if st.button("♻️ RESETUJ PULĘ HASEŁ"):
            w_df = get_words_from_sheet()
            w_df['Użyte'] = 0
            save_data("baza_hasel", w_df)
            st.success("Baza zresetowana!")
    with t2:
        col_a, col_b = st.columns(2)
        if col_a.button("🔥 ZERUJ PUNKTY"):
            for p in gs['cached_players']: p['score'] = 0
            save_data("gracze", pd.DataFrame(gs['cached_players']))
            st.rerun()
        if col_b.button("🔄 ODŚWIEŻ Z GOOGLE"):
            st.cache_data.clear()
            p_df = get_players_from_sheet()
            if not p_df.empty: gs['cached_players'] = p_df.to_dict('records')
            st.rerun()
        st.divider()
        with st.form("add_p", clear_on_submit=True):
            nl, np = st.text_input("Login"), st.text_input("Hasło", type="password")
            if st.form_submit_button("DODAJ"):
                if nl and np:
                    gs['cached_players'].append({'login': nl, 'pwd': np, 'score': 0})
                    save_data("gracze", pd.DataFrame(gs['cached_players']))
                    st.rerun()
        for i, pl in enumerate(gs['cached_players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"🔹 {pl['login']} ({int(float(pl.get('score', 0)))} PKT)")
            if pl['login'] != ADMIN_USER and c2.button("X", key=f"del_{i}"):
                gs['cached_players'].pop(i)
                save_data("gracze", pd.DataFrame(gs['cached_players']))
                st.rerun()
    with t3:
        new_w = st.data_editor(get_words_from_sheet(), num_rows="dynamic", use_container_width=True)
        if st.button("ZAPISZ BAZĘ"): save_data("baza_hasel", new_w); st.rerun()

# --- 3. ARENA ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user
    if gs['game_state'] == 'WAITING':
        st.subheader("🏆 RANKING SYSTEMU")
        df_rank = pd.DataFrame(gs['cached_players'])[['login', 'score']].sort_values(by='score', ascending=False)
        df_rank['score'] = df_rank['score'].apply(lambda x: int(float(x)))
        st.table(df_rank)

        # WYŚWIETLANIE INFO O IMPOSTORZE Z POPRZEDNIEJ RUNDY
        if gs.get('last_impostors'):
            st.markdown(
                f"<div style='text-align:center; color:#ff4b4b; font-weight:bold; border:1px solid #ff4b4b; border-radius:10px; padding:10px;'>Ostatni Impostor: {', '.join(gs['last_impostors'])}</div>",
                unsafe_allow_html=True)

        if user == ADMIN_USER and st.button("🚀 START RUNDY"):
            if start_new_round(): st.rerun()
    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            if user in gs['impostors']:
                st.markdown(f"<div class='role-card impostor-card'><h3>JESTEŚ IMPOSTOREM! 😈</h3>",
                            unsafe_allow_html=True)
                if gs['settings']['hints']: st.write(f"PODPOWIEDŹ: {gs['current_hint']}")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div class='role-card player-card'><h3>JESTEŚ GRACZEM 😇</h3><p>HASŁO: <br><span style='font-size: 1.5rem; color: #00d4ff;'>{gs['current_word']}</span></p></div>",
                    unsafe_allow_html=True)
        if user == ADMIN_USER:
            c1, c2 = st.columns(2)
            if c1.button("🔔 GŁOSOWANIE"): gs['game_state'] = 'VOTING_AGAIN'; st.rerun()
            if c2.button("🔄 RESTART"):
                if start_new_round(): st.rerun()
    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Głosowanie: Kontynuuj?")
        st.progress(len(gs['votes_again']) / len(gs['participants']))
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()
        if user == ADMIN_USER and st.button("PODSUMUJ"):
            yes = sum(1 for v in gs['votes_again'].values() if v)
            gs['game_state'] = 'PLAYING' if yes > (len(gs['votes_again']) / 2) else 'VOTING_IMPOSTOR'
            gs['votes_again'] = {};
            st.rerun()
    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Wskaż Impostora!")
        st.progress(len(gs['votes_impostor']) / len(gs['participants']))
        others = [p for p in gs['participants'] if p != user]
        choice = st.selectbox("CEL:", others) if others else None
        if st.button("ZATWIERDŹ") and choice: gs['votes_impostor'][user] = choice; st.success("OK")
        if user == ADMIN_USER and st.button("🏆 PODLICZ WYNIKI"):
            voted = list(gs['votes_impostor'].values())
            for p in gs['cached_players']:
                if p['login'] in gs['participants']:
                    pts = ((len(gs['participants']) - 1) - voted.count(p['login'])) if p['login'] in gs[
                        'impostors'] else (2 if gs['votes_impostor'].get(p['login']) in gs['impostors'] else 0)
                    p['score'] = int(float(p.get('score', 0))) + pts

            # ZAPISUJEMY KTO BYŁ IMPOSTOREM PRZED RESETEM
            gs['last_impostors'] = gs['impostors']
            save_data("gracze", pd.DataFrame(gs['cached_players']))
            gs['game_state'] = 'WAITING';
            gs['votes_impostor'] = {};
            st.rerun()

    if user == ADMIN_USER and st.button("⚙️ PANEL SYSTEMU"): st.session_state.view = "admin_panel"; st.rerun()
    if st.button("WYLOGUJ"): st.session_state.clear(); st.rerun()
st.markdown('<div class="footer"> © 2026 IMPOSTOR WEB APP v1 by Dawid Czarnota</div>', unsafe_allow_html=True)