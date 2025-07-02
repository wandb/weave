"""Example showing how to create an async FastAPI server using the new async interface."""

from fastapi import APIRouter, FastAPI

from weave.trace_server.adapters.sync_to_async_adapter import SyncToAsyncAdapter
from weave.trace_server.reference.generate import (
    AsyncServiceDependency,
    AsyncTraceService,
    AuthParams,
    generate_async_routes,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def create_async_sqlite_trace_service(auth: AuthParams) -> AsyncTraceService:
    """Factory function to create an async trace service from a sync SQLite server."""
    # Create the sync SQLite server
    sync_server = SqliteTraceServer(db_path=":memory:")

    # Wrap it with the sync-to-async adapter
    async_server = SyncToAsyncAdapter(sync_server)

    # Return the async trace service
    return AsyncTraceService(async_server)


def create_async_app() -> FastAPI:
    """Create a FastAPI app with async endpoints."""
    app = FastAPI(title="Weave Async Trace Server")

    # Create the async service dependency
    async_service_dependency = AsyncServiceDependency(
        service_factory=create_async_sqlite_trace_service
    )

    # Generate async routes
    async_router = generate_async_routes(APIRouter(), async_service_dependency)

    # Include the router in the app
    app.include_router(async_router)

    return app


# Create the app
app = create_async_app()


@app.get("/")
async def root():
    """Root endpoint to verify server is running."""
    return {"message": "Weave Async Trace Server is running"}


if __name__ == "__main__":
    import uvicorn

    print("Starting async Weave trace server...")
    print("Server will be available at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000)
