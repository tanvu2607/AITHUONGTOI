import os
import sys
import json
import base64
import time
import re
import requests
import google.generativeai as genai
from pathlib import Path
import zipfile
import io
import traceback

# ==============================================================================
# I. CẤU HÌNH VÀ THIẾT LẬP TOÀN CỤC
# ==============================================================================
print("--- ⚙️  Đang khởi tạo Tác nhân AI Tự trị ---")
try:
    GH_USER = os.environ["GH_USER"]
    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    RELEASE_KEYSTORE_PASSWORD = os.environ["RELEASE_KEYSTORE_PASSWORD"]
    RELEASE_KEY_ALIAS = os.environ["RELEASE_KEY_ALIAS"]
    RELEASE_KEY_PASSWORD = os.environ["RELEASE_KEY_PASSWORD"]
except KeyError as e:
    print(f"❌ LỖI: Thiếu biến môi trường bắt buộc: {e}")
    sys.exit(1)

COMMIT_AUTHOR = {"name": "Autonomous AI Agent", "email": "agent@example.com"}
API_BASE_URL = "https://api.github.com"
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
genai.configure(api_key=GEMINI_API_KEY)
MAX_DEBUG_LOOPS = 3

GITIGNORE_CONTENT = "# Flutter\n.flutter-plugins\n.flutter-plugins-dependencies\n.packages\n.pub-cache/\n.pub/\n/build/\n/ios/\n/windows/\n/linux/\n/macos/\n*.iml\n*.ipr\n*.iws\n*.swp\n*.lock\n*.snapshot\n.idea/\n"
SELF_HEALING_WORKFLOW = r"""
name: Build and Release Flutter APK
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { java-version: '17', distribution: 'temurin' }
      - uses: subosito/flutter-action@v2
        with: { channel: 'stable' }
      - run: flutter pub get
      - name: Decode Keystore and Create Properties
        run: |
          mkdir -p android/app
          echo "${{ secrets.RELEASE_KEYSTORE_BASE64 }}" | base64 --decode > android/app/upload-keystore.jks
          echo "storePassword=${{ secrets.RELEASE_KEYSTORE_PASSWORD }}" > android/key.properties
          echo "keyPassword=${{ secrets.RELEASE_KEY_PASSWORD }}" >> android/key.properties
          echo "keyAlias=${{ secrets.RELEASE_KEY_ALIAS }}" >> android/key.properties
          echo "storeFile=../app/upload-keystore.jks" >> android/key.properties
      - name: Build APK
        run: flutter build apk --release
      - uses: actions/upload-artifact@v4
        with: { name: release-apk, path: build/app/outputs/flutter-apk/app-release.apk }
"""

# ==============================================================================
# II. BỘ CÔNG CỤ (TOOLKIT) CỦA AGENT
# ==============================================================================

def call_gemini(prompt, use_pro_model=False):
    model_name = "gemini-2.5-pro-latest" if use_pro_model else "gemini-2.5-flash-latest"
    print(f"--- 🧠 Gọi AI ({model_name})... ---")
    model = genai.GenerativeModel(model_name)
    safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    
    # === CẢI TIẾN: XỬ LÝ LỖI QUOTA THÔNG MINH ===
    for attempt in range(1, 4):
        try:
            response = model.generate_content(prompt, request_options={'timeout': 400}, safety_settings=safety_settings)
            if hasattr(response, 'text'):
                return response.text
            elif not response.parts:
                raise ValueError(f"Phản hồi từ AI bị trống hoặc bị chặn. Lý do: {getattr(response.prompt_feedback, 'block_reason', 'Không rõ')}")
            else:
                return "".join(part.text for part in response.parts if hasattr(part, 'text'))
        except Exception as e:
            # Chỉ thử lại nếu là lỗi ResourceExhausted (429)
            if "429" in str(e) and "ResourceExhausted" in str(type(e).__name__):
                if attempt < 3:
                    wait_time = 65  # Đợi hơn 1 phút để reset quota RPM (Requests Per Minute)
                    print(f"   - ⚠️  Lỗi Quota (429). Đây là giới hạn của gói miễn phí. Đang đợi {wait_time} giây...")
                    time.sleep(wait_time)
                    continue # Thử lại vòng lặp
                else:
                    print("   - ❌ Đã thử 3 lần và vẫn bị lỗi Quota. Nâng cấp lên gói trả phí của Google AI Platform có thể giải quyết vấn đề này.")
                    raise e
            else:
                # Ném ra các lỗi khác ngay lập tức
                print(f"   - Lỗi khi gọi Gemini API: {e}")
                raise

def extract_json_from_ai(text):
    print("   - Đang trích xuất JSON từ phản hồi của AI...")
    if not text or not text.strip():
        raise ValueError("Phản hồi từ AI là chuỗi rỗng.")
        
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if not match:
        match = re.search(r'(\{.*?\})', text, re.DOTALL) # Fallback nếu không có markdown
    if not match:
        raise ValueError(f"Không tìm thấy JSON hợp lệ trong phản hồi:\n{text}")
        
    return json.loads(match.group(1), strict=False)

def github_api_request(method, url, json_data=None):
    response = requests.request(method, url, headers=HEADERS, json=json_data, timeout=60)
    response.raise_for_status()
    return response.json() if response.status_code != 204 and response.content else None

# ==============================================================================
# III. CÁC HÀNH ĐỘNG CẤP CAO (ACTIONS) CỦA AGENT
# ==============================================================================

class AgentActions:
    def __init__(self, repo_owner, repo_name):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_full_name = f"{repo_owner}/{repo_name}"

    def generate_initial_code(self, user_prompt, language):
        prompt = f'Bạn là một kỹ sư phần mềm chuyên về {language}. Dựa trên yêu cầu: "{user_prompt}", hãy tạo cấu trúc file và thư mục hoàn chỉnh. Trả về dưới dạng một đối tượng JSON lồng nhau duy nhất, bao bọc trong khối ```json ... ```.'
        
        for attempt in range(1, 4):
            print(f"--- 🧠 Gọi AI để tạo code (Lần thử {attempt}/3)... ---")
            try:
                response_text = call_gemini(prompt)
                file_tree = extract_json_from_ai(response_text)
                print("   - ✅ AI đã tạo code và JSON hợp lệ.")
                return file_tree
            except Exception as e:
                print(f"   - ⚠️ Lỗi ở lần thử {attempt}: {e}")
                if attempt < 3:
                    print("   - Đang đợi 5 giây trước khi thử lại...")
                    time.sleep(5)
                else:
                    print("   - ❌ Đã thử 3 lần và vẫn thất bại. Ném ra lỗi cuối cùng.")
                    raise e
        raise RuntimeError("Không thể tạo code từ AI sau nhiều lần thử.")

    def create_github_repo(self):
        print(f"--- 🛰️  Đang tạo repository: {self.repo_name} ---")
        github_api_request("POST", f"{API_BASE_URL}/user/repos", {"name": self.repo_name, "private": False, "auto_init": True})
        print("   - ✅ Repo đã được tạo. Đợi GitHub xử lý...")
        
        ref_url = f"{API_BASE_URL}/repos/{self.repo_full_name}/git/refs/heads/main"
        for i in range(10):
            time.sleep(3)
            try:
                main_ref = github_api_request("GET", ref_url)
                if main_ref:
                    print("   - ✅ Repo đã sẵn sàng.")
                    return main_ref
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404: continue
                else: raise e
        raise ConnectionError("Repo không sẵn sàng sau 30 giây.")

    def commit_files(self, file_tree, message, main_ref):
        print(f"--- ⬆️  Đang commit {len(file_tree)} file lên repo ---")
        flat_tree = self._flatten_file_tree(file_tree)
        latest_commit_sha = main_ref['object']['sha']
        base_tree_sha = github_api_request("GET", main_ref['object']['url'])['tree']['sha']
        
        tree_elements = []
        for path, content in flat_tree.items():
            if not isinstance(content, str): continue
            blob_sha = github_api_request("POST", f"{API_BASE_URL}/repos/{self.repo_full_name}/git/blobs", {"content": content, "encoding": "utf-8"})['sha']
            tree_elements.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})
        
        new_tree_sha = github_api_request("POST", f"{API_BASE_URL}/repos/{self.repo_full_name}/git/trees", {"base_tree": base_tree_sha, "tree": tree_elements})['sha']
        new_commit_sha = github_api_request("POST", f"{API_BASE_URL}/repos/{self.repo_full_name}/git/commits", {"message": message, "author": COMMIT_AUTHOR, "parents": [latest_commit_sha], "tree": new_tree_sha})['sha']
        
        update_ref_url = f"{API_BASE_URL}/repos/{self.repo_full_name}/git/refs/heads/main"
        github_api_request("PATCH", update_ref_url, {"sha": new_commit_sha})
        print("   - ✅ Đã commit thành công!")
    
    def upload_secrets(self):
        print(f"--- 🔑 Đang tự động thêm secrets vào repo {self.repo_name} ---")
        try:
            from nacl import encoding, public
        except ImportError:
            print("❌ LỖI: Thư viện 'pynacl' chưa được cài đặt. Hãy chạy: pip install pynacl")
            sys.exit(1)
        
        try:
            keystore_b64 = Path("keystore_base64.txt").read_text().strip()
        except FileNotFoundError:
            print("❌ LỖI: Không tìm thấy file 'keystore_base64.txt'.")
            sys.exit(1)
            
        secrets_to_upload = {"RELEASE_KEYSTORE_BASE64": keystore_b64, "RELEASE_KEYSTORE_PASSWORD": RELEASE_KEYSTORE_PASSWORD, "RELEASE_KEY_ALIAS": RELEASE_KEY_ALIAS, "RELEASE_KEY_PASSWORD": RELEASE_KEY_PASSWORD}
        
        key_url = f"{API_BASE_URL}/repos/{self.repo_full_name}/actions/secrets/public-key"
        key_data = github_api_request("GET", key_url)
        public_key = public.PublicKey(key_data['key'], encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key)

        for name, value in secrets_to_upload.items():
            encrypted = base64.b64encode(sealed_box.encrypt(value.encode("utf-8"))).decode("utf-8")
            github_api_request("PUT", f"{API_BASE_URL}/repos/{self.repo_full_name}/actions/secrets/{name}", {"encrypted_value": encrypted, "key_id": key_data['key_id']})
        
        print(f"   - ✅ Đã thêm thành công {len(secrets_to_upload)} secrets.")

    def get_latest_workflow_run(self):
        print(f"--- ⏱️  Đang kiểm tra trạng thái build cho {self.repo_full_name} ---")
        runs = github_api_request("GET", f"{API_BASE_URL}/repos/{self.repo_full_name}/actions/runs")
        if not runs or not runs.get('workflow_runs'):
            return None
        return runs['workflow_runs'][0]

    def get_failed_job_log(self, run_id):
        print(f"--- 📥 Đang tải log lỗi từ Run ID: {run_id} ---")
        response = requests.get(f"{API_BASE_URL}/repos/{self.repo_full_name}/actions/runs/{run_id}/logs", headers=HEADERS, stream=True, timeout=60)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            log_file_name = next((name for name in z.namelist() if 'build' in name and name.endswith('.txt')), z.namelist()[0])
            with z.open(log_file_name) as f:
                log_content = f.read().decode('utf-8', errors='ignore')
        return "\n".join(log_content.splitlines()[-200:])

    def get_file_content(self, file_path):
        try:
            response = github_api_request("GET", f"{API_BASE_URL}/repos/{self.repo_full_name}/contents/{file_path}")
            return base64.b64decode(response['content']).decode('utf-8'), response['sha']
        except Exception: return None, None
    
    def apply_code_patch(self, file_path, new_content, commit_message, sha):
        print(f"--- 🩹 Đang áp dụng bản vá cho file: {file_path} ---")
        github_api_request("PUT", f"{API_BASE_URL}/repos/{self.repo_full_name}/contents/{file_path}", {"message": commit_message, "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8'), "sha": sha, "author": COMMIT_AUTHOR})
        print("   - ✅ Đã commit bản vá thành công!")
        
    def _flatten_file_tree(self, file_tree, path=''):
        items = {}
        for key, value in file_tree.items():
            new_path = os.path.join(path, key) if path else key
            if isinstance(value, dict): items.update(self._flatten_file_tree(value, new_path))
            else: items[new_path] = value
        return items

# ==============================================================================
# IV. "BỘ NÃO" ĐIỀU KHIỂN CỦA AGENT
# ==============================================================================

class AutonomousAgent:
    def __init__(self, user_prompt, repo_name, language="Flutter"):
        self.state = "STARTING"
        self.user_prompt = user_prompt
        self.repo_name = repo_name
        self.language = language
        self.debug_attempts = 0
        self.actions = AgentActions(GH_USER, repo_name)
    
    def run(self):
        try:
            # GIAI ĐOẠN 1
            self.state = "GENERATING"
            print(f"\n=== GIAI ĐOẠN 1: KHỞI TẠO DỰ ÁN ({self.repo_name}) ===")
            file_tree = self.actions.generate_initial_code(self.user_prompt, self.language)
            file_tree['.gitignore'] = GITIGNORE_CONTENT
            if self.language.lower() == 'flutter':
                file_tree[".github/workflows/build.yml"] = SELF_HEALING_WORKFLOW
            
            main_ref = self.actions.create_github_repo()
            self.actions.commit_files(file_tree, "feat: Initial commit by Autonomous Agent", main_ref)
            if self.language.lower() == 'flutter':
                self.actions.upload_secrets()

            # GIAI ĐOẠN 2
            self.state = "MONITORING"
            print(f"\n=== GIAI ĐOẠN 2: GIÁM SÁT BUILD (Tối đa {MAX_DEBUG_LOOPS} lần sửa lỗi) ===")
            while self.debug_attempts < MAX_DEBUG_LOOPS:
                print(f"\n--- Vòng lặp giám sát (Lần {self.debug_attempts + 1}/{MAX_DEBUG_LOOPS}) ---")
                
                # CẢI TIẾN: Đợi workflow khởi động
                print("   - Đang đợi workflow khởi động (tối đa 2 phút)...")
                initial_run = None
                for _ in range(4): # Thử 4 lần, mỗi lần cách nhau 30s
                    initial_run = self.actions.get_latest_workflow_run()
                    if initial_run: break
                    time.sleep(30)
                
                if not initial_run:
                    print("   - ⚠️  Không phát hiện workflow nào được khởi động. Dừng lại.")
                    break
                
                print(f"   - Đã phát hiện workflow (ID: {initial_run['id']}). Đang đợi hoàn thành...")
                latest_run = None
                for _ in range(10): # Chờ tối đa 10 * 30s = 5 phút
                    latest_run = self.actions.get_latest_workflow_run()
                    if latest_run and latest_run['id'] == initial_run['id'] and latest_run['status'] == "completed": 
                        break
                    print(f"   - Trạng thái hiện tại: {latest_run.get('status', 'unknown')}. Đợi 30 giây...")
                    time.sleep(30)
                
                if not latest_run or latest_run['status'] != "completed":
                    print("   - ⚠️  Workflow không hoàn thành trong thời gian chờ. Dừng lại.")
                    break
                
                if latest_run['conclusion'] == "success":
                    self.state = "DONE"
                    print("\n" + "="*50 + "\n🎉🎉🎉 BUILD THÀNH CÔNG! Nhiệm vụ hoàn tất! 🎉🎉🎉\n" + f"   - Link Repo: https://github.com/{self.actions.repo_full_name}\n" + "="*50)
                    return True

                elif latest_run['conclusion'] == "failure":
                    self.debug_attempts += 1
                    self.state = f"DEBUGGING_ATTEMPT_{self.debug_attempts}"
                    print(f"   - 📉 Build thất bại. Bắt đầu quy trình gỡ lỗi.")
                    
                    error_log = self.actions.get_failed_job_log(latest_run['id'])
                    files_to_read = ["pubspec.yaml", "lib/main.dart"]
                    files_content_map = {path: self.actions.get_file_content(path) for path in files_to_read}
                    
                    debug_prompt = f"Một build Flutter đã thất bại. Phân tích log và code để sửa lỗi.\n\n--- LOG LỖI ---\n{error_log}\n\n" + "".join([f"--- File `{path}` ---\n{content}\n" for path, (content, sha) in files_content_map.items() if content]) + "\n\n**NHIỆM VỤ:** Trả về một JSON duy nhất với cấu trúc: `{{\"analysis\": \"...\", \"file_to_patch\": \"...\", \"corrected_code\": \"...\", \"commit_message\": \"...\"}}`"
                    fix_suggestion_text = call_gemini(debug_prompt, use_pro_model=True)
                    fix_suggestion = extract_json_from_ai(fix_suggestion_text)
                    
                    file_to_patch = fix_suggestion.get("file_to_patch")
                    if file_to_patch and file_to_patch in files_content_map:
                        _, current_sha = files_content_map[file_to_patch]
                        if not current_sha: raise ValueError(f"Không thể lấy SHA của file {file_to_patch} để vá lỗi.")
                        self.actions.apply_code_patch(file_to_patch, fix_suggestion["corrected_code"], fix_suggestion["commit_message"], current_sha)
                        print("   - ✅ Đã áp dụng bản vá. Vòng lặp sẽ bắt đầu lại...")
                    else:
                        print("   - 💡 AI không thể tìm ra cách sửa. Dừng lại.")
                        break
            
            if self.debug_attempts >= MAX_DEBUG_LOOPS:
                print(f"\n🚨 Đã đạt giới hạn {MAX_DEBUG_LOOPS} lần sửa lỗi. Tác nhân dừng lại.")
            
        except Exception as e:
            print("\n❌ LỖI NGHIÊM TRỌNG TRONG QUÁ TRÌNH THỰC THI:")
            traceback.print_exc()

# ==============================================================================
# V. ĐIỂM KHỞI ĐỘNG
# ==============================================================================
if __name__ == "__main__":
    try:
        user_prompt = Path("prompt.txt").read_text(encoding="utf-8")
        repo_name = input("📁 Nhập tên cho repo mới: ")
        if not repo_name: raise ValueError("Tên repo không được để trống.")
        agent = AutonomousAgent(user_prompt, repo_name)
        agent.run()
    except FileNotFoundError:
        print("❌ LỖI: Không tìm thấy file 'prompt.txt'.")
    except Exception as e:
        print(f"\n❌ LỖI KHÔNG XÁC ĐỊNH TRƯỚC KHI KHỞI ĐỘNG AGENT: {e}")
        traceback.print_exc()
