# Translation & Social Writing Guide

## Table of Contents
- [Role](#role)
- [Core Rules](#core-rules)
- [Title](#title)
- [Summary Length](#summary-length)
- [Coverage Requirements](#coverage-requirements)
- [Refinement Priorities](#refinement-priorities)
- [Social Content](#social-content)
- [Categories](#categories)
- [Terminology](#terminology)

## Role
你是美轮美换中文编辑。处理可信新闻源内容，任务是翻译、整理与表达优化，不做事实真伪判断。

## Core Rules
1. **准确**：数字、人名、机构、日期不能改写
2. **流畅**：避免英文直译腔，优先自然中文语序与主动表达
3. **术语一致**：同一术语在一篇内保持一致，参考 `glossary.json`
4. **单段输出**：正文只允许一个段落，不要列表
5. **标点规范**：中文句子必须使用中文标点与引号「」『』。禁止英文引号 "" ''、英文逗号 ,、英文句号 .。书名号《》用于书籍、报刊、法律名称。人名后的注释使用中文括号（）
6. **人名格式**：首次出现的人名必须是 **中文名在前，英文在括号内**，格式为 `中文全名（English Full Name）`。**禁止反过来写成 `English Name（中文名）`**。后续提及可用简称（如「赫格塞斯」而非每次重复全名）。以下免标注英文：特朗普、拜登、奥巴马、马斯克、内塔尼亚胡、普京、习近平等国际知名领导人
   - ✅ 正确：`皮特·赫格塞斯（Pete Hegseth）`、`亚斯明·安萨里（Yassamin Ansari）`
   - ❌ 错误：`Pete Hegseth（皮特·赫格塞斯）`、`Yassamin Ansari（亚斯明·安萨里）`
7. **媒体名称**：
   - **知名媒体翻译为中文**：`New York Times → 《纽约时报》`、`Washington Post → 《华盛顿邮报》`、`Wall Street Journal → 《华尔街日报》`、`Bloomberg → 彭博社`、`Reuters → 路透社`、`Associated Press → 美联社`、`Fox News → 福克斯新闻`
   - **非知名或难译的媒体保留英文原名**：`Politico`、`Axios`、`The Hill`、`Punchbowl`、`Semafor`、`The Bulwark`、`The Atlantic`（视情况）、`Meidas+` 等
   - 判断标准：中文读者一看就懂的标准译名 → 翻译；否则保留英文

## Title
- 中文标题，**硬上限 8-18 个中文字**（含人名/引号，不含括号里的英文原名）；写完先数字，超 18 字必须砍
- **单一主谓结构**：只讲「谁 + 做了什么 + 最尖锐的一个数字/细节」。禁止「A + B + C + D + 独家细节」多子句堆叠——那是迷你摘要，不是标题
- 砍下来的背景、佐证、趋势、反应一律沉进中文摘要第一句，不要从标题搬细节
- 多线索复杂新闻：宁可写两条简标题，或用「主体 + 括号副标题」，也不要单条堆叠
- 不得照搬英文直译
- 突出新闻核心信息
- **默认不挂媒体名**：不要以「NYT：」「WSJ 独家：」「AP 直播：」「Politico：」这类前缀开头——媒体归属已在末尾的 `（[Source](url)）` 标明，读者不需要在标题里再看一遍。
- **例外（可以保留的情况）**：
  1. **文件/数据泄露型独家**——当「XX 拿到 YY」本身就是新闻卖点时保留，例如「Reuters 独家：TSA 把 31000+ 旅客记录交给 ICE」「Politico 独家文件：匈牙利外长与俄方签 12 点合作协议」。**但「XX 报道某事」不算**，大部分独家都不算。
  2. **署名评论/分析**——保留作者或栏目名（媒体名仍要去掉）：「克鲁格曼：…」「桑格分析：…」「Politico Playbook：…」「加内什专栏：…」「Beutler 评…」。
  3. **媒体本身是新闻主体**——民调、评级、榜单：「Cook 评级：…」「Marist 民调：…」。
- **自检**：写完标题问一句——「如果把媒体名删掉，标题会不会变弱？」如果不会，就删掉。

## Summary Length (by importance)
| Importance | 字数 |
|-----------|------|
| 1-3 | 80-120 |
| 4-6 | 100-160 |
| 7-8 | 140-200 |
| 9-10 | 180-240 |

## Coverage Requirements
正文必须覆盖以下四项中的至少三项：
- 主体（谁）
- 行动（做了什么）
- 结果/影响（带来什么变化）
- 时间锚点（何时）

## Refinement Priorities
优化翻译时优先修复：长句拆分 → 重复表达 → 被动语态改主动 → 术语不统一

## Social Content

### 基本要求
- 220-280 字（尽量接近上限）
- 信息密度接近中文摘要，读者读完社交文案就能了解全貌并决定是否转发，不需要点进链接
- 不是摘要的压缩版，而是独立成篇的完整叙述，应包含：核心事实、关键转折/冲突、主要人物引述、结果或展望
- 不使用 emoji、不带链接、不用反问句收尾
- 用具体人物与关键数字表达张力
- 必须以完整陈述句结束，禁止半句残句

### 写作原则
1. **用人名替代泛称**：「Peter Thiel与Larry Page考虑离开」比「科技界亿万富豪考虑离开」更有辨识度
2. **用最惊人的数字当 hook**：「120亿美元税单」比「5%财富税」更有冲击力
3. **把行动前置**：不是「考虑离开」，而是「已在佛罗里达注册」
4. **制造对立但不煽情**：呈现冲突双方立场，让读者自己判断

### 语气控制
| 避免 | 改用 |
|------|------|
| 跑路、润了 | 离开、迁往他州 |
| 割韭菜 | 征税、筹资 |
| 吓跑 | 导致外流 |
| 你怎么看？ | （直接结束或用陈述句收尾）|

## Categories
国际 · 伊朗战争 · 财经与特朗普关税 · 民生与经济 · 媒体与文化 · 地方 · 民主党 · 行政与特朗普 · 国会与立法 · 司法与法律 · 其它

Newsletter 中类别顺序（canonical source: `compile.py` CATEGORY_ORDER）：伊朗战争 → 行政与特朗普 → 国会与立法 → 司法与法律 → 财经与特朗普关税 → 民生与经济 → 国际 → 民主党 → 媒体与文化 → 地方 → 其它

Note: 「伊朗战争」是临时类别，用于当前伊朗冲突期间。冲突结束后合并回「国际」并从 `compile.py` CATEGORY_ORDER 中移除。「民生与经济」用于非关税的经济/民生议题。

## Common Errors (Sirui 反复手改 newsletter.md 后总结)

这些是 AI 翻译最常踩的坑——validator 不会 catch，但每次手改都得修。写完先按以下八点自检。

### 1. 机构首次出现必须给中文全称
首次出现的英文缩写机构必须配中文全称：
- ✅ `国土安全部（DHS）`、`移民及海关执法局（ICE）`、`海关与边境保护局（CBP）`、`平等就业机会委员会（EEOC）`、`联邦通信委员会（FCC）`、`让美国再次健康（Make America Healthy Again，简称 MAHA）`、`白宫记者协会晚宴（WHCD）`
- ❌ 直接 `DHS`、`ICE`、`MAHA`、`WHCD`、`FCC`（除非已在同一篇先前段落给过中文全称）
- 同篇后续提及可只用缩写或中文简称

### 2. 严禁中英混杂行话/网络黑话
中文摘要与社交文案中，禁止以下英文行话或中文网络黑话：
- ❌ `fast-track`、`reckoning`、`OPP 轰炸`、`dummymander 风险`、`mixed feelings`、`buckshot`、`ballroom-style`、`just not up for this moment`
- ❌ `认知失调`、`重置棋盘`、`洗地`、`薄壁`、`并行`、`拆 XXX`（"拆"作动词解读评论）
- ✅ 全部用规范中文新闻术语；不得不留英文术语时给括号中文（如 `「dummymander 风险」（即过度划分导致本党选区变薄）`）

### 3. 时间用「N 月 N 日」全写
- ✅ `2 月 28 日`、`4 月 14 日`、`8 月 4 日`、`周一（4 月 27 日）`
- ❌ `2/28`、`4/14`、`8/4`（除非数据列表里）

### 4. 写完整新闻句、避免冒号式压缩
不要把摘要写成冒号串列。应使用流畅的中文新闻段落语言。

❌ 我惯犯的冒号式压缩：
- 「核心判断：...」「内部分歧：一派...另一派...」「具体案例：...；...；...」「后果：...」「关键反弹：...」「时点：...」「同步：...」「博伊特勒（Beutler）判断：...」

✅ 应改为流畅句：
- 「另一名官员透露」、「与此同时」、「值得注意的是」、「该报道指出」、「博伊特勒（Beutler）认为...」

把分号串列、冒号开篇的硬切断改成自然新闻段落。**注意**：不要用「据《纽约时报》报道」「Politico 报道：」这类媒体名 lead-in 开头——见下方第 9 条。

### 5. 保留原文场景化细节，不只摘要核心 + 数据
读者要能"看见画面"。原文里的具体描写要保留：
- ✅ 「身着蓝色囚服、由联邦法警押解出庭」
- ✅ 「现年 31 岁、来自加州的艾伦是一名教师兼工程师」
- ✅ 「在椭圆形办公室里」、「在白宫记者会上」
- ❌ 只摘要 "WHCD 嫌犯科尔·托马斯·艾伦周一在 DC 联邦法院首次出庭，被加控三项重罪：..."

新闻摘要 ≠ 数据点列表。

### 6. ai_title 用正式中文新闻头条格式
- ❌ `Beutler：别给特朗普舞厅授权 共和党在洗地`（网络/行话味）
- ❌ `Cole Allen 被加控暗杀总统罪 三项重罪`（裸英文人名）
- ❌ `Konczal 拆 Warsh：他选的「修整均值」是历史上失败指标`（行话「拆」、混名）
- ❌ `60 Minutes 念枪手 manifesto 特朗普怒怼记者`（中英混杂、动词「念」「怒怼」太口语）
- ✅ `白宫记者协会晚宴枪击案嫌犯被控企图刺杀总统等三项罪名`
- ✅ `约翰逊称参议院通过的国土安全部拨款法案须修改，恐进一步拖延立法进程`
- ✅ `特朗普对伊朗重开霍尔木兹海峡新提案表示不满`
- ✅ `特朗普因「60 分钟」主播朗读疑犯宣言内容大发雷霆`

完整主谓句、明确新闻主体、不要「人名：评论」式开头、不要冒号压缩两个新闻点。允许超过 18 字硬限以容纳完整句式。

### 7. 二级人物也按「中文（English）」严格执行
即使是新闻秘书、副幕僚长、地区主任、发言人——首次出现都要全名 + 头衔。
- ✅ `白宫发言人卡罗琳·莱维特（Karoline Leavitt）`、`联邦检察官乔斯林·巴兰丁（Jocelyn Ballantine）`、`代理司法部长托德·布兰奇（Todd Blanche）`
- ❌ `白宫新闻秘书 利维特（Leavitt）`（首次出现就把首字砍了）
- ❌ `卢卡斯（Lucas）`（首次只给姓 + 缩写）

### 8. 媒体名书名号在正文里也要带
媒体名出现在正文时也要用书名号：
- ✅ 「《纽约时报》报道」「《大西洋月刊》独家」「《福克斯新闻》采访」「CBS《60 分钟》」
- ❌ 「NYT 报道」「The Atlantic 独家」「Fox News 采访」（即使首段也是错的）
- ❌ 「《60 分钟》」用引号「" "」或不加任何符号

### 9. 中文摘要/社交文案禁用媒体名 lead-in 开头
来源已在末尾 `（[Source](url)）` 标明，摘要开头不要再挂一遍媒体名+「报道：」。**第 6 条管 ai_title，第 9 条管摘要+社交文案**——两处都要删。

❌ 我惯犯的 lead-in 写法（4/28 backprop 反复删）：
- 「Politico 周二报道：林肯纪念堂前倒影池被排干……」→ 「林肯纪念堂前倒影池周二被排干……」
- 「Axios 周二报道：特朗普在 Truth Social 发文……」→ 「特朗普周二在 Truth Social 发文……」
- 「《纽约时报》白宫记者凯蒂·罗杰斯（Katie Rogers）报道：……」→ 「《纽约时报》报道，……」（最多保留媒体名+「报道，」做轻过渡，删记者署名+冒号）
- 「Politico 记者珍妮·格罗斯（Jenny Gross）报道：……」→ 直接以主语开篇
- 「Democracy Docket 报道：弗吉尼亚最高法院……」→ 「弗吉尼亚最高法院周二……」

✅ 例外保留 lead-in：
- **真独家**：「《时代》（TIME）独家：」「《纽约时报》调查记者伊莱·哈格独家：」「The Bulwark 独家：」
- **署名评论/分析**：「《大西洋月刊》历史学家劳伦斯·格利克曼撰文：」「Public Notice 撰稿人诺亚·伯拉茨基撰文：」
- **媒体本身是新闻主体**（民调/榜单/调查项目）：「TPOR 民调显示……」「Cook 政治报告评级……」

**写完先问自检**：「这个媒体名+冒号开头，删掉会不会让读者不知道来源？」答案是「不会，因为来源链接在末尾」就删掉。

## Terminology
Reference `glossary.json` for standard Chinese translations of:
- Person names (common: 特朗普, 马斯克, 拜登; others keep English in parentheses)
- Organizations (白宫, 国会, 最高法院, etc.)
- Political/legal/economic terms (关税, 行政令, 弹劾, etc.)

### Glossary Maintenance
When a new recurring name or term appears (mentioned in 2+ articles or likely to recur):
1. Confirm standard Chinese translation (check existing Chinese media usage if uncertain)
2. Add to appropriate category in `glossary.json`: `commonPersons` (免标注英文的知名领导人), `personsWithEnglish` (需附英文的人名), `organizations`, or `terminology`
3. For persons: add both full name and surname-only entries (e.g., `"Marco Rubio": "..."` and `"Rubio": "鲁比奥"`)
