"""六个既有训练场景的 2D 世界配置（空间 / 角色 / 热点 / 任务绑定）。

设计边界（重要）：
- 本模块**不保存也不改写任何训练语料**。每一步的 `prompt / hints / praise` 仍然来自
  `app.services.training_scripts`，由 TrainingService 在每一次回答后返回；
- 本模块只描述「这一步发生在哪个房间、谁在说话、孩子该走向哪个热点、屏幕上写什么任务」，
  是纯粹的空间与演出层，因此可以放心地复用同一批房间资产；
- 六个场景 key 与 `SCENARIOS` 严格一一对应，不能新增、删除或替换。

坐标系统：16 × 11 的等距网格，(x, y) 为物体占地在世界坐标中的**中心**，w/h 为占地尺寸；
前端使用 iso 投影把 (x, y) 映射到屏幕。`stand` 是「孩子应该走到哪里」的锚点，桌面上的
小物件必须显式给出 stand，否则会站到桌子里面。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.training_scripts import SCENARIOS

GRID_W = 16.0
GRID_H = 11.0

# ---------------------------------------------------------------- 数据结构


@dataclass(frozen=True)
class PropDef:
    """一件可观察的家具/道具。"""

    id: str
    name: str
    art: str
    x: float
    y: float
    w: float = 1.0
    h: float = 1.0
    lift: int = 0
    """屏幕像素：把造型整体上移，用于摆到桌面/架子顶层。"""
    z: float = 0.0
    """深度排序微调：桌面上的小物件要给正数，才会画在桌子前面。"""
    solid: bool = True
    interact: bool = True
    note: str = ""
    stand: tuple[float, float] | None = None


@dataclass(frozen=True)
class NpcDef:
    id: str
    name: str
    role: str
    x: float
    y: float
    facing: str = "down"
    scale: float = 1.0
    line: str = ""
    stand: tuple[float, float] | None = None


@dataclass(frozen=True)
class SceneDef:
    id: str
    name: str
    env: str  # indoor / outdoor
    art: str  # home / classroom / playground / store
    accent: str
    props: tuple[PropDef, ...]
    npcs: tuple[NpcDef, ...]
    spawn: tuple[float, float]


@dataclass(frozen=True)
class StepDef:
    index: int
    scene: str
    speaker: str
    focus: str
    task: str
    voice: str = "npc"  # npc = 角色开口；coach = 教练旁白，角色只补一句
    gestures: tuple[str, ...] = ()
    line: str = ""


@dataclass(frozen=True)
class WorldDef:
    scenario: str
    scenes: dict[str, SceneDef]
    steps: tuple[StepDef, ...]

    @property
    def start_scene(self) -> str:
        return self.steps[0].scene


# ---------------------------------------------------------------- 角色


_CAST: dict[str, tuple[str, str, str]] = {
    "mom": ("妈妈", "parent", "我在呢。"),
    "teacher": ("老师", "teacher", "老师在这儿。"),
    "auntie": ("阿姨", "auntie", "阿姨在这儿呀。"),
    "peer_a": ("小伙伴", "peer", "一起玩吗？"),
    "peer_b": ("小伙伴", "peer", "我们在搭城堡。"),
    "shopkeeper": ("店员", "shopkeeper", "欢迎光临～"),
}


def _npc(
    key: str,
    x: float,
    y: float,
    facing: str = "down",
    name: str = "",
    stand: tuple[float, float] | None = None,
) -> NpcDef:
    default_name, role, line = _CAST[key]
    return NpcDef(
        id=key,
        name=name or default_name,
        role=role,
        x=x,
        y=y,
        facing=facing,
        line=line,
        stand=stand,
    )


# ---------------------------------------------------------------- 房间资产
# 四个房间被六个场景复用；每个场景只替换 NPC 与出生点。

_HOME_PROPS: tuple[PropDef, ...] = (
    PropDef("rug", "地毯", "rug", 5.4, 4.0, 4.6, 2.8, solid=False, note="地毯是粉色的，踩上去软软的。", stand=(5.4, 6.0)),
    PropDef("bookshelf", "书架", "bookshelf", 2.2, 1.6, 2.4, 1.2, note="书架上有绘本，还有一盒拼图。", stand=(2.4, 3.4)),
    PropDef("sofa", "沙发", "sofa", 7.6, 1.5, 4.4, 1.8, note="沙发软软的，妈妈最喜欢坐这里。", stand=(7.6, 3.3)),
    PropDef("lamp", "落地灯", "lamp", 11.8, 1.5, 0.9, 0.9, note="落地灯的灯光是暖黄色的。", stand=(11.8, 2.8)),
    PropDef("plant", "绿萝", "plant", 14.2, 2.2, 1.2, 1.2, note="绿萝的叶子凉凉的。", stand=(14.2, 3.6)),
    PropDef("coffee_table", "茶几", "coffee_table", 7.4, 4.6, 3.0, 1.8, note="茶几上放着刚拼好的拼图。", stand=(7.4, 6.3)),
    PropDef("dining_table", "餐桌", "dining_table", 12.6, 6.4, 3.2, 2.0, note="餐桌上有一盘青椒。", stand=(11.4, 8.0)),
    PropDef("toy_box", "积木箱", "toy_box", 2.8, 7.8, 2.2, 1.2, note="积木箱里有好多积木，哗啦哗啦响。", stand=(2.8, 9.2)),
    PropDef("puzzle", "拼图", "puzzle", 7.4, 4.6, 0.7, 0.5, lift=66, z=2.0, solid=False, note="拼图少了一块，找找看？", stand=(7.4, 6.3)),
    PropDef("biscuit", "饼干", "biscuit", 8.6, 4.5, 0.5, 0.4, lift=60, z=2.1, solid=False, note="饼干是圆的，闻起来香香的。", stand=(8.9, 6.2)),
    PropDef("crayons", "蜡笔", "crayons", 5.2, 6.6, 0.7, 0.5, solid=False, note="蜡笔撒了一地。", stand=(5.2, 7.3)),
    PropDef("plate", "餐盘", "plate", 12.4, 6.3, 0.9, 0.6, lift=68, z=2.0, solid=False, note="盘子里有青椒。", stand=(12.0, 7.9)),
    PropDef("blocks", "积木", "blocks", 3.8, 6.9, 1.2, 0.8, solid=False, note="积木搭成了一座小城堡。", stand=(3.8, 7.8)),
)

_CLASSROOM_PROPS: tuple[PropDef, ...] = (
    PropDef("rug", "阅读角地毯", "rug", 2.8, 8.7, 3.2, 2.0, solid=False, note="阅读角的地毯软软的。", stand=(2.8, 9.6)),
    PropDef("bookshelf", "书架", "bookshelf", 2.0, 1.7, 2.2, 1.2, note="书架上摆着绘本和拼图盒。", stand=(2.0, 3.2)),
    PropDef("puzzle_box", "拼图盒", "puzzle_box", 2.0, 1.7, 0.8, 0.6, lift=152, z=2.0, solid=False, note="拼图盒在最上面一层，要抬高手才够得到。", stand=(2.0, 3.2)),
    PropDef("teacher_desk", "讲台", "teacher_desk", 12.0, 2.4, 3.2, 1.6, note="老师的桌上有小朋友的画。", stand=(11.4, 3.7)),
    PropDef("water_bottle", "水杯", "water_bottle", 11.6, 2.5, 0.5, 0.4, lift=72, z=2.0, solid=False, note="水杯盖拧得紧紧的。", stand=(11.8, 3.8)),
    PropDef("desk_a", "小课桌", "desk", 4.6, 4.6, 2.8, 1.5, note="小桌上摆着蜡笔和练习本。", stand=(4.6, 6.1)),
    PropDef("desk_b", "小课桌", "desk", 9.0, 5.5, 2.8, 1.5, note="桌角贴着一张星星贴纸。", stand=(9.0, 7.0)),
    PropDef("blocks", "积木", "blocks", 5.0, 7.6, 1.2, 0.8, solid=False, note="积木堆在垫子上。", stand=(5.0, 8.5)),
    PropDef("plant", "绿植", "plant", 14.2, 8.4, 1.2, 1.2, note="窗台边的绿植在晒太阳。", stand=(14.2, 9.8)),
)

_PLAYGROUND_PROPS: tuple[PropDef, ...] = (
    PropDef("swing", "秋千", "swing", 3.4, 3.0, 2.8, 2.0, note="秋千荡起来，风从耳边过去。", stand=(3.4, 4.7)),
    PropDef("slide", "滑梯", "slide", 12.4, 3.6, 3.0, 2.4, note="滑梯是薄荷绿色的，滑下来会呼呼响。", stand=(12.4, 5.7)),
    PropDef("sandbox", "沙池", "sandbox", 6.4, 7.2, 3.4, 2.0, note="沙池里有小铲子和水桶。", stand=(6.4, 8.9)),
    PropDef("bench", "长椅", "bench", 13.4, 7.8, 2.6, 1.0, note="长椅上有妈妈的水杯。", stand=(13.4, 8.9)),
    PropDef("tree", "大树", "tree", 1.2, 6.4, 1.4, 1.4, note="大树底下有阴凉。", stand=(1.2, 7.8)),
    PropDef("ball", "皮球", "ball", 4.4, 6.4, 0.8, 0.8, solid=False, note="皮球滚到脚边了。", stand=(4.4, 7.2)),
)

_STORE_PROPS: tuple[PropDef, ...] = (
    PropDef("shelf_left", "货架", "shelf", 2.6, 3.2, 2.6, 1.4, note="货架上摆着饼干和果汁。", stand=(2.6, 4.6)),
    PropDef("shelf_right", "货架", "shelf", 13.2, 3.2, 2.6, 1.4, note="这边是糖果和纸巾。", stand=(13.2, 4.6)),
    PropDef("fridge", "冷藏柜", "fridge", 6.0, 2.0, 2.6, 1.2, note="冷藏柜里有一盒盒牛奶，凉凉的。", stand=(6.0, 3.4)),
    PropDef("milk", "牛奶", "milk", 6.0, 2.0, 0.6, 0.5, lift=108, z=2.0, solid=False, note="牛奶盒上画着一头小奶牛。", stand=(6.0, 3.4)),
    PropDef("counter", "收银台", "counter", 9.6, 5.6, 3.8, 1.6, note="收银台上贴着付款码。", stand=(9.6, 8.3)),
    PropDef("basket", "购物篮", "basket", 6.4, 7.6, 1.2, 0.9, solid=False, note="购物篮里空空的。", stand=(6.4, 8.5)),
    PropDef("plant", "门口的绿植", "plant", 1.4, 8.6, 1.2, 1.2, note="门口的绿植摇摇晃晃。", stand=(1.4, 10.0)),
)

_SCENE_META: dict[str, tuple[str, str, str, str]] = {
    # id: (名字, 室内/室外, 美术主题, 主题色)
    "home_living": ("家里的客厅", "indoor", "home", "#F6A8BB"),
    "classroom": ("明亮的教室", "indoor", "classroom", "#8FD3C3"),
    "playground": ("幼儿园操场", "outdoor", "playground", "#9CCDF0"),
    "store": ("街角便利店", "indoor", "store", "#F7CE79"),
}

_SCENE_PROPS: dict[str, tuple[PropDef, ...]] = {
    "home_living": _HOME_PROPS,
    "classroom": _CLASSROOM_PROPS,
    "playground": _PLAYGROUND_PROPS,
    "store": _STORE_PROPS,
}


def _scene(
    scene_id: str,
    npcs: tuple[NpcDef, ...],
    spawn: tuple[float, float],
) -> SceneDef:
    name, env, art, accent = _SCENE_META[scene_id]
    return SceneDef(
        id=scene_id,
        name=name,
        env=env,
        art=art,
        accent=accent,
        props=_SCENE_PROPS[scene_id],
        npcs=npcs,
        spawn=spawn,
    )


# ---------------------------------------------------------------- 六个世界

_WORLDS: dict[str, WorldDef] = {
    # 1. 日常道谢 —— 家庭客厅
    "thanks": WorldDef(
        scenario="thanks",
        scenes={
            "home_living": _scene(
                "home_living",
                npcs=(
                    _npc("mom", 10.0, 3.1, "right"),
                    _npc("auntie", 5.4, 6.6, "right"),
                    _npc("peer_a", 9.6, 5.6, "left", name="小雨"),
                ),
                spawn=(7.6, 9.2),
            ),
        },
        steps=(
            StepDef(0, "home_living", "mom", "mom", "走到妈妈身边，回应她", "npc",
                    ("点点头", "对妈妈微笑", "指指拼图"), "拼图给你，慢慢玩～"),
            StepDef(1, "home_living", "auntie", "crayons", "谢谢阿姨帮你捡蜡笔", "npc",
                    ("点点头", "指指阿姨"), "蜡笔都捡起来啦。"),
            StepDef(2, "home_living", "peer_a", "biscuit", "谢谢小伙伴，并说出还想要", "npc",
                    ("点点头", "指指饼干"), "这块饼干分给你！"),
        ),
    ),
    # 2. 礼貌求助 —— 教室
    "help": WorldDef(
        scenario="help",
        scenes={
            "classroom": _scene(
                "classroom",
                npcs=(
                    _npc("teacher", 11.0, 4.0, "down"),
                    _npc("peer_a", 6.2, 7.0, "up", name="小宇"),
                ),
                spawn=(9.0, 8.8),
            ),
        },
        steps=(
            StepDef(0, "classroom", "teacher", "teacher", "请老师帮你拿拼图", "coach",
                    ("指指架子",), "拼图在最上面一层哦。"),
            StepDef(1, "classroom", "teacher", "teacher", "问一问洗手间在哪里", "coach",
                    ("指指门",), "需要帮忙吗？"),
            StepDef(2, "classroom", "teacher", "water_bottle", "请老师帮你打开水杯", "coach",
                    ("递水杯给老师",), "水杯给我看看？"),
        ),
    ),
    # 3. 表达不适 —— 客厅 → 教室 → 客厅
    "discomfort": WorldDef(
        scenario="discomfort",
        scenes={
            "home_living": _scene(
                "home_living",
                npcs=(_npc("mom", 10.0, 3.1, "left"),),
                spawn=(7.6, 9.2),
            ),
            "classroom": _scene(
                "classroom",
                npcs=(
                    _npc("teacher", 10.4, 4.4, "down"),
                    _npc("peer_a", 5.4, 7.2, "up", name="小宇"),
                ),
                spawn=(9.0, 8.8),
            ),
        },
        steps=(
            StepDef(0, "home_living", "mom", "mom", "告诉妈妈你肚子疼", "coach",
                    ("指指肚子",), "怎么啦，脸皱皱的？"),
            StepDef(1, "classroom", "teacher", "teacher", "告诉老师声音太吵了", "coach",
                    ("指指耳朵",), "今天教室有点热闹。"),
            StepDef(2, "home_living", "mom", "mom", "告诉妈妈你累了", "coach",
                    ("指指沙发",), "玩累了吧？"),
        ),
    ),
    # 4. 礼貌拒绝 —— 客厅
    "refuse": WorldDef(
        scenario="refuse",
        scenes={
            "home_living": _scene(
                "home_living",
                npcs=(
                    _npc("mom", 10.4, 8.4, "right"),
                    _npc("auntie", 3.6, 5.4, "right"),
                    _npc("peer_a", 2.8, 8.6, "down", name="小雨"),
                ),
                spawn=(8.6, 9.4),
            ),
        },
        steps=(
            StepDef(0, "home_living", "mom", "plate", "告诉妈妈你不想吃青椒", "npc",
                    ("摇摇头",), "青椒有营养，吃一口吧。"),
            StepDef(1, "home_living", "auntie", "auntie", "告诉阿姨你现在不想被抱", "coach",
                    ("摇摇头",), "来，抱一个！"),
            StepDef(2, "home_living", "peer_a", "blocks", "告诉小伙伴你想先停下", "coach",
                    ("摇摇头", "指指积木"), "再搭一层！"),
        ),
    ),
    # 5. 同伴邀约 —— 教室 → 操场
    "invite": WorldDef(
        scenario="invite",
        scenes={
            "classroom": _scene(
                "classroom",
                npcs=(
                    _npc("peer_a", 4.3, 6.6, "right", name="小宇"),
                    _npc("peer_b", 6.0, 6.7, "left", name="小雨"),
                    _npc("teacher", 12.8, 7.4, "down"),
                ),
                spawn=(9.0, 9.0),
            ),
            "playground": _scene(
                "playground",
                npcs=(
                    _npc("peer_a", 10.0, 6.2, "right", name="小宇"),
                    _npc("peer_b", 12.4, 6.0, "left", name="小雨"),
                    _npc("mom", 12.6, 8.6, "down"),
                ),
                spawn=(8.4, 9.6),
            ),
        },
        steps=(
            StepDef(0, "classroom", "peer_a", "blocks", "问问小伙伴能不能一起玩", "npc",
                    ("指指积木", "点点头"), "我们在搭城堡～"),
            StepDef(1, "playground", "peer_a", "slide", "邀请小伙伴去玩滑梯", "npc",
                    ("指指滑梯",), "滑梯那边好好玩！"),
            StepDef(2, "playground", "peer_b", "peer_b", "小伙伴拒绝了，试试回应他", "npc",
                    ("点点头",), "我现在不想玩啦。"),
        ),
    ),
    # 6. 简单购物 —— 便利店
    "shopping": WorldDef(
        scenario="shopping",
        scenes={
            "store": _scene(
                "store",
                npcs=(
                    # 店员在收银台后面：孩子站在柜台前方稍远处，才不会被挡住视线
                    _npc("shopkeeper", 9.6, 4.2, "down", stand=(9.6, 8.35)),
                    _npc("mom", 4.0, 7.4, "right"),
                ),
                spawn=(8.2, 9.4),
            ),
        },
        steps=(
            StepDef(0, "store", "shopkeeper", "shopkeeper", "进店先和店员打招呼", "npc",
                    ("对店员微笑", "点点头"), "欢迎光临～"),
            StepDef(1, "store", "shopkeeper", "shopkeeper", "告诉店员你要买牛奶", "coach",
                    ("指指牛奶",), "想买点什么？"),
            StepDef(2, "store", "shopkeeper", "counter", "问价格并付款", "coach",
                    ("递钱给店员",), "一共五块钱。"),
            StepDef(3, "store", "shopkeeper", "shopkeeper", "谢谢店员，说再见", "npc",
                    ("对店员微笑", "点点头"), "慢走，下次再来～"),
        ),
    ),
}


# ---------------------------------------------------------------- 对外接口


def _prop_payload(prop: PropDef) -> dict[str, Any]:
    return {
        "id": prop.id,
        "name": prop.name,
        "art": prop.art,
        "x": prop.x,
        "y": prop.y,
        "w": prop.w,
        "h": prop.h,
        "lift": prop.lift,
        "z": prop.z,
        "solid": prop.solid,
        "interact": prop.interact,
        "note": prop.note,
        "stand": {"x": prop.stand[0], "y": prop.stand[1]} if prop.stand else None,
    }


def _npc_payload(npc: NpcDef) -> dict[str, Any]:
    # 孩子站在角色的「侧前方」：屏幕上约向右 64px、向下 38px。
    # 纵向站得太近会整个人挡住对方，横向错开才能看清两个人的脸。
    stand = npc.stand or (npc.x + 2.4, npc.y + 0.2)
    return {
        "id": npc.id,
        "name": npc.name,
        "role": npc.role,
        "x": npc.x,
        "y": npc.y,
        "facing": npc.facing,
        "scale": npc.scale,
        "line": npc.line,
        # 孩子要站在角色「斜前方一臂远」的位置：太近会整个人叠在角色身上
        "stand": {"x": stand[0], "y": stand[1]},
    }


def _scene_payload(scene: SceneDef) -> dict[str, Any]:
    return {
        "id": scene.id,
        "name": scene.name,
        "env": scene.env,
        "art": scene.art,
        "accent": scene.accent,
        "props": [_prop_payload(prop) for prop in scene.props],
        "npcs": [_npc_payload(npc) for npc in scene.npcs],
        "spawn": {"x": scene.spawn[0], "y": scene.spawn[1]},
        "bounds": {"minX": 0.7, "maxX": GRID_W - 0.7, "minY": 0.7, "maxY": GRID_H - 0.7},
    }


def _step_payload(step: StepDef) -> dict[str, Any]:
    return {
        "index": step.index,
        "scene": step.scene,
        "speaker": step.speaker,
        "focus": step.focus,
        "task": step.task,
        "voice": step.voice,
        "gestures": list(step.gestures),
        "line": step.line,
    }


def world_payload(scenario: str) -> dict[str, Any]:
    """返回前端渲染一个完整关卡所需的全部空间与任务数据。"""
    world = _WORLDS[scenario]
    scenario_def = SCENARIOS[scenario]
    cast: list[dict[str, str]] = []
    seen: set[str] = set()
    for scene in world.scenes.values():
        for npc in scene.npcs:
            if npc.id in seen:
                continue
            seen.add(npc.id)
            cast.append({"id": npc.id, "name": npc.name, "role": npc.role})
    return {
        "scenario": scenario,
        "name": scenario_def.name,
        "goal": scenario_def.goal,
        "intro": scenario_def.intro,
        "start_scene": world.start_scene,
        "grid": {"w": GRID_W, "h": GRID_H},
        "scenes": {scene_id: _scene_payload(scene) for scene_id, scene in world.scenes.items()},
        "steps": [_step_payload(step) for step in world.steps],
        "cast": [{"id": "child", "name": "我", "role": "child"}, *cast],
    }


def world_catalog() -> list[dict[str, Any]]:
    """场景选择页使用的轻量列表：六个关卡，一个不多一个不少。"""
    items: list[dict[str, Any]] = []
    for key, scenario_def in SCENARIOS.items():
        world = _WORLDS[key]
        start = world.scenes[world.start_scene]
        items.append(
            {
                "scenario": key,
                "name": scenario_def.name,
                "goal": scenario_def.goal,
                "intro": scenario_def.intro,
                "steps": len(world.steps),
                "scene": start.id,
                "scene_name": start.name,
                "env": start.env,
                "art": start.art,
                "accent": start.accent,
                "casts": [npc.name for npc in start.npcs],
                "scenes": list(world.scenes.keys()),
            }
        )
    return items


def get_world(scenario: str) -> WorldDef:
    world = _WORLDS.get(scenario)
    if world is None:
        raise KeyError(f"未知训练场景: {scenario}")
    return world


def get_step(scenario: str, index: int) -> StepDef | None:
    world = get_world(scenario)
    if 0 <= index < len(world.steps):
        return world.steps[index]
    return None


def scene_of(scenario: str, index: int) -> SceneDef:
    world = get_world(scenario)
    step = get_step(scenario, index) or world.steps[-1]
    return world.scenes[step.scene]


def start_state(scenario: str) -> dict[str, Any]:
    scene = scene_of(scenario, 0)
    return {
        "scene": scene.id,
        "player": {"x": scene.spawn[0], "y": scene.spawn[1]},
        "visited": [],
        "actions": [],
    }


def validate_worlds() -> list[str]:
    """自检：配置与训练脚本必须严格对齐，供测试与启动期使用。"""
    problems: list[str] = []
    for key, scenario_def in SCENARIOS.items():
        world = _WORLDS.get(key)
        if world is None:
            problems.append(f"{key}: 缺少世界配置")
            continue
        if set(world.scenes) - set(_SCENE_META):
            problems.append(f"{key}: 引用了未知房间")
        if len(world.steps) != len(scenario_def.steps):
            problems.append(
                f"{key}: 步骤数不一致 world={len(world.steps)} script={len(scenario_def.steps)}"
            )
        for step in world.steps:
            scene = world.scenes.get(step.scene)
            if scene is None:
                problems.append(f"{key}#{step.index}: 房间 {step.scene} 不存在")
                continue
            npc_ids = {npc.id for npc in scene.npcs}
            if step.speaker not in npc_ids:
                problems.append(f"{key}#{step.index}: 说话人 {step.speaker} 不在房间内")
            prop_ids = {prop.id for prop in scene.props}
            if step.focus not in npc_ids and step.focus not in prop_ids:
                problems.append(f"{key}#{step.index}: 焦点 {step.focus} 不存在")
            if not step.task:
                problems.append(f"{key}#{step.index}: 缺少任务文案")
            if len(step.gestures) > 3:
                problems.append(f"{key}#{step.index}: 非语言按钮超过 3 个")
    extra = set(_WORLDS) - set(SCENARIOS)
    if extra:
        problems.append(f"存在训练脚本之外的世界配置: {sorted(extra)}")
    return problems


__all__ = [
    "GRID_W",
    "GRID_H",
    "NpcDef",
    "PropDef",
    "SceneDef",
    "StepDef",
    "WorldDef",
    "get_step",
    "get_world",
    "scene_of",
    "start_state",
    "validate_worlds",
    "world_catalog",
    "world_payload",
]
