# Social Platform Algorithm Guide

Based on X/Twitter 2025-2026 algorithm research. Used by `publish.py` to format threads.

## Thread Structure (optimized for algorithm)

1. **Hook（第一条）**：纯文本，120-200字，不带链接、emoji、方括号。用最有冲击力的事实或数字开头
2. **正文续接（第2-N条）**：自回复线程（self-reply），算法给予 150x 加权
3. **来源（倒数第2条）**：在回复中附上原文链接，避免首条链接的 -50~90% 惩罚
4. **订阅 CTA（最后一条）**：`关注 @theamericanroulette 获取每日美国政治新闻中文摘要`

## Algorithm Weights

| 行为 | 加权 |
|------|------|
| 自回复线程 | 150x |
| 回复（reply） | 27x |
| 引用转发（quote） | 20x |
| 收藏（bookmark） | 10x |
| 外部链接（首条） | -50~90% |

## Best Practices

- 首条必须纯文本，链接放在回复中
- 不使用 emoji 前缀——降低专业感且不提高互动
- 不使用方括号标签（如【突发】）——中文推特用户对此反感
- hook 用最惊人的数字或人名开头，不用泛称
- Twitter: 280 字符/条, Bluesky: 300 字符, Threads: 500 字符

## Posting Operations

- 发布后前 15 分钟是关键窗口——算法根据早期互动决定是否扩大分发
- 发布后主动回复评论 20-30 分钟
- 每日发布 2-4 条为宜，过多触发刷量惩罚
- 视频内容获 50%+ 加权
- 引用转发优于纯转发
