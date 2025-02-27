# Tea-Fi-Bot

## 安装说明

### 1. 安装系统依赖

打开终端，运行以下命令：

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip git -y
```

### 2. 克隆GitHub仓库

选择一个目录（如 `/home/你的用户名/tea-fi-autocheck`），然后运行以下命令：

```bash
mkdir -p /home/你的用户名/tea-fi-autocheck
cd /home/你的用户名/tea-fi-autocheck
git clone https://github.com/你的用户名/tea-fi-autocheck.git .
```

注意末尾的 `.` 表示克隆到当前目录。

### 3. 创建虚拟环境

确保独立安装，不影响其他脚本，运行以下命令：

```bash
python3 -m venv venv
```

### 4. 激活虚拟环境

运行以下命令激活虚拟环境：

```bash
source venv/bin/activate
```

### 5. 安装依赖项

运行以下命令安装依赖项：

```bash
pip3 install -r requirements.txt
```

### 6. 编辑配置文件

打开 `wallet_address.txt` 和 `proxy.txt`，填入你的EVM地址和代理：

编辑 `wallet_address.txt` 文件：

```bash
nano wallet_address.txt
```

输入地址（如 `0xa3dfd1f30Bb82230e8c876D3f294deB98B917F16`），每行一个，保存（`Ctrl+O`，然后 `Enter`，`Ctrl+X` 退出）。

编辑 `proxy.txt` 文件：

```bash
nano proxy.txt
```

输入代理（如 `http://127.0.0.1:10809`），每行一个，保存。

### 7. 运行脚本

运行以下命令以执行脚本：

```bash
python3 main.py
```

查看 `log.txt` 记录结果。

### 8. 退出虚拟环境

运行以下命令退出虚拟环境：

```bash
deactivate
```