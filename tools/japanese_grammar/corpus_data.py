"""Cleaned and Ruby/Romaji-annotated Japanese grammar curriculum corpus.

Derived strictly from RemNote root "语法" (`Pu9aItzklny3OlLlK`) with all
RemNote structural/chat artifacts removed and typographical errors corrected.
All flashcards use Schema-2 unified atomic `fill_blank` (`grading: "exact"`).
"""

from __future__ import annotations

COURSE_ID = 'japanese-grammar-core'
COURSE_TITLE = '日本語文法 · 核心语法掌握'
SUBJECT_ID = 'japanese'
SOURCE_REM_ID = 'Pu9aItzklny3OlLlK'
B1, B2, B3, B4 = '{{blank:b1}}', '{{blank:b2}}', '{{blank:b3}}', '{{blank:b4}}'

GRAPH_SPEC = {
    'schema_version': 3,
    'subject_id': SUBJECT_ID,
    'course_id': COURSE_ID,
    'title': COURSE_TITLE,
    'nodes': [
        {
            'topic_id': 'jp01-copula-particles',
            'title': '1. 判断句与基本助词：だ・の・な 与 は・が',
            'member': True,
        },
        {
            'topic_id': 'jp02-spo-object-particles',
            'title': '2. 主谓宾句型、核心格助词与自他动词',
            'member': True,
        },
        {
            'topic_id': 'jp03-adjectives-and-mo',
            'title': '3. 形容词活用与包含助词「も」',
            'member': True,
        },
        {
            'topic_id': 'jp04-verbs-existence-past',
            'title': '4. 动词分类、存在句（ある・いる）与过去时',
            'member': True,
        },
        {
            'topic_id': 'jp05-negation-system',
            'title': '5. 否定型完整体系：名词・形容词・动词',
            'member': True,
        },
        {
            'topic_id': 'jp06-modifiers-and-listing',
            'title': '6. 连体修饰语序与并列列举助词',
            'member': True,
        },
    ],
    'edges': [
        {
            'from': 'jp01-copula-particles',
            'to': 'jp02-spo-object-particles',
            'type': 'prerequisite',
            'reason': '掌握主题「は」与主格「が」及定语「の・な」规则，才能分辨「SはOをV」「SがOをV」及「の」避开双重「を」。',
        },
        {
            'from': 'jp02-spo-object-particles',
            'to': 'jp03-adjectives-and-mo',
            'type': 'prerequisite',
            'reason': '助词「も」既直接覆盖「は/が/を」，又需后置叠加于「に/へ/から/で」之上；な形容词活用复用「だ/の/な」。',
        },
        {
            'from': 'jp02-spo-object-particles',
            'to': 'jp04-verbs-existence-past',
            'type': 'prerequisite',
            'reason': '动词分类与存在句「ある・いる」直接承接格助词「を/が/に」与自他动词对立体系。',
        },
        {
            'from': 'jp03-adjectives-and-mo',
            'to': 'jp05-negation-system',
            'type': 'prerequisite',
            'reason': '完整否定体系涵盖い形容词与な形容词的活用切换。',
        },
        {
            'from': 'jp04-verbs-existence-past',
            'to': 'jp05-negation-system',
            'type': 'prerequisite',
            'reason': '动词「ない形」及「ある → ない」「来る → こない」等不规则否定以动词三大分类为基础。',
        },
        {
            'from': 'jp04-verbs-existence-past',
            'to': 'jp06-modifiers-and-listing',
            'type': 'prerequisite',
            'reason': '连体修饰小句需要纯熟运用动词辞书形与过去简体「〜た」。',
        },
        {
            'from': 'jp05-negation-system',
            'to': 'jp06-modifiers-and-listing',
            'type': 'prerequisite',
            'reason': '状态表达小句与动词小句修饰名词时需自由运用「〜じゃない」「〜なかった」等否定形。',
        },
    ],
}


def r(surface: str, kana: str) -> str:
    """Annotate kanji/surface text with ruby furigana."""
    return f'<ruby>{surface}<rp>(</rp><rt>{kana}</rt><rp>)</rp></ruby>'


def term(ja_html: str, romaji: str, zh: str = '') -> str:
    """Render an inline annotated Japanese term with romaji."""
    zh_part = f'（{zh}）' if zh else ''
    return f'<span class="jp-term">{ja_html}<span class="jp-romaji"> {romaji}</span></span>{zh_part}'


def ex(ja_html: str, romaji: str, zh: str, note: str = '') -> str:
    """Render a structured Japanese example block."""
    note_html = f'<span class="jp-note">—— {note}</span>' if note else ''
    return (
        '<div class="jp-ex">'
        f'<div class="jp-ja">{ja_html}</div>'
        f'<div class="jp-romaji">{romaji}</div>'
        f'<div class="jp-zh">{zh}{note_html}</div>'
        '</div>'
    )


def bad_ex(ja_text: str, note: str) -> str:
    """Render an ungrammatical counterexample."""
    return f'<div class="jp-bad-ex"><span class="jp-bad">× {ja_text}</span><span class="jp-note">（{note}）</span></div>'


def tbl(headers: list[str], rows: list[list[str]]) -> str:
    """Render a clean HTML comparison/conjugation table."""
    ths = ''.join(f'<th>{h}</th>' for h in headers)
    trs = ''.join(
        '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
        for row in rows
    )
    return f'<table class="jp-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'


def tip(title: str, body: str) -> str:
    """Render a key takeaway callout."""
    return f'<div class="jp-tip"><strong>{title}：</strong>{body}</div>'


def blank_spec(bid: str, label: str, answers: list[str]) -> dict:
    """Create a validated fill_blank blank definition."""
    return {'id': bid, 'label': label, 'answers': answers}


def fc(
    card_id: str,
    title: str,
    point_ids: list[str],
    prompt_zh: str,
    question_ja: str,
    html_ja: str,
    romaji_hint: str,
    zh_gloss: str,
    blanks: list[dict],
    explanation_html: str,
    constraints: str = '请填写日语假名或汉字（系统自动忽略全半角空白）。',
    learning_phases: list[str] | None = None,
) -> dict:
    """Construct a Schema-2 fill_blank flashcard spec."""
    phases = learning_phases or (['learn', 'review'] if len(point_ids) == 1 else ['review'])
    question = f'{prompt_zh}\n{question_ja}（{zh_gloss}）'
    html = (
        '<div class="jp-card">'
        f'<p class="jp-prompt">{prompt_zh}</p>'
        f'<p class="jp-ja">{html_ja}</p>'
        f'<p class="jp-romaji">{romaji_hint}</p>'
        f'<p class="jp-zh">{zh_gloss}</p>'
        '</div>'
    )
    ref_answer = '；'.join(b['answers'][0] for b in blanks)
    return {
        'id': card_id,
        'title': title,
        'point_ids': point_ids,
        'learning_phases': phases,
        'answer_type': 'fill_blank',
        'constraints': constraints,
        'question': question,
        'html': html,
        'reference_answer': ref_answer,
        'explanation_html': explanation_html,
        'interaction': {
            'version': 1,
            'type': 'fill_blank',
            'grading': 'exact',
            'blanks': blanks,
        },
    }


def _expl(answer_ja: str, romaji: str, rule_zh: str) -> str:
    """Format uniform flashcard explanation HTML."""
    return (
        '<div class="jp-expl">'
        f'<div class="jp-ja">{answer_ja}</div>'
        f'<div class="jp-romaji">{romaji}</div>'
        f'<p>{rule_zh}</p>'
        '</div>'
    )


TOPICS = [
    # =========================================================================
    # Topic 1: jp01-copula-particles
    # =========================================================================
    {
        'id': 'jp01-copula-particles',
        'title': '1. 判断句与基本助词：だ・の・な 与 は・が',
        'sections': [
            {
                'id': 'sec-jp01-copula',
                'title': '一、断定词「だ」与定语修饰「の・な」',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp01-wa-ga',
                'title': '二、助词「は」与「が」的本质区别与对比',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp01-copula',
                'section_id': 'sec-jp01-copula',
                'title': '断定词「だ」的句末谓语职能与直接定语禁区',
                'html': (
                    '<h3>断定词「だ」作句末谓语与「*だ＋名词」禁区</h3>'
                    '<p>在日语判断句与状态句中，断定词「だ」的核心职责是置于<strong>句末作谓语/表语</strong>，用来进行断定或说明主语处于某种状态；但若要作<strong>定语（直接修饰后面的名词）</strong>，则<strong>绝对禁止</strong>直接接「だ」。</p>'
                    '<h4>1. 作表语/谓语：完全可以（句末断定与状态说明）</h4>'
                    '<p>当「名词 / な形容词 + だ」放在句末时，它充当全句谓语，对主题进行断定或性状说明：</p>'
                    + ex(f"{r('彼', 'かれ')}は{r('学生', 'がくせい')}だ。", 'kare wa gakusei da.', '他是学生。', '名词 + だ')
                    + ex(f"この{r('部屋', 'へや')}は{r('静', 'しず')}かだ。", 'kono heya wa shizuka da.', '这个房间很安静。', 'な形容词 + だ')
                    + '<h4>2. 作定语（直接修饰名词）时的正确替换规则</h4>'
                    '<p>千万不能直接用「だ」去连接后面的名词，否则语法错误。直接修饰名词时，必须把「だ」替换掉：</p>'
                    + bad_ex('学生だ田中さん / 静かだ部屋', '不可直接以「だ」作定语修饰名词')
                    + '<ul>'
                    '<li><strong>名词作定语（名词变「の」）</strong>：结构为 <code>名词 + の + 名词</code>。'
                    + ex(f"{r('学生', 'がくせい')}の{r('田中', 'たなか')}さん", 'gakusei no tanaka-san', '学生身份的田中先生')
                    + ex(f"{r('日本人', 'にほんじん')}の{r('友達', 'ともだち')}", 'nihonjin no tomodachi', '日本朋友')
                    + bad_ex('学生だ田中さん', '名词直接修饰名词不可用「だ」')
                    + '</li>'
                    '<li><strong>な形容词作定语（な形容词变「な」）</strong>：结构为 <code>な形容词 + な + 名词</code>（这正是它被称为「な形容词 / 形容动词」的原因）。'
                    + ex(f"{r('静', 'しず')}かな{r('部屋', 'へや')}", 'shizuka na heya', '安静的房间')
                    + ex(f"{r('有名', 'ゆうめい')}なお{r('店', 'みせ')}", 'yūmei na omise', '有名的店')
                    + bad_ex('静かだ部屋', 'な形容词直接修饰名词不可用「だ」')
                    + '</li>'
                    '</ul>'
                    '<h4>引用与同位小句中的「だ」例外</h4>'
                    '<p>只有当修饰成分里包含<strong>直接引用、推测或「〜という」同位完整小句</strong>时，「だ」才作为从句内部的句末成分被保留下来：</p>'
                    + ex(f"「{r('学生', 'がくせい')}だ」と{r('言', 'い')}った{r('人', 'ひと')}", '"gakusei da" to itta hito', '说了“是学生”的那个人', '「だ」属于被直接引用的说话内容')
                    + ex(f"{r('高校生', 'こうこうせい')}だという{r('理由', 'りゆう')}", 'kōkōsei da to iu riyū', '所谓的“是高中生”这个理由', '属于「〜という」同位小句')
                    + tip('直接定语口诀', '只要是直接修饰名词，<strong>名词用「の」，な形容词用「な」</strong>，绝不用「だ」。')
                ),
            },
            {
                'id': 'intro-jp01-wa-ga',
                'section_id': 'sec-jp01-wa-ga',
                'title': '主题助词「は」与标识助词「が」的四大维度对比',
                'html': (
                    '<h3>一、为什么「は」和「が」不是词义上的“是”</h3>'
                    '<p>许多入门教材把 <code>A は B です</code> 简译成“A [是] B”，容易让人误以为「は」或「が」等于“是”。实际上，<strong>真正的“是”是句末状态断定词「です / だ」</strong>；「は」（读作 <em>wa</em>）和「が」（读作 <em>ga</em>）则是把名词扣在谓语上的<strong>语法扣环（助词）</strong>。在动词句中压根没有“是”：</p>'
                    + ex(f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さんが{r('来', 'き')}ました。", 'kyō, miyamoto-san ga kimashita.', '今天，宫本女士来了。', '谓语是动词「来ました」，「が」仅标记动作执行者')
                    + '<p><strong>书面必须、口语可省</strong>：日语名词本身无词形变化，标准语法必须紧跟助词（如「が」标主语、「を」标宾语、「に」标目标或时间）来确定角色；但在日常快速口语且语境明确时，「が」「を」常可自然省略（如 ' + term(f"{r('千葉', 'ちば')}さん、{r('来', 'き')}ましたか？", 'chiba-san, kimashita ka?', '千叶先生来了吗？') + '）。</p>'
                    '<h3>二、核心定位与四大辨析维度</h3>'
                    '<p>根据《Japanese Grammar Guide》与《Making Sense of Japanese Grammar》，「は」是<strong>主题助词（Topic Particle）</strong>，「が」是<strong>标识助词（Identifier Particle）</strong>，两者的本质差异体现在以下四个核心维度：</p>'
                    + tbl(
                        ['对比维度', '主题助词「は」（wa）', '标识助词「が」（ga）'],
                        [
                            ['核心定位', '相当于 “Speaking of...（关于/至于……）”', '精确标识动作执行者或符合条件的对象'],
                            ['注意力焦点', '<strong>看后面</strong>：聚焦「は」后面的谓语说明', '<strong>看前面</strong>：聚焦「が」前面的名词本身'],
                            ['典型例句', ex(f"{r('私', 'わたし')}は{r('学生', 'がくせい')}です。", 'watashi wa gakusei desu.', '关于我，身份是学生。'), ex(f"{r('私', 'わたし')}が{r('学生', 'がくせい')}です。", 'watashi ga gakusei desu.', '<strong>正是我</strong>才是那个学生。')],
                            ['疑问词规则', '不能在疑问词作主语时使用（<code>*誰は学生？</code> 错）', '疑问词（誰・何・どれ）作主语<strong>只能用「が」</strong>，回答主语也保持「が」'],
                            ['信息演变模型', '<strong>进入轨道的卫星</strong>：上文已提及的已知背景', '<strong>刚升空的火箭</strong>：首次引入的新人物/新信息'],
                            ['排他与对比', '在特定语境中带有对比排他语义（周一是休息日，言外之意其他日不休）', '仅作客观主语标识，无此对比主题功能'],
                        ],
                    )
                    + '<h4>疑问词搭配与回答主语铁律</h4>'
                    '<p>疑问词（<code>誰・何・どれ</code>）代表未知新信息，逻辑上无法作为“已知主题”，因此<strong>疑问词作主语只能用「が」不能用「は」</strong>；相对地，当主语是已知待寻对象而疑问词在谓语时，用「は」：</p>'
                    + ex(f"{r('誰', 'だれ')}が{r('学生', 'がくせい')}？ — ジムが{r('学生', 'がくせい')}。", 'dare ga gakusei? — jimu ga gakusei.', '谁是学生？——吉姆是那个学生。', '问答主语都保持「が」')
                    + bad_ex('誰は学生？', '疑问词作主语绝不可用「は」')
                    + ex(f"{r('学生', 'がくせい')}は{r('誰', 'だれ')}？", 'gakusei wa dare?', '关于学生，是谁呢？', '已知对象「学生」作主题用「は」')
                    + ex(f"お{r('名前', 'なまえ')}は{r('何', 'なん')}ですか。", 'onamae wa nan desu ka.', '请问您的名字是什么？')
                    + '<h4>火箭与卫星模型及排他对比</h4>'
                    + ex(f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さんが{r('来', 'き')}ました。{r('宮本', 'みやもと')}さんは{r('日本語', 'にほんご')}の{r('先生', 'せんせい')}です。", 'kyō, miyamoto-san ga kimashita. miyamoto-san wa nihongo no sensei desu.', '今天宫本女士来了（新信息火箭→が）。宫本女士是日语老师（已知背景卫星→は）。')
                    + ex(f"{r('月曜日', 'げつようび')}は{r('休', 'やす')}みです。", 'getsuyōbi wa yasumi desu.', '周一是休息日（暗指其他日子不休息）。', '对比排他用法')
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp01-pred-da',
                'introduction_id': 'intro-jp01-copula',
                'title': '断定词「だ」作句末谓语与「の・な」定语替换',
                'html': '<p>「名词 / な形容词 + だ」只作句末谓语断定；直接修饰名词时，名词变「の」，な形容词变「な」。</p>',
                'anchor_quotes': ['断定词「だ」作句末谓语与「*だ＋名词」禁区'],
                'points': [
                    {'id': 'p-jp01-da-pred', 'text': '「名词 / な形容词 + だ」用于句末作谓语断定，直接修饰名词时禁止用「だ」。'},
                    {'id': 'p-jp01-noun-no', 'text': '名词直接修饰名词须将「だ」换为「の」（名词 + の + 名词）。'},
                    {'id': 'p-jp01-na-attr', 'text': 'な形容词直接修饰名词须将「だ」换为「な」（な形容词 + な + 名词）。'},
                ],
            },
            {
                'id': 'chunk-jp01-quote-exception',
                'introduction_id': 'intro-jp01-copula',
                'title': '引用与同位小句中的「だ」例外',
                'html': '<p>直接引用（<code>「学生だ」と言った人</code>）或同位说明（<code>高校生だという理由</code>）中保留「だ」。</p>',
                'anchor_quotes': ['引用与同位小句中的「だ」例外'],
                'points': [
                    {'id': 'p-jp01-da-quote', 'text': '只有包含直接引用或「〜という」完整同位小句时，「だ」才保留在修饰成分内部。'},
                ],
            },
            {
                'id': 'chunk-jp01-wa-ga-focus',
                'introduction_id': 'intro-jp01-wa-ga',
                'title': '「は」「が」非“是”本质与焦点方向',
                'html': '<p>「は」「が」是语法扣环而非“是”；「は」焦点在后（说明），「が」焦点在前（指认）。</p>',
                'anchor_quotes': ['一、为什么「は」和「が」不是词义上的“是”', '二、核心定位与四大辨析维度'],
                'points': [
                    {'id': 'p-jp01-not-copula', 'text': '「は」「が」不是词义上的“是”（“是”由句末「だ/です」表达）；书面须标助词，口语明确时「が/を」可省略。'},
                    {'id': 'p-jp01-wa-focus', 'text': '「は」（wa）设定讨论主题，听众注意力落在后面的谓语说明（“关于A，情况是B”）。'},
                    {'id': 'p-jp01-ga-focus', 'text': '「が」（ga）精确标识主语并在候选项中指认对象，焦点在前面的名词（“正是A”）。'},
                ],
            },
            {
                'id': 'chunk-jp01-wh-info-flow',
                'introduction_id': 'intro-jp01-wa-ga',
                'title': '疑问词「が」铁律、火箭与卫星模型及对比「は」',
                'html': '<p>疑问词作主语及回答主语用「が」；新信息「が」（火箭）→ 已知背景「は」（卫星）；「は」可表排他对比。</p>',
                'anchor_quotes': ['疑问词搭配与回答主语铁律', '火箭与卫星模型及排他对比'],
                'points': [
                    {'id': 'p-jp01-wh-ga', 'text': '疑问词作主语及回答主语只能用「が」（誰が学生？／ジムが学生）；已知对象被问时用「は」（学生は誰？）。'},
                    {'id': 'p-jp01-rocket-satellite', 'text': '新人物/信息首次出现用「が」（火箭），上文已知后转用「は」（卫星）；「は」还可用于对比排他（月曜日は休みです）。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp01-01', '句末名词断定「だ」', ['p-jp01-da-pred'],
                '请填入句末简体断定词完成判断句：',
                '彼は学生{{blank:b1}}。',
                f"{r('彼', 'かれ')}は{r('学生', 'がくせい')}{B1}。",
                'kare wa gakusei [ ? ]',
                '他是学生。（简体）',
                [blank_spec('b1', '简体断定词', ['だ'])],
                _expl(f"{r('彼', 'かれ')}は{r('学生', 'がくせい')}<strong>だ</strong>。", 'kare wa gakusei da.', '名词在句末作谓语断定，简体直接使用「だ」。'),
            ),
            fc(
                'fc-jp01-02', '句末な形容词断定「だ」', ['p-jp01-da-pred'],
                '请填入句末简体断定词说明状态：',
                'この部屋は静か{{blank:b1}}。',
                f"この{r('部屋', 'へや')}は{r('静', 'しず')}か{B1}。",
                'kono heya wa shizuka [ ? ]',
                '这个房间很安静。（简体）',
                [blank_spec('b1', '简体断定词', ['だ'])],
                _expl(f"この{r('部屋', 'へや')}は{r('静', 'しず')}か<strong>だ</strong>。", 'kono heya wa shizuka da.', 'な形容词在句末作谓语时与名词一样接「だ」（不可误用在名词前作直接定语）。'),
            ),
            fc(
                'fc-jp01-03', '名词修饰名词用「の」', ['p-jp01-noun-no'],
                '请填入连接两个名词作直接定语的助词：',
                '学生{{blank:b1}}田中さん',
                f"{r('学生', 'がくせい')}{B1}{r('田中', 'たなか')}さん",
                'gakusei [ ? ] tanaka-san',
                '学生身份的田中先生',
                [blank_spec('b1', '定语助词', ['の'])],
                _expl(f"{r('学生', 'がくせい')}<strong>の</strong>{r('田中', 'たなか')}さん", 'gakusei no tanaka-san', '名词直接修饰名词时，不能说「*学生だ田中さん」，必须把「だ」换成「の」。'),
            ),
            fc(
                'fc-jp01-04', '日本朋友：名词+の+名词', ['p-jp01-noun-no'],
                '请填入正确助词表达所属/身份修饰：',
                '日本人{{blank:b1}}友達',
                f"{r('日本人', 'にほんじん')}{B1}{r('友達', 'ともだち')}",
                'nihonjin [ ? ] tomodachi',
                '日本朋友',
                [blank_spec('b1', '定语助词', ['の'])],
                _expl(f"{r('日本人', 'にほんじん')}<strong>の</strong>{r('友達', 'ともだち')}", 'nihonjin no tomodachi', '「日本人」与「友達」都是名词，须以「の」相连。'),
            ),
            fc(
                'fc-jp01-05', 'な形容词直接修饰名词「な」', ['p-jp01-na-attr'],
                '请填入修饰后面名词的正确连接假名：',
                '静か{{blank:b1}}部屋',
                f"{r('静', 'しず')}か{B1}{r('部屋', 'へや')}",
                'shizuka [ ? ] heya',
                '安静的房间',
                [blank_spec('b1', '连体假名', ['な'])],
                _expl(f"{r('静', 'しず')}か<strong>な</strong>{r('部屋', 'へや')}", 'shizuka na heya', 'な形容词直接修饰名词时，必须把「だ」换成「な」。'),
            ),
            fc(
                'fc-jp01-06', 'な形容词「有名」修饰名词', ['p-jp01-na-attr'],
                '填入正确助词修饰后面的名词：',
                '有名{{blank:b1}}お店',
                f"{r('有名', 'ゆうめい')}{B1}お{r('店', 'みせ')}",
                'yūmei [ ? ] omise',
                '有名的店',
                [blank_spec('b1', '连体假名', ['な'])],
                _expl(f"{r('有名', 'ゆうめい')}<strong>な</strong>お{r('店', 'みせ')}", 'yūmei na omise', '「有名」属于な形容词，修饰名词「お店」需加「な」。'),
            ),
            fc(
                'fc-jp01-07', '直接引用小句保留「だ」', ['p-jp01-da-quote'],
                '引号内为完整直接引语，填入简体断定词：',
                '「学生{{blank:b1}}」と言った人',
                f"「{r('学生', 'がくせい')}{B1}」と{r('言', 'い')}った{r('人', 'ひと')}",
                '"gakusei [ ? ]" to itta hito',
                '说了“是学生”的那个人',
                [blank_spec('b1', '引语断定词', ['だ'])],
                _expl(f"「{r('学生', 'がくせい')}<strong>だ</strong>」と{r('言', 'い')}った{r('人', 'ひと')}", '"gakusei da" to itta hito', '此处属于「〜と言った」直接引用内容，非直接定语，故保留「だ」。'),
            ),
            fc(
                'fc-jp01-08', '「〜という」同位从句保留「だ」', ['p-jp01-da-quote'],
                '填入「〜という」同位小句内部保留的简体断定词：',
                '高校生{{blank:b1}}という理由',
                f"{r('高校生', 'こうこうせい')}{B1}という{r('理由', 'りゆう')}",
                'kōkōsei [ ? ] to iu riyū',
                '所谓的“是高中生”这个理由',
                [blank_spec('b1', '从句断定词', ['だ'])],
                _expl(f"{r('高校生', 'こうこうせい')}<strong>だ</strong>という{r('理由', 'りゆう')}", 'kōkōsei da to iu riyū', '包含「〜という」完整小句时，内部可用「だ」结句。'),
            ),
            fc(
                'fc-jp01-09', '真正表达“是”的词（敬体）', ['p-jp01-not-copula'],
                '在日语判断句中，「は」只标主题；请在句末填入真正表达“是”的敬体词（含句号亦可不写句号）：',
                '私は学生{{blank:b1}}。',
                f"{r('私', 'わたし')}は{r('学生', 'がくせい')}{B1}。",
                'watashi wa gakusei [ ? ]',
                '我是学生。（敬体）',
                [blank_spec('b1', '敬体断定词', ['です'])],
                _expl(f"{r('私', 'わたし')}は{r('学生', 'がくせい')}<strong>です</strong>。", 'watashi wa gakusei desu.', '「は」不是“是”，「です」（简体「だ」）才是句末的状态断言词。'),
            ),
            fc(
                'fc-jp01-10', '动词句中仅标记主语（无“是”）', ['p-jp01-not-copula'],
                '请填入标记初次出场动作执行者（主语）的助词：',
                '今日、宮本さん{{blank:b1}}来ました。',
                f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さん{B1}{r('来', 'き')}ました。",
                'kyō, miyamoto-san [ ? ] kimashita.',
                '今天，宫本女士来了。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さん<strong>が</strong>{r('来', 'き')}ました。", 'kyō, miyamoto-san ga kimashita.', '动词句中没有“是”；书面规范须用「が」把新引入的动作执行者扣在动词「来ました」上。'),
            ),
            fc(
                'fc-jp01-11', '「は」设定主题（焦点在后）', ['p-jp01-wa-focus'],
                '设“我”为全句主题，把焦点放到后半句的身份说明上：',
                '私{{blank:b1}}学生です。',
                f"{r('私', 'わたし')}{B1}{r('学生', 'がくせい')}です。",
                'watashi [ ? ] gakusei desu.',
                '关于我，我的身份是学生。',
                [blank_spec('b1', '主题助词', ['は'])],
                _expl(f"{r('私', 'わたし')}<strong>は</strong>{r('学生', 'がくせい')}です。", 'watashi wa gakusei desu.', '「は」（读 wa）把焦点引导至后面的谓语「学生です」。'),
            ),
            fc(
                'fc-jp01-12', '「が」精确指认（焦点在前）', ['p-jp01-ga-focus'],
                '在多人中精确指认“正是我”才是那个学生（焦点在前面）：',
                '私{{blank:b1}}学生です。',
                f"{r('私', 'わたし')}{B1}{r('学生', 'がくせい')}です。",
                'watashi [ ? ] gakusei desu.',
                '（正是）我才是那个学生。',
                [blank_spec('b1', '标识助词', ['が'])],
                _expl(f"{r('私', 'わたし')}<strong>が</strong>{r('学生', 'がくせい')}です。", 'watashi ga gakusei desu.', '「が」聚焦前面的名词「私」，用于在候选项中精确识别。'),
            ),
            fc(
                'fc-jp01-13', '回答疑问句主语用「が」', ['p-jp01-ga-focus'],
                '回答“谁是学生？”并准确指认“吉姆才是那个学生”：',
                'ジム{{blank:b1}}学生。',
                f"ジム{B1}{r('学生', 'がくせい')}。",
                'jimu [ ? ] gakusei.',
                '吉姆是那个学生。',
                [blank_spec('b1', '标识助词', ['が'])],
                _expl(f"ジム<strong>が</strong>{r('学生', 'がくせい')}。", 'jimu ga gakusei.', '回答以「が」提问的主语时，同样保持使用标识助词「が」。'),
            ),
            fc(
                'fc-jp01-14', '疑问词作主语铁律', ['p-jp01-wh-ga'],
                '以疑问词「誰」作主语提问“谁是学生？”时，填入正确的助词：',
                '誰{{blank:b1}}学生？',
                f"{r('誰', 'だれ')}{B1}{r('学生', 'がくせい')}？",
                'dare [ ? ] gakusei?',
                '谁是学生？',
                [blank_spec('b1', '助词', ['が'])],
                _expl(f"{r('誰', 'だれ')}<strong>が</strong>{r('学生', 'がくせい')}？", 'dare ga gakusei?', '疑问词代表未知信息，作主语时只能用「が」（绝不能说「*誰は学生？」）。'),
            ),
            fc(
                'fc-jp01-15', '被问及已知主题用「は」', ['p-jp01-wh-ga'],
                '“学生”已是双方共知对象，在其后接助词引出对“是谁”的提问：',
                '学生{{blank:b1}}誰？',
                f"{r('学生', 'がくせい')}{B1}{r('誰', 'だれ')}？",
                'gakusei [ ? ] dare?',
                '关于学生，是谁呢？',
                [blank_spec('b1', '主题助词', ['は'])],
                _expl(f"{r('学生', 'がくせい')}<strong>は</strong>{r('誰', 'だれ')}？", 'gakusei wa dare?', '已知待询问对象作主题在句首时，用「は」引出后面的疑问焦点。'),
            ),
            fc(
                'fc-jp01-16', '礼貌询问已知对象「お名前」', ['p-jp01-wh-ga'],
                '以“您的名字”为主题询问“是什么”：',
                'お名前{{blank:b1}}何ですか。',
                f"お{r('名前', 'なまえ')}{B1}{r('何', 'なん')}ですか。",
                'onamae [ ? ] nan desu ka.',
                '请问您叫什么名字？',
                [blank_spec('b1', '主题助词', ['は'])],
                _expl(f"お{r('名前', 'なまえ')}<strong>は</strong>{r('何', 'なん')}ですか。", 'onamae wa nan desu ka.', '「お名前」是已知被询问对象，用「は」作主题，疑问词「何」位于句末谓语。'),
            ),
            fc(
                'fc-jp01-17', '「は」的排他与对比语境', ['p-jp01-rocket-satellite'],
                '填入带有“对比其他日子（言下之意其他天不休息）”语感的助词：',
                '月曜日{{blank:b1}}休みです。',
                f"{r('月曜日', 'げつようび')}{B1}{r('休', 'やす')}みです。",
                'getsuyōbi [ ? ] yasumi desu.',
                '周一是休息日（其他日子不是）。',
                [blank_spec('b1', '对比助词', ['は'])],
                _expl(f"{r('月曜日', 'げつようび')}<strong>は</strong>{r('休', 'やす')}みです。", 'getsuyōbi wa yasumi desu.', '「は」在特定集合语境下隐含对比与排他含义。'),
            ),
            fc(
                'fc-jp01-18', '综合复盘：火箭→卫星信息演变', ['p-jp01-wa-focus', 'p-jp01-ga-focus', 'p-jp01-rocket-satellite'],
                '按新信息（火箭）先登场、已知背景（卫星）后继说的规律，依次填入助词：',
                '今日、宮本さん{{blank:b1}}来ました。宮本さん{{blank:b2}}日本語の先生です。',
                f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さん{B1}{r('来', 'き')}ました。{r('宮本', 'みやもと')}さん{B2}{r('日本語', 'にほんご')}の{r('先生', 'せんせい')}です。",
                'kyō, miyamoto-san [ ? ] kimashita. miyamoto-san [ ? ] nihongo no sensei desu.',
                '今天宫本女士来了。宫本女士是日语老师。',
                [blank_spec('b1', '第一空（新引入）', ['が']), blank_spec('b2', '第二空（已知背景）', ['は'])],
                _expl(f"{r('今日', 'きょう')}、{r('宮本', 'みやもと')}さん<strong>が</strong>{r('来', 'き')}ました。{r('宮本', 'みやもと')}さん<strong>は</strong>{r('日本語', 'にほんご')}の{r('先生', 'せんせい')}です。", 'kyō, miyamoto-san ga kimashita. miyamoto-san wa nihongo no sensei desu.', '首次引入用「が」（火箭升空）；随后转为已知背景用「は」（卫星入轨）。'),
            ),
            fc(
                'fc-jp01-19', '综合复盘：直接定语与引用小句', ['p-jp01-noun-no', 'p-jp01-na-attr', 'p-jp01-da-quote'],
                '依次填入正确形式区分“名词定语 / な形容词定语 / 引用小句”：',
                '日本人{{blank:b1}}友達 ／ 有名{{blank:b2}}お店 ／ 「学生{{blank:b3}}」と言った人',
                f"{r('日本人', 'にほんじん')}{B1}{r('友達', 'ともだち')} ／ {r('有名', 'ゆうめい')}{B2}お{r('店', 'みせ')} ／ 「{r('学生', 'がくせい')}{B3}」と{r('言', 'い')}った{r('人', 'ひと')}",
                'nihonjin [ ? ] tomodachi / yūmei [ ? ] omise / "gakusei [ ? ]" to itta hito',
                '日本朋友 ／ 有名的店 ／ 说了“是学生”的人',
                [blank_spec('b1', '名词定语', ['の']), blank_spec('b2', 'な形定语', ['な']), blank_spec('b3', '直接引语', ['だ'])],
                _expl(f"{r('日本人', 'にほんじん')}<strong>の</strong>{r('友達', 'ともだち')} ／ {r('有名', 'ゆうめい')}<strong>な</strong>お{r('店', 'みせ')} ／ 「{r('学生', 'がくせい')}<strong>だ</strong>」と{r('言', 'い')}った{r('人', 'ひと')}", 'nihonjin no tomodachi / yūmei na omise / "gakusei da" to itta hito', '直接修饰名词时名词用「の」、な形容词用「な」；直接引语内部保留「だ」。'),
            ),
            fc(
                'fc-jp01-20', '综合复盘：疑问词主语问答对', ['p-jp01-wh-ga', 'p-jp01-ga-focus'],
                '完成这组“疑问词提问主语＋指认回答”对话：',
                '誰{{blank:b1}}学生？ — ジム{{blank:b2}}学生。',
                f"{r('誰', 'だれ')}{B1}{r('学生', 'がくせい')}？ — ジム{B2}{r('学生', 'がくせい')}。",
                'dare [ ? ] gakusei? — jimu [ ? ] gakusei.',
                '谁是学生？——吉姆是学生。',
                [blank_spec('b1', '提问主语', ['が']), blank_spec('b2', '回答主语', ['が'])],
                _expl(f"{r('誰', 'だれ')}<strong>が</strong>{r('学生', 'がくせい')}？ — ジム<strong>が</strong>{r('学生', 'がくせい')}。", 'dare ga gakusei? — jimu ga gakusei.', '疑问词作主语必须用「が」，回答主语时同样用「が」精准标识。'),
            ),
            fc(
                'fc-jp01-21', '综合复盘：「は」看后面 vs「が」看前面', ['p-jp01-wa-focus', 'p-jp01-wh-ga'],
                '第一句以“学生”作已知主题提问“是谁”，第二句以“我”为主题说明身份：',
                '学生{{blank:b1}}誰？ — 私{{blank:b2}}学生です。',
                f"{r('学生', 'がくせい')}{B1}{r('誰', 'だれ')}？ — {r('私', 'わたし')}{B2}{r('学生', 'がくせい')}です。",
                'gakusei [ ? ] dare? — watashi [ ? ] gakusei desu.',
                '学生是谁？——我是学生。',
                [blank_spec('b1', '已知对象主题', ['は']), blank_spec('b2', '说明主题', ['は'])],
                _expl(f"{r('学生', 'がくせい')}<strong>は</strong>{r('誰', 'だれ')}？ — {r('私', 'わたし')}<strong>は</strong>{r('学生', 'がくせい')}です。", 'gakusei wa dare? — watashi wa gakusei desu.', '「学生は誰？」把已知概念设为主题问其身份；答句如侧重说明“我的身份”也用「は」（若强调“正是我”则换「が」）。'),
            ),
            fc(
                'fc-jp01-22', '综合复盘：判断句与定语替换速测', ['p-jp01-da-pred', 'p-jp01-noun-no', 'p-jp01-na-attr'],
                '依次填入句末简体谓语与名词前定语所需的正确形式：',
                'この部屋は静か{{blank:b1}}。 ／ 静か{{blank:b2}}部屋 ／ 学生{{blank:b3}}田中さん',
                f"この{r('部屋', 'へや')}は{r('静', 'しず')}か{B1}。 ／ {r('静', 'しず')}か{B2}{r('部屋', 'へや')} ／ {r('学生', 'がくせい')}{B3}{r('田中', 'たなか')}さん",
                'kono heya wa shizuka [ ? ]. / shizuka [ ? ] heya / gakusei [ ? ] tanaka-san',
                '这个房间很安静。 ／ 安静的房间 ／ 学生田中先生',
                [blank_spec('b1', '句末谓语', ['だ']), blank_spec('b2', 'な形定语', ['な']), blank_spec('b3', '名词定语', ['の'])],
                _expl(f"この{r('部屋', 'へや')}は{r('静', 'しず')}か<strong>だ</strong>。 ／ {r('静', 'しず')}か<strong>な</strong>{r('部屋', 'へや')} ／ {r('学生', 'がくせい')}<strong>の</strong>{r('田中', 'たなか')}さん", 'kono heya wa shizuka da. / shizuka na heya / gakusei no tanaka-san', '句末断定用「だ」；直接修饰名词时，な形容词用「な」，名词用「の」。'),
            ),
        ],
    },
    # =========================================================================
    # Topic 2: jp02-spo-object-particles
    # =========================================================================
    {
        'id': 'jp02-spo-object-particles',
        'title': '2. 主谓宾句型、核心格助词与自他动词',
        'sections': [
            {
                'id': 'sec-jp02-spo',
                'title': '一、主谓宾句型：「SはOをV」与「SがOをV」',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp02-particles',
                'title': '二、四大核心格助词（を・に・へ・で）与双重「を」限制',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp02-transitivity',
                'title': '三、自动词与他动词、成对词表及「要る・分かる」',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp02-spo',
                'section_id': 'sec-jp02-spo',
                'title': '日语主谓宾默认模板「S は O を V」与改用「S が O を V」的四大场景',
                'html': (
                    '<h3>日语“主谓宾”默认模板：S は + O を + 他动词</h3>'
                    '<p>在独立日常主句中，表达“主—谓—宾”时最普遍的模板是 <code>S は + O を + 他动词</code>（日语语序为主—宾—谓）。由于日常谈话中主语常是双方已知背景，<code>S は</code> 出现的频率远高于 <code>S が</code>——它把主语平稳设为主题，将注意力推向后面的核心新信息「做了什么」：</p>'
                    + ex(f"{r('私', 'わたし')}は{r('朝', 'あさ')}ご{r('飯', 'はん')}を{r('食', 'た')}べた。", 'watashi wa asagohan o tabeta.', '至于我呢，吃了早饭。')
                    + '<p><strong>确定「S は」后连续省略主语</strong>：一旦句首用 <code>S は</code>（或 <code>S も</code>）立住主题，后文哪怕连续出现十几个动作，也可以省去主语，直接简化成 <code>O を + 他动词</code>（如太宰治文本中在「この原田内助も……」之后连续使用 '
                    + term(f"{r('眼', 'め')}を{r('固', 'かた')}くつぶって", 'me o kataku tsubutte', '紧紧闭上眼睛') + '、'
                    + term(f"{r('論語', 'ろんご')}をひらいて", 'rongo o hiraite', '翻开《论语》') + '、'
                    + term(f"{r('酒', 'さけ')}を{r('飲', 'の')}んで", 'sake o nonde', '喝酒') + ' 等连串结构）。</p>'
                    '<h3>主谓宾句子何时必须改用「S が + O を + 他动词」？</h3>'
                    '<p>在以下 <strong>4 种特定场景</strong>下，必须将主语助词换为「が」：</p>'
                    '<ol>'
                    '<li><strong>追查或强调“到底是谁干的”（指认施动者）</strong>：'
                    + ex(f"{r('誰', 'だれ')}が{r('窓', 'まど')}を{r('開', 'あ')}けた？ → {r('私', 'わたし')}が{r('窓', 'まど')}を{r('開', 'あ')}けた。", 'dare ga mado o aketa? → watashi ga mado o aketa.', '谁把窗户打开的？→ 是我把窗户打开的！')
                    + '</li>'
                    '<li><strong>突发状况或新人物首次登场（刚升空的火箭）</strong>：'
                    + ex(f"あっ、{r('猫', 'ねこ')}が{r('魚', 'さかな')}を{r('盗', 'ぬす')}んだ！", 'a, neko ga sakana o nusunda!', '啊，有只猫偷了鱼！', '猫是突然闯入视野的新信息')
                    + '</li>'
                    '<li><strong>缩进从句（定语小句、条件句）内部作小主语</strong>：全句大主题用「は」，定语从句内小主语退居「が」：'
                    + ex(f"{r('私', 'わたし')}は{r('母', 'はは')}が{r('作', 'つく')}った{r('料理', 'りょうり')}を{r('食', 'た')}べた。", 'watashi wa haha ga tsukutta ryōri o tabeta.', '我吃了妈妈做的菜。', '大主题「私は」+ 定语从句小主语「母が」')
                    + '</li>'
                    '<li><strong>宾语被提前加上「は」进行对比时（O は S が + 动词）</strong>：'
                    + ex(f"この{r('蜆', 'しじみ')}は、{r('原田内助', 'はらだないじょ')}が{r('全部', 'ぜんぶ')}{r('買', 'か')}いしめた。", 'kono shijimi wa, harada naijo ga zenbu kaishimeta.', '至于这些蚬子呢，是原田内助全买光了。')
                    + '</li>'
                    '</ol>'
                ),
            },
            {
                'id': 'intro-jp02-particles',
                'section_id': 'sec-jp02-particles',
                'title': '动词周围四大核心格助词、场所「に/で」辨析与双重「を」限制',
                'html': (
                    '<h3>一、动词周围的四大核心格助词：を・に・へ・で</h3>'
                    '<p>日语谓语/动词永远放在句末，因此需要名词后面的<strong>格助词（Phrase Particles）</strong>作为桥梁把各成分扣到动词上：</p>'
                    '<ul>'
                    '<li><strong>宾语助词「を」（读作 o，罗马字写作 wo）</strong>：标示动作直接承受对象（直接宾语），也可与移动动词连用表示离开的起点或穿过的空间（因为「部屋」不是目的地终点，不用「に」）：'
                    + ex(f"{r('日本語', 'にほんご')}を{r('勉強', 'べんきょう')}する。", 'nihongo o benkyō suru.', '学习日语。')
                    + ex(f"{r('部屋', 'へや')}を{r('出', 'で')}る。", 'heya o deru.', '离开房间。', '离开的起点空间')
                    + '</li>'
                    '<li><strong>目标助词「に」（Target / Placement Marker，相当于 to / at / into）</strong>：标示移动终点、静态存在场所、动作落脚归宿与特定时间点：'
                    + ex(f"{r('日本', 'にほん')}に{r('行', 'い')}く。", 'nihon ni iku.', '去日本。', '移动终点')
                    + ex(f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}にいる。", 'neko wa heya ni iru.', '猫在房间里。', '静态存在点')
                    + ex(f"{r('本', 'ほん')}を{r('机', 'つくえ')}の{r('上', 'うえ')}に{r('置', 'お')}く。", 'hon o tsukue no ue ni oku.', '把书放在桌子上。', '动作落脚归宿')
                    + ex(f"{r('九時', 'くじ')}に{r('着', 'つ')}きます。", 'kuji ni tsukimasu.', '九点到达。', '具体时间点')
                    + '</li>'
                    '<li><strong>方向助词「へ」（Directional Marker，助词读作 e，相当于 towards）</strong>：仅标示朝向的大致物理方向，不强调最终是否到达；<strong>不可用于非方向性的抽象转化</strong>：'
                    + ex(f"{r('日本', 'にほん')}へ{r('行', 'い')}った。", 'nihon e itta.', '朝日本的方向去了。')
                    + ex(f"{r('医者', 'いしゃ')}になる。", 'isha ni naru.', '成为医生。', '抽象转化只能用「に」')
                    + bad_ex('医者へなる', '「へ」不可用于非物理方向的状态转化')
                    + '</li>'
                    '<li><strong>范围/手段助词「で」（Context / Domain Marker，相当于 at / in / by / with）</strong>：标示活动场所或工具/交通手段：'
                    + ex(f"{r('図書館', 'としょかん')}で{r('勉強', 'べんきょう')}する。", 'toshokan de benkyō suru.', '在图书馆学习。', '动作开展的空间域')
                    + ex(f"{r('車', 'くるま')}で行く。", 'kuruma de iku.', '坐车去。', '所用交通工具/手段')
                    + '</li>'
                    '</ul>'
                    '<h3>二、核心辨析：静态落脚点「に」vs 动态活动域「で」</h3>'
                    + ex(f"ホテルに{r('車', 'くるま')}をとめる。", 'hoteru ni kuruma o tomeru.', '把车停在饭店。', '「に」关注物体最终停放落脚在何处')
                    + ex(f"{r('図書館', 'としょかん')}で{r('昼寝', 'ひるね')}する。", 'toshokan de hirune suru.', '在图书馆午睡。', '「で」关注活动在哪个空间范围内展开')
                    + '<h3>三、语法铁律：双重「を」限制（Double-O Constraint）</h3>'
                    '<p>在一个动词领地内，<strong>绝对不能同时出现两个「を」</strong>。以「勉強（する）」为例：「勉強する」可作整体动词，也可拆成「勉強をする」。一旦要加入直接宾语「日本語」，必须二选一修正：</p>'
                    + ex(f"{r('日本語', 'にほんご')}を{r('勉強', 'べんきょう')}する。", 'nihongo o benkyō suru.', '学习日语。', '把「勉強する」当整体动词，只留一个「を」')
                    + ex(f"{r('日本語', 'にほんご')}の{r('勉強', 'べんきょう')}をする。", 'nihongo no benkyō o suru.', '做日语的学习。', '用「の」合并成单一名词短语，再接「をする」')
                    + bad_ex('日本語を勉強をする', '一句话里出现两个「を」，违反双重「を」限制')
                ),
            },
            {
                'id': 'intro-jp02-transitivity',
                'section_id': 'sec-jp02-transitivity',
                'title': '自动词与他动词、成对词表及「要る・分かる」的「が」句型',
                'html': (
                    '<h3>一、自动词与他动词的核心定义及成对现象</h3>'
                    '<p><strong>他动词（Transitive Verb）</strong>描述由明确施动者主动施加的动作，必须用「を」标示直接宾语（<code>[施动者]が/は + [宾语]を + 他动词</code>）；<strong>自动词（Intransitive Verb）</strong>描述自然发生、无直接人为干预的客观变化，<strong>绝对不能带直接宾语「を」</strong>，事物本身作主语用「が」（<code>[主语/现象]が/は + 自动词</code>）。</p>'
                    + ex(f"{r('私', 'わたし')}が{r('電気', 'でんき')}をつけた。", 'watashi ga denki o tsuketa.', '我把灯打开了。', '他动词 + を')
                    + ex(f"{r('電気', 'でんき')}がついた。", 'denki ga tsuita.', '灯亮了。', '自动词 + が')
                    + bad_ex('窓開いた / 電気消える', '标准语法中自动词必须用「が」标示主语（应为「窓が開いた」「電気が消える」）')
                    + tbl(
                        ['动作概念', '他动词（施动者 + を）', '自动词（现象/主语 + が）'],
                        [
                            ['开', ex(f"{r('窓', 'まど')}を{r('開', 'あ')}ける", 'mado o akeru', '打开窗户'), ex(f"{r('窓', 'まど')}が{r('開', 'あ')}く", 'mado ga aku', '窗户开了')],
                            ['关', ex(f"ドアを{r('閉', 'し')}める", 'doa o shimeru', '关门'), ex(f"ドアが{r('閉', 'し')}まる", 'doa ga shimaru', '门关上了')],
                            ['开灯 / 关灯', ex(f"{r('灯', 'あか')}りをつける／{r('消', 'け')}す", 'akari o tsukeru / kesu', '开灯 / 熄灯'), ex(f"{r('灯', 'あか')}りがつく／{r('消', 'き')}える", 'akari ga tsuku / kieru', '灯亮了 / 灯灭了')],
                            ['放入 / 进入', ex(f"{r('箱', 'はこ')}に{r('入', 'い')}れる", 'hako ni ireru', '放进盒子里'), ex(f"{r('箱', 'はこ')}に{r('入', 'はい')}る", 'hako ni hairu', '进入盒子里')],
                        ],
                    )
                    + '<h3>二、及物度标度：「要る」「分かる」为什么接「が」而不接「を」</h3>'
                    f'<p>《Making Sense of Japanese Grammar》提出“<strong>及物度标度（Transitivity Scale）</strong>”：从最典型的强施动他动词（如打、杀）到最典型的自然自动词（如睡觉、开花），中间存在连续过渡地带，而英语与日语在这条标尺上的划界位置不同。英语把 <em>need / want / understand</em> 划在他动词一侧（如 <em>I need a computer</em>）；但日语把界限划得更高，将表示心理倾向、理解或必要状态的「{r("要", "い")}る（いる，需要）」「{r("分", "わ")}かる（わかる，明白）」「{r("足", "た")}りない（たりない，不够）」归为<strong>自动词/状态动词</strong>。因此，被需要或理解的对象 B 才是语法上的主语，必须用「が」；省略上文主语直接说 <code>B が 要る</code> 完全地道自然，而在日语里说 <code>*B を 要る</code> 或 <code>*B を A が 要る</code> 就如同英文说 <em>*I am needed a computer</em> 一样语法错误。</p>'
                    '<p>若补全体验者/对象 A，完整结构为 <code>A に（は）B が 要る</code>——其中「に」相当于英语的 <em>to / for A</em>（“对 A 而言”），「は」将该背景提作全句主题：</p>'
                    + ex(f"（{r('私', 'わたし')}には）パソコンがいります。", '(watashi ni wa) pasokon ga irimasu.', '（对我来说）需要电脑。', '完整结构为 A に（は）B が 要る；省略主语说「パソコンがいる」同样自然')
                    + bad_ex('パソコンをいります / パソコンを私が要る', '「要る」是不及物状态动词，绝不可接「を」')
                    + ex(f"（{r('私', 'わたし')}には）{r('日本語', 'にほんご')}が{r('分', 'わ')}からない。", '(watashi ni wa) nihongo ga wakaranai.', '（对我来说）我不懂日语。')
                    + ex(f"（{r('彼', 'かれ')}には）{r('時間', 'じかん')}が{r('足', 'た')}りない。", '(kare ni wa) jikan ga tarinai.', '（对他来说）时间不够。')
                    + '<p><strong>如果写作中非要用「を」表达“需要”</strong>，必须换成他动词短语 ' + term(f"{r('必要', 'ひつよう')}とする", 'hitsuyō to suru', '需要') + '（结构：<code>A が B を 必要とする</code>）：</p>'
                    + ex(f"{r('彼', 'かれ')}がパソコンを{r('必要', 'ひつよう')}とする。", 'kare ga pasokon o hitsuyō to suru.', '他需要电脑。', '换用他动词短语后才能接宾格「を」')
                    + tip('「要る」vs「必要とする」助词切换规则', '表达“需要”时用自动词「' + f"{r('要', 'い')}" + 'る」，对象<strong>只能接「が」</strong>（<code>B が 要る</code>）；想用<strong>「を」</strong>，则必须改用他动词短语「' + f"{r('必要', 'ひつよう')}" + 'とする」（<code>B を 必要とする</code>）。')
                    + tip('情感类自动词提示', '注意上述 <code>A に（は）B が 状态动词</code> 模板适用于必要、可能、理解、不足等状态评估；表达具体外部对象的情感类动词一般不直接套用此「A に B が」规则。')
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp02-spo-default',
                'introduction_id': 'intro-jp02-spo',
                'title': '默认主谓宾模板「S は + O を + 他动词」与主题后省略',
                'html': '<p>主句平铺直叙主谓宾事件首选「S は + O を + 他动词」，立住主题后下文连续动作常省去主语只留「O を + 动词」。</p>',
                'anchor_quotes': ['日语“主谓宾”默认模板：S は + O を + 他动词'],
                'points': [
                    {'id': 'p-jp02-spo-wa', 'text': '日常叙事主谓宾默认模板为「S は + O を + 他动词」，立住主题后可连续省略主语。'},
                ],
            },
            {
                'id': 'chunk-jp02-spo-ga',
                'introduction_id': 'intro-jp02-spo',
                'title': '改用「S が + O を + 他动词」的四大特定场景',
                'html': '<p>指认施动者、突发新事件、定语从句内小主语（大主题は+小主语が）以及宾语提前作主题（OはSがV）时主语须用「が」。</p>',
                'anchor_quotes': ['主谓宾句子何时必须改用「S が + O を + 他动词」？'],
                'points': [
                    {'id': 'p-jp02-spo-ga-sub', 'text': '指认施动者、突发新事件、从句内小主语及「O は S が V」前置对比时，主语须用「が」。'},
                ],
            },
            {
                'id': 'chunk-jp02-o-ni-e-de',
                'introduction_id': 'intro-jp02-particles',
                'title': '四大核心格助词「を・に・へ・で」的职能与「に vs で」场所辨析',
                'html': '<p>「を」标宾语与离开起点；「に」锁定终点/存在点/时间/转化；「へ」仅表大致物理方向；「で」标动态活动域与手段。</p>',
                'anchor_quotes': ['一、动词周围的四大核心格助词：を・に・へ・で', '二、核心辨析：静态落脚点「に」vs 动态活动域「で」'],
                'points': [
                    {'id': 'p-jp02-o-marker', 'text': '「を」标示直接宾语及移动动词离开的起点空间（部屋を出る）。'},
                    {'id': 'p-jp02-ni-e-diff', 'text': '「に」精准锁定移动终点、存在点、时间点及抽象转化（医者になる）；「へ」（读 e）仅指物理大致方向。'},
                    {'id': 'p-jp02-ni-vs-de', 'text': '场所区分：「に」表物体静态落脚点（ホテルに車をとめる）；「で」表动态活动场所域与工具手段（図書館で昼寝する・車で行く）。'},
                ],
            },
            {
                'id': 'chunk-jp02-double-o',
                'introduction_id': 'intro-jp02-particles',
                'title': '双重「を」限制（Double-O Constraint）',
                'html': '<p>一个动词句内绝不能同时存在两个「を」；需改作「日本語を勉強する」或「日本語の勉強をする」。</p>',
                'anchor_quotes': ['三、语法铁律：双重「を」限制（Double-O Constraint）'],
                'points': [
                    {'id': 'p-jp02-double-o', 'text': '同一动词领地内禁止两个「を」，须合并成「〜を勉強する」或用「の」连接成「〜の勉強をする」。'},
                ],
            },
            {
                'id': 'chunk-jp02-trans-pairs',
                'introduction_id': 'intro-jp02-transitivity',
                'title': '自他动词对立规则与核心成对动词表',
                'html': '<p>他动词带「を」，自动词只带「が」；掌握 開ける/開く、閉める/閉まる、つける/つく、消す/消える、入れる/入る。</p>',
                'anchor_quotes': ['一、自动词与他动词的核心定义及成对现象'],
                'points': [
                    {'id': 'p-jp02-trans-rule', 'text': '他动词描述人为施动配「を」；自动词描述客观变化主语配「が」且禁止带「を」。'},
                    {'id': 'p-jp02-trans-pairs', 'text': '牢记核心自他成对动词：開ける/開く、閉める/閉まる、つける/つく、消す/消える、入れる/入る。'},
                ],
            },
            {
                'id': 'chunk-jp02-iru-wakaru',
                'introduction_id': 'intro-jp02-transitivity',
                'title': '「要る・分かる」的自动词本质与「A に（は）B が」句型',
                'html': '<p>按「及物度标度」，日语将「要る・分かる・足りない」归入自动词：省略主语直接说 <code>B が 要る</code> 完全自然（完整形式为 <code>A に（は）B が 要る</code>），绝不可用 <code>*を</code>；若写作中非要用「を」表需要，须换他动词短语「必要とする」（<code>A が B を 必要とする</code>）。</p>',
                'anchor_quotes': ['二、及物度标度：「要る」「分かる」为什么接「が」而不接「を」'],
                'points': [
                    {'id': 'p-jp02-iru-ga', 'text': '「要る」「分かる」「足りない」在日语中是自动词，所需/理解对象用「が」（パソコンがいります）；用「を」须改用「必要とする」。'},
                    {'id': 'p-jp02-ni-experiencer', 'text': '「A に（は）B が」中的「に」表示“对 A 而言（to/for A）”，一般不用于外部情感类动词。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp02-01', '默认主谓宾句型「S は O を V」', ['p-jp02-spo-wa'],
                '请按主句常规平铺直叙模板，依次填入主题助词与直接宾语助词：',
                '私{{blank:b1}}朝ご飯{{blank:b2}}食べた。',
                f"{r('私', 'わたし')}{B1}{r('朝', 'あさ')}ご{r('飯', 'はん')}{B2}{r('食', 'た')}べた。",
                'watashi [ ? ] asagohan [ ? ] tabeta.',
                '我吃了早饭。（主句常规陈述）',
                [blank_spec('b1', '主题助词', ['は']), blank_spec('b2', '宾格助词', ['を'])],
                _expl(f"{r('私', 'わたし')}<strong>は</strong>{r('朝', 'あさ')}ご{r('飯', 'はん')}<strong>を</strong>{r('食', 'た')}べた。", 'watashi wa asagohan o tabeta.', '主句常规讲“某人做了某事”时首选「S は + O を + 他动词」。'),
            ),
            fc(
                'fc-jp02-02', '立住主题后省略主语仅留「O を V」', ['p-jp02-spo-wa'],
                '上文已立住主题，填入后继连串动作中的宾语助词：',
                '酒{{blank:b1}}飲んで',
                f"{r('酒', 'さけ')}{B1}{r('飲', 'の')}んで",
                'sake [ ? ] nonde',
                '喝了酒（之后……）',
                [blank_spec('b1', '宾格助词', ['を'])],
                _expl(f"{r('酒', 'さけ')}<strong>を</strong>{r('飲', 'の')}んで", 'sake o nonde', '确立主题后主语常省略，只保留核心的「O を + 动词」。'),
            ),
            fc(
                'fc-jp02-03', '突发状况「S が O を V」', ['p-jp02-spo-ga-sub'],
                '播报突发画面且新角色首次登场，依次填入主语与宾语助词：',
                'あっ、猫{{blank:b1}}魚{{blank:b2}}盗んだ！',
                f"あっ、{r('猫', 'ねこ')}{B1}{r('魚', 'さかな')}{B2}{r('盗', 'ぬす')}んだ！",
                'a, neko [ ? ] sakana [ ? ] nusunda!',
                '啊，有只猫偷了鱼！',
                [blank_spec('b1', '主格助词', ['が']), blank_spec('b2', '宾格助词', ['を'])],
                _expl(f"あっ、{r('猫', 'ねこ')}<strong>が</strong>{r('魚', 'さかな')}<strong>を</strong>{r('盗', 'ぬす')}んだ！", 'a, neko ga sakana o nusunda!', '突发事件及新人物首次亮相属于新信息（火箭），主语用「が」。'),
            ),
            fc(
                'fc-jp02-04', '大主题「は」+ 从句内小主语「が」', ['p-jp02-spo-ga-sub'],
                '区分主句大主题（我）与定语从句内部小主语（妈妈）：',
                '私{{blank:b1}}母{{blank:b2}}作った料理を食べた。',
                f"{r('私', 'わたし')}{B1}{r('母', 'はは')}{B2}{r('作', 'つく')}った{r('料理', 'りょうり')}を{r('食', 'た')}べた。",
                'watashi [ ? ] haha [ ? ] tsukutta ryōri o tabeta.',
                '我吃了妈妈做的菜。',
                [blank_spec('b1', '主句大主题', ['は']), blank_spec('b2', '从句小主语', ['が'])],
                _expl(f"{r('私', 'わたし')}<strong>は</strong>{r('母', 'はは')}<strong>が</strong>{r('作', 'つく')}った{r('料理', 'りょうり')}を{r('食', 'た')}べた。", 'watashi wa haha ga tsukutta ryōri o tabeta.', '「は」统领全句大主题，定语从句内部的小主语必须退居为「が」。'),
            ),
            fc(
                'fc-jp02-05', '宾语前置对比「O は S が V」', ['p-jp02-spo-ga-sub'],
                '将宾语“这些蚬子”提前作主题，后面留守主语指认执行者：',
                'この蜆{{blank:b1}}、原田内助{{blank:b2}}全部買いしめた。',
                f"この{r('蜆', 'しじみ')}{B1}、{r('原田内助', 'はらだないじょ')}{B2}{r('全部', 'ぜんぶ')}{r('買', 'か')}いしめた。",
                'kono shijimi [ ? ], harada naijo [ ? ] zenbu kaishimeta.',
                '至于这些蚬子，是原田内助全买光了。',
                [blank_spec('b1', '前置宾语主题', ['は']), blank_spec('b2', '留守主语标识', ['が'])],
                _expl(f"この{r('蜆', 'しじみ')}<strong>は</strong>、{r('原田内助', 'はらだないじょ')}<strong>が</strong>{r('全部', 'ぜんぶ')}{r('買', 'か')}いしめた。", 'kono shijimi wa, harada naijo ga zenbu kaishimeta.', '宾语用「は」提前对比后，后面的主语要用「が」标明。'),
            ),
            fc(
                'fc-jp02-06', '直接宾语助词「を」', ['p-jp02-o-marker'],
                '填入标示直接承受动作对象的格助词：',
                '日本語{{blank:b1}}勉強する。',
                f"{r('日本語', 'にほんご')}{B1}{r('勉強', 'べんきょう')}する。",
                'nihongo [ ? ] benkyō suru.',
                '学习日语。',
                [blank_spec('b1', '宾格助词', ['を'])],
                _expl(f"{r('日本語', 'にほんご')}<strong>を</strong>{r('勉強', 'べんきょう')}する。", 'nihongo o benkyō suru.', '「勉強する」作为他动词，直接宾语用「を」标示。'),
            ),
            fc(
                'fc-jp02-07', '移动离开的起点助词「を」', ['p-jp02-o-marker'],
                '房间并非到达目标而是离开的起点，与移动动词「出る」连用时应填：',
                '部屋{{blank:b1}}出る。',
                f"{r('部屋', 'へや')}{B1}{r('出', 'で')}る。",
                'heya [ ? ] deru.',
                '离开房间。',
                [blank_spec('b1', '离开起点助词', ['を'])],
                _expl(f"{r('部屋', 'へや')}<strong>を</strong>{r('出', 'で')}る。", 'heya o deru.', '与「出る」等移动动词连用表示离开某地时不用「に」，而用「を」。'),
            ),
            fc(
                'fc-jp02-08', '精准终点目标「に」', ['p-jp02-ni-e-diff'],
                '精准锁定移动的最终目标地点（to，到达终点日本）：',
                '日本{{blank:b1}}行く。',
                f"{r('日本', 'にほん')}{B1}{r('行', 'い')}く。",
                'nihon [ ? ] iku.',
                '去日本（目标终点是日本）。',
                [blank_spec('b1', '目标终点助词', ['に'])],
                _expl(f"{r('日本', 'にほん')}<strong>に</strong>{r('行', 'い')}く。", 'nihon ni iku.', '「に」像精准落点，锁定移动的最终到达目标。'),
            ),
            fc(
                'fc-jp02-09', '大致物理方向「へ」', ['p-jp02-ni-e-diff'],
                '强调“朝着日本的大致方向”（towards），并不强调是否抵达：',
                '日本{{blank:b1}}行った。',
                f"{r('日本', 'にほん')}{B1}{r('行', 'い')}った。",
                'nihon [ ? ] itta.',
                '朝日本的方向去了。',
                [blank_spec('b1', '方向助词', ['へ'])],
                _expl(f"{r('日本', 'にほん')}<strong>へ</strong>{r('行', 'い')}った。", 'nihon e itta.', '「へ」（作助词读 e）仅指朝某方向行进，较「に」更侧重方向感。'),
            ),
            fc(
                'fc-jp02-10', '抽象转化结果只用「に」', ['p-jp02-ni-e-diff'],
                '表示非物理方向的身份/状态转化，填入目标助词：',
                '医者{{blank:b1}}なる。',
                f"{r('医者', 'いしゃ')}{B1}なる。",
                'isha [ ? ] naru.',
                '成为医生。',
                [blank_spec('b1', '转化目标助词', ['に'])],
                _expl(f"{r('医者', 'いしゃ')}<strong>に</strong>なる。", 'isha ni naru.', '「成为……」属于抽象转化目标，只能用「に」，不能说「*医者へなる」。'),
            ),
            fc(
                'fc-jp02-11', '特定时间点「に」', ['p-jp02-ni-e-diff'],
                '标示动作发生的具体时间点：',
                '九時{{blank:b1}}着きます。',
                f"{r('九時', 'くじ')}{B1}{r('着', 'つ')}きます。",
                'kuji [ ? ] tsukimasu.',
                '九点到达。',
                [blank_spec('b1', '时间点助词', ['に'])],
                _expl(f"{r('九時', 'くじ')}<strong>に</strong>{r('着', 'つ')}きます。", 'kuji ni tsukimasu.', '具体的时刻目标点使用「に」标记。'),
            ),
            fc(
                'fc-jp02-12', '静态落脚归宿「に」', ['p-jp02-ni-vs-de'],
                '强调车最终停放落脚在饭店这一附着点：',
                'ホテル{{blank:b1}}車をとめる。',
                f"ホテル{B1}{r('車', 'くるま')}をとめる。",
                'hoteru [ ? ] kuruma o tomeru.',
                '把车停在饭店。',
                [blank_spec('b1', '静态落脚助词', ['に'])],
                _expl(f"ホテル<strong>に</strong>{r('車', 'くるま')}をとめる。", 'hoteru ni kuruma o tomeru.', '关注物体最终停留/附着的位置时用「に」。'),
            ),
            fc(
                'fc-jp02-13', '动态活动空间域「で」', ['p-jp02-ni-vs-de'],
                '强调“午睡”这项动态活动在图书馆空间范围内展开：',
                '図書館{{blank:b1}}昼寝する。',
                f"{r('図書館', 'としょかん')}{B1}{r('昼寝', 'ひるね')}する。",
                'toshokan [ ? ] hirune suru.',
                '在图书馆午睡。',
                [blank_spec('b1', '活动场所助词', ['で'])],
                _expl(f"{r('図書館', 'としょかん')}<strong>で</strong>{r('昼寝', 'ひるね')}する。", 'toshokan de hirune suru.', '动作发生或持续展开的空间范围使用「で」。'),
            ),
            fc(
                'fc-jp02-14', '交通工具与手段「で」', ['p-jp02-ni-vs-de'],
                '标示所使用的交通工具或手段：',
                '車{{blank:b1}}行く。',
                f"{r('車', 'くるま')}{B1}{r('行', 'い')}く。",
                'kuruma [ ? ] iku.',
                '坐车去。',
                [blank_spec('b1', '工具/手段助词', ['で'])],
                _expl(f"{r('車', 'くるま')}<strong>で</strong>{r('行', 'い')}く。", 'kuruma de iku.', '工具、方式、交通手段统一用「で」。'),
            ),
            fc(
                'fc-jp02-15', '静态存在场所「に」', ['p-jp02-ni-vs-de'],
                '与存在动词「いる」连用标示静态存在位置：',
                '猫は部屋{{blank:b1}}いる。',
                f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}{B1}いる。",
                'neko wa heya [ ? ] iru.',
                '猫在房间里。',
                [blank_spec('b1', '存在场所助词', ['に'])],
                _expl(f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}<strong>に</strong>いる。", 'neko wa heya ni iru.', '表示静态人或物存在于某处时，场所后用「に」。'),
            ),
            fc(
                'fc-jp02-16', '遵守双重「を」限制（改用「の」连接）', ['p-jp02-double-o'],
                '用名词短语结构表达“做日语的学习”，依次填入连接助词与宾语助词：',
                '日本語{{blank:b1}}勉強{{blank:b2}}する。',
                f"{r('日本語', 'にほんご')}{B1}{r('勉強', 'べんきょう')}{B2}する。",
                'nihongo [ ? ] benkyō [ ? ] suru.',
                '做日语的学习。',
                [blank_spec('b1', '名词连接助词', ['の']), blank_spec('b2', '宾语助词', ['を'])],
                _expl(f"{r('日本語', 'にほんご')}<strong>の</strong>{r('勉強', 'べんきょう')}<strong>を</strong>する。", 'nihongo no benkyō o suru.', '通过「の」把「日本語の勉強」组合成单个名词短语，从而全句只留一个「を」。'),
            ),
            fc(
                'fc-jp02-17', '双重「を」限制：整体动词法', ['p-jp02-double-o'],
                '把「勉強する」看作不可拆分的整体动词，直接标示“学习日语”：',
                '毎日日本語{{blank:b1}}勉強する。',
                f"{r('毎日', 'まいにち')}{r('日本語', 'にほんご')}{B1}{r('勉強', 'べんきょう')}する。",
                'mainichi nihongo [ ? ] benkyō suru.',
                '每天学习日语。',
                [blank_spec('b1', '宾格助词', ['を'])],
                _expl(f"{r('毎日', 'まいにち')}{r('日本語', 'にほんご')}<strong>を</strong>{r('勉強', 'べんきょう')}する。", 'mainichi nihongo o benkyō suru.', '使用整体复合动词「勉強する」，只在「日本語」后用一次「を」。'),
            ),
            fc(
                'fc-jp02-18', '他动词句型：明确施动者 + 宾语を', ['p-jp02-trans-rule'],
                '强调“是我把灯打开的”（他动词句型）：',
                '私{{blank:b1}}電気{{blank:b2}}つけた。',
                f"{r('私', 'わたし')}{B1}{r('電気', 'でんき')}{B2}つけた。",
                'watashi [ ? ] denki [ ? ] tsuketa.',
                '我把灯打开了。',
                [blank_spec('b1', '施动者标识', ['が']), blank_spec('b2', '直接宾语', ['を'])],
                _expl(f"{r('私', 'わたし')}<strong>が</strong>{r('電気', 'でんき')}<strong>を</strong>つけた。", 'watashi ga denki o tsuketa.', '「つける」是他动词，须用「を」带直接宾语，「私が」标识明确施动者。'),
            ),
            fc(
                'fc-jp02-19', '自动词句型：客观状态变化用「が」', ['p-jp02-trans-rule'],
                '描述客观现象（灯自己亮了），填入正确的助词：',
                '電気{{blank:b1}}ついた。',
                f"{r('電気', 'でんき')}{B1}ついた。",
                'denki [ ? ] tsuita.',
                '灯亮了。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('電気', 'でんき')}<strong>が</strong>ついた。", 'denki ga tsuita.', '「つく」是自动词，事物自身作主语用「が」标记。'),
            ),
            fc(
                'fc-jp02-20', '他动词「開けた」配「を」', ['p-jp02-trans-rule'],
                '询问“谁人为打开了窗户？”，填入正确的助词：',
                '誰が窓{{blank:b1}}開けた？',
                f"{r('誰', 'だれ')}が{r('窓', 'まど')}{B1}{r('開', 'あ')}けた？",
                'dare ga mado [ ? ] aketa?',
                '谁把窗户打开的？',
                [blank_spec('b1', '直接宾语助词', ['を'])],
                _expl(f"{r('誰', 'だれ')}が{r('窓', 'まど')}<strong>を</strong>{r('開', 'あ')}けた？", 'dare ga mado o aketa?', '「開ける」是他动词，宾语「窓」配「を」。'),
            ),
            fc(
                'fc-jp02-21', '自动词「開いた」配「が」', ['p-jp02-trans-rule'],
                '询问“窗户怎么自己开了？”，填入正确的助词：',
                '窓{{blank:b1}}どうして開いた？',
                f"{r('窓', 'まど')}{B1}どうして{r('開', 'あ')}いた？",
                'mado [ ? ] dōshite aita?',
                '窗户怎么自己开了？',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('窓', 'まど')}<strong>が</strong>どうして{r('開', 'あ')}いた？", 'mado ga dōshite aita?', '「開く」是自动词，只能以「が」标记「窓」作主语。'),
            ),
            fc(
                'fc-jp02-22', '自他成对动词：閉める ↔ 閉まる', ['p-jp02-trans-pairs'],
                '对应“关门”，请填入表示“门自己关上”的【自动词原形】：',
                'ドアが{{blank:b1}}。',
                f"ドアが{B1}。",
                'doa ga [ ? ].',
                '门关上了。（自动词原形）',
                [blank_spec('b1', '自动词原形', ['閉まる', 'しまる'])],
                _expl(f"ドアが<strong>{r('閉', 'し')}まる</strong>。", 'doa ga shimaru.', '他动词「閉める（shimeru）」对应自动词「閉まる（shimaru）」。'),
            ),
            fc(
                'fc-jp02-23', '自他成对动词：消える ↔ 消す', ['p-jp02-trans-pairs'],
                '对应“灯灭了”，请填入表示“人为关灯”的【他动词原形】：',
                '灯りを{{blank:b1}}。',
                f"{r('灯', 'あか')}りを{B1}。",
                'akari o [ ? ].',
                '把灯关掉（熄灯）。（他动词原形）',
                [blank_spec('b1', '他动词原形', ['消す', 'けす'])],
                _expl(f"{r('灯', 'あか')}りを<strong>{r('消', 'け')}す</strong>。", 'akari o kesu.', '自动词「消える（kieru）」对应他动词「消す（kesu）」。'),
            ),
            fc(
                'fc-jp02-24', '自他成对动词：入れる ↔ 入る', ['p-jp02-trans-pairs'],
                '对应“放进盒里”，请填入表示“进入里面”的【自动词原形】：',
                '箱に{{blank:b1}}。',
                f"{r('箱', 'はこ')}に{B1}。",
                'hako ni [ ? ].',
                '进入盒子里。（自动词原形）',
                [blank_spec('b1', '自动词原形', ['入る', 'はいる'])],
                _expl(f"{r('箱', 'はこ')}に<strong>{r('入', 'はい')}る</strong>。", 'hako ni hairu.', '他动词「入れる（ireru）」对应自动词「入る（hairu）」。'),
            ),
            fc(
                'fc-jp02-25', '「要る」作自动词搭配「が」', ['p-jp02-iru-ga'],
                '使用状态动词「要る（いります）」表达“我需要电脑”，填入正确助词：',
                'パソコン{{blank:b1}}いります。',
                f"パソコン{B1}いります。",
                'pasokon [ ? ] irimasu.',
                '需要电脑。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl('パソコン<strong>が</strong>いります。', 'pasokon ga irimasu.', '「要る」在日语中属于自动词/状态动词，被需要的对象「パソコン」是语法主语，只能接「が」。'),
            ),
            fc(
                'fc-jp02-26', '使用「を」时须改用「必要とする」', ['p-jp02-iru-ga'],
                '当助词已选「を」表达“他需要电脑”时，填入唯一合法的【他动词短语】：',
                '彼がパソコンを{{blank:b1}}。',
                f"{r('彼', 'かれ')}がパソコンを{B1}。",
                'kare ga pasokon o [ ? ].',
                '他需要电脑。（他动词短语）',
                [blank_spec('b1', '他动词短语', ['必要とする', 'ひつようとする'])],
                _expl(f"{r('彼', 'かれ')}がパソコンを<strong>{r('必要', 'ひつよう')}とする</strong>。", 'kare ga pasokon o hitsuyō to suru.', '想用直接宾语「を」时，须改用他动词短语「必要とする」。'),
            ),
            fc(
                'fc-jp02-27', '「分かる」配主格助词「が」', ['p-jp02-iru-ga'],
                '「分かる」与「要る」同属状态自动词，表达“不懂日语”应填：',
                '日本語{{blank:b1}}分からない。',
                f"{r('日本語', 'にほんご')}{B1}{r('分', 'わ')}からない。",
                'nihongo [ ? ] wakaranai.',
                '我不懂日语。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('日本語', 'にほんご')}<strong>が</strong>{r('分', 'わ')}からない。", 'nihongo ga wakaranai.', '理解的对象「日本語」在日语里作「分かる」的语法主语，使用「が」。'),
            ),
            fc(
                'fc-jp02-28', '「A に（は）B が 〜」完整双助词结构', ['p-jp02-ni-experiencer'],
                '补全“对他来说，时间不够”中“对象（to him）”与“主语”助词：',
                '彼{{blank:b1}}時間{{blank:b2}}足りない。',
                f"{r('彼', 'かれ')}{B1}{r('時間', 'じかん')}{B2}{r('足', 'た')}りない。",
                'kare [ ? ] jikan [ ? ] tarinai.',
                '对他而言时间不够。',
                [blank_spec('b1', '对象助词', ['に']), blank_spec('b2', '主语助词', ['が'])],
                _expl(f"{r('彼', 'かれ')}<strong>に</strong>{r('時間', 'じかん')}<strong>が</strong>{r('足', 'た')}りない。", 'kare ni jikan ga tarinai.', '「に」标示“对于 A 而言”，「が」标示真正不足的主体「時間」（亦可主题化为「彼には」）。'),
            ),
            fc(
                'fc-jp02-29', '综合复盘：场所「に・で」与起点「を」', ['p-jp02-ni-vs-de', 'p-jp02-o-marker'],
                '依次填入静态落脚、动态活动域及移动离开起点助词：',
                '本を机の上{{blank:b1}}置く。 ／ 図書館{{blank:b2}}勉強する。 ／ 部屋{{blank:b3}}出る。',
                f"{r('本', 'ほん')}を{r('机', 'つくえ')}の{r('上', 'うえ')}{B1}{r('置', 'お')}く。 ／ {r('図書館', 'としょかん')}{B2}{r('勉強', 'べんきょう')}する。 ／ {r('部屋', 'へや')}{B3}{r('出', 'で')}る。",
                'hon o tsukue no ue [ ? ] oku. / toshokan [ ? ] benkyō suru. / heya [ ? ] deru.',
                '把书放在桌上 ／ 在图书馆学习 ／ 离开房间',
                [blank_spec('b1', '落脚点', ['に']), blank_spec('b2', '活动域', ['で']), blank_spec('b3', '离开起点', ['を'])],
                _expl(f"{r('本', 'ほん')}を{r('机', 'つくえ')}の{r('上', 'うえ')}<strong>に</strong>{r('置', 'お')}く。 ／ {r('図書館', 'としょかん')}<strong>で</strong>{r('勉強', 'べんきょう')}する。 ／ {r('部屋', 'へや')}<strong>を</strong>{r('出', 'で')}る。", 'hon o tsukue no ue ni oku. / toshokan de benkyō suru. / heya o deru.', '静态归宿用「に」，活动场所用「で」，移动脱离起点用「を」。'),
            ),
            fc(
                'fc-jp02-30', '综合复盘：自他动词与「要る」助词搭配', ['p-jp02-trans-rule', 'p-jp02-trans-pairs', 'p-jp02-iru-ga'],
                '补全“打开窗户”（他动词原形）、“窗户开了”（助词）及“需要电脑”（助词）：',
                '窓を{{blank:b1}}。 ／ 窓{{blank:b2}}開く。 ／ パソコン{{blank:b3}}いる。',
                f"{r('窓', 'まど')}を{B1}。 ／ {r('窓', 'まど')}{B2}{r('開', 'あ')}く。 ／ パソコン{B3}いる。",
                'mado o [ ? ]. / mado [ ? ] aku. / pasokon [ ? ] iru.',
                '打开窗户 ／ 窗户开了 ／ 需要电脑',
                [blank_spec('b1', '他动词原形', ['開ける', 'あける']), blank_spec('b2', '自动词主语', ['が']), blank_spec('b3', '「要る」主语', ['が'])],
                _expl(f"{r('窓', 'まど')}を<strong>{r('開', 'あ')}ける</strong>。 ／ {r('窓', 'まど')}<strong>が</strong>{r('開', 'あ')}く。 ／ パソコン<strong>が</strong>いる。", 'mado o akeru. / mado ga aku. / pasokon ga iru.', '他动词「開ける」配「を」，自动词「開く」和状态动词「要る」都配「が」。'),
            ),
            fc(
                'fc-jp02-2222-01', '直接宾语填空：「冷たい水」', ['p-jp02-o-marker'],
                '他动词「飲む」的直接承受对象需用宾语助词标记：',
                '昨日、冷たい水{{blank:b1}}飲んだ。',
                f"{r('昨日', 'きのう')}、{r('冷', 'つめ')}たい{r('水', 'みず')}{B1}{r('飲', 'の')}んだ。",
                'kinō, tsumetai mizu [ ? ] nonda.',
                '昨天喝了冷水。',
                [blank_spec('b1', '宾语助词', ['を'])],
                _expl(f"{r('昨日', 'きのう')}、{r('冷', 'つめ')}たい{r('水', 'みず')}<strong>を</strong>{r('飲', 'の')}んだ。", 'kinō, tsumetai mizu o nonda.', '他动词「飲む」的直接承受对象用宾语助词「を」标示（作为助词读作 o）。'),
            ),
            fc(
                'fc-jp02-2222-02', '移动动词穿行场所「を」', ['p-jp02-o-marker'],
                '移动动词「歩く」搭配经过的路线或空间时，填入正确的格助词：',
                '毎日、学校の近くの道{{blank:b1}}歩く。',
                f"{r('毎日', 'まいにち')}、{r('学校', 'がっこう')}の{r('近', 'ちか')}くの{r('道', 'みち')}{B1}{r('歩', 'ある')}く。",
                'mainichi, gakkō no chikaku no michi [ ? ] aruku.',
                '每天在学校附近的路上散步。',
                [blank_spec('b1', '穿行路径助词', ['を'])],
                _expl(f"{r('毎日', 'まいにち')}、{r('学校', 'がっこう')}の{r('近', 'ちか')}くの{r('道', 'みち')}<strong>を</strong>{r('歩', 'ある')}く。", 'mainichi, gakkō no chikaku no michi o aruku.', '「歩く」「走る」「出る」等移动动词搭配场所时，用「を」表示穿行经过的路径或离开的起点。'),
            ),
            fc(
                'fc-jp02-2222-03', '宾语话题化禁区：禁止「*をは」叠用', ['p-jp02-o-marker'],
                '将直接宾语“日语”提作全句话题时，「を」必须脱落，应填入的话题助词是：',
                '日本語{{blank:b1}}、毎日勉強する。',
                f"{r('日本語', 'にほんご')}{B1}、{r('毎日', 'まいにち')}{r('勉強', 'べんきょう')}する。",
                'nihongo [ ? ], mainichi benkyō suru.',
                '至于日语，每天都会学习。',
                [blank_spec('b1', '话题助词', ['は'])],
                _expl(f"{r('日本語', 'にほんご')}<strong>は</strong>、{r('毎日', 'まいにち')}{r('勉強', 'べんきょう')}する。", 'nihongo wa, mainichi benkyō suru.', '宾语助词「を」绝对不能与话题「は」叠用写成「*をは」，宾语提作话题时「を」必须脱落。'),
            ),
            fc(
                'fc-jp02-2222-04', '移动最终落脚归宿「に」', ['p-jp02-ni-e-diff'],
                '填入锁定移动动词「帰る」最终目的地与归宿的助词：',
                '夜、遅くに家{{blank:b1}}帰る。',
                f"{r('夜', 'よる')}、{r('遅', 'おそ')}くに{r('家', 'いえ')}{B1}{r('帰', 'かえ')}る。",
                'yoru, osoku ni ie [ ? ] kaeru.',
                '晚上很晚才回家。',
                [blank_spec('b1', '目的地助词', ['に'])],
                _expl(f"{r('夜', 'よる')}、{r('遅', 'おそ')}くに{r('家', 'いえ')}<strong>に</strong>{r('帰', 'かえ')}る。", 'yoru, osoku ni ie ni kaeru.', '「帰る」「行く」「来る」等移动动词的最终落脚点由目标助词「に」锁定。'),
            ),
            fc(
                'fc-jp02-2222-05', '自动词「会う」的动作对象点「に」', ['p-jp02-ni-e-diff'],
                '「会う」（见面）属于自动词，不可用「を」；填入标记见面对象点的目标助词：',
                '昨日、駅の前で友達{{blank:b1}}会った。',
                f"{r('昨日', 'きのう')}、{r('駅', 'えき')}の{r('前', 'まえ')}で{r('友達', 'ともだち')}{B1}{r('会', 'あ')}った。",
                'kinō, eki no mae de tomodachi [ ? ] atta.',
                '昨天在车站前遇见了朋友。',
                [blank_spec('b1', '目标对象助词', ['に'])],
                _expl(f"{r('昨日', 'きのう')}、{r('駅', 'えき')}の{r('前', 'まえ')}で{r('友達', 'ともだち')}<strong>に</strong>{r('会', 'あ')}った。", 'kinō, eki no mae de tomodachi ni atta.', '「会う」属于自动词，所面向的对象用目标助词「に」（或伴随「と」）标示，不可用「を」。'),
            ),
            fc(
                'fc-jp02-2222-06', '目标「に」vs 起点「から」对比', ['p-jp02-ni-e-diff'],
                '填入表示来源与起点的助词（意为“从这所学校来的”）：',
                '彼女はこの学校{{blank:b1}}来た。',
                f"{r('彼女', 'かのじょ')}はこの{r('学校', 'がっこう')}{B1}{r('来', 'き')}た。",
                'kanojo wa kono gakkō [ ? ] kita.',
                '她是从这所学校过来的。',
                [blank_spec('b1', '起点助词', ['から'])],
                _expl(f"{r('彼女', 'かのじょ')}はこの{r('学校', 'がっこう')}<strong>から</strong>{r('来', 'き')}た。", 'kanojo wa kono gakkō kara kita.', '「に」指向终点“去到某地”，而表示离开或“来自某处”必须使用起点助词「から」。'),
            ),
            fc(
                'fc-jp02-2222-07', '物理移动朝向「へ」', ['p-jp02-ni-e-diff'],
                '强调“朝日本的方向去了”（助词读作 e），填入方向助词：',
                '友達は昨日、日本{{blank:b1}}行った。',
                f"{r('友達', 'ともだち')}は{r('昨日', 'きのう')}、{r('日本', 'にほん')}{B1}{r('行', 'い')}った。",
                'tomodachi wa kinō, nihon [ ? ] itta.',
                '朋友昨天往日本去了。',
                [blank_spec('b1', '方向助词', ['へ'])],
                _expl(f"{r('友達', 'ともだち')}は{r('昨日', 'きのう')}、{r('日本', 'にほん')}<strong>へ</strong>{r('行', 'い')}った。", 'tomodachi wa kinō, nihon e itta.', '与「に」相比，「へ」侧重移动所朝向的大致方向，在句中固定读作 e（え）。'),
            ),
            fc(
                'fc-jp02-2222-08', '非方向抽象变化纠错：必用「に」', ['p-jp02-ni-e-diff'],
                '成为医生属于身份状态转化而非物理方向，不可误用「へ」，应填入：',
                '弟は来年、医者{{blank:b1}}なる。',
                f"{r('弟', 'おとうと')}は{r('来年', 'らいねん')}、{r('医者', 'いしゃ')}{B1}なる。",
                'otōto wa rainen, isha [ ? ] naru.',
                '弟弟明年要当医生。',
                [blank_spec('b1', '转化目标助词', ['に'])],
                _expl(f"{r('弟', 'おとうと')}は{r('来年', 'らいねん')}、{r('医者', 'いしゃ')}<strong>に</strong>なる。", 'otōto wa rainen, isha ni naru.', '“变成医生”属于状态/身份转化结果，不具有物理位移方向，不能说「*医者へなる」，必须用「に」。'),
            ),
            fc(
                'fc-jp02-2222-09', '交通方式与手段「で」', ['p-jp02-ni-vs-de'],
                '填入标示所乘坐的交通工具与方式的工具/手段助词：',
                '毎日、電車{{blank:b1}}大学に行く。',
                f"{r('毎日', 'まいにち')}、{r('電車', 'でんしゃ')}{B1}{r('大学', 'だいがく')}に{r('行', 'い')}く。",
                'mainichi, densha [ ? ] daigaku ni iku.',
                '每天坐电车去大学。',
                [blank_spec('b1', '手段助词', ['で'])],
                _expl(f"{r('毎日', 'まいにち')}、{r('電車', 'でんしゃ')}<strong>で</strong>{r('大学', 'だいがく')}に{r('行', 'い')}く。", 'mainichi, densha de daigaku ni iku.', '乘坐的交通工具与使用的道具/方式统一由手段助词「で」标示。'),
            ),
            fc(
                'fc-jp02-2222-10', '用餐与动态活动场所「で」', ['p-jp02-ni-vs-de'],
                '“吃午饭”是在某场所内展开的活动事件，填入活动范围助词：',
                '友達と店{{blank:b1}}昼ご飯を食べた。',
                f"{r('友達', 'ともだち')}と{r('店', 'みせ')}{B1}{r('昼', 'ひる')}ご{r('飯', 'はん')}を{r('食', 'た')}べた。",
                'tomodachi to mise [ ? ] hirugohan o tabeta.',
                '和朋友在店里吃了午饭。',
                [blank_spec('b1', '活动场所助词', ['で'])],
                _expl(f"{r('友達', 'ともだち')}と{r('店', 'みせ')}<strong>で</strong>{r('昼', 'ひる')}ご{r('飯', 'はん')}を{r('食', 'た')}べた。", 'tomodachi to mise de hirugohan o tabeta.', '“吃午饭”是在某个场所内展开的具体活动，活动舞台使用领域助词「で」。'),
            ),
            fc(
                'fc-jp02-2222-11', '疑问词「何で（なにで）」询问手段', ['p-jp02-ni-vs-de'],
                '回答给出了交通方式「車で来た」，请补全问句“用什么工具/方式来的？”：',
                '駅まで何{{blank:b1}}来た？ 車で来た。',
                f"{r('駅', 'えき')}まで{r('何', 'なに')}{B1}{r('来', 'き')}た？ {r('車', 'くるま')}で{r('来', 'き')}た。",
                'eki made nani [ ? ] kita? kuruma de kita.',
                '坐什么来车站的？ 开车来的。',
                [blank_spec('b1', '手段助词', ['で'])],
                _expl(f"{r('駅', 'えき')}まで{r('何', 'なに')}<strong>で</strong>{r('来', 'き')}た？ {r('車', 'くるま')}で{r('来', 'き')}た。", 'eki made nani de kita? kuruma de kita.', '答句为交通工具「車で」，说明问句中的「何で」读作 nani de（用什么手段），而非表原因的 nan de。'),
            ),
            fc(
                'fc-jp02-2222-12', '静态存在点「に」：「小さい猫」', ['p-jp02-ni-vs-de'],
                '「いる」仅表达人或动物静态存在的位置，填入静态存在点助词：',
                '小さい猫は部屋{{blank:b1}}いる。',
                f"{r('小', 'ちい')}さい{r('猫', 'ねこ')}は{r('部屋', 'へや')}{B1}いる。",
                'chiisai neko wa heya [ ? ] iru.',
                '小猫在房间里。',
                [blank_spec('b1', '存在点助词', ['に'])],
                _expl(f"{r('小', 'ちい')}さい{r('猫', 'ねこ')}は{r('部屋', 'へや')}<strong>に</strong>いる。", 'chiisai neko wa heya ni iru.', '「いる / ある」只表示人或物的静态存在位置，不存在动作过程，必须用存在点助词「に」。'),
            ),
            fc(
                'fc-jp02-2222-13', '物品最终落脚点「に」：「机の上に置く」', ['p-jp02-ni-vs-de'],
                '「置く」聚焦动作结束后物品最终停放附着的位置，填入落脚点助词：',
                '買った本を机の上{{blank:b1}}置く。',
                f"{r('買', 'か')}った{r('本', 'ほん')}を{r('机', 'つくえ')}の{r('上', 'うえ')}{B1}{r('置', 'お')}く。",
                'katta hon o tsukue no ue [ ? ] oku.',
                '把买来的书放在桌子上。',
                [blank_spec('b1', '落脚点助词', ['に'])],
                _expl(f"{r('買', 'か')}った{r('本', 'ほん')}を{r('机', 'つくえ')}の{r('上', 'うえ')}<strong>に</strong>{r('置', 'お')}く。", 'katta hon o tsukue no ue ni oku.', '「置く」聚焦于物品最终停放附着的位置，故用静态落脚点助词「に」。'),
            ),
            fc(
                'fc-jp02-2222-14', '动态行为发生范围「で」：「公園で本を読んだ」', ['p-jp02-ni-vs-de'],
                '“看书”是持续展开的动作事件，「公園」作为活动舞台应填：',
                '休みの日に公園{{blank:b1}}本を読んだ。',
                f"{r('休', 'やす')}みの{r('日', 'ひ')}に{r('公園', 'こうえん')}{B1}{r('本', 'ほん')}を{r('読', 'よ')}んだ。",
                'yasumi no hi ni kōen [ ? ] hon o yonda.',
                '休息日在公园里看了书。',
                [blank_spec('b1', '活动范围助词', ['で'])],
                _expl(f"{r('休', 'やす')}みの{r('日', 'ひ')}に{r('公園', 'こうえん')}<strong>で</strong>{r('本', 'ほん')}を{r('読', 'よ')}んだ。", 'yasumi no hi ni kōen de hon o yonda.', '“看书（読む）”是持续进行的动作事件，「公園」为事件开展的空间范围，须用「で」。'),
            ),
            fc(
                'fc-jp02-2222-15', '避免双重「を」：直接复合动词「勉強する」', ['p-jp02-double-o'],
                '同一句中前面已有「日本語を」，避免双重「を」违规，直接补全复合动词词尾（“做/学习”）：',
                '毎日、部屋で日本語を勉強{{blank:b1}}。',
                f"{r('毎日', 'まいにち')}、{r('部屋', 'へや')}で{r('日本語', 'にほんご')}を{r('勉強', 'べんきょう')}{B1}。",
                'mainichi, heya de nihongo o benkyō [ ? ].',
                '每天在房间里学习日语。',
                [blank_spec('b1', '复合动词词尾', ['する'])],
                _expl(f"{r('毎日', 'まいにち')}、{r('部屋', 'へや')}で{r('日本語', 'にほんご')}を{r('勉強', 'べんきょう')}<strong>する</strong>。", 'mainichi, heya de nihongo o benkyō suru.', '同一动词领地内禁止连用两个「を」；前面已有「日本語を」时，后面直接将「勉強する」视作整体复合动词。'),
            ),
            fc(
                'fc-jp02-2222-16', '避免双重「を」：用「の」合并名词短语', ['p-jp02-double-o'],
                '若句尾保留「をする」，前面须先用连接助词把「日本語」与「勉強」合成一个名词短语：',
                '毎日、日本語{{blank:b1}}勉強をする。',
                f"{r('毎日', 'まいにち')}、{r('日本語', 'にほんご')}{B1}{r('勉強', 'べんきょう')}をする。",
                'mainichi, nihongo [ ? ] benkyō o suru.',
                '每天进行日语的学习。',
                [blank_spec('b1', '连接助词', ['の'])],
                _expl(f"{r('毎日', 'まいにち')}、{r('日本語', 'にほんご')}<strong>の</strong>{r('勉強', 'べんきょう')}をする。", 'mainichi, nihongo no benkyō o suru.', '若保留「をする」，须把前面的「日本語」改用「の」连成整体名词短语「日本語の勉強」，再接单一「を」。'),
            ),
            fc(
                'fc-jp02-2222-17', '他动词＋直接宾语：「私が電気をつけた」', ['p-jp02-trans-rule'],
                '「つける」是由人主动施加动作的他动词，承受对象「電気」后应填：',
                '部屋が暗いから、私が電気{{blank:b1}}つけた。',
                f"{r('部屋', 'へや')}が{r('暗', 'くら')}いから、{r('私', 'わたし')}が{r('電気', 'でんき')}{B1}つけた。",
                'heya ga kurai kara, watashi ga denki [ ? ] tsuketa.',
                '因为房间暗，我把灯打开了。',
                [blank_spec('b1', '直接宾语助词', ['を'])],
                _expl(f"{r('部屋', 'へや')}が{r('暗', 'くら')}いから、{r('私', 'わたし')}が{r('電気', 'でんき')}<strong>を</strong>つけた。", 'heya ga kurai kara, watashi ga denki o tsuketa.', '「つける」是明确由人施加动作的他动词，承受对象「電気」须用「を」。'),
            ),
            fc(
                'fc-jp02-2222-18', '自动词客观现象：「スイッチを押すと電気がついた」', ['p-jp02-trans-rule'],
                '无需施动者主语，「つく」仅描述灯自然亮起的客观状态，应填入：',
                'スイッチを押すと、電気{{blank:b1}}ついた。',
                f"スイッチを{r('押', 'お')}すと、{r('電気', 'でんき')}{B1}ついた。",
                'suitchi o osu to, denki [ ? ] tsuita.',
                '按下开关后，灯亮了。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"スイッチを{r('押', 'お')}すと、{r('電気', 'でんき')}<strong>が</strong>ついた。", 'suitchi o osu to, denki ga tsuita.', '「つく」是描述自然亮起状态的自动词，不能带「を」，现象主体「電気」用「が」标记。'),
            ),
            fc(
                'fc-jp02-2222-19', '自动词误接「を」改错：「どうして窓が開いた？」', ['p-jp02-trans-rule'],
                '修正误句「*窓を開いた」：「開く（あく）」是不带宾语的自动词，助词应改为：',
                'どうして窓{{blank:b1}}開いた？',
                f"どうして{r('窓', 'まど')}{B1}{r('開', 'あ')}いた？",
                'dōshite mado [ ? ] aita?',
                '为什么窗户自己开了？',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"どうして{r('窓', 'まど')}<strong>が</strong>{r('開', 'あ')}いた？", 'dōshite mado ga aita?', '「開く（あく）」是不带直接宾语的自动词，原误句「*窓を開いた」的「を」必须改成「が」（或话题「は」）。'),
            ),
            fc(
                'fc-jp02-2222-20', '自他成对活用：「開ける」vs「開く」', ['p-jp02-trans-pairs'],
                '请从「開ける / 開く」中选用合适动词的【过去简体】（注意句中有施动者与宾语「窓を」）：',
                '寒いから、誰が窓を{{blank:b1}}？',
                f"{r('寒', 'さむ')}いから、{r('誰', 'だれ')}が{r('窓', 'まど')}を{B1}？",
                'samui kara, dare ga mado o [ ? ]?',
                '好冷啊，是谁把窗户打开了？',
                [blank_spec('b1', '他动词过去简体', ['開けた', 'あけた'])],
                _expl(f"{r('寒', 'さむ')}いから、{r('誰', 'だれ')}が{r('窓', 'まど')}を<strong>{r('開', 'あ')}けた</strong>？", 'samui kara, dare ga mado o aketa?', '句中有施动者「誰が」且宾语是「窓を」，必须选用他动词「開ける」的过去形「開けた」。'),
            ),
            fc(
                'fc-jp02-2222-21', '自他成对活用：「閉める」vs「閉まる」', ['p-jp02-trans-pairs'],
                '请用「閉める / 閉まる」中合适动词的【过去简体】（注意主语是「ドアが」）：',
                '風が吹いて、ドアが{{blank:b1}}。',
                f"{r('風', 'かぜ')}が{r('吹', 'ふ')}いて、ドアが{B1}。",
                'kaze ga fuite, doa ga [ ? ].',
                '风一吹，门关上了。',
                [blank_spec('b1', '自动词过去简体', ['閉まった', 'しまった'])],
                _expl(f"{r('風', 'かぜ')}が{r('吹', 'ふ')}いて、ドアが<strong>{r('閉', 'し')}まった</strong>。", 'kaze ga fuite, doa ga shimatta.', '主语「ドアが」自然闭合而非人为去关，应选自动词「閉まる」（过去五段促音变「閉まった」）。'),
            ),
            fc(
                'fc-jp02-2222-22', '综合复盘：自他成对动词「落とす」vs「落ちる」与「を」', ['p-jp02-trans-rule', 'p-jp02-trans-pairs'],
                '注意前面助词为「を」，请从「落とす / 落ちる」中选用合适动词的【过去简体】：',
                '机から本を{{blank:b1}}。',
                f"{r('机', 'つくえ')}から{r('本', 'ほん')}を{B1}。",
                'tsukue kara hon o [ ? ].',
                '把书从桌子上弄掉了。',
                [blank_spec('b1', '他动词过去简体', ['落とした', 'おとした'])],
                _expl(f"{r('机', 'つくえ')}から{r('本', 'ほん')}を<strong>{r('落', 'お')}とした</strong>。", 'tsukue kara hon o otoshita.', '「本を」表明书是承受动作的宾语，必须配对他动词「落とす」→「落とした」（自动词为「落ちる→落ちた」）。'),
            ),
            fc(
                'fc-jp02-2222-23', '及物度标度：「要る」的唯一格助词搭配', ['p-jp02-iru-ga'],
                '「要る」在日语里属自动词/状态动词，所需要之物是语法主语，应填入：',
                '私には新しい車{{blank:b1}}要る。',
                f"{r('私', 'わたし')}には{r('新', 'あたら')}しい{r('車', 'くるま')}{B1}{r('要', 'い')}る。",
                'watashi ni wa atarashii kuruma [ ? ] iru.',
                '我需要一辆新车。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('私', 'わたし')}には{r('新', 'あたら')}しい{r('車', 'くるま')}<strong>が</strong>{r('要', 'い')}る。", 'watashi ni wa atarashii kuruma ga iru.', '「要る」属自动词/状态动词，所需之物「車」是语法主语，必须接「が」，不可说「*車を要る」；想用「を」须改用「必要とする」。'),
            ),
            fc(
                'fc-jp02-2222-24', '综合复盘：认知自动词「分かる」与「A には B が」结构', ['p-jp02-iru-ga', 'p-jp02-ni-experiencer'],
                '「分かる」与「要る」同理，对象是语法主语（不可用「を」），在「彼には」后补全主格助词：',
                '彼には簡単な日本語{{blank:b1}}分かる。',
                f"{r('彼', 'かれ')}には{r('簡単', 'かんたん')}な{r('日本語', 'にほんご')}{B1}{r('分', 'わ')}かる。",
                'kare ni wa kantan na nihongo [ ? ] wakaru.',
                '他懂简单的日语。',
                [blank_spec('b1', '主格助词', ['が'])],
                _expl(f"{r('彼', 'かれ')}には{r('簡単', 'かんたん')}な{r('日本語', 'にほんご')}<strong>が</strong>{r('分', 'わ')}かる。", 'kare ni wa kantan na nihongo ga wakaru.', '「分かる」和「要る」同属状态自动词，体验者用「に（は）」、对象用「が」；只有换用他动词短语如「必要とする」「理解する」时才用「を」。'),
            ),
        ],
    },
    # =========================================================================
    # Topic 3: jp03-adjectives-and-mo
    # =========================================================================
    {
        'id': 'jp03-adjectives-and-mo',
        'title': '3. 形容词活用与包含助词「も」',
        'sections': [
            {
                'id': 'sec-jp03-adj',
                'title': '一、い形容词与な形容词的分类及四大基础活用表',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp03-mo',
                'title': '二、包含助词「も」的覆盖规则与六大衍生用法',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp03-adj',
                'section_id': 'sec-jp03-adj',
                'title': 'い形容词与な形容词的识别法则与两张完整活用表',
                'html': (
                    '<h3>一、快速识别：如何区分「い形容词」与「な形容词」</h3>'
                    '<p>日语形容词分为两大阵营：<strong>い形容词（i-形容词）</strong>自身词尾可发生活用；<strong>な形容词（na-形容词 / 形容动词）</strong>本质像名词一样，自身词干不变，必须靠后面的断定词完成变化。</p>'
                    '<ul>'
                    '<li><strong>い形容词特征</strong>：原形字典形必然以 <code>-ii, -ai, -oi, -ui</code> 结尾，且末尾的「い」作为<strong>送假名独立露在汉字外面</strong>，例如 '
                    + term(f"{r('高', 'たか')}い", 'takai', '高/贵') + '、'
                    + term(f"{r('美味', 'おい')}しい", 'oishii', '好吃') + '、'
                    + term(f"{r('広', 'ひろ')}い", 'hiroi', '宽敞') + '。</li>'
                    '<li><strong>な形容词与“伪装者”识别</strong>：词尾不符合 <code>-ii, -ai, -oi, -ui</code> 规律（如 '
                    + term(f"{r('有名', 'ゆうめい')}", 'yūmei', '有名') + '、'
                    + term(f"{r('静', 'しず')}か", 'shizuka', '安静') + '），或者虽以 /i/ 结尾但属 <code>-ei</code>（或假名包在汉字内部）的词，例如 '
                    + term(f"{r('綺麗', 'きれい')}／きれい", 'kirei', '漂亮，-ei 结尾') + '，都属于<strong>な形容词</strong>！</li>'
                    '</ul>'
                    '<h3>二、い形容词四大基础活用（以「高い」为例）</h3>'
                    '<p>变形规则极为统一：<strong>去掉词尾「い」，替换为对应词尾</strong>。</p>'
                    + tbl(
                        ['时态 / 语态', '变形规则', '简体示例（高い）', '敬体示例'],
                        [
                            ['非过去肯定', '原形', term(f"{r('高', 'たか')}い", 'takai', '高'), f"{r('高', 'たか')}い<strong>です</strong>"],
                            ['非过去否定', '去「い」+ <strong>くない</strong>', term(f"{r('高', 'たか')}くない", 'takakunai', '不高'), f"{r('高', 'たか')}くない<strong>です</strong> ／ {r('高', 'たか')}く<strong>ありません</strong>"],
                            ['过去肯定', '去「い」+ <strong>かった</strong>', term(f"{r('高', 'たか')}かった", 'takakatta', '过去高'), f"{r('高', 'たか')}かった<strong>です</strong>"],
                            ['过去否定', '去「い」+ <strong>くなかった</strong>', term(f"{r('高', 'たか')}くなかった", 'takakunakatta', '过去不高'), f"{r('高', 'たか')}くなかった<strong>です</strong> ／ {r('高', 'たか')}く<strong>ありませんでした</strong>"],
                        ],
                    )
                    + '<h3>三、な形容词四大基础活用（以「静か」为例）</h3>'
                    '<p>な形容词直接复用名词状态断定变形：</p>'
                    + tbl(
                        ['时态 / 语态', '变形规则', '简体示例（静か）', '敬体示例'],
                        [
                            ['非过去肯定', '词干 + (<strong>だ</strong>)', term(f"{r('静', 'しず')}か（だ）", 'shizuka (da)', '安静'), f"{r('静', 'しず')}か<strong>です</strong>"],
                            ['非过去否定', '词干 + <strong>じゃない</strong>', term(f"{r('静', 'しず')}かじゃない", 'shizuka janai', '不安静'), f"{r('静', 'しず')}かじゃない<strong>です</strong> ／ {r('静', 'しず')}か<strong>ではありません</strong>"],
                            ['过去肯定', '词干 + <strong>だった</strong>', term(f"{r('静', 'しず')}かだった", 'shizuka datta', '过去安静'), f"{r('静', 'しず')}か<strong>でした</strong>"],
                            ['过去否定', '词干 + <strong>じゃなかった</strong>', term(f"{r('静', 'しず')}かじゃなかった", 'shizuka janakatta', '过去不安静'), f"{r('静', 'しず')}かじゃなかった<strong>です</strong> ／ {r('静', 'しず')}か<strong>ではありませんでした</strong>"],
                        ],
                    )
                ),
            },
            {
                'id': 'intro-jp03-mo',
                'section_id': 'sec-jp03-mo',
                'title': '包含助词「も」的替代与叠加规律及六大衍生表达',
                'html': (
                    '<h3>一、包含助词「も」与「は/が/を」覆盖、其他格助词叠加</h3>'
                    '<p>助词「も」（mo）被称为<strong>包含主题助词（Inclusive Topic Particle）</strong>，意为“也（also / too / either）”。不同于「は」单独挑出主题，「も」提示新对象归入同性质的已知集合。</p>'
                    '<ul>'
                    '<li><strong>直接覆盖取代「は」「が」「を」</strong>：作用于主语或直接宾语时直接替换原本的 <code>は / が / を</code>，绝不能叠写成 <code>*がも</code> 或 <code>*をも</code>：'
                    + ex(f"{r('千葉', 'ちば')}さんは{r('先生', 'せんせい')}です。{r('山田', 'やまだ')}さん<strong>も</strong>{r('先生', 'せんせい')}です。", 'chiba-san wa sensei desu. yamada-san mo sensei desu.', '千叶先生是老师。山田女士也是老师。', '取代主语は/が')
                    + ex(f"{r('新聞', 'しんぶん')}を{r('買', 'か')}いました。{r('雑誌', 'ざっし')}<strong>も</strong>{r('買', 'か')}いました。", 'shinbun o kaimashita. zasshi mo kaimashita.', '买了报纸。也买了杂志。', '直接覆盖宾语「を」')
                    + ex(f"{r('新聞', 'しんぶん')}は{r('買', 'か')}いませんでした。{r('雑誌', 'ざっし')}<strong>も</strong>{r('買', 'か')}いませんでした。", 'shinbun wa kaimasen deshita. zasshi mo kaimasen deshita.', '没买报纸。也没有买杂志。', '否定句表“也不……”')
                    + '</li>'
                    '<li><strong>与其他格助词（から・へ・に・で）后置叠加</strong>：「も」必须紧跟在这些格助词<strong>后面</strong>：'
                    + ex(f"{r('沖縄', 'おきなわ')}から<strong>も</strong>{r('代表', 'だいひょう')}が{r('来', 'き')}ました。", 'okinawa kara mo daihyō ga kimashita.', '也有代表从冲绳赶来。', 'から + も')
                    + ex(f"{r('長野', 'ながの')}へ<strong>も</strong>{r('行', 'い')}きました。", 'nagano e mo ikimashita.', '也去了长野。', 'へ + も')
                    + '</li>'
                    '</ul>'
                    '<h3>二、「も」的六大衍生拓展用法</h3>'
                    '<ol>'
                    '<li><strong>疑问词 +（格助词）+ も + 否定 = 全盘否定</strong>：'
                    + ex(f"{r('誰', 'だれ')}も{r('知', 'し')}らない。 ／ {r('何', 'なに')}もない。 ／ どこに<strong>も</strong>{r('行', 'い')}かなかった。", 'dare mo shiranai. / nani mo nai. / doko ni mo ikanakatta.', '谁也不知道。／ 什么也没有。／ 哪儿也没去。', '「に」排在「も」前')
                    + '</li>'
                    '<li><strong>数量词 + も = 强调数量之多/超出预期</strong>：'
                    + ex(f"{r('昨日', 'きのう')}、{r('電話', 'でんわ')}{r('三回', 'さんかい')}<strong>も</strong>したよ！", 'kinō, denwa sankai mo shita yo!', '昨天足足打了三次电话！')
                    + ex(f"{r('試験', 'しけん')}のために{r('三時間', 'さんじかん')}<strong>も</strong>{r('勉強', 'べんきょう')}した。", 'shiken no tame ni sanjikan mo benkyō shita.', '为了考试整整学了三个小时。')
                    + ex(f"{r('今年', 'ことし')}、{r('十', 'じゅっ')}キロ<strong>も</strong>{r('太', 'ふと')}っちゃった！", 'kotoshi, jukkiro mo futotchatta!', '今年竟然胖了整整十公斤！')
                    + '</li>'
                    '<li><strong>动词 て 形 + も = 许可与让步（即使……也 / 可以……）</strong>：<code>〜てもいい / 〜ても大丈夫 / 〜ても構わない</code> 表允许；<code>〜なくてもいい</code> 表不必：'
                    + ex(f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べてもいいよ。 ／ {r('全部', 'ぜんぶ')}{r('飲', 'の')}んでも{r('大丈夫', 'だいじょうぶ')}だよ。", 'zenbu tabete mo ii yo. / zenbu nonde mo daijōbu da yo.', '全部吃掉也可以哦。／ 全部喝掉也没关系。')
                    + ex(f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べなくてもいいよ。", 'zenbu tabenakute mo ii yo.', '不需要全部吃完（不吃也可以）。')
                    + '</li>'
                    '<li><strong>疑问词 + より + (も) = 最高级表达</strong>：'
                    + ex(f"{r('商品', 'しょうひん')}の{r('品質', 'ひんしつ')}を{r('何', 'なに')}より{r('大切', 'たいせつ')}にしています。", 'shōhin no hinshitsu o nani yori taisetsu ni shite imasu.', '把产品质量看得比什么都重要。')
                    + ex(f"この{r('仕事', 'しごと')}は{r('誰', 'だれ')}よりも{r('早', 'はや')}くできます。", 'kono shigoto wa dare yori mo hayaku dekimasu.', '这工作我做起来比任何人都快。')
                    + '</li>'
                    '<li><strong>接续助词「ながら」+ も = 转折让步（尽管……也……）</strong>：'
                    + ex(f"{r('残念', 'ざんねん')}ながらも ／ {r('貧乏', 'びんぼう')}ながらも", 'zannen nagara mo / binbō nagara mo', '虽然很遗憾…… ／ 尽管贫穷……')
                    + '</li>'
                    '<li><strong>句中多成员叠用「A も B も」（既……也……）</strong>：'
                    + ex(f"{r('弟', 'おとうと')}さん<strong>も</strong>{r('妹', 'いもうと')}さん<strong>も</strong>{r('来', 'き')}ました。", 'otōto-san mo imōto-san mo kimashita.', '弟弟和妹妹都来了。')
                    + '</li>'
                    '</ol>'
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp03-adj-classify',
                'introduction_id': 'intro-jp03-adj',
                'title': 'い形容词与な形容词的拼写和音节识别法',
                'html': '<p>い形容词末假名「い」露在汉字外且呈 -ii/-ai/-oi/-ui；きれい(-ei)、静か、有名等属な形容词。</p>',
                'anchor_quotes': ['一、快速识别：如何区分「い形容词」与「な形容词」'],
                'points': [
                    {'id': 'p-jp03-adj-id', 'text': 'い形容词词尾为 -ii/-ai/-oi/-ui 且末尾「い」为独立送假名；きれい（-ei）、静か、有名等属于な形容词。'},
                ],
            },
            {
                'id': 'chunk-jp03-adj-tables',
                'introduction_id': 'intro-jp03-adj',
                'title': 'い形容词与な形容词四大基础活用表',
                'html': '<p>い形容词去「い」换 くない/かった/くなかった；な形容词复用名词断定 だ/じゃない/だった/じゃなかった。</p>',
                'anchor_quotes': ['二、い形容词四大基础活用（以「高い」为例）', '三、な形容词四大基础活用（以「静か」为例）'],
                'points': [
                    {'id': 'p-jp03-i-neg-past', 'text': 'い形容词去「い」分别换「くない」（否定）、「かった」（过去）、「くなかった」（过去否定），敬体否定另可接「くありません（でした）」。'},
                    {'id': 'p-jp03-na-conj', 'text': 'な形容词词干后直接接「だ/です」「じゃない/ではありません」「だった/でした」「じゃなかった/ではありませんでした」。'},
                ],
            },
            {
                'id': 'chunk-jp03-mo-replace',
                'introduction_id': 'intro-jp03-mo',
                'title': '「も」覆盖「は/が/を」与后置叠加「から/へ/に/で」',
                'html': '<p>「も」直接替换「は/が/を」（禁用 *がも/*をも），而在「から・へ・に・で」之后叠写。</p>',
                'anchor_quotes': ['一、包含助词「も」与「は/が/を」覆盖、其他格助词叠加'],
                'points': [
                    {'id': 'p-jp03-mo-overwrite', 'text': '「も」会直接覆盖取代主格「は/が」和宾格「を」（如 雑誌も買いました），绝不叠写成 *がも 或 *をも。'},
                    {'id': 'p-jp03-mo-stack', 'text': '与「から」「へ」「に」「で」连用时，「も」必须排在这些格助词后面（沖縄からも、長野へも、どこにも）。'},
                ],
            },
            {
                'id': 'chunk-jp03-mo-extensions',
                'introduction_id': 'intro-jp03-mo',
                'title': '「も」的六大衍生用法（全盘否定・数量・て形・最高级・ながらも）',
                'html': '<p>疑问词+も+否定=全盘否定；数量词+も表惊讶数量；〜てもいい表允许；谁よりも表最高级。</p>',
                'anchor_quotes': ['二、「も」的六大衍生拓展用法'],
                'points': [
                    {'id': 'p-jp03-mo-wh-neg', 'text': '「疑问词 + (格助词) + も + 否定」表示全盘否定（誰も知らない、何もない、どこにも行かなかった）。'},
                    {'id': 'p-jp03-mo-qty-more', 'text': '「数量词+も」强调数量大；「〜てもいい/〜なくてもいい」表许可与不必；「疑问词+より(も)」表最高级；「ながらも」表让步；「AもBも」表两者皆是。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp03-01', '伪装な形容词「きれい」修饰名词', ['p-jp03-adj-id'],
                '请填入“漂亮（きれい）”修饰后面名词时的正确形式：',
                '{{blank:b1}}部屋',
                f"{B1}{r('部屋', 'へや')}",
                '[ ? ] heya',
                '漂亮的房间',
                [blank_spec('b1', '漂亮（连体）', ['きれいな', '綺麗な'])],
                _expl(f"<strong>{r('綺麗', 'きれい')}な</strong>{r('部屋', 'へや')}", 'kirei na heya', '「きれい」以 -ei 结尾（非 -ii/-ai/-oi/-ui），是な形容词，修饰名词须加「な」。'),
            ),
            fc(
                'fc-jp03-02', 'い形容词「広い」直接修饰名词', ['p-jp03-adj-id'],
                '请填入“宽敞（広い）”修饰后面名词时的正确形式：',
                '{{blank:b1}}部屋',
                f"{B1}{r('部屋', 'へや')}",
                '[ ? ] heya',
                '宽敞的房间',
                [blank_spec('b1', '宽敞的', ['広い', 'ひろい'])],
                _expl(f"<strong>{r('広', 'ひろ')}い</strong>{r('部屋', 'へや')}", 'hiroi heya', '「広い（hiroi）」以 -oi 结尾且「い」在汉字外，直接用原形修饰名词。'),
            ),
            fc(
                'fc-jp03-03', 'い形容词非过去否定简体', ['p-jp03-i-neg-past'],
                '将「高い（高/贵）」变为【非过去否定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（高い → 非过去否定简体）',
                '不高 / 不贵（简体）',
                [blank_spec('b1', '非过去否定简体', ['高くない', 'たかくない'])],
                _expl(f"<strong>{r('高', 'たか')}くない</strong>", 'takakunai', 'い形容词变非过去否定：去掉「い」加「くない」。'),
            ),
            fc(
                'fc-jp03-04', 'い形容词过去肯定简体', ['p-jp03-i-neg-past'],
                '将「高い（高/贵）」变为【过去肯定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（高い → 过去肯定简体）',
                '过去高 / 过去贵（简体）',
                [blank_spec('b1', '过去肯定简体', ['高かった', 'たかかった'])],
                _expl(f"<strong>{r('高', 'たか')}かった</strong>", 'takakatta', 'い形容词变过去肯定：去掉「い」加「かった」。'),
            ),
            fc(
                'fc-jp03-05', 'い形容词过去否定简体', ['p-jp03-i-neg-past'],
                '将「高い（高/贵）」变为【过去否定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（高い → 过去否定简体）',
                '过去不高 / 过去不贵（简体）',
                [blank_spec('b1', '过去否定简体', ['高くなかった', 'たかくなかった'])],
                _expl(f"<strong>{r('高', 'たか')}くなかった</strong>", 'takakunakatta', 'い形容词变过去否定：去掉「い」加「くなかった」。'),
            ),
            fc(
                'fc-jp03-06', 'い形容词过去否定敬体（〜ありませんでした式）', ['p-jp03-i-neg-past'],
                '用「ありません」系正式敬体写出「高い（高/贵）」的【过去否定】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（高い → 正式过去否定敬体）',
                '过去不高（正式敬体）',
                [blank_spec('b1', '过去否定敬体', ['高くありませんでした', 'たかくありませんでした'])],
                _expl(f"<strong>{r('高', 'たか')}くありませんでした</strong>", 'takaku arimasen deshita', 'い形容词「高い」除了「高くなかったです」，也可用更礼貌的「高くありませんでした」。'),
            ),
            fc(
                'fc-jp03-07', 'な形容词非过去否定简体', ['p-jp03-na-conj'],
                '写出な形容词「静か（安静）」的【非过去否定简体】（口语或书面皆可）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（静か → 非过去否定简体）',
                '不安静（简体）',
                [blank_spec('b1', '非过去否定简体', ['静かじゃない', '静かではない', 'しずかじゃない', 'しずかではない'])],
                _expl(f"<strong>{r('静', 'しず')}かじゃない</strong>（书面：{r('静', 'しず')}かではない）", 'shizuka janai / shizuka dewa nai', 'な形容词否定直接复用名词规则：词干 + 「じゃない / ではない」。'),
            ),
            fc(
                'fc-jp03-08', 'な形容词过去肯定简体', ['p-jp03-na-conj'],
                '写出な形容词「静か」的【过去肯定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（静か → 过去肯定简体）',
                '过去很安静（简体）',
                [blank_spec('b1', '过去肯定简体', ['静かだった', 'しずかだった'])],
                _expl(f"<strong>{r('静', 'しず')}かだった</strong>", 'shizuka datta', 'な形容词过去肯定复用名词规则：词干 + 「だった」。'),
            ),
            fc(
                'fc-jp03-09', 'な形容词过去肯定敬体', ['p-jp03-na-conj'],
                '写出な形容词「静か」的【过去肯定敬体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（静か → 过去肯定敬体）',
                '过去很安静（敬体）',
                [blank_spec('b1', '过去肯定敬体', ['静かでした', 'しずかでした'])],
                _expl(f"<strong>{r('静', 'しず')}かでした</strong>", 'shizuka deshita', 'な形容词过去肯定敬体为「词干 + でした」。'),
            ),
            fc(
                'fc-jp03-10', 'な形容词过去否定简体', ['p-jp03-na-conj'],
                '写出な形容词「静か」的【过去否定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（静か → 过去否定简体）',
                '过去不安静（简体）',
                [blank_spec('b1', '过去否定简体', ['静かじゃなかった', '静かではなかった', 'しずかじゃなかった', 'しずかではなかった'])],
                _expl(f"<strong>{r('静', 'しず')}かじゃなかった</strong>（书面：{r('静', 'しず')}かではなかった）", 'shizuka janakatta / shizuka dewa nakatta', 'な形容词过去否定复用名词规则：词干 + 「じゃなかった / ではなかった」。'),
            ),
            fc(
                'fc-jp03-11', '「も」覆盖主语助词「は/が」', ['p-jp03-mo-overwrite'],
                '用包含助词覆盖原本的「は」，表示“山田女士也是老师”：',
                '千葉さんは先生です。山田さん{{blank:b1}}先生です。',
                f"{r('千葉', 'ちば')}さんは{r('先生', 'せんせい')}です。{r('山田', 'やまだ')}さん{B1}{r('先生', 'せんせい')}です。",
                'chiba-san wa sensei desu. yamada-san [ ? ] sensei desu.',
                '千叶先生是老师。山田女士也是老师。',
                [blank_spec('b1', '包含助词', ['も'])],
                _expl(f"{r('山田', 'やまだ')}さん<strong>も</strong>{r('先生', 'せんせい')}です。", 'yamada-san mo sensei desu.', '「も」会直接替代主语助词「は」或「が」（不可写 *はも/*がも）。'),
            ),
            fc(
                'fc-jp03-12', '「も」直接覆盖宾语助词「を」', ['p-jp03-mo-overwrite'],
                '在宾语位置加入“也”的语义（绝对不能写出「*をも」）：',
                '新聞を買いました。雑誌{{blank:b1}}買いました。',
                f"{r('新聞', 'しんぶん')}を{r('買', 'か')}いました。{r('雑誌', 'ざっし')}{B1}{r('買', 'か')}いました。",
                'shinbun o kaimashita. zasshi [ ? ] kaimashita.',
                '买了报纸。也买了杂志。',
                [blank_spec('b1', '包含助词', ['も'])],
                _expl(f"{r('雑誌', 'ざっし')}<strong>も</strong>{r('買', 'か')}いました。", 'zasshi mo kaimashita.', '在直接宾语位置，「も」直接取代「を」，禁止出现「*をも」。'),
            ),
            fc(
                'fc-jp03-13', '否定句中「も」表“也不……”', ['p-jp03-mo-overwrite'],
                '填入覆盖宾格、与否定谓语配合表“也没有买杂志”的助词：',
                '新聞は買いませんでした。雑誌{{blank:b1}}買いませんでした。',
                f"{r('新聞', 'しんぶん')}は{r('買', 'か')}いませんでした。{r('雑誌', 'ざっし')}{B1}{r('買', 'か')}いませんでした。",
                'shinbun wa kaimasen deshita. zasshi [ ? ] kaimasen deshita.',
                '没买报纸。也没有买杂志。',
                [blank_spec('b1', '包含助词', ['も'])],
                _expl(f"{r('雑誌', 'ざっし')}<strong>も</strong>{r('買', 'か')}いませんでした。", 'zasshi mo kaimasen deshita.', '与否定动词搭配时，「も」表示“（……）也不……”。'),
            ),
            fc(
                'fc-jp03-14', '「も」叠加在「から」之后', ['p-jp03-mo-stack'],
                '按“先起点助词，再包含助词”的严格次序，补全“也有代表从冲绳赶来”：',
                '沖縄{{blank:b1}}{{blank:b2}}代表が来ました。',
                f"{r('沖縄', 'おきなわ')}{B1}{B2}{r('代表', 'だいひょう')}が{r('来', 'き')}ました。",
                'okinawa [ ? ] [ ? ] daihyō ga kimashita.',
                '也有代表从冲绳赶来。',
                [blank_spec('b1', '起点助词', ['から']), blank_spec('b2', '包含助词', ['も'])],
                _expl(f"{r('沖縄', 'おきなわ')}<strong>からも</strong>{r('代表', 'だいひょう')}が{r('来', 'き')}ました。", 'okinawa kara mo daihyō ga kimashita.', '起点助词「から」必须写在「も」的前面，构成「からも」。'),
            ),
            fc(
                'fc-jp03-15', '「も」叠加在方向助词「へ」之后', ['p-jp03-mo-stack'],
                '按正确语序依次填入方向助词与包含助词，补全“也去了长野”：',
                '長野{{blank:b1}}{{blank:b2}}行きました。',
                f"{r('長野', 'ながの')}{B1}{B2}{r('行', 'い')}きました。",
                'nagano [ ? ] [ ? ] ikimashita.',
                '也去了长野。',
                [blank_spec('b1', '方向助词', ['へ']), blank_spec('b2', '包含助词', ['も'])],
                _expl(f"{r('長野', 'ながの')}<strong>へも</strong>{r('行', 'い')}きました。", 'nagano e mo ikimashita.', '方向助词「へ」不与「も」冲突替换，须排在「も」前（へも）。'),
            ),
            fc(
                'fc-jp03-16', '疑问词 +「も」+ 否定：誰〜ない', ['p-jp03-mo-wh-neg'],
                '填入助词构成“谁也不知道”的全盘否定：',
                '誰{{blank:b1}}知らない。',
                f"{r('誰', 'だれ')}{B1}{r('知', 'し')}らない。",
                'dare [ ? ] shiranai.',
                '谁也不知道（没人知道）。',
                [blank_spec('b1', '助词', ['も'])],
                _expl(f"{r('誰', 'だれ')}<strong>も</strong>{r('知', 'し')}らない。", 'dare mo shiranai.', '疑问词「誰」后接「も」并配否定动词，构成全盘否定“谁也不……”。'),
            ),
            fc(
                'fc-jp03-17', '疑问词 +「も」+ 否定：何〜ない', ['p-jp03-mo-wh-neg'],
                '填入助词构成“什么也没有”：',
                '何{{blank:b1}}ない。',
                f"{r('何', 'なに')}{B1}ない。",
                'nani [ ? ] nai.',
                '什么也没有。',
                [blank_spec('b1', '助词', ['も'])],
                _expl(f"{r('何', 'なに')}<strong>も</strong>ない。", 'nani mo nai.', '「何も + 否定」表示“什么也不 / 什么都没有”。'),
            ),
            fc(
                'fc-jp03-18', '疑问词 + 格助词 +「も」：どこにも行かなかった', ['p-jp03-mo-wh-neg'],
                '按正确格助词顺序填入“目标助词＋包含助词”，构成“哪儿也没去”：',
                'どこ{{blank:b1}}{{blank:b2}}行かなかった。',
                f"どこ{B1}{B2}{r('行', 'い')}かなかった。",
                'doko [ ? ] [ ? ] ikanakatta.',
                '哪儿也没去。',
                [blank_spec('b1', '目标助词', ['に']), blank_spec('b2', '包含助词', ['も'])],
                _expl(f"どこ<strong>にも</strong>{r('行', 'い')}かなかった。", 'doko ni mo ikanakatta.', '目标助词「に」排在「も」前面，组成「どこにも + 否定（哪儿也不……）」。'),
            ),
            fc(
                'fc-jp03-19', '数量词 +「も」强调超出预期', ['p-jp03-mo-qty-more'],
                '填入强调“足足三次”、表达惊讶或过度的助词：',
                '昨日、電話三回{{blank:b1}}したよ！',
                f"{r('昨日', 'きのう')}、{r('電話', 'でんわ')}{r('三回', 'さんかい')}{B1}したよ！",
                'kinō, denwa sankai [ ? ] shita yo!',
                '昨天足足打了三次电话！',
                [blank_spec('b1', '数量强调助词', ['も'])],
                _expl(f"{r('昨日', 'きのう')}、{r('電話', 'でんわ')}{r('三回', 'さんかい')}<strong>も</strong>したよ！", 'kinō, denwa sankai mo shita yo!', '「数量词 + も」不再表“也”，而是强调数量多到超出预期。'),
            ),
            fc(
                'fc-jp03-20', '动词 て 形 +「も」：许可「〜てもいい」', ['p-jp03-mo-qty-more'],
                '填入表示许可（“……也可以”）的接续形式，补全“全部吃掉也可以哦”：',
                '全部食べ{{blank:b1}}いいよ。',
                f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べ{B1}いいよ。",
                'zenbu tabe[ ? ] ii yo.',
                '全部吃掉也可以哦。',
                [blank_spec('b1', '许可连接', ['ても'])],
                _expl(f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べ<strong>ても</strong>いいよ。", 'zenbu tabete mo ii yo.', '一段动词「食べる」的て形「食べて」+「も」+「いい」，表示许可。'),
            ),
            fc(
                'fc-jp03-21', '「〜なくてもいい」：不必／不……也可以', ['p-jp03-mo-qty-more'],
                '填入表示“不必 / 不……也可以”的接续形式，补全“不需要全部吃完”：',
                '全部食べ{{blank:b1}}いいよ。',
                f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べ{B1}いいよ。",
                'zenbu tabe[ ? ] ii yo.',
                '不需要全部吃完（不吃也可以）。',
                [blank_spec('b1', '不必连接', ['なくても'])],
                _expl(f"{r('全部', 'ぜんぶ')}{r('食', 'た')}べ<strong>なくても</strong>いいよ。", 'zenbu tabenakute mo ii yo.', '否定形「〜ない」变为「〜なくて」再接「もいい」，表示“不……也可以”。'),
            ),
            fc(
                'fc-jp03-22', '疑问词 +「よりも」构成最高级', ['p-jp03-mo-qty-more'],
                '填入表示“比任何人（都）……”的比较助词组合：',
                'この仕事は誰{{blank:b1}}早くできます。',
                f"この{r('仕事', 'しごと')}は{r('誰', 'だれ')}{B1}{r('早', 'はや')}くできます。",
                'kono shigoto wa dare [ ? ] hayaku dekimasu.',
                '这工作我做得比任何人都快。',
                [blank_spec('b1', '比较助词组合', ['よりも'])],
                _expl(f"この{r('仕事', 'しごと')}は{r('誰', 'だれ')}<strong>よりも</strong>{r('早', 'はや')}くできます。", 'kono shigoto wa dare yori mo hayaku dekimasu.', '「疑问词 + より(も)」表示最高级“比任何（人/物）都……”。'),
            ),
            fc(
                'fc-jp03-23', '「ながら」+「も」表转折让步', ['p-jp03-mo-qty-more'],
                '在「残念」后填入表示“虽然……”让步转折的接续助词组合：',
                '残念{{blank:b1}}',
                f"{r('残念', 'ざんねん')}{B1}",
                'zannen [ ? ]',
                '虽然很遗憾……',
                [blank_spec('b1', '让步连词', ['ながらも'])],
                _expl(f"{r('残念', 'ざんねん')}<strong>ながらも</strong>", 'zannen nagara mo', '「ながら」加上「も」从“一边……一边……”转为“尽管……也……”的让步语气。'),
            ),
            fc(
                'fc-jp03-24', '「A も B も」句中多重叠用', ['p-jp03-mo-qty-more'],
                '依次填入两个包含助词，表示“弟弟和妹妹都来了”：',
                '弟さん{{blank:b1}}妹さん{{blank:b2}}来ました。',
                f"{r('弟', 'おとうと')}さん{B1}{r('妹', 'いもうと')}さん{B2}{r('来', 'き')}ました。",
                'otōto-san [ ? ] imōto-san [ ? ] kimashita.',
                '弟弟和妹妹都来了。',
                [blank_spec('b1', '第一个「也」', ['も']), blank_spec('b2', '第二个「也」', ['も'])],
                _expl(f"{r('弟', 'おとうと')}さん<strong>も</strong>{r('妹', 'いもうと')}さん<strong>も</strong>{r('来', 'き')}ました。", 'otōto-san mo imōto-san mo kimashita.', '「A も B も」可连续将多个并列成员纳入同一陈述“既A也B”。'),
            ),
            fc(
                'fc-jp03-25', '综合复盘：い形容词 vs な形容词过去否定简体', ['p-jp03-i-neg-past', 'p-jp03-na-conj'],
                '分别写出「高い（い形）」和「静か（な形）」的【过去否定简体】：',
                '高い → {{blank:b1}} ／ 静か → {{blank:b2}}',
                f"{r('高', 'たか')}い → {B1} ／ {r('静', 'しず')}か → {B2}",
                'takai → [ ? ] / shizuka → [ ? ]',
                '过去不高 ／ 过去不安静（简体）',
                [
                    blank_spec('b1', '高い 过去否定', ['高くなかった', 'たかくなかった']),
                    blank_spec('b2', '静か 过去否定', ['静かじゃなかった', '静かではなかった', 'しずかじゃなかった', 'しずかではなかった']),
                ],
                _expl(f"<strong>{r('高', 'たか')}くなかった</strong> ／ <strong>{r('静', 'しず')}かじゃなかった</strong>", 'takakunakatta / shizuka janakatta', 'い形容词本身词尾变「くなかった」；な形容词词干不变，后挂「じゃなかった」。'),
            ),
        ],
    },
    # =========================================================================
    # Topic 4: jp04-verbs-existence-past
    # =========================================================================
    {
        'id': 'jp04-verbs-existence-past',
        'title': '4. 动词分类、存在句（ある・いる）与过去时',
        'sections': [
            {
                'id': 'sec-jp04-classes',
                'title': '一、动词三大分类、iru/eru 五段特例与存在动词「ある・いる」',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp04-past',
                'title': '二、动词过去时（〜た形）、音变规则与通用过去否定（〜なかった）',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp04-classes',
                'section_id': 'sec-jp04-classes',
                'title': '日语动词三大分类、三梯度 iru/eru 特例表与存在动词「ある・いる」',
                'html': (
                    '<h3>一、单动词成句与日语动词三大分类（3.5）</h3>'
                    '<p>与英语不同，日语只要一个动词（以词典原形/<strong>字典形</strong>为所有变形起点）就能构成语法完整的独立句子（如 ' + term(f"{r('食', 'た')}べる。", 'taberu.', '吃。') + '）。全日语动词分为三大类：</p>'
                    '<ul>'
                    '<li><strong>一段动词（ru-verb / 词典标 <code>(v1)</code>）</strong>：如 ' + term(f"{r('食', 'た')}べる", 'taberu', '吃') + '、' + term(f"{r('起', 'お')}きる", 'okiru', '起床') + '。必定以假名「る」结尾。</li>'
                    '<li><strong>五段动词（u-verb / 词典标 <code>(v5)</code>）</strong>：共有 <strong>9 个结尾假名</strong>——<code>る・つ・す・く・ぐ・む・ぶ・う・ぬ</code>。其中 ' + term(f"{r('死', 'し')}ぬ", 'shinu', '死') + ' 是全日语<strong>唯一以「ぬ」结尾</strong>的动词。</li>'
                    '<li><strong>不规则动词（Exception Verbs）</strong>：全日语<strong>只有两个</strong>——' + term('する', 'suru', '做') + ' 和 ' + term(f"{r('来', 'く')}る", 'kuru', '来') + '。</li>'
                    '</ul>'
                    '<h3>二、二步精准识别法则与 iru/eru 五段特例表</h3>'
                    '<ol>'
                    '<li><strong>第一步（看罗马音末尾）</strong>：若不以 <code>-iru</code> 或 <code>-eru</code> 结尾（如 <code>話す hanasu</code>、<code>飲む nomu</code>、<code>買う kau</code>、<code>取る toru</code>、<code>直る naoru</code>），则<strong>必然是五段动词</strong>。</li>'
                    '<li><strong>第二步（处理 <code>-iru/-eru</code> 结尾）</strong>：罗马音以 <code>-iru</code> 或 <code>-eru</code> 结尾时<strong>通常</strong>是一段动词，但存在少数按五段活用的特例动词，需要按频度梯度记忆：</li>'
                    '</ol>'
                    + tbl(
                        ['难度梯度', '虽以 -iru/-eru 结尾却属五段动词（u-verb）的特例词汇'],
                        [
                            ['初级（Basic）', '要る（いる，需要）、帰る（かえる，归）、切る（きる，剪/切）、しゃべる（聊天）、知る（しる，知道）、入る（はいる，进入）、走る（はしる，跑）、減る（へる，减少）'],
                            ['中级（Intermediate）', '焦る（あせる，着急）、限る（かぎる，限于）、蹴る（ける，踢）、滑る（すべる，滑）、握る（にぎる，握）、練る（ねる，锤炼）、参る（まいる，去/认输）、交じる（まじる，掺杂）'],
                            ['高级（Advanced）', '嘲る（あざける，嘲笑）、覆る（くつがえる，翻转）、遮る（さえぎる，遮挡）、罵る（ののしる，斥骂）、捻る（ひねる，拧）、翻る（ひるがえる，飘扬）、滅入る（めいる，消沉）、蘇る（よみがえる，复活）'],
                        ],
                    )
                    + '<p>区分一段与五段动词的直接用途：変否定形（一段去「る」+「ない」，五段 /u/ 变 /a/ +「ない」）与提取敬体ます形词干（一段去「る」，五段 /u/ 变 /i/，如 <code>泳ぐ → 泳ぎ</code>）。</p>'
                    '<h3>三、存在动词「ある」与「いる」：生命性区分与「ある → ない」特例</h3>'
                    '<ul>'
                    '<li><strong>生命性区分</strong>：<strong>「ある」</strong>（五段）用于无生命物体/资金/抽象存在（' + term(f"お{r('金', 'かね')}がある", 'okane ga aru', '有钱') + '）；<strong>「いる」</strong>（正规<strong>一段动词</strong>）用于人、动物等有生命对象（' + term(f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}にいる", 'neko wa heya ni iru', '猫在房间里') + '）。</li>'
                    '<li><strong>「ある」否定特例</strong>：「ある」的简体否定直接为<strong>「ない」</strong>（绝不存在 <code>*あらない</code>），表“不存在”。</li>'
                    '</ul>'
                ),
            },
            {
                'id': 'intro-jp04-past',
                'section_id': 'sec-jp04-past',
                'title': '动词过去时（3.7.1〜3.7.3）：音变四类、三大特例与「〜なかった」',
                'html': (
                    '<h3>一、一段动词与五段动词的过去肯定简体（3.7.1〜3.7.2）</h3>'
                    '<p>在《Japanese Grammar Guide》中，3.7 动词过去时被作者称为全书最关键的一关。只要把过去时变形拿下，后续て形等所有活用都会迎刃而解：</p>'
                    '<ul>'
                    '<li><strong>一段动词（ru-verb）</strong>：直接去掉词尾「る」换为「た」：<code>出る → 出た</code>、<code>捨てる → 捨てた</code>。'
                    + ex(f"ご{r('飯', 'はん')}は、{r('食', 'た')}べた。 ／ {r('映画', 'えいが')}は、{r('全部', 'ぜんぶ')}{r('見', 'み')}た。", 'gohan wa, tabeta. / eiga wa, zenbu mita.', '关于饭，吃过了。／ 关于电影，全部看过了。')
                    + '</li>'
                    '<li><strong>五段动词（u-verb）四大音变分类</strong>：'
                    + tbl(
                        ['词尾假名', '变化规则', '课本推导示例'],
                        [
                            ['す', 'す → した', '話す → 話した（hanashita，说了）'],
                            ['く / ぐ', 'く → いた ／ ぐ → いだ（浊音）', '書く → 書いた（kaita）／ 泳ぐ → 泳いだ（oyoida）'],
                            ['む / ぬ / ぶ', 'む・ぬ・ぶ → んだ（拨音+浊音）', '噛む → 噛んだ ／ 死ぬ → 死んだ ／ 遊ぶ → 遊んだ'],
                            ['る / つ / う', 'る・つ・う → った（促音化）', '切る → 切った ／ 持つ → 持った ／ 買う → 買った'],
                        ],
                    )
                    + '</li>'
                    '<li><strong>过去时三大特例</strong>：<code>する → した</code>、<code>来る（くる）→ 来た（きた）</code>，以及虽属正规五段动词但在过去时发生特殊促音音变的 <code>行く → 行った</code>（不可写成 <code>*行いた</code>）。'
                    + ex(f"{r('今日', 'きょう')}は、{r('走', 'はし')}った。 ／ {r('友達', 'ともだち')}が{r('来', 'き')}た。 ／ {r('私', 'わたし')}も{r('遊', 'あそ')}んだ。 ／ {r('勉強', 'べんきょう')}は、した。", 'kyō wa, hashitta. / tomodachi ga kita. / watashi mo asonda. / benkyō wa, shita.', '今天跑步了。／ 朋友来了。／ 我也玩了。／ 关于学习，做过了。')
                    + '</li>'
                    '</ul>'
                    '<h3>二、所有动词通用的过去否定形（〜なかった）与特殊语用（3.7.3）</h3>'
                    '<p>由于日语所有动词的简体否定都落在「ない」上，因此<strong>无论一段、五段还是不规则动词，过去否定规则完全统一</strong>：先变为否定形「〜ない」，再去「い」替换为「かった」构成<strong>「〜なかった」</strong>（如 <code>捨てる → 捨てない → 捨てなかった</code>、<code>行く → 行かない → 行かなかった</code>）：</p>'
                    + ex(f"アリスは{r('食', 'た')}べなかった。 ／ ジムがしなかった。 ／ ボブも{r('行', 'い')}かなかった。", 'arisu wa tabenakatta. / jimu ga shinakatta. / bobu mo ikanakatta.', '爱丽丝没有吃。／ 没做的是吉姆。／ 鲍勃也没去。')
                    + ex(f"お{r('金', 'かね')}がなかった。 ／ {r('私', 'わたし')}は{r('買', 'か')}わなかった。 ／ {r('猫', 'ねこ')}はいなかった。", 'okane ga nakatta. / watashi wa kawanakatta. / neko wa inakatta.', '没有钱。／ 我没有买。／ 猫不在。', '无生命「ない→なかった」vs 有生命「いない→いなかった」')
                    + tip('《Making Sense of Japanese Grammar》过去时特殊语用', '① <strong>确认/回忆已商定事项</strong>：' + term(f"{r('締切', 'しめきり')}は、いつでしたか。", 'shimekiri wa, itsu deshita ka.', '您之前说截止日期是什么时候来着？') + '；② <strong>表达社交往来完结</strong>：' + term('ありがとうございました。', 'arigatō gozaimashita.', '感谢您刚才/此前为我做的一切。'))
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp04-verb-classes',
                'introduction_id': 'intro-jp04-classes',
                'title': '动词三大分类、9种五段词尾、「死ぬ」与 iru/eru 五段特例',
                'html': '<p>一段动词(v1)、五段动词(v5，9种u段词尾含唯一「死ぬ」)、两不规则动词(する/来る)；另有三梯度 -iru/-eru 五段特例。</p>',
                'anchor_quotes': ['一、单动词成句与日语动词三大分类（3.5）', '二、二步精准识别法则与 iru/eru 五段特例表'],
                'points': [
                    {'id': 'p-jp04-verb-3classes', 'text': '日语动词分一段(v1)、五段(v5，9个u段词尾，唯一「ぬ」结尾是死ぬ)、两不规则动词（する、来る）；五段ます形词干将/u/变/i/。'},
                    {'id': 'p-jp04-iru-eru-exc', 'text': '要る、帰る、切る、知る、入る、走る、減る、しゃべる 等词虽以 -iru/-eru 结尾，却属于五段动词特例，需按五段规则活用。'},
                ],
            },
            {
                'id': 'chunk-jp04-aru-iru',
                'introduction_id': 'intro-jp04-classes',
                'title': '存在动词「ある・いる」的生命性分工与「ある→ない」',
                'html': '<p>「ある」用于无生命事物，否定直接为「ない」；「いる」是正规一段动词，用于人或动物。</p>',
                'anchor_quotes': ['三、存在动词「ある」与「いる」：生命性区分与「ある → ない」特例'],
                'points': [
                    {'id': 'p-jp04-aru-vs-iru', 'text': '无生命存在用「ある」（否定直接为「ない」）；人/动物等有生命存在用一段动词「いる」。'},
                ],
            },
            {
                'id': 'chunk-jp04-past-ru-u',
                'introduction_id': 'intro-jp04-past',
                'title': '一段与五段动词过去时四大音变及三大特例',
                'html': '<p>一段去る+た；五段按す→した、く/ぐ→いた/いだ、むぬぶ→んだ、るつう→った；特例：する→した、来る→来た、行く→行った。</p>',
                'anchor_quotes': ['一、一段动词与五段动词的过去肯定简体（3.7.1〜3.7.2）'],
                'points': [
                    {'id': 'p-jp04-past-ru', 'text': '一段动词过去简体直接去「る」加「た」（出る → 出た、捨てる → 捨てた）。'},
                    {'id': 'p-jp04-past-u-4rules', 'text': '五段动词过去音变：す→した，く/ぐ→いた/いだ，む/ぬ/ぶ→んだ，る/つ/う→った。'},
                    {'id': 'p-jp04-past-3exc', 'text': '过去时三大特例：する→した、来る(くる)→来た(きた)、行く→行った。'},
                ],
            },
            {
                'id': 'chunk-jp04-past-neg',
                'introduction_id': 'intro-jp04-past',
                'title': '通用过去否定「〜なかった」与过去时的确认/完结语用',
                'html': '<p>全动词否定形去「い」+「かった」变「〜なかった」；过去时亦用于礼貌确认已约定事项及结清致谢。</p>',
                'anchor_quotes': ['二、所有动词通用的过去否定形（〜なかった）与特殊语用（3.7.3）'],
                'points': [
                    {'id': 'p-jp04-past-neg-rule', 'text': '所有动词过去否定统一由「〜ない」去「い」加「かった」变「〜なかった」（食べなかった、買わなかった、なかった、いなかった）。'},
                    {'id': 'p-jp04-past-pragmatic', 'text': '过去时可用于确认之前商定好的事项（締切はいつでしたか）及表示社交交易完结（ありがとうございました）。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp04-01', '全日语唯一「ぬ」结尾五段动词', ['p-jp04-verb-3classes'],
                '填入全日语中唯一一个以假名「ぬ」结尾的动词辞书形（意为“死”）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（“死”的辞书形）',
                '死（辞书形）',
                [blank_spec('b1', '辞书形', ['死ぬ', 'しぬ'])],
                _expl(f"<strong>{r('死', 'し')}ぬ</strong>", 'shinu', '五段动词共有 る・つ・す・く・ぐ・む・ぶ・う・ぬ 9 种词尾，「死ぬ」是唯一以「ぬ」结尾的动词。'),
            ),
            fc(
                'fc-jp04-02', '全日语仅有的两个不规则动词', ['p-jp04-verb-3classes'],
                '全日语只有两个真正的不规则动词，一个是「する」，另一个（意为“来”）是：',
                'する ／ {{blank:b1}}',
                'する ／ {{blank:b1}}',
                'suru / [ ? ]',
                '做 ／ 来',
                [blank_spec('b1', '不规则动词“来”', ['来る', 'くる'])],
                _expl(f"する ／ <strong>{r('来', 'く')}る</strong>", 'suru / kuru', '不规则动词仅有「する（做）」与「来る（くる，来）」两个。'),
            ),
            fc(
                'fc-jp04-03', '五段动词提取ます形词干', ['p-jp04-verb-3classes'],
                '按动词分类规则，写出「泳ぐ（游泳）」的ます形词干（不含「ます」）：',
                '泳ぐ → {{blank:b1}}ます',
                f"{r('泳', 'およ')}ぐ → {B1}ます",
                'oyogu → [ ? ] masu',
                '（他/她）游泳（敬体）',
                [blank_spec('b1', 'ます形词干', ['泳ぎ', 'およぎ'])],
                _expl(f"{r('泳', 'およ')}ぐ → <strong>{r('泳', 'およ')}ぎ</strong>ます", 'oyogu → oyogimasu', '五段动词提取词干（Stem）时将词尾 /u/ 段假名换为同行 /i/ 段（ぐ → ぎ）。'),
            ),
            fc(
                'fc-jp04-04', 'iru/eru 五段特例「帰る」', ['p-jp04-iru-eru-exc'],
                '根据动词分类规则，写出「帰る（かえる，回家）」的【非过去否定简体】：',
                '家に{{blank:b1}}。',
                f"{r('家', 'いえ')}に{B1}。",
                'ie ni [ ? ].',
                '不回家。（「帰る」否定简体）',
                [blank_spec('b1', '帰る 否定简体', ['帰らない', 'かえらない'])],
                _expl(f"{r('家', 'いえ')}に<strong>{r('帰', 'かえ')}らない</strong>。", 'ie ni kaeranai.', '「帰る」虽以 -eru 结尾但属五段动词，因此否定变为「帰らない」，不可说「*帰ない」。'),
            ),
            fc(
                'fc-jp04-05', 'iru/eru 五段特例「切る」', ['p-jp04-iru-eru-exc'],
                '根据动词分类规则，写出「切る（きる，剪/切）」的【过去肯定简体】：',
                '紙を{{blank:b1}}。',
                f"{r('紙', 'かみ')}を{B1}。",
                'kami o [ ? ].',
                '把纸剪/切了。（「切る」过去简体）',
                [blank_spec('b1', '切る 过去简体', ['切った', 'きった'])],
                _expl(f"{r('紙', 'かみ')}を<strong>{r('切', 'き')}った</strong>。", 'kami o kitta.', '「切る（切）」是五段特例，过去发生促音变「切った」（注意与一段动词「着る→着た（穿了）」区分）。'),
            ),
            fc(
                'fc-jp04-06', 'iru/eru 五段特例「走る」', ['p-jp04-iru-eru-exc'],
                '根据动词分类规则，写出「走る（はしる，跑）」的【非过去否定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（走る → 否定简体）',
                '不跑（简体）',
                [blank_spec('b1', '走る 否定简体', ['走らない', 'はしらない'])],
                _expl(f"<strong>{r('走', 'はし')}らない</strong>", 'hashiranai', '「走る（hashiru）」是五段动词，否定变为「走らない」。'),
            ),
            fc(
                'fc-jp04-07', '无生命存在动词「ある」', ['p-jp04-aru-vs-iru'],
                '表达无生命对象“有钱”（辞书形）：',
                'お金が{{blank:b1}}。',
                f"お{r('金', 'かね')}が{B1}。",
                'okane ga [ ? ].',
                '有钱。（存在动词辞书形）',
                [blank_spec('b1', '无生命存在动词', ['ある'])],
                _expl(f"お{r('金', 'かね')}が<strong>ある</strong>。", 'okane ga aru.', '无生命物体或抽象存在使用「ある」。'),
            ),
            fc(
                'fc-jp04-08', '有生命存在动词「いる」（一段）', ['p-jp04-aru-vs-iru'],
                '表达有生命对象“猫在房间里”（辞书形）：',
                '猫は部屋に{{blank:b1}}。',
                f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}に{B1}。",
                'neko wa heya ni [ ? ].',
                '猫在房间里。（有生命存在动词）',
                [blank_spec('b1', '有生命存在动词', ['いる', '居る'])],
                _expl(f"{r('猫', 'ねこ')}は{r('部屋', 'へや')}に<strong>いる</strong>。", 'neko wa heya ni iru.', '人或动物等有生命体的存在必须用正规一段动词「いる」。'),
            ),
            fc(
                'fc-jp04-09', '「ある」的否定特例「ない」', ['p-jp04-aru-vs-iru'],
                '写出无生命存在动词「ある」的【简体否定】“没有钱”：',
                'お金が{{blank:b1}}。',
                f"お{r('金', 'かね')}が{B1}。",
                'okane ga [ ? ].',
                '没有钱。（简体）',
                [blank_spec('b1', 'ある 简体否定', ['ない'])],
                _expl(f"お{r('金', 'かね')}が<strong>ない</strong>。", 'okane ga nai.', '「ある」的简体否定直接是「ない」，绝不说「*あらない」。'),
            ),
            fc(
                'fc-jp04-10', '一段动词过去简体「出る」', ['p-jp04-past-ru'],
                '将一段动词「出る（出/离开）」变为【过去简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（出る → 过去简体）',
                '出去了 / 离开了（过去简体）',
                [blank_spec('b1', '出る 过去简体', ['出た', 'でた'])],
                _expl(f"<strong>{r('出', 'で')}た</strong>", 'deta', '一段动词变过去简体：直接去「る」加「た」。'),
            ),
            fc(
                'fc-jp04-11', '一段动词过去简体「捨てる」', ['p-jp04-past-ru'],
                '将一段动词「捨てる（扔掉）」变为【过去简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（捨てる → 过去简体）',
                '扔掉了（过去简体）',
                [blank_spec('b1', '捨てる 过去简体', ['捨てた', 'すてた'])],
                _expl(f"<strong>{r('捨', 'す')}てた</strong>", 'suteta', '一段动词「捨てる」去「る」加「た」得「捨てた」。'),
            ),
            fc(
                'fc-jp04-12', '一段动词过去简体例句「見る」', ['p-jp04-past-ru'],
                '补全课本原例中的过去动词（「見る」→ 过去简体）：',
                '映画は、全部{{blank:b1}}。',
                f"{r('映画', 'えいが')}は、{r('全部', 'ぜんぶ')}{B1}。",
                'eiga wa, zenbu [ ? ].',
                '关于电影，全部看过了。',
                [blank_spec('b1', '見る 过去简体', ['見た', 'みた'])],
                _expl(f"{r('映画', 'えいが')}は、{r('全部', 'ぜんぶ')}<strong>{r('見', 'み')}た</strong>。", 'eiga wa, zenbu mita.', '「見る」也是一段动词，去「る」加「た」得到「見た」。'),
            ),
            fc(
                'fc-jp04-13', '五段「す」结尾过去音变', ['p-jp04-past-u-4rules'],
                '将「話す（说）」变为【过去简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（話す → 过去简体）',
                '说了（过去简体）',
                [blank_spec('b1', '話す 过去简体', ['話した', 'はなした'])],
                _expl(f"<strong>{r('話', 'はな')}した</strong>", 'hanashita', '「す」结尾的五段动词过去音变为「した」。'),
            ),
            fc(
                'fc-jp04-14', '五段「く / ぐ」结尾过去音变', ['p-jp04-past-u-4rules'],
                '分别写出「書く」和「泳ぐ」的【过去简体】（注意是否浊音）：',
                '書く → {{blank:b1}} ／ 泳ぐ → {{blank:b2}}',
                f"{r('書', 'か')}く → {B1} ／ {r('泳', 'およ')}ぐ → {B2}",
                'kaku → [ ? ] / oyogu → [ ? ]',
                '写了 ／ 游泳了（注意清浊）',
                [blank_spec('b1', '書く 过去简体', ['書いた', 'かいた']), blank_spec('b2', '泳ぐ 过去简体', ['泳いだ', 'およいだ'])],
                _expl(f"<strong>{r('書', 'か')}いた</strong> ／ <strong>{r('泳', 'およ')}いだ</strong>", 'kaita / oyoida', '「く → いた」清音结尾，带浊音的「ぐ → いだ」保留浊音。'),
            ),
            fc(
                'fc-jp04-15', '五段「む / ぬ / ぶ」结尾过去音变', ['p-jp04-past-u-4rules'],
                '分别写出「噛む」「死ぬ」「遊ぶ」的【过去简体】：',
                '噛む → {{blank:b1}} ／ 死ぬ → {{blank:b2}} ／ 遊ぶ → {{blank:b3}}',
                f"{r('噛', 'か')}む → {B1} ／ {r('死', 'し')}ぬ → {B2} ／ {r('遊', 'あそ')}ぶ → {B3}",
                'kamu → [ ? ] / shinu → [ ? ] / asobu → [ ? ]',
                '咬了 ／ 死了 ／ 玩了',
                [blank_spec('b1', '噛む 过去', ['噛んだ', 'かんだ']), blank_spec('b2', '死ぬ 过去', ['死んだ', 'しんだ']), blank_spec('b3', '遊ぶ 过去', ['遊んだ', 'あそんだ'])],
                _expl(f"<strong>{r('噛', 'か')}んだ</strong> ／ <strong>{r('死', 'し')}んだ</strong> ／ <strong>{r('遊', 'あそ')}んだ</strong>", 'kanda / shinda / asonda', '以「む・ぬ・ぶ」结尾的五段动词过去统一音变为「んだ」。'),
            ),
            fc(
                'fc-jp04-16', '五段「つ / う」结尾过去促音变', ['p-jp04-past-u-4rules'],
                '分别写出「持つ」和「買う」的【过去简体】：',
                '持つ → {{blank:b1}} ／ 買う → {{blank:b2}}',
                f"{r('持', 'も')}つ → {B1} ／ {r('買', 'か')}う → {B2}",
                'motsu → [ ? ] / kau → [ ? ]',
                '拿过 / 持有过 ／ 买了',
                [blank_spec('b1', '持つ 过去', ['持った', 'もった']), blank_spec('b2', '買う 过去', ['買った', 'かった'])],
                _expl(f"<strong>{r('持', 'も')}った</strong> ／ <strong>{r('買', 'か')}った</strong>", 'motta / katta', '「る（五段）・つ・う」结尾统一发生促音化变为「った」。'),
            ),
            fc(
                'fc-jp04-17', '过去时三大特例之一：「行く」', ['p-jp04-past-3exc'],
                '请写出「行く（去）」的【过去肯定简体】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（行く → 过去简体）',
                '去了（「行く」过去简体）',
                [blank_spec('b1', '行く 过去简体', ['行った', 'いった'])],
                _expl(f"<strong>{r('行', 'い')}った</strong>", 'itta', '「行く」不按「く→いた」变为「*行いた」，而发生特殊促音变成为「行った」。'),
            ),
            fc(
                'fc-jp04-18', '两大不规则动词的过去简体', ['p-jp04-past-3exc'],
                '分别写出「する」和「来る（くる）」的【过去简体】：',
                'する → {{blank:b1}} ／ 来る → {{blank:b2}}',
                f"する → {B1} ／ {r('来', 'く')}る → {B2}",
                'suru → [ ? ] / kuru → [ ? ]',
                '做了 ／ 来了',
                [blank_spec('b1', 'する 过去', ['した']), blank_spec('b2', '来る 过去', ['来た', 'きた'])],
                _expl(f"<strong>した</strong> ／ <strong>{r('来', 'き')}た</strong>", 'shita / kita', '注意「来る」读音从辞书形「kuru」变成过去形「kita（きた）」。'),
            ),
            fc(
                'fc-jp04-19', '一段动词过去否定简体「捨てる」', ['p-jp04-past-neg-rule'],
                '将「捨てる（扔掉）」变为【过去否定简体】（过去没扔）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（捨てる → 过去否定简体）',
                '过去没扔（简体）',
                [blank_spec('b1', '捨てる 过去否定', ['捨てなかった', 'すてなかった'])],
                _expl(f"<strong>{r('捨', 'す')}てなかった</strong>", 'sutenakatta', '通用过去否定规则：将否定形「〜ない」的「い」换为「かった」→「〜なかった」。'),
            ),
            fc(
                'fc-jp04-20', '五段特例「行く」过去否定（含「行かなかった」）', ['p-jp04-past-neg-rule'],
                '将「行く（去）」变为【过去否定简体】，补全“鲍勃也没去”：',
                'ボブも{{blank:b1}}。',
                f"ボブも{B1}。",
                'bobu mo [ ? ].',
                '鲍勃也没去。（「行く」过去否定简体）',
                [blank_spec('b1', '行く 过去否定', ['行かなかった', 'いかなかった'])],
                _expl(f"ボブも<strong>{r('行', 'い')}かなかった</strong>。", 'bobu mo ikanakatta.', '先正规变为否定「行かない」，再去「い」换「かった」得「行かなかった」。'),
            ),
            fc(
                'fc-jp04-21', '「買う」过去否定（含「う→わ」音变）', ['p-jp04-past-neg-rule'],
                '填入「買う（买）」的【过去否定简体】“我没有买”：',
                '私は{{blank:b1}}。',
                f"{r('私', 'わたし')}は{B1}。",
                'watashi wa [ ? ].',
                '关于我，没有买。（简体）',
                [blank_spec('b1', '買う 过去否定', ['買わなかった', 'かわなかった'])],
                _expl(f"{r('私', 'わたし')}は<strong>{r('買', 'か')}わなかった</strong>。", 'watashi wa kawanakatta.', '「買う」先变为否定「買わない」（う变わ），再换为过去否定「買わなかった」。'),
            ),
            fc(
                'fc-jp04-22', '存在动词过去否定对照（ある vs いる）', ['p-jp04-past-neg-rule'],
                '分别用无生命和有生命存在动词的【过去否定简体】补全两句：',
                'お金が{{blank:b1}}。 ／ 猫は{{blank:b2}}。',
                f"お{r('金', 'かね')}が{B1}。 ／ {r('猫', 'ねこ')}は{B2}。",
                'okane ga [ ? ]. / neko wa [ ? ].',
                '没有钱（过去不存在钱）。／ 猫当时不在。',
                [blank_spec('b1', '无生命过去否定', ['なかった']), blank_spec('b2', '有生命过去否定', ['いなかった', '居なかった'])],
                _expl(f"お{r('金', 'かね')}が<strong>なかった</strong>。 ／ {r('猫', 'ねこ')}は<strong>いなかった</strong>。", 'okane ga nakatta. / neko wa inakatta.', '「ない → なかった」表无生命过去不存在；一段动词「いる → いない → いなかった」表有生命体过去不在。'),
            ),
            fc(
                'fc-jp04-23', '过去时特殊语用：确认已商定的未来时间', ['p-jp04-past-pragmatic'],
                '询问并确认之前已经约定好的截止日期时，填入句末过去礼貌断定词：',
                '締切は、いつ{{blank:b1}}か。',
                f"{r('締切', 'しめきり')}は、いつ{B1}か。",
                'shimekiri wa, itsu [ ? ] ka.',
                '“（您之前说）截止日期是什么时候来着？”',
                [blank_spec('b1', '过去礼貌断定词', ['でした'])],
                _expl(f"{r('締切', 'しめきり')}は、いつ<strong>でした</strong>か。", 'shimekiri wa, itsu deshita ka.', '《Making Sense of Japanese Grammar》指出：即使截止日期在将来，确认“之前商定好的信息”时仍可用过去式「でした」。'),
            ),
            fc(
                'fc-jp04-24', '过去时特殊语用：社交交易完结致谢', ['p-jp04-past-pragmatic'],
                '用于事件或服务已经圆满结束时表达完整感谢：',
                'ありがとう{{blank:b1}}。',
                'ありがとう{{blank:b1}}。',
                'arigatō [ ? ].',
                '多谢您（刚才为我做的一切）。',
                [blank_spec('b1', '过去礼貌敬语词尾', ['ございました'])],
                _expl('ありがとう<strong>ございました</strong>。', 'arigatō gozaimashita.', '用过去时「ございました」表示针对已完成的整套社交互动表达致谢。'),
            ),
            fc(
                'fc-jp04-25', '综合复盘：过去肯否综合检验', ['p-jp04-past-u-4rules', 'p-jp04-past-3exc', 'p-jp04-past-neg-rule'],
                '根据提示依次填入课本原例动词（全部使用简体过去形式）：',
                '友達が{{blank:b1}}。（来了） ／ 勉強は、{{blank:b2}}。（做过了） ／ ジムが{{blank:b3}}。（没做）',
                f"{r('友達', 'ともだち')}が{B1}。 ／ {r('勉強', 'べんきょう')}は、{B2}。 ／ ジムが{B3}。",
                'tomodachi ga [ ? ]. / benkyō wa, [ ? ]. / jimu ga [ ? ].',
                '朋友来了 ／ 功课做过了 ／ 没做的是吉姆',
                [
                    blank_spec('b1', '来る 过去', ['来た', 'きた']),
                    blank_spec('b2', 'する 过去', ['した']),
                    blank_spec('b3', 'する 过去否定', ['しなかった']),
                ],
                _expl(f"{r('友達', 'ともだち')}が<strong>{r('来', 'き')}た</strong>。 ／ {r('勉強', 'べんきょう')}は、<strong>した</strong>。 ／ ジムが<strong>しなかった</strong>。", 'tomodachi ga kita. / benkyō wa, shita. / jimu ga shinakatta.', '「来る → 来た」、「する → した」，否定形「しない」再变为过去否定「しなかった」。'),
            ),
            fc(
                'fc-jp04-2222-01', '非 iru/eru 结尾动词判定', ['p-jp04-verb-3classes'],
                '以下 5 个动词的字典形末尾都不是 /iru/ 或 /eru/，请判断它们全部属于哪一类动词（一段 / 五段）：',
                '読む・書く・遊ぶ・買う・死ぬ → {{blank:b1}}',
                f"{r('読', 'よ')}む・{r('書', 'か')}く・{r('遊', 'あそ')}ぶ・{r('買', 'か')}う・{r('死', 'し')}ぬ → {B1}",
                'yomu / kaku / asobu / kau / shinu → [ ? ]',
                '读・写・玩・买・死（判断动词大类：一段 / 五段）',
                [blank_spec('b1', '动词分类', ['五段', 'ごだん', '五段动词', '五段動詞', 'ごだんどうし'])],
                _expl(f"<strong>{r('五段', 'ごだん')}</strong>（{r('五段動詞', 'ごだんどうし')}）", 'godan (u-verbs)', '只要字典形末尾不是 /iru/ 或 /eru/ 发音（如 -mu / -ku / -bu / -u / -nu），百分之百归为五段动词。'),
            ),
            fc(
                'fc-jp04-2222-02', '标准一段动词识别', ['p-jp04-verb-3classes'],
                '以下动词均以 /iru/ 或 /eru/ 结尾且无五段特例，请判断它们全部属于哪一类动词（一段 / 五段）：',
                '食べる・見る・寝る・起きる・出る → {{blank:b1}}',
                f"{r('食', 'た')}べる・{r('見', 'み')}る・{r('寝', 'ね')}る・{r('起', 'お')}きる・{r('出', 'で')}る → {B1}",
                'taberu / miru / neru / okiru / deru → [ ? ]',
                '吃・看・睡・起床・出门（判断动词大类：一段 / 五段）',
                [blank_spec('b1', '动词分类', ['一段', 'いちだん', '一段动词', '一段動詞', 'いちだんどうし'])],
                _expl(f"<strong>{r('一段', 'いちだん')}</strong>（{r('一段動詞', 'いちだんどうし')}）", 'ichidan (ru-verbs)', '词尾「る」前假名为 /i/ 段或 /e/ 段且不在五段特例表内的词，属于一段动词。'),
            ),
            fc(
                'fc-jp04-2222-03', '唯二不规则动词记忆：「来る」与「する」', ['p-jp04-verb-3classes'],
                '日语动词分类中既不属于一段也不属于五段的两个不规则动词是「来る」和：',
                '来る ／ {{blank:b1}}',
                f"{r('来', 'く')}る ／ {B1}",
                'kuru / [ ? ]',
                '来 ／ 做（唯二不规则动词）',
                [blank_spec('b1', '不规则动词“做”', ['する'])],
                _expl(f"{r('来', 'く')}る ／ <strong>する</strong>", 'kuru / suru', '全日语只有「する」和「来る（くる）」两个独立不规则动词，其余几乎全可纳入一段/五段规则。'),
            ),
            fc(
                'fc-jp04-2222-04', '高频 iru/eru 五段特例组识别', ['p-jp04-iru-eru-exc'],
                '以下 4 个高频动词虽以 iru/eru 结尾，但均属假一段真五段特例，请填写其真正类别（一段 / 五段）：',
                '帰る・切る・入る・走る → {{blank:b1}}',
                f"{r('帰', 'かえ')}る・{r('切', 'き')}る・{r('入', 'はい')}る・{r('走', 'はし')}る → {B1}",
                'kaeru / kiru / hairu / hashiru → [ ? ]',
                '回家・切・进入・跑（判断真实所属大类：一段 / 五段）',
                [blank_spec('b1', '动词分类', ['五段', 'ごだん', '五段动词', '五段動詞', 'ごだんどうし'])],
                _expl(f"<strong>{r('五段', 'ごだん')}</strong>（{r('帰', 'かえ')}った・{r('切', 'き')}った・{r('入', 'はい')}った・{r('走', 'はし')}った）", 'godan (kaetta / kitta / haitta / hashitta)', '这 4 个高频特例动词过去式按五段促音变「帰った・切った・入った・走った」变化，绝不是「*帰た」。'),
            ),
            fc(
                'fc-jp04-2222-05', '混排辨认：找出唯一的 iru/eru 五段特例', ['p-jp04-iru-eru-exc'],
                '在下列以 /iru/ 或 /eru/ 结尾的 4 个动词中，唯一真正属于【五段动词（特例）】的是：',
                '着る・寝る・知る・出る → 五段特例：{{blank:b1}}',
                f"{r('着', 'き')}る・{r('寝', 'ね')}る・{r('知', 'し')}る・{r('出', 'で')}る → {r('五段特例', 'ごだんとくれい')}：{B1}",
                'kiru / neru / shiru / deru → [ ? ]',
                '在四个常用动词（着る / 寝る / 知る / 出る）中找出唯一的五段特例',
                [blank_spec('b1', '五段特例动词', ['知る', 'しる'])],
                _expl(f"<strong>{r('知', 'し')}る</strong>", 'shiru', '「着る」「寝る」「出る」是正规一段动词；「知る（shiru）」与「要る」「しゃべる」同为 iru/eru 五段特例。'),
            ),
            fc(
                'fc-jp04-2222-06', '综合复盘：同音「いる（存在）」vs「要る（需要）」词类对比', ['p-jp04-iru-eru-exc', 'p-jp04-aru-vs-iru'],
                '表示有生命存在的「いる」（人在）是一段动词，而表示“需要”的「要る」（iru）则属于哪一类动词（一段 / 五段）：',
                'いる（存在：一段） vs 要る（需要） → {{blank:b1}}',
                f"いる（{r('存在', 'そんざい')}：{r('一段', 'いちだん')}） vs {r('要', 'い')}る（{r('必要', 'ひつよう')}） → {B1}",
                'iru (exist: ichidan) vs iru (need) → [ ? ]',
                '“有/在”（一段） vs “需要”（判断「要る」所属动词大类：一段 / 五段）',
                [blank_spec('b1', '要る 的动词分类', ['五段', 'ごだん', '五段动词', '五段動詞', 'ごだんどうし'])],
                _expl(f"<strong>{r('五段', 'ごだん')}</strong>（{r('要', 'い')}った・{r('要', 'い')}らない）", 'godan (itta / iranai)', '同读音 /iru/ 却不同类：「いる」（存在，一段→いない）vs「要る」（需要，五段→要らない）。'),
            ),
            fc(
                'fc-jp04-2222-07', '一段动词过去时：「映画を見た」', ['p-jp04-past-ru'],
                '用一段动词「見る」的【过去肯定简体】补全句子：',
                '昨日、家で古い映画を全部{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('家', 'いえ')}で{r('古', 'ふる')}い{r('映画', 'えいが')}を{r('全部', 'ぜんぶ')}{B1}。",
                'kinō, ie de furui eiga o zenbu [ ? ].',
                '昨天在家里把老电影全看完了。',
                [blank_spec('b1', '見る 过去简体', ['見た', 'みた'])],
                _expl(f"{r('昨日', 'きのう')}、{r('家', 'いえ')}で{r('古', 'ふる')}い{r('映画', 'えいが')}を{r('全部', 'ぜんぶ')}<strong>{r('見', 'み')}た</strong>。", 'kinō, ie de furui eiga o zenbu mita.', '一段动词变过去式只需去掉词尾「る」直接加「た」：見る → 見た。'),
            ),
            fc(
                'fc-jp04-2222-08', '一段动词过去时：「家を出た」', ['p-jp04-past-ru'],
                '用一段动词「出る」的【过去肯定简体】补全句子：',
                '今朝、七時に家を{{blank:b1}}。',
                f"{r('今朝', 'けさ')}、{r('七時', 'しちじ')}に{r('家', 'いえ')}を{B1}。",
                'kesa, shichiji ni ie o [ ? ].',
                '今天早上七点出了门（离开了家）。',
                [blank_spec('b1', '出る 过去简体', ['出た', 'でた'])],
                _expl(f"{r('今朝', 'けさ')}、{r('七時', 'しちじ')}に{r('家', 'いえ')}を<strong>{r('出', 'で')}た</strong>。", 'kesa, shichiji ni ie o deta.', '「出る」为一段动词（-eru），去「る」加「た」即得「出た」。'),
            ),
            fc(
                'fc-jp04-2222-09', '「す」结尾五段过去时：「話した」', ['p-jp04-past-u-4rules'],
                '用「話す」的【过去肯定简体】补全句子：',
                '昨日、先生と日本語について長く{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('先生', 'せんせい')}と{r('日本語', 'にほんご')}について{r('長', 'なが')}く{B1}。",
                'kinō, sensei to nihongo ni tsuite nagaku [ ? ].',
                '昨天和老师关于日语聊了很久。',
                [blank_spec('b1', '話す 过去简体', ['話した', 'はなした'])],
                _expl(f"{r('昨日', 'きのう')}、{r('先生', 'せんせい')}と{r('日本語', 'にほんご')}について{r('長', 'なが')}く<strong>{r('話', 'はな')}した</strong>。", 'kinō, sensei to nihongo ni tsuite nagaku hanashita.', '以「す」结尾的五段动词（如 話す、出す），过去规则为 す → した。'),
            ),
            fc(
                'fc-jp04-2222-10', '「く」结尾五段清音音变：「書いた」', ['p-jp04-past-u-4rules'],
                '用「書く」的【过去肯定简体】补全句子：',
                '彼は手紙を{{blank:b1}}。',
                f"{r('彼', 'かれ')}は{r('手紙', 'てがみ')}を{B1}。",
                'kare wa tegami o [ ? ].',
                '他写了信。',
                [blank_spec('b1', '書く 过去简体', ['書いた', 'かいた'])],
                _expl(f"{r('彼', 'かれ')}は{r('手紙', 'てがみ')}を<strong>{r('書', 'か')}いた</strong>。", 'kare wa tegami o kaita.', '「く」结尾常规五段动词（書く、聞く、歩く）过去式 く → いた（唯一例外只有 行く → 行った）。'),
            ),
            fc(
                'fc-jp04-2222-11', '「ぐ」结尾五段浊音音变：「泳いだ」', ['p-jp04-past-u-4rules'],
                '用「泳ぐ」的【过去肯定简体】补全句子（注意保留浊音）：',
                '夏に海でよく{{blank:b1}}。',
                f"{r('夏', 'なつ')}に{r('海', 'うみ')}でよく{B1}。",
                'natsu ni umi de yoku [ ? ].',
                '夏天经常在海里游泳。',
                [blank_spec('b1', '泳ぐ 过去简体', ['泳いだ', 'およいだ'])],
                _expl(f"{r('夏', 'なつ')}に{r('海', 'うみ')}でよく<strong>{r('泳', 'およ')}いだ</strong>。", 'natsu ni umi de yoku oyoida.', '「ぐ」结尾带浊音，过去式保留浊音变成 いだ（千万不要忘写浊点变成「*泳いた」）。'),
            ),
            fc(
                'fc-jp04-2222-12', '「む」结尾拨音便：「飲んだ」', ['p-jp04-past-u-4rules'],
                '用「飲む」的【过去肯定简体】补全句子：',
                '今朝、冷たい水を{{blank:b1}}。',
                f"{r('今朝', 'けさ')}、{r('冷', 'つめ')}たい{r('水', 'みず')}を{B1}。",
                'kesa, tsumetai mizu o [ ? ].',
                '今天早上喝了凉水。',
                [blank_spec('b1', '飲む 过去简体', ['飲んだ', 'のんだ'])],
                _expl(f"{r('今朝', 'けさ')}、{r('冷', 'つめ')}たい{r('水', 'みず')}を<strong>{r('飲', 'の')}んだ</strong>。", 'kesa, tsumetai mizu o nonda.', 'む / ぬ / ぶ 结尾的五段动词发生拨音便并伴随浊音化：飲む → 飲んだ、読む → 読んだ。'),
            ),
            fc(
                'fc-jp04-2222-13', '「ぶ」结尾拨音便：「遊んだ」', ['p-jp04-past-u-4rules'],
                '用「遊ぶ」的【过去肯定简体】补全句子：',
                '昨日、公園で友達と一緒に{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('公園', 'こうえん')}で{r('友達', 'ともだち')}と{r('一緒', 'いっしょ')}に{B1}。",
                'kinō, kōen de tomodachi to issho ni [ ? ].',
                '昨天在公园里和朋友一起玩了。',
                [blank_spec('b1', '遊ぶ 过去简体', ['遊んだ', 'あそんだ'])],
                _expl(f"{r('昨日', 'きのう')}、{r('公園', 'こうえん')}で{r('友達', 'ともだち')}と{r('一緒', 'いっしょ')}に<strong>{r('遊', 'あそ')}んだ</strong>。", 'kinō, kōen de tomodachi to issho ni asonda.', '「ぶ」结尾同样变为 んだ（遊ぶ → 遊んだ；死ぬ → 死んだ），注意区分非浊音「った」。'),
            ),
            fc(
                'fc-jp04-2222-14', '「う」结尾促音便：「買った」', ['p-jp04-past-u-4rules'],
                '用「買う」的【过去肯定简体】补全句子：',
                '新しい靴を店で{{blank:b1}}。',
                f"{r('新', 'あたら')}しい{r('靴', 'くつ')}を{r('店', 'みせ')}で{B1}。",
                'atarashii kutsu o mise de [ ? ].',
                '在店里买了新鞋。',
                [blank_spec('b1', '買う 过去简体', ['買った', 'かった'])],
                _expl(f"{r('新', 'あたら')}しい{r('靴', 'くつ')}を{r('店', 'みせ')}で<strong>{r('買', 'か')}った</strong>。", 'atarashii kutsu o mise de katta.', 'う / つ / る（五段）统一促音变为 った（買う → 買った、待つ → 待った、持つ → 持った）。'),
            ),
            fc(
                'fc-jp04-2222-15', '综合复盘：五段「る」特例「帰る」过去促音变', ['p-jp04-past-u-4rules', 'p-jp04-iru-eru-exc'],
                '用五段特例动词「帰る」的【过去肯定简体】补全句子：',
                '朝、友達はもう家に{{blank:b1}}。',
                f"{r('朝', 'あさ')}、{r('友達', 'ともだち')}はもう{r('家', 'いえ')}に{B1}。",
                'asa, tomodachi wa mō ie ni [ ? ].',
                '早上朋友已经回家了。',
                [blank_spec('b1', '帰る 过去简体', ['帰った', 'かえった'])],
                _expl(f"{r('朝', 'あさ')}、{r('友達', 'ともだち')}はもう{r('家', 'いえ')}に<strong>{r('帰', 'かえ')}った</strong>。", 'asa, tomodachi wa mō ie ni kaetta.', '帰る、切る、入る、走る 是伪装成一段的五段动词，过去式遵循促音变 った（帰った），绝不是「*帰た」。'),
            ),
            fc(
                'fc-jp04-2222-16', '过去时三大特例：「行く → 行った」', ['p-jp04-past-3exc'],
                '用「行く」的【过去肯定简体】补全句子（警惕不要误写成「*行いた」）：',
                '昨日、駅まで歩いて{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('駅', 'えき')}まで{r('歩', 'ある')}いて{B1}。",
                'kinō, eki made aruite [ ? ].',
                '昨天步行去了车站。',
                [blank_spec('b1', '行く 过去简体', ['行った', 'いった'])],
                _expl(f"{r('昨日', 'きのう')}、{r('駅', 'えき')}まで{r('歩', 'ある')}いて<strong>{r('行', 'い')}った</strong>。", 'kinō, eki made aruite itta.', '「行く」虽以「く」结尾且其余变形皆规则（行かない），唯独过去形（及 て形）例外促音变为「行った」。'),
            ),
            fc(
                'fc-jp04-2222-17', '不规则动词过去式：「家へ来た」', ['p-jp04-past-3exc'],
                '用不规则动词「来る」的【过去肯定简体】补全句子：',
                '昨日、友達が家へ{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('友達', 'ともだち')}が{r('家', 'いえ')}へ{B1}。",
                'kinō, tomodachi ga ie e [ ? ].',
                '昨天朋友来我家了。',
                [blank_spec('b1', '来る 过去简体', ['来た', 'きた'])],
                _expl(f"{r('昨日', 'きのう')}、{r('友達', 'ともだち')}が{r('家', 'いえ')}へ<strong>{r('来', 'き')}た</strong>。", 'kinō, tomodachi ga ie e kita.', '「くる（来る）」过去式变作「きた（来た）」，「する」过去式变作「した」，需直接记忆。'),
            ),
            fc(
                'fc-jp04-2222-18', '一段动词过去否定：「食べなかった」', ['p-jp04-past-neg-rule'],
                '用一段动词「食べる」的【过去否定简体】补全句子：',
                '忙しくて、私は昨日ご飯を{{blank:b1}}。',
                f"{r('忙', 'いそが')}しくて、{r('私', 'わたし')}は{r('昨日', 'きのう')}ご{r('飯', 'はん')}を{B1}。",
                'isogashikute, watashi wa kinō gohan o [ ? ].',
                '因为太忙，我昨天没吃饭。',
                [blank_spec('b1', '食べる 过去否定', ['食べなかった', 'たべなかった'])],
                _expl(f"{r('忙', 'いそが')}しくて、{r('私', 'わたし')}は{r('昨日', 'きのう')}ご{r('飯', 'はん')}を<strong>{r('食', 'た')}べなかった</strong>。", 'isogashikute, watashi wa kinō gohan o tabenakatta.', '所有动词过去否定均遵循同一法则：先变否定形「ない」（食べない），再去「い」加「かった」。'),
            ),
            fc(
                'fc-jp04-2222-19', '五段「う→わ」联动过去否定：「買わなかった」', ['p-jp04-past-neg-rule'],
                '用「買う」的【过去否定简体】补全句子：',
                '高かったから、その車を{{blank:b1}}。',
                f"{r('高', 'たか')}かったから、その{r('車', 'くるま')}を{B1}。",
                'takakatta kara, sono kuruma o [ ? ].',
                '因为太贵了，所以没买那辆车。',
                [blank_spec('b1', '買う 过去否定', ['買わなかった', 'かわなかった'])],
                _expl(f"{r('高', 'たか')}かったから、その{r('車', 'くるま')}を<strong>{r('買', 'か')}わなかった</strong>。", 'takakatta kara, sono kuruma o kawanakatta.', '「買う」变否定时「う」必须变「わ」（買わない），再按统一步骤去「い」加「かった」得「買わなかった」。'),
            ),
            fc(
                'fc-jp04-2222-20', '综合复盘：存在动词「いる」过去否定', ['p-jp04-past-neg-rule', 'p-jp04-aru-vs-iru'],
                '学生属于有生命对象，请用存在动词「いる」的【过去否定简体】补全句子：',
                '昨日、図書館には学生が一人も{{blank:b1}}。',
                f"{r('昨日', 'きのう')}、{r('図書館', 'としょかん')}には{r('学生', 'がくせい')}が{r('一人', 'ひとり')}も{B1}。",
                'kinō, toshokan ni wa gakusei ga hitori mo [ ? ].',
                '昨天图书馆里一个学生都没有。',
                [blank_spec('b1', 'いる 过去否定', ['いなかった', '居なかった'])],
                _expl(f"{r('昨日', 'きのう')}、{r('図書館', 'としょかん')}には{r('学生', 'がくせい')}が{r('一人', 'ひとり')}も<strong>いなかった</strong>。", 'kinō, toshokan ni wa gakusei ga hitori mo inakatta.', '有生命物体（学生）用 いる → いない → いなかった；若是无生命物（如钱、时间）才用特例 ある → ない → なかった。'),
            ),
        ],
    },
    # =========================================================================
    # Topic 5: jp05-negation-system
    # =========================================================================
    {
        'id': 'jp05-negation-system',
        'title': '5. 否定型完整体系：名词・形容词・动词',
        'sections': [
            {
                'id': 'sec-jp05-distinction',
                'title': '一、三大区分法则：名词/な形否定 vs 动词否定与「んじゃない」',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp05-three-classes',
                'title': '二、三大词类否定变形全规律与所有必记特例',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp05-distinction',
                'section_id': 'sec-jp05-distinction',
                'title': '快速区分名词否定与动词否定的三大方法及「〜んじゃない」避坑',
                'html': (
                    '<h3>一、本质差异与三大快速区分法</h3>'
                    '<p>区分日语中<strong>名词否定</strong>与<strong>动词否定</strong>的核心在于：<strong>名词自身不变，靠外部助词「では / じゃ」连接否定；动词自身词干变形，直接咬合「ない」</strong>。</p>'
                    '<ol>'
                    '<li><strong>方法一（看中间有没有「では / じゃ」）</strong>：名词必须通过格助词「で」+ 提示助词「は」（口语缩读为「じゃ」）连接（<code>学生 ＋ じゃ ＋ ない ＝ 学生じゃない</code>、<code>先生 ＋ では ＋ ない ＝ 先生ではない</code>）；而动词直接词干变形加「ない」，中间绝不会出现「じゃ」（<code>行く → 行かない</code>，绝不说 <code>*行くじゃない</code>；<code>食べる → 食べない</code>）。</li>'
                    '<li><strong>方法二（看词本体是否变音）</strong>：名词词身完整无损（如 <code>学生 gakusei</code>、<code>日本人 nihonjin</code> 去掉否定词尾仍是完整名词）；动词词尾元音变成 /a/ 段或去掉「る」（<code>書か＋ない</code>←書く、<code>飲ま＋ない</code>←飲む、<code>食べ＋ない</code>←食べる），剩下的是不能独立成词的词干。</li>'
                    '<li><strong>方法三（看敬体词尾结尾）</strong>：动词敬体否定必定以<strong>「〜ません」</strong>结尾（<code>飲みません</code>、<code>行きません</code>）；名词敬体否定保留「では / じゃ」，以<strong>「〜じゃありません / 〜じゃないです / 〜ではありません」</strong>结尾（<code>学生じゃありません</code>、<code>学生じゃないです</code>、<code>会社員ではありません</code>）。</li>'
                    '</ol>'
                    '<h3>二、避坑提示：口语「动词 + んじゃない」是什么？</h3>'
                    '<p>日剧和动漫中的「' + term(f"{r('行', 'い')}くんじゃない！", 'ikun janai!', '不准去！') + '」或「' + term(f"{r('食', 'た')}べるんじゃない？", 'taberun janai?', '是不是要吃啊？') + '」不是普通动词否定：</p>'
                    '<ul>'
                    '<li><strong>行かない</strong>：单纯陈述“不去”（动词否定）。</li>'
                    '<li><strong>行くんじゃない</strong>：由 <code>行く ＋ の（缩读为 ん）＋ ではない</code> 构成，通过「の/ん」将动词名词化后套用名词否定框架，表达<strong>强烈禁止命令</strong>（“不准去！”）或<strong>反问揣测</strong>。</li>'
                    '</ul>'
                ),
            },
            {
                'id': 'intro-jp05-three-classes',
                'section_id': 'sec-jp05-three-classes',
                'title': '名词・形容词・动词否定变形完整规则与核心特例',
                'html': (
                    '<h3>一、名词（体言）与な形容词：全员统一、谨防“い结尾伪装者”</h3>'
                    '<p><strong>1. 名词否定公式（零例外）</strong>：无论本土词 ' + term(f"{r('雨', 'あめ')}", 'ame', '雨') + '、汉语词 ' + term(f"{r('学生', 'がくせい')}", 'gakusei', '学生') + '、还是外来语 ' + term('ホテル', 'hoteru', '酒店') + '（哪怕词尾刚好长得像「い」或「る」如 <code>先生</code>、<code>ホテル</code>），<strong>唯一公式</strong>都是：<code>名词 + じゃない / ではない</code>（敬体：<code>じゃありません / じゃないです / ではありません</code>）：<code>雨じゃない</code>、<code>ホテルじゃない</code>。</p>'
                    '<p><strong>2. な形容词（形容动词）</strong>：去掉连体词尾「な」后完全当作名词处理：<code>静かじゃない</code>、<code>簡単じゃない</code>。务必牢记以下“以「い」结尾的伪装者”：</p>'
                    + ex(f"きれい → きれい<strong>じゃない</strong> ／ {r('嫌', 'きら')}い → {r('嫌', 'きら')}い<strong>じゃない</strong> ／ {r('有名', 'ゆうめい')} → {r('有名', 'ゆうめい')}<strong>じゃない</strong>", 'kirei janai / kirai janai / yūmei janai', '不漂亮 ／ 不讨厌 ／ 不有名', '绝不能说「*きれくない」')
                    + '<h3>二、い形容词：去「い」换「く」+ ない，唯一特例「いい → よくない」</h3>'
                    '<p>所有真正的「い形容词」直接把末尾送假名「い」改为「くない」（敬体 <code>〜くないです / 〜くありません</code>）：'
                    + term(f"{r('高', 'たか')}い → {r('高', 'たか')}くない", 'takai → takakunai', '不高/不贵') + '、'
                    + term('おいしい → おいしくない', 'oishii → oishikunai', '不好吃') + '。</p>'
                    + tip('唯一特例「いい（好）」', '发生任何活用（含否定、过去时）时必须先还原为古语原形<strong>「よい」</strong>，因此否定为<strong>「よくない」</strong>（绝不能说 <code>*いくない</code>）。')
                    + '<h3>三、动词否定（未然形 + ない）与必记特殊音变</h3>'
                    '<ul>'
                    '<li><strong>一段动词（ru动词）</strong>：识别特征为以「る」结尾且前假名在 i/e 段，直接砍掉「る」加「ない」：<code>食べる → 食べない</code>、<code>見る → 見ない</code>。</li>'
                    '<li><strong>五段动词（u动词）</strong>：词尾假名从 u 段变为同行 a 段加「ない」：<code>書く (kaku) → 書かない (kakanai)</code>、<code>飲む (nomu) → 飲まない (nomanai)</code>、<code>作る (tsukuru) → 作らない (tsukuranai)</code>。<strong>两处必记特例</strong>：'
                    '<ol>'
                    '<li><strong>「う」结尾变成「わ」（而不是「あ」）</strong>：<code>買う (kau) → 買わない (kawanai，不买)</code>。</li>'
                    '<li><strong>「ある」（存在/有）</strong>：简体否定直接为<strong>「ない」</strong>（敬体依然是「ありません」）。</li>'
                    '</ol>'
                    '</li>'
                    '<li><strong>不规则动词（仅两个）</strong>：<code>する → しない</code>、<code>来る（くる）→ 来ない（こない）</code>（汉字「来」的读音从 <em>ku</em> 变为 <em>ko</em>）。</li>'
                    '</ul>'
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp05-noun-vs-verb-neg',
                'introduction_id': 'intro-jp05-distinction',
                'title': '名词与动词否定的三大本质差异及「んじゃない」避坑',
                'html': '<p>名词靠中介「では/じゃ」（敬体 〜じゃありません/〜ではありません），动词词干变形直接咬合「ない」（敬体 〜ません）；「んじゃない」为名词化禁止/反问。</p>',
                'anchor_quotes': ['一、本质差异与三大快速区分法', '二、避坑提示：口语「动词 + んじゃない」是什么？'],
                'points': [
                    {'id': 'p-jp05-dewa-ja', 'text': '名词否定须借助「では/じゃ」（敬体 〜じゃありません/〜ではありません），动词词干变形直接接「ない」（敬体 〜ません），词尾并发生元音切换或去る。'},
                    {'id': 'p-jp05-no-janai-trap', 'text': '「动词简体 + んじゃない」是「の(ん) + ではない」的名词化结构，表强烈禁止或反问揣测，区别于动词普通否定。'},
                ],
            },
            {
                'id': 'chunk-jp05-noun-adj-neg',
                'introduction_id': 'intro-jp05-three-classes',
                'title': '名词（零例外）、な形容词伪装者与い形容词「いい → よくない」',
                'html': '<p>名词含 ホテル、先生 零例外接 じゃない/ではない；な形容词 きれい・嫌い・有名 同理；い形容词去「い」加「くない」，特例「いい → よくない」。</p>',
                'anchor_quotes': ['一、名词（体言）与な形容词：全员统一、谨防“い结尾伪装者”', '二、い形容词：去「い」换「く」+ ない，唯一特例「いい → よくない」'],
                'points': [
                    {'id': 'p-jp05-noun-na-neg', 'text': '所有名词（如 雨・ホテル）和な形容词（如 静か・簡単・きれい・嫌い・有名）均按「词干 + じゃない / ではない」否定。'},
                    {'id': 'p-jp05-i-adj-neg', 'text': 'い形容词去「い」加「くない」（敬体 〜くないです / 〜くありません）；唯一特例「いい」须还原「よい」变为「よくない」。'},
                ],
            },
            {
                'id': 'chunk-jp05-verb-neg',
                'introduction_id': 'intro-jp05-three-classes',
                'title': '动词一段/五段/不规则「ない形」及三大特殊音变',
                'html': '<p>一段去る+ない；五段u变a+ない（「う→わ」如 買わない）；ある→ない（敬体ありません）；する→しない；来る(くる)→来ない(こない)。</p>',
                'anchor_quotes': ['三、动词否定（未然形 + ない）与必记特殊音变'],
                'points': [
                    {'id': 'p-jp05-ru-u-neg', 'text': '一段动词去「る」加「ない」；五段动词词尾 u 段变同行 a 段加「ない」，其中「う」结尾必须变「わ」（買う → 買わない）。'},
                    {'id': 'p-jp05-verb-neg-exc', 'text': '存在动词「ある」简体否定为「ない」（敬体「ありません」）；不规则动词「する → しない」、「来る（くる）→ 来ない（こない）」。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp05-01', '名词否定中介「じゃ / では」', ['p-jp05-dewa-ja'],
                '依次填入名词简体否定（口语缩读 vs 书面正式）所需的中介助词：',
                '学生{{blank:b1}}ない（口语） ／ 先生{{blank:b2}}ない（书面）',
                f"{r('学生', 'がくせい')}{B1}ない（口语） ／ {r('先生', 'せんせい')}{B2}ない（书面）",
                'gakusei [ ? ] nai / sensei [ ? ] nai',
                '不是学生（口语） ／ 不是老师（书面）',
                [blank_spec('b1', '口语中介', ['じゃ']), blank_spec('b2', '书面中介', ['では'])],
                _expl(f"{r('学生', 'がくせい')}<strong>じゃ</strong>ない ／ {r('先生', 'せんせい')}<strong>では</strong>ない", 'gakusei janai / sensei dewa nai', '名词自身不变，必须靠格助词「で」与提示助词「は」（口语缩读「じゃ」）连接否定。'),
            ),
            fc(
                'fc-jp05-02', '名词正式敬体否定「〜ではありません」', ['p-jp05-dewa-ja'],
                '使用正式书面礼貌否定结尾，补全“不是公司职员”：',
                '会社員{{blank:b1}}。',
                f"{r('会社員', 'かいしゃいん')}{B1}。",
                'kaishain [ ? ].',
                '不是公司职员。（正式礼貌否定）',
                [blank_spec('b1', '正式敬体否定', ['ではありません'])],
                _expl(f"{r('会社員', 'かいしゃいん')}<strong>ではありません</strong>。", 'kaishain dewa arimasen.', '名词敬体否定在「では/じゃ」后接「ありません」（或口语「〜じゃないです」）。'),
            ),
            fc(
                'fc-jp05-03', '动词敬体否定「飲みません」', ['p-jp05-dewa-ja'],
                '写出五段动词「飲む（喝）」的【敬体否定】（不喝）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（飲む → 敬体否定）',
                '不喝（敬体）',
                [blank_spec('b1', '敬体否定', ['飲みません', 'のみません'])],
                _expl(f"<strong>{r('飲', 'の')}みません</strong>", 'nomimasen', '动词敬体否定必定以「〜ません」结尾（词干「飲み」+「ません」）。'),
            ),
            fc(
                'fc-jp05-04', '动词敬体否定「行きません」', ['p-jp05-dewa-ja'],
                '写出动词「行く（去）」的【敬体否定】（不去）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（行く → 敬体否定）',
                '不去（敬体）',
                [blank_spec('b1', '敬体否定', ['行きません', 'いきません'])],
                _expl(f"<strong>{r('行', 'い')}きません</strong>", 'ikimasen', '五段动词「行く」的ます形词干为「行き」，加「ません」构成敬体否定。'),
            ),
            fc(
                'fc-jp05-05', '避坑对比：「行く＋んじゃない」强烈禁止', ['p-jp05-no-janai-trap'],
                '用形式名词化借用名词否定框架表达强烈禁止命令“不准去！”：',
                '行く{{blank:b1}}！',
                f"{r('行', 'い')}く{B1}！",
                'iku [ ? ]!',
                '不准去！（强烈禁止语气）',
                [blank_spec('b1', '形式名词化否定', ['んじゃない', 'のではない'])],
                _expl(f"{r('行', 'い')}く<strong>んじゃない</strong>！", 'ikun janai!', '「行く＋の(ん)＋ではない」借用名词否定结构表达强烈禁止“不准去！”，不是客观否定。'),
            ),
            fc(
                'fc-jp05-06', '与禁止区分：客观陈述“不去”（动词否定）', ['p-jp05-no-janai-trap'],
                '与「行くんじゃない」相反，单纯客观陈述“不去”（「行く」的【简体否定】）是：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（行く → 简体否定）',
                '不去（客观陈述）',
                [blank_spec('b1', '行く 简体否定', ['行かない', 'いかない'])],
                _expl(f"<strong>{r('行', 'い')}かない</strong>", 'ikanai', '动词直接未然形变形加「ない」（く→か+ない），客观表示“不去”。'),
            ),
            fc(
                'fc-jp05-07', '外来语名词以「る」结尾也不例外', ['p-jp05-noun-na-neg'],
                '写出「ホテル（酒店）」的【简体否定】“不是酒店”：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（ホテル → 简体否定）',
                '不是酒店（简体）',
                [blank_spec('b1', 'ホテル 简体否定', ['ホテルじゃない', 'ホテルではない'])],
                _expl('<strong>ホテルじゃない</strong>（书面：ホテルではない）', 'hoteru janai', '日语名词否定全员零例外，外来语词尾长得像「る」依然直接加「じゃない / ではない」。'),
            ),
            fc(
                'fc-jp05-08', 'な形容词伪装者「きれい」否定', ['p-jp05-noun-na-neg'],
                '写出「きれい（漂亮）」的【简体否定】（不漂亮）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（きれい → 简体否定）',
                '不漂亮（简体）',
                [blank_spec('b1', 'きれい 简体否定', ['きれいじゃない', 'きれいではない', '綺麗じゃない', '綺麗ではない'])],
                _expl(f"<strong>{r('綺麗', 'きれい')}じゃない</strong>（或：きれいじゃない）", 'kirei janai', '「きれい」是な形容词，去掉「な」按名词规则接「じゃない / ではない」。'),
            ),
            fc(
                'fc-jp05-09', '另两个常见“い结尾”な形容词否定', ['p-jp05-noun-na-neg'],
                '分别写出「嫌い（讨厌）」与「有名（有名）」的【口语简体否定】：',
                '嫌い → {{blank:b1}} ／ 有名 → {{blank:b2}}',
                f"{r('嫌', 'きら')}い → {B1} ／ {r('有名', 'ゆうめい')} → {B2}",
                'kirai → [ ? ] / yūmei → [ ? ]',
                '不讨厌 ／ 不有名（简体口语）',
                [
                    blank_spec('b1', '嫌い 否定', ['嫌いじゃない', 'きらいじゃない', '嫌いではない', 'きらいではない']),
                    blank_spec('b2', '有名 否定', ['有名じゃない', 'ゆうめいじゃない', '有名ではない', 'ゆうめいではない']),
                ],
                _expl(f"<strong>{r('嫌', 'きら')}いじゃない</strong> ／ <strong>{r('有名', 'ゆうめい')}じゃない</strong>", 'kirai janai / yūmei janai', '「嫌い」与「有名」均属な形容词，必须用「じゃない / ではない」否定。'),
            ),
            fc(
                'fc-jp05-10', 'い形容词否定「おいしい」', ['p-jp05-i-adj-neg'],
                '写出い形容词「おいしい（好吃）」的【简体否定】（不好吃）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（おいしい → 简体否定）',
                '不好吃（简体）',
                [blank_spec('b1', 'おいしい 简体否定', ['おいしくない', '美味しくない'])],
                _expl('<strong>おいしくない</strong>', 'oishikunai', 'い形容词去掉末尾送假名「い」变成「く」再接「ない」。'),
            ),
            fc(
                'fc-jp05-11', 'い形容词唯一特例「いい → よくない」', ['p-jp05-i-adj-neg'],
                '写出「いい（好）」的【简体否定】（不好）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（いい → 简体否定）',
                '不好（简体）',
                [blank_spec('b1', 'いい 简体否定', ['よくない', '良くない'])],
                _expl('<strong>よくない</strong>', 'yokunai', '「いい」变否定（及过去式）前必须还原成「よい」，再变为「よくない」（绝不可说「*いくない」）。'),
            ),
            fc(
                'fc-jp05-12', 'い形容词敬体否定「高くありません」', ['p-jp05-i-adj-neg'],
                '用「ありません」系正式敬体写出「高い（高/贵）」的【非过去否定】：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（高い → 正式非过去否定敬体）',
                '不高 / 不贵（礼貌敬体）',
                [blank_spec('b1', '高い 敬体否定', ['高くありません', 'たかくありません'])],
                _expl(f"<strong>{r('高', 'たか')}くありません</strong>", 'takaku arimasen', 'い形容词礼貌敬体否定可将「〜くない」改为「〜くないです」或更正式的「〜くありません」。'),
            ),
            fc(
                'fc-jp05-13', '一段动词简体否定「食べる / 見る」', ['p-jp05-ru-u-neg'],
                '分别写出「食べる（吃）」与「見る（看）」的【非过去否定简体】：',
                '食べる → {{blank:b1}} ／ 見る → {{blank:b2}}',
                f"{r('食', 'た')}べる → {B1} ／ {r('見', 'み')}る → {B2}",
                'taberu → [ ? ] / miru → [ ? ]',
                '不吃 ／ 不看（简体）',
                [blank_spec('b1', '食べる 否定', ['食べない', 'たべない']), blank_spec('b2', '見る 否定', ['見ない', 'みない'])],
                _expl(f"<strong>{r('食', 'た')}べない</strong> ／ <strong>{r('見', 'み')}ない</strong>", 'tabenai / minai', '一段动词规则极为简单：直接去掉「る」加「ない」。'),
            ),
            fc(
                'fc-jp05-14', '五段动词简体否定（u段变a段）', ['p-jp05-ru-u-neg'],
                '分别写出「書く」「飲む」「作る」的【非过去否定简体】：',
                '書く → {{blank:b1}} ／ 飲む → {{blank:b2}} ／ 作る → {{blank:b3}}',
                f"{r('書', 'か')}く → {B1} ／ {r('飲', 'の')}む → {B2} ／ {r('作', 'つく')}る → {B3}",
                'kaku → [ ? ] / nomu → [ ? ] / tsukuru → [ ? ]',
                '不写 ／ 不喝 ／ 不做',
                [
                    blank_spec('b1', '書く 否定', ['書かない', 'かかない']),
                    blank_spec('b2', '飲む 否定', ['飲まない', 'のまない']),
                    blank_spec('b3', '作る 否定', ['作らない', 'つくらない']),
                ],
                _expl(f"<strong>{r('書', 'か')}かない</strong> ／ <strong>{r('飲', 'の')}まない</strong> ／ <strong>{r('作', 'つく')}らない</strong>", 'kakanai / nomanai / tsukuranai', '五段动词未然形变化：ku→ka、mu→ma、ru→ra，然后直接加「ない」。'),
            ),
            fc(
                'fc-jp05-15', '五段特殊音变：「う」结尾变「わ」', ['p-jp05-ru-u-neg'],
                '写出「買う（买）」的【非过去否定简体】（不买）：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（買う → 简体否定）',
                '不买（简体）',
                [blank_spec('b1', '買う 简体否定', ['買わない', 'かわない'])],
                _expl(f"<strong>{r('買', 'か')}わない</strong>", 'kawanai', '以「う」结尾的五段动词（如「買う kau」）否定形变「わ」，得「買わない（kawanai）」。'),
            ),
            fc(
                'fc-jp05-16', '存在动词「ある」简体 vs 敬体否定', ['p-jp05-verb-neg-exc'],
                '用存在动词「ある」表达“没有钱”，依次写出【简体否定】与【敬体否定】：',
                '简体：お金が{{blank:b1}}。 ／ 敬体：お金が{{blank:b2}}。',
                f"简体：お{r('金', 'かね')}が{B1}。 ／ 敬体：お{r('金', 'かね')}が{B2}。",
                'okane ga [ ? ]. / okane ga [ ? ].',
                '没有钱（简体）／ 没有钱（敬体）',
                [blank_spec('b1', '简体否定', ['ない']), blank_spec('b2', '敬体否定', ['ありません'])],
                _expl(f"お{r('金', 'かね')}が<strong>ない</strong>。 ／ お{r('金', 'かね')}が<strong>ありません</strong>。", 'okane ga nai. / okane ga arimasen.', '「ある」的简体否定是特例「ない」（绝不说 *あらない），但敬体仍遵循五段ます形为「ありません」。'),
            ),
            fc(
                'fc-jp05-17', '两大不规则动词的简体否定', ['p-jp05-verb-neg-exc'],
                '分别写出「する」和「来る（くる）」的【简体否定】：',
                'する → {{blank:b1}} ／ 来る → {{blank:b2}}',
                f"する → {B1} ／ {r('来', 'く')}る → {B2}",
                'suru → [ ? ] / kuru → [ ? ]',
                '不做 ／ 不来（简体）',
                [blank_spec('b1', 'する 简体否定', ['しない']), blank_spec('b2', '来る 简体否定', ['来ない', 'こない'])],
                _expl(f"<strong>しない</strong> ／ <strong>{r('来', 'こ')}ない</strong>", 'shinai / konai', '「する → しない」，「来る（くる）→ 来ない（こない）」。'),
            ),
            fc(
                'fc-jp05-18', '不规则动词「来ない」的假名读音', ['p-jp05-verb-neg-exc'],
                '动词「来る（くる）」变为否定「来ない」后，汉字「来」的读音发生变化；请仅用【平假名】写出「来ない」的完整读音：',
                '来ない ＝ {{blank:b1}}',
                '来ない ＝ {{blank:b1}}',
                '来ない（请填完整平假名读音）',
                '不来（读音检查）',
                [blank_spec('b1', '平假名读音', ['こない'])],
                _expl(f"{r('来', 'こ')}ない ＝ <strong>こない</strong>", 'konai', '「来る」辞书形读「くる (kuru)」，变否定时汉字「来」变为「こ (ko)」，写作「こない」。'),
            ),
            fc(
                'fc-jp05-19', '综合复盘：な形伪装者 vs い形特例', ['p-jp05-noun-na-neg', 'p-jp05-i-adj-neg'],
                '对比写出「綺麗（漂亮）」与「いい（好）」的【简体否定】：',
                '綺麗 → {{blank:b1}} ／ いい → {{blank:b2}}',
                f"{r('綺麗', 'きれい')} → {B1} ／ いい → {B2}",
                'kirei → [ ? ] / ii → [ ? ]',
                '不漂亮 ／ 不好（简体）',
                [
                    blank_spec('b1', '綺麗 简体否定', ['綺麗じゃない', 'きれいじゃない', '綺麗ではない', 'きれいではない']),
                    blank_spec('b2', 'いい 简体否定', ['よくない', '良くない']),
                ],
                _expl(f"<strong>{r('綺麗', 'きれい')}じゃない</strong> ／ <strong>よくない</strong>", 'kirei janai / yokunai', '「綺麗/きれい」实为な形容词须加「じゃない」；「いい」是唯一须先还原为「よい」的い形容词，变「よくない」。'),
            ),
            fc(
                'fc-jp05-20', '综合复盘：动词否定四大特例总检', ['p-jp05-ru-u-neg', 'p-jp05-verb-neg-exc'],
                '依次写出四大必考陷阱动词的【简体否定】（買う・ある・する・来る）：',
                '買う → {{blank:b1}} ／ ある → {{blank:b2}} ／ する → {{blank:b3}} ／ 来る → {{blank:b4}}',
                f"{r('買', 'か')}う → {B1} ／ ある → {B2} ／ する → {B3} ／ {r('来', 'く')}る → {B4}",
                'kau → [ ? ] / aru → [ ? ] / suru → [ ? ] / kuru → [ ? ]',
                '不买 ／ 没有 ／ 不做 ／ 不来',
                [
                    blank_spec('b1', '買う 否定', ['買わない', 'かわない']),
                    blank_spec('b2', 'ある 否定', ['ない']),
                    blank_spec('b3', 'する 否定', ['しない']),
                    blank_spec('b4', '来る 否定', ['来ない', 'こない']),
                ],
                _expl(f"<strong>{r('買', 'か')}わない</strong> ／ <strong>ない</strong> ／ <strong>しない</strong> ／ <strong>{r('来', 'こ')}ない</strong>", 'kawanai / nai / shinai / konai', '「う→わ（買わない）」、「ある→ない」、「する→しない」、「来る(くる)→来ない(こない)」。'),
            ),
        ],
    },
    # =========================================================================
    # Topic 6: jp06-modifiers-and-listing
    # =========================================================================
    {
        'id': 'jp06-modifiers-and-listing',
        'title': '6. 连体修饰语序与并列列举助词',
        'sections': [
            {
                'id': 'sec-jp06-modifiers',
                'title': '一、连体修饰句（3.10.1〜3.10.3）与语序本质（3.10.4）',
                'level': 1,
                'parent_id': None,
            },
            {
                'id': 'sec-jp06-noun-particles',
                'title': '二、名词关联助词：と（3.11.2）、や/とか（3.11.3）与万能の（3.11.4〜3.11.5）',
                'level': 1,
                'parent_id': None,
            },
        ],
        'introductions': [
            {
                'id': 'intro-jp06-modifiers',
                'section_id': 'sec-jp06-modifiers',
                'title': '无关系代词的连体修饰小句（3.10.1〜3.10.3）与谓语后置铁律（3.10.4）',
                'html': (
                    '<h3>一、核心概念与状态表达小句修饰名词（3.10.1〜3.10.2）</h3>'
                    '<p>英语定语从句需要关系代词（<em>who / which / that</em>）并放在名词后面；日语<strong>不需要任何关系代词</strong>，动词活用形和状态小句在行为上如同「い形容词」，<strong>直接放在被修饰名词之前</strong>。</p>'
                    '<p><strong>状态表达小句修饰名词规律</strong>：在所有否定与过去活用形态中，名词和な形容词小句可直接前置修饰名词，形态与在句末独立结句时完全一致；<strong>只有“非过去肯定”不得用「だ」直接修饰名词</strong>，必须按词类分别替换为<strong>「の」</strong>（名词）或<strong>「な」</strong>（な形容词）。</p>'
                    + tbl(
                        ['时态 / 极性', '能否直接用句末形态修饰名词', '正确示例'],
                        [
                            ['非过去肯定', '<strong>不可以直接用「だ」</strong>（名词→「の」，な形→「な」）', f"{r('学生', 'がくせい')}<strong>の</strong>{r('人', 'ひと')} ／ {r('静', 'しず')}か<strong>な</strong>{r('部屋', 'へや')}"],
                            ['非过去否定', '可以（直接用「じゃない / ではない」）', ex(f"{r('学生', 'がくせい')}じゃない{r('人', 'ひと')}は、{r('学校', 'がっこう')}に{r('行', 'い')}かない。", 'gakusei janai hito wa, gakkō ni ikanai.', '不是学生的人不去学校。')],
                            ['过去肯定', '可以（直接用「だった」）', ex(f"{r('子供', 'こども')}だったアリスが{r('立派', 'りっぱ')}な{r('大人', 'おとな')}になった。", 'kodomo datta arisu ga rippa na otona ni natta.', '曾经是孩子的爱丽丝成了优秀的大人。')],
                            ['过去肯定（带时间）', '可以（直接用「だった」）', ex(f"{r('先週', 'せんしゅう')}に{r('医者', 'いしゃ')}だったボブは、{r('仕事', 'しごと')}を{r('辞', 'や')}めた。", 'senshū ni isha datta bobu wa, shigoto o yameta.', '上周还是医生的鲍勃辞职了。')],
                            ['过去否定', '可以（直接用「じゃなかった」）', ex(f"{r('友達', 'ともだち')}じゃなかったアリスは、いい{r('友達', 'ともだち')}になった。", 'tomodachi janakatta arisu wa, ii tomodachi ni natta.', '过去不是朋友的爱丽丝成了好朋友。')],
                        ],
                    )
                    + '<p><strong>补充：名词直接并列（Chaining of nouns）</strong>：多个名词直接组合构成复合词时中间不加任何助词，如 '
                    + term(f"{r('国際教育', 'こくさいきょういく')}センター", 'kokusai kyōiku sentā', '国际教育中心') + '、'
                    + term(f"{r('登場人物', 'とうじょうじんぶつ')}", 'tōjō jinbutsu', '登场人物') + '、'
                    + term(f"{r('立入禁止', 'たちいりきんし')}", 'tachiiri kinshi', '禁止入内') + '。</p>'
                    '<h3>二、动词小句修饰名词与嵌套定语（3.10.3）</h3>'
                    '<p>任何完整动词小句（包含时间、场所、主语、宾语），只要谓语保持<strong>简体（辞书形・〜ない形・〜た形・〜なかった形）</strong>，都能直接置于名词前作定语，甚至多层嵌套：</p>'
                    + ex(f"{r('先週', 'せんしゅう')}に{r('映画', 'えいが')}を{r('見', 'み')}た{r('人', 'ひと')}は{r('誰', 'だれ')}？", 'senshū ni eiga o mita hito wa dare?', '上周看了电影的人是谁？')
                    + ex(f"ボブは、いつも{r('勉強', 'べんきょう')}する{r('人', 'ひと')}だ。", 'bobu wa, itsumo benkyō suru hito da.', '鲍勃是一个总是学习的人。')
                    + ex(f"{r('赤', 'あか')}いズボンを{r('買', 'か')}う{r('友達', 'ともだち')}はボブだ。", 'akai zubon o kau tomodachi wa bobu da.', '买红裤子的朋友是鲍勃。')
                    + ex(f"{r('晩', 'ばん')}ご{r('飯', 'はん')}を{r('食', 'た')}べなかった{r('人', 'ひと')}は、{r('映画', 'えいが')}で{r('見', 'み')}た{r('銀行', 'ぎんこう')}に{r('行', 'い')}った。", 'bangohan o tabenakatta hito wa, eiga de mita ginkō ni itta.', '没吃晚饭的人去了在电影里看过的银行。', '嵌套修饰句：「食べなかった」修饰「人」，「見た」修饰「銀行」')
                    + '<h3>三、日语语序本质：谓语后置铁律与前部语序自由调换（3.10.4）</h3>'
                    '<p>并非“英语 SVO、日语只是死板的 SOV 倒装”。日语唯一必不可少且必须位于句末的是<strong>主句动词/谓语</strong>（如单说 ' + term(f"{r('食', 'た')}べた。", 'tabeta.', '吃了。') + ' 在语法上就是完整句子）；因为助词（<code>は・が・を・で</code>）已明确指定每个名词的角色，动词前面各成分的顺序可以自由调换：</p>'
                    + ex(f"{r('私', 'わたし')}は{r('公園', 'こうえん')}でお{r('弁当', 'べんとう')}を{r('食', 'た')}べた。 ＝ {r('公園', 'こうえん')}で{r('私', 'わたし')}はお{r('弁当', 'べんとう')}を{r('食', 'た')}べた。 ＝ お{r('弁当', 'べんとう')}を{r('私', 'わたし')}は{r('公園', 'こうえん')}で{r('食', 'た')}べた。", 'watashi wa kōen de obentō o tabeta.', '主语、场所、宾语位置互换意思完全成立；连体修饰句永远置于名词前（お弁当を食べた学生が公園に行った）。')
                ),
            },
            {
                'id': 'intro-jp06-noun-particles',
                'section_id': 'sec-jp06-noun-particles',
                'title': '名词关联助词：「と」「や・とか」与万能助词「の」（3.11.2〜3.11.5）',
                'html': (
                    '<h3>一、完全列举/同伴助词「と」（3.11.2）与模糊列举「や・とか」（3.11.3）</h3>'
                    '<ul>'
                    '<li><strong>完全列举（穷尽列出，无他项）</strong>：'
                    + ex(f"スプーン<strong>と</strong>フォークで{r('魚', 'さかな')}を{r('食', 'た')}べた。", 'supūn to fōku de sakana o tabeta.', '用勺子和叉子吃了鱼。')
                    + ex(f"{r('本', 'ほん')}<strong>と</strong>{r('雑誌', 'ざっし')}<strong>と</strong>{r('葉書', 'はがき')}を{r('買', 'か')}った。", 'hon to zasshi to hagaki o katta.', '买了书、杂志和明信片。')
                    + '</li>'
                    '<li><strong>共同动作对象 & 自动词「会う」辨析</strong>：'
                    + ex(f"{r('友達', 'ともだち')}<strong>と</strong>{r('話', 'はな')}した。", 'tomodachi to hanashita.', '和朋友说话了。', '对比对某人单向诉说可用「友達に話した」')
                    + ex(f"{r('先生', 'せんせい')}<strong>と</strong>{r('会', 'あ')}った。", 'sensei to atta.', '与老师见面了。', '「会う」是自动词，只能配「に / と」，绝不可用「*友達を会う」')
                    + tip('「と」的连接禁区', '<strong>「と」只能连接名词或名词短语</strong>，绝不能像英语 <em>and</em> 那样去直接连接两个动词、两个形容词或两个句子！')
                    + '</li>'
                    '<li><strong>不完全/模糊列举「や」（书面/标准）与「とか」（口语/随性）</strong>：暗示“……和……等（还有其他未提及事物）”：'
                    + ex(f"{r('飲', 'の')}み{r('物', 'もの')}<strong>や</strong>カップ<strong>や</strong>ナプキンは、いらない？ ／ {r('靴', 'くつ')}<strong>や</strong>シャツを{r('買', 'か')}う。", 'nomimono ya kappu ya napukin wa, iranai? / kutsu ya shatsu o kau.', '饮料、杯子、餐巾纸之类的不需要吗？／ 买鞋子、衬衫等。')
                    + ex(f"{r('飲', 'の')}み{r('物', 'もの')}<strong>とか</strong>カップ<strong>とか</strong>ナプキンは、いらない？ ／ {r('靴', 'くつ')}<strong>とか</strong>シャツを{r('買', 'か')}う。", 'nomimono toka kappu toka napukin wa, iranai? / kutsu toka shatsu o kau.', '饮料、杯子、餐巾纸什么的不需要吗？／ 买鞋子、衬衫什么的。')
                    + '</li>'
                    '</ul>'
                    '<h3>二、万能助词「の」的三大名词功能（3.11.4）与句尾解释语气（3.11.5）</h3>'
                    '<ol>'
                    '<li><strong>连接名词修饰名词（领属/属性/身份）</strong>：<code>ボブの本</code>（鲍勃的书）、<code>日本語の先生</code>（日语老师）、<code>メキシコ人の友達</code>（墨西哥朋友）。</li>'
                    '<li><strong>代称化（替代已知上文名词，相当于 one / thing）</strong>：'
                    + ex(f"そのシャツは{r('誰', 'だれ')}<strong>の</strong>？ — ボブ<strong>の</strong>だ。", 'sono shatsu wa dare no? — bobu no da.', '那件衬衫是谁的？——是鲍勃的[那件]。')
                    + '</li>'
                    '<li><strong>形容词/动词小句名词化（Nominalization）</strong>：接「の」后即可充当主语或宾语，且不用像 <code>物（具体物体）</code> 或 <code>こと（抽象事件）</code> 那样区分具象与抽象：'
                    + ex(f"{r('白', 'しろ')}い<strong>の</strong>は、かわいい。 ／ {r('授業', 'じゅぎょう')}に{r('行', 'い')}く<strong>の</strong>を{r('忘', 'わす')}れた。", 'shiroi no wa, kawaii. / jugyō ni iku no o wasureta.', '白色的那个很可爱（对比：白い物 具体物体）。／ 忘了去上课这件事（对比：授業に行くこと 抽象事件）。')
                    + '</li>'
                    '<li><strong>句尾说明/解释语气（3.11.5 Explanatory Tone）</strong>：置于句末赋予“其实是……嘛 / 事情是这样的”语气；接续「ようだ」等时仍保留名词用「の」、な形容词用「な」：'
                    + ex(f"{r('今', 'いま')}は{r('忙', 'いそが')}しい<strong>の</strong>。 ／ {r('学生', 'がくせい')}<strong>の</strong>ようだ。 ／ ここは{r('静', 'しず')}か<strong>な</strong>ようだ。", 'ima wa isogashii no. / gakusei no yō da. / koko wa shizuka na yō da.', '（其实）我现在挺忙的嘛。／ 看似是学生。／ 这里看似很安静。')
                    + '</li>'
                    '</ol>'
                ),
            },
        ],
        'memory_chunks': [
            {
                'id': 'chunk-jp06-state-subclause',
                'introduction_id': 'intro-jp06-modifiers',
                'title': '状态表达小句修饰名词与非过去肯定「の/な」例外',
                'html': '<p>「じゃない・だった・じゃなかった」直接修饰名词；仅非过去肯定禁「だ」而换「の」（名词）或「な」（な形）。另有直接名词罗列。</p>',
                'anchor_quotes': ['一、核心概念与状态表达小句修饰名词（3.10.1〜3.10.2）'],
                'points': [
                    {'id': 'p-jp06-state-mod', 'text': '修饰名词时否定（じゃない）、过去（だった）、过去否定（じゃなかった）与句末一致直接前置；唯非过去肯定禁止用「だ」须换「の/な」。'},
                ],
            },
            {
                'id': 'chunk-jp06-verb-subclause-order',
                'introduction_id': 'intro-jp06-modifiers',
                'title': '动词小句前置定语（无关系代词）与谓语后置・语序调换',
                'html': '<p>完整简体动词小句直接放名词前支持嵌套；主句谓语必放句末，动词前各成分因助词标位可自由调换。</p>',
                'anchor_quotes': ['二、动词小句修饰名词与嵌套定语（3.10.3）', '三、日语语序本质：谓语后置铁律与前部语序自由调换（3.10.4）'],
                'points': [
                    {'id': 'p-jp06-verb-mod', 'text': '日语无关系代词，简体动词小句直接前置修饰名词且支持嵌套（晩ご飯を食べなかった人は映画で見た銀行に行った）。'},
                    {'id': 'p-jp06-sentence-order', 'text': '主句核心谓语必须置于句末（单动词即可成句），谓语前面带格助词的各成分顺序可自由调换，定语小句必在名词前。'},
                ],
            },
            {
                'id': 'chunk-jp06-to-ya-toka',
                'introduction_id': 'intro-jp06-noun-particles',
                'title': '完全列举/同伴「と」（只连名词・会う配にと）与模糊列举「や/とか」',
                'html': '<p>「と」表穷尽列举与共同同伴（只连名词）；「会う」为自动词只能配「に/と」；「や/とか」表不完全模糊列举。</p>',
                'anchor_quotes': ['一、完全列举/同伴助词「と」（3.11.2）与模糊列举「や・とか」（3.11.3）'],
                'points': [
                    {'id': 'p-jp06-to-particle', 'text': '「と」只连名词或短语（不可连形容词/动词/句子），表穷尽列举及同伴（「会う」属自动词须用「友達に/と会う」，禁用「を」）。'},
                    {'id': 'p-jp06-ya-toka', 'text': '「や」（偏书面）与「とか」（口语随性）用于不完全模糊列举，暗示还有未列尽的事物。'},
                ],
            },
            {
                'id': 'chunk-jp06-no-particle',
                'introduction_id': 'intro-jp06-noun-particles',
                'title': '万能「の」三大名词功能与句尾说明语气（含「ようだ」接续）',
                'html': '<p>「の」用于属性连接、代称化(one)、形容词/动词名词化（对比 物/こと）以及句尾说明语气（「ようだ」前名词用「の」な形用「な」）。</p>',
                'anchor_quotes': ['二、万能助词「の」的三大名词功能（3.11.4）与句尾解释语气（3.11.5）'],
                'points': [
                    {'id': 'p-jp06-no-3uses', 'text': '「の」兼任名词连接（日本語の先生）、代称（誰の？→ボブのだ）及小句名词化（白いの・行くのを忘れた，无需区分具体物与抽象こと）。'},
                    {'id': 'p-jp06-no-explain', 'text': '句末「の」表解释说明语气（今は忙しいの）；「ようだ」前仍遵守名词用「の」（学生のようだ）、な形用「な」（静かなようだ）。'},
                ],
            },
        ],
        'flashcards': [
            fc(
                'fc-jp06-01', '状态否定小句直接修饰名词', ['p-jp06-state-mod'],
                '状态否定直接置于名词前作定语：“不是学生的人不去学校”：',
                '学生{{blank:b1}}人は、学校に行かない。',
                f"{r('学生', 'がくせい')}{B1}{r('人', 'ひと')}は、{r('学校', 'がっこう')}に{r('行', 'い')}かない。",
                'gakusei [ ? ] hito wa, gakkō ni ikanai.',
                '不是学生的人不去学校。',
                [blank_spec('b1', '否定状态（简体）', ['じゃない', 'ではない'])],
                _expl(f"{r('学生', 'がくせい')}<strong>じゃない</strong>{r('人', 'ひと')}は、{r('学校', 'がっこう')}に{r('行', 'い')}かない。", 'gakusei janai hito wa, gakkō ni ikanai.', '否定形「じゃない / ではない」在句末与修饰名词时的形态完全一致，可直接前置。'),
            ),
            fc(
                'fc-jp06-02', '状态过去小句直接修饰名词', ['p-jp06-state-mod'],
                '填入状态过去形，修饰“鲍勃”：“上周还是医生的鲍勃辞职了”：',
                '先週に医者{{blank:b1}}ボブは、仕事を辞めた。',
                f"{r('先週', 'せんしゅう')}に{r('医者', 'いしゃ')}{B1}ボブは、{r('仕事', 'しごと')}を{r('辞', 'や')}めた。",
                'senshū ni isha [ ? ] bobu wa, shigoto o yameta.',
                '上周还是医生的鲍勃辞职了。',
                [blank_spec('b1', '过去状态（简体）', ['だった'])],
                _expl(f"{r('先週', 'せんしゅう')}に{r('医者', 'いしゃ')}<strong>だった</strong>ボブは、{r('仕事', 'しごと')}を{r('辞', 'や')}めた。", 'senshū ni isha datta bobu wa, shigoto o yameta.', '过去形「だった」可直接置于名词前充当定语从句。'),
            ),
            fc(
                'fc-jp06-03', '状态过去否定小句直接修饰名词', ['p-jp06-state-mod'],
                '填入过去否定状态：“过去不是朋友的爱丽丝成了好朋友”：',
                '友達{{blank:b1}}アリスは、いい友達になった。',
                f"{r('友達', 'ともだち')}{B1}アリスは、いい{r('友達', 'ともだち')}になった。",
                'tomodachi [ ? ] arisu wa, ii tomodachi ni natta.',
                '过去不是朋友的爱丽丝成了好朋友。',
                [blank_spec('b1', '过去否定状态（简体）', ['じゃなかった', 'ではなかった'])],
                _expl(f"{r('友達', 'ともだち')}<strong>じゃなかった</strong>アリスは、いい{r('友達', 'ともだち')}になった。", 'tomodachi janakatta arisu wa, ii tomodachi ni natta.', '过去否定「じゃなかった / ではなかった」直接前置修饰名词。'),
            ),
            fc(
                'fc-jp06-04', '非过去肯定修饰唯一例外：の vs な', ['p-jp06-state-mod'],
                '依次填入非过去肯定状态下直接修饰名词所需的连接形式：',
                '学生{{blank:b1}}人 ／ 静か{{blank:b2}}部屋',
                f"{r('学生', 'がくせい')}{B1}{r('人', 'ひと')} ／ {r('静', 'しず')}か{B2}{r('部屋', 'へや')}",
                'gakusei [ ? ] hito / shizuka [ ? ] heya',
                '是学生的人 ／ 安静的房间',
                [blank_spec('b1', '名词定语', ['の']), blank_spec('b2', 'な形定语', ['な'])],
                _expl(f"{r('学生', 'がくせい')}<strong>の</strong>{r('人', 'ひと')} ／ {r('静', 'しず')}か<strong>な</strong>{r('部屋', 'へや')}", 'gakusei no hito / shizuka na heya', '仅“非过去肯定”需避开「だ」：名词用「の」，な形容词用「な」。'),
            ),
            fc(
                'fc-jp06-05', '动词过去小句前置修饰名词', ['p-jp06-verb-mod'],
                '将动词「見る」变为过去简体，直接放于「人」前作定语：“上周看了电影的人是谁？”',
                '先週に映画を{{blank:b1}}人は誰？',
                f"{r('先週', 'せんしゅう')}に{r('映画', 'えいが')}を{B1}{r('人', 'ひと')}は{r('誰', 'だれ')}？",
                'senshū ni eiga o [ ? ] hito wa dare?',
                '上周看了电影的人是谁？',
                [blank_spec('b1', '見る 过去简体', ['見た', 'みた'])],
                _expl(f"{r('先週', 'せんしゅう')}に{r('映画', 'えいが')}を<strong>{r('見', 'み')}た</strong>{r('人', 'ひと')}は{r('誰', 'だれ')}？", 'senshū ni eiga o mita hito wa dare?', '日语不需关系代词，保持简体的动词小句直接放在被修饰名词「人」前面。'),
            ),
            fc(
                'fc-jp06-06', '多层嵌套连体修饰句', ['p-jp06-verb-mod'],
                '分别将「食べる（过去否定简体）」与「見る（过去肯定简体）」填入两个嵌套定语小句：',
                '晩ご飯を{{blank:b1}}人は、映画で{{blank:b2}}銀行に行った。',
                f"{r('晩', 'ばん')}ご{r('飯', 'はん')}を{B1}{r('人', 'ひと')}は、{r('映画', 'えいが')}で{B2}{r('銀行', 'ぎんこう')}に{r('行', 'い')}った。",
                'bangohan o [ ? ] hito wa, eiga de [ ? ] ginkō ni itta.',
                '没吃晚饭的人去了在电影里看过的银行。',
                [
                    blank_spec('b1', '食べる 过去否定', ['食べなかった', 'たべなかった']),
                    blank_spec('b2', '見る 过去肯定', ['見た', 'みた']),
                ],
                _expl(f"{r('晩', 'ばん')}ご{r('飯', 'はん')}を<strong>{r('食', 'た')}べなかった</strong>{r('人', 'ひと')}は、{r('映画', 'えいが')}で<strong>{r('見', 'み')}た</strong>{r('銀行', 'ぎんこう')}に{r('行', 'い')}った。", 'bangohan o tabenakatta hito wa, eiga de mita ginkō ni itta.', '「食べなかった」修饰「人」，「映画で見た」修饰「銀行」，均须保持简体。'),
            ),
            fc(
                'fc-jp06-07', '动词辞书形小句修饰名词', ['p-jp06-verb-mod'],
                '用习惯/经常性动词辞书形「勉強する」修饰「人」：“鲍勃是一个总是学习的人”：',
                'ボブは、いつも{{blank:b1}}人だ。',
                f"ボブは、いつも{B1}{r('人', 'ひと')}だ。",
                'bobu wa, itsumo [ ? ] hito da.',
                '鲍勃是一个总是学习的人。',
                [blank_spec('b1', '学习（辞书形）', ['勉強する', 'べんきょうする'])],
                _expl(f"ボブは、いつも<strong>{r('勉強', 'べんきょう')}する</strong>{r('人', 'ひと')}だ。", 'bobu wa, itsumo benkyō suru hito da.', '动作习惯用简体辞书形「勉強する」直接置在「人」之前修饰。'),
            ),
            fc(
                'fc-jp06-08', '语序自由调换：靠格助词准确还原角色', ['p-jp06-sentence-order'],
                '即使把宾语提至句首、场所放在后面，只要助词正确意思就完全不变，依次填入三个格助词：',
                'お弁当{{blank:b1}}私{{blank:b2}}公園{{blank:b3}}食べた。',
                f"お{r('弁当', 'べんとう')}{B1}{r('私', 'わたし')}{B2}{r('公園', 'こうえん')}{B3}{r('食', 'た')}べた。",
                'obentō [ ? ] watashi [ ? ] kōen [ ? ] tabeta.',
                '（至于我，）在公园吃了便当。',
                [blank_spec('b1', '宾语助词', ['を']), blank_spec('b2', '主题助词', ['は']), blank_spec('b3', '活动场所', ['で'])],
                _expl(f"お{r('弁当', 'べんとう')}<strong>を</strong>{r('私', 'わたし')}<strong>は</strong>{r('公園', 'こうえん')}<strong>で</strong>{r('食', 'た')}べた。", 'obentō o watashi wa kōen de tabeta.', '核心谓语「食べた」留在句末；前面靠「を / は / で」锁定成分功能，语序可自由调换。'),
            ),
            fc(
                'fc-jp06-09', '修饰小句 + 句末谓语语序整合', ['p-jp06-sentence-order'],
                '依次填入从句修饰后的主语标识助词与移动精准终点助词：',
                'お弁当を食べた学生{{blank:b1}}公園{{blank:b2}}行った。',
                f"お{r('弁当', 'べんとう')}を{r('食', 'た')}べた{r('学生', 'がくせい')}{B1}{r('公園', 'こうえん')}{B2}{r('行', 'い')}った。",
                'obentō o tabeta gakusei [ ? ] kōen [ ? ] itta.',
                '吃了便当的学生去了公园（到达目的地）。',
                [blank_spec('b1', '主格助词', ['が']), blank_spec('b2', '精准目的地终点', ['に'])],
                _expl(f"お{r('弁当', 'べんとう')}を{r('食', 'た')}べた{r('学生', 'がくせい')}<strong>が</strong>{r('公園', 'こうえん')}<strong>に</strong>{r('行', 'い')}った。", 'obentō o tabeta gakusei ga kōen ni itta.', '连体修饰句置于「学生」前，全句主句谓语「行った」置于句末。'),
            ),
            fc(
                'fc-jp06-10', '完全列举助词「と」（两项全含）', ['p-jp06-to-particle'],
                '表示穷尽列举“用勺子和叉子（仅这两样）吃了鱼”：',
                'スプーン{{blank:b1}}フォークで魚を食べた。',
                f"スプーン{B1}フォークで{r('魚', 'さかな')}を{r('食', 'た')}べた。",
                'supūn [ ? ] fōku de sakana o tabeta.',
                '用勺子和叉子吃了鱼。',
                [blank_spec('b1', '完全列举助词', ['と'])],
                _expl(f"スプーン<strong>と</strong>フォークで{r('魚', 'さかな')}を{r('食', 'た')}べた。", 'supūn to fōku de sakana o tabeta.', '「と」用于连接名词作穷尽式完全列举。'),
            ),
            fc(
                'fc-jp06-11', '三项以上完全列举连用「と」', ['p-jp06-to-particle'],
                '穷尽列举“买了书、杂志和明信片（仅此三样）”：',
                '本{{blank:b1}}雑誌{{blank:b2}}葉書を買った。',
                f"{r('本', 'ほん')}{B1}{r('雑誌', 'ざっし')}{B2}{r('葉書', 'はがき')}を{r('買', 'か')}った。",
                'hon [ ? ] zasshi [ ? ] hagaki o katta.',
                '买了书、杂志和明信片。',
                [blank_spec('b1', '第一个并列', ['と']), blank_spec('b2', '第二个并列', ['と'])],
                _expl(f"{r('本', 'ほん')}<strong>と</strong>{r('雑誌', 'ざっし')}<strong>と</strong>{r('葉書', 'はがき')}を{r('買', 'か')}った。", 'hon to zasshi to hagaki o katta.', '多项名词穷尽列举时在各名词间依次放入「と」。'),
            ),
            fc(
                'fc-jp06-12', '自动词「会う」的伴随对象助词「と」', ['p-jp06-to-particle'],
                '请填入表示“与某人一起会面”的伴随对象助词：',
                '先生{{blank:b1}}会った。',
                f"{r('先生', 'せんせい')}{B1}{r('会', 'あ')}った。",
                'sensei [ ? ] atta.',
                '与老师见面了。（共同同伴）',
                [blank_spec('b1', '同伴助词', ['と'])],
                _expl(f"{r('先生', 'せんせい')}<strong>と</strong>{r('会', 'あ')}った。", 'sensei to atta.', '与人会面可用「と（同伴）」或「に（对象）」，绝不可误用「*先生を会った」。'),
            ),
            fc(
                'fc-jp06-13', '共同同伴「と」：和朋友交谈', ['p-jp06-to-particle'],
                '区分“对某人单向说（に）”与“和朋友互相交谈”，填入同伴助词：',
                '友達{{blank:b1}}話した。',
                f"{r('友達', 'ともだち')}{B1}{r('話', 'はな')}した。",
                'tomodachi [ ? ] hanashita.',
                '和朋友说话了。',
                [blank_spec('b1', '共同对象助词', ['と'])],
                _expl(f"{r('友達', 'ともだち')}<strong>と</strong>{r('話', 'はな')}した。", 'tomodachi to hanashita.', '表示共同互动的对象用「と」（「友達に話した」侧重单向诉说）。'),
            ),
            fc(
                'fc-jp06-14', '书面/标准不完全列举「や」', ['p-jp06-ya-toka'],
                '暗示除了列举出的鞋子和衬衫之外还有其他未提及物品，填入【标准模糊列举助词】：',
                '靴{{blank:b1}}シャツを買う。',
                f"{r('靴', 'くつ')}{B1}シャツを{r('買', 'か')}う。",
                'kutsu [ ? ] shatsu o kau.',
                '买鞋子、衬衫等。',
                [blank_spec('b1', '模糊列举助词', ['や'])],
                _expl(f"{r('靴', 'くつ')}<strong>や</strong>シャツを{r('買', 'か')}う。", 'kutsu ya shatsu o kau.', '「や」用于不完全列举代表性示例，意为“……和……等”。'),
            ),
            fc(
                'fc-jp06-15', '口语化模糊列举「とか」', ['p-jp06-ya-toka'],
                '使用更为随性、【口语化的模糊列举助词】补全两处空缺：',
                '飲み物{{blank:b1}}カップ{{blank:b2}}ナプキンは、いらない？',
                f"{r('飲', 'の')}み{r('物', 'もの')}{B1}カップ{B2}ナプキンは、いらない？",
                'nomimono [ ? ] kappu [ ? ] napukin wa, iranai?',
                '饮料、杯子、餐巾纸什么的不需要吗？',
                [blank_spec('b1', '口语列举一', ['とか']), blank_spec('b2', '口语列举二', ['とか'])],
                _expl(f"{r('飲', 'の')}み{r('物', 'もの')}<strong>とか</strong>カップ<strong>とか</strong>ナプキンは、いらない？", 'nomimono toka kappu toka napukin wa, iranai?', '「とか」功能与「や」相同，但更具口语随性感。'),
            ),
            fc(
                'fc-jp06-16', '「の」的代称化（替代上文已知物）', ['p-jp06-no-3uses'],
                '填入可替代上文已知名词、避免重复「シャツ」的代称助词（等同英语的 one）：',
                'そのシャツは誰{{blank:b1}}？ — ボブ{{blank:b2}}だ。',
                f"そのシャツは{r('誰', 'だれ')}{B1}？ — ボブ{B2}だ。",
                'sono shatsu wa dare [ ? ]? — bobu [ ? ] da.',
                '那件衬衫是谁的？——是鲍勃的（那件）。',
                [blank_spec('b1', '提问代称', ['の']), blank_spec('b2', '回答代称', ['の'])],
                _expl(f"そのシャツは{r('誰', 'だれ')}<strong>の</strong>？ — ボブ<strong>の</strong>だ。", 'sono shatsu wa dare no? — bobu no da.', '「の」能替代语境已知的名词，避免重复说出「シャツ」。'),
            ),
            fc(
                'fc-jp06-17', '「の」将形容词与动词小句名词化', ['p-jp06-no-3uses'],
                '分别将形容词「白い」与动词小句「授業に行く」转化为名词成分：',
                '白い{{blank:b1}}は、かわいい。 ／ 授業に行く{{blank:b2}}を忘れた。',
                f"{r('白', 'しろ')}い{B1}は、かわいい。 ／ {r('授業', 'じゅぎょう')}に{r('行', 'い')}く{B2}を{r('忘', 'わす')}れた。",
                'shiroi [ ? ] wa, kawaii. / jugyō ni iku [ ? ] o wasureta.',
                '白色的那个很可爱。／ 忘了去上课这件事。',
                [blank_spec('b1', '形容词名词化', ['の']), blank_spec('b2', '动词小句名词化', ['の'])],
                _expl(f"{r('白', 'しろ')}い<strong>の</strong>は、かわいい。 ／ {r('授業', 'じゅぎょう')}に{r('行', 'い')}く<strong>の</strong>を{r('忘', 'わす')}れた。", 'shiroi no wa, kawaii. / jugyō ni iku no o wasureta.', '「の」作为通用名词化助词，可接在形容词或动词小句后直接充当主语或宾语。'),
            ),
            fc(
                'fc-jp06-18', '「物」vs「こと」与「の」的精细对比', ['p-jp06-no-3uses'],
                '如果不用通用「の」而要明确区分为【具体实物】与【抽象事件/概念】，分别应接：',
                '白い{{blank:b1}}（具体物体） ／ 授業に行く{{blank:b2}}（抽象事件）',
                f"{r('白', 'しろ')}い{B1}（具体物体） ／ {r('授業', 'じゅぎょう')}に{r('行', 'い')}く{B2}（抽象事件）",
                'shiroi [ ? ] / jugyō ni iku [ ? ]',
                '白色的物体 ／ 去上课这件事',
                [blank_spec('b1', '具体物体', ['物', 'もの']), blank_spec('b2', '抽象事件', ['こと', '事'])],
                _expl(f"{r('白', 'しろ')}い<strong>{r('物', 'もの')}</strong> ／ {r('授業', 'じゅぎょう')}に{r('行', 'い')}く<strong>こと</strong>", 'shiroi mono / jugyō ni iku koto', '「物（もの）」特指具体实物，「こと」特指抽象概念事件；而「の」可同时涵盖两者。'),
            ),
            fc(
                'fc-jp06-19', '句末说明/解释语气「の」', ['p-jp06-no-explain'],
                '在句尾填入赋予“其实是……嘛”说明解释语气的助词：',
                '今は忙しい{{blank:b1}}。',
                f"{r('今', 'いま')}は{r('忙', 'いそが')}しい{B1}。",
                'ima wa isogashii [ ? ].',
                '（其实）我现在挺忙的嘛。',
                [blank_spec('b1', '句尾解释助词', ['の'])],
                _expl(f"{r('今', 'いま')}は{r('忙', 'いそが')}しい<strong>の</strong>。", 'ima wa isogashii no.', '置于句尾的「の」赋予全句说明原因、解释隐情的语气。'),
            ),
            fc(
                'fc-jp06-20', '接续「ようだ」时名词「の」与な形「な」', ['p-jp06-no-explain'],
                '「ようだ（看似……）」前必须严格遵守非过去肯定修饰规律，依次填入：',
                '学生{{blank:b1}}ようだ。 ／ ここは静か{{blank:b2}}ようだ。',
                f"{r('学生', 'がくせい')}{B1}ようだ。 ／ ここは{r('静', 'しず')}か{B2}ようだ。",
                'gakusei [ ? ] yō da. / koko wa shizuka [ ? ] yō da.',
                '看似是学生。／ 这里看似很安静。',
                [blank_spec('b1', '名词接「ようだ」', ['の']), blank_spec('b2', 'な形接「ようだ」', ['な'])],
                _expl(f"{r('学生', 'がくせい')}<strong>の</strong>ようだ。 ／ ここは{r('静', 'しず')}か<strong>な</strong>ようだ。", 'gakusei no yō da. / koko wa shizuka na yō da.', '因为「ようだ」属于名词性助动词，修饰它时名词用「の」、な形容词用「な」。'),
            ),
            fc(
                'fc-jp06-21', '综合复盘：状态修饰 vs 动词修饰', ['p-jp06-state-mod', 'p-jp06-verb-mod'],
                '依次补全“曾经是孩子”“不是学生”“买红裤子”三组前置定语：',
                '子供{{blank:b1}}アリス ／ 学生{{blank:b2}}人 ／ 赤いズボンを{{blank:b3}}友達',
                f"{r('子供', 'こども')}{B1}アリス ／ {r('学生', 'がくせい')}{B2}{r('人', 'ひと')} ／ {r('赤', 'あか')}いズボンを{B3}{r('友達', 'ともだち')}",
                'kodomo [ ? ] arisu / gakusei [ ? ] hito / akai zubon o [ ? ] tomodachi',
                '曾经是孩子的爱丽丝 ／ 不是学生的人 ／ 买红裤子的朋友',
                [
                    blank_spec('b1', '过去状态定语', ['だった']),
                    blank_spec('b2', '否定状态定语', ['じゃない', 'ではない']),
                    blank_spec('b3', '买（辞书形）', ['買う', 'かう']),
                ],
                _expl(f"{r('子供', 'こども')}<strong>だった</strong>アリス ／ {r('学生', 'がくせい')}<strong>じゃない</strong>{r('人', 'ひと')} ／ {r('赤', 'あか')}いズボンを<strong>{r('買', 'か')}う</strong>{r('友達', 'ともだち')}", 'kodomo datta arisu / gakusei janai hito / akai zubon o kau tomodachi', '过去「だった」、否定「じゃない」与动词简体「買う」均可直接置于被修饰名词前。'),
            ),
            fc(
                'fc-jp06-2222-01', '状态否定小句修饰名词：「この部屋に入らない」', ['p-jp06-state-mod'],
                '填入状态非过去否定形式，直接置于名词前作定语（“不是学生的人不进这房间”）：',
                '学生{{blank:b1}}人は、この部屋に入らない。',
                f"{r('学生', 'がくせい')}{B1}{r('人', 'ひと')}は、この{r('部屋', 'へや')}に{r('入', 'はい')}らない。",
                'gakusei [ ? ] hito wa, kono heya ni hairanai.',
                '不是学生的人，不进这个房间。',
                [blank_spec('b1', '否定状态（简体）', ['じゃない', 'ではない'])],
                _expl(f"{r('学生', 'がくせい')}<strong>じゃない</strong>{r('人', 'ひと')}は、この{r('部屋', 'へや')}に{r('入', 'はい')}らない。", 'gakusei janai hito wa, kono heya ni hairanai.', '状态表达的否定形（〜じゃない / 〜ではない）形态不变，无需借助「の/な」即可直接置在名词前作定语。'),
            ),
            fc(
                'fc-jp06-2222-02', '状态过去小句修饰名词：「先生だった彼女」', ['p-jp06-state-mod'],
                '填入状态过去肯定形式，直接修饰后面的「彼女」：',
                '先週まで先生{{blank:b1}}彼女は、仕事を辞めた。',
                f"{r('先週', 'せんしゅう')}まで{r('先生', 'せんせい')}{B1}{r('彼女', 'かのじょ')}は、{r('仕事', 'しごと')}を{r('辞', 'や')}めた。",
                'senshū made sensei [ ? ] kanojo wa, shigoto o yameta.',
                '上周为止还是老师的她，辞掉了工作。',
                [blank_spec('b1', '过去状态（简体）', ['だった'])],
                _expl(f"{r('先週', 'せんしゅう')}まで{r('先生', 'せんせい')}<strong>だった</strong>{r('彼女', 'かのじょ')}は、{r('仕事', 'しごと')}を{r('辞', 'や')}めた。", 'senshū made sensei datta kanojo wa, shigoto o yameta.', '过去肯定「〜だった」（及过去否定「〜じゃなかった」）均可直接修饰后面的名词。'),
            ),
            fc(
                'fc-jp06-2222-03', '非过去肯定修饰名词禁用「だ」纠错', ['p-jp06-state-mod'],
                '不能说「*学生だ人」；非过去肯定直接修饰名词时不可用「だ」，此处中间必须改用：',
                '学生{{blank:b1}}人',
                f"{r('学生', 'がくせい')}{B1}{r('人', 'ひと')}",
                'gakusei [ ? ] hito',
                '是学生的人',
                [blank_spec('b1', '名词定语助词', ['の'])],
                _expl(f"{r('学生', 'がくせい')}<strong>の</strong>{r('人', 'ひと')}", 'gakusei no hito', '只有非过去肯定的「だ」被禁止直接放名词前，名词必须由修饰助词「の」接管（な形容词用「な」）。'),
            ),
            fc(
                'fc-jp06-2222-04', '动词过去小句修饰名词：「昨日、手紙を書いた人」', ['p-jp06-verb-mod'],
                '用「書く」的【过去肯定简体】直接修饰「人」，表达“昨天写信的人是谁？”：',
                '昨日、手紙を{{blank:b1}}人は誰？',
                f"{r('昨日', 'きのう')}、{r('手紙', 'てがみ')}を{B1}{r('人', 'ひと')}は{r('誰', 'だれ')}？",
                'kinō, tegami o [ ? ] hito wa dare?',
                '昨天写了信的人是谁？',
                [blank_spec('b1', '書く 过去简体', ['書いた', 'かいた'])],
                _expl(f"{r('昨日', 'きのう')}、{r('手紙', 'てがみ')}を<strong>{r('書', 'か')}いた</strong>{r('人', 'ひと')}は{r('誰', 'だれ')}？", 'kinō, tegami o kaita hito wa dare?', '日语没有关系代词，完整动词小句保持简体直接挂到被修饰名词「人」前面。'),
            ),
            fc(
                'fc-jp06-2222-05', '动词现在肯定小句修饰名词：「赤い靴を買う友達」', ['p-jp06-verb-mod'],
                '用表示“买”的动词【现在肯定辞书形】补全连体修饰小句：',
                '赤い靴を{{blank:b1}}友達は、あそこにいる。',
                f"{r('赤', 'あか')}い{r('靴', 'くつ')}を{B1}{r('友達', 'ともだち')}は、あそこにいる。",
                'akai kutsu o [ ? ] tomodachi wa, asoko ni iru.',
                '买红鞋的朋友就在那边。',
                [blank_spec('b1', '买（辞书形）', ['買う', 'かう'])],
                _expl(f"{r('赤', 'あか')}い{r('靴', 'くつ')}を<strong>{r('買', 'か')}う</strong>{r('友達', 'ともだち')}は、あそこにいる。", 'akai kutsu o kau tomodachi wa, asoko ni iru.', '以辞书形结尾的动词小句可直接置于「友達」前面修饰名词，无需关系代词。'),
            ),
            fc(
                'fc-jp06-2222-06', '双层嵌套动词定语小句：「昨日見た店」', ['p-jp06-verb-mod'],
                '前句否定修饰「友達」，后句用「見る」的【过去肯定简体】修饰「店」完成双层嵌套：',
                '朝ご飯を食べなかった友達は、昨日{{blank:b1}}店に行った。',
                f"{r('朝', 'あさ')}ご{r('飯', 'はん')}を{r('食', 'た')}べなかった{r('友達', 'ともだち')}は、{r('昨日', 'きのう')}{B1}{r('店', 'みせ')}に{r('行', 'い')}った。",
                'asagohan o tabenakatta tomodachi wa, kinō [ ? ] mise ni itta.',
                '没吃早饭的朋友，去了昨天看过的店。',
                [blank_spec('b1', '見る 过去简体', ['見た', 'みた'])],
                _expl(f"{r('朝', 'あさ')}ご{r('飯', 'はん')}を{r('食', 'た')}べなかった{r('友達', 'ともだち')}は、{r('昨日', 'きのう')}<strong>{r('見', 'み')}た</strong>{r('店', 'みせ')}に{r('行', 'い')}った。", 'asagohan o tabenakatta tomodachi wa, kinō mita mise ni itta.', '前句修饰「友達」（过去否定），后句「昨日見た」修饰「店」（过去肯定），各自在所属名词前用简体收束。'),
            ),
            fc(
                'fc-jp06-2222-07', '日语语序铁律：唯一固定锁定句末的谓语动词', ['p-jp06-sentence-order'],
                '无论把「私は・公園で・お弁当を」怎么调换前部语序，全句唯一必须锁定在句末的核心动词（“吃”的过去简体）是：',
                'お弁当を私は公園で{{blank:b1}}。',
                f"お{r('弁当', 'べんとう')}を{r('私', 'わたし')}は{r('公園', 'こうえん')}で{B1}。",
                'obentō o watashi wa kōen de [ ? ].',
                '我在公园吃了便当。',
                [blank_spec('b1', '句末核心动词', ['食べた', 'たべた'])],
                _expl(f"お{r('弁当', 'べんとう')}を{r('私', 'わたし')}は{r('公園', 'こうえん')}で<strong>{r('食', 'た')}べた</strong>。", 'obentō o watashi wa kōen de tabeta.', '格助词（は / で / を）已标明语法角色，所以动词前的成分顺序自由，唯独主句核心动词「食べた」不可移出句末。'),
            ),
            fc(
                'fc-jp06-2222-08', '极简完整句：单动词即可成句', ['p-jp06-sentence-order'],
                '在对话中表示“（已经）吃过了”时，日语省略主语与宾语，仅用这一个动词（过去简体）即可构成语法完整的句子：',
                '{{blank:b1}}',
                '{{blank:b1}}',
                '[ ? ]（“吃”的过去简体，单动词成句）',
                '吃过了。（极简完整句）',
                [blank_spec('b1', '单动词完整句', ['食べた', 'たべた', '食べた。', 'たべた。'])],
                _expl(f"<strong>{r('食', 'た')}べた。</strong>", 'tabeta.', '日语唯一不可缺少的核心成分只有句末谓语/动词，已知语境下的主语与宾语均可省略。'),
            ),
            fc(
                'fc-jp06-2222-09', '穷尽式完全列举：「本と手紙」', ['p-jp06-to-particle'],
                '一共只买了书和信纸这两样（不含其他），填入穷尽式完全列举助词：',
                '店で本{{blank:b1}}手紙を買った。',
                f"{r('店', 'みせ')}で{r('本', 'ほん')}{B1}{r('手紙', 'てがみ')}を{r('買', 'か')}った。",
                'mise de hon [ ? ] tegami o katta.',
                '在店里买了书和信纸（仅此两样）。',
                [blank_spec('b1', '完全列举助词', ['と'])],
                _expl(f"{r('店', 'みせ')}で{r('本', 'ほん')}<strong>と</strong>{r('手紙', 'てがみ')}を{r('買', 'か')}った。", 'mise de hon to tegami o katta.', '「と」用于列出全部项目（不含“等其他物品”），仅连接名词或名词短语。'),
            ),
            fc(
                'fc-jp06-2222-10', '共同动作伴随对象：「友達と公園で遊んだ」', ['p-jp06-to-particle'],
                '与动作动词「遊ぶ」连用时，填入标记“和某人一起”的伴随助词：',
                '日曜日、友達{{blank:b1}}公園で遊んだ。',
                f"{r('日曜日', 'にちようび')}、{r('友達', 'ともだち')}{B1}{r('公園', 'こうえん')}で{r('遊', 'あそ')}んだ。",
                'nichiyōbi, tomodachi [ ? ] kōen de asonda.',
                '周日和朋友在公园玩了。',
                [blank_spec('b1', '伴随对象助词', ['と'])],
                _expl(f"{r('日曜日', 'にちようび')}、{r('友達', 'ともだち')}<strong>と</strong>{r('公園', 'こうえん')}で{r('遊', 'あそ')}んだ。", 'nichiyōbi, tomodachi to kōen de asonda.', '与动作动词「遊ぶ」「話す」「会う」连用时，「と」标记“和某人一起”。'),
            ),
            fc(
                'fc-jp06-2222-11', '「と」词性连接限制纠错（只连名词）', ['p-jp06-to-particle'],
                '助词「と」有严格的词性连接限制；下列两句中，语法错误的是（请填选项字母 A 或 B）：',
                'A. 先生と話した ／ B. 高いと新しい本を買った → {{blank:b1}}',
                f"A. {r('先生', 'せんせい')}と{r('話', 'はな')}した ／ B. {r('高', 'たか')}いと{r('新', 'あたら')}しい{r('本', 'ほん')}を{r('買', 'か')}った → {B1}",
                'A. sensei to hanashita / B. takai to atarashii hon o katta → [ ? ]',
                '选出违反「と」连接限制的错句（A / B）',
                [blank_spec('b1', '错误句选项', ['B', 'b'])],
                _expl(f"<strong>B</strong>（{r('正', 'ただ')}しい{r('例', 'れい')}：A. {r('先生', 'せんせい')}と{r('話', 'はな')}した）", 'B is ungrammatical (correct: A. sensei to hanashita)', '错句为 B：日语的「と」只能连接名词或名词短语，绝不能像英语 and 那样直接连接两个形容词或两个动词小句。'),
            ),
            fc(
                'fc-jp06-2222-12', '不完全列举「や」：「冷たい水やお茶など」', ['p-jp06-ya-toka'],
                '暗示除了凉水和茶之外还有其他未尽举的饮料，填入标准模糊列举助词：',
                '冷たい水{{blank:b1}}お茶などは、いらない？',
                f"{r('冷', 'つめ')}たい{r('水', 'みず')}{B1}お{r('茶', 'ちゃ')}などは、いらない？",
                'tsumetai mizu [ ? ] ocha nado wa, iranai?',
                '凉水、茶之类的东西，不需要吗？',
                [blank_spec('b1', '模糊列举助词', ['や'])],
                _expl(f"{r('冷', 'つめ')}たい{r('水', 'みず')}<strong>や</strong>お{r('茶', 'ちゃ')}などは、いらない？", 'tsumetai mizu ya ocha nado wa, iranai?', '当想表达“A 和 B 等（言外还有别的）”时使用不完全列举助词「や」。'),
            ),
            fc(
                'fc-jp06-2222-13', '口语模糊列举「とか」：「靴とか服」', ['p-jp06-ya-toka'],
                '用比「や」更口语随性的模糊列举助词补全“鞋子、衣服什么的”：',
                '休みに靴{{blank:b1}}服を買うつもりだ。',
                f"{r('休', 'やす')}みに{r('靴', 'くつ')}{B1}{r('服', 'ふく')}を{r('買', 'か')}うつもりだ。",
                'yasumi ni kutsu [ ? ] fuku o kau tsumori da.',
                '打算放假时买点鞋子、衣服什么的。',
                [blank_spec('b1', '口语列举助词', ['とか'])],
                _expl(f"{r('休', 'やす')}みに{r('靴', 'くつ')}<strong>とか</strong>{r('服', 'ふく')}を{r('買', 'か')}うつもりだ。", 'yasumi ni kutsu toka fuku o kau tsumori da.', '「とか」与「や」一样表不完全列举，但语气更口语、随性。'),
            ),
            fc(
                'fc-jp06-2222-14', '「の」属性修饰链顺序：「日本の大学の学生」', ['p-jp06-no-3uses'],
                '按日语从前向后逐层收窄修饰的顺序，填入缺少的名词连接助词：',
                '彼は日本{{blank:b1}}大学の学生だ。',
                f"{r('彼', 'かれ')}は{r('日本', 'にほん')}{B1}{r('大学', 'だいがく')}の{r('学生', 'がくせい')}だ。",
                'kare wa nihon [ ? ] daigaku no gakusei da.',
                '他是日本一所大学的学生。',
                [blank_spec('b1', '属性连接助词', ['の'])],
                _expl(f"{r('彼', 'かれ')}は{r('日本', 'にほん')}<strong>の</strong>{r('大学', 'だいがく')}の{r('学生', 'がくせい')}だ。", 'kare wa nihon no daigaku no gakusei da.', '日语修饰关系用「の」从前向后逐层收窄（日本の大学 → 日本の大学の学生），不可倒装。'),
            ),
            fc(
                'fc-jp06-2222-15', '「の」替代已知重复名词：「私のだ」', ['p-jp06-no-3uses'],
                '上下文已明确讨论「本」，用代称助词省略重复中心名词“（我的）那本”：',
                'その本は誰の本？ ああ、私{{blank:b1}}だ。',
                f"その{r('本', 'ほん')}は{r('誰', 'だれ')}の{r('本', 'ほん')}？ ああ、{r('私', 'わたし')}{B1}だ。",
                'sono hon wa dare no hon? aa, watashi [ ? ] da.',
                '那本书是谁的书？ 哦，是我（的那本）。',
                [blank_spec('b1', '代称助词', ['の'])],
                _expl(f"その{r('本', 'ほん')}は{r('誰', 'だれ')}の{r('本', 'ほん')}？ ああ、{r('私', 'わたし')}<strong>の</strong>だ。", 'sono hon wa dare no hon? aa, watashi no da.', '上下文已经明确讨论「本」时，用「私の」即可替代「私の本」，省略重复中心名词。'),
            ),
            fc(
                'fc-jp06-2222-16', '「の」将动词小句名词化：「行くのを忘れた」', ['p-jp06-no-3uses'],
                '填入将动词短语「学校に行く」直接名词化以衔接宾格「を」的助词：',
                '昨日、学校に行く{{blank:b1}}を忘れた。',
                f"{r('昨日', 'きのう')}、{r('学校', 'がっこう')}に{r('行', 'い')}く{B1}を{r('忘', 'わす')}れた。",
                'kinō, gakkō ni iku [ ? ] o wasureta.',
                '昨天忘了要去上学（这件事）。',
                [blank_spec('b1', '名词化助词', ['の'])],
                _expl(f"{r('昨日', 'きのう')}、{r('学校', 'がっこう')}に{r('行', 'い')}く<strong>の</strong>を{r('忘', 'わす')}れた。", 'kinō, gakkō ni iku no o wasureta.', '动词短语后接「の」即可直接名词化，从而接上宾格「を」充当「忘れる」的对象。'),
            ),
            fc(
                'fc-jp06-2222-17', '句尾说明语气：名词后接「のだ」须加「な」', ['p-jp06-no-explain'],
                '用「のだ」对“其实他是我朋友呀”作解释说明时，名词后必须插入防歧义连接假名：',
                '彼は私の友達{{blank:b1}}のだ。',
                f"{r('彼', 'かれ')}は{r('私', 'わたし')}の{r('友達', 'ともだち')}{B1}のだ。",
                'kare wa watashi no tomodachi [ ? ] no da.',
                '其实他是我朋友呀。',
                [blank_spec('b1', '防歧义连接假名', ['な'])],
                _expl(f"{r('彼', 'かれ')}は{r('私', 'わたし')}の{r('友達', 'ともだち')}<strong>な</strong>のだ。", 'kare wa watashi no tomodachi na no da.', '若直接说「友達のだ」会被听成“是朋友的（东西）”，名词后接说明语气「の / んだ」必须先加「な」防歧义。'),
            ),
            fc(
                'fc-jp06-2222-18', '日常口语追问/解释：「どこに行くの？」', ['p-jp06-no-explain'],
                '疑问句中柔和打听缘由/近况（与答句「〜んだ」配对），填入句尾说明语气助词：',
                'これからどこに行く{{blank:b1}}？ 友達に会いに行くんだ。',
                f"これからどこに{r('行', 'い')}く{B1}？ {r('友達', 'ともだち')}に{r('会', 'あ')}いに{r('行', 'い')}くんだ。",
                'kore kara doko ni iku [ ? ]? tomodachi ni ai ni ikun da.',
                '你这是要去哪儿呀？ 我要去见朋友（呢）。',
                [blank_spec('b1', '说明语气助词', ['の'])],
                _expl(f"これからどこに{r('行', 'い')}く<strong>の</strong>？ {r('友達', 'ともだち')}に{r('会', 'あ')}いに{r('行', 'い')}くんだ。", 'kore kara doko ni iku no? tomodachi ni ai ni ikun da.', '疑问句中常用「の？」柔和地打听缘由/近况，回答则配对说明语气「〜んだ」给出解释。'),
            ),
            fc(
                'fc-jp06-2222-19', '综合复盘：「〜んじゃない／んじゃなかった」懊悔解释语气', ['p-jp06-no-explain', 'p-jp06-state-mod'],
                '将说明语气「んだ」的句尾「だ」作【过去否定简体】活用，表达“早知道不吃早饭好了”：',
                'お腹が痛くて、朝ご飯を食べるん{{blank:b1}}。',
                f"お{r('腹', 'なか')}が{r('痛', 'いた')}くて、{r('朝', 'あさ')}ご{r('飯', 'はん')}を{r('食', 'た')}べるん{B1}。",
                'onaka ga itakute, asagohan o taberun [ ? ].',
                '肚子痛，真不该吃早饭的啊。',
                [blank_spec('b1', '过去否定简体', ['じゃなかった', 'ではなかった'])],
                _expl(f"お{r('腹', 'なか')}が{r('痛', 'いた')}くて、{r('朝', 'あさ')}ご{r('飯', 'はん')}を{r('食', 'た')}べるん<strong>じゃなかった</strong>。", 'onaka ga itakute, asagohan o taberun janakatta.', '先把动词句名词化接「ん(だ)」，再对句尾「だ」做过去否定活用「じゃなかった」，表达“本来不该……”的懊悔解释语气。'),
            ),
        ],
    },
]
