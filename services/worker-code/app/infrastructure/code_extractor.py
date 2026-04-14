import os
import shutil
import zipfile
import subprocess
import structlog

logger = structlog.get_logger(__name__)

class CodeExtractor:
    @staticmethod
    def extract_or_clone(tenant_id: str, source_id: str, file_path: str = None, github_url: str = None, branch: str = "main", access_token: str = None) -> str:
        """
        Extracts a ZIP file or clones a GitHub repo to a dedicated folder.
        Returns the absolute path to the codebase root.
        """
        base_dir = f"/tmp/tenants/{tenant_id}/code/{source_id}"
        
        # Clean up if exists
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir, exist_ok=True)
        
        if github_url:
            logger.info("code_extractor_cloning", url=github_url, branch=branch)
            env = os.environ.copy()
            if access_token:
                if "https://" in github_url:
                    auth_url = github_url.replace("https://", f"https://oauth2:{access_token}@")
                else:
                    auth_url = github_url
            else:
                auth_url = github_url
                
            cmd = ["git", "clone", "--branch", branch, "--single-branch", "--depth", "1", auth_url, base_dir]
            subprocess.run(cmd, check=True, capture_output=True, env=env)
            
            # Remove .git folder immediately to make parsing lighter
            git_dir = os.path.join(base_dir, ".git")
            if os.path.exists(git_dir):
                shutil.rmtree(git_dir)
                
        elif file_path and os.path.exists(file_path):
            if file_path.endswith('.zip'):
                logger.info("code_extractor_extracting", file_path=file_path)
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(base_dir)
                    
                # Often ZIPs have a single root folder, if so, move everything up
                items = os.listdir(base_dir)
                if len(items) == 1 and os.path.isdir(os.path.join(base_dir, items[0])):
                    inner_dir = os.path.join(base_dir, items[0])
                    for item in os.listdir(inner_dir):
                        shutil.move(os.path.join(inner_dir, item), base_dir)
                    os.rmdir(inner_dir)
            else:
                # Handle single file: Copy it to base_dir
                logger.info("code_extractor_copying_single_file", file_path=file_path)
                shutil.copy2(file_path, os.path.join(base_dir, os.path.basename(file_path)))
                
        else:
            raise ValueError("Must provide either a valid file_path or a github_url")
            
        return base_dir
