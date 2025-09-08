# --- START OF FILE script.py ---
import ast
import requests
from PIL import Image
import pytesseract
from langchain_community.document_loaders import WebBaseLoader
from urllib.parse import urlparse

import os
import gradio as gr
import json
import sqlite3
import numpy as np
import pypdf
import faiss
import pickle
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
# Configuration and Setup
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Agent Types Enumeration
class AgentType(Enum):
    LIFESTYLE = "🏋️ Lifestyle (Gym & Food)"
    EMOTIONAL = "💝 Emotional Support"
    PROFESSIONAL = "💼 Professional & Career"
    PLANNER = "📅 Day Planner"
    REFINER = "✍️ Refinement & Synthesis"
    # The General agent is now the refiner.

# --- Memory Management System (with Persistent RAG) ---
class SharedMemoryManager:
    """Manages persistent SQL history and persistent RAG vector stores for each user session."""
    def __init__(self, db_path: str = "chatbot_memory.db", rag_path: str = "rag_stores"):
        self.db_path = db_path
        self.rag_path = rag_path
        os.makedirs(self.rag_path, exist_ok=True)
        self.init_database()
        self.embedding_model = 'models/embedding-001'
        self.vector_stores: Dict[str, Dict[str, Any]] = {} # In-memory cache

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table with all required columns from the start
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                session_id TEXT, 
                role TEXT, 
                content TEXT, 
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # --- SCHEMA MIGRATION BLOCK (check each column individually) ---
        cursor.execute("PRAGMA table_info(conversations)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        # Only add columns that don't already exist
        if "session_id" not in existing_cols:
            cursor.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
        
        if "timestamp" not in existing_cols:
            cursor.execute("ALTER TABLE conversations ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        conn.commit()
        conn.close()

    def _get_rag_session_paths(self, session_id: str):
        safe_session_id = "".join(c for c in session_id if c.isalnum() or c in (' ', '_')).rstrip()
        index_path = os.path.join(self.rag_path, f"{safe_session_id}.index")
        chunks_path = os.path.join(self.rag_path, f"{safe_session_id}.pkl")
        return index_path, chunks_path

    def _load_rag_store(self, session_id: str):
        """Loads a user's vector store from disk into memory."""
        index_path, chunks_path = self._get_rag_session_paths(session_id)
        if os.path.exists(index_path) and os.path.exists(chunks_path):
            self.vector_stores[session_id] = {
                "index": faiss.read_index(index_path),
                "chunks": pickle.load(open(chunks_path, "rb"))
            }
            return True
        return False
        
    def _save_rag_store(self, session_id: str):
        """Saves a user's vector store from memory to disk."""
        if session_id in self.vector_stores:
            index_path, chunks_path = self._get_rag_session_paths(session_id)
            faiss.write_index(self.vector_stores[session_id]["index"], index_path)
            with open(chunks_path, 'wb') as f:
                pickle.dump(self.vector_stores[session_id]["chunks"], f)

    def add_document(self, session_id: str, file_path: str) -> str:
        """Enhanced to handle PDF, TXT, and Image files with OCR."""
        if session_id not in self.vector_stores:
            self._load_rag_store(session_id) or self.vector_stores.setdefault(session_id, {"chunks": [], "index": None})
        
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            text_chunks = []
            
            if file_ext == '.pdf':
                # Existing PDF handling
                reader = pypdf.PdfReader(file_path)
                text_chunks = [page.extract_text() for page in reader.pages if page.extract_text().strip()]
                
            elif file_ext == '.txt':
                # Handle text files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Split into chunks of ~1000 characters
                    chunk_size = 1000
                    text_chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
                    
            elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
                # Handle images with OCR
                try:
                    img = Image.open(file_path)
                    extracted_text = pytesseract.image_to_string(img)
                    if extracted_text.strip():
                        # Split OCR text into chunks
                        chunk_size = 500
                        text_chunks = [extracted_text[i:i+chunk_size] for i in range(0, len(extracted_text), chunk_size)]
                    else:
                        return f"⚠️ No text could be extracted from image: {os.path.basename(file_path)}"
                except Exception as ocr_error:
                    return f"⚠️ OCR failed for {os.path.basename(file_path)}: {str(ocr_error)}"
            else:
                return f"⚠️ Unsupported file type: {file_ext}"
            
            if not text_chunks or not any(chunk.strip() for chunk in text_chunks):
                return f"⚠️ No readable content found in {os.path.basename(file_path)}"
            
            # Filter out empty chunks
            text_chunks = [chunk for chunk in text_chunks if chunk.strip()]
            
            # Generate embeddings
            response = genai.embed_content(
                model=self.embedding_model, 
                content=text_chunks, 
                task_type="RETRIEVAL_DOCUMENT"
            )
            embeddings = np.array(response['embedding'])
            
            # Initialize or update vector store
            if self.vector_stores[session_id]["index"] is None:
                d = embeddings.shape[1]
                self.vector_stores[session_id]["index"] = faiss.IndexFlatL2(d)
            
            self.vector_stores[session_id]["index"].add(embeddings)
            self.vector_stores[session_id]["chunks"].extend(text_chunks)
            self._save_rag_store(session_id)
            
            return f"✅ Added '{os.path.basename(file_path)}' ({len(text_chunks)} chunks) to memory."
            
        except Exception as e:
            return f"⚠️ Error processing {os.path.basename(file_path)}: {str(e)}"

    def add_url_content(self, session_id: str, urls: str) -> str:
        """Web scraping tool integrated into memory system."""
        try:
            # Parse URL list from string
            url_list = ast.literal_eval(urls)
            if not isinstance(url_list, list) or not all(isinstance(url, str) for url in url_list):
                return "Invalid input format. Please provide a list of URLs as a string."
        except (ValueError, SyntaxError):
            return "Invalid input format. Please provide a list of URLs as a string."
        
        if session_id not in self.vector_stores:
            self._load_rag_store(session_id) or self.vector_stores.setdefault(session_id, {"chunks": [], "index": None})
        
        combined_content = []
        successful_urls = []
        
        for url in url_list:
            try:
                # Validate URL
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    combined_content.append(f"Invalid URL format: {url}")
                    continue
                
                # Scrape content
                loader = WebBaseLoader(
                    [url], 
                    requests_kwargs={"headers": {"User-Agent": "Multi-Agent AI Assistant"}}
                )
                documents = loader.load()
                
                for doc in documents:
                    if doc.page_content.strip():
                        # Split content into chunks
                        chunk_size = 1000
                        content = doc.page_content
                        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
                        combined_content.extend(chunks)
                        successful_urls.append(url)
                        
            except Exception as e:
                combined_content.append(f"Could not scrape {url}. Error: {str(e)}")
        
        if not combined_content:
            return "⚠️ No content could be scraped from the provided URLs."
        
        try:
            # Generate embeddings for scraped content
            valid_chunks = [chunk for chunk in combined_content if len(chunk.strip()) > 10]
            
            if valid_chunks:
                response = genai.embed_content(
                    model=self.embedding_model,
                    content=valid_chunks,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                embeddings = np.array(response['embedding'])
                
                # Add to vector store
                if self.vector_stores[session_id]["index"] is None:
                    d = embeddings.shape[1]
                    self.vector_stores[session_id]["index"] = faiss.IndexFlatL2(d)
                
                self.vector_stores[session_id]["index"].add(embeddings)
                self.vector_stores[session_id]["chunks"].extend(valid_chunks)
                self._save_rag_store(session_id)
                
                return f"✅ Scraped and added content from {len(successful_urls)} URLs ({len(valid_chunks)} chunks) to memory."
            else:
                return "⚠️ No valid content chunks found from scraped URLs."
                
        except Exception as e:
            return f"⚠️ Error processing scraped content: {str(e)}"


    def search_documents(self, session_id: str, query: str, k: int = 3) -> List[str]:
        """Searches the user's RAG store for relevant info."""
        if session_id not in self.vector_stores:
            if not self._load_rag_store(session_id): return []
        if self.vector_stores[session_id]["index"] is None: return []

        query_embedding = np.array(genai.embed_content(model=self.embedding_model, content=query, task_type="RETRIEVAL_QUERY")['embedding']).reshape(1, -1)
        index = self.vector_stores[session_id]["index"]
        distances, indices = index.search(query_embedding, k)
        return [self.vector_stores[session_id]["chunks"][i] for i in indices[0]]
        
    def save_conversation(self, session_id: str, role: str, content: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)', (session_id, role, content))
        conn.commit()
        conn.close()
    
    def load_conversation_history(self, session_id: str) -> List[List[str]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
        rows = cursor.fetchall()
        conn.close()
        # Reconstruct Gradio chat history format [[user_msg, bot_msg], ...]
        history = []
        for i in range(0, len(rows), 2):
            if i + 1 < len(rows) and rows[i][0] == 'user' and rows[i+1][0] == 'assistant':
                history.append([rows[i][1], rows[i+1][1]])
        return history

# --- Agent Definitions ---
@dataclass
class AgentConfig: name: str; system_prompt: str

class BaseAgent:
    def __init__(self, config: AgentConfig, memory_manager: SharedMemoryManager):
        self.config = config; self.memory_manager = memory_manager
        self.model = genai.GenerativeModel(model_name='gemini-2.5-flash')

    def run(self, prompt: str, session_id: str, history: List[Dict]):
        rag_context = self.memory_manager.search_documents(session_id, prompt)
        rag_prompt = "\n\n--- CONTEXT FROM UPLOADED DOCUMENTS (Use this to answer the user's query if relevant) ---\n" + "\n".join(rag_context) if rag_context else ""
        
        full_prompt = self.config.system_prompt + rag_prompt + "\n\n--- TASK ---\n" + prompt
        
        # We don't use long history for specialist agents to keep their focus sharp
        contents = [{'role': 'user', 'parts': [full_prompt]}]
        
        response = self.model.generate_content(contents)
        return response.text

# --- Specialist and Router Agents ---
class LifestyleAgent(BaseAgent):
    def __init__(self, mm): super().__init__(AgentConfig(name=AgentType.LIFESTYLE.value, system_prompt="You are a Lifestyle Coach specializing in fitness and nutrition."), mm)

class EmotionalSupportAgent(BaseAgent):
    def __init__(self, mm): super().__init__(AgentConfig(name=AgentType.EMOTIONAL.value, system_prompt="You are an empathetic Emotional Support Assistant. Provide compassionate listening and guidance."), mm)

class ProfessionalAgent(BaseAgent):
    def __init__(self, mm): super().__init__(AgentConfig(name=AgentType.PROFESSIONAL.value, system_prompt="You are a Professional and Career Advisor. Help with resumes, coding problems, and career growth."), mm)

class PlannerAgent(BaseAgent):
    def __init__(self, mm): super().__init__(AgentConfig(name=AgentType.PLANNER.value, system_prompt="You are a Productivity and Planning Assistant. Help organize schedules and manage tasks."), mm)

class RefinerAgent(BaseAgent):
    def __init__(self, mm):
        prompt = "You are a Refinement expert. Your task is to take a user's original query and the results from a chain of specialist agents and synthesize them into a single, comprehensive, and well-written final answer. Respond only with the final answer."
        super().__init__(AgentConfig(name=AgentType.REFINER.value, system_prompt=prompt), mm)

class MasterRouterAgent:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.system_prompt = f"""You are a master request router for a multi-agent AI system. Your job is to analyze the user's request and create a step-by-step execution plan by choosing from a list of available specialist agents.
        
        Available Agents:
        - LIFESTYLE: For questions about fitness, exercise, diet, and meal planning.
        - EMOTIONAL: For handling stress, anxiety, feelings, and providing mental wellness guidance.
        - PROFESSIONAL: For career advice, resume help, interview prep, and technical/coding questions.
        - PLANNER: For creating schedules, managing tasks, setting goals, and time management.

        Based on the user's request, you must formulate a plan.
        - For simple requests, a single agent is enough.
        - For complex requests, you MUST create a chain of agents. For example, 'Help me create a workout routine that fits my busy work schedule' requires PLANNER then LIFESTYLE.
        
        Respond ONLY with a JSON object in the following format:
        {{"plan": [
            {{"step": 1, "agent": "AGENT_NAME", "task": "A specific, precise instruction for this agent."}},
            {{"step": 2, "agent": "AGENT_NAME", "task": "A specific, precise instruction for this agent, possibly using output from step 1."}}
        ]}}
        """

    def create_plan(self, user_query: str) -> List[Dict]:
        prompt = self.system_prompt + f"\n\nUser Request: \"{user_query}\""
        try:
            response = self.model.generate_content(prompt)
            # Clean and parse the JSON response
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            plan_json = json.loads(cleaned_response)
            return plan_json.get("plan", [])
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            print(f"Error creating plan: {e}. Falling back to a simple plan.")
            return [{"step": 1, "agent": "LIFESTYLE", "task": user_query}] # Fallback to a default agent

# --- Main Orchestrator ---
class AgentOrchestrator:
    def __init__(self):
        self.memory = SharedMemoryManager()
        self.agents = {
            "LIFESTYLE": LifestyleAgent(self.memory),
            "EMOTIONAL": EmotionalSupportAgent(self.memory),
            "PROFESSIONAL": ProfessionalAgent(self.memory),
            "PLANNER": PlannerAgent(self.memory),
            "REFINER": RefinerAgent(self.memory)
        }
        self.router = MasterRouterAgent()
    
    def process_message(self, message: str, history: List, session_id: str):
        """Orchestrates the entire process from planning to execution and refinement."""
        # 1. Create a plan
        yield "🤔 Analyzing your request and creating a plan...", history
        plan = self.router.create_plan(message)
        if not plan:
            yield "Sorry, I couldn't devise a plan for that request. Please try rephrasing.", history
            return

        thought_process = "📝 **Execution Plan:**\n" + "\n".join([f"**Step {p['step']}:** Use **{p['agent']}** to `{p['task']}`" for p in plan])
        yield thought_process, history
        
        # 2. Execute the plan
        intermediate_outputs = []
        current_prompt = message
        for step in plan:
            agent_name = step.get("agent")
            task = step.get("task")
            if agent_name not in self.agents: continue

            agent = self.agents[agent_name]
            thought_process += f"\n\n⚙️ **Executing Step {step['step']}:** Handing off to `{agent_name}`..."
            yield thought_process, history

            # Create prompt for this step, potentially including previous outputs
            step_prompt = f"Original User Request: '{message}'\n\nCurrent Task: '{task}'\n\nPrior Steps' Output (if any):\n{''.join(intermediate_outputs)}"
            
            output = agent.run(step_prompt, session_id, history)
            intermediate_outputs.append(f"\n--- Output from {agent_name} ---\n{output}\n")
            thought_process += f" ✅ Done."
            yield thought_process, history

        # 3. Refine the final answer
        thought_process += "\n\n✍️ **Synthesizing final answer...**"
        yield thought_process, history
        
        refiner_prompt = f"Original Request: '{message}'\n\n--- Collected outputs from specialist agents ---\n{''.join(intermediate_outputs)}"
        final_answer = self.agents["REFINER"].run(refiner_prompt, session_id, history)

        self.memory.save_conversation(session_id, 'user', message)
        self.memory.save_conversation(session_id, 'assistant', final_answer)
        
        history.append([message, final_answer])
        yield thought_process + " ✅ Complete!", history
    
    def load_history(self, session_id):
        return self.memory.load_conversation_history(session_id)

# --- Gradio Interface ---
def create_chatbot_interface():
    orchestrator = AgentOrchestrator()
    
    with gr.Blocks(theme=gr.themes.Soft(), css="""
        .gradio-container { 
            max-width: 95% !important; 
            margin: auto; 
            min-height: 100vh;
        }
        .thought-process { 
            padding: 15px; 
            background-color: #f8f9fa; 
            border-radius: 10px; 
            font-size: 0.9em; 
            border-left: 4px solid #007bff;
            margin: 10px 0;
        }
        .main-chat-area {
            min-height: 700px;
        }
        .sidebar-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 20px;
            color: white;
            min-height: 600px;
        }
        .url-input {
            background-color: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .chat-interface {
            border-radius: 15px;
            background: white;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            min-height: 700px;
        }
        /* Initial chatbot sizing */
        .gradio-chatbot {
            min-height: 700px !important;
            width: 100% !important;
        }
        /* Message input styling */
        .message-input {
            border-radius: 10px;
            border: 2px solid #e9ecef;
        }
        .send-button {
            border-radius: 10px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            border: none;
            color: white;
            font-weight: bold;
        }
    """) as demo:
        
        gr.Markdown("""
        # 🤖 Autonomous Multi-Agent AI Assistant
        ### I analyze your request and automatically choose the best expert agents to help you.
        """)
        
        with gr.Row():
            # Enhanced sidebar
            with gr.Column(scale=1, min_width=400, elem_classes="sidebar-section"):
                gr.Markdown("### 🎯 Session Control")
                
                session_id_input = gr.Textbox(
                    label="Session Name", 
                    value="default-session", 
                    info="Enter a name to save and load your conversation."
                )
                
                gr.Markdown("### 📚 Document Memory (RAG)")
                
                # Enhanced file upload with multiple formats
                file_upload_btn = gr.UploadButton(
                    "📁 Upload File", 
                    file_types=[".pdf", ".txt", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"],
                    variant="secondary"
                )
                
                # Web scraping section
                gr.Markdown("### 🌐 Web Scraping")
                url_input = gr.Textbox(
                    label="URLs to Scrape",
                    placeholder="['https://example.com', 'https://another-site.com']",
                    info="Enter URLs as a Python list format",
                    lines=2,
                    elem_classes="url-input"
                )
                scrape_btn = gr.Button("🔍 Scrape URLs", variant="secondary")
                
                file_status_display = gr.Markdown("No files or URLs loaded for this session.")
                
                gr.Markdown("---")
                gr.Markdown("### 🧠 Agent Thinking Process")
                thought_process_display = gr.Markdown(
                    "_Your agent's thought process will appear here..._", 
                    elem_classes="thought-process"
                )

            
           # Main chat area
            with gr.Column(scale=3, min_width=800):
                chatbot = gr.Chatbot(
                    height=700,
                    min_width=800,
                    label="💬 Conversation",
                    avatar_images=("👤", "🤖")
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Ask me anything! I can now work with PDFs, text files, images (OCR), and scraped web content.", 
                        label="Your Message", 
                        lines=3,
                        scale=4
                    )
                    send_btn = gr.Button("Send Request 🚀", variant="primary", scale=1)
                
                # Enhanced examples
                gr.Markdown("""
                ### 💡 Example Queries:
                - *"Analyze the document I uploaded and create a summary"*
                - *"Based on the scraped website content, what are the key insights?"*
                - *"Extract text from the image I uploaded and explain it"*
                - *"Help me create a plan based on all the uploaded documents"*
                """)
        
        # Event handlers
        def handle_message_and_update_ui(message, history, session_id):
            if not message.strip():
                return
            for thought_process, updated_history in orchestrator.process_message(message, history, session_id):
                yield updated_history, thought_process, ""

        def handle_file_upload(file, session_id):
            if file is None: 
                return "No file selected."
            status = orchestrator.memory.add_document(session_id, file.name)
            orchestrator.memory._load_rag_store(session_id)
            return status

        def handle_url_scraping(urls, session_id):
            if not urls.strip():
                return "Please enter URLs to scrape."
            status = orchestrator.memory.add_url_content(session_id, urls)
            orchestrator.memory._load_rag_store(session_id)
            return status

        def handle_session_load(session_id):
            history = orchestrator.load_history(session_id)
            is_rag_loaded = orchestrator.memory._load_rag_store(session_id)
            rag_status = f"✅ Loaded memory for '{session_id}'." if is_rag_loaded else "No documents found for this session."
            return history, rag_status

        # Wire up events
        send_btn.click(handle_message_and_update_ui, inputs=[msg_input, chatbot, session_id_input], outputs=[chatbot, thought_process_display, msg_input])
        msg_input.submit(handle_message_and_update_ui, inputs=[msg_input, chatbot, session_id_input], outputs=[chatbot, thought_process_display, msg_input])
        file_upload_btn.upload(handle_file_upload, inputs=[file_upload_btn, session_id_input], outputs=[file_status_display])
        scrape_btn.click(handle_url_scraping, inputs=[url_input, session_id_input], outputs=[file_status_display])
        session_id_input.submit(handle_session_load, inputs=[session_id_input], outputs=[chatbot, file_status_display])

        return demo


if __name__ == "__main__":
    if not API_KEY:
        print("FATAL: GEMINI_API_KEY environment variable not set.")
        exit(1)
    
    app = create_chatbot_interface()
    app.launch(share=True)