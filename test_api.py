import json
from pathlib import Path
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_generate_docs():
    print("Loading test data...")
    dir_path = Path(__file__).parent
    prompt_path = dir_path / "prompt.md"
    data_path = dir_path / "data.json"
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()
        
    with open(data_path, "r", encoding="utf-8") as f:
        json_payload = json.load(f)
        
    print("Sending POST request to /api/generate-docs...")
    response = client.post(
        "/api/generate-docs",
        json={
            "prompt": prompt_text,
            "json_payload": json_payload
        }
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        out_file = dir_path / "test_output.docx"
        with open(out_file, "wb") as f:
            f.write(response.content)
        print(f"Success! Saved test report to {out_file}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_generate_docs()
