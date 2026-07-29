import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas import SchemeUploadResponse
from app.rag.ingest import ingest_file
from app.rag.vector_store import list_schemes, delete_scheme
from app.auth import require_admin
from app.models import User, Scheme
from app.db import get_db

router = APIRouter(prefix="/schemes", tags=["schemes"])

UPLOAD_DIR = Path("./data/uploaded_schemes")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("", response_model=list[str])
def get_schemes():
    """List all scheme names currently indexed in the vector store. Public - no auth needed."""
    return list_schemes()


@router.get("/urls")
def get_scheme_urls(db: Session = Depends(get_db)):
    """Public: mapping of scheme_name -> official_url, used for 'Register' buttons."""
    rows = db.query(Scheme).filter(Scheme.official_url.isnot(None)).all()
    return {row.name: row.official_url for row in rows}


@router.post("/upload", response_model=SchemeUploadResponse)
async def upload_scheme(
    scheme_name: str = Form(..., description="Human-readable scheme name, e.g. 'PM-Kisan'"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: upload a new scheme PDF/text file and index it immediately."""
    if not file.filename.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Only .pdf, .txt, or .md files are supported")

    dest_path = UPLOAD_DIR / file.filename
    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    result = ingest_file(str(dest_path), scheme_name=scheme_name)

    existing = db.query(Scheme).filter(Scheme.name == scheme_name).first()
    if existing:
        existing.official_url = result["official_url"]
        existing.source_file = file.filename
    else:
        db.add(Scheme(name=scheme_name, official_url=result["official_url"], source_file=file.filename))
    db.commit()

    return SchemeUploadResponse(
        filename=file.filename,
        chunks_added=result["chunks_added"],
        status="indexed",
    )


@router.delete("/{scheme_name}")
def remove_scheme(scheme_name: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: remove a scheme (e.g. it's outdated/discontinued)."""
    deleted_count = delete_scheme(scheme_name)
    if deleted_count == 0:
        raise HTTPException(404, f"No chunks found for scheme '{scheme_name}'")
    db.query(Scheme).filter(Scheme.name == scheme_name).delete()
    db.commit()
    return {"scheme_name": scheme_name, "chunks_deleted": deleted_count}