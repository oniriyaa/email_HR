#!/usr/bin/env python3
from app import ImprovedContactSearcher
import time

def test_search():
    """ทดสอบการค้นหา"""
    searcher = ImprovedContactSearcher()
    
    # ทดสอบบริษัท
    test_companies = [
        "บริษัท เคอีเอ็กซ์ เอ็กซ์เพรส (ประเทศไทย) จำกัด (มหาชน)",
        "บริษัท ซีพี ออลล์ จำกัด (มหาชน)",
        "บริษัท แอดวานซ์ อินโฟ เซอร์วิส จำกัด (มหาชน)"
    ]
    
    print("🧪 เริ่มทดสอบการค้นหา...\n")
    
    for i, company in enumerate(test_companies, 1):
        print(f"{'='*50}")
        print(f"ทดสอบที่ {i}: {company}")
        print(f"{'='*50}")
        
        start_time = time.time()
        email, phone, website, source = searcher.comprehensive_search(company)
        elapsed_time = time.time() - start_time
        
        print(f"⏱️  เวลาที่ใช้: {elapsed_time:.2f} วินาที")
        print(f"📧 Email: {email or 'ไม่พบ'}")
        print(f"📞 Phone: {phone or 'ไม่พบ'}")
        print(f"🌐 Website: {website or 'ไม่พบ'}")
        print(f"🔍 แหล่งข้อมูล: {source}")
        print(f"✅ สถานะ: {'พบข้อมูล' if any([email, phone, website]) else 'ไม่พบข้อมูล'}")
        print()
    
    searcher.close_driver()
    print("🎉 ทดสอบเสร็จสิ้น!")

if __name__ == "__main__":
    test_search()
