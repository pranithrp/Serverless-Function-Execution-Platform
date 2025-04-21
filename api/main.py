from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import subprocess
import sqlite3
from run_function_docker import run_function, ensure_docker_images, prewarm_containers, initialize_database

app = FastAPI()
functions = []  # In-memory storage of function metadata

# SQLite connection for metrics
conn = sqlite3.connect("metrics.db", check_same_thread=False)

# Allow frontend access (e.g., Streamlit running on localhost:8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set specific frontend origin if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Function(BaseModel):
    id: Optional[int] = None  # ✅ Add this line
    name: str
    route: str
    language: str
    timeout: int
    runtime: str = "runc"
    settings: Optional[Dict[str, str]] = {}


@app.on_event("startup")
async def startup_event():
    print("✅ Starting FastAPI server...")
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("🐳 Docker is running.")
    except subprocess.CalledProcessError:
        raise RuntimeError("❌ Docker is not running or accessible.")

    try:
        initialize_database(conn)
        print("📦 Database initialized.")
        ensure_docker_images()
        print("🛠️ Docker images ready.")
        prewarm_containers("python", "runc")
        prewarm_containers("python", "runsc")
        prewarm_containers("node", "runc")
        prewarm_containers("node", "runsc")
        print("🔥 Pre-warmed containers.")
    except Exception as e:
        raise RuntimeError(f"Startup failed: {str(e)}")

# ----------------------- CRUD APIs ------------------------

@app.post("/functions/", status_code=201)
async def create_function(function: Function):
    func_id = len(functions) + 1
    function_data = function.dict()
    function_data["id"] = func_id
    functions.append(function_data)
    print(f"[+] Created: {function_data}")
    return {"message": "Function created", "id": func_id}

@app.get("/functions/", response_model=List[Function])
async def get_all_functions():
    return functions

@app.get("/functions/{func_id}", response_model=Function)
async def get_function(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    return functions[func_id - 1]

@app.put("/functions/{func_id}")
async def update_function(func_id: int, function: Function):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    updated_function = function.dict()
    updated_function["id"] = func_id
    functions[func_id - 1] = updated_function
    print(f"[~] Updated: {updated_function}")
    return {"message": "Function updated", "function": updated_function}

@app.delete("/functions/{func_id}")
async def delete_function(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")
    deleted_function = functions.pop(func_id - 1)
    print(f"[-] Deleted: {deleted_function}")
    return {"message": "Function deleted"}

# ----------------------- Execution ------------------------

@app.post("/functions/{func_id}/run")
async def run_function_endpoint(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")

    function = functions[func_id - 1]
    code = function.get("settings", {}).get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    print(f"⚙️ Running: {function['name']} ({function['runtime']})")
    try:
        output, _ = run_function(
            code,
            function["language"],
            function["timeout"],
            function["runtime"],
            function["name"],
            conn
        )
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

# ----------------------- Metrics ------------------------

@app.get("/functions/{func_id}/metrics")
async def get_function_metrics(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")

    function = functions[func_id - 1]
    name = function["name"]
    try:
        cursor = conn.execute(
            "SELECT response_time, error, stdout, stderr, memory_usage, cpu_usage FROM metrics WHERE function_name = ? ORDER BY rowid DESC LIMIT 1",
            (name,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No metrics found")

        return {
            "metrics": {
                "response_time": row[0],
                "error": row[1],
                "stdout": row[2],
                "stderr": row[3],
                "memory_usage": row[4],
                "cpu_usage": row[5]
            }
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/")
async def get_all_metrics():
    try:
        cursor = conn.execute(
            "SELECT function_name, runtime, AVG(response_time), SUM(error), AVG(memory_usage), AVG(cpu_usage) "
            "FROM metrics GROUP BY function_name, runtime"
        )
        result = [
            {
                "function_name": row[0],
                "runtime": row[1],
                "avg_response_time": row[2],
                "error_count": row[3],
                "avg_memory_usage_mb": row[4],
                "avg_cpu_usage_percent": row[5]
            }
            for row in cursor.fetchall()
        ]
        return {"metrics": result}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/functions/{func_id}/compare")
async def compare_performance(func_id: int):
    if func_id > len(functions) or func_id <= 0:
        raise HTTPException(status_code=404, detail="Function not found")

    function = functions[func_id - 1]
    code = function.get("settings", {}).get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    runc_output, runc_metrics = run_function(code, function["language"], function["timeout"], "runc", function["name"], conn)
    runsc_output, runsc_metrics = run_function(code, function["language"], function["timeout"], "runsc", function["name"], conn)

    return {
        "comparison": {
            "runc": {
                "response_time": runc_metrics["response_time"],
                "memory_usage": runc_metrics["memory_usage"],
                "cpu_usage": runc_metrics["cpu_usage"],
                "output": runc_output
            },
            "runsc": {
                "response_time": runsc_metrics["response_time"],
                "memory_usage": runsc_metrics["memory_usage"],
                "cpu_usage": runsc_metrics["cpu_usage"],
                "output": runsc_output
            }
        }
    }

