from concurrent.futures import ThreadPoolExecutor
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from database import execute_query
import asyncio

class Document:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}

class OrganizationSystemChat:
    def __init__(self):
        """Initialize the chat model, prompt template, and text splitter."""
        self.model = ChatOllama(model="mistral")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=100)
        self.prompt = PromptTemplate.from_template(
            """
            <s> [INST] You are an assistant for question-answering tasks. Use the following pieces of retrieved context 
            to answer the question. If you don't know the answer, just say that you don't know. Use three sentences
             maximum and keep the answer concise. [/INST] </s> 
            [INST] Question: {question} 
            Context: {context} 
            Answer: [/INST]
            """
        )
        self.vector_store = None
        self.retriever = None
        self.chain = None
        self.context = ""

    async def ingest_document(self, pdf_file_path: str):
        """Ingest documents from a PDF file."""
        try:
            print("Ingesting document...")
            docs = PyPDFLoader(file_path=pdf_file_path).load()
            chunks = self.text_splitter.split_documents(docs)
            chunks = filter_complex_metadata(chunks)
            await self._initialize_vector_store(chunks)
        except Exception as e:
            print(f"Error during document ingestion: {e}")
            return f"Error during document ingestion: {e}"

    async def ingest_database(self, tables):
        """Fetch data and metadata from selected tables and ingest it into the vector store."""
        try:
            print("Ingesting database...")
            all_chunks = []
            tasks = []

            async def fetch_table_data(table):
                # Fetch table metadata
                metadata_query = f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table}';
                """
                metadata_result = list(execute_query(metadata_query))
                if metadata_result:
                    metadata_text = f"Table: {table}\nColumns:\n"
                    metadata_text += "\n".join([f"{column[0]} ({column[1]})" for batch in metadata_result for column in batch])
                    all_chunks.append(Document(page_content=metadata_text))

                # Fetch table data in batches
                data_query = f"SELECT * FROM {table}"
                for batch in execute_query(data_query, batch_size=1000):  # Adjust batch size as needed
                    for row in batch:
                        row_text = " | ".join(str(cell) for cell in row)
                        all_chunks.append(Document(page_content=f"Table: {table}\n{row_text}"))

            async def fetch_relationships():
                relationship_query = """
                SELECT 
                    tc.table_name, kcu.column_name, 
                    ccu.ss AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu 
                      ON ccu.constraint_name = tc.constraint_name
                WHERE constraint_type = 'FOREIGN KEY';
                """
                relationship_result = list(execute_query(relationship_query))
                if relationship_result:
                    relationship_text = "Relationships among tables:\n"
                    relationship_text += "\n".join([f"{row[0]} ({row[1]}) -> {row[2]} ({row[3]})" for batch in relationship_result for row in batch])
                    all_chunks.append(Document(page_content=relationship_text))

            # Fetch table data
            for table in tables:
                tasks.append(fetch_table_data(table))
            
            # Fetch relationships
            tasks.append(fetch_relationships())

            await asyncio.gather(*tasks)

            self.context = "\n".join([doc.page_content for doc in all_chunks])
            await self._initialize_vector_store(all_chunks)
        except Exception as e:
            print(f"Error during database ingestion: {e}")
            return f"Error during database ingestion: {e}"

    async def _initialize_vector_store(self, chunks):
        """Initialize the vector store with the given chunks."""
        try:
            print("Initializing vector store...")
            self.vector_store = Chroma.from_documents(documents=chunks, embedding=FastEmbedEmbeddings())
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "k": 3,
                    "score_threshold": 0.5,
                },
            )
            self.chain = ({"context": self.retriever, "question": RunnablePassthrough()}
                          | self.prompt
                          | self.model
                          | StrOutputParser())
            print("Vector store initialized successfully.")
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            return f"Error initializing vector store: {e}"

    def ask(self, query: str):
        """Ask a question using the model."""
        if not self.chain:
            print("Chain is not initialized.")
            return "Please, add a document or connect to a database first."
        try:
            print(f"Asking question: {query}")
            # Retrieve context from the retriever
            context_docs = self.retriever.get_relevant_documents(query)
            context = " ".join([doc.page_content for doc in context_docs])
            # Include the overall context if specific context is not enough
            if not context.strip():
                context = self.context
            # Invoke the chain with the context and the question
            response = self.chain.invoke({"context": context, "question": query})
            return self._format_response(response)
        except Exception as e:
            print(f"Error during query processing: {e}")
            return f"Error during query processing: {e}"

    def generate_insights(self, tables, query):
        """Generate insights based on selected tables and user query."""
        try:
            # Example logic to analyze data and generate insights
            insights = []
            for table in tables:
                # Analyze table data
                data_query = f"SELECT * FROM {table} LIMIT 5"  # Example query to fetch sample data
                data_sample = list(execute_query(data_query))
                if data_sample:
                    insights.append(f"Sample data from {table}: {data_sample}")
            
            # Combine insights into a response
            response = " ".join(insights)
            return self._format_response(response)
        except Exception as e:
            print(f"Error generating insights: {e}")
            return f"Error generating insights: {e}"

    def _format_response(self, response):
        """Format the response to be concise and clear."""
        if isinstance(response, str):
            response_lines = response.strip().split("\n")
            if "Sample data from" in response_lines[0]:
                return "I have identified some sample data. Please specify if you need more details."
            return response_lines[0]  # Taking only the first line for brevity
        return response

    def clear(self):
        """Clear the vector store and retriever."""
        print("Clearing vector store and retriever...")
        self.vector_store = None
        self.retriever = None
        self.chain = None
        self.context = ""
        print("Cleared successfully.")
