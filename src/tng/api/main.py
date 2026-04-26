"""FastAPI application entry point.

Wires together all routers and configures the application with:
- Lifespan context manager for startup/shutdown hooks
- OpenAPI metadata (title, description, version, contact)
- All v1 routers

The ``app`` object is the WSGI/ASGI entry point imported by uvicorn.
The ``run()`` function is used by the ``tng-api`` CLI script.
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tng.api.dependencies import lifespan
from tng.api.routers import atoms, health, ingest, narratives, patterns, render, transforms

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transformable Narrative Graph System",
    description=(
        "A graph-native system for representing, transforming, and rendering "
        "literary narratives.  Stores narratives as property graphs in Neo4j and "
        "applies auditable literary transformations (POV, mood, genre, chronotope, "
        "reliability, Barthesian code overlay)."
    ),
    version="0.1.0",
    contact={"name": "Matt Briggs", "email": "matt.briggs@gmail.com"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(narratives.router)
app.include_router(patterns.router)
app.include_router(transforms.router)
app.include_router(render.router)
app.include_router(atoms.router)


def run() -> None:
    """CLI entry point — start the uvicorn server.

    Reads host and port from environment or uses defaults.
    """
    uvicorn.run("tng.api.main:app", host="0.0.0.0", port=8000, reload=False)
