from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.openapi import API_VERSION, DESCRIPTION, TAGS_METADATA, build_openapi
from app.api.routers import applications, auth, companies, products, system, underwriter
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, setup_logging

API_PREFIX = "/api/v1"


def _operation_id(route: APIRoute) -> str:
    # operationId = имя функции-обработчика (camelCase): из него генерируются имена функций клиента
    return route.name


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Умный кредитный кабинет — API ядра",
        version=API_VERSION,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        generate_unique_id_function=_operation_id,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    for router in (auth, products, companies, applications, underwriter):
        app.include_router(router.router, prefix=API_PREFIX)
    app.include_router(underwriter.audit_router, prefix=API_PREFIX)
    app.include_router(system.router)

    app.openapi = lambda: build_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
