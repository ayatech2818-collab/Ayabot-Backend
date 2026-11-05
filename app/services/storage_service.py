
from app.core.supabase import get_supabase_client


BUCKET_NAME = "ayabot-knowledge"


def upload_knowledge_file(
    file_path: str,
    file_content: bytes,
    content_type: str,
) -> str:
    """
    Upload a knowledge document to private Supabase Storage.
    Returns the storage path.
    """

    supabase = get_supabase_client()

    response = supabase.storage.from_(BUCKET_NAME).upload(
        path=file_path,
        file=file_content,
        file_options={
            "content-type": content_type,
            "upsert": "false",
        },
    )

    return file_path


def delete_knowledge_file(file_path: str) -> None:
    """Delete a knowledge document from private Supabase Storage."""

    supabase = get_supabase_client()

    supabase.storage.from_(BUCKET_NAME).remove([file_path])


def download_knowledge_file(file_path: str) -> bytes:
    """Download a knowledge document from private Supabase Storage."""

    supabase = get_supabase_client()

    return supabase.storage.from_(BUCKET_NAME).download(file_path)
