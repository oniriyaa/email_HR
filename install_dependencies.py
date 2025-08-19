#!/usr/bin/env python3
import subprocess
import sys
import os

def install_requirements():
    """ติดตั้ง Python packages"""
    print("🔧 กำลังติดตั้ง Python packages...")
    
    packages = [
        "Flask==2.3.3",
        "pandas==2.0.3", 
        "openpyxl==3.1.2",
        "requests==2.31.0",
        "beautifulsoup4==4.12.2",
        "lxml==4.9.3",
        "selenium==4.15.0",
        "webdriver-manager==4.0.1"
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ ติดตั้ง {package} สำเร็จ")
        except subprocess.CalledProcessError:
            print(f"❌ ติดตั้ง {package} ไม่สำเร็จ")

def setup_chrome_driver():
    """ตั้งค่า Chrome Driver"""
    print("\n🌐 กำลังตั้งค่า Chrome Driver...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # ติดตั้ง ChromeDriver อัตโนมัติ
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.quit()
        
        print("✅ Chrome Driver พร้อมใช้งาน")
        
    except Exception as e:
        print(f"❌ ข้อผิดพลาด Chrome Driver: {e}")
        print("💡 กรุณาติดตั้ง Google Chrome และลองใหม่")

def create_folders():
    """สร้าง folders ที่จำเป็น"""
    print("\n📁 กำลังสร้าง folders...")
    
    folders = ['uploads', 'results', 'static', 'templates']
    
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"✅ สร้าง folder {folder}")
        else:
            print(f"📂 folder {folder} มีอยู่แล้ว")

if __name__ == "__main__":
    print("🚀 เริ่มการติดตั้งระบบ...")
    
    install_requirements()
    create_folders()
    setup_chrome_driver()
    
    print("\n🎉 ติดตั้งเสร็จสิ้น!")
    print("🌐 รันคำสั่ง: python app.py")
    print("🔗 เปิดเบราว์เซอร์ไปที่: http://localhost:5000")
