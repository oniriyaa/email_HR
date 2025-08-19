from flask import Flask, request, send_file, jsonify, render_template_string
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import os
import random
from werkzeug.utils import secure_filename
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import threading
from concurrent.futures import ThreadPoolExecutor
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'

# สร้าง folder หากไม่มี
for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULT_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# กำหนด logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovedContactSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.driver = None
        
    def setup_session(self):
        """ตั้งค่า session สำหรับ HTTP requests"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        }
        self.session.headers.update(headers)
    
    def init_selenium_driver(self):
        """เริ่มต้น Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return True
        except Exception as e:
            logger.error(f"Error initializing Selenium: {e}")
            return False
    
    def close_driver(self):
        """ปิด Selenium WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
    
    def extract_contact_info(self, text_content):
        """ดึงข้อมูลติดต่อจาก text"""
        email = None
        phone = None
        website = None
        
        # ค้นหา Email (รูปแบบไทยและสากล)
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com|co\.th|net|org|th)',
        ]
        
        for pattern in email_patterns:
            emails = re.findall(pattern, text_content, re.IGNORECASE)
            if emails:
                # กรองอีเมลที่ไม่ใช่ spam
                valid_emails = [e for e in emails if not any(spam in e.lower() 
                    for spam in ['noreply', 'no-reply', 'donotreply', 'google', 'facebook'])]
                if valid_emails:
                    email = valid_emails[0]
                    break
        
        # ค้นหาเบอร์โทรไทย
        phone_patterns = [
            r'0[2-9][0-9]{7,8}',  # เบอร์ไทย 02-xxx-xxxx, 08x-xxx-xxxx
            r'\+66[0-9]{8,9}',    # +66 format
            r'66[0-9]{8,9}',      # 66 format
            r'0[0-9]{1,2}[-\s]?[0-9]{3}[-\s]?[0-9]{4}',  # 02-xxx-xxxx
            r'0[0-9]{2}[-\s]?[0-9]{3}[-\s]?[0-9]{3,4}',  # 08x-xxx-xxxx
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text_content.replace(' ', '').replace('-', ''))
            if phones:
                phone = phones[0]
                break
        
        # ค้นหาเว็บไซต์
        website_patterns = [
            r'https?://[^\s<>"]+(?:\.[^\s<>"]+)*',
            r'www\.[^\s<>"]+(?:\.[^\s<>"]+)+',
            r'[a-zA-Z0-9.-]+\.(?:com|co\.th|net|org|th)(?:/[^\s<>"]*)?'
        ]
        
        for pattern in website_patterns:
            websites = re.findall(pattern, text_content, re.IGNORECASE)
            if websites:
                # กรองเว็บไซต์ที่ไม่เกี่ยวข้อง
                valid_sites = []
                for site in websites:
                    site = site.rstrip('.,)')
                    if not any(exclude in site.lower() for exclude in 
                        ['google', 'facebook', 'twitter', 'youtube', 'instagram', 'linkedin']):
                        valid_sites.append(site)
                
                if valid_sites:
                    website = valid_sites[0]
                    if not website.startswith('http'):
                        website = 'https://' + website
                    break
        
        return email, phone, website
    
    def search_with_selenium(self, company_name):
        """ค้นหาด้วย Selenium"""
        try:
            if not self.driver:
                if not self.init_selenium_driver():
                    return None, None, None
            
            # สร้าง search query
            queries = [
                f"{company_name} ติดต่อ เบอร์โทร อีเมล",
                f"{company_name} contact phone email thailand",
                f'"{company_name}" email phone website'
            ]
            
            for query in queries:
                try:
                    # ค้นหาใน Google
                    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    self.driver.get(search_url)
                    
                    # รอให้หน้าโหลด
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    time.sleep(random.uniform(2, 4))
                    
                    # ดึงข้อมูล
                    page_source = self.driver.page_source
                    email, phone, website = self.extract_contact_info(page_source)
                    
                    if any([email, phone, website]):
                        return email, phone, website
                        
                except TimeoutException:
                    logger.warning(f"Timeout searching for {company_name} with query: {query}")
                    continue
                except Exception as e:
                    logger.error(f"Error in selenium search: {e}")
                    continue
            
            return None, None, None
            
        except Exception as e:
            logger.error(f"Selenium search error for {company_name}: {e}")
            return None, None, None
    
    def search_duckduckgo(self, company_name):
        """ค้นหาจาก DuckDuckGo"""
        try:
            query = f"{company_name} contact email phone thailand"
            url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return self.extract_contact_info(response.text)
                
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
        
        return None, None, None
    
    def search_bing(self, company_name):
        """ค้นหาจาก Bing"""
        try:
            query = f"{company_name} contact email phone thailand"
            url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return self.extract_contact_info(response.text)
                
        except Exception as e:
            logger.error(f"Bing search error: {e}")
        
        return None, None, None
    
    def search_company_website_direct(self, company_name):
        """ค้นหาเว็บไซต์บริษัทโดยตรง"""
        try:
            # ลองหาเว็บไซต์โดยตรง
            possible_domains = [
                f"{company_name.lower().replace(' ', '')}.com",
                f"{company_name.lower().replace(' ', '')}.co.th",
                f"{company_name.lower().replace(' ', '')}.net",
                f"www.{company_name.lower().replace(' ', '')}.com",
                f"www.{company_name.lower().replace(' ', '')}.co.th"
            ]
            
            for domain in possible_domains:
                try:
                    # ลบอักขระพิเศษออก
                    domain = re.sub(r'[^\w.-]', '', domain)
                    url = f"https://{domain}"
                    
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        email, phone, website = self.extract_contact_info(response.text)
                        if any([email, phone]):
                            return email, phone, url
                            
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Direct website search error: {e}")
        
        return None, None, None
    
    def search_business_directories(self, company_name):
        """ค้นหาจากไดเรกทอรีธุรกิจ"""
        try:
            directories = [
                f"https://www.yellowpages.co.th/search?q={company_name.replace(' ', '+')}",
                f"https://www.thailandyp.com/search.php?keyword={company_name.replace(' ', '+')}",
            ]
            
            for directory_url in directories:
                try:
                    response = self.session.get(directory_url, timeout=15)
                    if response.status_code == 200:
                        email, phone, website = self.extract_contact_info(response.text)
                        if any([email, phone, website]):
                            return email, phone, website
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Business directory search error: {e}")
        
        return None, None, None
    
    def comprehensive_search(self, company_name):
        """ค้นหาแบบครอบคลุมจากหลายแหล่ง"""
        logger.info(f"Starting comprehensive search for: {company_name}")
        
        # ลำดับการค้นหา
        search_methods = [
            ("Selenium Google", self.search_with_selenium),
            ("DuckDuckGo", self.search_duckduckgo),
            ("Bing", self.search_bing),
            ("Direct Website", self.search_company_website_direct),
            ("Business Directories", self.search_business_directories)
        ]
        
        for method_name, search_func in search_methods:
            try:
                logger.info(f"Searching {company_name} using {method_name}")
                email, phone, website = search_func(company_name)
                
                if any([email, phone, website]):
                    logger.info(f"Found data for {company_name} via {method_name}")
                    return email, phone, website, method_name
                
                # Delay ระหว่างการค้นหา
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"Error in {method_name} for {company_name}: {e}")
                continue
        
        logger.info(f"No data found for {company_name}")
        return None, None, None, "ไม่พบข้อมูล"

# Global searcher instance
searcher = ImprovedContactSearcher()

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 ระบบค้นหาข้อมูลติดต่อธุรกิจ (ปรับปรุงแล้ว)</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            max-width: 900px; margin: 0 auto; padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        h1 { 
            color: #333; 
            text-align: center; 
            margin-bottom: 30px;
            font-size: 2.2em;
        }
        
        .upload-area { 
            border: 3px dashed #007bff; 
            padding: 40px; 
            text-align: center; 
            margin: 20px 0; 
            border-radius: 10px;
            background: #f8f9ff;
            transition: all 0.3s ease;
        }
        
        .upload-area:hover { 
            border-color: #0056b3; 
            background: #e6f3ff;
        }
        
        .btn { 
            background: linear-gradient(45deg, #007bff, #0056b3); 
            color: white; 
            border: none; 
            padding: 12px 25px; 
            cursor: pointer; 
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            margin: 10px 5px;
        }
        
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,123,255,0.3);
        }
        
        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
        }
        
        .progress { 
            display: none; 
            margin: 30px 0; 
            padding: 20px;
            background: #f1f3f4;
            border-radius: 10px;
        }
        
        .progress-bar {
            background: #e9ecef; 
            height: 25px; 
            border-radius: 12px; 
            margin: 15px 0;
            overflow: hidden;
        }
        
        .progress-fill {
            background: linear-gradient(45deg, #28a745, #20c997); 
            height: 100%; 
            border-radius: 12px; 
            width: 0%;
            transition: width 0.5s ease;
        }
        
        .result { 
            margin: 30px 0; 
            padding: 25px; 
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            border-radius: 10px;
            border: 1px solid #c3e6cb;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        
        .file-info {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        
        .alert-info {
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }
        
        .log-area {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 15px;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #666;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 ระบบค้นหาข้อมูลติดต่อธุรกิจ</h1>
        <p style="text-align: center; color: #666; margin-bottom: 30px;">
            ปรับปรุงแล้ว! ใช้ Selenium + หลายแหล่งข้อมูล
        </p>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <input type="file" id="fileInput" accept=".xlsx,.xls" style="display:none">
            <div style="font-size: 3em; margin-bottom: 15px;">📁</div>
            <h3>เลือกไฟล์ Excel (.xlsx)</h3>
            <p>ไฟล์ต้องมีคอลัมน์ "Company" สำหรับชื่อบริษัทที่ต้องการค้นหา</p>
            <div id="fileInfo" class="file-info" style="display:none;"></div>
        </div>
        
        <div style="text-align: center;">
            <button class="btn" onclick="startSearch()" id="searchBtn" disabled>
                🚀 เริ่มค้นหาข้อมูล
            </button>
        </div>
        
        <div class="alert alert-info">
            <strong>💡 คุณสมบัติใหม่:</strong><br>
            • ใช้ Selenium สำหรับ Google Search<br>
            • ค้นหาจาก DuckDuckGo, Bing<br>
            • ค้นหาเว็บไซต์บริษัทโดยตรง<br>
            • ค้นหาจากไดเรกทอรีธุรกิจ<br>
            • แสดงผลแบบ real-time
        </div>
        
        <div class="progress" id="progress">
            <h4>กำลังค้นหา... <span id="progressText">0%</span></h4>
            <div class="progress-bar">
                <div id="progressFill" class="progress-fill"></div>
            </div>
            <div id="currentCompany" style="margin-top: 10px; font-weight: bold;"></div>
            <div class="log-area" id="logArea"></div>
        </div>
        
        <div class="result" id="result" style="display:none;">
            <h3>✅ ผลลัพธ์การค้นหา</h3>
            <div class="stats" id="stats"></div>
            <button class="btn" onclick="downloadResult()" id="downloadBtn">
                💾 ดาวน์โหลดผลลัพธ์ (.xlsx)
            </button>
        </div>
        
        <div class="footer">
            <p>🔧 Powered by Selenium, BeautifulSoup & Multiple Search Engines</p>
            <p>📊 รองรับการค้นหาจาก Google, DuckDuckGo, Bing และแหล่งข้อมูลอื่นๆ</p>
        </div>
    </div>

    <script>
        let selectedFile = null;
        let resultFilename = null;
        let searchInterval = null;

        document.getElementById('fileInput').addEventListener('change', function(e) {
            selectedFile = e.target.files[0];
            const fileInfo = document.getElementById('fileInfo');
            const searchBtn = document.getElementById('searchBtn');
            
            if (selectedFile) {
                fileInfo.innerHTML = `
                    <strong>ไฟล์ที่เลือก:</strong> ${selectedFile.name}<br>
                    <strong>ขนาด:</strong> ${(selectedFile.size / 1024).toFixed(2)} KB<br>
                    <strong>ประเภท:</strong> ${selectedFile.type}
                `;
                fileInfo.style.display = 'block';
                searchBtn.disabled = false;
                searchBtn.innerHTML = '🚀 เริ่มค้นหาข้อมูล';
            } else {
                fileInfo.style.display = 'none';
                searchBtn.disabled = true;
            }
        });

        function updateLog(message) {
            const logArea = document.getElementById('logArea');
            const timestamp = new Date().toLocaleTimeString();
            logArea.textContent += `[${timestamp}] ${message}\\n`;
            logArea.scrollTop = logArea.scrollHeight;
        }

        function updateProgress(current, total, companyName, found) {
            const percent = Math.round((current / total) * 100);
            document.getElementById('progressText').textContent = `${percent}% (${current}/${total})`;
            document.getElementById('progressFill').style.width = `${percent}%`;
            document.getElementById('currentCompany').textContent = 
                `กำลังค้นหา: ${companyName} ${found ? '✅' : '⏳'}`;
        }

        async function checkProgress() {
            try {
                const response = await fetch('/progress');
                if (response.ok) {
                    const data = await response.json();
                    updateProgress(data.current, data.total, data.current_company, data.found_data);
                    updateLog(data.message);
                    
                    if (data.completed) {
                        clearInterval(searchInterval);
                        showResults(data.results);
                    }
                }
            } catch (error) {
                console.error('Error checking progress:', error);
            }
        }

        function showResults(results) {
            document.getElementById('progress').style.display = 'none';
            document.getElementById('result').style.display = 'block';
            
            resultFilename = results.filename;
            
            const stats = `
                <div class="stat-card">
                    <div class="stat-number">${results.total_companies}</div>
                    <div class="stat-label">บริษัททั้งหมด</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${results.found_emails}</div>
                    <div class="stat-label">พบอีเมล</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${results.found_phones}</div>
                    <div class="stat-label">พบเบอร์โทร</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${results.found_websites}</div>
                    <div class="stat-label">พบเว็บไซต์</div>
                </div>
            `;
            
            document.getElementById('stats').innerHTML = stats;
            document.getElementById('searchBtn').disabled = false;
            document.getElementById('searchBtn').innerHTML = '🚀 ค้นหาไฟล์ใหม่';
        }

        async function startSearch() {
            if (!selectedFile) {
                alert('กรุณาเลือกไฟล์ Excel ก่อน');
                return;
            }

            const formData = new FormData();
            formData.append('file', selectedFile);

            document.getElementById('progress').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            document.getElementById('searchBtn').disabled = true;
            document.getElementById('searchBtn').innerHTML = '⏳ กำลังประมวลผล...';
            
            updateLog('เริ่มการค้นหา...');

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    updateLog('อัปโหลดไฟล์สำเร็จ เริ่มค้นหาข้อมูล...');
                    
                    // เริ่มตรวจสอบความคืบหนา
                    searchInterval = setInterval(checkProgress, 2000);
                    
                } else {
                    const error = await response.json();
                    alert('เกิดข้อผิดพลาด: ' + error.error);
                    document.getElementById('progress').style.display = 'none';
                    document.getElementById('searchBtn').disabled = false;
                    document.getElementById('searchBtn').innerHTML = '🚀 เริ่มค้นหาข้อมูล';
                }
            } catch (error) {
                alert('เกิดข้อผิดพลาด: ' + error.message);
                document.getElementById('progress').style.display = 'none';
                document.getElementById('searchBtn').disabled = false;
                document.getElementById('searchBtn').innerHTML = '🚀 เริ่มค้นหาข้อมูล';
            }
        }

        function downloadResult() {
            if (resultFilename) {
                window.open(`/download/${resultFilename}`, '_blank');
            }
        }
    </script>
</body>
</html>
"""

# Global variables for progress tracking
progress_data = {
    'current': 0,
    'total': 0,
    'current_company': '',
    'found_data': False,
    'completed': False,
    'results': None,
    'message': ''
}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    global progress_data
    
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่มีไฟล์'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ไม่มีไฟล์ที่เลือก'}), 400
    
    if file and file.filename.endswith(('.xlsx', '.xls')):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Reset progress
        progress_data = {
            'current': 0,
            'total': 0,
            'current_company': '',
            'found_data': False,
            'completed': False,
            'results': None,
            'message': 'เริ่มการประมวลผล...'
        }
        
        # Start processing in background thread
        thread = threading.Thread(target=process_companies_async, args=(filepath,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'message': 'เริ่มการประมวลผล'})
    
    return jsonify({'error': 'ไฟล์ต้องเป็น .xlsx หรือ .xls'}), 400

@app.route('/progress')
def get_progress():
    return jsonify(progress_data)

def process_companies_async(filepath):
    global progress_data
    
    try:
        # อ่านไฟล์ Excel
        df = pd.read_excel(filepath)
        
        if 'Company' not in df.columns:
            progress_data['message'] = 'ข้อผิดพลาด: ไฟล์ต้องมีคอลัมน์ "Company"'
            progress_data['completed'] = True
            return
        
        total_companies = len(df)
        progress_data['total'] = total_companies
        progress_data['message'] = f'เริ่มค้นหา {total_companies} บริษัท'
        
        results = []
        found_emails = 0
        found_phones = 0
        found_websites = 0
        
        for index, row in df.iterrows():
            company_name = str(row['Company']).strip()
            progress_data['current'] = index + 1
            progress_data['current_company'] = company_name
            progress_data['found_data'] = False
            
            if not company_name or company_name == 'nan':
                results.append({
                    'Company': company_name,
                    'Email': '',
                    'Phone': '',
                    'Website': '',
                    'Address': '',
                    'Source': 'ไม่มีข้อมูล'
                })
                progress_data['message'] = f'ข้าม: {company_name} (ชื่อไม่ถูกต้อง)'
                continue
            
            progress_data['message'] = f'กำลังค้นหา: {company_name}'
            
            # ค้นหาข้อมูล
            email, phone, website, source = searcher.comprehensive_search(company_name)
            
            if any([email, phone, website]):
                progress_data['found_data'] = True
                if email: found_emails += 1
                if phone: found_phones += 1
                if website: found_websites += 1
                progress_data['message'] = f'พบข้อมูล: {company_name} ({source})'
            else:
                progress_data['message'] = f'ไม่พบข้อมูล: {company_name}'
            
            results.append({
                'Company': company_name,
                'Email': email or '',
                'Phone': phone or '',
                'Website': website or '',
                'Address': '',
                'Source': source
            })
        
        # บันทึกผลลัพธ์
        result_df = pd.DataFrame(results)
        result_filename = f"contact_results_{int(time.time())}.xlsx"
        result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)
        result_df.to_excel(result_path, index=False)
        
        # Complete
        progress_data['completed'] = True
        progress_data['results'] = {
            'filename': result_filename,
            'total_companies': total_companies,
            'found_emails': found_emails,
            'found_phones': found_phones,
            'found_websites': found_websites
        }
        progress_data['message'] = 'เสร็จสิ้น!'
        
        # Close selenium driver
        searcher.close_driver()
        
    except Exception as e:
        logger.error(f"Error in async processing: {e}")
        progress_data['message'] = f'ข้อผิดพลาด: {str(e)}'
        progress_data['completed'] = True

@app.route('/download/<filename>')
def download_file(filename):
    result_path = os.path.join(app.config['RESULT_FOLDER'], filename)
    if os.path.exists(result_path):
        return send_file(result_path, as_attachment=True, 
                        download_name=f'contact_results_{filename}')
    return jsonify({'error': 'ไฟล์ไม่พบ'}), 404

if __name__ == '__main__':
    # ตรวจสอบว่ามี ChromeDriver
    try:
        searcher.init_selenium_driver()
        searcher.close_driver()
        print("✅ Selenium ChromeDriver พร้อมใช้งาน")
    except Exception as e:
        print(f"⚠️  ข้อผิดพลาด ChromeDriver: {e}")
        print("💡 กรุณาติดตั้ง ChromeDriver และ Chrome")
    
    print("🚀 เริ่มเว็บเซิร์ฟเวอร์...")
    print("🌐 เปิด http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
