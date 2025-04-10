import os
import uuid
import subprocess
import shutil

def run_function_firecracker(code: str, timeout: int = 3):
    exec_id = str(uuid.uuid4())
    exec_dir = f"executions/{exec_id}"
    os.makedirs(exec_dir, exist_ok=True)

    # 1. Write function.py inside exec dir
    with open(f"{exec_dir}/function.py", "w") as f:
        f.write(code)

    # 2. Copy rootfs into exec dir
    rootfs_path = f"{exec_dir}/rootfs.ext4"
    shutil.copy("hello-rootfs.ext4", rootfs_path)

    # 3. Mount code into rootfs using debugfs or guest tools (future work)

    # 4. Create API socket path
    api_socket = f"/tmp/firecracker-{exec_id}.sock"

    # 5. Start Firecracker VM
    fc_cmd = [
        "sudo", "firecracker",
        "--api-sock", api_socket
    ]
    process = subprocess.Popen(fc_cmd)

    # 6. Build JSON config
    import time
    time.sleep(0.5)

    import requests_unixsocket
    session = requests_unixsocket.Session()

    base = f"http+unix://{api_socket.replace('/', '%2F')}"
    def fc_put(path, payload):
        return session.put(base + path, json=payload)

    # 7. Send boot source + drives
    fc_put("/boot-source", {
        "kernel_image_path": "vmlinux.bin",
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
    })

    fc_put("/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": rootfs_path,
        "is_root_device": True,
        "is_read_only": False
    })

    fc_put("/machine-config", {
        "vcpu_count": 1,
        "mem_size_mib": 256
    })

    # 8. Start the VM
    fc_put("/actions", {
        "action_type": "InstanceStart"
    })

    return {
        "message": "Function sent to Firecracker microVM!",
        "vm_id": exec_id
    }
