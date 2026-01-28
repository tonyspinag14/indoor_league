import json
import os
import pandas as pd

DATA_FILE = "league_data.json"

DEFAULT_DATA = {
    "teams": {str(i): f"Team {i}" for i in range(1, 7)},
    "matches": []  # List of match objects
}

def load_data():
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return DEFAULT_DATA

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def reset_league():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    return load_data()

def update_team_name(data, team_id, new_name):
    data["teams"][team_id] = new_name
    save_data(data)
    return data

def add_team(data, name="New Team"):
    # Find max ID
    current_ids = [int(i) for i in data["teams"].keys()]
    new_id = str(max(current_ids) + 1) if current_ids else "1"
    data["teams"][new_id] = name
    save_data(data)
    return data

def add_match(data, round_num, t1_id, t2_id):
    start_id = max([m["id"] for m in data["matches"]]) + 1 if data["matches"] else 0
    new_match = {
        "id": start_id,
        "round": round_num,
        "t1": t1_id,
        "t2": t2_id,
        "g1": 0, "g2": 0,
        "f1": 0, "f2": 0,
        "done": False
    }
    data["matches"].append(new_match)
    save_data(data)
    return data

def delete_match(data, match_id):
    data["matches"] = [m for m in data["matches"] if m["id"] != match_id]
    save_data(data)
    return data

def calculate_standings(data):
    teams = data["teams"]
    matches = data["matches"]
    
    # Initialize stats for ALL teams
    stats = {tid: {"Team": name, "GP": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "PTS": 0} 
             for tid, name in teams.items()}
    
    # Process matches
    for m in matches:
        if not m.get("done") and (m["g1"] == 0 and m["g2"] == 0 and m["f1"] == 0 and m["f2"] == 0):
             # Optional: count 0-0 unplayed matches as not played? 
             # For now, we count them as played if they exist in the list and user sees them.
             # Actually, logic said "done" flag. We generally only count "done" matches.
             # But our add_match initializes done=False. 
             # If user adds match, it appears on screen. 
             # Let's count it only if it has been interacted with OR we consider 0-0 start.
             # Common practice: 0-0 is a result if time passed, but here let's stick to "done" flag 
             # OR just simple existence if we trust user inputs score.
             # Actually, let's treat all added matches as GP=0 until customized? 
             # No, standard app: added match = 0-0 draw if not updated? 
             # Let's check `done` flag.
             pass

        if not m.get("done"):
             # If strictly unplayed, skip standings update? 
             # User said "Matches: Manual pairings... Save Matchday".
             # If I add a match, it is 0-0.
             continue
            
        t1, t2 = m["t1"], m["t2"]
        g1, g2 = m["g1"], m["g2"]
        
        # Verify teams exist (in case deleted, though we don't hold delete logic yet)
        if t1 not in stats or t2 not in stats:
            continue

        # Update GP
        stats[t1]["GP"] += 1
        stats[t2]["GP"] += 1
        
        # Update Goals
        stats[t1]["GF"] += g1
        stats[t1]["GA"] += g2
        stats[t1]["GD"] += (g1 - g2)
        
        stats[t2]["GF"] += g2
        stats[t2]["GA"] += g1
        stats[t2]["GD"] += (g2 - g1)
        
        # Update W/D/L/PTS
        if g1 > g2:
            stats[t1]["W"] += 1
            stats[t1]["PTS"] += 3
            stats[t2]["L"] += 1
        elif g2 > g1:
            stats[t2]["W"] += 1
            stats[t2]["PTS"] += 3
            stats[t1]["L"] += 1
        else:
            stats[t1]["D"] += 1
            stats[t1]["PTS"] += 1
            stats[t2]["D"] += 1
            stats[t2]["PTS"] += 1

    df = pd.DataFrame.from_dict(stats, orient="index")
    
    # Sort: PTS > GD > GF
    if not df.empty:
        df = df.sort_values(by=["PTS", "GD", "GF"], ascending=[False, False, False])

    # Reorder and Filter Columns as requested (PTS after Team, Hide GF/GA)
    wanted_cols = ["Team", "PTS", "GP", "W", "D", "L", "GD"]
    # Ensure column exists before selecting (in case of empty df with no cols initialized correctly)
    final_cols = [c for c in wanted_cols if c in df.columns]
    df = df[final_cols]
    
    return df
