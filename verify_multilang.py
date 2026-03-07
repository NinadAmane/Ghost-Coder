import os
import shutil
from src.tools.docker_sandbox import DockerSandbox

def test_language_detection():
    sandbox = DockerSandbox()
    temp_dirs = ["test_python", "test_rust", "test_node"]
    
    # Create mock project structures
    os.makedirs("test_python", exist_ok=True)
    with open("test_python/requirements.txt", "w") as f: f.write("pytest")
    
    os.makedirs("test_rust", exist_ok=True)
    with open("test_rust/Cargo.toml", "w") as f: f.write("[package]")
    
    os.makedirs("test_node", exist_ok=True)
    with open("test_node/package.json", "w") as f: f.write("{}")
    
    try:
        # Test Python
        python_cfg = sandbox.detect_language(os.path.abspath("test_python"))
        print(f"Python detection: {python_cfg['language']} (Expected: python)")
        
        # Test Rust
        rust_cfg = sandbox.detect_language(os.path.abspath("test_rust"))
        print(f"Rust detection: {rust_cfg['language']} (Expected: rust)")
        
        # Test Node
        node_cfg = sandbox.detect_language(os.path.abspath("test_node"))
        print(f"Node detection: {node_cfg['language']} (Expected: node)")
        
        success = (python_cfg['language'] == 'python' and 
                   rust_cfg['language'] == 'rust' and 
                   node_cfg['language'] == 'node')
        
        if success:
            print("\n✅ Verification SUCCESS: Language detection is working perfectly!")
        else:
            print("\n❌ Verification FAILED: Language detection returned incorrect values.")
            
    finally:
        # Cleanup
        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__":
    test_language_detection()
