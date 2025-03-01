import { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { createWorker } from 'tesseract.js';
import * as pdfjsLib from 'pdfjs-dist';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min?url'; // Use the worker URL
import './App.css';

// Configure PDF.js to use the worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

const Chatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [filePreview, setFilePreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessingFile, setIsProcessingFile] = useState(false);
  const [error, setError] = useState(null);

  // Handle file upload and text extraction
  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);

    setIsProcessingFile(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:8080/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (data.error) throw new Error(data.error);

      setFilePreview({ name: selectedFile.name, extractedText: data.text });
    } catch (error) {
      console.error("File upload error:", error);
      setError(error.message);
    } finally {
      setIsProcessingFile(false);
    }
  };

  // Handle sending messages
  const handleSend = async () => {
    if (!input.trim() && !filePreview?.extractedText) return;

    setIsLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: input }]);

    try {
      const response = await fetch("http://localhost:8080/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: input,
          fileContent: filePreview?.extractedText || "",
        }),
      });

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
    } catch (error) {
      console.error("Error fetching response:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "Error processing request." }]);
    } finally {
      setIsLoading(false);
      setInput("");
    }
  };

  // Clear uploaded file
  const handleClearFile = useCallback(() => {
    setFilePreview(null);
    setError(null);
  }, []);

  // Handle Enter key press
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="chatbot-container">
      <h1 className="chatbot-title">AI Legal Assistant</h1>

      {error && <div className="error-message">{error}</div>}

      <div className="chatbot-messages">
        {messages.map((msg, index) => (
          <div key={index} className={`chatbot-message ${msg.role}`}>
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        ))}

        {isLoading && (
          <div className="chatbot-message assistant">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </div>

      <div className="chatbot-input-container">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          className="chatbot-input"
          disabled={isLoading || isProcessingFile}
        />
        <button
          onClick={handleSend}
          className="chatbot-send-button"
          disabled={isLoading || isProcessingFile}
        >
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>

      <div className="file-upload-container">
        <label className="file-upload-label">
          {isProcessingFile ? 'Processing...' : 'Upload PDF/Image'}
          <input
            type="file"
            accept=".pdf,image/*"
            onChange={handleFileUpload}
            className="file-upload-input"
            disabled={isLoading || isProcessingFile}
          />
        </label>

        {filePreview && (
          <div className="file-preview-container">
            <div className="file-preview">
              <span>📄 {filePreview.name}</span>
              {filePreview.extractedText && (
                <div className="extracted-text-preview">
                  <small>Extracted text:</small>
                  <p>{filePreview.extractedText.slice(0, 150)}...</p>
                </div>
              )}
            </div>
            <button onClick={handleClearFile} className="clear-file-button">
              Clear
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Chatbot;