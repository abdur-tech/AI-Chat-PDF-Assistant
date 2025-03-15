document.addEventListener("DOMContentLoaded", function() {
    const uploadBtn = document.getElementById("upload-btn");
    const chatBtn = document.getElementById("chat-btn");
    const deleteBtn = document.getElementById("delete-btn");
    const userInput = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const pdfUpload = document.getElementById("pdfUpload");
    const uploadStatus = document.getElementById("uploadStatus");

    console.log("DOM fully loaded, script initialized");
    console.log("deleteBtn:", deleteBtn); // Confirm button is found

    // Initially hide delete button
    deleteBtn.style.display = "none";
    console.log("Initial deleteBtn display:", deleteBtn.style.display);
    checkPdfStatus();

    uploadBtn.addEventListener("click", async function() {
        console.log("Upload button clicked");
        const file = pdfUpload.files[0];
        if (!file) {
            uploadStatus.textContent = "❌ Please select a PDF file.";
            return;
        }

        const formData = new FormData();
        formData.append("pdf", file);

        uploadStatus.textContent = "⏳ Uploading...";
        console.log("Initiating fetch to upload API");

        try {
            const response = await fetch("http://127.0.0.1:5000/upload", {
                method: "POST",
                body: formData,
            });

            console.log("Upload response status:", response.status);
            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const data = await response.json();
            console.log("Upload response data:", data);
            uploadStatus.textContent = "✅ " + (data.message || "PDF uploaded successfully!");
            uploadStatus.classList.add("success");
            pdfUpload.value = "";

        } catch (error) {
            console.error("Upload error:", error);
            uploadStatus.textContent = `❌ Error: ${error.message}`;
            uploadStatus.classList.remove("success");
        } finally {
            console.log("Upload fetch completed");
            setTimeout(() => {
                uploadStatus.textContent = "";
                uploadStatus.classList.remove("success");
                checkPdfStatus();
            }, 3000);
        }
    });

    deleteBtn.addEventListener("click", async function() {
        console.log("Delete button clicked");
        uploadStatus.textContent = "⏳ Deleting...";

        try {
            const response = await fetch("http://127.0.0.1:5000/delete-pdf", {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const data = await response.json();
            console.log("Delete response:", data);
            uploadStatus.textContent = "✅ " + (data.message || "PDF deleted successfully!");
            uploadStatus.classList.add("success");
        } catch (error) {
            console.error("Delete error:", error);
            uploadStatus.textContent = `❌ Error: ${error.message}`;
            uploadStatus.classList.remove("success");
        } finally {
            setTimeout(() => {
                uploadStatus.textContent = "";
                uploadStatus.classList.remove("success");
                checkPdfStatus();
            }, 3000);
        }
    });

    chatBtn.addEventListener("click", sendMessage);

    userInput.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            console.log("Enter key pressed for chat");
            sendMessage();
        }
    });

    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        console.log("Sending chat message:", message);
        addMessage(message, "user-message");
        userInput.value = "";

        try {
            const response = await fetch("http://127.0.0.1:5000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: message }),
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const data = await response.json();
            console.log("Chat response:", data);
            addMessage(data.answer || "No response from AI.", "bot-message");
        } catch (error) {
            console.error("Chat error:", error);
            addMessage(`❌ Error: ${error.message}`, "bot-message");
        }
    }

    function addMessage(text, className) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", className);
        const textSpan = document.createElement("span");
        textSpan.textContent = text;

        const timestampSpan = document.createElement("span");
        timestampSpan.classList.add("message-timestamp");
        timestampSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        messageDiv.appendChild(textSpan);
        messageDiv.appendChild(timestampSpan);
        chatBox.appendChild(messageDiv);

        setTimeout(() => {
            const chatContainer = chatBox.parentElement;
            chatContainer.scrollTop = chatContainer.scrollHeight;
            console.log("Scrolled to bottom, scrollHeight:", chatContainer.scrollHeight);
        }, 0);
    }

    async function checkPdfStatus() {
        console.log("Checking PDF status...");
        try {
            const response = await fetch("http://127.0.0.1:5000/pdf-status", {
                method: "GET",
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const data = await response.json();
            console.log("PDF status response:", data);

            if (data.status === "uploaded") {
                uploadStatus.textContent = `✅ PDF '${data.filename}' is uploaded`;
                uploadStatus.classList.add("success");
                deleteBtn.style.display = "inline-block";
                console.log("Set deleteBtn display to inline-block");
            } else {
                uploadStatus.textContent = "";
                deleteBtn.style.display = "none";
                console.log("Set deleteBtn display to none (no PDF)");
            }
            console.log("Current deleteBtn display:", deleteBtn.style.display);
        } catch (error) {
            console.error("PDF status check error:", error);
            uploadStatus.textContent = `❌ Error checking PDF status: ${error.message}`;
            uploadStatus.classList.remove("success");
            deleteBtn.style.display = "none";
            console.log("Set deleteBtn display to none (error case)");
        }
    }
});