#!/bin/bash
# ============================================================
# Raspberry Pi ミニキーボードプロジェクト セットアップスクリプト
#
# まっさらなラズパイで以下を実行:
#   chmod +x setup.sh && sudo ./setup.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# USER_NAME: sudoで実行された場合は SUDO_USER、そうでなければ現在のユーザー
USER_NAME="${SUDO_USER:-$(whoami)}"
USER_HOME=$(eval echo "~$USER_NAME")

echo "============================================================"
echo " ミニキーボードプロジェクト セットアップ"
echo "============================================================"
echo "プロジェクトディレクトリ: $SCRIPT_DIR"
echo "ユーザー: $USER_NAME"
echo ""

# ------ 1. システムパッケージのインストール ------
echo "--- 1/6: システムパッケージのインストール ---"
apt-get update
apt-get install -y \
    python3-pip \
    python3-venv \
    ffmpeg \
    alsa-utils \
    pulseaudio \
    libsdl2-mixer-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-ttf-2.0-0 \
    megatools
echo "✓ システムパッケージ完了"
echo ""

# ------ 2. Python パッケージのインストール ------
echo "--- 2/6: Python パッケージのインストール ---"
pip3 install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null || \
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
echo "✓ Python パッケージ完了"
echo ""

# ------ 3. ディレクトリ構造の作成 ------
echo "--- 3/6: ディレクトリ構造の作成 ---"
mkdir -p "$SCRIPT_DIR/audio/direction"
mkdir -p "$SCRIPT_DIR/audio/bird_names"
mkdir -p "$SCRIPT_DIR/audio/bird_songs"
mkdir -p "$SCRIPT_DIR/cache/fan_messages/names"
mkdir -p "$SCRIPT_DIR/cache/fan_messages/messages"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/mukashimukashi/titles"
chown -R "$USER_NAME:$USER_NAME" "$SCRIPT_DIR/audio" "$SCRIPT_DIR/cache" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/mukashimukashi"
echo "✓ ディレクトリ構造完了"
echo ""

# ------ 4. .env ファイルの確認 ------
echo "--- 4/6: 環境変数ファイルの確認 ---"
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    chown "$USER_NAME:$USER_NAME" "$SCRIPT_DIR/.env"
    echo "⚠️  .env ファイルを .env.example からコピーしました。"
    echo "   各APIキーや設定値を編集してください:"
    echo "   nano $SCRIPT_DIR/.env"
else
    echo "✓ .env ファイルは既に存在します"
fi
echo ""

# ------ 5. systemd サービスの設定 ------
echo "--- 5/6: systemd サービスの設定 ---"
SERVICE_FILE="$SCRIPT_DIR/mukashimukashi.service"

# サービスファイル内のパスとユーザーを現在の環境に合わせて更新
sed -i "s|User=.*|User=$USER_NAME|" "$SERVICE_FILE"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$SCRIPT_DIR|" "$SERVICE_FILE"
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $SCRIPT_DIR/keyboard_test_v2.py|" "$SERVICE_FILE"

# UID を取得して XDG_RUNTIME_DIR を設定
USER_UID=$(id -u "$USER_NAME")
sed -i "s|Environment=XDG_RUNTIME_DIR=.*|Environment=XDG_RUNTIME_DIR=/run/user/$USER_UID|" "$SERVICE_FILE"
sed -i "s|Environment=PULSE_RUNTIME_PATH=.*|Environment=PULSE_RUNTIME_PATH=/run/user/$USER_UID/pulse|" "$SERVICE_FILE"

cp "$SERVICE_FILE" /etc/systemd/system/mukashimukashi.service
systemctl daemon-reload
systemctl enable mukashimukashi.service
echo "✓ サービス登録完了（自動起動ON）"
echo ""

# ------ 6. 音声ファイルの生成 ------
echo "--- 6/6: UI音声ファイルの生成 ---"
if [ -f "$SCRIPT_DIR/.env" ] && grep -q "AWS_ACCESS_KEY_ID" "$SCRIPT_DIR/.env" 2>/dev/null; then
    echo "AWS認証情報が .env にあります。音声ファイルを生成します..."
    sudo -u "$USER_NAME" python3 "$SCRIPT_DIR/generate_ui_audio.py"
else
    echo "⚠️  AWS認証情報が .env にありません。"
    echo "   .env に AWS_ACCESS_KEY_ID と AWS_SECRET_ACCESS_KEY を設定してから"
    echo "   以下を実行してください:"
    echo "   python3 $SCRIPT_DIR/generate_ui_audio.py"
fi
echo ""

# ------ 完了 ------
echo "============================================================"
echo " セットアップ完了！"
echo "============================================================"
echo ""
echo "次のステップ:"
echo "  1. .env を編集して各APIキーを設定"
echo "     nano $SCRIPT_DIR/.env"
echo ""
echo "  2. 音声ファイルを生成（まだの場合）"
echo "     python3 $SCRIPT_DIR/generate_ui_audio.py"
echo "     python3 $SCRIPT_DIR/generate_titles.py"
echo ""
echo "  3. サービスを開始"
echo "     sudo systemctl start mukashimukashi.service"
echo ""
echo "  4. ログ確認"
echo "     journalctl -u mukashimukashi.service -f"
echo ""
