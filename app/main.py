import logging
from collections.abc import Callable, Generator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine, get_db
from app.models import Task
from app.schemas import TaskCreate, TaskRead, TaskUpdate

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("taskboard")


def create_app(
    db_engine: Engine = engine,
    session_dependency: Callable[..., Generator[Session, None, None]] = get_db,
) -> FastAPI:
    application = FastAPI(title="Server Taskboard API", version="1.0.0")
    application.state.db_engine = db_engine
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(
            "Database operation failed: method=%s path=%s error_type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database unavailable"},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(request: Request) -> JSONResponse:
        try:
            with request.app.state.db_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error(
                "Readiness check failed: error_type=%s",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not ready", "database": "unavailable"},
            )
        return JSONResponse(content={"status": "ready", "database": "ok"})

    @application.get("/api/tasks", response_model=list[TaskRead])
    def list_tasks(db: Session = Depends(session_dependency)) -> list[Task]:
        return list(db.scalars(select(Task).order_by(Task.id.desc())))

    @application.post("/api/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
    def create_task(payload: TaskCreate, db: Session = Depends(session_dependency)) -> Task:
        task = Task(title=payload.title.strip(), description=payload.description.strip())
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info("Created task id=%s", task.id)
        return task

    @application.patch("/api/tasks/{task_id}", response_model=TaskRead)
    def update_task(
        task_id: int, payload: TaskUpdate, db: Session = Depends(session_dependency)
    ) -> Task:
        task = db.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        changes = payload.model_dump(exclude_unset=True)
        if "title" in changes:
            changes["title"] = changes["title"].strip()
        if "description" in changes:
            changes["description"] = changes["description"].strip()
        for field, value in changes.items():
            setattr(task, field, value)
        db.commit()
        db.refresh(task)
        logger.info("Updated task id=%s", task.id)
        return task

    @application.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_task(task_id: int, db: Session = Depends(session_dependency)) -> Response:
        task = db.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        db.delete(task)
        db.commit()
        logger.info("Deleted task id=%s", task_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return application


app = create_app()
