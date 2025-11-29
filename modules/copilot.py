import streamlit as st
import os
import tempfile
from datetime import datetime

try:
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
except ImportError as e:
    st.error(f"Required libraries not installed: {e}")
    st.stop()

# Initialize session state for vector store
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def render_copilot():
    """Render the Legislative Co-Pilot interface"""
    
    st.markdown("## 🤖 Legislative Co-Pilot")
    st.markdown("**The Reading Engine** - Upload draft bills or regulations for analysis")
    st.markdown("---")
    
    # PDF Upload Section
    st.subheader("📄 Upload Legislative Document")
    uploaded_file = st.file_uploader(
        "Upload PDF (Draft Bills/Regulations)",
        type=['pdf'],
        help="Upload a PDF file containing the legislative document you want to analyze"
    )
    
    if uploaded_file is not None:
        # Process the PDF
        with st.spinner("Processing document... This may take a moment."):
            try:
                # Save uploaded file to temporary location
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_path = tmp_file.name
                
                # Load PDF
                loader = PyPDFLoader(tmp_path)
                documents = loader.load()
                
                # Chunk text
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=100,
                    length_function=len
                )
                chunks = text_splitter.split_documents(documents)
                
                # Create embeddings (CPU-only)
                embeddings = HuggingFaceEmbeddings(
                    model_name="all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )
                
                # Create vector store
                st.session_state.vectorstore = Chroma.from_documents(
                    documents=chunks,
                    embedding=embeddings,
                    collection_name="legislative_docs"
                )
                
                # Clean up temp file
                os.unlink(tmp_path)
                
                st.success(f"✅ Document processed successfully! Created {len(chunks)} text chunks.")
                st.info(f"📊 Document: {uploaded_file.name} | Pages: {len(documents)} | Chunks: {len(chunks)}")
                
            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.error("File format not supported or corrupted.")
                return
    
    # Chat Interface
    st.markdown("---")
    st.subheader("💬 Query the Document")
    
    if st.session_state.vectorstore is None:
        st.info("👆 Please upload a PDF document first to start querying.")
    else:
        # Display chat history
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat['query'])
            with st.chat_message("assistant"):
                st.write(chat['response'])
                if 'chunks' in chat:
                    with st.expander("📚 Reference Evidence"):
                        for i, chunk in enumerate(chat['chunks'], 1):
                            st.markdown(f"**Chunk {i}:**")
                            st.text(chunk)
                            st.markdown("---")
        
        # Chat input
        user_query = st.chat_input("Ask a question about the uploaded document...")
        
        if user_query:
            # Display user message
            with st.chat_message("user"):
                st.write(user_query)
            
            # Process query
            with st.chat_message("assistant"):
                with st.spinner("Searching document..."):
                    try:
                        # Retrieve relevant chunks
                        results = st.session_state.vectorstore.similarity_search(
                            user_query,
                            k=3
                        )
                        
                        # Extract text from results
                        relevant_chunks = [doc.page_content for doc in results]
                        
                        # Display reference evidence
                        with st.expander("📚 Reference Evidence", expanded=True):
                            for i, chunk in enumerate(relevant_chunks, 1):
                                st.markdown(f"**Chunk {i}:**")
                                st.text(chunk)
                                st.markdown("---")
                        
                        # Mock summary (as per requirements)
                        st.warning("🔄 AI Summarization Pending (API Key Integration Required in Phase 2)")
                        st.info("**Mock Response:** The relevant sections have been retrieved above. In Phase 2, an AI model will provide a comprehensive summary and answer to your query.")
                        
                        response = "📋 Retrieved relevant sections from the document. AI summarization will be available in Phase 2."
                        
                        # Save to chat history
                        st.session_state.chat_history.append({
                            'query': user_query,
                            'response': response,
                            'chunks': relevant_chunks,
                            'timestamp': datetime.now().strftime("%H:%M:%S")
                        })
                        
                    except Exception as e:
                        st.error(f"❌ Error querying document: {str(e)}")
                        response = "An error occurred while processing your query."
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()
