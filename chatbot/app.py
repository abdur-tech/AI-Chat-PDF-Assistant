from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import sqlite3
import fitz
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:8000"}})

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DB_PATH = "pdf_content.db"

# ---------- Load Embedding Model ----------
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ---------- GLOBAL FAISS INDEX ----------
faiss_index = None
stored_chunks = []  # Will store chunks in RAM for retrieval


# ---------- Initialize Database ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk TEXT,
            embedding BLOB,
            filename TEXT
        )
    """)
    conn.commit()
    conn.close()
def rebuild_faiss():
    global faiss_index, stored_chunks

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chunk, embedding FROM pdf_chunks")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("No chunks in DB, FAISS not rebuilt.")
        faiss_index = None
        stored_chunks = []
        return

    print("Rebuilding FAISS index from database...")

    embedding_dim = 384
    faiss_index = faiss.IndexFlatL2(embedding_dim)

    stored_chunks = []

    for chunk, emb_blob in rows:
        emb = np.frombuffer(emb_blob, dtype=np.float32)
        faiss_index.add(np.array([emb]))
        stored_chunks.append(chunk)

    print("FAISS index rebuilt. Total vectors:", faiss_index.ntotal)

init_db()
rebuild_faiss()
# ---------- Load OpenAI ----------
OPENAI_API_KEY = os.getenv('OPENAI_KEY')
openai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENAI_API_KEY)

# ---------- Helper: Chunk Text ----------
def chunk_text(text, max_length=500):
    words = text.split()
    chunks = []
    current = []

    for word in words:
        current.append(word)
        if len(current) >= max_length:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))
    
    return chunks

# ---------- Helper: Convert to float32 numpy ----------
def to_float32(vec):
    return np.array(vec).astype("float32")


# ---------- UPLOAD ROUTE ----------
@app.route('/upload', methods=['POST'])
def upload():
    global faiss_index, stored_chunks
    stored_chunks = []

    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400
    
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Delete old uploads
    for f in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, f))

    filename = f"{int(time.time())}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Extract PDF text
    pdf = fitz.open(file_path)
    text = ""
    for page in pdf:
        text += page.get_text()
    pdf.close()

    # Chunk the text
    chunks = chunk_text(text,30)

    # Delete old DB content
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pdf_chunks")
    conn.commit()

    # Prepare FAISS index
    embedding_dim = 384
    faiss_index = faiss.IndexFlatL2(embedding_dim)

    # Insert chunks + embeddings into DB + FAISS
    for chunk in chunks:
        emb = embedder.encode(chunk)
        emb_32 = to_float32(emb)

        # Store in DB
        c.execute("INSERT INTO pdf_chunks (chunk, embedding, filename) VALUES (?, ?, ?)",
                  (chunk, emb_32.tobytes(), filename))

        # Add to FAISS
        faiss_index.add(np.array([emb_32]))
        stored_chunks.append(chunk)

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "PDF processed successfully"}), 200


# ---------- CHAT ROUTE ----------
@app.route('/chat', methods=['POST'])
def chat():
    global faiss_index, stored_chunks

    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "No question provided"}), 400

    question = data["question"]

    # Embed question
    q_emb = embedder.encode(question)
    q_emb = to_float32(q_emb).reshape(1, -1)

    # FAISS Search (top 3 chunks)
    D, I = faiss_index.search(q_emb, 3)
    print("Store Chunks =",stored_chunks)
    # Get matching chunks
    context = "\n\n".join([stored_chunks[i] for i in I[0]])
    print("***********")
    print(context)
    # Call LLM with only relevant chunks
    response = openai_client.chat.completions.create(
        model="openrouter/sherlock-dash-alpha",
        messages=[
            {"role": "system", "content": "Answer using the provided PDF content only."},
            {"role": "system", "content": context},
            {"role": "user", "content": question}
        ],
        max_tokens=300
    )

    answer = response.choices[0].message.content.strip()
    return jsonify({"answer": answer})

# ---------- CHECK STATUS ----------
@app.route('/pdf-status', methods=['GET'])
def pdf_status():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM pdf_chunks LIMIT 1")
    r = c.fetchone()
    conn.close()

    if r:
        return jsonify({"status": "uploaded", "filename": r[0]})
    return jsonify({"status": "none"})


# ---------- DELETE PDF ----------
@app.route('/delete-pdf', methods=['POST'])
def delete_pdf():
    global faiss_index, stored_chunks
    stored_chunks = []
    faiss_index = None

    # Clear uploads
    for f in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, f))

    # Clear DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pdf_chunks")
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "PDF deleted"}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)
