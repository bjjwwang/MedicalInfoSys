# 模块四：搜索与推荐服务

## 功能清单

### 4.1 基础搜索（Elasticsearch）
- 全文关键词搜索（中文分词：IK Analyzer）
- 多字段加权搜索（标题权重 > 健康状况 > 数据类型 > 正文描述）
- 筛选条件组合：健康状况分类、数据类型、治疗方式、质量评级、价格区间、交易所认证状态
- 排序：相关度 / 最新 / 最热 / 评分最高 / 价格
- 搜索建议（输入联想）
- 搜索高亮

### 4.2 语义搜索（向量检索）
- 用户用自然语言描述健康状况或数据需求
- LLM 将查询转为结构化意图 + 向量
- Milvus/Qdrant 向量相似度检索
- 结合 ES 关键词搜索做混合排序

示例查询：
> "有没有糖尿病患者长期服用二甲双胍同时配合饮食控制的完整健康数据？包含血糖监测和肠道菌群检测的优先。"

→ 系统识别：糖尿病，二甲双胍用药，饮食干预，血糖监测+肠道微生物数据，长期跟踪数据

### 4.3 相似数据资产推荐
- 基于当前查看的数据资产，推荐相似资产
- 相似度维度：健康状况类型、数据覆盖维度、数据提供者特征、治疗方式
- "看了又看"协同过滤推荐

### 4.4 交易所数据资产分类搜索
- 按交易所数据资产类目体系浏览
- 交易所认证资产专区搜索
- 已确权资产筛选
- 交易所热门资产同步展示

### 4.5 个性化推荐
- 医生/研究者端：根据研究方向和关注领域推荐新数据资产
- 药企端：根据药品管线推荐相关疾病领域数据
- 保险机构端：根据险种推荐相关健康数据
- 首页推荐流：热门 + 个性化混合

### 4.6 热门与趋势
- 热搜健康数据类型排行
- 近期热门数据资产
- 新增稀缺数据资产提醒
- 交易所热门交易趋势

## 技术实现

### 搜索流水线
```
用户查询
  ↓
查询理解（分词/纠错/同义词扩展/意图识别）
  ↓
并行检索：ES关键词 + 向量语义
  ↓
结果融合（RRF排序）
  ↓
业务过滤（权限/状态/确权状态/付费）
  ↓
返回结果 + 推荐
```

### 索引设计
```json
{
  "data_asset_index": {
    "title": { "type": "text", "analyzer": "ik_max_word", "boost": 3 },
    "health_condition": { "type": "text", "analyzer": "ik_smart", "boost": 2 },
    "data_types": { "type": "text", "analyzer": "ik_max_word", "boost": 2 },
    "data_summary": { "type": "text", "analyzer": "ik_max_word" },
    "treatment_method": { "type": "text", "analyzer": "ik_max_word" },
    "icd_code": { "type": "keyword" },
    "health_category": { "type": "keyword" },
    "data_category": { "type": "keyword" },
    "exchange_category": { "type": "keyword" },
    "exchange_certified": { "type": "boolean" },
    "verification_status": { "type": "keyword" },
    "price": { "type": "float" },
    "quality_score": { "type": "float" },
    "data_completeness": { "type": "float" },
    "data_time_span_days": { "type": "integer" },
    "published_at": { "type": "date" },
    "embedding": { "type": "dense_vector", "dims": 1024 }
  }
}
```

## 迭代计划

| 版本 | 功能 | 优先级 |
|------|------|--------|
| MVP | ES关键词搜索 + 基础筛选 | P0 |
| V1.0 | 搜索建议、高亮、排序优化、交易所分类搜索 | P0 |
| V1.5 | 相似数据资产推荐、热门排行 | P1 |
| V2.0 | 语义搜索、个性化推荐 | P1 |
| V3.0 | 多模态搜索（上传检查报告图片搜索相关数据资产） | P2 |
