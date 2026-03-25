from superset.app import create_app

def diagnostic():
    app = create_app()
    with app.app_context():
        # Import models inside context
        from superset.extensions import db
        from superset.models.dashboard import Dashboard
        from superset.models.embedded_dashboard import EmbeddedDashboard
        from flask_appbuilder.security.sqla.models import Role, PermissionView
        
        print("--- ROLES ---")
        roles = db.session.query(Role).all()
        for r in roles:
            print(f"- {r.name}")
        
        print("\n--- DASHBOARDS ---")
        dashes = db.session.query(Dashboard).all()
        for d in dashes:
            print(f"ID: {d.id}, UUID: {d.uuid}, Title: {d.dashboard_title}, Published: {d.published}")
            
        print("\n--- EMBEDDED CONFIGS ---")
        embeds = db.session.query(EmbeddedDashboard).all()
        for e in embeds:
            print(f"Dash ID: {e.dashboard_id}, Embedded UUID: {e.uuid}")

        print("\n--- PUBLIC ROLE PERMS ---")
        public = db.session.query(Role).filter_by(name='Public').first()
        if public:
            sorted_perms = sorted(public.permissions, key=lambda x: (str(x.view_menu.name), str(x.permission.name)))
            for p in sorted_perms:
                print(f"- {p.permission.name} on {p.view_menu.name}")
        else:
            print("Public role NOT FOUND")

if __name__ == "__main__":
    diagnostic()
