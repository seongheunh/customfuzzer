import os
import subprocess
import tempfile
import shutil
import random
import time
import threading
from pathlib import Path

# 환경 변수 설정
os.environ["ASAN_OPTIONS"] = "detect_leaks=0:detect_odr_violation=0"
os.environ["USE_ZEND_ALLOC"] = "0"

# Configuration
CHROME_PATH = "/home/ubuntu22/chromium/src/out/asan/chrome"
ASAN_SYMBOLIZE = "/home/ubuntu22/chromium/src/tools/valgrind/asan/asan_symbolize.py"
BASE_DIR = "/home/ubuntu22/bababak/fuzz_cases"
CRASH_DIR = "/home/ubuntu22/bababak/chrome_crashes"
PROCESS_DIR = "/home/ubuntu22/bababak/fuzz_cases/processing"
CRASH_IMMIDIATE_DIR = "/home/ubuntu22/bababak/chrome_crashes/crash"
CRASH_TIMEOUT_DIR = "/home/ubuntu22/bababak/chrome_crashes/crash_timeout"
TIMEOUT_DIR = "/home/ubuntu22/bababak/chrome_crashes/timeout"

def claim_case_folder(lock):
    # get case (moved to processing dir)
    with lock:
        case_folders = [f for f in os.listdir(BASE_DIR) if f.startswith("cases_")]
        if not case_folders:
            return None
        selected_folder = random.choice(case_folders)
        src = os.path.join(BASE_DIR, selected_folder)
        dest = os.path.join(PROCESS_DIR, selected_folder)
        try:
            shutil.move(src, dest)
            return dest
        except Exception as e:
            print(f"Error claiming case: {e}")
            return None

def symbolize_log(log_content):
    """Symbolize ASAN log output"""
    try:
        p1 = subprocess.Popen(['python3', ASAN_SYMBOLIZE], 
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(['c++filt'], 
                            stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
        p1.stdin.write(log_content)
        p1.stdin.close()
        return p2.communicate()[0]
    except Exception as e:
        print(f"Symbolization failed: {e}")
        return log_content

def check_asan_log(stderr_content):
    """Check if stderr contains ASAN error log"""
    asan_indicators = [
        "asan",
        "ERROR: AddressSanitizer",
        "ASAN:DEADLYSIGNAL",
        "ASAN:SIGSEGV",
        "AddressSanitizer:DEADLYSIGNAL",
        "Check failed:",  # Check failure도 ASAN 로그로 간주
        "FATAL:"         # FATAL error도 ASAN 로그로 간주
    ]
    return any(indicator in stderr_content for indicator in asan_indicators)

def run_test_case(case_dir):
    """Run the test case in Chrome and check for crashes"""
    file = 'fuzz-00001.html'
    crash_type = None

    user_data_dir = tempfile.mkdtemp()
    html_path = os.path.join(case_dir, file)
    
    cmd = [
        CHROME_PATH,
        f'--user-data-dir={user_data_dir}',
        '--enable-logging=stderr',
        "--disable-gpu",
        "--no-sandbox",
        "--js-flags=--expose_gc",
        "--enable-blink-test-features",
        "--disable-popup-blocking",
        "--ignore-certificate-errors",
        "--enable-experimental-web-platform-features",
        "--enable-features=AutofillAddressProfileSavePrompt",
        '--new-window',
        "file://"+html_path
    ]
    
    stdout_path = os.path.join(case_dir, f'{file}_stdout.log')
    stderr_path = os.path.join(case_dir, f'{file}_stderr.log')
    
    env = os.environ.copy()

    with open(stdout_path, 'w') as stdout_f, open(stderr_path, 'w') as stderr_f:
        proc = subprocess.Popen(cmd, env=env, stdout=stdout_f, stderr=stderr_f)

    try:
        returncode = proc.wait(timeout=30)
        # Timeout 없이 종료된 경우
        with open(stderr_path, 'r') as f:
            stderr_content = f.read()
        if check_asan_log(stderr_content):
            crash_type = "crash"  # ASAN 로그가 있으면서 즉시 종료된 경우
            print(f"[+] Immediate crash detected with ASAN log")
        else:
            crash_type = None     # 정상 종료

    except subprocess.TimeoutExpired:
        proc.kill()
        # Timeout 발생한 경우
        with open(stderr_path, 'r') as f:
            stderr_content = f.read()
        if check_asan_log(stderr_content):
            crash_type = "crash_timeout"  # ASAN 로그가 있는 timeout
            print(f"[+] Crash timeout detected with ASAN log")
        else:
            crash_type = "timeout"        # 일반 timeout
            print(f"[-] Normal timeout detected")

    except Exception as e:
        print(f"Error during test case execution: {e}")
        crash_type = None

    # Cleanup
    shutil.rmtree(user_data_dir, ignore_errors=True)
    return crash_type

def worker(lock):
    """Worker thread function for continuous fuzzing"""

    while True:
        case_dir = claim_case_folder(lock)
        if not case_dir:
            time.sleep(1)
            continue
            
        print(f"Processing: {os.path.basename(case_dir)}")
        try:
            crash_type = run_test_case(case_dir)
            if crash_type:
                crash_name = f"{os.path.basename(case_dir)}_{int(time.time())}"

                if crash_type == "crash":
                    dest_dir = CRASH_IMMIDIATE_DIR
                elif crash_type == "crash_timeout":
                    dest_dir = CRASH_TIMEOUT_DIR
                else:  # timeout
                    dest_dir = TIMEOUT_DIR

                crash_path = os.path.join(dest_dir, crash_name)
                shutil.move(case_dir, crash_path)
                print(f"[+] {crash_type} saved to {crash_path}")
            else:
                shutil.rmtree(case_dir, ignore_errors=True)
                print(f"[-] Cleaned {os.path.basename(case_dir)}")
        except Exception as e:
            print(f"Error processing case: {e}")
            shutil.rmtree(case_dir, ignore_errors=True)

def cleanup_processing_dir():
    """Clean up the processing directory"""
    for item in os.listdir(PROCESS_DIR):
        item_path = os.path.join(PROCESS_DIR, item)
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"Removed {item_path}")
            else:
                os.remove(item_path)
                print(f"Removed {item_path}")
        except Exception as e:
            print(f"Error removing {item_path}: {e}")

def main():
    os.makedirs(CRASH_DIR, exist_ok=True)
    os.makedirs(PROCESS_DIR, exist_ok=True)
    os.makedirs(CRASH_IMMIDIATE_DIR, exist_ok=True)
    os.makedirs(CRASH_TIMEOUT_DIR, exist_ok=True)
    os.makedirs(TIMEOUT_DIR, exist_ok=True)

    # 동시 실행 워커 수 (시스템 리소스에 맞게 조절)
    NUM_WORKERS = 10
    lock = threading.Lock()

    # 워커 스레드 시작
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(lock,), daemon=True)
        t.start()

    # 메인 스레드 유지
    try:
        while True:
            time.sleep(1)
            # 주기적으로 상태 확인 로직 추가 가능
    except KeyboardInterrupt:
        print("\nFuzzing stopped by user")
        cleanup_processing_dir()

if __name__ == '__main__':
    main()