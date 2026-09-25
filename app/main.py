from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import CLERK_PUBLISHABLE_KEY, STATIC_DIR, STATUTES_PATH
from app.database import init_db
from app.routers import agent, documents, events, evidence, vault
from app.statutes_loader import load_statute_table


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.statutes = load_statute_table(STATUTES_PATH)
    yield


app = FastAPI(title="CasaVault", lifespan=lifespan)

app.include_router(vault.router)
app.include_router(events.router)
app.include_router(agent.router)
app.include_router(evidence.router)
app.include_router(documents.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    """Public, non-secret config the frontend needs at load time. The
    publishable key is safe client-side by design (Clerk); null just means
    sign-in isn't configured yet and the frontend should skip it entirely."""
    return {"clerk_publishable_key": CLERK_PUBLISHABLE_KEY}


@app.get("/api/statutes")
def list_statutes():
    """Verified rules only — draft rules never leave the server. See
    app/statutes_loader.py and the status legend in statutes.yaml."""
    return app.state.statutes.verified_rules


# Mounted last so it acts as a catch-all for the plain HTML/JS front end
# without shadowing the /api/* routes above.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
