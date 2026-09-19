import os

import reflex as rx

FRONTEND_PORT = 3210
BACKEND_PORT = 8210

# The frontend bundle is compiled with api_url baked in, so it must be an address the
# BROWSER can reach -- not the server's own. Left as localhost, opening the app from a
# phone over Tailscale makes the phone dial its own localhost and everything fails:
# no websocket, no PDF preview, no obvious error. serve.sh sets this automatically.
PUBLIC_HOST = os.environ.get("RF_PUBLIC_HOST", "localhost")
IS_REMOTE = PUBLIC_HOST not in ("localhost", "127.0.0.1")

config = rx.Config(
    app_name="rfactory",
    app_module_import="rfactory.app",
    frontend_port=FRONTEND_PORT,
    backend_port=BACKEND_PORT,
    api_url=f"http://{PUBLIC_HOST}:{BACKEND_PORT}",
    deploy_url=f"http://{PUBLIC_HOST}:{FRONTEND_PORT}",
    # Vite refuses requests carrying an unrecognised Host header, which is exactly what
    # a .ts.net name is. Named explicitly rather than set to True.
    vite_allowed_hosts=[PUBLIC_HOST] if IS_REMOTE else False,
    # Declared explicitly: implicit Radix enablement is deprecated and removed in 1.0.
    plugins=[rx.plugins.RadixThemesPlugin(), rx.plugins.SitemapPlugin()],
)
