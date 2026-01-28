import streamlit as st
import utils
import copy

st.set_page_config(page_title="Indoor League", page_icon="⚽", layout="wide")

# Load CSS
def load_css():
    try:
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass 

load_css()

# Initialize Session State
if "data" not in st.session_state:
    st.session_state["data"] = utils.load_data()

if "match_history" not in st.session_state:
    st.session_state["match_history"] = [] 

# --- Sidebar ---
st.sidebar.title("Morningside League")
page = st.sidebar.radio("Navigate", ["Matches", "Standings", "Setup"])

# --- Helper Logic ---
def save_state():
    utils.save_data(st.session_state["data"])
    st.toast("Saved successfully!", icon="✅")

def update_stat(m_id, stat, delta, team_idx):
    real_match = next((m for m in st.session_state["data"]["matches"] if m["id"] == m_id), None)
    if not real_match: return

    snapshot = copy.deepcopy(real_match)
    st.session_state["match_history"].append(snapshot)
    
    if stat == "goal":
        key = f"g{team_idx}"
        real_match[key] = max(0, real_match[key] + delta)
    elif stat == "foul":
        key = f"f{team_idx}"
        real_match[key] = max(0, real_match[key] + delta)
        
        if delta > 0 and real_match[key] >= 3:
            real_match[key] = 0
            opp_idx = 2 if team_idx == 1 else 1
            real_match[f"g{opp_idx}"] += 1
            st.toast(f"3 Fouls! Penalty Goal for {'Team 2' if team_idx==1 else 'Team 1'}!", icon="⚠️")
    
    real_match["done"] = True

def delete_match_callback(m_id):
    st.session_state["data"] = utils.delete_match(st.session_state["data"], m_id)
    st.toast("Match Deleted!")

# --- Pages ---

if page == "Setup":
    st.title("League Setup")
    
    st.subheader("Manage Teams")
    teams = st.session_state["data"]["teams"]
    
    with st.form("add_team_form"):
        col1, col2 = st.columns([3, 1])
        new_team_name = col1.text_input("New Team Name", placeholder="Enter team name...")
        add_btn = col2.form_submit_button("Add Team")
        if add_btn and new_team_name:
            st.session_state["data"] = utils.add_team(st.session_state["data"], new_team_name)
            st.success(f"Added {new_team_name}!")
            st.rerun()

    st.markdown("---")
    
    st.write("Edit Existing Teams:")
    with st.form("team_form"):
        new_names = {}
        keys = list(teams.keys())
        for i in range(0, len(keys), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(keys):
                    tid = keys[i+j]
                    new_names[tid] = cols[j].text_input(f"ID: {tid}", value=teams[tid])
        
        submitted = st.form_submit_button("Update All Names")
        if submitted:
            for tid, name in new_names.items():
                utils.update_team_name(st.session_state["data"], tid, name)
            st.success("Team names updated!")
            
    st.markdown("---")
    st.subheader("Danger Zone")
    if st.button("RESET LEAGUE (Clear Matches)", type="primary"):
        st.session_state["data"] = utils.reset_league()
        st.session_state["match_history"] = []
        st.rerun()

elif page == "Matches":
    st.title("Match Day (Coach Mode)")
    
    data = st.session_state["data"]
    teams = data["teams"]
    matches = data["matches"]
    
    # --- Match Creator ---
    with st.expander("Create New Match", expanded=not matches):
        st.markdown("### Add Match")
        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        
        # Default round logic
        rounds_present = sorted(list(set(m["round"] for m in matches)))
        next_rnd = max(rounds_present) + 1 if rounds_present else 1
        
        round_input = c1.number_input("Round", min_value=1, value=next_rnd, step=1)
        
        team_options = {name: tid for tid, name in teams.items()}
        team_names = sorted(list(team_options.keys()))
        
        t1_name = c2.selectbox("Home Team", team_names, key="t1_sel")
        t2_name = c3.selectbox("Away Team", team_names, index=1 if len(team_names)>1 else 0, key="t2_sel")
        
        if c4.button("Add Match", type="secondary"):
            if t1_name == t2_name:
                st.error("Teams must be different!")
            else:
                st.session_state["data"] = utils.add_match(
                    st.session_state["data"], 
                    round_input, 
                    team_options[t1_name], 
                    team_options[t2_name]
                )
                st.success(f"Added Match!")
                st.rerun()

    st.markdown("---")

    # --- Rounds Display (Tabs) ---
    if not matches:
        st.info("No matches yet. Use the creator above to start the season!")
    else:
        rounds = sorted(list(set(m["round"] for m in matches)))
        tabs = st.tabs([f"Round {r}" for r in rounds])
        
        for r_idx, tab in enumerate(tabs):
            r_num = rounds[r_idx]
            with tab:
                current_matches = [m for m in matches if m["round"] == r_num]
                
                for match in current_matches:
                    if match["t1"] not in teams or match["t2"] not in teams: continue
                    t1_n, t2_n = teams[match["t1"]], teams[match["t2"]]
                    match_id = match['id']

                    # Card
                    with st.container():
                        st.markdown(f'<div class="match-card">', unsafe_allow_html=True)
                        
                        # Header with Delete Button
                        h1, h2, h3, h4 = st.columns([3, 1, 3, 0.5])
                        with h1: st.markdown(f"<h3 style='text-align:right'>{t1_n}</h3>", unsafe_allow_html=True)
                        with h2: st.markdown("<h3 style='text-align:center'>VS</h3>", unsafe_allow_html=True)
                        with h3: st.markdown(f"<h3 style='text-align:left'>{t2_n}</h3>", unsafe_allow_html=True)
                        with h4:
                            if st.button("🗑️", key=f"del_{match_id}"):
                                delete_match_callback(match_id)
                                st.rerun()

                        # Scores
                        col_l, col_c, col_r = st.columns([1, 0.4, 1])
                        
                        with col_l:
                            gc1, gc2 = st.columns([1, 1])
                            if gc1.button("-", key=f"{match_id}_t1_gm"): update_stat(match_id, "goal", -1, 1)
                            if gc2.button("+G", key=f"{match_id}_t1_gp"): update_stat(match_id, "goal", 1, 1)
                            fc1, fc2 = st.columns([1, 1])
                            fc1.write(f"Fouls: {match['f1']}")
                            if fc2.button("+F", key=f"{match_id}_t1_fp"): update_stat(match_id, "foul", 1, 1)

                        with col_c:
                            st.markdown(f"<h1 style='text-align:center; margin:0;'>{match['g1']} - {match['g2']}</h1>", unsafe_allow_html=True)

                        with col_r:
                            gc1, gc2 = st.columns([1, 1])
                            if gc1.button("-", key=f"{match_id}_t2_gm"): update_stat(match_id, "goal", -1, 2)
                            if gc2.button("+G", key=f"{match_id}_t2_gp"): update_stat(match_id, "goal", 1, 2)
                            fc1, fc2 = st.columns([1, 1])
                            fc1.write(f"Fouls: {match['f2']}")
                            if fc2.button("+F", key=f"{match_id}_t2_fp"): update_stat(match_id, "foul", 1, 2)
                        
                        st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)

    # Footer Actions
    ac1, ac2 = st.columns(2)
    with ac1:
        if st.button("Undo Last Change"):
            if st.session_state["match_history"]:
                last_state = st.session_state["match_history"].pop()
                for idx, m in enumerate(st.session_state["data"]["matches"]):
                    if m["id"] == last_state["id"]:
                        st.session_state["data"]["matches"][idx] = last_state
                        break
                st.rerun()
    with ac2:
        if st.button("Save Matchday Results", type="primary"):
            save_state()

elif page == "Standings":
    st.title("League Standings")
    if st.button("Refresh Table", type="secondary"): st.rerun()
    df = utils.calculate_standings(st.session_state["data"])
    st.markdown(df.to_html(classes="dataframe"), unsafe_allow_html=True)
    st.info("Tie-breakers: Points > Goal Difference > Goals For")
