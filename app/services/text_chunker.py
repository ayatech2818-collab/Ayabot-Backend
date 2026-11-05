
def split_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[str]:

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid overlap value")

    text = text.strip()

    if not text:
        return []

    paragraphs = [
        p.strip()
        for p in text.splitlines()
        if p.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:

        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""

            start = 0

            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))

                if end < len(paragraph):
                    boundary = paragraph.rfind(" ", start, end)

                    if boundary > start:
                        end = boundary

                piece = paragraph[start:end].strip()

                if piece:
                    chunks.append(piece)

                start = end

                if start < len(paragraph):
                    start = max(
                        start - overlap,
                        0,
                    )

                    # Move backwards to a word boundary.
                    while start > 0 and paragraph[start] != " ":
                        start -= 1

                    if start == 0:
                        start = end

            continue

        candidate = (
            f"{current}\n{paragraph}"
            if current
            else paragraph
        )

        if len(candidate) <= chunk_size:
            current = candidate

        else:
            if current:
                chunks.append(current)

            overlap_text = ""

            if overlap:
                overlap_text = current[-overlap:]

                # Avoid starting the next chunk in the middle of a word.
                if len(current) > overlap:
                    boundary = overlap_text.find(" ")
                    if boundary != -1:
                        overlap_text = overlap_text[boundary + 1:]

            current = (
                f"{overlap_text}\n{paragraph}"
                if overlap_text
                else paragraph
            )

    if current:
        chunks.append(current)

    return chunks
