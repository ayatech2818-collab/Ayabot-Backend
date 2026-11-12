
import re


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
        paragraph.strip()
        for paragraph in text.splitlines()
        if paragraph.strip()
    ]

    chunks: list[str] = []
    current = ""

    
    def split_long_text(value: str) -> list[str]:
        """Split oversized text at sentence/word boundaries with overlap."""

        target_size = chunk_size - overlap
        sentences = re.split(r"(?<=[.!?])\s+", value.strip())

        base_chunks: list[str] = []
        buffer = ""

        for sentence in sentences:
            if len(sentence) > target_size:
                if buffer:
                    base_chunks.append(buffer)
                    buffer = ""

                words = sentence.split()
                word_buffer = ""

                for word in words:
                    candidate = (
                        f"{word_buffer} {word}"
                        if word_buffer
                        else word
                    )

                    if len(candidate) <= target_size:
                        word_buffer = candidate
                    else:
                        if word_buffer:
                            base_chunks.append(word_buffer)
                        word_buffer = word

                if word_buffer:
                    base_chunks.append(word_buffer)

                continue

            candidate = (
                f"{buffer} {sentence}"
                if buffer
                else sentence
            )

            if len(candidate) <= target_size:
                buffer = candidate
            else:
                if buffer:
                    base_chunks.append(buffer)
                buffer = sentence

        if buffer:
            base_chunks.append(buffer)

        if not overlap or len(base_chunks) <= 1:
            return base_chunks

        result = [base_chunks[0]]

        for index in range(1, len(base_chunks)):
            previous = base_chunks[index - 1]
            prefix = previous[-overlap:]

            boundary = prefix.find(" ")
            if boundary != -1:
                prefix = prefix[boundary + 1:]

            result.append(f"{prefix} {base_chunks[index]}")

        return result


    def get_overlap(value: str) -> str:
        if not overlap or len(value) <= overlap:
            return value

        result = value[-overlap:]

        # Start at a word boundary.
        first_space = result.find(" ")

        if first_space != -1:
            result = result[first_space + 1:]

        return result

    for paragraph in paragraphs:

        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""

            pieces = split_long_text(paragraph)

            for piece in pieces:
                if current and len(current) + len(piece) + 1 <= chunk_size:
                    current = f"{current}\n{piece}"
                else:
                    if current:
                        chunks.append(current)

                    current = piece

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

            overlap_text = get_overlap(current)

            current = (
                f"{overlap_text}\n{paragraph}"
                if overlap_text
                and len(overlap_text) + len(paragraph) + 1 <= chunk_size
                else paragraph
            )

    if current:
        chunks.append(current)

    return chunks
