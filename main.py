import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v4.6", page_icon="🎭", layout="centered")

# --- STYLE CSS ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ padding: 20px; border-radius: 15px; background: #262730; border: 2px solid #ff4b4b; text-align: center; margin-bottom: 10px; }}
    .footer {{ position: fixed; left: 0; bottom: 0; width: 100%; background-color: transparent; color: #666; text-align: center; font-size: 0.8rem; padding: 10px; }}
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
        # Wyłączamy cache całkowicie dla haseł, aby system zawsze widział kolumnę 'Użyte'
        df = conn.read(worksheet="baza_hasel", ttl=0)
        return df.dropna(how='all').reset_index(drop=True) if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()


def save_data(name, df):
    try:
        conn.update(worksheet=name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Błąd zapisu {name}: {e}")


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def init_game_state():
    return {
        'game_state': 'WAITING',
        'current_word': '',
        'current_hint': '',
        'impostors': [],
        'participants': [],
        'votes_again': {},
        'votes_impostor': {},
        'settings': {"impostors": 1, "hints": True},
        'cached_players': []
    }


gs = init_game_state()

# SYNCHRONIZACJA GRACZY
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
        # Jeśli kolumny 'Użyte' nie ma (np. błąd odczytu), tworzymy ją wirtualnie
        if 'Użyte' not in w_df.columns:
            w_df['Użyte'] = ""

        # Filtrujemy tylko nieużyte hasła
        available_words = w_df[w_df['Użyte'].astype(str).str.upper() != "TAK"]

        # Jeśli brak haseł, automatycznie resetujemy wszystko w arkuszu
        if available_words.empty:
            w_df['Użyte'] = ""
            save_data("baza_hasel", w_df)
            available_words = w_df

        if not available_words.empty:
            active_list = gs['participants'] if gs['participants'] else [p['login'] for p in gs['cached_players']]

            # Losujemy hasło
            idx = available_words.sample(1).index[0]
            row = w_df.loc[idx]

            # Oznaczamy jako użyte w arkuszu
            w_df.at[idx, 'Użyte'] = "TAK"
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
    st.markdown("<span class='brand-text'>by D.CZ.</span>", unsafe_allow_html=True)


# --- EKRAN 1: LOGOWANIE ---
if st.session_state.view == "login":
    draw_header()
    u = st.text_input("Login")
    p = st.text_input("Hasło", type="password")
    if st.button("Zaloguj"):
        if (u == ADMIN_USER and p == ADMIN_PASSWORD) or any(
                x['login'] == u and x['pwd'] == p for x in gs['cached_players']):
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
        gs['settings']['impostors'] = st.slider("Liczba Impostorów", 1, 3, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Podpowiedzi dla Impostorów", gs['settings']['hints'])
        all_nicks = [p['login'] for p in gs['cached_players']]
        gs['participants'] = st.multiselect("Gracze w rundzie", all_nicks, default=all_nicks)

        st.divider()
        if gs['game_state'] == 'PLAYING':
            if st.button("🔙 POWRÓT DO TRWAJĄCEJ RUNDY", type="primary"):
                st.session_state.view = "game_room"
                st.rerun()
            if st.button("🔄 WYMUSZ NOWĄ RUNDĘ (NOWE HASŁO)"):
                if start_new_round():
                    st.session_state.view = "game_room"
                    st.rerun()
        else:
            if st.button("🚀 ROZPOCZNIJ RUNDĘ", type="primary"):
                if start_new_round():
                    st.session_state.view = "game_room"
                    st.rerun()

        st.divider()
        if st.button("♻️ ZRESETUJ PULĘ HASEŁ (CZYŚCI 'UŻYTE')"):
            w_df = get_words_from_sheet()
            if 'Użyte' in w_df.columns:
                w_df['Użyte'] = ""
                save_data("baza_hasel", w_df)
                st.success("Pula haseł została zresetowana!")

    with t2:
        st.subheader("Dodaj Nowego Gracza")
        with st.form("add_player_form", clear_on_submit=True):
            new_login = st.text_input("Login gracza")
            new_pwd = st.text_input("Hasło gracza", type="password")
            submit_button = st.form_submit_button("➕ DODAJ GRACZA")
            if submit_button:
                if new_login and new_pwd:
                    if not any(p['login'] == new_login for p in gs['cached_players']):
                        gs['cached_players'].append({'login': new_login, 'pwd': new_pwd, 'score': 0})
                        save_data("gracze", pd.DataFrame(gs['cached_players']))
                        st.success(f"Gracz {new_login} dodany!")
                        st.rerun()
                    else:
                        st.error("Gracz o tym loginie już istnieje!")
                else:
                    st.warning("Uzupełnij login i hasło!")

        st.divider()
        if st.button("🔄 ODŚWIEŻ LISTĘ Z GOOGLE"):
            p_df = conn.read(worksheet="gracze", ttl=0)
            if not p_df.empty: gs['cached_players'] = p_df.to_dict('records')
            st.cache_data.clear()
            st.rerun()
        if st.button("🔥 ZERUJ PUNKTY"):
            for p in gs['cached_players']: p['score'] = 0
            save_data("gracze", pd.DataFrame(gs['cached_players']))
            st.rerun()
        for i, pl in enumerate(gs['cached_players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"{pl['login']} - {int(float(pl.get('score', 0)))} pkt")
            if pl['login'] != ADMIN_USER and c2.button("Usuń", key=f"del_{i}"):
                gs['cached_players'].pop(i)
                save_data("gracze", pd.DataFrame(gs['cached_players']))
                st.rerun()

    with t3:
        curr_words = get_words_from_sheet()
        new_w = st.data_editor(curr_words, num_rows="dynamic", use_container_width=True)
        if st.button("ZAPISZ ZMIANY W BAZIE"):
            save_data("baza_hasel", new_w)
            st.rerun()

    with t4:
        st.dataframe(conn.read(worksheet="logi", ttl="1m"), use_container_width=True)

# --- EKRAN 3: ARENA ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user

    if gs['game_state'] == 'WAITING':
        st.subheader("🏆 RANKING")
        df_rank = pd.DataFrame(gs['cached_players'])[['login', 'score']].sort_values(by='score', ascending=False)
        df_rank['score'] = df_rank['score'].apply(lambda x: int(float(x)))
        st.table(df_rank)
        if user == ADMIN_USER:
            st.divider()
            if st.button("🚀 ROZPOCZNIJ RUNDĘ", type="primary"):
                if start_new_round():
                    st.rerun()
        else:
            st.info("Czekaj na start kolejnej tury przez Admina...")

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
        if user == ADMIN_USER:
            st.divider()
            c1, c2 = st.columns(2)
            if c1.button("🔔 GŁOSOWANIE", type="primary"):
                gs['game_state'] = 'VOTING_AGAIN'
                st.rerun()
            if c2.button("🔄 RESTART RUNDY"):
                if start_new_round():
                    st.rerun()

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Gramy dalej to samo?")
        if user == ADMIN_USER:
            st.info(f"📊 Oddano głosów: **{len(gs['votes_again'])} / {len(gs['participants'])}**")
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()
        if user == ADMIN_USER and st.button("PODLICZ"):
            yes = sum(1 for v in gs['votes_again'].values() if v)
            gs['game_state'] = 'PLAYING' if yes > (len(gs['votes_again']) / 2) else 'VOTING_IMPOSTOR'
            gs['votes_again'] = {}
            st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        if user == ADMIN_USER:
            st.info(f"📊 Oddano głosów: **{len(gs['votes_impostor'])} / {len(gs['participants'])}**")
        others = [p for p in gs['participants'] if p != user]
        choice = st.selectbox("Wskaż", others) if others else None
        if st.button("Głosuj") and choice:
            gs['votes_impostor'][user] = choice
            st.success("Głos oddany!")
        if user == ADMIN_USER and st.button("🏆 PODLICZ I POKAŻ RANKING"):
            results_summary = []
            voted_names = list(gs['votes_impostor'].values())
            for p in gs['cached_players']:
                if p['login'] in gs['participants']:
                    added_pts = 0
                    if p['login'] in gs['impostors']:
                        votes_on_him = voted_names.count(p['login'])
                        added_pts = (len(gs['participants']) - 1) - votes_on_him
                    else:
                        voted_for = gs['votes_impostor'].get(p['login'])
                        if voted_for in gs['impostors']:
                            added_pts = 2
                    p['score'] = int(float(p.get('score', 0))) + added_pts
                    results_summary.append(f"{p['login']}: +{added_pts}")
            log_entry = {"Data": datetime.now().strftime("%H:%M"), "Hasło": gs['current_word'],
                         "Impostorzy": ", ".join(gs['impostors']), "Wynik": " | ".join(results_summary)}
            try:
                current_logs = conn.read(worksheet="logi", ttl=0)
                updated_logs = pd.concat([current_logs, pd.DataFrame([log_entry])], ignore_index=True)
                save_data("logi", updated_logs)
            except:
                save_data("logi", pd.DataFrame([log_entry]))
            save_data("gracze", pd.DataFrame(gs['cached_players']))
            gs['game_state'] = 'WAITING'
            gs['votes_impostor'] = {}
            st.rerun()

    if user == ADMIN_USER:
        st.divider()
        if st.button("⚙️ PANEL ADMINA"):
            st.session_state.view = "admin_panel"
            st.rerun()
    if st.button("Wyloguj"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

st.markdown('<div class="footer">©Impostor Web App v1 by Dawid Czarnota</div>', unsafe_allow_html=True)