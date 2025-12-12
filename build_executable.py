import os
import subprocess
import sys
import shutil

def install_pyinstaller():
    """PyInstaller가 설치되어 있지 않으면 설치합니다."""
    try:
        import PyInstaller
        print("✅ PyInstaller is already installed.")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    print("🚀 Starting build process for AlphaSniper...")

    # PyInstaller 설치 확인
    install_pyinstaller()

    # 빌드 명령어 옵션 설정
    # --onefile: 하나의 실행 파일로 묶음
    # --name: 실행 파일 이름
    # --hidden-import: Telethon이 동적으로 로딩하는 모듈이 있을 경우 추가 (보통 기본으로 되지만 명시 권장)
    cmd = [
        "pyinstaller",
        "--clean",
        "--onefile",
        "--name=AlphaSniper",
        "--hidden-import=telethon",
        "main.py"
    ]

    print(f"🔨 Running command: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("\n" + "="*40)
        print("✅ Build Successful!")
        print("📁 Executable is located in the 'dist' folder.")
        print("="*40 + "\n")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build Failed: {e}")

if __name__ == "__main__":
    if os.path.exists("dist"):
        shutil.rmtree("dist") # 기존 빌드 삭제
    build()
