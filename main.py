import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v3.4", page_icon="🎭", layout="centered")

# --- STYLE CSS ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ padding: 20px; border-radius: 15px; background: #262730; border: 2px solid #ff4b4b; text-align: center; margin-bottom: 10px; }}
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE I FUNKCJE BAZY ---
conn = st.connection("gsheets", type=GSheetsConnection)


def load_sheet(name):
    try:
        df = conn.read(worksheet=name, ttl=0)
        if df is not None:
            return df.dropna(how='all').reset_index(drop=True)
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def save_sheet(name, df):
    try:
        conn.update(worksheet=name, data=df)
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Błąd zapisu ({name}): {e}")


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_gs():
    p_df = load_sheet("gracze")
    players = p_df.to_dict('records') if not p_df.empty else []

    # Upewnij się, że Admin jest na liście graczy w pamięci, by mógł zbierać punkty
    if not any(p['login'] == ADMIN_USER for p in players):
        players.append({'login': ADMIN_USER, 'pwd': ADMIN_PASSWORD, 'score': 0})

    for p in players:
        if 'score' not in p: p['score'] = 0
        p['score'] = int(p['score'])

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

# --- LOGIKA LOGOWANIA ---
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
        if (u == ADMIN_USER and p == ADMIN_PASSWORD) or any(x['login'] == u and x['pwd'] == p for x in gs['players']):
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

        all_nicks = [p['login'] for p in gs['players']]
        selected = st.multiselect("Gracze w rundzie", all_nicks, default=all_nicks)

        if gs['game_state'] == 'WAITING':
            if st.button("🚀 ROZPOCZNIJ RUNDĘ"):
                words_df = load_sheet("baza_hasel")
                if not words_df.empty and "Hasło" in words_df.columns:
                    valid_words = words_df[words_df["Hasło"].str.strip().astype(bool)]
                    if not valid_words.empty:
                        row = valid_words.sample(1).iloc[0]
                        gs.update({
                            'current_word': str(row['Hasło']),
                            'current_hint': str(row['Podpowiedź']) if 'Podpowiedź' in row else "",
                            'participants': selected,
                            'impostors': random.sample(selected, min(len(selected), gs['settings']['impostors'])),
                            'game_state': 'PLAYING', 'votes_again': {}, 'votes_impostor': {}
                        })
                        st.session_state.view = "game_room"
                        st.rerun()
                    else:
                        st.error("Baza haseł jest pusta!")
                else:
                    st.error("Błąd bazy haseł - sprawdź arkusz!")

        if st.button("🏠 POWRÓT DO ARNY"):
            st.session_state.view = "game_room";
            st.rerun()

    with t2:
        st.subheader("Zarządzaj graczami")
        if st.button("🔥 ZERUJ PUNKTY WSZYSTKIM"):
            for p in gs['players']: p['score'] = 0
            save_sheet("gracze", pd.DataFrame(gs['players']))
            st.rerun()

        for i, pl in enumerate(gs['players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {pl['login']} - {pl.get('score', 0)} pkt")
            if pl['login'] != ADMIN_USER and c2.button("Usuń", key=f"del_{pl['login']}"):
                gs['players'].pop(i)
                save_sheet("gracze", pd.DataFrame(gs['players']))
                st.rerun()

        st.divider()
        n_nick = st.text_input("Nowy Nick", key=f"n_{gs['reg_counter']}")
        n_pwd = st.text_input("Hasło", type="password", key=f"p_{gs['reg_counter']}")
        if st.button("DODAJ GRACZA"):
            if n_nick:
                gs['players'].append({'login': n_nick.strip(), 'pwd': n_pwd, 'score': 0})
                save_sheet("gracze", pd.DataFrame(gs['players']))
                gs['reg_counter'] += 1;
                st.rerun()

    with t3:
        st.subheader("Baza haseł")
        b_df = load_sheet("baza_hasel")
        edited_baza = st.data_editor(b_df, num_rows="dynamic", use_container_width=True, key="ed_baza")
        if st.button("ZAPISZ BAZĘ"):
            save_sheet("baza_hasel", edited_baza);
            st.rerun()

    with t4:
        st.subheader("Logi")
        l_df = load_sheet("logi")
        st.dataframe(l_df, use_container_width=True)
        if st.button("CZYŚĆ LOGI"):
            save_sheet("logi", pd.DataFrame(columns=["Data", "Impostorzy", "Hasło", "Punkty"]));
            st.rerun()

# --- EKRAN 3: ARENA GRY ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user

    if gs['game_state'] == 'WAITING':
        st.subheader("🏆 RANKING")
        rdf = pd.DataFrame(gs['players'])
        if not rdf.empty:
            st.table(rdf[['login', 'score']].sort_values(by='score', ascending=False))
        st.info("Oczekiwanie na start...")

    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='role-card'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                st.markdown(f"**PODPOWIEDŹ TYLKO DLA CIEBIE:** {gs['current_hint']}")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Hasło: **{gs['current_word']}**")
            st.markdown("</div>", unsafe_allow_html=True)

        if user == ADMIN_USER:
            if st.button("🔔 ZAKOŃCZ TURĘ I GŁOSUJ", type="primary"):
                gs['game_state'] = 'VOTING_AGAIN';
                st.rerun()

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Gramy dalej tym samym hasłem?")
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()
        if user == ADMIN_USER and st.button("PODLICZ GŁOSY"):
            yes = sum(1 for v in gs['votes_again'].values() if v)
            no = len(gs['votes_again']) - yes
            gs['game_state'] = 'PLAYING' if yes > no else 'VOTING_IMPOSTOR'
            gs['votes_again'] = {};
            st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        others = [p for p in gs['participants'] if p != user]
        choice = st.selectbox("Wybierz", others) if others else None
        if st.button("Głosuj") and choice:
            gs['votes_impostor'][user] = choice;
            st.success("Głos oddany!")

        if user == ADMIN_USER and st.button("🏆 PODLICZ I ZAKOŃCZ"):
            summary = []
            # Podliczanie punktów
            for p in gs['players']:
                name = p['login']
                if name in gs['participants']:
                    change = 0
                    if name in gs['impostors']:
                        # Impostor dostaje 2 pkt jeśli nikt go nie wskazał
                        if not any(v == name for v in gs['votes_impostor'].values()):
                            change = 2
                    else:
                        # Gracz dostaje 1 pkt za trafienie dowolnego impostora
                        if gs['votes_impostor'].get(name) in gs['impostors']:
                            change = 1
                    p['score'] = int(p.get('score', 0)) + change
                    summary.append(f"{name}: +{change}")

            # Logi i zapis
            new_log = pd.DataFrame([{"Data": datetime.now().strftime("%H:%M"), "Impostorzy": ", ".join(gs['impostors']),
                                     "Hasło": gs['current_word'], "Punkty": " | ".join(summary)}])
            save_sheet("logi", pd.concat([load_sheet("logi"), new_log], ignore_index=True))
            save_sheet("gracze", pd.DataFrame(gs['players']))

            gs['game_state'] = 'WAITING'
            gs['votes_impostor'] = {}
            st.rerun()

    if user == ADMIN_USER:
        st.divider()
        if st.button("⚙️ PANEL ADMINA"): st.session_state.view = "admin_panel"; st.rerun()
    if st.button("Wyloguj"):
        st.session_state.clear();
        st.query_params.clear();
        st.rerun()