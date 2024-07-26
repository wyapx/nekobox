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
ul = "\033[4m"
bd = "\033[1m"


def run(uin: int, host: str, port: int, token: str, protocol: str, sign_url: str, level: str):
    loop = it(asyncio.AbstractEventLoop)
    loop.set_exception_handler(loguru_exc_callback_async)
    server = Server(host=host, port=port)
    server.apply(NekoBoxAdapter(uin, token, sign_url, protocol, level))  # type: ignore
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
            input(f"{description}{f' {cyan}({default}){reset}' if default else f' {cyan}(必填项){reset}'}: ")
        )
        if not i:
            if not default:
                raise ValueError
            else:
                i = default
        if i and unique and i not in unique:
            raise ValueError
        cfg.set(section, option, i)
        return i
    except (TypeError, ValueError):
        print(f">>> 输入不符合约束: {green}{unique}{reset}")
        return set_cfg(cfg, section, option, description, default, unique)  # type: ignore


def generate_cfg(args):
    cfg = ConfigParser()
    if (Path.cwd() / CONFIG_FILE).exists():
        cfg.read(CONFIG_FILE, encoding="utf-8")
    print(f"{cyan}正在生成配置文件...{reset}")
    uin = args.uin
    if not uin:
        uin = set_cfg(cfg, "default", "uin", "Bot 的 QQ 号")
    cfg.add_section(uin)
    set_cfg(cfg, uin, "sign", "Bot 的 SignUrl")
    set_cfg(cfg, uin, "protocol", "Bot 的协议类型", default="linux", unique=["linux", "macos", "windows"])
    set_cfg(cfg, uin, "token", "Satori 的验证 token", default=secrets.token_hex(8))
    set_cfg(cfg, uin, "host", "Satori 服务器绑定地址", default="127.0.0.1")
    set_cfg(cfg, uin, "port", "Satori 服务器绑定端口", default="7777")
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


def _run(args):
    if not (Path.cwd() / CONFIG_FILE).exists():
        print(f"请先使用 {yellow}`nekobox gen {args.uin or ''}`{reset} 生成配置文件")
        return
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    uin = args.uin or cfg["default"]["uin"]
    if uin not in cfg:
        print(
            f"账号 {purple}{ul}{uin}{reset} 的相关配置不存在\n请先使用 {yellow}`nekobox gen {uin}`{reset} 生成对应账号的配置文件"
        )
        return
    host = cfg[uin]["host"]
    port = int(cfg[uin]["port"])
    token = cfg[uin]["token"]
    sign_url = cfg[uin]["sign"]
    protocol = cfg[uin]["protocol"]
    level = cfg[uin]["log_level"]
    logger.debug("读取配置文件完成")
    run(int(uin), host, port, token, protocol, sign_url, level)


def _clear(args):
    if (bots := Path("./bots")).exists():
        if not args.uin:
            res = input(
                f"{gold}即将清理: {green}{bots.resolve()} {gold}下的所有数据，是否继续? {bd}{magnet}[y/n] {cyan}(y): {reset}"
            )
            if res.lower() == "y":
                shutil.rmtree(bots)
                print(f"{green}{bots.resolve()}{reset} 清理完毕")
        elif (dir_ := (bots / str(args.uin))).exists():
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
    cfg.set("default", "uin", args.uin)
    with (Path.cwd() / CONFIG_FILE).open("w+", encoding="utf-8") as f:
        cfg.write(f)
    print(f"默认账号已设置为 {purple}{ul}{args.uin}{reset}")


def main():
    parser = ArgumentParser(description=f"{cyan}NekoBox/lagrange-python-satori Server 工具{reset}")
    command = parser.add_subparsers(dest="command", title=f"commands")
    run_parser = command.add_parser("run", help="启动服务器")
    run_parser.add_argument("uin", type=str, nargs="?", help="选择账号")
    run_parser.set_defaults(func=_run)
    gen_parser = command.add_parser("gen", help="生成配置文件")
    gen_parser.add_argument("uin", type=str, nargs="?", help="选择账号")
    gen_parser.set_defaults(func=generate_cfg)
    clean_parser = command.add_parser("clear", help="清除数据")
    clean_parser.add_argument("uin", type=str, nargs="?", help="选择账号")
    clean_parser.set_defaults(func=_clear)
    default_parser = command.add_parser("default", help="设置默认账号")
    default_parser.add_argument("uin", type=str, help="选择账号")
    default_parser.set_defaults(func=_default)
    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
