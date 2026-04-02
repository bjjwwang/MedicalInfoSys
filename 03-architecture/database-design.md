# 数据库设计

## ER 关系概览

```
User 1──N Case（一个用户可上传多个病例）
User 1──N Transaction（一个用户可有多笔交易）
Case 1──N Transaction（一个病例可被多次购买）
Case 1──N CaseReview（一个病例可有多条评审）
Case 1──N CaseMedia（一个病例可有多个附件）
User 1──1 DoctorCertification（医生认证信息）
User 1──N Favorite（收藏）
Case N──N Tag（病例标签，多对多）
```

## 核心表设计

### users - 用户表

```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    phone           VARCHAR(20) UNIQUE,          -- 手机号（加密存储）
    email           VARCHAR(100) UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    nickname        VARCHAR(50),
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL DEFAULT 'patient',  -- patient/doctor/institution/admin
    status          VARCHAR(20) NOT NULL DEFAULT 'active',   -- active/suspended/banned
    credit_score    INTEGER DEFAULT 100,         -- 信用分
    balance         DECIMAL(12,2) DEFAULT 0,     -- 账户余额
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### doctor_certifications - 医生认证表

```sql
CREATE TABLE doctor_certifications (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT REFERENCES users(id),
    real_name           VARCHAR(50),              -- 加密存储
    id_card_number      VARCHAR(50),              -- 加密存储
    hospital            VARCHAR(200),
    department          VARCHAR(100),
    title               VARCHAR(50),              -- 职称：主任医师/副主任/主治/住院
    license_number      VARCHAR(100),             -- 执业证号
    license_image_url   VARCHAR(500),             -- 执业证照片
    specialty           VARCHAR(200),             -- 擅长领域
    verification_status VARCHAR(20) DEFAULT 'pending', -- pending/approved/rejected
    verified_at         TIMESTAMPTZ,
    verified_by         BIGINT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### cases - 病例表（核心）

```sql
CREATE TABLE cases (
    id                  BIGSERIAL PRIMARY KEY,
    author_id           BIGINT REFERENCES users(id),
    
    -- 基本信息
    title               VARCHAR(200) NOT NULL,
    summary             TEXT,                      -- AI生成的摘要
    
    -- 疾病分类
    icd_code            VARCHAR(20),               -- ICD-10/11编码
    disease_category    VARCHAR(100),              -- 疾病大类
    disease_name        VARCHAR(200),              -- 疾病名称
    disease_rarity      VARCHAR(20),               -- common/uncommon/rare/ultra_rare
    
    -- 患者信息（脱敏后）
    patient_age_range   VARCHAR(20),               -- 年龄段：0-10/11-20/21-30...
    patient_gender      VARCHAR(10),               -- male/female/unknown
    patient_region      VARCHAR(50),               -- 省份级别
    
    -- 临床信息
    chief_complaint     TEXT,                      -- 主诉
    symptoms            JSONB,                     -- 症状列表 [{name, severity, duration}]
    medical_history     TEXT,                      -- 既往史
    examination         TEXT,                      -- 检查结果
    diagnosis_process   TEXT,                      -- 诊断过程
    
    -- 治疗信息
    treatment_type      VARCHAR(50),               -- medication/surgery/tcm/combined/other
    treatment_plan      TEXT,                      -- 治疗方案（付费内容核心）
    medications         JSONB,                     -- 用药详情 [{name, dosage, duration}]
    surgical_details    TEXT,                       -- 手术详情
    tcm_details         TEXT,                       -- 中医方案
    
    -- 疗效
    outcome             VARCHAR(20),               -- cured/improved/stable/ineffective
    outcome_description TEXT,                      -- 疗效描述
    follow_up_period    VARCHAR(50),               -- 随访时长
    follow_up_notes     TEXT,                      -- 随访记录
    
    -- 平台信息
    price               DECIMAL(10,2),             -- 定价（0为免费）
    visibility          VARCHAR(20) DEFAULT 'public', -- public/paid/private
    quality_score       DECIMAL(3,2),              -- 质量评分 0-5
    view_count          INTEGER DEFAULT 0,
    purchase_count      INTEGER DEFAULT 0,
    
    -- 审核
    review_status       VARCHAR(20) DEFAULT 'pending', -- pending/approved/rejected/revision
    review_notes        TEXT,
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         BIGINT,
    
    -- 脱敏
    desensitized        BOOLEAN DEFAULT FALSE,
    desensitization_log JSONB,                     -- 脱敏操作记录
    
    -- 元数据
    status              VARCHAR(20) DEFAULT 'draft', -- draft/published/archived/deleted
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 核心索引
CREATE INDEX idx_cases_disease ON cases(disease_category, disease_name);
CREATE INDEX idx_cases_icd ON cases(icd_code);
CREATE INDEX idx_cases_author ON cases(author_id);
CREATE INDEX idx_cases_status ON cases(status, review_status);
CREATE INDEX idx_cases_symptoms ON cases USING GIN(symptoms);
```

### case_media - 病例附件表

```sql
CREATE TABLE case_media (
    id              BIGSERIAL PRIMARY KEY,
    case_id         BIGINT REFERENCES cases(id),
    media_type      VARCHAR(20),               -- image/ct/mri/xray/lab_report/pathology/other
    file_url        VARCHAR(500),              -- 加密存储地址
    thumbnail_url   VARCHAR(500),
    description     VARCHAR(200),
    is_desensitized BOOLEAN DEFAULT FALSE,
    file_size       BIGINT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### transactions - 交易表

```sql
CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    order_no        VARCHAR(64) UNIQUE,        -- 订单号
    buyer_id        BIGINT REFERENCES users(id),
    seller_id       BIGINT REFERENCES users(id),
    case_id         BIGINT REFERENCES cases(id),
    
    amount          DECIMAL(10,2) NOT NULL,    -- 交易金额
    platform_fee    DECIMAL(10,2),             -- 平台手续费
    seller_income   DECIMAL(10,2),             -- 卖方收入
    
    payment_method  VARCHAR(20),               -- wechat/alipay/balance
    payment_status  VARCHAR(20) DEFAULT 'pending', -- pending/paid/refunded/failed
    payment_time    TIMESTAMPTZ,
    
    -- 退款
    refund_status   VARCHAR(20),               -- requested/approved/rejected/completed
    refund_reason   TEXT,
    refund_time     TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_buyer ON transactions(buyer_id);
CREATE INDEX idx_transactions_seller ON transactions(seller_id);
CREATE INDEX idx_transactions_case ON transactions(case_id);
```

### case_reviews - 病例评审/评价表

```sql
CREATE TABLE case_reviews (
    id              BIGSERIAL PRIMARY KEY,
    case_id         BIGINT REFERENCES cases(id),
    reviewer_id     BIGINT REFERENCES users(id),
    review_type     VARCHAR(20),               -- peer_review(同行评审) / buyer_review(购买评价)
    
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    accuracy_score  SMALLINT,                  -- 准确性评分 1-5
    usefulness_score SMALLINT,                 -- 实用性评分 1-5
    content         TEXT,
    
    is_anonymous    BOOLEAN DEFAULT FALSE,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### tags & case_tags - 标签系统

```sql
CREATE TABLE tags (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE,
    category    VARCHAR(30),                   -- disease/symptom/treatment/body_part
    usage_count INTEGER DEFAULT 0
);

CREATE TABLE case_tags (
    case_id     BIGINT REFERENCES cases(id),
    tag_id      BIGINT REFERENCES tags(id),
    PRIMARY KEY (case_id, tag_id)
);
```

### favorites - 收藏表

```sql
CREATE TABLE favorites (
    user_id     BIGINT REFERENCES users(id),
    case_id     BIGINT REFERENCES cases(id),
    folder      VARCHAR(50) DEFAULT 'default',  -- 收藏夹分类
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, case_id)
);
```

### audit_logs - 审计日志表

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT,
    action          VARCHAR(50),               -- view_case/purchase/export/search/...
    resource_type   VARCHAR(30),
    resource_id     BIGINT,
    ip_address      INET,
    user_agent      TEXT,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 按时间分区，方便清理历史数据
CREATE INDEX idx_audit_logs_time ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
```

## 数据安全设计

### 加密策略
- 手机号、身份证号等 PII 字段：AES-256 加密存储
- 密码：bcrypt/argon2 哈希
- 影像文件：服务端加密 (SSE)
- 传输层：全站 TLS 1.3

### 访问控制
- 数据库账号最小权限原则
- 应用层 RBAC 权限控制
- 敏感字段查询需审计日志
- 定期审查访问权限
