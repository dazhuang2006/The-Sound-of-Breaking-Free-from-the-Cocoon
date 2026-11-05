"""六类情景训练脚本。

每个步骤包含：
- prompt   ：教练说给孩子的场景描述（一次只问一个问题）
- expected ：可接受的表达关键词（口语或替代沟通方式都算达成）
- hints    ：三级分层提示，最后一级才是示范
- praise   ：具体化表扬（说出孩子做到了什么）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScenarioStep:
    goal: str
    prompt: str
    expected: tuple[str, ...]
    hints: tuple[str, str, str]
    praise: str
    example: str


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    goal: str
    intro: str
    steps: tuple[ScenarioStep, ...] = field(default_factory=tuple)


SCENARIOS: dict[str, Scenario] = {
    "thanks": Scenario(
        key="thanks",
        name="日常道谢",
        goal="在别人给予帮助或物品时，用自己喜欢的方式表达感谢",
        intro="我们来玩一个「道谢」的小练习。我会扮演身边的人，你用自己的方式回应就好，说话、点头、递图片都可以。",
        steps=(
            ScenarioStep(
                goal="接受物品时说谢谢",
                prompt="我把你最喜欢的拼图递给你了。你可以怎么回应我呢？",
                expected=("谢谢", "谢", "感谢", "多谢", "thank"),
                hints=(
                    "别人把东西递给你时，我们通常会说一句很短的话，表示收到了。",
                    "这句话只有两个字，第一个字是「谢」。",
                    "你可以说：「谢谢。」也可以点点头，或者把「谢谢」的图片递给我。",
                ),
                praise="你说出了「谢谢」，这就是很自然的回应。",
                example="谢谢",
            ),
            ScenarioStep(
                goal="对具体的人道谢",
                prompt="刚才阿姨帮你把掉在地上的蜡笔捡起来了。你会对阿姨说什么？",
                expected=("谢谢阿姨", "谢谢", "谢谢您", "多谢"),
                hints=(
                    "想一想，是谁帮了你？道谢时可以把称呼加上。",
                    "试着说：「谢谢……」后面加上她的称呼。",
                    "你可以说：「谢谢阿姨。」如果不方便说话，看着她笑一下、点点头也可以。",
                ),
                praise="你加上了称呼，对方会更清楚你在感谢她。",
                example="谢谢阿姨",
            ),
            ScenarioStep(
                goal="接受分享时表达喜欢",
                prompt="小朋友把一块饼干分给你，你还想要一点点。你可以怎么说？",
                expected=("谢谢", "喜欢", "还要", "可以再", "好吃"),
                hints=(
                    "先谢谢对方，再告诉他你的想法。",
                    "可以说：「谢谢，我还想……」",
                    "你可以说：「谢谢，我还想要一块，可以吗？」用手势比「一」也可以。",
                ),
                praise="你既表达了感谢，也说清楚了自己的需要。",
                example="谢谢，我还想要一块，可以吗？",
            ),
        ),
    ),
    "help": Scenario(
        key="help",
        name="礼貌求助",
        goal="在遇到困难时，主动向身边的大人求助",
        intro="我们练习「求助」。遇到做不到的事，说出来是完全可以的，我会帮你。",
        steps=(
            ScenarioStep(
                goal="请求拿高处物品",
                prompt="拼图盒子放在架子最上面，你够不到。你可以怎么对我说？",
                expected=("帮我", "帮忙", "拿一下", "够不到", "请帮"),
                hints=(
                    "先告诉我你遇到了什么困难，再说你需要什么。",
                    "可以说：「请帮我……」",
                    "你可以说：「请帮我拿一下拼图，我够不到。」指一指盒子也可以。",
                ),
                praise="你把困难和需要都说清楚了，这样别人更容易帮到你。",
                example="请帮我拿一下拼图，我够不到",
            ),
            ScenarioStep(
                goal="询问地点",
                prompt="你想去洗手间，但不知道在哪里。你会怎么问？",
                expected=("洗手间", "卫生间", "在哪里", "请问"),
                hints=(
                    "先叫住一个人，再问地点。",
                    "可以说：「请问，洗手间……」",
                    "你可以说：「请问洗手间在哪里？」也可以把洗手间的图片给对方看。",
                ),
                praise="你先说了「请问」，听起来很有礼貌。",
                example="请问洗手间在哪里？",
            ),
            ScenarioStep(
                goal="请求具体帮助",
                prompt="水杯盖太紧了，你打不开。旁边有老师在。你可以怎么说？",
                expected=("打不开", "帮我", "帮忙", "老师"),
                hints=(
                    "先叫一下老师，再说清楚哪里打不开。",
                    "可以说：「老师，我打不开……」",
                    "你可以说：「老师，我打不开水杯，可以帮我一下吗？」把水杯递过去也可以。",
                ),
                praise="你叫了老师，也说清楚了自己需要什么帮助。",
                example="老师，我打不开水杯，可以帮我一下吗？",
            ),
        ),
    ),
    "discomfort": Scenario(
        key="discomfort",
        name="表达不适",
        goal="在身体或感官不舒服时，能把感受告诉身边的人",
        intro="我们练习「说出不舒服」。身体不舒服的时候，让别人知道很重要。",
        steps=(
            ScenarioStep(
                goal="表达身体疼痛",
                prompt="你的肚子有点疼。你可以怎么告诉我？",
                expected=("肚子疼", "肚子痛", "疼", "痛", "不舒服"),
                hints=(
                    "先说出是身体的哪个部位不舒服。",
                    "可以说：「我肚子……」",
                    "你可以说：「我肚子疼。」也可以用手捂着肚子，指给大人看。",
                ),
                praise="你说清楚了是哪里不舒服，大人才能帮你。",
                example="我肚子疼",
            ),
            ScenarioStep(
                goal="表达感官过载",
                prompt="教室里的声音太大了，你觉得吵得难受。你会怎么说？",
                expected=("太吵", "吵", "安静", "声音大", "难受"),
                hints=(
                    "先说出是什么让你不舒服，再说你希望怎样。",
                    "可以说：「太吵了，我想……」",
                    "你可以说：「太吵了，我想安静一会儿。」或者用手捂住耳朵、指指耳朵。",
                ),
                praise="你既说出了感受，也说出了希望怎么调整。",
                example="太吵了，我想安静一会儿",
            ),
            ScenarioStep(
                goal="表达疲劳",
                prompt="你玩了一上午，觉得有点累了。你可以怎么跟我说？",
                expected=("累", "休息", "想睡觉", "没力气"),
                hints=(
                    "说出你现在的感觉。",
                    "可以说：「我有点……」",
                    "你可以说：「我有点累，想休息一会儿。」靠在椅子上、指指床也可以。",
                ),
                praise="你及时说出了「累」，休息一下会舒服很多。",
                example="我有点累，想休息一会儿",
            ),
        ),
    ),
    "refuse": Scenario(
        key="refuse",
        name="礼貌拒绝",
        goal="在不想要、不愿意时，用不伤害关系的方式表达拒绝",
        intro="我们练习「说不」。不想吃、不想抱、不想玩，都可以好好地说出来。",
        steps=(
            ScenarioStep(
                goal="拒绝食物",
                prompt="我把青椒放到你的碗里了，你不想吃。你可以怎么跟我说？",
                expected=("不想吃", "不要", "不吃", "不喜欢"),
                hints=(
                    "先说「我不想……」，再说是什么。",
                    "可以说：「我不想吃……」",
                    "你可以说：「我不想吃青椒，谢谢。」把碗轻轻推开也可以。",
                ),
                praise="你说出了「不想吃」，也没有把碗打翻。",
                example="我不想吃青椒，谢谢",
            ),
            ScenarioStep(
                goal="拒绝身体接触",
                prompt="有人想抱你，你现在不想被抱。你可以怎么说？",
                expected=("不想抱", "不要抱", "不要", "击掌", "握手"),
                hints=(
                    "直接说不想被抱是可以的，还可以给对方一个替代方式。",
                    "可以说：「我现在不想抱，我们……」",
                    "你可以说：「我现在不想抱，我们击个掌吧。」伸出手也可以。",
                ),
                praise="你拒绝了不想要的接触，还给了对方一个替代方式。",
                example="我现在不想抱，我们击个掌吧",
            ),
            ScenarioStep(
                goal="结束游戏",
                prompt="你还想再玩一会儿积木，但你现在想去做别的事。你会怎么跟小伙伴说？",
                expected=("不想玩", "下次", "先不", "去做", "结束"),
                hints=(
                    "先告诉对方你要停下了，再说一句让关系舒服的话。",
                    "可以说：「我不想玩了，我们……」",
                    "你可以说：「我不想玩了，我们下次再玩，好吗？」",
                ),
                praise="你清楚地结束了游戏，也照顾到了小伙伴的感受。",
                example="我不想玩了，我们下次再玩，好吗？",
            ),
        ),
    ),
    "invite": Scenario(
        key="invite",
        name="同伴邀约",
        goal="想加入同伴游戏或邀请别人一起玩时，能主动开口",
        intro="我们练习「一起玩」。想加入别人的游戏，可以先问一句。",
        steps=(
            ScenarioStep(
                goal="请求加入游戏",
                prompt="几个小朋友在搭积木，你也想一起搭。你可以怎么问？",
                expected=("一起玩", "加入", "我可以", "和你们"),
                hints=(
                    "先走近一点，等他们看你，再开口问。",
                    "可以说：「我可以和你们……」",
                    "你可以说：「我可以和你们一起搭积木吗？」指指积木也可以。",
                ),
                praise="你主动问了一句，这就是加入游戏的第一步。",
                example="我可以和你们一起搭积木吗？",
            ),
            ScenarioStep(
                goal="发出邀请",
                prompt="你想叫小伙伴一起去玩滑梯。你可以怎么说？",
                expected=("一起", "去玩", "滑梯", "好吗"),
                hints=(
                    "说出你想做什么，再邀请对方。",
                    "可以说：「我们去玩……」",
                    "你可以说：「我们去玩滑梯吧，好吗？」",
                ),
                praise="你发出了清楚的邀请，还问了对方的想法。",
                example="我们去玩滑梯吧，好吗？",
            ),
            ScenarioStep(
                goal="面对拒绝时的自我调节",
                prompt="小伙伴说「我现在不想玩」。你可以怎么回应，让自己也好受一点？",
                expected=("没关系", "好吧", "那我自己", "下次", "先玩"),
                hints=(
                    "被拒绝不等于被讨厌，可以先接受，再找别的事做。",
                    "可以说：「没关系，那我……」",
                    "你可以说：「没关系，那我先玩这个，等下再找你。」",
                ),
                praise="你接受了对方的拒绝，也给自己找到了下一步。",
                example="没关系，那我先玩这个，等下再找你",
            ),
        ),
    ),
    "shopping": Scenario(
        key="shopping",
        name="简单购物沟通",
        goal="在便利店完成一次简单的购物沟通",
        intro="我们练习「买东西」。等会儿我是店员，你来买牛奶，我们一步一步来。",
        steps=(
            ScenarioStep(
                goal="进店打招呼",
                prompt="你走进便利店，店员看着你。你可以先说什么？",
                expected=("你好", "阿姨好", "叔叔好", "您好"),
                hints=(
                    "进店后先打个招呼，会让后面的话更容易开口。",
                    "可以说：「你好……」",
                    "你可以说：「阿姨好。」点点头、挥挥手也可以。",
                ),
                praise="你主动打了招呼，这是很好的开始。",
                example="阿姨好",
            ),
            ScenarioStep(
                goal="说出想买的东西",
                prompt="你想买一盒牛奶。你可以怎么跟店员说？",
                expected=("我要买", "我要", "买", "牛奶"),
                hints=(
                    "直接说出你要买的东西。",
                    "可以说：「我要买……」",
                    "你可以说：「我要买一盒牛奶。」指着货架上的牛奶也可以。",
                ),
                praise="你说清楚了要买什么，店员一下就明白了。",
                example="我要买一盒牛奶",
            ),
            ScenarioStep(
                goal="询问价格并付款",
                prompt="店员把牛奶递给你，说「五块钱」。你可以怎么问或怎么说？",
                expected=("多少钱", "五块", "给你", "扫码", "付款"),
                hints=(
                    "可以先确认价格，再把钱或手机递过去。",
                    "可以说：「多少钱？」或者「给你……」",
                    "你可以说：「多少钱？……给你五块。」把手机付款码给店员看也可以。",
                ),
                praise="你确认了价格，也完成了付款。",
                example="多少钱？给你五块",
            ),
            ScenarioStep(
                goal="道谢离开",
                prompt="你拿到牛奶，准备离开了。你可以对店员说什么？",
                expected=("谢谢", "再见", "拜拜"),
                hints=(
                    "离开前说一句结束的话。",
                    "可以说：「谢谢，……」",
                    "你可以说：「谢谢，再见。」挥挥手也可以。",
                ),
                praise="你用「谢谢，再见」结束了这次购物，很完整。",
                example="谢谢，再见",
            ),
        ),
    ),
}

SCENARIO_ALIASES: dict[str, str] = {
    "道谢": "thanks",
    "感谢": "thanks",
    "谢谢": "thanks",
    "求助": "help",
    "帮忙": "help",
    "表达不适": "discomfort",
    "不舒服": "discomfort",
    "拒绝": "refuse",
    "邀约": "invite",
    "邀请": "invite",
    "购物": "shopping",
    "买东西": "shopping",
}

# 非口语表达：孩子用这些方式回应同样视为完成
AAC_CUES: tuple[str, ...] = ("点头", "摇头", "手势", "图片", "指", "递", "文字", "打字", "微笑", "眼神", "沟通板", "点头")


def resolve_scenario(text: str) -> str | None:
    for alias, key in SCENARIO_ALIASES.items():
        if alias in text:
            return key
    for key in SCENARIOS:
        if key in text:
            return key
    return None


def get_scenario(key: str) -> Scenario:
    scenario = SCENARIOS.get(key)
    if scenario is None:
        raise KeyError(f"未知训练场景: {key}")
    return scenario
