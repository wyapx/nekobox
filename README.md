# NekoBox  

基于 [`lagrange-python`](https://github.com/LagrangeDev/lagrange-python) 的
[`Satori协议`](https://satori.js.org/zh-CN) 实现，使用 [`satori-python`](https://github.com/RF-Tar-Railt/satori-python)


## 如何启动

```shell
# 安装环境
git clone https://github.com/wyapx/nekobox
cd nekobox

python -m pip install .

# 可选依赖，用于支持非silk格式audio发送
python -m pip install pysilk-mod

# 跟随步骤生成配置文件后，使用手Q扫码即可登录
python -m nekobox run
```

使用 `PDM`:

```shell
# 安装环境
git clone https://github.com/wyapx/nekobox
cd nekobox

pdm install

# 可选依赖，用于支持非silk格式audio发送
pdm sync --group audio

# 跟随步骤生成配置文件后，使用手Q扫码即可登录
pdm run nekobox run
```

## CLI 工具

```shell
$ nekobox
usage: nekobox [-h] {run,gen,clear,default} ...

NekoBox/lagrange-python-satori Server 工具

options:
  -h, --help            show this help message and exit

commands:
  {run,gen,clear,default}
    run                 启动服务器
    gen                 生成配置文件
    clear               清除数据
    default             设置默认账号
```


## 特性支持情况

1. 消息类型  
   - [x] Text
   - [x] At, AtAll
   - [x] Image
   - [x] Quote
   - [x] Audio

2. 主动操作
   - [x] message-create
   - [x] message-delete `部分支持：群聊`
   - [x] message-get `部分支持：群聊`
   - [x] guild-member-kick
   - [x] guild-member-mute
   - [x] guild-member-get
   - [x] guild-member-list
   - [x] guild-list
   - [x] channel-list
   - [x] login-get
   - [x] user-channel-create `用于向 user 发起私聊 (前提是好友)`
   - [x] guild-member-approve
   - [x] friend-list
   - [x] reaction-create
   - [x] reaction-delete
   - [x] reaction-clear

3. 事件
   - [x] message-created
   - [x] message-deleted  `部分支持：群聊`
   - [x] guild-member-added
   - [x] guild-member-removed
   - [x] guild-updated  `群名更改`
   - [x] guild-member-request

由于大多数事件和操作没有标准参考，特性的新增可能需要一些时间.
