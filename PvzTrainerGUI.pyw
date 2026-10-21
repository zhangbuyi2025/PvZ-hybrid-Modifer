# -*- coding: utf-8 -*-
"""
植物大战僵尸杂交版 0.30 修改器 (个人单机使用 · 常驻控制窗口)
功能: 无限阳光 / 植物无敌 / 卡牌无限制冷却 / 商店金币不足也可购买 / 秒杀屏幕内所有僵尸(按钮)
交互: 勾选开关即时生效 (Mod 后台热切换, 无需重启游戏);
      「秒杀屏幕内所有僵尸」按钮向游戏发送清场指令, 点击后场上僵尸全部倒下 (不做胜负判定)。
游戏内快捷键: 6=切换无限阳光 7=切换植物无敌 8=切换卡牌无冷却 0=秒杀屏幕内全部僵尸。
"""
import json
import os
import re
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import messagebox

APP_DATA = os.environ.get("APPDATA", "")
BASE = os.path.dirname(os.path.abspath(__file__))
GAME_ROOT = os.path.dirname(BASE)

USER_DIR = os.path.join(APP_DATA, "Godot", "app_userdata", "植物大战僵尸杂交版")
MODS_DIR = os.path.join(USER_DIR, "Mods")
CFG_PATH = os.path.join(USER_DIR, "pzhtrainer.cfg")
CMD_PATH = os.path.join(USER_DIR, "pzhtrainer.cmd")
LOG_PATH = os.path.join(USER_DIR, "PVZHE_Trainer.log")
PMOD_SRC = os.path.join(BASE, "pvztrainer.pmod")
GAME_EXE = os.path.join(GAME_ROOT, "植物大战僵尸杂交重制版", "植物大战僵尸杂交版发布版0.30.0.Csharp.exe")
MOD_ID = "pvztrainer"
JOURNAL_FILES = ("mod_boot_journal.json", "mod_last_good.json")

# (配置键, 显示名)
KEYS = [
    ("inf_sun", "无限阳光"),
    ("plant_god", "植物无敌"),
    ("card_cd", "卡牌无限制冷却"),
    ("shop_free", "商店金币不足也可购买"),
]


def read_cfg():
    """读取现有配置, 缺失项默认全开"""
    vals = {k: True for k, _ in KEYS}
    try:
        with open(CFG_PATH, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = (s.strip() for s in line.split("=", 1))
                if k in vals:
                    vals[k] = v.lower() in ("1", "true", "yes", "on")
    except OSError:
        pass
    return vals


def write_cfg(vals):
    """原子写配置 (先写临时再替换, 避免 Mod 读到半个文件)"""
    os.makedirs(USER_DIR, exist_ok=True)
    lines = [
        "# 植物大战僵尸杂交版 0.30 修改器 配置 (由 PvzTrainerGUI 生成)",
        "# 1/true = 开启, 0/false = 关闭; 本 Mod 支持热切换, 修改后即时生效",
    ]
    for k, _ in KEYS:
        lines.append("%s=%d" % (k, 1 if vals[k] else 0))
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, CFG_PATH)


def send_kill_cmd():
    """写入清场秒杀指令 (原子替换, 内容 'kill')"""
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = CMD_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("kill\n")
    os.replace(tmp, CMD_PATH)


def install_mod():
    """复制 pmod 到游戏 Mods 目录并登记到启用列表 (保留其他 mod)"""
    if not os.path.exists(PMOD_SRC):
        return "缺少修改器模块文件:\n" + PMOD_SRC
    os.makedirs(MODS_DIR, exist_ok=True)
    shutil.copy2(PMOD_SRC, os.path.join(MODS_DIR, MOD_ID + ".pmod"))

    ep = os.path.join(MODS_DIR, "enabled_mods.json")
    sel = {"schemaVersion": 2, "enabledIds": [MOD_ID], "preferredOrder": [MOD_ID]}
    try:
        with open(ep, "r", encoding="utf-8") as f:
            old = json.load(f)
        ids = list(old.get("enabledIds") or [])
        order = list(old.get("preferredOrder") or [])
        if MOD_ID not in ids:
            ids.append(MOD_ID)
        if MOD_ID not in order:
            order.append(MOD_ID)
        sel = {"schemaVersion": 2, "enabledIds": ids, "preferredOrder": order}
    except (OSError, ValueError):
        pass
    with open(ep, "w", encoding="utf-8") as f:
        json.dump(sel, f, ensure_ascii=False, indent=2)
    return "OK"


def running_pids():
    """检测正在运行的游戏进程 (exe 名含 '植物大战僵尸')"""
    try:
        flags = 0x08000000  # CREATE_NO_WINDOW: 不弹出命令行窗口
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Where-Object { $_.ProcessName -like '*植物大战僵尸*' } | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, timeout=10, creationflags=flags)
        return [int(x) for x in re.findall(r"\d+", out.stdout or "")]
    except Exception:
        return []


def clean_journals():
    """删除引导日志, 防止异常残留导致下次启动进入 Mod 安全模式"""
    for n in JOURNAL_FILES:
        try:
            p = os.path.join(MODS_DIR, n)
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


class App:
    def __init__(self, root):
        self.root = root
        self.vars = {}
        root.title("植物大战僵尸杂交版 0.30 修改器")
        root.resizable(False, False)
        f = ("Microsoft YaHei UI", 11)
        f9 = ("Microsoft YaHei UI", 9)

        pad = tk.Frame(root, padx=18, pady=14)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="植物大战僵尸杂交版 0.30 修改器", font=("Microsoft YaHei UI", 15, "bold"),
                 fg="#2e7d32").pack(anchor="w")
        tk.Label(pad, text="个人单机使用 · 功能开关即时生效, 无需重启游戏",
                 font=f9, fg="#888888").pack(anchor="w", pady=(0, 10))

        # 功能开关 (勾选变化立即生效)
        self.last_click = 0.0
        for k, name in KEYS:
            self.vars[k] = tk.BooleanVar(self.root)
            cb = tk.Checkbutton(pad, text=name, variable=self.vars[k], font=f,
                                anchor="w", command=lambda k=k: self.on_toggle(k))
            cb.pack(fill="x", pady=3)
        self.saved_hint = tk.Label(pad, text="", font=f9,
                                   fg="#7cb342", anchor="w")
        self.saved_hint.pack(fill="x")
        tk.Label(pad, text="★ 游戏内快捷键 (进入关卡后直接按键, 无需打开窗口):",
                 font=f9, fg="#5d4037").pack(anchor="w", pady=(2, 0))
        tk.Label(pad, text="6 无限阳光 · 7 植物无敌 · 8 卡牌冷却 · 0 秒杀僵尸",
                 font=("Microsoft YaHei UI", 10, "bold"), fg="#e65100").pack(anchor="w")

        # 清场秒杀按钮
        tk.Frame(pad, height=6).pack()
        kill_btn = tk.Button(pad, text="秒杀屏幕内所有僵尸", font=("Microsoft YaHei UI", 13, "bold"),
                             fg="white", bg="#c62828", activebackground="#b71c1c",
                             activeforeground="white", relief="flat",
                             command=self.on_kill)
        kill_btn.pack(fill="x", ipady=6)
        tk.Label(pad, text="点击后场上(屏幕内)所有僵尸立即倒下 (需处于关卡中)",
                 font=f9, fg="#999999").pack(anchor="w", pady=(4, 0))

        # 启动选项与按钮
        self.win_mode = tk.BooleanVar(self.root, value=True)
        tk.Checkbutton(pad, text="窗口模式启动游戏", variable=self.win_mode,
                       font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(10, 0))
        btns = tk.Frame(pad)
        btns.pack(fill="x", pady=(10, 6))
        tk.Button(btns, text="安装 / 更新 Mod", font=f9, command=self.on_install).pack(side="left")
        tk.Button(btns, text="启动游戏", font=f9, command=self.on_launch,
                  bg="#e8f5e9").pack(side="left", padx=(8, 0))
        tk.Button(btns, text="查看日志", font=f9, command=self.on_log).pack(side="right")

        # 状态栏
        self.status = tk.Label(pad, text="", font=f9,
                               fg="#555555", justify="left", anchor="w")
        self.status.pack(fill="x", pady=(6, 0))

        self.load_state()
        self.set_hint("")
        self.refresh_status()
        # 定期读取配置: 游戏内按 6/7/8 改动的开关状态实时同步到窗口复选框
        self.root.after(250, self.poll_cfg)

    # ---------- 逻辑 ----------
    def poll_cfg(self):
        try:
            if time.monotonic() - self.last_click < 0.8:
                return  # 用户正在操作窗口期间不打断, 避免刷新覆盖点击
            vals = read_cfg()
            for k, _ in KEYS:
                if self.vars[k].get() != vals[k]:
                    self.vars[k].set(vals[k])
        except Exception:
            pass
        finally:
            self.root.after(250, self.poll_cfg)
    def load_state(self):
        vals = read_cfg()
        for k, _ in KEYS:
            self.vars[k].set(vals[k])

    def active_summary(self, vals=None):
        src = vals if vals is not None else {k: v.get() for k, v in self.vars.items()}
        return " · ".join(name for k, name in KEYS if src[k])

    def on_toggle(self, key):
        """勾选变化 -> 合并写配置: 只认窗口里刚点击的这一项;
        其余项保留磁盘最新值 (游戏内快捷键刚写回的状态), 不再被窗口旧状态覆盖"""
        vals = read_cfg()
        vals[key] = self.vars[key].get()
        self.last_click = time.monotonic()
        try:
            write_cfg(vals)
            self.set_hint("已保存并即时生效: " + (self.active_summary(vals) or "无") + "  (游戏运行中也立即生效)")
        except Exception as e:
            self.set_hint("保存失败: %s" % e, err=True)

    def on_kill(self):
        """清场秒杀: 写入指令文件, 游戏内 Mod 轮询后执行"""
        pids = running_pids()
        if not pids:
            messagebox.showwarning("游戏未运行", "请先启动游戏并进入关卡, 再点击「秒杀屏幕内所有僵尸」。")
            return
        try:
            send_kill_cmd()
        except Exception as e:
            messagebox.showerror("发送失败", "无法写入秒杀指令:\n%s" % e)
            return
        self.set_hint("秒杀指令已发送 (场上的僵尸即将全部倒下)")

    def on_install(self):
        r = install_mod()
        if r == "OK":
            messagebox.showinfo("安装成功", "修改器 Mod 已安装并启用。\n若游戏正在运行, 需重启游戏后生效 (v1.1 起开关支持热切换)。")
        else:
            messagebox.showerror("安装失败", r)
        self.refresh_status()

    def on_launch(self):
        pids = running_pids()
        if pids:
            messagebox.showwarning("游戏正在运行",
                                   "请先关闭游戏 (PID: %s), 再点击本按钮启动。" % ", ".join(map(str, pids)))
            return
        if not os.path.exists(GAME_EXE):
            messagebox.showerror("找不到游戏", "未找到:\n" + GAME_EXE)
            return
        r = install_mod()
        if r != "OK":
            messagebox.showerror("Mod 未就绪", r)
            return
        clean_journals()
        cmd = [GAME_EXE]
        if self.win_mode.get():
            cmd.append("--windowed")
        subprocess.Popen(cmd, cwd=os.path.dirname(GAME_EXE))
        self.refresh_status()
        messagebox.showinfo("已启动", "游戏已启动。\n\n进入关卡后即可: 勾选开关即时生效; 点「秒杀屏幕内所有僵尸」清场;"
                                      " 也可直接按游戏内快捷键 6/7/8 切换开关, 按 0 清场。")

    def on_log(self):
        if os.path.exists(LOG_PATH):
            os.startfile(LOG_PATH)
        elif os.path.isdir(USER_DIR):
            os.startfile(USER_DIR)
        else:
            messagebox.showinfo("日志", "暂无日志: 请先启动过游戏。\n" + LOG_PATH)

    def set_hint(self, text, err=False):
        self.saved_hint.config(text=text, fg="#c62828" if err else "#7cb342")

    def refresh_status(self):
        lines = [
            "Mod: %s" % ("已安装" if os.path.exists(os.path.join(MODS_DIR, MOD_ID + ".pmod")) else "未安装 (请先点击 安装/更新 Mod)"),
            "游戏: %s" % ("运行中" if running_pids() else "未运行 · " + ("已找到" if os.path.exists(GAME_EXE) else "未找到")),
        ]
        self.status.config(text="\n".join(lines))

    def close(self):
        # 开关已在勾选时即时写盘, 关闭不再全量写, 避免覆盖游戏内快捷键刚切换的状态
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()