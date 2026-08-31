"""make_case_assets.py — 生成 Case 材料的 docx 与线框示意图。

只用标准库：PNG 手写 IHDR/IDAT/IEND；docx 是 zip + OOXML，只产出
`import_sources.py` 解析端认得的元素（outlineLvl 标题、普通段、w:tbl 表格、
a:blip 内嵌图、w:b 粗体）。材料正文以数据结构形式内联在各 build_* 函数里，
docx 入库后本脚本保留用于再生。

用法：python make_case_assets.py car-key-sharing
"""
from __future__ import annotations

import struct
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent / "cases"

# ---------------------------------------------------------------------------
# PNG：RGB 线框示意图（与既有 Case 示意图同水准的色块布局稿）


def _png(width: int, height: int, painter) -> bytes:
    rows = [[(246, 247, 249)] * width for _ in range(height)]

    def rect(x0, y0, x1, y1, color, fill=True, border=None):
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, width - 1), min(y1, height - 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                edge = x in (x0, x1) or y in (y0, y1)
                if fill and not edge:
                    rows[y][x] = color
                if edge:
                    rows[y][x] = border or color

    painter(rect)
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in rows)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


GREY = (229, 231, 235)
BLUE = (219, 234, 254)
GREEN = (220, 244, 228)
ORANGE = (254, 237, 213)
DARK = (31, 41, 55)
LINE = (203, 208, 216)


def png_share_setup() -> bytes:
    """分享设置页：联系人 / 权限 / 有效期三段 + 底部发出按钮。"""
    def paint(rect):
        rect(0, 0, 959, 46, DARK)                       # 顶栏
        rect(40, 70, 919, 150, BLUE, border=LINE)       # 联系人段
        rect(40, 170, 470, 260, GREY, border=LINE)      # 权限：全功能
        rect(489, 170, 919, 260, GREY, border=LINE)     # 权限：仅解闭锁
        rect(40, 280, 320, 344, GREY, border=LINE)      # 有效期三档
        rect(340, 280, 620, 344, GREY, border=LINE)
        rect(640, 280, 919, 344, GREY, border=LINE)
        rect(40, 366, 919, 398, ORANGE, border=LINE)    # 协议/提示条
        rect(300, 420, 660, 470, GREEN, border=LINE)    # 发出按钮
    return _png(960, 500, paint)


def png_share_manage() -> bytes:
    """分享管理页：状态卡 + 分享记录列表。"""
    def paint(rect):
        rect(0, 0, 959, 46, DARK)
        rect(40, 66, 919, 140, BLUE, border=LINE)       # 车辆与配额状态卡
        y = 160
        for color in (GREEN, GREEN, ORANGE, GREY, GREY):
            rect(40, y, 919, y + 56, color, border=LINE)  # 每条分享一行
            y += 66
    return _png(960, 500, paint)


def png_key_card_detail() -> bytes:
    """添加后的钥匙卡片详情：权限范围与有效期区。"""
    def paint(rect):
        rect(0, 0, 959, 46, DARK)
        rect(200, 70, 760, 190, GREEN, border=LINE)     # 钥匙卡片
        rect(200, 210, 760, 266, GREY, border=LINE)     # 权限范围行
        rect(200, 286, 760, 342, GREY, border=LINE)     # 有效期行
        rect(200, 362, 760, 418, ORANGE, border=LINE)   # 到期提醒说明
    return _png(960, 460, paint)


def png_accept_page() -> bytes:
    """被分享人接受页：车辆信息卡 + 权限/有效期说明 + 添加按钮。"""
    def paint(rect):
        rect(0, 0, 959, 46, DARK)
        rect(200, 70, 760, 210, BLUE, border=LINE)      # 车辆信息卡
        rect(200, 230, 760, 286, GREY, border=LINE)     # 权限范围
        rect(200, 306, 760, 362, GREY, border=LINE)     # 有效期与来自谁
        rect(320, 396, 640, 452, GREEN, border=LINE)    # 添加到钱包
    return _png(960, 500, paint)


# ---------------------------------------------------------------------------
# docx：最小 OOXML（标题=outlineLvl；段落；表格；内嵌图；**粗体**）

_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_EXTRA_NS = ('xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
             'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
             'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _runs(text: str) -> str:
    """`**粗体**` 切成带 w:b 的 run。"""
    out, bold = [], False
    for part in text.split("**"):
        if part:
            rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
            out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(part)}</w:t></w:r>')
        bold = not bold
    return "".join(out)


def _para(text: str, level: int = 0) -> str:
    ppr = f'<w:pPr><w:outlineLvl w:val="{level - 1}"/></w:pPr>' if level else ""
    return f"<w:p>{ppr}{_runs(text)}</w:p>"


def _table(rows: list[list[str]]) -> str:
    body = []
    for row in rows:
        cells = "".join(f"<w:tc><w:p>{_runs(cell)}</w:p></w:tc>" for cell in row)
        body.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(body)}</w:tbl>"


def _image(rid: str, name: str, cx: int = 5486400, cy: int = 2857500) -> str:
    return (
        f'<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="1" name="{name}"/>'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def write_docx(path: Path, blocks: list, images: dict[str, bytes]) -> None:
    """blocks: ('h', level, text) | ('p', text) | ('t', rows) | ('img', filename)"""
    rels, body = [], []
    rid_of = {}
    for index, name in enumerate(images, start=10):
        rid_of[name] = f"rId{index}"
        rels.append(f'<Relationship Id="rId{index}" '
                    f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                    f'Target="media/{name}"/>')
    for block in blocks:
        kind = block[0]
        if kind == "h":
            body.append(_para(block[2], level=block[1]))
        elif kind == "p":
            body.append(_para(block[1]))
        elif kind == "t":
            body.append(_table(block[1]))
        elif kind == "img":
            body.append(_image(rid_of[block[1]], block[1]))
        else:
            raise ValueError(f"未知块类型: {kind}")
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document {_W} {_EXTRA_NS}><w:body>{"".join(body)}</w:body></w:document>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(rels) + "</Relationships>")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CT)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        for name, blob in images.items():
            zf.writestr(f"word/media/{name}", blob)


# ---------------------------------------------------------------------------
# car-key-sharing 的两份 docx


def build_car_key_prd(out_dir: Path) -> Path:
    blocks = [
        ("h", 1, "数字车钥匙分享"),
        ("h", 2, "数字车钥匙分享 产品需求说明"),
        ("p", "撰写：出行产品组　　版本：v0.4"),
        ("h", 3, "一、背景与目标"),
        ("p", "一辆车全家用是常态，实体钥匙只有一两把：家人临时用车，车主要么跑一趟送钥匙，"
              "要么把钥匙提前藏在某个地方——这是数字车钥匙用户反馈最集中的一条。车钥匙本人使用的能力已经上线，"
              "本需求做的是分享：车主把钥匙分享给家人，对方的钱包里直接多出一把能用的钥匙，用完了车主随时收回。"),
        ("p", "**目标：分享能力上线三个月内，车钥匙用户中发起过分享的比例不低于 15%；"
              "「借车送钥匙」类客服咨询量下降一半。**"),
        ("h", 3, "二、用户旅程"),
        ("p", "1. 车主在钱包的车钥匙卡片上点「分享」，进入分享设置页；"),
        ("p", "2. 选择要分享给谁（从通讯录选，或直接输入对方账号）；"),
        ("p", "3. 选定对象之后，权限区才知道该给哪几档：家庭成员可以选全功能"
              "（解闭锁、启动、后备箱）或仅解闭锁；其他联系人只能选仅解闭锁——"
              "临时借车的人拿到启动权限，车主往往不是本意；"),
        ("p", "4. 选有效期：7 天、30 天，或自定义（最长 180 天）；"),
        ("p", "5. 确认发出。对方的钱包收到一把待接受的钥匙；"),
        ("p", "6. 对方在 72 小时内接受后钥匙生效；逾期没接受就自动作废，车主可以重新发；"),
        ("p", "7. 车主随时能在分享管理里看到每一条分享的状态，也随时可以撤销。"),
        ("h", 3, "三、界面设计"),
        ("p", "分享设置页分三段：给谁、什么权限、多长时间。**先选给谁，权限区才定得下来**——"
              "换一个对象，权限区要跟着重新确定；此前选的那档新对象用不了的话，要请他重选。"
              "三项都选好「发出」才可点击（图 1）："),
        ("img", "share-setup.png"),
        ("p", "图 1　分享设置页"),
        ("p", "分享管理页顶部是车辆与剩余可分享数，下方按条列出每条分享的对象、权限、有效期和状态，"
              "每条可以单独撤销（图 2）："),
        ("img", "share-manage.png"),
        ("p", "图 2　分享管理页"),
        ("p", "被分享人接受那一侧的界面（收到推送后看到什么、怎么添加进钱包）另行提供一份说明，不在本稿里。"),
        ("h", 3, "四、产品规则"),
        ("t", [["规则项", "取值", "说明"],
               ["同车分享上限", "5 人", "生效加待接受合计算；到上限后不能再发起，要给用户看得懂的原因"],
               ["待接受有效期", "72 小时", "逾期自动作废，作废的条目在列表里可见，可重新发起"],
               ["权限档位", "按对象与车辆的关系定：家庭成员可选全功能或仅解闭锁，其他联系人仅解闭锁",
                "本期不做「改权限」——要换权限就撤销这条重新分享"],
               ["有效期", "7 天 / 30 天 / 自定义至多 180 天", "到期自动失效"],
               ["撤销生效时限", "对方在线立即失效；离线的最长 24 小时内失效", "失效前车辆侧就要拒绝这把钥匙"],
               ["隐私", "页面与记录只显示对方昵称与打码后的账号", "任何页面不出现对方完整账号或手机号"]]),
        ("h", 3, "五、还没定的两件事"),
        ("p", "1. 被分享人能不能把钥匙再转给第三个人——我们倾向禁止，但要等安全评审的结论；"),
        ("p", "2. 撤销之后，对方设备和车辆都长期不联网的极端情况，要不要请车厂那边强制下线这把钥匙——还在和车厂谈。"),
        ("p", "这两件本期都先不做结论，方案里不要当成已定的事写。"),
        ("h", 3, "六、验收意图"),
        ("t", [["编号", "场景", "预期"],
               ["AC-K1", "发起分享", "三项选齐后发出，对方收到待接受的钥匙。"],
               ["AC-K2", "接受生效", "对方接受后钥匙可用，权限与车主所选一致。"],
               ["AC-K3", "逾期作废", "72 小时未接受自动作废，列表可见，可重新发起。"],
               ["AC-K4", "配额", "生效加待接受合计到 5 后不能再发起，能看到原因。"],
               ["AC-K5", "撤销", "对方在线立即失效；离线的 24 小时内失效，期间车辆不认这把钥匙。"],
               ["AC-K6", "中断续办", "发起途中退出或断网，回来接着办，不会发出第二条。"],
               ["AC-K7", "状态一致", "列表状态与实际一致：待接受、生效、已作废、已到期、撤销中、已撤销。"],
               ["AC-K8", "隐私", "全程页面与记录不出现对方完整账号或手机号。"],
               ["AC-K9", "入口门槛", "未登录或没有车钥匙的用户看不到分享入口。"],
               ["AC-K10", "功能开关", "开关关闭后不能发起新分享，已生效的分享不受影响。"],
               ["AC-K11", "权限随对象定", "选家庭成员时全功能可选；换成其他联系人后全功能不再可选，"
                "已选的全功能要请车主重选；换回家庭成员又可选。"]]),
    ]
    path = out_dir / "数字车钥匙分享.docx"
    write_docx(path, blocks, {
        "share-setup.png": png_share_setup(),
        "share-manage.png": png_share_manage(),
    })
    return path


def build_car_key_accept(out_dir: Path) -> Path:
    blocks = [
        ("h", 1, "车钥匙接受侧界面说明"),
        ("p", "撰写：出行产品组。补充给开发：被分享人那一侧的界面与交互，配合主需求稿一起看。"),
        ("h", 3, "一、接受页"),
        ("p", "被分享人收到推送，点进来看到的是一张车辆信息卡：车型与车主昵称、给到的权限范围、"
              "有效期到哪天。页面只有一个主动作「添加到钱包」（图 1）："),
        ("img", "accept-page.png"),
        ("p", "图 1　接受页"),
        ("p", "暂不添加就保持待接受，72 小时后自动作废——接受页不设「拒绝」按钮，不想要就放着。"),
        ("h", 3, "二、添加之后"),
        ("p", "添加成功后钥匙卡片进入对方的钱包卡包，卡片详情里能看到权限范围和有效期（图 2）；"
              "权限之外的功能不出现在对方的操作面上，而不是置灰。"),
        ("img", "key-card-detail.png"),
        ("p", "图 2　添加后的钥匙卡片详情"),
        ("h", 3, "三、可读性要求"),
        ("t", [["位置", "要求"],
               ["车辆信息卡", "先讲清这是谁分享的、能用到什么时候，再给添加按钮"],
               ["权限范围", "写人话：「能开门、能开走」而不是档位代号"],
               ["全局", "深色主题与大字体下，车辆信息与主按钮保持可读可点"]]),
    ]
    path = out_dir / "车钥匙接受侧界面说明.docx"
    write_docx(path, blocks, {"accept-page.png": png_accept_page(), "key-card-detail.png": png_key_card_detail()})
    return path


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "car-key-sharing"
    if target != "car-key-sharing":
        raise SystemExit(f"未知目标: {target}")
    out_dir = CASES / "car-key-sharing" / "supplements"
    for path in (build_car_key_prd(out_dir), build_car_key_accept(out_dir)):
        print(f"[assets] {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
