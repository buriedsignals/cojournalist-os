"""Port interfaces for the adapter pattern.

Services depend on these ABCs, never on concrete implementations.
Adapters in app.adapters.aws/ and app.adapters.supabase/ provide
concrete implementations selected at startup via DEPLOYMENT_TARGET.
"""
