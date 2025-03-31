from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from weave_rag import RAGModel, get_most_relevant_document
import weave

app = FastAPI()

# Allow local dev clients (like Docusaurus) to access this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust to restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

weave.init("weave-rag-mvp")

model = RAGModel(
    system_message="You are a Weave documentation assistant. Answer clearly using only the given context. If the context does not provide you with the answer, say so. Do not make up answers."
)

class QuestionRequest(BaseModel):
    question: str

@app.post("/predict")
async def predict(request: QuestionRequest):
    import io
    import traceback
    from contextlib import redirect_stdout

    try:
        f = io.StringIO()
        with redirect_stdout(f):
            result = model.predict(request.question)
        debug_output = f.getvalue()

        # Parse top-5 chunks from debug output
        retrieved = []
        for line in debug_output.splitlines():
            if line.startswith("[") and "]" in line:
                score_str, filename = line.split("]")
                score = float(score_str.strip("["))
                retrieved.append({"score": round(score, 4), "source": filename.strip()})

        return {
            "answer": result["answer"],
            "source": result["source"],
            "retrieved": retrieved
        }

    except Exception as e:
        print("Exception during prediction:")
        traceback.print_exc()
        return {
            "answer": "Request failed.",
            "source": "N/A",
            "retrieved": [],
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
