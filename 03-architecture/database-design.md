# 数据库设计

## ER 关系概览

```
User 1──N DataAsset（一个用户/数据提供方可上传多个健康数据资产）
User 1──N Transaction（一个用户可有多笔交易）
DataAsset 1──N Transaction（一个数据资产可被多次购买/消费）
DataAsset 1──N DataAssetView（一个数据资产可被多次查看，链上追踪）
DataAsset 1──N DataAssetMedia（一个数据资产可有多个附件）
DataAsset 1──N RevenueDistribution（一个数据资产可产生多次收益分配）
DataAsset 1──N ExchangeRecord（一个数据资产可有多条交易所记录）
DataAsset N──N Tag（数据资产标签，多对多）
User 1──1 DoctorCertification（医生认证信息）
User 1──N Favorite（收藏）
User 1──N BlockchainRecord（用户链上操作记录）
Transaction 1──1 ExchangeRecord（交易对应交易所记录）
DataAssetView 1──1 BlockchainRecord（查看记录对应链上存证）
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
    role            VARCHAR(20) NOT NULL DEFAULT 'patient',  -- patient/doctor/institution/data_provider/admin
    status          VARCHAR(20) NOT NULL DEFAULT 'active',   -- active/suspended/banned
    credit_score    INTEGER DEFAULT 100,         -- 信用分
    balance         DECIMAL(12,2) DEFAULT 0,     -- 账户余额
    blockchain_address VARCHAR(128),             -- 区块链账户地址（长安链/FISCO）
    blockchain_bindtime TIMESTAMPTZ,             -- 链上地址绑定时间
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_blockchain ON users(blockchain_address);
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

### data_assets - 健康数据资产表（核心）

```sql
CREATE TABLE data_assets (
    id                  BIGSERIAL PRIMARY KEY,
    provider_id         BIGINT REFERENCES users(id),  -- 数据提供方

    -- 基本信息
    title               VARCHAR(200) NOT NULL,
    summary             TEXT,                      -- AI生成的摘要
    asset_type          VARCHAR(50) NOT NULL,      -- blood_pressure/blood_sugar/medication/diet/microbiome/treatment_outcome

    -- 数据分类
    icd_code            VARCHAR(20),               -- ICD-10/11编码（如关联疾病）
    disease_category    VARCHAR(100),              -- 疾病大类
    disease_name        VARCHAR(200),              -- 疾病名称
    data_category       VARCHAR(50),               -- vital_signs/lab_results/lifestyle/genomics/clinical

    -- 数据提供者信息（脱敏后）
    subject_age_range   VARCHAR(20),               -- 年龄段：0-10/11-20/21-30...
    subject_gender      VARCHAR(10),               -- male/female/unknown
    subject_region      VARCHAR(50),               -- 省份级别

    -- 健康数据内容
    data_description    TEXT,                      -- 数据集描述
    data_schema         JSONB,                     -- 数据字段结构说明
    sample_data         JSONB,                     -- 脱敏后的样例数据
    data_volume         INTEGER,                   -- 数据记录条数
    data_time_range     TSTZRANGE,                 -- 数据采集时间范围

    -- 具体健康指标（根据 asset_type 填充）
    blood_pressure_stats JSONB,                    -- 血压统计 {avg_systolic, avg_diastolic, readings_count}
    blood_sugar_stats   JSONB,                     -- 血糖统计 {fasting_avg, postprandial_avg, hba1c}
    medications         JSONB,                     -- 用药详情 [{name, dosage, duration, outcome}]
    diet_profile        JSONB,                     -- 饮食习惯 {diet_type, calories_avg, nutrients}
    microbiome_profile  JSONB,                     -- 肠道菌群 {diversity_index, key_species, sample_count}
    treatment_outcomes  JSONB,                     -- 治疗效果 {treatment_type, baseline, result, follow_up}

    -- 资产定价与交易
    price               DECIMAL(10,2),             -- 定价（0为免费）
    visibility          VARCHAR(20) DEFAULT 'public', -- public/paid/private/exchange_only
    quality_score       DECIMAL(3,2),              -- 质量评分 0-5
    completeness_score  DECIMAL(3,2),              -- 数据完整度评分 0-5
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
    desensitization_level VARCHAR(20),             -- basic/standard/strict

    -- 确权与交易所
    blockchain_tx_hash  VARCHAR(128),              -- 确权上链交易哈希
    confirmed_at        TIMESTAMPTZ,               -- 确权时间
    exchange_asset_id   VARCHAR(128),              -- 贵阳大数据交易所资产编号
    exchange_status     VARCHAR(30) DEFAULT 'unregistered', -- unregistered/registered/listed/delisted
    exchange_listed_at  TIMESTAMPTZ,               -- 交易所上架时间

    -- 元数据
    status              VARCHAR(20) DEFAULT 'draft', -- draft/processing/confirmed/listed/archived/deleted
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 核心索引
CREATE INDEX idx_data_assets_type ON data_assets(asset_type, data_category);
CREATE INDEX idx_data_assets_disease ON data_assets(disease_category, disease_name);
CREATE INDEX idx_data_assets_icd ON data_assets(icd_code);
CREATE INDEX idx_data_assets_provider ON data_assets(provider_id);
CREATE INDEX idx_data_assets_status ON data_assets(status, review_status);
CREATE INDEX idx_data_assets_exchange ON data_assets(exchange_status, exchange_asset_id);
CREATE INDEX idx_data_assets_blockchain ON data_assets(blockchain_tx_hash);
CREATE INDEX idx_data_assets_schema ON data_assets USING GIN(data_schema);
```

### data_asset_media - 数据资产附件表

```sql
CREATE TABLE data_asset_media (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT REFERENCES data_assets(id),
    media_type      VARCHAR(20),               -- raw_data/report/chart/lab_report/other
    file_url        VARCHAR(500),              -- 加密存储地址
    thumbnail_url   VARCHAR(500),
    description     VARCHAR(200),
    is_desensitized BOOLEAN DEFAULT FALSE,
    file_size       BIGINT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### data_asset_views - 数据资产查看记录（区块链追踪）

```sql
CREATE TABLE data_asset_views (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT REFERENCES data_assets(id),
    viewer_id       BIGINT REFERENCES users(id),

    view_type       VARCHAR(20),               -- preview/full_access/download/api_access
    access_scope    JSONB,                     -- 访问了哪些字段/数据范围
    duration_sec    INTEGER,                   -- 查看时长（秒）

    -- 区块链存证
    blockchain_tx_hash VARCHAR(128),           -- 链上存证交易哈希
    blockchain_confirmed BOOLEAN DEFAULT FALSE,
    blockchain_confirmed_at TIMESTAMPTZ,

    -- 收益触发
    revenue_triggered BOOLEAN DEFAULT FALSE,   -- 是否触发了收益分配
    revenue_id      BIGINT,                    -- 关联的收益分配记录

    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_asset_views_asset ON data_asset_views(asset_id);
CREATE INDEX idx_asset_views_viewer ON data_asset_views(viewer_id);
CREATE INDEX idx_asset_views_blockchain ON data_asset_views(blockchain_tx_hash);
CREATE INDEX idx_asset_views_time ON data_asset_views(created_at);
```

### revenue_distributions - 收益分配表

```sql
CREATE TABLE revenue_distributions (
    id                  BIGSERIAL PRIMARY KEY,
    asset_id            BIGINT REFERENCES data_assets(id),
    provider_id         BIGINT REFERENCES users(id),   -- 数据提供方

    -- 触发来源
    trigger_type        VARCHAR(30),               -- view/purchase/subscription/exchange_trade
    trigger_ref_id      BIGINT,                    -- 关联的查看记录或交易ID
    trigger_ref_type    VARCHAR(30),               -- data_asset_view/transaction/exchange_record

    -- 金额分配
    total_amount        DECIMAL(12,2) NOT NULL,    -- 总收入
    provider_amount     DECIMAL(12,2) NOT NULL,    -- 数据提供方收入
    platform_amount     DECIMAL(12,2) NOT NULL,    -- 平台收入
    exchange_fee        DECIMAL(12,2) DEFAULT 0,   -- 交易所手续费

    -- 分配比例记录
    provider_ratio      DECIMAL(5,4),              -- 提供方分成比例 (如 0.7000 = 70%)
    platform_ratio      DECIMAL(5,4),              -- 平台分成比例
    exchange_ratio      DECIMAL(5,4),              -- 交易所分成比例

    -- 结算信息
    settlement_batch    VARCHAR(64),               -- 结算批次号（每周结算）
    settlement_status   VARCHAR(20) DEFAULT 'pending', -- pending/settled/failed
    settled_at          TIMESTAMPTZ,

    -- 区块链存证
    blockchain_tx_hash  VARCHAR(128),              -- 分配记录上链哈希

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_revenue_asset ON revenue_distributions(asset_id);
CREATE INDEX idx_revenue_provider ON revenue_distributions(provider_id);
CREATE INDEX idx_revenue_settlement ON revenue_distributions(settlement_batch, settlement_status);
```

### exchange_records - 交易所记录表

```sql
CREATE TABLE exchange_records (
    id                  BIGSERIAL PRIMARY KEY,
    asset_id            BIGINT REFERENCES data_assets(id),
    transaction_id      BIGINT REFERENCES transactions(id),

    -- 交易所信息
    exchange_name       VARCHAR(100) DEFAULT '贵阳大数据交易所',
    exchange_order_no   VARCHAR(128) UNIQUE,        -- 交易所订单号
    exchange_asset_id   VARCHAR(128),               -- 交易所资产编号

    -- 操作类型
    record_type         VARCHAR(30),               -- register/list/trade/delist/settle

    -- 交易详情
    buyer_exchange_id   VARCHAR(128),              -- 买方交易所账号
    amount              DECIMAL(12,2),
    exchange_fee        DECIMAL(12,2),

    -- 结算
    settlement_batch    VARCHAR(64),               -- 每周结算批次
    settlement_status   VARCHAR(20) DEFAULT 'pending', -- pending/confirmed/settled/failed
    settled_at          TIMESTAMPTZ,

    -- 状态
    status              VARCHAR(20) DEFAULT 'pending', -- pending/success/failed/cancelled
    response_data       JSONB,                     -- 交易所返回数据
    error_message       TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_exchange_asset ON exchange_records(asset_id);
CREATE INDEX idx_exchange_order ON exchange_records(exchange_order_no);
CREATE INDEX idx_exchange_settlement ON exchange_records(settlement_batch, settlement_status);
```

### blockchain_records - 区块链记录表

```sql
CREATE TABLE blockchain_records (
    id                  BIGSERIAL PRIMARY KEY,

    -- 关联信息
    user_id             BIGINT REFERENCES users(id),
    ref_type            VARCHAR(30),               -- data_asset/view/revenue/exchange
    ref_id              BIGINT,                    -- 关联记录ID

    -- 链上信息
    chain_type          VARCHAR(30) DEFAULT 'chainmaker', -- chainmaker/fisco_bcos
    tx_hash             VARCHAR(128) UNIQUE,        -- 交易哈希
    block_number        BIGINT,                    -- 区块号
    block_timestamp     TIMESTAMPTZ,               -- 区块时间戳
    contract_name       VARCHAR(100),              -- 合约名称
    contract_method     VARCHAR(100),              -- 合约方法

    -- 操作详情
    action              VARCHAR(50),               -- confirm_rights/record_view/distribute_revenue/register_asset
    action_data         JSONB,                     -- 上链数据摘要

    -- 验证
    verified            BOOLEAN DEFAULT FALSE,     -- 链上验证通过
    verified_at         TIMESTAMPTZ,

    -- 状态
    status              VARCHAR(20) DEFAULT 'pending', -- pending/confirmed/failed
    error_message       TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blockchain_tx ON blockchain_records(tx_hash);
CREATE INDEX idx_blockchain_ref ON blockchain_records(ref_type, ref_id);
CREATE INDEX idx_blockchain_user ON blockchain_records(user_id);
CREATE INDEX idx_blockchain_block ON blockchain_records(block_number);
```

### transactions - 交易表

```sql
CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    order_no        VARCHAR(64) UNIQUE,        -- 平台订单号
    buyer_id        BIGINT REFERENCES users(id),
    seller_id       BIGINT REFERENCES users(id),
    asset_id        BIGINT REFERENCES data_assets(id),

    amount          DECIMAL(10,2) NOT NULL,    -- 交易金额
    platform_fee    DECIMAL(10,2),             -- 平台手续费
    exchange_fee    DECIMAL(10,2) DEFAULT 0,   -- 交易所手续费
    seller_income   DECIMAL(10,2),             -- 卖方收入

    -- 交易所对接
    exchange_order_no VARCHAR(128),             -- 交易所订单号
    settlement_batch  VARCHAR(64),             -- 结算批次号（每周结算）
    settlement_status VARCHAR(20) DEFAULT 'pending', -- pending/settled/failed

    payment_method  VARCHAR(20),               -- wechat/alipay/balance/exchange
    payment_status  VARCHAR(20) DEFAULT 'pending', -- pending/paid/refunded/failed
    payment_time    TIMESTAMPTZ,

    -- 区块链存证
    blockchain_tx_hash VARCHAR(128),            -- 交易上链哈希

    -- 退款
    refund_status   VARCHAR(20),               -- requested/approved/rejected/completed
    refund_reason   TEXT,
    refund_time     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_buyer ON transactions(buyer_id);
CREATE INDEX idx_transactions_seller ON transactions(seller_id);
CREATE INDEX idx_transactions_asset ON transactions(asset_id);
CREATE INDEX idx_transactions_exchange ON transactions(exchange_order_no);
CREATE INDEX idx_transactions_settlement ON transactions(settlement_batch, settlement_status);
```

### case_reviews - 数据资产评审/评价表

```sql
CREATE TABLE case_reviews (
    id              BIGSERIAL PRIMARY KEY,
    asset_id        BIGINT REFERENCES data_assets(id),
    reviewer_id     BIGINT REFERENCES users(id),
    review_type     VARCHAR(20),               -- peer_review(同行评审) / buyer_review(购买评价) / quality_audit(质量审计)

    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    accuracy_score  SMALLINT,                  -- 准确性评分 1-5
    usefulness_score SMALLINT,                 -- 实用性评分 1-5
    completeness_score SMALLINT,               -- 完整度评分 1-5
    content         TEXT,

    is_anonymous    BOOLEAN DEFAULT FALSE,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### tags & data_asset_tags - 标签系统

```sql
CREATE TABLE tags (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE,
    category    VARCHAR(30),                   -- disease/data_type/health_indicator/body_system
    usage_count INTEGER DEFAULT 0
);

CREATE TABLE data_asset_tags (
    asset_id    BIGINT REFERENCES data_assets(id),
    tag_id      BIGINT REFERENCES tags(id),
    PRIMARY KEY (asset_id, tag_id)
);
```

### favorites - 收藏表

```sql
CREATE TABLE favorites (
    user_id     BIGINT REFERENCES users(id),
    asset_id    BIGINT REFERENCES data_assets(id),
    folder      VARCHAR(50) DEFAULT 'default',  -- 收藏夹分类
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, asset_id)
);
```

### audit_logs - 审计日志表

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT,
    action          VARCHAR(50),               -- view_asset/purchase/export/search/desensitize/
                                               -- confirm_rights/register_exchange/settle/
                                               -- blockchain_write/revenue_distribute/...
    resource_type   VARCHAR(30),               -- data_asset/transaction/exchange_record/blockchain_record/revenue
    resource_id     BIGINT,
    ip_address      INET,
    user_agent      TEXT,
    details         JSONB,                     -- 操作详情，含链上哈希等
    blockchain_tx_hash VARCHAR(128),           -- 如操作上链，记录交易哈希
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 按时间分区，方便清理历史数据
CREATE INDEX idx_audit_logs_time ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_blockchain ON audit_logs(blockchain_tx_hash);
```

## 数据安全设计

### 加密策略
- 手机号、身份证号等 PII 字段：AES-256 加密存储
- 密码：bcrypt/argon2 哈希
- 健康数据文件：服务端加密 (SSE)
- 传输层：全站 TLS 1.3
- 区块链私钥：HSM/KMS 托管，绝不落盘明文

### 访问控制
- 数据库账号最小权限原则
- 应用层 RBAC 权限控制（含 data_provider 角色）
- 敏感字段查询需审计日志
- 定期审查访问权限
- 数据资产访问通过区块链记录，不可篡改

### 区块链安全
- 链上仅存储数据哈希和元数据摘要，原始数据不上链
- 智能合约经第三方安全审计后部署
- 链上私钥通过 KMS 管理，支持多签机制
- 区块链节点间通信使用 TLS 加密

### 数据资产合规
- 脱敏流水线严格执行《个人信息保护法》要求
- 数据资产登记遵循贵阳大数据交易所规范
- 数据确权存证满足《数据安全法》溯源要求
- 每周结算记录完整可审计
