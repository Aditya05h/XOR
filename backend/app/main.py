from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.contracts import BootstrapDTO, GridPosition, HealthDTO, RackLayout
from app.core.ao02_state_and_graph import ResourceType


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health", response_model=HealthDTO)
    def health() -> HealthDTO:
        return HealthDTO()

    @app.get("/api/bootstrap", response_model=BootstrapDTO)
    def bootstrap() -> BootstrapDTO:
        # Public reference geometry only. No tenant or operational data is exposed.
        return BootstrapDTO(
            app_name=settings.app_name,
            resources=list(ResourceType),
            racks=[
                RackLayout(rack_id=f"R-{i + 1:02}", grid_position=GridPosition(row=i // 4, col=i % 4))
                for i in range(12)
            ],
            cooling_units=["CRAC Unit A (North)", "CRAC Unit B (South)"],
        )

    return app


app = create_app()
