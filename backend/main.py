import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import mockAgent

app = FastAPI(title="Agent Sentinel API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to hold the loaded model
classifier = None

@app.on_event("startup")
async def load_model():
    global classifier
    print("Loading DistilBERT classifier...")
    # Path to the classifier directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "results", "agent-sentinel-classifier")
    
    if os.path.exists(model_path):
        try:
            # We use a text-classification pipeline
            classifier = pipeline("text-classification", model=model_path, tokenizer=model_path)
            print("Classifier loaded successfully.")
        except Exception as e:
            print(f"Error loading classifier: {e}")
    else:
        print(f"WARNING: Classifier directory not found at {model_path}")

class ScenarioRequest(BaseModel):
    user_message: str
    attached_content: str = None

@app.post("/run-unprotected")
async def run_unprotected(request: ScenarioRequest):
    """
    Runs the scenario without any protection.
    """
    try:
        result = mockAgent.run_scenario(
            user_message=request.user_message,
            attached_content=request.attached_content
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-protected")
async def run_protected(request: ScenarioRequest):
    """
    Runs the scenario with the classifier as a defense mechanism.
    """
    risk_score = 0.0
    status = "approved"
    
    if request.attached_content and classifier:
        try:
            # Run the classifier on the attached content
            prediction = classifier(request.attached_content)
            # Example prediction format: [{'label': 'LABEL_1', 'score': 0.95}] or [{'label': '1', 'score': ...}]
            # We need to parse it based on the exact label names your model outputs.
            # Assuming 'LABEL_1' or '1' is the attack class.
            
            # Let's handle generic cases
            for pred in prediction:
                # Often fine-tuned models output 'LABEL_1' for class 1
                if pred['label'] == 'LABEL_1' or pred['label'] == '1' or 'attack' in pred['label'].lower():
                    risk_score = pred['score']
                elif pred['label'] == 'LABEL_0' or pred['label'] == '0' or 'safe' in pred['label'].lower():
                    # If it outputs safe score, the risk score is 1 - safe_score
                    risk_score = 1.0 - pred['score']

            # Threshold for blocking
            if risk_score > 0.5:
                status = "blocked"
                return {
                    "status": status,
                    "risk_score": risk_score,
                    "transcript": [],
                    "actions_taken": [],
                    "message": "Blocked by Sentinel Defense Classifier."
                }
        except Exception as e:
            print(f"Error during classification: {e}")

    # If not blocked, proceed to the mock agent
    try:
        result = mockAgent.run_scenario(
            user_message=request.user_message,
            attached_content=request.attached_content
        )
        result["status"] = "approved"
        result["risk_score"] = risk_score
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
