# No changes needed, just identifying the file.
from superset.extensions import db
from superset.security.manager import SupersetSecurityManager

def fix_public_role():
    app = create_app()
    with app.app_context():
        sm = app.appbuilder.sm
        # Grant global permissions to both Public and Gamma roles
        permissions = [
            ('can_access', 'all_database_access'),
            ('can_access', 'all_datasource_access'),
            ('can_read', 'Dashboard'),
            ('can_read', 'Chart'),
            ('can_read', 'Dataset'),
            ('can_external_metadata', 'Datasource'),
            ('can_explore_json', 'Superset'),
            ('can_embedded', 'Superset')
        ]
        
        for role_name in ['Public', 'Gamma']:
            role = sm.find_role(role_name)
            if not role:
                role = sm.add_role(role_name)
                print(f"Created role: {role_name}")
            
            for perm, view in permissions:
                view_menu = sm.find_view_menu(view)
                if not view_menu:
                    view_menu = sm.add_view_menu(view)
                
                p = sm.find_permission(perm)
                if not p:
                    p = sm.add_permission(perm)
                
                pv = sm.find_permission_view_menu(perm, view)
                if not pv:
                    pv = sm.add_permission_view_menu(perm, view)
                
                if pv not in role.permissions:
                    sm.add_permission_role(role, pv)
                    print(f"Granted {perm} on {view} to {role_name}")

        db.session.commit()
        print("Successfully synchronized Public and Gamma role permissions")

if __name__ == "__main__":
    fix_public_role()
