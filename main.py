import streamlit as st
import pandas as pd
import random
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
        'logs': {'głosowanie': [], 'historia_haseł': [], 'historia_impostorów': []},
        'settings': {"impostors": 1, "hints": True},
        'game_active': False,
        'current_game_data': {},
        'game_id': 0  # Licznik rund do wymuszania odświeżania
    }


gs = get_global_state()

# --- SYNCHRONIZACJA (Odświeżanie co 2 sekundy) ---
# To sprawia, że telefon gracza sam "zauważy" start gry
st_autorefresh(interval=2000, key="datarefresh")

# --- INICJALIZACJA SESJI LOKALNEJ ---
if 'view' not in st.session_state: st.session_state.view = "player_login"
if 'logged_user' not in st.session_state: st.session_state.logged_user = None
if 'admin_sub_menu' not in st.session_state: st.session_state.admin_sub_menu = "Główny"


# --- FUNKCJA LOSOWANIA ---
def start_game():
    used_passwords = gs['logs']['historia_haseł']
    available_passwords = gs['passwords_df'][
        ~gs['passwords_df']['Hasło'].isin(used_passwords)
    ]

    if len(available_passwords) == 0:
        return "Błąd: Brak nowych haseł!"

    selected_row = available_passwords.sample(n=1).iloc[0]

    all_participants = [p['login'] for p in gs['players']]
    if ADMIN_USER not in all_participants:
        all_participants.append(ADMIN_USER)

    if len(all_participants) < 3:
        return "Błąd: Min. 3 graczy!"

    num_imp = min(gs['settings']['impostors'], len(all_participants) - 1)
    impostors = random.sample(all_participants, num_imp)

    # Zapisanie wszystkiego do globalnego stanu
    gs['current_game_data'] = {
        "haslo": selected_row['Hasło'],
        "podpowiedz": selected_row['Podpowiedź'],
        "impostors": impostors
    }

    gs['logs']['historia_haseł'].append(selected_row['Hasło'])
    gs['logs']['historia_impostorów'].append(", ".join(impostors))
    gs['game_active'] = True
    gs['game_id'] += 1  # Zmiana ID rundy
    return None


# --- UI: LOGOWANIE ADMINA ---
if st.session_state.view == "admin_auth":
    st.title("🔐 Autoryzacja Admina")
    u_a = st.text_input("Login")
    p_a = st.text_input("Hasło", type="password")
    if st.button("Wejdź"):
        if u_a == ADMIN_USER and p_a == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_only"
            st.session_state.view = "admin_panel"
            st.rerun()
        else:
            st.error("Błąd!")
    if st.button("Wróć"): st.session_state.view = "player_login"; st.rerun()

# --- UI: PANEL ADMINA ---
elif st.session_state.view == "admin_panel":
    st.title("🛠️ Zarządzanie Grą")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Dodaj graczy"): st.session_state.admin_sub_menu = "Dodaj"
    if c2.button("Baza haseł"): st.session_state.admin_sub_menu = "Baza"
    if c3.button("Rozgrywka"): st.session_state.admin_sub_menu = "Rozgrywka"
    if c4.button("Logi"): st.session_state.admin_sub_menu = "Logi"

    st.divider()

    if st.session_state.admin_sub_menu == "Dodaj":
        if st.button("KASUJ WSZYSTKICH"): gs['players'] = []; st.rerun()
        st.write(f"Zarejestrowani: {len(gs['players'])}/12")
        for i, p in enumerate(gs['players']):
            st.text(f"{i + 1}. {p['login']}")

        n_l = st.text_input("Login nowego gracza")
        n_p = st.text_input("Hasło", type="password")
        if st.button("Dodaj gracza"):
            if n_l and n_p:
                gs['players'].append({'login': n_l, 'pwd': n_p})
                st.rerun()

    elif st.session_state.admin_sub_menu == "Baza":
        st.subheader("Baza haseł (Kolumna 1: Hasło, Kolumna 2: Podpowiedź)")
        gs['passwords_df'] = st.data_editor(gs['passwords_df'], num_rows="dynamic", use_container_width=True)

    elif st.session_state.admin_sub_menu == "Rozgrywka":
        gs['settings']['impostors'] = st.number_input("Liczba impostorów", 1, 5, gs['settings']['impostors'])
        gs['settings']['hints'] = st.checkbox("Podpowiedzi dla Impostora", gs['settings']['hints'])

    elif st.session_state.admin_sub_menu == "Logi":
        k = st.selectbox("Kategoria", ["głosowanie", "historia_haseł", "historia_impostorów"])
        st.write(gs['logs'][k])
        if st.button("Wyczyść wszystko"): gs['logs'] = {key: [] for key in gs['logs']}; st.rerun()

    if st.button("Wyloguj"): st.session_state.view = "player_login"; st.rerun()

# --- UI: PANEL LOGOWANIA ---
elif st.session_state.view == "player_login":
    st.title("🎭 Impostor - Logowanie")
    l_u = st.text_input("Twój Login")
    l_p = st.text_input("Twoje Hasło", type="password")

    if st.button("Zaloguj się", use_container_width=True):
        if l_u == ADMIN_USER and l_p == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_as_player"
            st.session_state.view = "game_room"
            st.rerun()
        else:
            match = next((p for p in gs['players'] if p['login'] == l_u and p['pwd'] == l_p), None)
            if match:
                st.session_state.logged_user = l_u
                st.session_state.view = "game_room"
                st.rerun()
            else:
                st.error("Nie znaleziono takiego gracza!")

    if st.button("⚙️ Admin"): st.session_state.view = "admin_auth"; st.rerun()

# --- UI: POKÓJ GRY ---
elif st.session_state.view == "game_room":
    st.title("🕹️ Arena Gry")
    nick = ADMIN_USER if st.session_state.logged_user == "admin_as_player" else st.session_state.logged_user

    if not gs['game_active']:
        st.warning("⏳ Oczekiwanie na rozpoczęcie rundy przez admina...")
        if st.session_state.logged_user == "admin_as_player":
            if st.button("🚀 ROZPOCZNIJ ROZGRYWKĘ", type="primary"):
                err = start_game()
                if err:
                    st.error(err)
                else:
                    st.rerun()
            if st.button("⚙️ PANEL ADMINA"): st.session_state.view = "admin_panel"; st.rerun()
    else:
        # POKAZYWANIE RÓL
        st.divider()
        impostors = gs['current_game_data'].get('impostors', [])

        if nick in impostors:
            st.error("🕵️ JESTEŚ IMPOSTOREM!")
            if gs['settings']['hints']:
                st.info(f"Twoja podpowiedź: **{gs['current_game_data']['podpowiedz']}**")
        else:
            st.success(f"Twoje hasło to: **{gs['current_game_data']['haslo']}**")

        st.divider()
        if st.session_state.logged_user == "admin_as_player":
            if st.button("🛑 ZAKOŃCZ RUNDĘ"):
                gs['game_active'] = False
                st.rerun()

    if st.button("Wyjdź do menu"):
        st.session_state.logged_user = None
        st.session_state.view = "player_login"
        st.rerun()