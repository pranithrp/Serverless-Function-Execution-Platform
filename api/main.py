from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

# Initialize FastAPI app
app = FastAPI()

# In-memory database to store function details
functions = []

# Pydantic model for function details
class Function(BaseModel):
    name: str
    route: str
    language: str
    timeout: int
    settings: Optional[Dict[str, str]] = {}  # Add settings as a dictionary (optional)

# Create a new function with metadata (including settings)
@app.post("/functions/", status_code=201)
async def create_function(function: Function):
    func_id = len(functions) + 1
    function_data = function.dict()
    function_data["id"] = func_id
    functions.append(function_data)
    return {"message": "Function created", "id": func_id}

# Get all functions
@app.get("/functions/", response_model=List[Function])
async def get_all_functions():
    return functions

# Get a single function by ID
@app.get("/functions/{func_id}", response_model=Function)
async def get_function(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    return functions[func_id - 1]

# Update a function by ID
@app.put("/functions/{func_id}")
async def update_function(func_id: int, function: Function):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    
    # Update the function details, including settings
    updated_function = function.dict()
    updated_function["id"] = func_id
    functions[func_id - 1] = updated_function
    return {"message": "Function updated", "function": updated_function}

# Delete a function by ID
@app.delete("/functions/{func_id}")
async def delete_function(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    
    functions.pop(func_id - 1)
    return {"message": "Function deleted"}
