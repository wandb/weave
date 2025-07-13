import os
import sys
import numpy as np
import pickle
import weave
from weave import Model
from openai import OpenAI
import yaml
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ────────────────────────────────────────────────
# STEP 1: Load real docs from the Weave repo
# ────────────────────────────────────────────────

DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs"))
INDEX_FILE = os.path.join(os.path.dirname(__file__), "weave_rag_index.pkl")

with open(os.path.join(os.path.dirname(__file__), "llms.yaml"), "r") as f:
    META = yaml.safe_load(f)

def load_articles():
    articles = []
    for root, _, files in os.walk(DOCS_DIR):
        for fname in files:
            if fname.endswith((".md", ".mdx")):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, DOCS_DIR)
                with open(full_path, encoding="utf-8") as f:
                    articles.append({
                        "text": f.read(),
                        "source": rel_path  # preserve subfolder structure
                    })
    return articles



def docs_to_embeddings(articles: list) -> list:
    openai = OpenAI()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

    chunks_with_source = []
    for article in articles:
        chunks = splitter.split_text(article["text"])
        for chunk in chunks:
            chunks_with_source.append({"text": chunk, "source": article["source"]})

    document_embeddings = []
    for chunk in chunks_with_source:
        response = (
            openai.embeddings.create(input=chunk["text"], model="text-embedding-3-small")
            .data[0]
            .embedding
        )
        document_embeddings.append((chunk, response))

    return document_embeddings


# Load or build embedding index
if os.path.exists(INDEX_FILE):
    print("Existing docs embeddings found. Loading now...")
    with open(INDEX_FILE, "rb") as f:
        article_chunks, article_embeddings = pickle.load(f)
else:
    print("No docs embeddings found. Creating now...")
    articles = load_articles()
    article_chunks, article_embeddings = zip(*docs_to_embeddings(articles))
    article_chunks = list(article_chunks)
    article_embeddings = list(article_embeddings)
    with open(INDEX_FILE, "wb") as f:
        pickle.dump((article_chunks, article_embeddings), f)

# ────────────────────────────────────────────────
# STEP 2: Retrieval step (traced)
# ────────────────────────────────────────────────

def get_source_bias(query: str, source: str) -> float:
    for topic, meta in META.items():
        if any(word in query.lower() for word in meta["query_keywords"]):
            if source in meta["preferred_files"]:
                return 1.2
    return 1.0

@weave.op()
def get_most_relevant_document(query: str) -> dict:
    openai = OpenAI()
    query_embedding = (
        openai.embeddings.create(input=query, model="text-embedding-3-small")
        .data[0]
        .embedding
    )
    scores = []
    for i, doc_emb in enumerate(article_embeddings):
        sim = np.dot(query_embedding, doc_emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb))
        boost = get_source_bias(query, article_chunks[i]["source"])
        scores.append(sim * boost)

    top_k = sorted(enumerate(scores), key=lambda x: -x[1])[:5]
    print("\nTop 5 retrieved chunks:")
    for idx, score in top_k:
        print(f"[{score:.4f}] {article_chunks[idx]['source']}")

    idx = int(np.argmax(scores))
    return article_chunks[idx]

# ────────────────────────────────────────────────
# STEP 3: RAG model (traced)
# ────────────────────────────────────────────────

class RAGModel(Model):
    system_message: str
    model_name: str = "gpt-3.5-turbo"

    @weave.op()
    def predict(self, question: str) -> dict:
        client = OpenAI()
        context = get_most_relevant_document(question)
        query = f"""Use the following information from `{context['source']}` to answer the question. If the answer cannot be found, say \"I don't know.\"

Context:
\"\"\"
{context['text']}
\"\"\"

Question: {question}
"""
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": query},
            ],
            temperature=0.2,
            response_format={"type": "text"},
        )
        return {
            "answer": response.choices[0].message.content,
            "context": context["text"],
            "source": context["source"]
        }

# ────────────────────────────────────────────────
# STEP 4: CLI runner
# ────────────────────────────────────────────────

if __name__ == "__main__":
    weave.init("weave-rag-mvp")

    model = RAGModel(
        system_message="You are a Weave documentation assistant. Answer clearly using only the given context. If the context does not provide you with the answer, say so. Do not make up answers."
    )

    if len(sys.argv) < 2:
        print("Please provide a question as a command-line argument.")
        print("Example: python weave_rag.py \"What is a weave panel?\"")
        sys.exit(1)

    question = sys.argv[1]
    output = model.predict(question)

    print("\nQuestion:\n", question)
    print("\nAnswer:\n", output["answer"])
    print("\nSource:", output["source"])
