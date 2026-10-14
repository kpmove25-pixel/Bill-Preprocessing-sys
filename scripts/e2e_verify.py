"""端到端验证：上传真实票据 → 解析 → 打印字段。"""
import json
import time
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8000"


def post(path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        BASE + path, data=json.dumps(data).encode() if data else None, headers=headers
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


# 登录
token = post("/api/auth/login", {"username": "admin", "password": "admin123"})["token"]

# 上传一张微信图片（multipart）
boundary = "----Boundary"
img_path = "uploads/2026101423175290d250/original/微信图片_20261014213044_70_8.jpg"
with open(img_path, "rb") as f:
    img_data = f.read()

body = (
    ("--" + boundary + "\r\n").encode()
    + b'Content-Disposition: form-data; name="files"; filename="test.jpg"\r\n'
    + b"Content-Type: image/jpeg\r\n\r\n"
    + img_data
    + ("\r\n--" + boundary + "--\r\n").encode()
)
req = urllib.request.Request(
    BASE + "/api/tasks/upload",
    data=body,
    headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary},
)
with urllib.request.urlopen(req) as r:
    upload = json.loads(r.read())
task_id = upload["task_id"]
print("task_id:", task_id)

# 等待处理
for _ in range(30):
    time.sleep(1)
    task = post("/api/tasks/" + task_id, token=token)
    if task["status"] in ("done", "failed"):
        break

# 查询解析结果
invoices = post("/api/tasks/" + task_id + "/invoices", token=token)
for inv in invoices:
    for k in ("invoice_no", "buyer_name", "buyer_tax_no", "seller_name", "seller_tax_no",
              "amount", "amount_excluding_tax", "tax_amount", "tax_rate", "invoice_date",
              "drawer", "status"):
        print("  %-20s: %r" % (k, inv.get(k)))
