import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from ingest import process_documents


# -----------------------------
# Load environment variables
# -----------------------------
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# -----------------------------
# Initialize OpenAI client
# -----------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# Initialize Persistent Chroma
# -----------------------------
chroma_client = chromadb.PersistentClient(path="chroma_db")

embedding_function = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

collection = chroma_client.get_or_create_collection(
    name="support_docs",
    embedding_function=embedding_function
)


# -----------------------------
# Ingest Documents (Only Once)
# -----------------------------
def ingest_into_vector_db():
    existing_count = collection.count()

    if existing_count > 0:
        print("Vector database already populated.")
        return

    chunks = process_documents()

    documents = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk["content"])
        metadatas.append({"filename": chunk["filename"]})
        ids.append(f"doc_{i}")

    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    print(f"Inserted {len(documents)} chunks into vector database.")


# -----------------------------
# Retrieval Function (with scoring)
# -----------------------------
def retrieve_context(query, top_k=3):
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print("\nTop Retrieved Chunks:\n")

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        confidence = 1 - dist
        print(f"Result {i+1} (from {meta['filename']})")
        print(f"Distance: {dist:.4f} | Confidence: {confidence:.4f}")
        print(doc)
        print("-" * 50)

    return documents, distances


# -----------------------------
# Generation Function
# -----------------------------
def generate_answer(query, retrieved_chunks):
    context = "\n\n".join(retrieved_chunks)

    prompt = f"""
You are a customer support assistant for Kolet SaaS Platform.

Answer the user's question using ONLY the context provided below.
If the answer is not in the context, say you do not have enough information.

Context:
{context}

User Question:
{query}

Answer:
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful support assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    ingest_into_vector_db()

    CONFIDENCE_THRESHOLD = 0.5

    while True:
        user_query = input("\nAsk a question (or type 'exit'): ")

        if user_query.lower() == "exit":
            break

        retrieved, distances = retrieve_context(user_query)

        best_distance = distances[0]
        confidence = 1 - best_distance

        if confidence < CONFIDENCE_THRESHOLD:
            print("\nFinal Answer:\n")
            print("I'm not confident enough to answer this based on available documentation.")
            print("=" * 60)
            continue

        answer = generate_answer(user_query, retrieved)

        print("\nFinal Answer:\n")
        print(answer)
        print("=" * 60)