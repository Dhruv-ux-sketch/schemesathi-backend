from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Bookmark
from app.auth import get_current_user
from app.schemas import BookmarkCreate, BookmarkOut

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=list[BookmarkOut])
def list_bookmarks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Bookmark).filter(Bookmark.user_id == current_user.id).all()


@router.post("", response_model=BookmarkOut)
def add_bookmark(
    request: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == current_user.id, Bookmark.scheme_name == request.scheme_name)
        .first()
    )
    if existing:
        return existing

    bookmark = Bookmark(
        user_id=current_user.id,
        scheme_name=request.scheme_name,
        source_file=request.source_file,
        note=request.note,
    )
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.delete("/{bookmark_id}")
def remove_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookmark = (
        db.query(Bookmark)
        .filter(Bookmark.id == bookmark_id, Bookmark.user_id == current_user.id)
        .first()
    )
    if not bookmark:
        raise HTTPException(404, "Bookmark not found")
    db.delete(bookmark)
    db.commit()
    return {"status": "deleted"}
