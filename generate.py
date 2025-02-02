import os
import subprocess
import random
import string
import shutil
import time

DOMATO_PATH = "/home/ubuntu22/bababak/domato"
BASE_DIR = "/home/ubuntu22/bababak/fuzz_cases"
PROCESS_DIR = "/home/ubuntu22/bababak/fuzz_cases/processing"

def generate_random_string(length=8):
    # 랜덤 문자열 생성
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_html_files(num_files=10):
    # 랜덤 폴더 이름 생성
    random_folder_name = f"cases_{generate_random_string()}"
    temp_dir = os.path.join("/tmp", random_folder_name)
    output_dir = os.path.join(BASE_DIR, random_folder_name)
    _process_dir = os.path.join(PROCESS_DIR, random_folder_name)
    try:
        os.makedirs(temp_dir, exist_ok=True)

        # Domato를 사용하여 HTML 파일 생성
        subprocess.run([
            "python3", f"{DOMATO_PATH}/generator.py",
            "-o", temp_dir,
            "-n", str(num_files)
        ])

        # 생성된 HTML 파일을 수정하여 location.href 추가
        for i in range(num_files):  
            file_path = os.path.join(temp_dir, f"fuzz-{i:05d}.html")
            with open(file_path, "r") as file:
                content = file.read()

            if (i + 1) % 10 != 0 and i < num_files - 1:
                # 10개 단위로 끊지 않고, 다음 파일로 이동하는 스크립트 추가
                next_file_path = os.path.join(_process_dir, f"fuzz-{i+1:05d}.html")
                content = content.replace("</html>", f'</html><script>window.location.href = "file://{next_file_path}";</script>')
            else:
                # 9번 파일에서는 window.close() 추가
                content = content.replace("</html>", '</html><script>window.close();</script>')

            with open(file_path, "w") as file:
                file.write(content)

        shutil.move(temp_dir, output_dir)

        print(f"Generated {num_files} HTML files in {output_dir}")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Cleaning up temporary files...")
        raise
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Temporary directory {temp_dir} has been cleaned up.")

if __name__ == "__main__":
    while(1):
        generate_html_files()
        #time.sleep(1)
