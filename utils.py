import json
import os
import sqlite3
import pandas as pd

DB_FILE = "league.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_num INTEGER,
                    t1_id INTEGER,
                    t2_id INTEGER,
                    g1 INTEGER DEFAULT 0,
                    g2 INTEGER DEFAULT 0,
                    f1 INTEGER DEFAULT 0,
                    f2 INTEGER DEFAULT 0,
                    is_done BOOLEAN DEFAULT 0,
                    FOREIGN KEY(t1_id) REFERENCES teams(id),
                    FOREIGN KEY(t2_id) REFERENCES teams(id)
                )''')
    
    # Check if teams exist, if not add defaults
    c.execute("SELECT count(*) FROM teams")
    if c.fetchone()[0] == 0:
        default_teams = [(f"Team {i}",) for i in range(1, 7)]
        c.executemany("INSERT INTO teams (name) VALUES (?)", default_teams)
    
    conn.commit()
    conn.close()

def load_data():
    # Ensure DB exists
    init_db()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    data = {"teams": {}, "matches": []}
    
    # Load Teams
    c.execute("SELECT * FROM teams")
    rows = c.fetchall()
    for r in rows:
        data["teams"][str(r["id"])] = r["name"]
        
    # Load Matches
    c.execute("SELECT * FROM matches")
    rows = c.fetchall()
    for r in rows:
        m = dict(r)
        # Rename is_done to done, t1_id to t1, etc to match app.py expectations
        # The DB schema uses t1_id, t2_id, is_done.
        # The app expects: id, round, t1, t2, g1, g2, f1, f2, done
        match_obj = {
            "id": m["id"],
            "round": m["round_num"],
            "t1": str(m["t1_id"]),
            "t2": str(m["t2_id"]),
            "g1": m["g1"],
            "g2": m["g2"],
            "f1": m["f1"],
            "f2": m["f2"],
            "done": bool(m["is_done"])
        }
        data["matches"].append(match_obj)
        
    conn.close()
    return data

def save_data(data):
    """
    Saves the 'matches' list from the data dict to SQLite.
    Since app.py modifies matches in memory and then calls this,
    we iterate through data['matches'] and update them.
    Teams are updated via separate calls, so strictly we could just update matches here.
    """
    conn = get_connection()
    c = conn.cursor()
    
    for m in data["matches"]:
        c.execute("""
            UPDATE matches 
            SET g1=?, g2=?, f1=?, f2=?, is_done=?
            WHERE id=?
        """, (m["g1"], m["g2"], m["f1"], m["f2"], m["done"], m["id"]))
        
    conn.commit()
    conn.close()

def reset_league():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    return load_data()

def update_team_name(data, team_id, new_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE teams SET name = ? WHERE id = ?", (new_name, team_id))
    conn.commit()
    conn.close()
    return load_data()

def add_team(data, name="New Team"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO teams (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return load_data()

def add_match(data, round_num, t1_id, t2_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matches (round_num, t1_id, t2_id, g1, g2, f1, f2, is_done)
        VALUES (?, ?, ?, 0, 0, 0, 0, 0)
    """, (round_num, t1_id, t2_id))
    conn.commit()
    conn.close()
    return load_data()

def delete_match(data, match_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()
    return load_data()

def calculate_standings(data):
    # This logic operates on the 'data' dictionary which is already loaded.
    # No changes needed for SQLite since 'data' structure is preserved by load_data.
    teams = data["teams"]
    matches = data["matches"]
    
    # Initialize stats for ALL teams
    stats = {tid: {"Team": name, "GP": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "PTS": 0} 
             for tid, name in teams.items()}
    
    # Process matches
    for m in matches:
        if not m.get("done") and (m["g1"] == 0 and m["g2"] == 0 and m["f1"] == 0 and m["f2"] == 0):
             continue

        if not m.get("done"):
             continue
            
        t1, t2 = m["t1"], m["t2"]
        g1, g2 = m["g1"], m["g2"]
        
        # Verify teams exist
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

    # Reorder and Filter Columns
    wanted_cols = ["Team", "PTS", "GP", "W", "D", "L", "GD"]
    final_cols = [c for c in wanted_cols if c in df.columns]
    df = df[final_cols]
    
    return df

def restore_from_backup(backup_data):
    """
    Restores the database state from a JSON-compatible dictionary.
    Exepcted structure: {"teams": {"id": "name"}, "matches": [...]}
    """
    # 1. Reset DB
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    init_db()
    
    conn = get_connection()
    c = conn.cursor()
    
    # 2. Restore Teams
    # We need to preserve IDs. Since auto-increment is used, we can force IDs if we turn off auto-increment or just insert.
    # SQLite allows inserting into INTEGER PRIMARY KEY columns explicitly.
    teams = backup_data.get("teams", {})
    if teams:
        c.execute("DELETE FROM teams") # Ensure clean slate
        for t_id, t_name in teams.items():
            c.execute("INSERT INTO teams (id, name) VALUES (?, ?)", (int(t_id), t_name))
            
    # 3. Restore Matches
    matches = backup_data.get("matches", [])
    if matches:
        # DB schema: id, round_num, t1_id, t2_id, g1, g2, f1, f2, is_done
        # Backup schema (from matches match_obj): id, round, t1, t2, g1, g2, f1, f2, done
        c.execute("DELETE FROM matches")
        for m in matches:
            c.execute("""
                INSERT INTO matches (id, round_num, t1_id, t2_id, g1, g2, f1, f2, is_done)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m["id"], 
                m["round"], 
                int(m["t1"]), 
                int(m["t2"]), 
                m["g1"], 
                m["g2"], 
                m["f1"], 
                m["f2"], 
                1 if m["done"] else 0
            ))
            
    conn.commit()
    conn.close()
    return load_data()
