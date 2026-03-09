from db.repo_json import load_db, save_db, load_analytics, save_analytics

db = load_db()
analytics = load_analytics()

old_events = db.get("events", []) or []
current_events = analytics.get("events", []) or []

if old_events:
    analytics["events"] = current_events + old_events
    save_analytics(analytics)

    db.pop("events", None)
    save_db(db)

    print(f"Se migraron {len(old_events)} eventos a analytics.json")
else:
    print("No había eventos para migrar")