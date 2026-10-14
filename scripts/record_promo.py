"""Record existing Qt widgets with isolated demonstration data; no network or desktop capture.

Run with the desktop Python environment. Generated media stays in ignored dist/.
No business write, credential reader, host transcript reader, or browser is used.
"""
from __future__ import annotations

import argparse
from array import array
from dataclasses import dataclass
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass
class Scene:
    key: str
    seconds: int
    tag: str
    title: str
    lines: tuple[str, ...]
    voice: str


SCENES = [
    Scene("hello", 6, "McPet · 麦麦搭子", "鲸鲸，来陪你啦。", ("余额有人盯", "进度有人陪", "干饭有人喊"), "忙到忘记吃饭？让麦麦搭子，住进你的屏幕角落。"),
    Scene("menu", 6, "01 / 轻轻右键", "小小一只，都在这里。", ("查进度、看额度、找饭饭", "右键小菜单，结果冒气泡", "陪伴可以很轻"), "轻轻右键，进度、额度、饭饭和咖啡，都藏在小菜单里。"),
    Scene("agent", 6, "02 / Agent 里的搭子", "继续用熟悉的 Agent。", ("通过 Skill / MCP 调用", "OpenCode、Claude Code 等可接入", "没有另一套聊天流程"), "继续和你熟悉的 Agent 聊天。通过 Skill 和 MCP，让桌宠接住小任务。"),
    Scene("progress", 8, "03 / 进度有人陪", "你写代码，她陪你盯。", ("查看会话状态与上下文占用", "等待输入、报错会提醒", "完成要有明确记录"), "在忙、等输入，还是遇到小麻烦？鲸鲸陪你盯着。完成了，也要有明确记录。"),
    Scene("balance", 7, "04 / 余额有人盯", "小钱包，也有人惦记。", ("DeepSeek API 余额", "订阅额度按窗口分别查看", "没查到，就诚实说未知"), "小钱包有人惦记。余额和订阅额度分开看，没查到的时候，就诚实说未知。"),
    Scene("usage", 5, "05 / 用量小本本", "今天用了多少呀？", ("查看本机用量记录", "本机用量与厂商余额分开", "慢慢算，清清楚楚"), "今天用了多少？小本本帮你记。但本机用量，和厂商余额要分开算。"),
    Scene("meal", 6, "06 / 干饭有人喊", "鲸鲸想了想：先吃饭！", ("饭点与咖啡时间可设置", "到点冒个小气泡", "把注意力还给饭饭"), "鲸鲸想了想，代码可以继续写，饭饭不能一直等。到点，就轻轻喊你一声。"),
    Scene("coupons", 6, "07 / 麦当劳小雷达", "券券，先帮你看看。", ("查询可领券与已有券", "主动领取前，先问你", "优惠结果在气泡里看"), "想吃点好的？先看看可领券和已有券。主动领取之前，当然先问你。"),
    Scene("deals", 7, "08 / 门店与比价", "挑门店，再算饭钱。", ("附近门店与餐品报价", "券后价格，放在一起比较", "指定门店、预算先对好"), "挑好门店，再看看餐品和券后价格。门店对不对，饭钱多少，都要先讲清楚。"),
    Scene("coffee", 12, "09 / 瑞幸咖啡雷达", "给脑袋，续一杯。", ("门店 → 商品 → 口味规格", "订单预览，先看实付", "已知订单可查状态与取餐码"), "给脑袋续一杯。选门店、挑咖啡、调口味，先看订单预览。已有订单，也能查状态。"),
    Scene("confirm", 6, "10 / 你点头，才继续", "买不买，听你的。", ("门店、餐品、金额先核对", "确认框里，可以随时取消", "支付由你在商家渠道完成"), "买不买，听你的。门店、餐品、金额，核对清楚再继续。支付这一步，交给你。"),
    Scene("nutrition", 7, "11 / 饭饭小本本", "吃过的，都记一笔。", ("选择餐品与份数", "本机保存饮食记录", "查看今天的营养累计"), "吃过的饭饭，也记一笔。选餐品、填份数，今天的营养累计，就在小本本里。"),
    Scene("settings", 5, "12 / 小窝按你喜欢的来", "时间、位置，自己定。", ("饭点与咖啡时间可改", "城市与日志来源可设置", "凭证输入会遮住内容"), "饭点、咖啡时间、城市和日志来源，都能自己定。小窝按你喜欢的来。"),
    Scene("skins", 8, "13 / 本机皮肤预览", "今天，谁来陪你？", ("DeepSeek 娘 / ChatGPT 娘", "默认套装与麦麦套装随时切换", "不把某一套穿搭定死"), "今天让谁陪你？DeepSeek 娘，还是 ChatGPT 娘？默认套装和麦麦套装，也可以随时切换。"),
    Scene("actions", 8, "14 / 两段动作，一起上岗", "换好衣服，薯条出锅！", ("换装动作 → 工装待机", "炸薯条动作可循环", "也能随时停止动作"), "换好衣服，薯条出锅！换装和炸薯条，都做进桌宠里啦。想停下来，也很方便。"),
    Scene("roam", 5, "15 / 屏幕角落的日常", "溜达一下，再陪你。", ("闲逛与拖动", "置顶小窗，轻巧陪伴", "想安静，也可以先藏起来"), "陪你工作，也能溜达一下。想安静，就让她先藏一会儿。"),
    Scene("rest", 4, "16 / 休息也是正经事", "打个盹，等你回来。", ("休息 / 唤醒", "轻轻摸摸，接着陪你"), "打个盹，等你回来。休息好了，再一起把今天慢慢做好。"),
    Scene("bye", 6, "McPet · 当前版本功能演示", "饭饭与代码，都有人陪。", ("余额有人盯，进度有人陪，干饭有人喊", "在你熟悉的 Agent 里，叫上麦麦搭子", "github.com/songconmaisaix31-design/mcpet"), "余额有人盯，进度有人陪，干饭有人喊。麦麦搭子，陪你把今天慢慢做好。"),
]


def audio_tracks(folder: Path) -> Path:
    """Use local Windows speech plus an original, softly synthesized music bed."""
    spec = [{"text": s.voice, "output": str(folder / f"voice-{i:02}.wav")} for i, s in enumerate(SCENES)]
    (folder / "voice-plan.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    ps = r'''param([string]$Plan)
Add-Type -AssemblyName System.Speech
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speech.SelectVoice('Microsoft Huihui Desktop')
$speech.Rate = 1
foreach ($item in (Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json)) {
    $speech.SetOutputToWaveFile($item.output)
    $speech.Speak($item.text)
}
$speech.Dispose()
'''
    script = folder / "narrate.ps1"
    script.write_text(ps, encoding="utf-8-sig")
    subprocess.run(["powershell.exe", "-NoProfile", "-File", str(script), "-Plan", str(folder / "voice-plan.json")], check=True, stdout=subprocess.DEVNULL)
    rate = 22050
    length = sum(s.seconds for s in SCENES)
    samples = array("f", [0]) * (rate * length)
    offset = 0
    for i, scene in enumerate(SCENES):
        with wave.open(str(folder / f"voice-{i:02}.wav"), "rb") as f:
            if f.getsampwidth() != 2 or f.getnchannels() != 1:
                raise ValueError("Narration requires mono PCM16")
            source_rate = f.getframerate()
            values = array("h", f.readframes(f.getnframes()))
        duration = len(values) / source_rate
        # Fit speech without cropping words; report any acceleration in the review file.
        factor = max(1.0, duration / (scene.seconds - 0.7))
        count = int(len(values) * rate / source_rate / factor)
        for j in range(count):
            source = j * source_rate / rate * factor
            k = min(int(source), len(values) - 1)
            fraction = source - k
            v = values[k] * (1 - fraction) + values[min(k + 1, len(values) - 1)] * fraction
            index = int((offset + 0.35) * rate) + j
            if index < len(samples):
                samples[index] += v / 32768 * 0.84
        offset += scene.seconds
    # Original pentatonic melody, no downloaded music or samples.
    notes = [60, 64, 67, 69, 67, 64, 62, 67, 60, 62, 64, 69, 67, 64, 62, 60]
    for i in range(len(samples)):
        t = i / rate
        beat = int(t / 0.5)
        local = t % 0.5
        frequency = 440 * 2 ** ((notes[beat % len(notes)] - 69) / 12)
        envelope = min(1, local / 0.02) * math.exp(-local * 8)
        melody = math.sin(2 * math.pi * frequency * local) + 0.18 * math.sin(4 * math.pi * frequency * local)
        bass = math.sin(2 * math.pi * 130.8128 * t) * 0.15
        fade = min(1, t / 2, (length - t) / 3)
        samples[i] += (melody * envelope + bass) * 0.038 * fade
    pcm = array("h", (int(max(-0.98, min(0.98, value)) * 32767) for value in samples))
    path = folder / "soundtrack.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())
    return path


def write_timeline(folder: Path):
    def stamp(seconds):
        return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},000"
    subtitles, chapters, timeline = [], [";FFMETADATA1", "title=McPet - 麦麦搭子功能宣传片"], []
    start = 0
    for i, scene in enumerate(SCENES):
        end = start + scene.seconds
        subtitles.append(f"{i + 1}\n{stamp(start)} --> {stamp(end)}\n{scene.voice}\n")
        chapters.extend(["[CHAPTER]", "TIMEBASE=1/1000", f"START={start * 1000}", f"END={end * 1000}", f"title={scene.tag}"])
        timeline.append({"start": start, "end": end, "feature": scene.tag, "title": scene.title})
        start = end
    (folder / "narration.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (folder / "chapters.txt").write_text("\n".join(chapters), encoding="utf-8")
    (folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")


def record(args, folder: Path) -> Path:
    # Isolation is established before importing any application module.
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["MCPET_DATA_DIR"] = str(folder / "demo-profile")
    os.environ["MCPET_CONFIG_PATH"] = str(folder / "demo-profile/config.json")
    os.environ["MCPET_REMINDERS"] = "true"
    for key in ("MCD_MCP_TOKEN", "LUCKIN_MCP_TOKEN", "DEEPSEEK_API_KEY", "STEPFUN_API_KEY"):
        os.environ[key] = "none"
    os.environ.update(MCPET_CITY="北京", MCPET_LONGITUDE="116.326497", MCPET_LATITUDE="39.788104", MCPET_COFFEE_DEPT_ID="1")
    from PySide6.QtCore import QObject, Signal, QTimer, Qt, QRectF, QPoint
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu
    from src import config
    from src.main import MonsterApp
    from src.accounts.models import AccountSnapshot, AccountStatus, MoneyBalance, QuotaBucket
    from src.agentbridge.records import ProgressRecord, UsageTotals
    from src.progress.tracker import ProgressSnapshot, SessionProgress
    from src.mcd_mcp.brain import CouponRoundup, DealQuote, StoreInfo, NutritionFact
    from src.pet.menu import populate_menu

    class Monitor(QObject):
        progress_ready = Signal(object)
        usage_ready = Signal(object)
        failed = Signal(str)
        task_completed = Signal(object)
        snapshot_ready = Signal(object)
        stopped = Signal()
        def start(self): pass
        def refresh(self): pass
        def refresh_progress(self): pass
        def refresh_usage(self): pass
        def stop(self): self.stopped.emit()

    class DemoBrain:
        def coupon_roundup(self, *, claim=False):
            if claim:
                raise RuntimeError("Recording cannot claim coupons")
            return CouponRoundup(available_count=6, my_coupon_count=3, my_coupons=["餐品优惠示例"] * 3)
        def resolve_default_store(self):
            return StoreInfo("DEMO", "演示门店 · 北京西红门荟聚")
        def best_deal(self, store):
            return [DealQuote("演示汉堡", "DEMO", "演示优惠券", baseline_cents=3000, payable_cents=2200)]
        def nutrition(self):
            return [NutritionFact("演示汉堡", energy_kcal=450, protein_g=22, fat_g=18, carb_g=50, sodium_mg=800)]

    class DemoCoffee:
        pending = None
        def query(self, tool, payload):
            if tool == "searchProductForMcp":
                return [{"productName": "演示生椰拿铁", "estimatePrice": "16.60", "productId": 1, "skuCode": "DEMO"}]
            if tool == "queryOrderDetailInfo":
                return {"orderStatusName": "制作中（演示）", "takeMealCodeInfo": {"code": "DEMO"}}
            raise RuntimeError("Recording permits only its explicit read fixtures")
        def prepare(self, dept, items, longitude, latitude):
            self.pending = {"summary": "演示门店 · 西红门荟聚\n生椰拿铁 × 1\n大杯 / 冰 / 不额外加糖\n演示实付 ¥16.60\n预算 ¥30；尚未提交"}
            return self.pending
        def confirm(self, *args):
            raise RuntimeError("Recording cannot create an order")
        def cancel(self, *args):
            raise RuntimeError("Recording cannot cancel an order")

    qt = QApplication.instance() or QApplication([])
    # The offscreen Windows plugin has no automatic system-font discovery.
    font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    families = []
    for name in ("msyh.ttc", "msyhbd.ttc", "seguisym.ttf", "segoeui.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_dir / name))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    if not families:
        raise RuntimeError("A Chinese-capable Microsoft YaHei font is required")
    font_family = families[0]
    QFont.insertSubstitution("Microsoft YaHei UI", font_family)
    qt.setFont(QFont(font_family, 10))
    default_font = QFont(font_family, 10)
    default_font.setFamilies([font_family, "Segoe UI Symbol", "Segoe UI"])
    qt.setFont(default_font)
    config.load_env = lambda: None  # Never read the user's .env or host accounts.
    app = MonsterApp([], enforce_single_instance=False, monitor_factory=Monitor, account_monitor_factory=Monitor)
    app.scheduler.stop()
    app.tasks.worker.ensure_client = lambda: DemoBrain()
    app.tasks.worker.coffee = DemoCoffee()
    app.window.move(300, 350)
    app.window.set_character("deepseek", skin_id="default")
    app.window.set_roaming(False)
    app.window.set_resting(False)
    app.window.bubble.label.setFont(default_font)
    folder.mkdir(parents=True, exist_ok=True)
    silent = folder / "picture.mp4"
    log = (folder / "encode.log").open("wb")
    encoder = subprocess.Popen([str(args.ffmpeg), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", str(args.fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent)], stdin=subprocess.PIPE, stdout=log, stderr=log)
    current = {"index": -1, "menu": None, "frame": 0, "enter": 0, "errors": []}
    starts = []
    elapsed = 0
    for scene in SCENES:
        starts.append(elapsed)
        elapsed += scene.seconds
    length = min(elapsed, args.seconds) if args.seconds else elapsed
    metadata = {"source": "existing Qt widgets / isolated demonstration data", "network": False, "desktop_capture": False, "frames": 0, "scenes": [], "duration": length}
    delayed = []

    def later(seconds, callback):
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(round(seconds * 1000))
        delayed.append(timer)

    def cancel_ask():
        if app.window.bubble.interacting:
            app.window.bubble.buttons[-1].click()

    def ask_until_cancel(callback, seconds):
        later(seconds, cancel_ask)
        callback()

    def show_menu(group=None):
        menu = QMenu(app.window)
        populate_menu(menu, app.menu_entries())
        if group:
            menu = next(a.menu() for a in menu.actions() if a.text() == group)
        menu.popup(QPoint(25, 25))
        current["menu"] = menu

    def close_menu():
        if current["menu"]:
            current["menu"].close()
            current["menu"] = None

    def scene_enter(index):
        key = SCENES[index].key
        if current["menu"]:
            current["menu"].close()
            current["menu"] = None
        app.window.stop_action()
        app.window.bubble.hide()
        metadata["scenes"].append(key)
        print(f"recording {index + 1}/{len(SCENES)}: {key}", flush=True)
        if key == "hello":
            app.window.say("鲸鲸到岗！\n陪你把今天慢慢做好～", 12000)
        elif key == "menu":
            show_menu()
        elif key == "agent":
            app.action_panel()
        elif key == "progress":
            record = ProgressRecord("generic", "demo-session", state="working", title="宣传视频剪辑（演示）", context_used=24000, context_limit=100000, updated_at=time.time())
            app._progress_ready(ProgressSnapshot([SessionProgress(record)], ["generic"]))
            app.action_progress()
            later(4, lambda: app._task_completed({"completion_id": "demo-completed"}))
        elif key == "balance":
            app.account_snapshot = AccountSnapshot((AccountStatus("deepseek", "DeepSeek API（演示）", "ok", time.time(), balances=(MoneyBalance("CNY", Decimal("8.60"), Decimal("0.60"), Decimal("8")),)), AccountStatus("codex", "订阅额度（演示）", "ok", time.time(), buckets=(QuotaBucket("周窗口", 36, None),))), time.time())
            app._accounts_requested = True
            app.account_refreshing = False
            app._render_accounts()
        elif key == "usage":
            from src.metering.usage import UsageSnapshot
            app.usage_snapshot = (UsageSnapshot(today=UsageTotals(tokens=12500, calls=8), window=UsageTotals(tokens=8400, calls=4), sources=["generic"]), 8400, False)
            app.action_balance()
        elif key == "meal":
            app.on_lunch()
            later(3, lambda: app.on_scheduled("coffee", False))
        elif key == "coupons":
            app.action_coupon_report()
            show_menu("麦当劳")
            later(2.2, close_menu)
            later(3, lambda: ask_until_cancel(app.action_claim_coupons, 2))
        elif key == "deals":
            app.action_best_deal()
        elif key == "coffee":
            app.action_coffee_products(automatic=True)
            show_menu("瑞幸咖啡")
            later(2.2, close_menu)
            app.coffee_product = {"productId": 1, "skuCode": "DEMO"}
            app.coffee_dept = 1
            later(3, lambda: app._business_message(app.tasks.worker.coffee.prepare(1, [], 116, 39)["summary"]))
            later(6, lambda: ask_until_cancel(app.action_coffee_confirm, 2))
            app.coffee_order = "DEMO"
            later(8.5, app.action_coffee_order)
        elif key == "confirm":
            ask_until_cancel(lambda: app._confirm("这份演示订单对了吗？", "演示门店 · 北京西红门荟聚\n汉堡 × 1；外带\n实付示例 ¥22.00 / 预算 ¥30\n尚未提交订单", "下单"), 4.5)
            app.window.say("已取消，没有提交订单。", 5000)
        elif key == "nutrition":
            fact = DemoBrain().nutrition()[0]
            app.ledger.add_fact(fact)
            app.action_nutrition_summary()
            later(3, lambda: ask_until_cancel(lambda: app.window.ask("今天吃了什么？（演示餐品）", [("演示汉堡 · 450 kcal", 1), ("演示薯条 · 220 kcal", 2)]), 2))
        elif key == "settings":
            app.action_settings()
            later(2.5, lambda: show_menu("设置"))
        elif key == "skins":
            app.action_skin_maimai()
            app.window.say("麦麦套装换好啦～", 3000)
            later(2.5, lambda: app._change_character("maimai"))
            later(5.2, lambda: app._change_character("deepseek"))
            later(6.2, app.action_skin_default)
        elif key == "actions":
            app.action_outfit()
            later(4.1, app.action_frying)
        elif key == "roam":
            app.window.bubble.hide()
            app.action_roaming()
        elif key == "rest":
            app.window.set_roaming(False)
            app.action_resting()
            app.window.say("鲸鲸充电中，等你回来～", 6000)
        elif key == "bye":
            app.window.set_resting(False)
            app.window.set_skin("default")
            app.window.say("今天也辛苦啦。\n记得吃饭，也记得休息～", 9000)

    def text(p, x, y, w, h, value, size, color="#493D36", bold=False):
        font = QFont(font_family)
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(QRectF(x, y, w, h), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, value)

    def capture(widget):
        # Render the same Qt widget at export density so text stays sharp.
        scale = 2.4
        image = QImage(round(widget.width() * scale), round(widget.height() * scale), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.scale(scale, scale)
        widget.render(painter, QPoint())
        painter.end()
        return QPixmap.fromImage(image)

    def paint(t):
        scene = SCENES[current["index"]]
        local = t - starts[current["index"]]
        image = QImage(1920, 1080, QImage.Format_RGB888)
        image.fill(QColor("#FFF8EE"))
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EAF4FB"))
        p.drawEllipse(QRectF(1260, -200, 900, 900))
        p.setBrush(QColor("#FFF0DF"))
        p.drawEllipse(QRectF(-220, 740, 740, 650))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(960, 154, 870, 755), 38, 38)
        text(p, 96, 54, 850, 68, "McPet  /  麦麦搭子", 34, bold=True)
        text(p, 1220, 58, 600, 58, "桌宠界面录制 · 演示数据", 25, "#75665B")
        # Captured widgets remain faithful; framing and titles are editorial overlays.
        if app.window.isVisible():
            pet = capture(app.window)
            shift = max(-100, min(100, (app.window.x() - 300) * 2)) if scene.key == "roam" else 0
            p.drawPixmap(QRectF(1120 + shift, 438, 550, 550), pet, QRectF(pet.rect()))
        if app.window.bubble.isVisible():
            bubble = capture(app.window.bubble)
            scale = min(624 / bubble.width(), 455 / bubble.height())
            width, height = bubble.width() * scale, bubble.height() * scale
            p.drawPixmap(QRectF(1394 - width / 2, 210, width, height), bubble, QRectF(bubble.rect()))
        if current["menu"] and current["menu"].isVisible():
            pix = capture(current["menu"])
            scale = min(2.3 / 2.4, 770 / pix.width(), 650 / pix.height())
            width, height = pix.width() * scale, pix.height() * scale
            p.drawPixmap(QRectF(1005, 196, width, height), pix, QRectF(pix.rect()))
        # Staggered entrances; the cream wipe below joins adjacent scenes.
        enter = 1 - max(0, 1 - local / 0.8) ** 3
        p.save()
        p.setOpacity(enter)
        p.translate(0, 25 * (1 - enter))
        text(p, 98, 193, 790, 56, scene.tag, 27, "#AD6D39", True)
        text(p, 92, 277, 800, 207, scene.title, 74, bold=True)
        for i, line in enumerate(scene.lines):
            p.setOpacity(max(0, min(1, (local - 0.3 - i * 0.12) / 0.5)))
            p.setBrush(QColor("#72AAD7"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(99, 546 + i * 102, 13, 13))
            text(p, 135, 520 + i * 102, 725, 82, line, 31)
        p.restore()
        text(p, 100, 970, 1450, 52, "余额有人盯，进度有人陪，干饭有人喊", 27, "#75665B")
        text(p, 1690, 970, 190, 52, f"{current['index'] + 1:02} / {len(SCENES):02}", 27, "#75665B")
        p.setPen(QPen(QColor("#EEDFD1"), 4))
        p.drawLine(98, 1040, 1822, 1040)
        p.setPen(QPen(QColor("#72AAD7"), 4))
        p.drawLine(98, 1040, 98 + round(1724 * t / elapsed), 1040)
        if local < 0.25 and current["index"]:
            p.setOpacity(1 - local / 0.25)
            p.fillRect(image.rect(), QColor("#FFF8EE"))
        p.end()
        return image

    def tick():
        t = current["frame"] / args.fps
        if t >= length:
            timer.stop()
            cancel_ask()
            if current["menu"]:
                current["menu"].close()
            app.quit()
            return
        index = max(i for i, start in enumerate(starts) if t >= start)
        if index != current["index"]:
            current["index"] = index
            QTimer.singleShot(0, lambda i=index: guarded_enter(i))
        frame = paint(t)
        try:
            encoder.stdin.write(frame.constBits().tobytes())
            if abs(t - starts[index] - 1.8) < 0.5 / args.fps:
                frame.save(str(folder / f"scene-{index:02}.png"))
                if index == 0:
                    frame.save(str(folder / "cover.png"))
            if abs(t - starts[index] - 4) < 0.5 / args.fps:
                frame.save(str(folder / f"scene-{index:02}-detail.png"))
            current["frame"] += 1
            metadata["frames"] = current["frame"]
        except Exception as exc:
            current["errors"].append(str(exc))
            timer.stop()
            app.quit()

    def guarded_enter(index):
        try:
            scene_enter(index)
        except Exception as exc:
            current["errors"].append(f"{SCENES[index].key}: {type(exc).__name__}: {exc}")
            print(current["errors"][-1], flush=True)

    timer = QTimer()
    timer.setTimerType(Qt.PreciseTimer)
    timer.setInterval(round(1000 / args.fps))
    timer.timeout.connect(tick)
    timer.start()
    app.app.exec()
    encoder.stdin.close()
    status = encoder.wait()
    log.close()
    metadata["errors"] = current["errors"]
    (folder / "capture-review.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if status or current["errors"]:
        raise RuntimeError("Capture failed; inspect capture-review.json and encode.log")
    return silent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/promo-20261014")
    parser.add_argument("--fps", type=int, choices=(24, 30), default=30)
    parser.add_argument("--seconds", type=int, help="Short smoke capture, without narration")
    parser.add_argument("--mux-only", action="store_true", help="Reuse this directory's existing capture and soundtrack")
    args = parser.parse_args()
    folder = args.output.resolve()
    # Keep the deliverable out of Git, including all local character previews.
    if ROOT / "dist" not in (folder, *folder.parents):
        parser.error("Output must stay inside the repository's ignored dist directory")
    folder.mkdir(parents=True, exist_ok=True)
    if args.seconds is not None and args.seconds <= 0:
        parser.error("--seconds must be positive")
    if args.mux_only and args.seconds:
        parser.error("--mux-only cannot be combined with --seconds")
    silent = folder / "picture.mp4" if args.mux_only else record(args, folder)
    if not args.seconds:
        audio = folder / "soundtrack.wav" if args.mux_only else audio_tracks(folder)
        if not silent.is_file() or not audio.is_file():
            parser.error("The existing capture and soundtrack are required")
        write_timeline(folder)
        with (folder / "mux.log").open("wb") as log:
            subprocess.run([str(args.ffmpeg), "-y", "-i", str(silent), "-i", str(audio), "-i", str(folder / "narration.srt"), "-i", str(folder / "chapters.txt"), "-map", "0:v", "-map", "1:a", "-map", "2:s", "-map_metadata", "3", "-map_chapters", "3", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-t", str(sum(s.seconds for s in SCENES)), "-movflags", "+faststart", str(folder / "McPet-promo-1080p.mp4")], check=True, stdout=subprocess.DEVNULL, stderr=log)
    print("Promo capture complete", flush=True)


if __name__ == "__main__":
    main()
