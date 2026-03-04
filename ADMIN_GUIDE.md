# 👑 Admin & Management Guide

This document covers everything an administrator needs to know to manage the platform and empower their engineering teams.

---

## 📊 1. The Admin Experience

### Registration & Onboarding
- **Multi-Tenancy**: The first user to register an organization becomes the **Admin** for that `tenant_id`.
- **Organization Control**: Admins can invite or remove team members and assign roles (Viewer vs Admin).

### Data Source Management
- **Security**: Admins manage external SQL connections. Credentials are encrypted at rest.
- **Auto-Analysis**: When a source is added, the system automatically runs a discovery job to build the initial dashboard.

---

## 🤝 2. Team Handover & Empowerment

We move from "Building the Skeleton" to "Building the Muscles." 

### Strategic Phases:
1.  **Code Audit (Week 1)**: Teams take ownership and perform line-by-line critiques of the current MVP logic.
2.  **Quality Engineering**: Teams are responsible for 100% test coverage within their respective modules.
3.  **Invention Mode**: Teams should focus on the **Innovation Roadmaps** (DuckDB for CSV, Query Optimization for SQL).

### Communication Goal:
Instruct teams that their job isn't basic CRUD anymore—it's building high-performance AI engines. The assistant provided the foundation; the engineers provide the world-class scaling.

---

## 🛠️ 3. Admin-Only Capabilities
| Feature | Admin | Viewer |
| :--- | :---: | :---: |
| Connect Data Sources | ✅ | ❌ |
| Invite/Remove Users | ✅ | ❌ |
| View Org-wide History | ✅ | ❌ |
| Run Ad-hoc Analysis | ✅ | ✅ |
| View Dashboards | ✅ | ✅ |
