# คู่มือการเช่า Cloud VPS โตเกียว & ติดตั้ง LINE OpenChat Protocol Sniper (< 20ms)

คู่มือนี้จะสอนขั้นตอนการเช่าเซิร์ฟเวอร์ Cloud VPS ที่ **โตเกียว ประเทศญี่ปุ่น** และเปิดใช้งานบอทสไนเปอร์ความเร็วสูงระดับโปรโตคอล เพื่อยิงแซงบอทคู่แข่งในเสี้ยววินาที (< 20ms)

---

## ขั้นตอนที่ 1: เลือกและเช่า Cloud VPS ที่ "โตเกียว (Tokyo, Japan)"

> [!IMPORTANT]
> ต้องเลือก Data Center Location เป็น **Tokyo, Japan (โตเกียว ประเทศญี่ปุ่น)** เท่านั้น เพราะเซิร์ฟเวอร์หลักของ LINE อยู่ที่โตเกียว การเลือกโตเกียวจะทำให้มีค่าปิงเหลือเพียง **1 - 3 ms**!

### ตัวเลือกที่ 1: Vultr (แนะนำมากที่สุด - สะดวกและเร็วที่สุด)
1. ไปที่เว็บไซต์ [Vultr.com](https://www.vultr.com/)
2. กด **Deploy Server** -> เลือก **Cloud Compute - Shared CPU**
3. เลือก Server Location: **Tokyo (Japan)** 🇯🇵
4. เลือก Operating System: **Ubuntu 22.04 LTS** หรือ **24.04 LTS**
5. เลือก Plan: แผนเริ่มต้น **$5 / เดือน** (1 vCPU, 1 GB RAM, 25 GB SSD) เพียงพอเหลือเฟือสำหรับการรันบอทสไนเปอร์ความเร็วสูง
6. กด **Deploy Now** และรอประมาณ 1 นาที จะได้รับ **IP Address, Username (root) และ Password**

### ตัวเลือกที่ 2: AWS Lightsail
1. เข้าคอนโซล [AWS Lightsail](https://lightsail.aws.amazon.com/)
2. เลือก Region: **Tokyo (ap-northeast-1)** 🇯🇵
3. เลือก OS: **Linux/Unix** -> **Ubuntu 22.04 LTS**
4. เลือก Plan: **$3.50 / เดือน** (512 MB RAM หรือ 1 GB)
5. กด **Create Instance**

---

## ขั้นตอนที่ 2: เชื่อมต่อ SSH เข้าเซิร์ฟเวอร์ VPS

เปิดโปรแกรม **Terminal (บน Mac/Linux)** หรือ **PowerShell / Command Prompt (บน Windows)** แล้วพิมพ์:

```bash
ssh root@<IP_ของเซิร์ฟเวอร์คุณ>
```
*(ใส่รหัสผ่านที่ได้รับจาก Vultr/AWS)*

---

## ขั้นตอนที่ 3: ติดตั้งระบบด้วย 1-Click Script

เมื่อล็อกอินเข้าสู่ VPS เรียบร้อยแล้ว ให้ก็อปปี้คำสั่งด้านล่างนี้ไปวางในหน้าต่าง SSH:

```bash
# 1. โคลนโปรเจกต์ หรืออัปโหลดโค้ดมาที่ /opt/chat-line-bot
sudo git clone https://github.com/your-username/chat-line-bot.git /opt/chat-line-bot
cd /opt/chat-line-bot

# 2. รันสคริปต์ติดตั้งอัตโนมัติ
chmod +x deploy/setup_tokyo_vps.sh
./deploy/setup_tokyo_vps.sh
```

---

## ขั้นตอนที่ 4: ตั้งค่า Token ในไฟล์ `.env`

สร้างหรือแก้ไขไฟล์ `.env`:

```bash
nano /opt/chat-line-bot/.env
```

ใส่ข้อมูลเบื้องต้น:
```env
# โทเค็นบัญชี LINE ที่ใช้ยิง (แนะนำบัญชีสำรอง)
LINE_AUTH_TOKEN=your_auth_token_here

# โฮสต์เซิร์ฟเวอร์ LINE โตเกียว (ค่ามาตรฐานความเร็วสูงสุด)
LINE_TOKYO_HOST=ga2.line.naver.jp

# ไอดีห้อง OpenChat เป้าหมาย (ใส่หรือไม่ใส่ก็ได้ ถ้าไม่ใส่จะสไนเปอร์ทุกห้องที่ตรงกฎ)
TARGET_SQUARE_CHAT_MID=
```
กด `Ctrl + O` แล้ว `Enter` เพื่อบันทึก และ `Ctrl + X` เพื่อออก

---

## ขั้นตอนที่ 5: เริ่มการทำงานของสไนเปอร์

### ทดสอบรันสดเพื่อดูความเร็วและค่า Ping:
```bash
cd /opt/chat-line-bot
source venv/bin/activate
python -m gateways.cloud_protocol_sniper.runner
```
หน้าจอจะแสดง:
- ⚡ ความเร็วประกอบ Binary Thrift ในแรม: **~3 µs (0.003 มิลลิวินาที)**
- 📡 ค่า Ping ไปยัง LINE Tokyo Gateway: **1 - 3 ms** 🟢
- 📋 รายการกฎการ CF ทั้งหมดในระบบ

### สั่งให้ทำงานเบื้องหลัง 24 ชั่วโมง (ไม่ต้องเปิดหน้าต่างทิ้งไว้):
```bash
# เริ่ม Service
sudo systemctl start line-tokyo-sniper

# ดูสถานะการทำงาน
sudo systemctl status line-tokyo-sniper

# ดู Log การยิง CF สดๆ แบบ Real-time
sudo journalctl -u line-tokyo-sniper -f
```

---

## ตรวจสอบสถานะผ่าน Web Browser
คุณสามารถเปิดดูสถิติการดูดข้อความและการยิง CF ผ่านเว็บบราวเซอร์ได้ที่:
```
http://<IP_ของ_VPS>:8080/status
```
