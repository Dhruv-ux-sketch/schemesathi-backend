import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from app.schemas import SchemeUploadResponse
from app.rag.ingest import ingest_file
from app.rag.vector_store import list_schemes, delete_scheme
from app.auth import require_admin
from app.models import User

router = APIRouter(prefix="/schemes", tags=["schemes"])

UPLOAD_DIR = Path("./data/uploaded_schemes")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("", response_model=list[str])
def get_schemes():
    """List all scheme names currently indexed in the vector store. Public - no auth needed."""
    return list_schemes()


@router.post("/upload", response_model=SchemeUploadResponse)
async def upload_scheme(
    scheme_name: str = Form(..., description="Human-readable scheme name, e.g. 'PM-Kisan'"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
):
    """Admin-only: upload a new scheme PDF/text file and index it immediately."""
    if not file.filename.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Only .pdf, .txt, or .md files are supported")

    dest_path = UPLOAD_DIR / file.filename
    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks_added = ingest_file(str(dest_path), scheme_name=scheme_name)

    return SchemeUploadResponse(
        filename=file.filename,
        chunks_added=chunks_added,
        status="indexed",
    )


@router.delete("/{scheme_name}")
def remove_scheme(scheme_name: str, admin: User = Depends(require_admin)):
    """Admin-only: remove a scheme (e.g. it's outdated/discontinued)."""
    deleted_count = delete_scheme(scheme_name)
    if deleted_count == 0:
        raise HTTPException(404, f"No chunks found for scheme '{scheme_name}'")
    return {"scheme_name": scheme_name, "chunks_deleted": deleted_count}
