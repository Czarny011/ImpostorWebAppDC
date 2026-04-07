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
        'passwords_df': pd.DataFrame(columns=['LP', 'Hasło', 'Podpowiedź']),
        'logs': {'głosowanie': [], 'historia_haseł': [], 'historia_impostorów': [], 'historia_punktacji': []},
        'settings': {"impostors": 1, "hints": True},

        'game_state': 'WAITING',
        'current_game_data': {},
        'scores': {},
        'last_round_points': {},

        'votes_again': {},
        'show_results_until': 0,
        'votes_impostor': {},

        'game_id': 0,
        'reg_counter': 0
    }


gs = get_global_state()

# --- SYNCHRONIZACJA ---
st_autorefresh(interval=2000, key="datarefresh")

# --- INICJALIZACJA SESJI LOKALNEJ ---
if 'view' not in st.session_state: st.session_state.view = "player_login"
if 'logged_user' not in st.session_state: st.session_state.logged_user = None
if 'admin_sub_menu' not in st.session_state: st.session_state.admin_sub_menu = "Główny"
if 'temp_df' not in st.session_state: st.session_state.temp_df = gs['passwords_df'].copy()


# --- FUNKCJE POMOCNICZE ---
def draw_footer():
    st.markdown("""
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: rgba(255,255,255,0.05);
            color: gray;
            text-align: center;
            font-size: 0.8rem;
            padding: 5px;
            z-index: 100;
        }
        </style>
        <div class="footer">
        © 2026 Impostor Web App v1 by Dawid Czarnota
        </div>
        """, unsafe_allow_html=True)


def init_scores():
    for p in gs['players']:
        if p['login'] not in gs['scores']: gs['scores'][p['login']] = 0
    if ADMIN_USER not in gs['scores']: gs['scores'][ADMIN_USER] = 0


def calculate_points():
    participants = gs['current_game_data']['participants']
    impostors = gs['current_game_data']['impostors']
    total_players = len(participants)
    vote_counts = {p: 0 for p in participants}
    for voter, voted_for in gs['votes_impostor'].items():
        vote_counts[voted_for] += 1

    round_scores = {}
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
        round_scores[player] = pts_gained
        round_log.append(f"{player}: +{pts_gained}")

    gs['last_round_points'] = round_scores
    gs['logs']['historia_punktacji'].append(", ".join(round_log))


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
    gs['last_round_points'] = {}
    gs['game_id'] += 1
    return None


# --- EKRANY ---

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

elif st.session_state.view == "admin_panel":
    st.title("🛠️ Panel Admina")
    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("Gracze"): st.session_state.admin_sub_menu = "Dodaj"
    if c2.button("Baza"): st.session_state.admin_sub_menu = "Baza"
    if c3.button("Opcje"): st.session_state.admin_sub_menu = "Rozgrywka"
    if c4.button("Logi"): st.session_state.admin_sub_menu = "Logi"
    if c5.button(
        "Gra"): st.session_state.logged_user = "admin_as_player"; st.session_state.view = "game_room"; st.rerun()

    st.divider()

    if st.session_state.admin_sub_menu == "Dodaj":
        st.subheader("Zarządzanie graczami")
        cd1, cd2 = st.columns(2)
        if cd1.button("KASUJ WSZYSTKICH", type="primary"): gs['players'] = []; gs['reg_counter'] += 1; st.rerun()
        if len(gs['players']) > 0:
            to_rem = cd2.selectbox("Usuń", [p['login'] for p in gs['players']])
            if cd2.button("Wykonaj"): gs['players'] = [p for p in gs['players'] if p['login'] != to_rem]; gs[
                'reg_counter'] += 1; st.rerun()

        count = len(gs['players'])
        st.write(f"Zarejestrowani: {count}/12")
        if count < 12:
            st.write(f"### Rejestracja: Gracz {count + 1}")
            n_l = st.text_input("Nazwa", key=f"n_{gs['reg_counter']}")
            n_p = st.text_input("Hasło", type="password", key=f"p_{gs['reg_counter']}")
            ca, cb = st.columns(2)
            if ca.button("Dodaj kolejnego"):
                if n_l.strip():
                    gs['players'].append({'login': n_l.strip(), 'pwd': n_p})
                    gs['reg_counter'] += 1;
                    st.rerun()
                else:
                    st.error("Nazwa nie może być pusta!")
            if cb.button("Zakończ dodawanie"):
                if n_l.strip(): gs['players'].append({'login': n_l.strip(), 'pwd': n_p})
                if len(gs['players']) >= 3:
                    gs['reg_counter'] += 1
                    st.session_state.admin_sub_menu = "Główny";
                    st.rerun()
                else:
                    st.error("Min. 3 graczy!")

    elif st.session_state.admin_sub_menu == "Baza":
        st.subheader("Baza haseł")
        edited = st.data_editor(
            st.session_state.temp_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "LP": st.column_config.TextColumn("LP", width="small"),
                "Hasło": st.column_config.TextColumn("Hasło", required=True),
                "Podpowiedź": st.column_config.TextColumn("Podpowiedź")
            }
        )
        st.session_state.temp_df = edited
        c_a, c_b = st.columns(2)
        if c_a.button("Zapisz", type="primary"):
            gs['passwords_df'] = edited.copy()
            st.success("Zapisano!")
        if c_b.button("Wróć"): st.session_state.admin_sub_menu = "Główny"; st.rerun()

    elif st.session_state.admin_sub_menu == "Rozgrywka":
        gs['settings']['impostors'] = st.number_input("Impostorzy", 1, 5, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Podpowiedzi", gs['settings']['hints'])

    elif st.session_state.admin_sub_menu == "Logi":
        kat = st.selectbox("Kategoria", ["głosowanie", "historia_haseł", "historia_impostorów", "historia_punktacji"])
        for idx, val in enumerate(gs['logs'][kat]):
            cc1, cc2 = st.columns([4, 1])
            cc1.write(f"{idx + 1}. {val}")
            if cc2.button("Usuń", key=f"del_{kat}_{idx}"): gs['logs'][kat].pop(idx); st.rerun()
        if st.button("Czyść kategorię"): gs['logs'][kat] = []; st.rerun()

elif st.session_state.view == "player_login":
    st.title("🎭 Impostor")
    l_u = st.text_input("Login")
    l_p = st.text_input("Hasło", type="password")
    if st.button("Zaloguj", use_container_width=True):
        if l_u == ADMIN_USER and l_p == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_as_player";
            st.session_state.view = "game_room";
            st.rerun()
        else:
            match = next((p for p in gs['players'] if p['login'] == l_u and p['pwd'] == l_p), None)
            if match:
                st.session_state.logged_user = l_u; st.session_state.view = "game_room"; st.rerun()
            else:
                st.error("Błędne dane!")
    if st.button("⚙️ Admin"): st.session_state.view = "admin_auth"; st.rerun()

elif st.session_state.view == "game_room":
    nick = ADMIN_USER if st.session_state.logged_user == "admin_as_player" else st.session_state.logged_user
    is_admin = (st.session_state.logged_user == "admin_as_player")

    if is_admin:
        ca1, ca2 = st.columns(2)
        if ca1.button("⚙️ Panel Admina"): st.session_state.view = "admin_panel"; st.rerun()
        if ca2.button("🔄 Zakończ"): gs['game_state'] = 'WAITING'; st.rerun()

    if gs['game_state'] == 'WAITING':
        st.info("Oczekiwanie na start...")
        if is_admin and st.button("🚀 START", type="primary", use_container_width=True):
            err = start_game()
            if err:
                st.error(err)
            else:
                st.rerun()

    elif gs['game_state'] == 'PLAYING':
        if nick in gs['current_game_data']['impostors']:
            st.error("🕵️ JESTEŚ IMPOSTOREM!")
            if gs['settings']['hints']: st.info(f"Podpowiedź: {gs['current_game_data']['podpowiedz']}")
        else:
            st.success(f"Hasło: {gs['current_game_data']['haslo']}")
        if is_admin and st.button("🛑 Przejdź do głosowania", use_container_width=True):
            gs['game_state'] = 'VOTING_AGAIN';
            st.rerun()

    elif gs['game_state'] == 'VOTING_AGAIN':
        st.subheader("Czy gramy kolejną turę z tym samym hasłem?")
        if nick not in gs['votes_again']:
            v1, v2 = st.columns(2)
            if v1.button("✅ TAK"): gs['votes_again'][nick] = "TAK"; st.rerun()
            if v2.button("❌ NIE"): gs['votes_again'][nick] = "NIE"; st.rerun()
        else:
            st.write("Czekamy na resztę...")
        if len(gs['votes_again']) == len(gs['current_game_data']['participants']):
            gs['show_results_until'] = time.time() + 5
            gs['game_state'] = 'SHOWING_AGAIN_RESULTS';
            st.rerun()

    elif gs['game_state'] == 'SHOWING_AGAIN_RESULTS':
        t_c = list(gs['votes_again'].values()).count("TAK")
        n_c = list(gs['votes_again'].values()).count("NIE")
        st.subheader(f"Wynik: TAK ({t_c}) | NIE ({n_c})")
        if time.time() > gs['show_results_until']:
            # KLUCZOWA POPRAWKA: czyścimy słownik głosów przed zmianą stanu
            gs['votes_again'] = {}
            gs['game_state'] = 'PLAYING' if t_c > n_c else 'VOTING_IMPOSTOR'
            st.rerun()

    elif gs['game_state'] == 'VOTING_IMPOSTOR':
        st.subheader("Głosowanie na Impostora!")
        if nick not in gs['votes_impostor']:
            others = [p for p in gs['current_game_data']['participants'] if p != nick]
            vote = st.selectbox("Wybierz:", ["---"] + others)
            if st.button("Głosuj"):
                if vote != "---": gs['votes_impostor'][nick] = vote; st.rerun()
        if len(gs['votes_impostor']) == len(gs['current_game_data']['participants']):
            calculate_points()
            gs['game_state'] = 'SHOWING_IMPOSTOR_RESULTS';
            st.rerun()

    elif gs['game_state'] == 'SHOWING_IMPOSTOR_RESULTS':
        st.subheader("Wyniki głosowania i punkty:")
        participants = gs['current_game_data']['participants']
        v_counts = {p: 0 for p in participants}
        for v in gs['votes_impostor'].values(): v_counts[v] += 1

        res_data = []
        for p in participants:
            role = "🕵️ IMPOSTOR" if p in gs['current_game_data']['impostors'] else "👤 Gracz"
            pts = gs['last_round_points'].get(p, 0)
            res_data.append({"Gracz": p, "Rola": role, "Głosy": v_counts[p], "Punkty +": pts})

        st.table(pd.DataFrame(res_data))
        if is_admin and st.button("🚀 Następna tura (Nowe hasło)", use_container_width=True):
            gs['game_state'] = 'WAITING';
            st.rerun()

    st.divider()
    with st.expander("🏆 Ranking ogólny"):
        for p, s in sorted(gs['scores'].items(), key=lambda x: x[1], reverse=True): st.write(f"**{p}**: {s} pkt")
    if st.button("Wyloguj"): st.session_state.logged_user = None; st.session_state.view = "player_login"; st.rerun()

draw_footer()