import streamlit as st
import pandas as pd
import random

# --- KONFIGURACJA STAŁYCH ---
ADMIN_USER = "Dawid"
ADMIN_PASSWORD = "Printiverse69"

# --- INICJALIZACJA STANU APLIKACJI (Bazy danych w pamięci) ---
if 'players' not in st.session_state: st.session_state.players = []
if 'passwords_df' not in st.session_state: st.session_state.passwords_df = pd.DataFrame(columns=['Hasło', 'Podpowiedź'])
if 'logs' not in st.session_state:
    st.session_state.logs = {'głosowanie': [], 'historia_haseł': [], 'historia_impostorów': []}
if 'view' not in st.session_state: st.session_state.view = "player_login"
if 'logged_user' not in st.session_state: st.session_state.logged_user = None
if 'admin_sub_menu' not in st.session_state: st.session_state.admin_sub_menu = "Główny"
if 'game_active' not in st.session_state: st.session_state.game_active = False
if 'current_game_data' not in st.session_state: st.session_state.current_game_data = {}
if 'settings' not in st.session_state: st.session_state.settings = {"impostors": 1, "hints": True}


# --- FUNKCJE LOGIKI GRY ---
def start_game():
    # Filtrowanie haseł, których jeszcze nie było
    used_passwords = st.session_state.logs['historia_haseł']
    available_passwords = st.session_state.passwords_df[
        ~st.session_state.passwords_df['Hasło'].isin(used_passwords)
    ]

    if len(available_passwords) == 0:
        st.error("Błąd: Wszystkie hasła z bazy zostały już wykorzystane!")
        return

    # Losowanie hasła i podpowiedzi
    selected_row = available_passwords.sample(n=1).iloc[0]
    haslo = selected_row['Hasło']
    podpowiedz = selected_row['Podpowiedź']

    # Budowanie listy wszystkich uczestników
    all_participants = [p['login'] for p in st.session_state.players]
    # Jeśli admin jest zalogowany jako gracz, dodajemy go do puli
    if st.session_state.logged_user == "admin_as_player" and ADMIN_USER not in all_participants:
        all_participants.append(ADMIN_USER)

    if len(all_participants) < 3:
        st.error("Za mało graczy, aby rozpocząć losowanie!")
        return

    # Losowanie impostorów
    num_imp = min(st.session_state.settings['impostors'], len(all_participants) - 1)
    impostors = random.sample(all_participants, num_imp)

    # Zapisanie wyników rundy
    st.session_state.current_game_data = {
        "haslo": haslo,
        "podpowiedz": podpowiedz,
        "impostors": impostors
    }

    # Aktualizacja logów
    st.session_state.logs['historia_haseł'].append(haslo)
    st.session_state.logs['historia_impostorów'].append(", ".join(impostors))
    st.session_state.game_active = True


# --- UI: LOGOWANIE ADMINA (DO USTAWIEŃ) ---
if st.session_state.view == "admin_auth":
    st.title("🔐 Autoryzacja Administratora")
    user_a = st.text_input("Login")
    pwd_a = st.text_input("Hasło", type="password")
    if st.button("Zaloguj do Panelu"):
        if user_a == ADMIN_USER and pwd_a == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_only"
            st.session_state.view = "admin_panel"
            st.rerun()
        else:
            st.error("Nieprawidłowe dane admina.")
    if st.button("Wróć do logowania graczy"):
        st.session_state.view = "player_login"
        st.rerun()

# --- UI: PANEL ADMINA (ZARZĄDZANIE) ---
elif st.session_state.view == "admin_panel":
    st.title("🛠️ Panel Zarządzania (Dawid)")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Dodaj graczy"): st.session_state.admin_sub_menu = "Dodaj"
    if c2.button("Baza haseł"): st.session_state.admin_sub_menu = "Baza"
    if c3.button("Rozgrywka"): st.session_state.admin_sub_menu = "Rozgrywka"
    if c4.button("Logi"): st.session_state.admin_sub_menu = "Logi"

    st.divider()

    if st.session_state.admin_sub_menu == "Dodaj":
        st.subheader("Zarządzanie Graczami")
        if st.button("KASUJ WSZYSTKICH GRACZY", type="primary"):
            st.session_state.players = []
            st.rerun()

        count = len(st.session_state.players)
        if count < 12:
            st.write(f"### Rejestracja: Gracz {count + 1}")
            n_login = st.text_input("Nazwa gracza")
            n_pwd = st.text_input("Hasło dla gracza", type="password")

            col_a, col_b = st.columns(2)
            if col_a.button("Dodaj kolejnego gracza"):
                if n_login and n_pwd:
                    st.session_state.players.append({"login": n_login, "pwd": n_pwd})
                    st.rerun()
                else:
                    st.warning("Uzupełnij pola!")

            if col_b.button("Zakończ dodawanie"):
                if count + 1 < 3:
                    st.error("W grze musi wziąć udział przynajmniej 3 graczy!")
                elif n_login and n_pwd:
                    st.session_state.players.append({"login": n_login, "pwd": n_pwd})
                    st.session_state.admin_sub_menu = "Główny"
                    st.rerun()
        else:
            st.success("Osiągnięto limit 12 graczy.")
            if st.button("Wróć"): st.session_state.admin_sub_menu = "Główny"; st.rerun()

    elif st.session_state.admin_sub_menu == "Baza":
        st.subheader("Baza haseł")
        st.write("Wklej dane z Excela poniżej (Kolumna 1: Hasło, Kolumna 2: Podpowiedź)")
        st.session_state.passwords_df = st.data_editor(st.session_state.passwords_df, num_rows="dynamic",
                                                       use_container_width=True)
        if st.button("Zapisz i wróć"): st.session_state.admin_sub_menu = "Główny"; st.rerun()

    elif st.session_state.admin_sub_menu == "Rozgrywka":
        st.subheader("Ustawienia rundy")
        st.session_state.settings['impostors'] = st.number_input("Liczba impostorów", 1, 5,
                                                                 st.session_state.settings['impostors'])
        st.session_state.settings['hints'] = st.checkbox("Wyświetlaj podpowiedzi impostorom",
                                                         st.session_state.settings['hints'])
        if st.button("Wróć"): st.session_state.admin_sub_menu = "Główny"; st.rerun()

    elif st.session_state.admin_sub_menu == "Logi":
        st.subheader("Historia i Dane")
        kat = st.selectbox("Wybierz kategorię", ["głosowanie", "historia_haseł", "historia_impostorów"])
        st.write(st.session_state.logs[kat])

        if st.button("Wyczyść tę kategorię"):
            st.session_state.logs[kat] = []
            st.rerun()
        if st.button("WYCZYŚĆ WSZYSTKO"):
            st.session_state.logs = {k: [] for k in st.session_state.logs}
            st.rerun()

        csv = pd.DataFrame(st.session_state.logs[kat]).to_csv(index=False)
        st.download_button("Eksportuj do CSV", csv, "logi.csv", "text/csv")

    if st.button("Wyloguj Admina"):
        st.session_state.logged_user = None
        st.session_state.view = "player_login"
        st.rerun()

# --- UI: PANEL LOGOWANIA GRACZY ---
elif st.session_state.view == "player_login":
    st.title("Gra Impostor - Wejdź do gry")
    l_user = st.text_input("Login", key="p_log")
    l_pwd = st.text_input("Hasło", type="password", key="p_pwd")

    if st.button("Zaloguj", use_container_width=True):
        if l_user == ADMIN_USER and l_pwd == ADMIN_PASSWORD:
            st.session_state.logged_user = "admin_as_player"
            st.session_state.view = "game_room"
            st.rerun()
        else:
            p_match = next((p for p in st.session_state.players if p['login'] == l_user and p['pwd'] == l_pwd), None)
            if p_match:
                st.session_state.logged_user = l_user
                st.session_state.view = "game_room"
                st.rerun()
            else:
                st.error("Błędny login lub hasło!")

    st.divider()
    if st.button("⚙️ Zaloguj jako ADMIN (Ustawienia)"):
        st.session_state.view = "admin_auth"
        st.rerun()

# --- UI: POKÓJ GRY (WIDOK DLA GRACZA I ADMINA-GRACZA) ---
elif st.session_state.view == "game_room":
    st.title("🕹️ Pokój Rozgrywki")
    nick = ADMIN_USER if st.session_state.logged_user == "admin_as_player" else st.session_state.logged_user
    st.write(f"Zalogowany jako: **{nick}**")

    if not st.session_state.game_active:
        st.info("🕒 Oczekiwanie na rozpoczęcie gry przez admina...")
        if st.session_state.logged_user == "admin_as_player":
            if st.button("🚀 WYSTARTUJ ROZGRYWKĘ", type="primary", use_container_width=True):
                start_game()
                st.rerun()
            if st.button("⚙️ PANEL ADMINA"):
                st.session_state.view = "admin_panel"
                st.rerun()
    else:
        # Gra jest aktywna - wyświetlanie ról
        st.divider()
        impostors = st.session_state.current_game_data.get('impostors', [])

        if nick in impostors:
            st.error("🕵️ JESTEŚ IMPOSTOREM!")
            if st.session_state.settings['hints']:
                st.info(f"Podpowiedź: {st.session_state.current_game_data['podpowiedz']}")
        else:
            st.success(f"Hasło: {st.session_state.current_game_data['haslo']}")

        st.divider()
        if st.session_state.logged_user == "admin_as_player":
            if st.button("🛑 ZAKOŃCZ RUNDĘ", use_container_width=True):
                st.session_state.game_active = False
                st.rerun()

    if st.button("Wyjdź z gry"):
        st.session_state.logged_user = None
        st.session_state.view = "player_login"
        st.rerun()