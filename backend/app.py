from flask import Flask, request, jsonify
from flask_cors import CORS
import groq
import chromadb
import tiktoken
import pypdf
from sentence_transformers import SentenceTransformer
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize ChromaDB
try:
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="legal_docs")
    logger.info("ChromaDB initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing ChromaDB: {e}")

# Load Sentence Transformer Model
try:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("Sentence Transformer model loaded successfully.")
except Exception as e:
    logger.error(f"Error loading Sentence Transformer model: {e}")

# Initialize Groq client
GROQ_API_KEY = "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"
try:
    groq_client = groq.Client(api_key=GROQ_API_KEY)
    logger.info("Groq client initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Groq client: {e}")

# Token Counter Function
def count_tokens(text):
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        return 0

# Extract Text from PDF
def extract_text_from_pdf(file):
    try:
        pdf_reader = pypdf.PdfReader(file)
        text = " ".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
        logger.info("Text extracted from PDF successfully.")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return None

# Split Text into Chunks
def chunk_text(text, chunk_size=500):
    try:
        words = text.split()
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        logger.info(f"Text split into {len(chunks)} chunks.")
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        return []


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        logger.error("No file uploaded.")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.error("No selected file.")
        return jsonify({"error": "No selected file"}), 400

    try:
        # Extract text from the uploaded file
        text = extract_text_from_pdf(file)
        if not text:
            return jsonify({"error": "Failed to extract text from the file."}), 400

        # Check token count
        token_count = count_tokens(text)
        if token_count > 8000:
            logger.error("File too large.")
            return jsonify({"error": "File too large. Please upload a smaller document."}), 400

        # Split text into chunks
        chunks = chunk_text(text)
        if not chunks:
            return jsonify({"error": "Failed to chunk text."}), 400

        # Store chunks in ChromaDB
        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk).tolist()  # Create embedding
            collection.add(
                ids=[f"{file.filename}_{i}"],
                embeddings=[embedding],
                metadatas=[{"text": chunk, "source": file.filename}]
            )
        logger.info("File processed and stored in ChromaDB successfully.")

        return jsonify({"text": text}), 200

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


@app.route("/query", methods=["POST"])
def query():
    data = request.json
    user_question = data.get("question", "")
    file_content = data.get("fileContent", "")

    if not user_question and not file_content:
        logger.error("No question or file content provided.")
        return jsonify({"error": "Question or file content is required"}), 400

    try:
        # Retrieve relevant chunks from ChromaDB
        results = collection.query(query_texts=[user_question], n_results=3)
        retrieved_texts = [doc["text"] for doc in results["metadatas"][0]]
        logger.info(f"Retrieved {len(retrieved_texts)} relevant chunks from ChromaDB.")

        # Combine user question, file content, and retrieved texts
        prompt = f"User Question: {user_question}\n\nFile Content: {file_content}\n\nRelevant Legal Documents:\n{retrieved_texts}\n\nAnswer:"
        logger.debug(f"Prompt: {prompt}")

        # Send query to Groq API
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": "You are a legal expert."},
                      {"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        logger.info("Response generated successfully.")

        return jsonify({"answer": answer}), 200

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return jsonify({"error": f"Error generating response: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(port=8080, debug=True)