from app.services.storage_service import download_knowledge_file
from app.services.document_extractor import extract_text


file_path = (
    "2954c1bd-466c-403e-af6d-3c7e6f419d93/"
    "faedb30d-9ee5-4b97-8649-db18e70e9343/"
    "original.pdf"
)

file_content = download_knowledge_file(file_path)

text = extract_text(
    file_content=file_content,
    file_name="5.1.1-Dec 2025-Ayadi Courses.pdf",
)

print("Extraction successful!")
print("Characters extracted:", len(text))
print("\nFirst 1000 characters:\n")
print(text[:1000])