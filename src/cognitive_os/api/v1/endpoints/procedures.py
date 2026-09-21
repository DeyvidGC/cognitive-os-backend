from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from cognitive_os.api.dependencies import Db, Member
from cognitive_os.application import procedures
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Procedure, ProcedureVersion, Tutorial
from cognitive_os.schemas.procedures import (
    KnowledgeResult, ProcedureCreate, ProcedureResponse, StepReorder, StepResponse, StepWrite,
    TutorialResponse, TutorialWrite, VersionCreate, VersionResponse,
)

router = APIRouter(tags=["procedures"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/procedures", response_model=ProcedureResponse, status_code=201)
def create_procedure(data: ProcedureCreate, db: Db, member: Member):
    return procedures.create_procedure(db, member, data)


@router.get("/procedures", response_model=list[ProcedureResponse])
def list_procedures(db: Db, member: Member, limit: Limit = 20, offset: Offset = 0):
    query = select(Procedure).where(Procedure.organization_id == member.organization_id)
    if member.role == "reader":
        query = query.where(select(ProcedureVersion.id).where(
            ProcedureVersion.procedure_id == Procedure.id,
            ProcedureVersion.organization_id == member.organization_id,
            ProcedureVersion.status == "published").exists())
    return db.scalars(query.order_by(Procedure.created_at.desc(), Procedure.id).limit(limit).offset(offset)).all()


@router.post("/procedures/{procedure_id}/versions", response_model=VersionResponse, status_code=201)
def create_version(procedure_id: UUID, data: VersionCreate, db: Db, member: Member):
    return procedures.create_version(db, member, procedure_id, data)


@router.get("/procedures/{procedure_id}/versions", response_model=list[VersionResponse])
def list_versions(procedure_id: UUID, db: Db, member: Member, limit: Limit = 20, offset: Offset = 0):
    procedures.get_procedure(db, member, procedure_id)
    query = select(ProcedureVersion).where(ProcedureVersion.organization_id == member.organization_id,
                                           ProcedureVersion.procedure_id == procedure_id)
    if member.role == "reader":
        query = query.where(ProcedureVersion.status == "published")
    return db.scalars(query.order_by(ProcedureVersion.version_number.desc()).limit(limit).offset(offset)).all()


@router.get("/procedure-versions/{version_id}", response_model=VersionResponse)
def get_version(version_id: UUID, db: Db, member: Member):
    return procedures.get_version(db, member, version_id)


@router.post("/procedure-versions/{version_id}/steps", response_model=StepResponse, status_code=201)
def create_step(version_id: UUID, data: StepWrite, db: Db, member: Member):
    return procedures.write_step(db, member, version_id, data)


@router.put("/procedure-versions/{version_id}/steps/reorder", response_model=list[StepResponse])
def reorder_steps(version_id: UUID, data: StepReorder, db: Db, member: Member):
    return procedures.reorder_steps(db, member, version_id, data.step_ids)


@router.put("/procedure-versions/{version_id}/steps/{step_id}", response_model=StepResponse)
def update_step(version_id: UUID, step_id: UUID, data: StepWrite, db: Db, member: Member):
    return procedures.write_step(db, member, version_id, data, step_id)


@router.get("/procedure-versions/{version_id}/steps", response_model=list[StepResponse])
def list_steps(version_id: UUID, db: Db, member: Member):
    return procedures.version_steps(db, member, version_id)


@router.put("/procedure-versions/{version_id}/tutorial", response_model=TutorialResponse)
def write_tutorial(version_id: UUID, data: TutorialWrite, db: Db, member: Member):
    return procedures.write_tutorial(db, member, version_id, data.content)


@router.get("/procedure-versions/{version_id}/tutorial", response_model=TutorialResponse)
def get_tutorial(version_id: UUID, db: Db, member: Member):
    procedures.get_version(db, member, version_id)
    tutorial = db.scalar(select(Tutorial).where(Tutorial.organization_id == member.organization_id,
                                               Tutorial.version_id == version_id, Tutorial.format == "markdown"))
    if tutorial is None:
        raise ApplicationError(404, "Tutorial not found")
    return tutorial


@router.post("/procedure-versions/{version_id}/submit", response_model=VersionResponse)
def submit(version_id: UUID, db: Db, member: Member):
    return procedures.transition(db, member, version_id, "submit")


@router.post("/procedure-versions/{version_id}/return", response_model=VersionResponse)
def return_to_draft(version_id: UUID, db: Db, member: Member):
    return procedures.transition(db, member, version_id, "return")


@router.post("/procedure-versions/{version_id}/approve", response_model=VersionResponse)
def approve(version_id: UUID, db: Db, member: Member):
    return procedures.transition(db, member, version_id, "approve")


@router.post("/procedure-versions/{version_id}/publish", response_model=VersionResponse)
def publish(version_id: UUID, db: Db, member: Member):
    return procedures.publish(db, member, version_id)


@router.post("/procedure-versions/{version_id}/retire", response_model=VersionResponse)
def retire(version_id: UUID, db: Db, member: Member):
    return procedures.transition(db, member, version_id, "retire")


@router.get("/knowledge/search", response_model=list[KnowledgeResult], tags=["knowledge"])
def search_knowledge(db: Db, member: Member, q: Annotated[str, Query(min_length=1, max_length=500)],
                     limit: Limit = 10):
    return procedures.search_knowledge(db, member.organization_id, q, limit)
