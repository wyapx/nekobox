import shutil
import asyncio
import secrets
from pathlib import Path
from argparse import ArgumentParser
from configparser import ConfigParser
from typing import List, Optional, overload

from creart import it
from loguru import logger
from satori.server import Server

from nekobox import __version__
from nekobox.main import NekoBoxAdapter
from nekobox.log import loguru_exc_callback_async

CONFIG_FILE = Path("nekobox.ini")
cyan = "\033[96m"
reset = "\033[0m"
green = "\033[32m"
gold = "\033[33m"
yellow = "\033[93m"
purple = "\033[95m"
magnet = "\033[35m"
red = "\033[31m"
ul = "\033[4m"
bd = "\033[1m"


def run(uin: int, host: str, port: int, token: str, path: str, protocol: str, sign_url: str, level: str, use_png: bool):
    loop = it(asyncio.AbstractEventLoop)
    loop.set_exception_handler(loguru_exc_callback_async)
    server = Server(host=host, port=port, path=path, token=token, stream_threshold=4 * 1024 * 1024)
    server.apply(NekoBoxAdapter(uin, sign_url, protocol, level, use_png))  # type: ignore
    server.run()


@overload
def set_cfg(
    cfg: ConfigParser, section: str, option: str, description: str, *, unique: Optional[List[str]] = None
) -> str: ...


@overload
def set_cfg(
    cfg: ConfigParser,
    section: str,
    option: str,
    description: str,
    default: str,
    unique: Optional[List[str]] = None,
) -> str: ...


def set_cfg(
    cfg: ConfigParser,
    section: str,
    option: str,
    description: str,
    default: Optional[str] = None,
    unique: Optional[List[str]] = None,
):
    if not unique:
        unique = []
    try:
        i = str(
            input(
                f"{description}{f' {cyan}(必填项){reset}' if default is None else f' {cyan}({default}){reset}'}: "
            )
        )
        if not i:
            if default is None:
                raise ValueError
            else:
                i = default
        if i and unique and i not in unique:
            raise ValueError

        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, option, i)

        return i
    except (TypeError, ValueError):
        print(f">>> 输入不符合约束: {green}{unique}{reset}")
        return set_cfg(cfg, section, option, description, default, unique)  # type: ignore


def generate_cfg(args):
    cfg = ConfigParser()
    exist = False
    if (Path.cwd() / CONFIG_FILE).exists():
        exist = True
        cfg.read(CONFIG_FILE, encoding="utf-8")
        print(f"{cyan}正在更新配置文件...{reset}")
    else:
        print(f"{cyan}正在生成配置文件...{reset}")
    uin = args.uin
    if not uin or uin == "?":
        if exist:
            for section in cfg.sections():
                if section == "default":
                    continue
                print(f" - {magnet}{ul}{section}{reset}")
            uin = (
                input(f"{gold}请选择一个账号{reset} {cyan}({cfg['default']['uin']}){reset}: ").strip()
                or cfg["default"]["uin"]
            )
        else:
            uin = set_cfg(cfg, "default", "uin", "Bot 的 QQ 号")
    if uin not in cfg:
        cfg.add_section(uin)
    set_cfg(cfg, uin, "sign", "Bot 的 SignUrl")
    set_cfg(cfg, uin, "protocol", "Bot 的协议类型", default="linux", unique=["linux", "macos", "windows"])
    set_cfg(cfg, uin, "token", "Satori 服务器的验证 token", default=secrets.token_hex(8))
    set_cfg(cfg, uin, "host", "Satori 服务器绑定地址", default="127.0.0.1")
    set_cfg(cfg, uin, "port", "Satori 服务器绑定端口", default="7777")
    set_cfg(cfg, uin, "path", "Satori 服务器部署路径 (可以为空)", default="")
    set_cfg(
        cfg,
        uin,
        "log_level",
        "默认日志等级",
        default="INFO",
        unique=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    with (Path.cwd() / CONFIG_FILE).open("w+", encoding="utf-8") as f:
        cfg.write(f)
    print(f"{green}配置文件已保存{reset}")


def _delete(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        print(f"请先使用 {yellow}`nekobox gen {args.uin or ''}`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    if not args.uin or args.uin == "?":
        exists = [section for section in cfg.sections() if section != "default"]
        for section in exists:
            print(f" - {magnet}{ul}{section}{reset}")
        args.uin = input(f"{gold}请选择一个账号{reset}: ")
    if args.uin not in cfg:
        print(f"账号 {purple}{ul}{args.uin}{reset} 的相关配置不存在")
        return
    cfg.remove_section(args.uin)
    with (Path.cwd() / CONFIG_FILE).open("w+", encoding="utf-8") as f:
        cfg.write(f)
    print(f"账号 {purple}{ul}{args.uin}{reset} 的配置已删除")


def _run(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        if args.uin and args.uin != "?":
            print(f"请先使用 {yellow}`nekobox gen {args.uin}`{reset} 生成配置文件")
        else:
            print(f"请先使用 {yellow}`nekobox gen`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    uin = args.uin or cfg["default"]["uin"]
    if uin == "?":
        for section in cfg.sections():
            if section == "default":
                continue
            print(f" - {magnet}{ul}{section}{reset}")
        uin = (
            input(f"{gold}请选择一个账号{reset} {cyan}({cfg['default']['uin']}){reset}: ").strip()
            or cfg["default"]["uin"]
        )
    if uin not in cfg:
        print(
            f"账号 {purple}{ul}{uin}{reset} 的相关配置不存在\n请先使用 {yellow}`nekobox gen {uin}`{reset} 生成对应账号的配置文件"
        )
        return
    host = cfg[uin]["host"]
    port = int(cfg[uin]["port"])
    token = cfg[uin]["token"]
    sign_url = cfg[uin]["sign"]
    path = cfg[uin].get("path", "")
    protocol = cfg[uin]["protocol"]
    level = "DEBUG" if args.debug else cfg[uin]["log_level"]
    logger.success("读取配置文件完成")
    run(int(uin), host, port, token, path, protocol, sign_url, level, args.use_png)


def _show(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        print(f"请先使用 {yellow}`nekobox gen {args.uin or ''}`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    if not args.uin or args.uin == "?":
        exists = [section for section in cfg.sections() if section != "default"]
        for section in exists:
            print(f" - {magnet}{ul}{section}{reset}")
        args.uin = (
            input(f"{gold}请选择一个账号{reset} {cyan}({cfg['default']['uin']}){reset}: ")
            or cfg["default"]["uin"]
        )
    if args.uin not in cfg:
        print(f"账号 {purple}{ul}{args.uin}{reset} 的相关配置不存在")
        return
    print(f"{green}SignUrl:        {reset}{cfg[args.uin]['sign']}")
    print(f"{green}协议类型:       {reset}{cfg[args.uin]['protocol']}")
    print(f"{green}验证 token:     {reset}{cfg[args.uin]['token']}")
    print(f"{green}服务器绑定地址: {reset}{cfg[args.uin]['host']}")
    print(f"{green}服务器绑定端口: {reset}{cfg[args.uin]['port']}")
    print(f"{green}服务器部署路径: {reset}{cfg[args.uin].get('path', '')}")
    print(f"{green}默认日志等级:   {reset}{cfg[args.uin]['log_level']}")


def _clear(args):
    if (bots := Path("./bots")).exists():
        if not args.uin:
            res = input(
                f"{gold}即将清理: {green}{bots.resolve()} {gold}下的所有数据，是否继续? {bd}{magnet}[y/n] {cyan}(y): {reset}"
            )
            if res.lower() == "y":
                shutil.rmtree(bots)
                print(f"{green}{bots.resolve()}{reset} 清理完毕")
            return
        if args.uin == "?":
            accounts = [bot.name for bot in bots.iterdir()]
            for index, bot in enumerate(accounts):
                print(f" {index}. {magnet}{ul}{bot}{reset}")
            args.uin = accounts[int(input(f"{gold}请选择一个账号{reset} {cyan}(0){reset}: ").strip() or "0")]
        if (dir_ := (bots / str(args.uin))).exists():
            res = input(
                f"{gold}即将清理: {green}{dir_.resolve()} {gold}下的所有数据，是否继续? {bd}{magnet}[y/n] {cyan}(y): {reset}"
            )
            if res.lower() == "y":
                shutil.rmtree(dir_)
                print(f"{green}{dir_.resolve()}{reset} 数据清理完毕")
        else:
            print(f"{green}{dir_.resolve()}{reset} 不存在")


def _default(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        print(f"请先使用 {yellow}`nekobox gen {args.uin or ''}`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    if not args.uin or args.uin == "?":
        exists = [section for section in cfg.sections() if section != "default"]
        for section in exists:
            print(f" - {magnet}{ul}{section}{reset}")
        args.uin = input(f"{gold}请选择一个账号{reset}: ")
    if args.uin not in cfg:
        print(f"账号 {purple}{ul}{args.uin}{reset} 的相关配置不存在")
        return
    cfg.set("default", "uin", args.uin)
    with (Path.cwd() / CONFIG_FILE).open("w+", encoding="utf-8") as f:
        cfg.write(f)
    print(f"默认账号已设置为 {purple}{ul}{args.uin}{reset}")


def _list(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        print(f"请先使用 {yellow}`nekobox gen {args.uin or ''}`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    print(f"{cyan}当前配置文件中的账号有:{reset}")
    for section in cfg.sections():
        if section == "default":
            continue
        print(f" - {magnet}{ul}{section}{reset}")


def main():
    parser = ArgumentParser(description=f"{cyan}NekoBox/lagrange-python-satori Server 工具{reset}")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    command = parser.add_subparsers(dest="command", title=f"commands")
    run_parser = command.add_parser("run", help="启动服务器")
    run_parser.add_argument("uin", type=str, nargs="?", help="选择账号; 输入 '?' 以交互式选择账号")
    run_parser.add_argument("--debug", action="store_true", default=False, help="强制启用调试等级日志")
    run_parser.add_argument("--file-qrcode", "-Q", dest="use_png", action="store_true", default=False, help="使用文件保存二维码")
    run_parser.set_defaults(func=_run)
    gen_parser = command.add_parser("gen", help="生成或更新配置文件")
    gen_parser.add_argument("uin", type=str, nargs="?", help="选择账号")
    gen_parser.set_defaults(func=generate_cfg)
    list_parser = command.add_parser("list", help="列出所有账号")
    list_parser.set_defaults(func=_list)
    show_parser = command.add_parser("show", help="显示账号配置")
    show_parser.add_argument("uin", type=str, nargs="?", help="选择账号; 输入 '?' 以交互式选择账号")
    show_parser.set_defaults(func=_show)
    clean_parser = command.add_parser("clear", help="清除数据")
    clean_parser.add_argument("uin", type=str, nargs="?", help="选择账号; 输入 '?' 以交互式选择账号")
    clean_parser.set_defaults(func=_clear)
    delete_parser = command.add_parser("delete", help="删除账号配置")
    delete_parser.add_argument("uin", type=str, nargs="?", help="选择账号; 输入 '?' 以交互式选择账号")
    delete_parser.set_defaults(func=_delete)
    default_parser = command.add_parser("default", help="设置默认账号")
    default_parser.add_argument("uin", type=str, nargs="?", help="选择账号")
    default_parser.set_defaults(func=_default)

    args = parser.parse_args()

    try:
        if args.command:
            args.func(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print(f"\n{red}运行已中断。{reset}")


if __name__ == "__main__":
    main()
