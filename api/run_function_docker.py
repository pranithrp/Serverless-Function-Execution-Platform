import subprocess
import uuid
import os

def ensure_docker_images():
    """Build Docker images if they don’t exist."""
    for lang, dockerfile, tag in [
        ("python", "Dockerfile.python", "code-runner-python"),
        ("node", "Dockerfile.node", "code-runner-node")
    ]:
        if not os.path.exists(dockerfile):
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile}. Ensure it’s in the current directory.")
        
        try:
            subprocess.run(["docker", "image", "inspect", tag], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            print(f"Building {tag} image from {dockerfile}...")
            subprocess.run(
                ["docker", "build", "-f", dockerfile, "-t", tag, "."],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

def run_function_docker(code: str, language: str, timeout: int) -> str:
    """Run code in a Docker container with timeout and cleanup."""
    ensure_docker_images()
    
    temp_id = str(uuid.uuid4())
    
    if language == "python":
        filename = f"/tmp/{temp_id}.py"
        image_tag = "code-runner-python"
        command = f"python {os.path.basename(filename)}"
    elif language == "node":
        filename = f"/tmp/{temp_id}.js"
        image_tag = "code-runner-node"
        command = f"node {os.path.basename(filename)}"
    else:
        raise ValueError(f"Unsupported language: {language}")
    
    with open(filename, "w") as f:
        f.write(code)
    
    try:
        result = subprocess.run([
            "docker", "run", "--rm",
            "-v", f"{os.path.dirname(os.path.abspath(filename))}:/app",
            image_tag,
            "sh", "-c", command
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        stdout = result.stdout.decode()
        stderr = result.stderr.decode()
        output = stdout if stdout else stderr
    except subprocess.TimeoutExpired:
        output = f"Execution timed out after {timeout} seconds."
    except subprocess.CalledProcessError as e:
        output = f"Execution failed: {e.stderr.decode()}"
    finally:
        if os.path.exists(filename):
            os.remove(filename)
    
    return output

if __name__ == "__main__":
    print(run_function_docker('print("Hello from Python Docker")', "python", 5))
    print(run_function_docker('console.log("Hello from Node Docker")', "node", 5))
