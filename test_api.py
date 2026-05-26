import json
import io
from pathlib import Path
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from api import app

client = TestClient(app)

def run_test(case_name, data=None, files=None):
    print(f"\n--- Running Test: {case_name} ---")
    response = client.post("/api/generate-docs", data=data, files=files)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        dir_path = Path(__file__).parent
        out_file = dir_path / f"test_output_{case_name}.docx"
        with open(out_file, "wb") as f:
            f.write(response.content)
        print(f"Success! Saved test report to {out_file}")
    else:
        print(f"Error: {response.text}")

def test_flexible_inputs():
    dir_path = Path(__file__).parent
    prompt_path = dir_path / "prompt.md"
    data_path = dir_path / "data.json"
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()
        
    with open(data_path, "r", encoding="utf-8") as f:
        raw_json_str = f.read()
        
    # --- Test Case 1: Uploading prompt file + Uploading json file ---
    files_case1 = {
        "prompt_file": ("prompt.md", io.BytesIO(prompt_text.encode("utf-8")), "text/markdown"),
        "json_file": ("data.json", io.BytesIO(raw_json_str.encode("utf-8")), "application/json")
    }
    # fastapi requires form parameters to be defined even if None, but here we can just pass empty dict
    run_test("case1_both_files", files=files_case1)
    
    # --- Test Case 2: Pasting prompt text + Pasting raw JSON string in form ---
    data_case2 = {
        "prompt": prompt_text,
        "json_payload": raw_json_str
    }
    # To simulate form fields we pass the data dict
    run_test("case2_both_text", data=data_case2)

    # --- Test Case 3: Mixed (Pasted prompt + Uploaded JSON file) ---
    data_case3 = {
        "prompt": prompt_text
    }
    files_case3 = {
        "json_file": ("data.json", io.BytesIO(raw_json_str.encode("utf-8")), "application/json")
    }
    run_test("case3_mixed_text_prompt_file_json", data=data_case3, files=files_case3)

if __name__ == "__main__":
    test_flexible_inputs()
