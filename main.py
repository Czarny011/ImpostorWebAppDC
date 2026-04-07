import streamlit as st
import pandas as pd
import random
import time
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURACJA STAŁYCH ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"


# --- GLOBALNA PAMIĘĆ (WSPÓLNA DLA WSZYSTKICH) ---
@st.cache_resource
def get_global_state():
    return {
        'players': [],
        'passwords_df': pd.DataFrame(columns=['Hasło', 'Podpowiedź']),
        'logs': {'głosowanie': [], 'historia_haseł': [], 'historia_impostorów': [], 'historia_punktacji': []},
        'settings': {"impostors": 1, "hints": True},

        'game_state': 'WAITING',
        'current_game_data': {},
        'scores': {},

        'votes_again': {},
        'show_results_until': 0,
        'votes_impostor': {},

        'game_id': 0
    }


gs = get_global_state()

# --- SYNCHRONIZACJA (Odświeżanie co 2 sekundy) ---
st_autorefresh(interval=2000, key="datarefresh")

# --- INICJALIZACJA SESJI LOKALNEJ ---
if 'view' not in st.session_state: st.session_state.view = "player_login"
if 'logged_user' not in st.session_state: st.session_state.logged_user = None
if 'admin_sub_menu' not in st.session_state: st.session_state.admin_sub_menu = "Główny"
if 'temp_df' not in st.session_state: st.session_state.temp_df = gs['passwords_df'].copy()


# --- FUNKCJE POMOCNICZE ---
def init_scores():
    for p in gs['players']:
        if p['login'] not in gs['scores']: gs['scores'][p['login']] = 0
    if ADMIN_USER not in gs['scores']: gs['scores'][ADMIN_USER] = 0


def start_game():
    init_scores()
    used_passwords = gs['logs']['historia_haseł']
    available_passwords = gs['passwords_df'][~gs['passwords_df']['Hasło'].isin(used_passwords)]

    if len(available_passwords) == 0: return "Błąd: Brak nowych haseł w bazie!"

    selected_row = available_passwords.sample(n=1).iloc[0]
    haslo, podpowiedz = selected_row['Hasło'], selected_row['Podpowiedź']

    all_participants = [p['login'] for p in gs['players']]
    if st.session_state.logged_user == "admin_as_player" and ADMIN_USER not in all_participants:
        all_participants.append(ADMIN_USER)

    if len(all_participants) < 3: return "Błąd: W grze musi wziąć udział przynajmniej 3 graczy!"

    num_imp = min(gs['settings']['impostors'], len(all_participants) - 1)
    impostors = random.sample(all_participants, num_imp)

    gs['current_game_data'] = {
        "haslo": haslo,
        "podpowiedz": podpowiedz,
        "impostors": impostors,
        "participants": all_participants
    }

    gs['logs']['historia_haseł'].append(haslo)
    gs['logs']['historia_impostorów'].append(", ".join(impostors))
    gs['game_state'] = 'PLAYING'
    gs['votes_again'] = {}
    gs['votes_impostor'] = {}
    gs['game_id'] += 1
    return None


def calculate_points():
    participants = gs['current_game_data']['participants']
    impostors = gs['current_game_data']['impostors']
    total_players = len(participants)
    vote_counts = {p: 0 for p in participants}
    for voter, voted_for in gs['votes_impostor'].items():
        vote_counts[voted_for] += 1

    round_log = []
    for player in participants:
        pts_gained = 0
        if player in impostors:
            pts_gained = (total_players - 1) - vote_counts[player]
            pts_gained = max(0, pts_gained)
        else:
            voted_for = gs['votes_impostor'].get(player)
            if voted_for in impostors: pts_gained = 2

        gs['scores'][player] += pts_gained
        round_log.append(f"{player}: +{pts_gained} pkt")
    gs['logs']['historia_punktacji'].append(", ".join(round_log))


# --- UI: LOGOWANIE ADMINA ---
if st.session_state.view == "admin_auth":
    st.title("🔐 Autoryzacja Admina")
    if st.button("Powrót"): st.session_state.view = "player_login"; st.rerun()
    u_a = st.text_input("Login")
    p_a = st.text_input("Hasło", type="password")
    if st.button("Zaloguj"):
        if u_a == ADMIN_USER and p_a == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_only";
            st.session_state.view = "admin_panel";
            st.rerun()
        else:
            st.error("Błędne dane!")

# --- UI: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    st.title("🛠️ Zarządzanie")
    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("Dodaj graczy"): st.session_state.admin_sub_menu = "Dodaj"
    if c2.button("Baza haseł"): st.session_state.admin_sub_menu = "Baza"
    if c3.button("Rozgrywka"): st.session_state.admin_sub_menu = "Rozgrywka"
    if c4.button("Logi"): st.session_state.admin_sub_menu = "Logi"
    if c5.button(
        "Powrót do gry"): st.session_state.logged_user = "admin_as_player"; st.session_state.view = "game_room"; st.rerun()

    st.divider()

    if st.session_state.admin_sub_menu == "Dodaj":
        st.subheader("Zarządzanie graczami")
        cd1, cd2 = st.columns(2)
        if cd1.button("KASUJ WSZYSTKICH GRACZY", type="primary"): gs['players'] = []; st.rerun()
        if len(gs['players']) > 0:
            to_rem = cd2.selectbox("Usuń gracza", [p['login'] for p in gs['players']])
            if cd2.button("Usuń"): gs['players'] = [p for p in gs['players'] if p['login'] != to_rem]; st.rerun()

        count = len(gs['players'])
        st.write(f"Zarejestrowani: {count}/12")

        if count < 12:
            st.write(f"### Rejestracja: Gracz {count + 1}")
            # Używamy kluczy sesji, aby móc je wyczyścić
            n_l = st.text_input("Nazwa gracza", key="reg_name")
            n_p = st.text_input("Hasło", type="password", key="reg_pwd")

            ca, cb = st.columns(2)

            if ca.button("Dodaj kolejnego gracza"):
                if n_l.strip():  # Walidacja: nie puste
                    gs['players'].append({'login': n_l.strip(), 'pwd': n_p})
                    st.session_state.reg_name = ""  # Czyścimy pole
                    st.session_state.reg_pwd = ""  # Czyścimy pole
                    st.rerun()
                else:
                    st.error("Nazwa gracza nie może być pusta!")

            if cb.button("Zakończ dodawanie gracza"):
                if n_l.strip():
                    gs['players'].append({'login': n_l.strip(), 'pwd': n_p})

                if len(gs['players']) >= 3:
                    st.session_state.reg_name = ""
                    st.session_state.reg_pwd = ""
                    st.session_state.admin_sub_menu = "Główny"
                    st.rerun()
                else:
                    st.error("W grze musi wziąć udział przynajmniej 3 graczy!")

    elif st.session_state.admin_sub_menu == "Baza":
        st.subheader("Baza haseł")
        st.session_state.temp_df.index = range(1, len(st.session_state.temp_df) + 1)
        edited = st.data_editor(st.session_state.temp_df, num_rows="dynamic", use_container_width=True)
        st.session_state.temp_df = edited

        c_a, c_b = st.columns(2)
        if c_a.button("Zapisz", type="primary"):
            gs['passwords_df'] = edited.copy()
            st.success("Zapisano!")
        if c_b.button("Gotowe / Wróć"): st.session_state.admin_sub_menu = "Główny"; st.rerun()

    elif st.session_state.admin_sub_menu == "Rozgrywka":
        gs['settings']['impostors'] = st.number_input("Liczba impostorów", 1, 5, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Podpowiedzi", gs['settings']['hints'])

    elif st.session_state.admin_sub_menu == "Logi":
        kat = st.selectbox("Kategoria", ["głosowanie", "historia_haseł", "historia_impostorów", "historia_punktacji"])
        for idx, val in enumerate(gs['logs'][kat]):
            cc1, cc2 = st.columns([4, 1])
            cc1.write(f"{idx + 1}. {val}")
            if cc2.button("Usuń", key=f"del_{kat}_{idx}"): gs['logs'][kat].pop(idx); st.rerun()
        st.divider()
        if st.button("Wyczyść kategorię"): gs['logs'][kat] = []; st.rerun()
        if st.button("WYCZYŚĆ WSZYSTKO", type="primary"): gs['logs'] = {k: [] for k in gs['logs']}; st.rerun()

# --- UI: PANEL LOGOWANIA GRACZY ---
elif st.session_state.view == "player_login":
    st.title("🎭 Impostor")
    l_u = st.text_input("Login")
    l_p = st.text_input("Hasło", type="password")
    if st.button("Zaloguj się", use_container_width=True):
        if l_u == ADMIN_USER and l_p == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_as_player";
            st.session_state.view = "game_room";
            st.rerun()
        else:
            match = next((p for p in gs['players'] if p['login'] == l_u and p['pwd'] == l_p), None)
            if match:
                st.session_state.logged_user = l_u; st.session_state.view = "game_room"; st.rerun()
            else:
                st.error("Błąd logowania!")
    if st.button("⚙️ Admin"): st.session_state.view = "admin_auth"; st.rerun()

# --- UI: POKÓJ GRY ---
elif st.session_state.view == "game_room":
    nick = ADMIN_USER if st.session_state.logged_user == "admin_as_player" else st.session_state.logged_user
    is_admin = (st.session_state.logged_user == "admin_as_player")

    if is_admin:
        ca1, ca2, ca3 = st.columns(3)
        if ca1.button("⚙️ Panel Admina"): st.session_state.view = "admin_panel"; st.rerun()
        if ca2.button("🔄 Zakończ rozgrywkę"):  # RESET DO LOBBY
            gs['game_state'] = 'WAITING'
            gs['votes_again'] = {}
            gs['votes_impostor'] = {}
            st.rerun()

    st.title("🕹️ Arena")

    if gs['game_state'] == 'WAITING':
        st.info("⏳ Oczekiwanie na start...")
        if is_admin:
            if st.button("🚀 Wystartuj rozgrywkę", type="primary", use_container_width=True):
                err = start_game()
                if err:
                    st.error(err)
                else:
                    st.rerun()

    elif gs['game_state'] == 'PLAYING':
        imp = gs['current_game_data']['impostors']
        if nick in imp:
            st.error("🕵️ JESTEŚ IMPOSTOREM!")
            if gs['settings']['hints']: st.info(f"Podpowiedź: **{gs['current_game_data']['podpowiedz']}**")
        else:
            st.success(f"Hasło: **{gs['current_game_data']['haslo']}**")
        if is_admin:
            if st.button("🛑 Zakończ rundę (Głosowanie)"): gs['game_state'] = 'VOTING_AGAIN'; st.rerun()

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Kolejna runda z tym samym hasłem?")
        if nick not in gs['votes_again']:
            v1, v2 = st.columns(2)
            if v1.button("✅ TAK"): gs['votes_again'][nick] = "TAK"; st.rerun()
            if v2.button("❌ NIE"): gs['votes_again'][nick] = "NIE"; st.rerun()
        else:
            st.write("Czekamy...")
        if len(gs['votes_again']) == len(gs['current_game_data']['participants']):
            gs['show_results_until'] = time.time() + 5
            gs['game_state'] = 'SHOWING_AGAIN_RESULTS';
            st.rerun()

    elif gs['game_state'] == 'SHOWING_AGAIN_RESULTS':
        t_c = list(gs['votes_again'].values()).count("TAK")
        n_c = list(gs['votes_again'].values()).count("NIE")
        st.write(f"TAK: {t_c} | NIE: {n_c}")
        if time.time() > gs['show_results_until']:
            gs['game_state'] = 'PLAYING' if t_c > n_c else 'VOTING_IMPOSTOR';
            st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Kto jest Impostorem?")
        if nick not in gs['votes_impostor']:
            others = [p for p in gs['current_game_data']['participants'] if p != nick]
            vote = st.selectbox("Twój typ:", ["Wybierz..."] + others)
            if st.button("Głosuj"):
                if vote != "Wybierz...": gs['votes_impostor'][nick] = vote; st.rerun()
        if len(gs['votes_impostor']) == len(gs['current_game_data']['participants']):
            calculate_points();
            gs['game_state'] = 'SHOWING_IMPOSTOR_RESULTS';
            st.rerun()

    elif gs['game_state'] == 'SHOWING_IMPOSTOR_RESULTS':
        st.subheader("Wyniki!")
        participants = gs['current_game_data']['participants']
        impostors = gs['current_game_data']['impostors']
        v_counts = {p: 0 for p in participants}
        for v in gs['votes_impostor'].values(): v_counts[v] += 1
        for p in participants:
            if p in impostors:
                st.error(f"🕵️ {p} (IMPOSTOR) - Głosów: {v_counts[p]}")
            else:
                st.success(f"👤 {p} - Głosów: {v_counts[p]}")
        if is_admin:
            if st.button("🚀 Następna tura (Nowe hasło)"): gs['game_state'] = 'WAITING'; st.rerun()

    st.divider()
    with st.expander("🏆 Podgląd punktacji"):
        if gs['scores']:
            for p, s in sorted(gs['scores'].items(), key=lambda x: x[1], reverse=True): st.write(f"**{p}**: {s} pkt")
    if st.button("Wyjdź"): st.session_state.logged_user = None; st.session_state.view = "player_login"; st.rerun()