from app.services.storage_service import download_knowledge_file
from app.services.document_extractor import extract_text
from app.services.text_chunker import split_text


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

chunks = split_text(text)

print("Chunking successful!")
print("Total characters:", len(text))
print("Total chunks:", len(chunks))

for index, chunk in enumerate(chunks):
    print(f"\n--- Chunk {index} ({len(chunk)} characters) ---")
    print(chunk)