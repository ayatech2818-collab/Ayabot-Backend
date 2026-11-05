from app.services.storage_service import (
    upload_knowledge_file,
    download_knowledge_file,
    delete_knowledge_file,
)

file_path = "test-product/test-document/test.txt"
content = b"AYABOT storage integration test."

# 1. Upload
uploaded_path = upload_knowledge_file(
    file_path=file_path,
    file_content=content,
    content_type="text/plain",
)
print("Upload successful:", uploaded_path)

# 2. Download
downloaded = download_knowledge_file(file_path)
print("Download successful:", downloaded.decode())

# 3. Delete
delete_knowledge_file(file_path)
print("Delete successful")