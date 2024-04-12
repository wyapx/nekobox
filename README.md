# NekoBox  

基于lagrange-python的satori协议实现


## 如何启动

```shell
# 安装环境
git clone https://github.com/wyapx/nekobox
cd nekobox

python -m pip install .

# 可选依赖，用于控制台渲染登录二维码
python -m pip install qrcode
# 可选依赖，用于支持非silk格式audio发送
python -m pip install pysilk-mod

# 跟随步骤生成配置文件后，使用手Q扫码即可登录
python main.py
```

## 特性支持情况

1. 消息类型  
   - [x] Text
   - [x] At
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
   - [x] guild-list
   - [x] guild-member-list

3. 事件
   - [x] message-created
   - [x] message-deleted  `部分支持：群聊`
   - [x] guild-member-added
   - [x] guild-member-removed

由于大多数事件和操作没有标准参考，特性的新增可能需要一些时间.
