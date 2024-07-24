import asyncio
import os
import secrets

from configparser import ConfigParser
from creart import it
from satori.server import Server
from loguru import logger
from nekobox.log import loguru_exc_callback_async
from nekobox.main import NekoBoxAdapter


CONFIG_FILE = 'nekobox.ini'


def run(uin: int, host: str, port: int, token: str, protocol: str, sign_url: str, level: str):
    loop = it(asyncio.AbstractEventLoop)
    loop.set_exception_handler(loguru_exc_callback_async)
    server = Server(host=host, port=port)
    server.apply(NekoBoxAdapter(uin, token, sign_url, protocol, level))   # type: ignore
    server.run()


def set_cfg(cfg: ConfigParser, section: str, option: str, description: str, default=None, unique=None):
    if not unique:
        unique = []
    try:
        i = str(input(f">>> {description}{f'[{default}]' if default else '*'}: "))
        if not i and not default:
            raise ValueError
        elif i and unique and i not in unique:
            raise ValueError
    except (TypeError, ValueError):
        logger.error(f"输入不符合约束: {unique}")
        return set_cfg(cfg, section, option, description, default, unique)
    cfg.set(section, option, i or default)


def generate_cfg():
    cfg = ConfigParser()
    logger.info("正在生成配置文件...")
    cfg.add_section("Core")
    set_cfg(cfg, "Core", "uin", "Bot的QQ号")
    set_cfg(cfg, "Core", "sign", "Bot的Sign服务器地址(HTTP)")
    set_cfg(cfg, "Core", "protocol", "Bot的协议类型", default="linux", unique=["linux", "macos", "windows"])
    set_cfg(cfg, "Core", "token", "Satori的验证token（不输入则随机生成）", default=secrets.token_hex(8))
    set_cfg(cfg, "Core", "host", "Satori服务器绑定地址", default="127.0.0.1")
    set_cfg(cfg, "Core", "port", "Satori服务器绑定端口", default="7777")
    set_cfg(cfg, "Core", "log_level", "默认日志等级", default="INFO", unique=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)
    logger.success("配置文件已保存")


def main():
    if not os.path.isfile(CONFIG_FILE):
        logger.warning("配置文件不存在")
        generate_cfg()
    cfg = ConfigParser()
    cfg.read(CONFIG_FILE)
    logger.debug("读取配置文件完成")
    uin = int(cfg["Core"]["uin"])
    host = cfg["Core"]["host"]
    port = int(cfg["Core"]["port"])
    token = cfg["Core"]["token"]
    sign_url = cfg["Core"]["sign"]
    protocol = cfg["Core"]["protocol"]
    level = cfg["Core"]["log_level"]
    run(uin, host, port, token, protocol, sign_url, level)


if __name__ == '__main__':
    main()
