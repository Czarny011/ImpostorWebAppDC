import streamlit as st
import pandas as pd
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

st.set_page_config(page_title="Impostor Cloud v3.3", page_icon="🎭", layout="centered")

# --- STYLE CSS (Branding by D.CZ.) ---
st.markdown(f"""
    <style>
    .stButton>button {{ width: 100%; border-radius: 12px; height: 3em; background-color: #ff4b4b; color: white; border: none; }}
    .brand-text {{ font-size: 0.7rem; color: #666; text-align: center; display: block; margin-top: -15px; margin-bottom: 20px; }}
    .impostor-title {{ font-size: 3rem; font-weight: bold; text-align: center; color: white; margin-bottom: 0; }}
    .role-card {{ padding: 20px; border-radius: 15px; background: #262730; border: 2px solid #ff4b4b; text-align: center; }}
    .ranking-table {{ width: 100%; border-collapse: collapse; }}
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
        st.error(f"Błąd zapisu do Google Sheets ({name}): {e}")


# --- GLOBALNY STAN GRY ---
@st.cache_resource
def get_gs():
    p_df = load_sheet("gracze")
    # Inicjalizacja punktów jeśli nie istnieją w arkuszu
    players = p_df.to_dict('records') if not p_df.empty else []
    for p in players:
        if 'score' not in p: p['score'] = 0

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
                words_df = load_sheet("baza_hasel")
                if not words_df.empty and "Hasło" in words_df.columns:
                    valid_words = words_df[words_df["Hasło"].str.strip().astype(bool)]
                    if not valid_words.empty:
                        row = valid_words.sample(1).iloc[0]
                        gs.update({
                            'current_word': row['Hasło'],
                            'current_hint': row['Podpowiedź'] if 'Podpowiedź' in row else "",
                            'participants': selected,
                            'impostors': random.sample(selected, min(len(selected), gs['settings']['impostors'])),
                            'game_state': 'PLAYING', 'votes_again': {}, 'votes_impostor': {}
                        })
                        st.session_state.view = "game_room"
                        st.rerun()
                    else:
                        st.error("Baza haseł jest pusta!")
                else:
                    st.error("Sprawdź nazwę kolumny: Hasło")
        else:
            st.info("Runda trwa. Panel sterowania jest na Arenie.")

        if st.button("🏠 POWRÓT DO GRY"):
            st.session_state.view = "game_room";
            st.rerun()

    with t2:
        st.subheader("Zarządzaj graczami")
        if st.button("🔥 WYCZYŚĆ WSZYSTKIE PUNKTY"):
            for p in gs['players']: p['score'] = 0
            save_sheet("gracze", pd.DataFrame(gs['players']))
            st.rerun()

        for i, pl in enumerate(gs['players']):
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {pl['login']} ({pl.get('score', 0)} pkt)")
            if c2.button("Usuń", key=f"del_{pl['login']}"):
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
                gs['reg_counter'] += 1
                st.rerun()

    with t3:
        st.subheader("Baza haseł")
        baza_df = load_sheet("baza_hasel")
        if baza_df.empty: baza_df = pd.DataFrame(columns=["Hasło", "Podpowiedź"])
        edited_baza = st.data_editor(baza_df, num_rows="dynamic", use_container_width=True, key="ed_baza")
        if st.button("ZAPISZ BAZĘ"):
            save_sheet("baza_hasel", edited_baza);
            st.rerun()

    with t4:
        st.subheader("Logi rozgrywek")
        logi_df = load_sheet("logi")
        st.dataframe(logi_df, use_container_width=True)
        if st.button("WYCZYŚĆ LOGI"):
            save_sheet("logi", pd.DataFrame(columns=["Data", "Impostorzy", "Hasło", "Głosowanie", "Punkty"]));
            st.rerun()

# --- EKRAN 3: ARENA GRY ---
elif st.session_state.view == "game_room":
    draw_header("ARENA")
    user = st.session_state.logged_user
    st.write(f"Zalogowany: **{user}**")

    # --- STAN: LOBBY (RANKING) ---
    if gs['game_state'] == 'WAITING':
        st.subheader("🏆 Ranking Graczy")
        # Admin traktowany jako gracz (jeśli Dawid jest na liście graczy, używamy jego punktów)
        full_list = pd.DataFrame(gs['players'])
        if not full_list.empty:
            # Sortowanie od najlepszego
            ranking = full_list[['login', 'score']].sort_values(by='score', ascending=False).reset_index(drop=True)
            st.table(ranking)
        else:
            st.info("Brak graczy w systemie.")
        st.info("Czekamy na start rundy...")

    # --- STAN: GRA (HASŁA) ---
    elif gs['game_state'] == 'PLAYING':
        if user in gs['participants']:
            st.markdown("<div class='role-card'>", unsafe_allow_html=True)
            if user in gs['impostors']:
                st.error("JESTEŚ IMPOSTOREM! 😈")
                if gs['settings']['hints']:
                    st.markdown(f"**PODPOWIEDŹ TYLKO DLA CIEBIE:**\n\n{gs['current_hint']}")
            else:
                st.success("JESTEŚ GRACZEM 😇")
                st.write(f"Twoje hasło: **{gs['current_word']}**")
                st.write(f"Podpowiedź dla wszystkich: {gs['current_hint']}")
            st.markdown("</div>", unsafe_allow_html=True)

        if user == ADMIN_USER:
            st.divider()
            if st.button("🔔 ZAKOŃCZ TURĘ I GŁOSUJ", type="primary"):
                gs['game_state'] = 'VOTING_AGAIN'
                st.rerun()

    # --- STAN: CZY DALEJ TO SAMO ---
    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Czy gramy kolejną turę z tym samym hasłem?")
        c1, c2 = st.columns(2)
        if c1.button("TAK"): gs['votes_again'][user] = True; st.rerun()
        if c2.button("NIE"): gs['votes_again'][user] = False; st.rerun()

        if user == ADMIN_USER:
            st.divider()
            v_count = len(gs['votes_again'])
            st.write(f"Głosy: {v_count}/{len(gs['participants'])}")
            if st.button("PODLICZ GŁOSY"):
                yes = sum(1 for v in gs['votes_again'].values() if v)
                no = v_count - yes
                gs['game_state'] = 'PLAYING' if yes > no else 'VOTING_IMPOSTOR'
                gs['votes_again'] = {};
                st.rerun()

    # --- STAN: WSKAZANIE IMPOSTORA ---
    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        others = [p for p in gs['participants'] if p != user]
        if others:
            choice = st.selectbox("Wybierz podejrzanego", others)
            if st.button("ODDAJ GŁOS"):
                gs['votes_impostor'][user] = choice;
                st.success(f"Zagłosowano na: {choice}")

        if user == ADMIN_USER:
            st.divider()
            st.write(f"Głosowało: {len(gs['votes_impostor'])}/{len(gs['participants'])}")
            if st.button("🏆 ZAKOŃCZ RUNDĘ I PODLICZ PUNKTY"):
                # LOGIKA PUNKTACJI
                votes = gs['votes_impostor']
                impostors = gs['impostors']
                points_summary = []

                # Gracze dostają 1 pkt za każdy poprawny głos na dowolnego impostora
                # Impostorzy dostają 2 pkt jeśli nikt na nich nie zagłosował (przetrwanie)
                for p in gs['players']:
                    p_name = p['login']
                    if p_name in gs['participants']:
                        added = 0
                        # Jeśli gracz nie jest impostorem i trafił
                        if p_name not in impostors:
                            if votes.get(p_name) in impostors:
                                p['score'] += 1
                                added = 1
                        # Jeśli jest impostorem i nikt go nie wskazał
                        else:
                            who_voted_me = [u for u, v in votes.items() if v == p_name]
                            if not who_voted_me:
                                p['score'] += 2
                                added = 2
                        points_summary.append(f"{p_name}: +{added}")

                # Zapis logów
                log_data = {
                    "Data": datetime.now().strftime("%d/%m %H:%M"),
                    "Impostorzy": ", ".join(impostors),
                    "Hasło": gs['current_word'],
                    "Głosowanie": str(votes),
                    "Punkty": " | ".join(points_summary)
                }
                old_logi = load_sheet("logi")
                save_sheet("logi", pd.concat([old_logi, pd.DataFrame([log_data])], ignore_index=True))
                save_sheet("gracze", pd.DataFrame(gs['players']))

                gs['game_state'] = 'WAITING'
                gs['votes_impostor'] = {}
                st.rerun()

    # --- STOPKA ---
    if user == ADMIN_USER:
        st.divider()
        if st.button("⚙️ PANEL STEROWANIA"): st.session_state.view = "admin_panel"; st.rerun()
    if st.button("Wyloguj"):
        st.session_state.clear();
        st.query_params.clear();
        st.session_state.view = "login";
        st.rerun()