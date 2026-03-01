import os


# -----------------------------
# Load Raw Documents
# -----------------------------
def load_documents(data_folder="data"):
    documents = []

    for filename in os.listdir(data_folder):
        if filename.endswith(".txt"):
            file_path = os.path.join(data_folder, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

                documents.append({
                    "filename": filename,
                    "content": text
                })

    return documents


# -----------------------------
# Smarter Semantic Chunking
# -----------------------------
def chunk_text(text, chunk_size=800, overlap=150):
    """
    Paragraph-aware chunking.
    Avoids cutting sentences mid-way.
    Maintains overlap between chunks.
    """

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:

        # If adding this paragraph exceeds chunk size,
        # store current chunk and start new one with overlap
        if len(current_chunk) + len(paragraph) > chunk_size:
            chunks.append(current_chunk.strip())

            # Overlap from previous chunk
            overlap_text = current_chunk[-overlap:]
            current_chunk = overlap_text + "\n\n" + paragraph
        else:
            current_chunk += "\n\n" + paragraph

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# -----------------------------
# Process Documents
# -----------------------------
def process_documents():
    raw_docs = load_documents()
    all_chunks = []

    for doc in raw_docs:
        chunks = chunk_text(doc["content"])

        for chunk in chunks:
            all_chunks.append({
                "filename": doc["filename"],
                "content": chunk
            })

    return all_chunks


# -----------------------------
# Debug Run
# -----------------------------
if __name__ == "__main__":
    chunks = process_documents()

    print(f"Created {len(chunks)} chunks.\n")

    for i, chunk in enumerate(chunks[:5]):
        print(f"Chunk {i+1} from {chunk['filename']}:")
        print(chunk["content"])
        print("-" * 50)