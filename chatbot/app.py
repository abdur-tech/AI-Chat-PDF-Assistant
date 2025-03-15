from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import sqlite3
import fitz
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:8000"}})

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DB_PATH = "pdf_content.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_content 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, filename TEXT)''')
    conn.commit()
    conn.close()

init_db()

OPENAI_API_KEY = os.getenv('OPENAI_KEY')
openai_client = OpenAI( base_url="https://openrouter.ai/api/v1",api_key=OPENAI_API_KEY)

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        file = request.files['pdf']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        for existing_file in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, existing_file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        filename = f"{os.path.splitext(file.filename)[0]}_{int(time.time())}{os.path.splitext(file.filename)[1]}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        pdf_document = fitz.open(file_path)
        pdf_text = ""
        for page in pdf_document:
            pdf_text += page.get_text()
        pdf_document.close()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM pdf_content")
        c.execute("INSERT INTO pdf_content (content, filename) VALUES (?, ?)", (pdf_text, filename))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": f"File '{file.filename}' uploaded and processed"}), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "No question provided"}), 400
        
        question = data['question']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT content FROM pdf_content LIMIT 1")
        result = c.fetchone()
        conn.close()

        if not result:
            return jsonify({"answer": "No PDF content available. Please upload a PDF first."}), 200
        
        pdf_content = result[0]
        response = openai_client.chat.completions.create(
            model="google/gemma-3-12b-it:free",
            messages=[
                {"role": "system", "content": "You are an assistant that answers questions based on the provided content of pdf. Here is the content:\n" + pdf_content},
                {"role": "user", "content": question}
            ],
            max_tokens=500
        )

        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/pdf-status', methods=['GET'])
def pdf_status():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT filename FROM pdf_content LIMIT 1")
        result = c.fetchone()
        conn.close()

        if result:
            filename = result[0]
            return jsonify({"status": "uploaded", "filename": filename}), 200
        else:
            return jsonify({"status": "none"}), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/delete-pdf', methods=['POST'])
def delete_pdf():
    try:
        # Clear the uploads folder
        for existing_file in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, existing_file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        # Clear the database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM pdf_content")
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "PDF deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)