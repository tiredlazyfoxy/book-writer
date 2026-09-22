"""Admin HTTP route package (``/api/admin/...``).

Package marker for the admin-only route layer (feature 005). Each admin router
owns its own ``/api/admin/...`` prefix and is mounted individually by the
composition root (``app/main.py``); this package does not aggregate. The users
router lives in :mod:`app.routes.admin.users`.
"""
