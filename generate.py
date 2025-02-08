import os
import subprocess
import random
import string
import shutil
import time

#TODO: Configuration (change it to fit your system)
DOMATO_PATH = "/home/ubuntu22/bababak/domato"
BASE_DIR = "/home/ubuntu22/bababak/fuzz_cases"
PROCESS_DIR = "/home/ubuntu22/bababak/fuzz_cases/processing"

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# TODO : select num_files for your mind
def generate_html_files(num_files=10):
    # generate random string for dir name
    random_folder_name = f"cases_{generate_random_string()}"
    temp_dir = os.path.join("/tmp", random_folder_name)
    output_dir = os.path.join(BASE_DIR, random_folder_name)
    _process_dir = os.path.join(PROCESS_DIR, random_folder_name)
    try:
        # first, make cases on /tmp, then move it is created
        os.makedirs(temp_dir, exist_ok=True)

        # Domato
        subprocess.run([
            "python3", f"{DOMATO_PATH}/generator.py",
            "-o", temp_dir,
            "-n", str(num_files)
        ])

        # modify generated html for inject location.href & close
        for i in range(num_files):  
            file_path = os.path.join(temp_dir, f"fuzz-{i:05d}.html")
            with open(file_path, "r") as file:
                content = file.read()
                
            if (i + 1) % num_files != 0 and i < num_files - 1:
                # move in units of 10
                next_file_path = os.path.join(_process_dir, f"fuzz-{i+1:05d}.html")
                content = content.replace("</html>", f'</html><script>window.location.href = "file://{next_file_path}";</script>')
            else:
                # window.close() on last html
                content = content.replace("</html>", '</html><script>window.close();</script>')

            with open(file_path, "w") as file:
                file.write(content)
        # temp to fuzz_cases
        shutil.move(temp_dir, output_dir)

        print(f"Generated {num_files} HTML files in {output_dir}")

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Cleaning up temporary files...")
        raise
    finally:
        if os.path.exists(temp_dir):
            # clear tempdir if it stopped while make test cases
            shutil.rmtree(temp_dir)
            print(f"Temporary directory {temp_dir} has been cleaned up.")

if __name__ == "__main__":
    while(1):
        generate_html_files()
        #time.sleep(1)
