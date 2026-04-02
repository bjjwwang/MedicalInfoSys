# 模块四：搜索与推荐服务

## 功能清单

### 4.1 基础搜索（Elasticsearch）
- 全文关键词搜索（中文分词：IK Analyzer）
- 多字段加权搜索（标题权重 > 疾病名 > 症状 > 正文）
- 筛选条件组合：疾病分类、治疗类型、疗效、价格区间、评分
- 排序：相关度 / 最新 / 最热 / 评分最高 / 价格
- 搜索建议（输入联想）
- 搜索高亮

### 4.2 语义搜索（向量检索）
- 用户用自然语言描述症状或情况
- LLM 将查询转为结构化意图 + 向量
- Milvus/Qdrant 向量相似度检索
- 结合 ES 关键词搜索做混合排序

示例查询：
> "我爸65岁，糖尿病十年，最近脚趾发黑，医院说要截肢，有没有保住的案例？"

→ 系统识别：糖尿病足/坏疽，65岁男性，寻求保肢治疗方案

### 4.3 相似病例推荐
- 基于当前查看病例，推荐相似案例
- 相似度维度：疾病类型、症状组合、患者特征、治疗方式
- "看了又看"协同过滤推荐

### 4.4 个性化推荐
- 医生端：根据科室和擅长领域推荐新案例
- 患者端：根据搜索历史和收藏推荐相关案例
- 首页推荐流：热门 + 个性化混合

### 4.5 热门与趋势
- 热搜病种排行
- 近期热门案例
- 新增稀缺病种提醒

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
业务过滤（权限/状态/付费）
  ↓
返回结果 + 推荐
```

### 索引设计
```json
{
  "case_index": {
    "title": { "type": "text", "analyzer": "ik_max_word", "boost": 3 },
    "disease_name": { "type": "text", "analyzer": "ik_smart", "boost": 2 },
    "symptoms": { "type": "text", "analyzer": "ik_max_word", "boost": 2 },
    "chief_complaint": { "type": "text", "analyzer": "ik_max_word" },
    "treatment_plan": { "type": "text", "analyzer": "ik_max_word" },
    "icd_code": { "type": "keyword" },
    "disease_category": { "type": "keyword" },
    "treatment_type": { "type": "keyword" },
    "outcome": { "type": "keyword" },
    "price": { "type": "float" },
    "quality_score": { "type": "float" },
    "published_at": { "type": "date" },
    "embedding": { "type": "dense_vector", "dims": 1024 }
  }
}
```

## 迭代计划

| 版本 | 功能 | 优先级 |
|------|------|--------|
| MVP | ES关键词搜索 + 基础筛选 | P0 |
| V1.0 | 搜索建议、高亮、排序优化 | P0 |
| V1.5 | 相似病例推荐、热门排行 | P1 |
| V2.0 | 语义搜索、个性化推荐 | P1 |
| V3.0 | 多模态搜索（上传检查报告图片搜索） | P2 |
