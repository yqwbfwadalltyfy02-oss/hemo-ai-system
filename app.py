from flask import Flask, request, jsonify
import os
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)

# دالة الاتصال بقاعدة البيانات السحابية في Railway
def get_db_connection():
    url = urlparse(os.environ.get("DATABASE_URL"))
    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    return conn

# إنشاء الجدول لتخزين القراءات المعتمدة فقط
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS measurements (
                id SERIAL PRIMARY KEY,
                sensor_value INTEGER,
                hb_value REAL,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database Init Error: {e}")

init_db()

@app.route('/')
def home():
    return "Hemo-AI Secure Backend is Active!"

# نقطة استقبال البيانات مع الفلترة الصارمة (رفض أي صورة عادية أو قراءة وهمية)
@app.route('/upload_data', methods=['POST'])
def upload_data():
    data = request.json
    sensor_value = data.get('sensor_value')
    hb_value = data.get('hb_value')
    
    if sensor_value is not None and hb_value is not None:
        # --- شرط الفلترة الصارم لمنع الصور العادية والقراءات الوهمية ---
        MIN_BLOOD_THRESHOLD = 200
        MAX_BLOOD_THRESHOLD = 850
        
        # إذا كانت القراءة خارج نطاق الدم الحقيقي (صورة عادية، فراغ، إضاءة غرفة)
        if not (MIN_BLOOD_THRESHOLD <= sensor_value <= MAX_BLOOD_THRESHOLD):
            return jsonify({
                "status": "rejected", 
                "message": "Access Denied: Normal image or invalid sample detected. No value generated."
            }), 400
        
        # إذا اجتازت العينة الفحص بنجاح، يتم حفظها حصرياً في قاعدة البيانات
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO measurements (sensor_value, hb_value, status) VALUES (%s, %s, %s)",
                (sensor_value, hb_value, "Verified Blood Sample")
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({
                "status": "success", 
                "message": "Valid blood sample verified and saved to database!",
                "hb_value": hb_value
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
            
    return jsonify({"status": "error", "message": "Invalid data format"}), 400

# نقطة استعراض القراءات المعتمدة حصرياً من قاعدة البيانات
@app.route('/get_records', methods=['GET'])
def get_records():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, sensor_value, hb_value, status, created_at FROM measurements ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        records = []
        for row in rows:
            records.append({
                "id": row[0],
                "sensor_value": row[1],
                "hb_value": row[2],
                "status": row[3],
                "time": str(row[4])
            })
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)