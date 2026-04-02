# 安全开发规范

## 安全优先级（前4条挡住90%攻击）

1. 用ORM，别拼SQL — 防注入
2. 每个API校验权限 — 防越权
3. 所有接口加限流 — 防刷
4. 全站HTTPS + 云WAF — 防中间人+常见Web攻击

---

## 一、SQL注入防御

### 原则：永远不要拼接SQL

```python
# 错 — 拼字符串，一打一个准
query = f"SELECT * FROM cases WHERE disease = '{user_input}'"

# 对 — ORM参数化查询，天然防注入
case = db.query(Case).filter(Case.disease == user_input).first()

# 如果必须写原生SQL，用参数绑定
from sqlalchemy import text
result = db.execute(text("SELECT * FROM cases WHERE disease = :name"), {"name": user_input})
```

### 检查清单
- [ ] 全项目搜索 `f"SELECT` / `f"INSERT` / `f"UPDATE` / `f"DELETE`，确认零结果
- [ ] 全项目搜索 `.format(` 后跟SQL关键字，确认零结果
- [ ] 使用 `bandit` 静态分析工具自动检测

---

## 二、XSS（跨站脚本）防御

### 病例内容是重灾区 — 用户输入的富文本必须清洗

```python
# 后端：白名单过滤HTML标签
import bleach

ALLOWED_TAGS = ['p', 'br', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 'h3', 'h4', 'blockquote']
ALLOWED_ATTRS = {}  # 不允许任何属性（尤其是 href/src/onclick）

def sanitize_html(raw_content: str) -> str:
    return bleach.clean(raw_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
```

```typescript
// 前端：React默认转义，但以下场景要小心
// 错 — 直接插入HTML
<div dangerouslySetInnerHTML={{ __html: caseContent }} />

// 对 — 用DOMPurify二次清洗
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(caseContent) }} />
```

### HTTP安全头

```nginx
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options DENY;
add_header X-XSS-Protection "1; mode=block";
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https://oss.example.com;";
add_header Referrer-Policy strict-origin-when-cross-origin;
```

---

## 三、越权访问防御（最容易忽视，后果最严重）

### 原则：每个API都必须验证"这个用户有没有权限做这件事"

```python
# 错 — 只要知道ID就能看任何人的完整病例
@app.get("/api/cases/{case_id}/full")
async def get_full_case(case_id: int):
    return db.query(Case).get(case_id)

# 对 — 验证身份 + 验证权限
@app.get("/api/cases/{case_id}/full")
async def get_full_case(case_id: int, current_user = Depends(get_current_user)):
    case = db.query(Case).get(case_id)
    if not case:
        raise HTTPException(404)
    
    # 作者本人可以看
    if case.author_id == current_user.id:
        return case
    
    # 已购买可以看
    purchase = db.query(Transaction).filter(
        Transaction.case_id == case_id,
        Transaction.buyer_id == current_user.id,
        Transaction.payment_status == "paid"
    ).first()
    if not purchase:
        raise HTTPException(403, "未购买此病例")
    
    return case
```

### 常见越权场景检查表

| 场景 | 检查 |
|------|------|
| 查看他人完整病例 | 必须已购买或是作者 |
| 编辑/删除病例 | 必须是作者本人 |
| 查看他人订单 | 必须是买方或卖方 |
| 管理后台操作 | 必须是管理员角色 |
| 修改用户资料 | 必须是本人 |
| 提现 | 必须是本人且已实名 |
| 审核操作 | 必须是审核员角色 |

### IDOR（不安全的直接对象引用）防御

```python
# 错 — 用自增ID，容易被遍历
/api/cases/1
/api/cases/2
/api/cases/3  # 攻击者依次尝试

# 对 — 外部用UUID，内部用自增ID
import uuid

class Case(Base):
    id = Column(BigInteger, primary_key=True)              # 内部用
    public_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True)  # 对外用

# API用public_id
@app.get("/api/cases/{public_id}/full")
```

---

## 四、接口限流

### 关键接口限流配置

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 验证码 — 最容易被刷（短信费钱）
@app.post("/api/auth/sms-code")
@limiter.limit("1/minute")         # 同一IP每分钟1次
async def send_sms(request: Request, phone: str):
    # 额外：同一手机号每天最多10条
    daily_count = redis.get(f"sms:daily:{phone}")
    if daily_count and int(daily_count) >= 10:
        raise HTTPException(429, "今日验证码已达上限")
    ...

# 登录 — 防暴力破解
@app.post("/api/auth/login")
@limiter.limit("10/minute")        # 同一IP每分钟10次
async def login(request: Request):
    # 额外：同一账号连续失败5次锁定30分钟
    fail_count = redis.get(f"login:fail:{phone}")
    if fail_count and int(fail_count) >= 5:
        raise HTTPException(423, "账号已锁定，请30分钟后重试")
    ...

# 搜索 — 防爬虫
@app.get("/api/cases/search")
@limiter.limit("60/minute")

# 支付 — 防重复下单
@app.post("/api/orders")
@limiter.limit("10/minute")
```

### 完整限流表

| 接口类别 | 限制 | 说明 |
|----------|------|------|
| 发送验证码 | 1次/分钟/IP, 10次/天/手机号 | 防短信轰炸 |
| 登录 | 10次/分钟/IP, 5次失败锁定30分钟 | 防暴力破解 |
| 注册 | 5次/小时/IP | 防批量注册 |
| 搜索 | 60次/分钟 | 防爬虫 |
| 病例详情 | 120次/分钟 | 防批量抓取 |
| 创建订单 | 10次/分钟 | 防重复下单 |
| 上传文件 | 20次/小时 | 防存储滥用 |
| 管理后台API | 30次/分钟 | 正常使用足够 |

---

## 五、认证与密码安全

### 密码存储

```python
# 用bcrypt或argon2，绝对不要用md5/sha256
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 存储
hashed = pwd_context.hash(plain_password)
# 验证
is_valid = pwd_context.verify(plain_password, hashed)
```

### JWT Token设计

```python
from datetime import datetime, timedelta
from jose import jwt

# access_token: 短过期时间
def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=15)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm="HS256")

# refresh_token: 较长过期，单次使用后作废
def create_refresh_token(user_id: int) -> str:
    token_id = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(days=7)
    # 存Redis，用一次就删
    redis.setex(f"refresh:{token_id}", 7*86400, user_id)
    return jwt.encode({"sub": str(user_id), "jti": token_id, "exp": expire}, SECRET_KEY)

# 刷新时：旧refresh_token作废，发新的（Rotation）
def refresh(old_token: str):
    payload = jwt.decode(old_token, SECRET_KEY)
    token_id = payload["jti"]
    # 检查是否已使用
    user_id = redis.get(f"refresh:{token_id}")
    if not user_id:
        # 可能被盗用，吊销该用户所有token
        revoke_all_tokens(payload["sub"])
        raise HTTPException(401, "Token已失效")
    # 作废旧token
    redis.delete(f"refresh:{token_id}")
    # 发新token
    return create_access_token(int(user_id)), create_refresh_token(int(user_id))
```

### 敏感字段加密存储

```python
from cryptography.fernet import Fernet

# 密钥从环境变量或KMS获取，绝不硬编码
cipher = Fernet(os.environ["ENCRYPTION_KEY"])

# 加密
def encrypt_field(plaintext: str) -> str:
    return cipher.encrypt(plaintext.encode()).decode()

# 解密
def decrypt_field(ciphertext: str) -> str:
    return cipher.decrypt(ciphertext.encode()).decode()

# 使用
user.phone_encrypted = encrypt_field("13800138000")
user.id_card_encrypted = encrypt_field("110101199001011234")
```

### 需要加密的字段清单

| 字段 | 加密方式 | 说明 |
|------|---------|------|
| 密码 | bcrypt哈希（不可逆） | 永远不存明文 |
| 手机号 | AES-256加密 | 需要解密用于登录/通知 |
| 身份证号 | AES-256加密 | 需要解密用于认证 |
| 银行卡号 | AES-256加密 | 需要解密用于提现 |
| 执业证号 | AES-256加密 | 需要解密用于认证 |
| 原始病历附件 | 服务端加密(SSE) | 对象存储层面加密 |

---

## 六、文件上传安全

```python
import magic  # python-magic，通过文件头判断真实类型

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
    "application/dicom": ".dcm",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

async def upload_media(file: UploadFile, current_user = Depends(get_current_user)):
    # 1. 读取内容
    content = await file.read()
    
    # 2. 检查文件大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件不能超过50MB")
    
    # 3. 检查真实MIME类型（不信任扩展名和Content-Type）
    real_type = magic.from_buffer(content, mime=True)
    if real_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的文件类型: {real_type}")
    
    # 4. 生成安全文件名（防路径穿越）
    safe_name = f"{uuid4()}{ALLOWED_TYPES[real_type]}"
    
    # 5. 存到对象存储（不要存到Web可直接访问的目录）
    oss_path = f"cases/{current_user.id}/{safe_name}"
    oss_client.put_object(bucket, oss_path, content)
    
    # 6. 返回签名URL（不暴露真实存储路径）
    signed_url = oss_client.sign_url("GET", bucket, oss_path, expires=3600)
    
    return {"url": signed_url}
```

### 文件安全检查清单
- [ ] 不信任客户端传的文件名和Content-Type
- [ ] 用magic bytes检测真实文件类型
- [ ] 文件名用UUID重新生成
- [ ] 存储路径不在Web根目录下
- [ ] 访问通过签名URL，不直接暴露路径
- [ ] 图片文件做一次重新编码（去除EXIF中的GPS等隐私信息）

---

## 七、支付安全

### 核心原则：不信任客户端，金额从服务端取

```python
# 创建订单
async def create_order(case_id: int, current_user = Depends(get_current_user)):
    case = db.query(Case).get(case_id)
    
    # 金额从数据库读，不信任前端传的价格
    order = Transaction(
        order_no=generate_order_no(),
        buyer_id=current_user.id,
        seller_id=case.author_id,
        case_id=case.id,
        amount=case.price,            # 从数据库取
        platform_fee=case.price * Decimal("0.2"),
        seller_income=case.price * Decimal("0.8"),
    )
    db.add(order)
    db.commit()
    
    # 调用微信支付
    wx_params = create_wechat_payment(order.order_no, order.amount)
    return wx_params

# 支付回调 — 三重验证
async def wechat_notify(request: Request):
    body = await request.body()
    
    # 1. 验证微信签名（防伪造回调）
    if not verify_wechat_signature(request.headers, body):
        return PlainTextResponse("FAIL")
    
    data = parse_callback(body)
    order = db.query(Transaction).filter(Transaction.order_no == data["order_no"]).first()
    
    # 2. 幂等处理（同一回调可能来多次）
    if order.payment_status == "paid":
        return xml_response("SUCCESS")
    
    # 3. 金额一致性校验
    if Decimal(data["amount"]) != order.amount:
        logger.error(f"金额不一致: 回调{data['amount']}, 订单{order.amount}")
        return PlainTextResponse("FAIL")
    
    # 更新订单状态
    order.payment_status = "paid"
    order.payment_time = datetime.utcnow()
    db.commit()
    
    return xml_response("SUCCESS")
```

### 支付安全检查清单
- [ ] 金额永远从服务端数据库获取
- [ ] 回调接口验证支付平台签名
- [ ] 回调金额与订单金额对比
- [ ] 幂等处理防止重复到账
- [ ] 订单号全局唯一，含随机成分
- [ ] 每日对账（平台记录 vs 微信/支付宝账单）
- [ ] 退款只走原路退，不退到其他账户

---

## 八、基础设施安全

### Nginx配置

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;  # 强制HTTPS
}

server {
    listen 443 ssl http2;
    server_name example.com;
    
    # TLS配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    
    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; img-src 'self' https://oss.example.com;";
    
    # 隐藏版本号
    server_tokens off;
    
    # 请求限制
    client_max_body_size 50m;
    
    # 限流（全局）
    limit_req_zone $binary_remote_addr zone=global:10m rate=100r/s;
    limit_req zone=global burst=200 nodelay;
}
```

### Docker安全

```dockerfile
# 不用root跑应用
FROM python:3.12-slim
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 数据库安全

```sql
-- 应用账号：最小权限
CREATE USER 'app_user'@'%' IDENTIFIED BY 'strong_random_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON medical_db.* TO 'app_user'@'%';
-- 不给 DROP, ALTER, CREATE, GRANT

-- 迁移账号：仅CI/CD使用
CREATE USER 'migration_user'@'%' IDENTIFIED BY 'another_strong_password';
GRANT ALL PRIVILEGES ON medical_db.* TO 'migration_user'@'%';

-- 只读账号：给数据分析用
CREATE USER 'readonly_user'@'%' IDENTIFIED BY 'yet_another_password';
GRANT SELECT ON medical_db.* TO 'readonly_user'@'%';
```

### 云服务安全组

```
入站规则：
  80/443   → 0.0.0.0/0        (Web流量，前面有WAF)
  22       → 办公室IP/VPN IP   (SSH，不对外开放)
  5432     → 应用服务器内网IP   (PostgreSQL，不对外)
  6379     → 应用服务器内网IP   (Redis，不对外)
  9200     → 应用服务器内网IP   (Elasticsearch，不对外)

出站规则：
  全部放行（或按需限制）
```

### 密钥管理

```bash
# 绝不硬编码密钥到代码中
# 错
SECRET_KEY = "my-secret-key-123"
DB_PASSWORD = "root123"

# 对 — 环境变量
SECRET_KEY = os.environ["SECRET_KEY"]
DB_URL = os.environ["DATABASE_URL"]

# 更好 — 云KMS
# 阿里云KMS / 腾讯云SSM 管理所有密钥
```

### .gitignore 必须包含

```gitignore
.env
.env.*
*.pem
*.key
credentials.json
service-account.json
```

---

## 九、审计日志

### 需要记录的操作

| 操作 | 记录内容 | 保留时间 |
|------|---------|---------|
| 登录/登出 | 用户ID, IP, User-Agent, 成功/失败 | 1年 |
| 查看完整病例 | 用户ID, 病例ID, IP | 2年 |
| 下载附件 | 用户ID, 文件ID, IP | 2年 |
| 创建/修改/删除病例 | 用户ID, 病例ID, 变更内容 | 永久 |
| 支付/退款 | 用户ID, 订单ID, 金额 | 5年 |
| 管理员操作 | 管理员ID, 操作类型, 目标对象 | 永久 |
| 导出数据 | 用户ID, 导出范围 | 2年 |
| 修改账户信息 | 用户ID, 修改字段 | 1年 |

### 实现

```python
async def audit_log(
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    request: Request,
    details: dict = None
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        details=details,
    )
    db.add(log)
    # 异步写入，不阻塞主流程
    await db.commit()

# 使用
@app.get("/api/cases/{case_id}/full")
async def get_full_case(case_id: int, request: Request, current_user = Depends(get_current_user)):
    case = get_and_check_permission(case_id, current_user)
    await audit_log(current_user.id, "view_full_case", "case", case_id, request)
    return case
```

---

## 十、开发流程安全

### 依赖安全

```bash
# Python — 定期检查依赖漏洞
pip install pip-audit
pip-audit                    # 检查已知漏洞
pip-audit --fix              # 自动修复

# Node.js
npm audit
npm audit fix

# 在CI/CD中强制执行
# .github/workflows/security.yml
- name: Security audit
  run: pip-audit --strict     # 有漏洞则构建失败
```

### 代码静态分析

```bash
# Python安全扫描
pip install bandit
bandit -r src/               # 检测常见安全问题

# 常见检出项：
# - 硬编码密码
# - eval/exec使用
# - 不安全的随机数
# - SQL拼接
```

### pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ['-c', 'bandit.yaml']
  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets         # 检测代码中的密钥/密码
```

### 安全发布检查清单（每次上线前）

- [ ] `pip-audit` / `npm audit` 无高危漏洞
- [ ] `bandit` 扫描无高危告警
- [ ] 无硬编码密钥/密码
- [ ] 新增API都有权限校验
- [ ] 新增用户输入都有验证和清洗
- [ ] 数据库变更不影响已有数据安全
- [ ] 错误响应不泄露内部信息（堆栈、SQL、文件路径）

---

## 十一、应急响应流程

### 发现安全事件后

```
0-15分钟: 确认 → 评估影响范围 → 止血（关闭泄露通道/封禁攻击IP）
15分钟-1小时: 详细排查 → 保留证据（日志快照）→ 通知团队
1-24小时: 修复漏洞 → 评估数据泄露范围 → 通知受影响用户
24-72小时: 向监管部门报告（PIPL要求）→ 根因分析
1周内: 复盘报告 → 改进措施落地
```

### 常备工具

| 工具 | 用途 |
|------|------|
| fail2ban | 自动封禁恶意IP |
| 云WAF日志 | 分析攻击模式 |
| Sentry | 异常监控，发现异常行为 |
| 数据库审计日志 | 追溯数据访问 |
| 备份恢复 | 被加密勒索时的最后防线 |

---

## 总结：安全不是一次性的事

```
开发阶段: ORM + 输入验证 + 权限校验 + 代码审计
部署阶段: HTTPS + WAF + 安全组 + 最小权限
运行阶段: 监控告警 + 审计日志 + 定期扫描
持续改进: 依赖更新 + 渗透测试（年度）+ 应急演练
```
