from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from run_function_docker import run_function_docker, ensure_docker_images
import subprocess

app = FastAPI()
functions = []

class Function(BaseModel):
    name: str
    route: str
    language: str  # "python" or "node"
    timeout: int
    settings: Optional[Dict[str, str]] = {}  # Code will be stored in settings

class CodeInput(BaseModel):  # Kept for compatibility, but not used in /run
    code: str

@app.on_event("startup")
async def startup_event():
    """Validate environment and build Docker images."""
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        raise RuntimeError("Docker is not running or accessible.")
    
    try:
        ensure_docker_images()
    except FileNotFoundError as e:
        raise RuntimeError(str(e))
    except RuntimeError as e:
        raise RuntimeError(f"Docker image build failed: {str(e)}")

@app.post("/functions/", status_code=201)
async def create_function(function: Function):
    """Create a new function with metadata and code in settings."""
    func_id = len(functions) + 1
    function_data = function.dict()
    function_data["id"] = func_id
    functions.append(function_data)
    return {"message": "Function created", "id": func_id}

@app.get("/functions/", response_model=List[Function])
async def get_all_functions():
    """Retrieve all stored functions."""
    return functions

@app.get("/functions/{func_id}", response_model=Function)
async def get_function(func_id: int):
    """Retrieve a specific function by ID."""
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    return functions[func_id - 1]

@app.put("/functions/{func_id}")
async def update_function(func_id: int, function: Function):
    """Update an existing function."""
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    updated_function = function.dict()
    updated_function["id"] = func_id
    functions[func_id - 1] = updated_function
    return {"message": "Function updated", "function": updated_function}

@app.delete("/functions/{func_id}")
async def delete_function(func_id: int):
    """Delete a function by ID."""
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    functions.pop(func_id - 1)
    return {"message": "Function deleted"}

@app.post("/functions/{func_id}/run")
async def run_function(func_id: int):
    """Execute a function using code from settings."""
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    
    function = functions[func_id - 1]
    code = function.get("settings", {}).get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided in function settings")
    
    try:
        output = run_function_docker(
            code=code,
            language=function["language"],
            timeout=function["timeout"]
        )
        return {"output": output}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")
