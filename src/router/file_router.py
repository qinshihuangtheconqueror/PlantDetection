from fastapi import APIRouter
from src.utils.logger import logger
from src.module.files.file_services import handle_file_upload

router = APIRouter(prefix="/api/files", tags=["file"])


@router.get(path="/upload")
async def root():
    logger.info("FILE UPLOAD API!")
    handle_file_upload()
    return {"message": "file upload api"}