# Raspberry Pi Audio & Mini Keyboard Project

## 1. プロジェクト概要 (Overview)
本プロジェクトは、Raspberry Piを使用した**音声再生・録音・ブログ投稿機能付きのインタラクティブ・デバイス**（ミニキーボードシステム）の制御ソフトウェアです。
Pythonと各種クラウドAPI（AWS, OpenAI, Render, GAS）を組み合わせ、ロータリーエンコーダとキーボード操作による直感的なUIを提供します。

### 主な機能
- **「むかしむかし」物語再生:** GitHub管理のオーディオブック（.m4a）をストリーミング再生します。
- **ファンメッセージ機能:** Google Apps Script (GAS) 経由でメッセージを取得し、AWS Pollyで音声合成して読み上げます。
- **音声ブログ投稿:** マイクで音声を録音し、OpenAI Whisperでテキスト化。Render上のAPIを経由してエキサイトブログに自動投稿します。
- **ハードウェア制御:** USB入力デバイス（ミニキーボード）のキーとつまみ（ロータリーエンコーダ）を使用してメニュー操作や音量制御を行います。

---

## 2. ファイル構成図 (File Structure)
```
mini_keyboard/
├── keyboard_test_v2.py          # ★メインスクリプト（本番稼働用）
├── keyboard_test_v2_with_blog.py # 開発中/テスト用バリエーション
│
├── [モジュール]
├── blog_poster.py               # ブログ投稿モジュール（Render API連携）
├── fan_messages.py              # ファンメッセージ取得モジュール（GAS連携）
├── voice_to_text.py             # 音声認識モジュール（OpenAI Whisper API）
├── podcast_player.py            # ポッドキャスト再生モジュール
│
├── [ユーティリティ]
├── generate_ui_audio.py         # UI音声一括生成（Polly）
├── generate_titles.py           # 物語タイトル音声生成（Polly）
├── generate_fan_message_audio.py # メッセージ音声生成バッチ（cron用）
├── prepare_bird_audio.py        # 鳥の鳴き声データ準備
├── audio_test.py                # オーディオ診断ツール
├── play_audio.py                # 単体WAV再生ユーティリティ
│
├── [設定]
├── .env.example                 # 環境変数テンプレート
├── .env                         # [必須] 環境変数設定ファイル
├── mukashimukashi.service       # systemd サービス定義
├── bird_songs.json              # 鳥データ定義
├── podcast_channels.json        # ポッドキャストチャンネル定義
│
├── [音声ファイル]
├── audio/                       # UI操作音・効果音（.wav）
│   ├── menu_*.wav               # メニュー音声
│   ├── beep.wav, kettei.wav     # UI効果音
│   ├── blog_*.wav               # ブログ関連音声
│   ├── bird_songs/              # 鳥の鳴き声WAV
│   ├── bird_names/              # 鳥の名前読み上げWAV
│   └── direction/               # 方角読み上げWAV
│
├── cache/                       # キャッシュ
│   └── fan_messages/            # ファンメッセージ音声キャッシュ
│       ├── names/               # 送信者名WAV
│       └── messages/            # メッセージ本文WAV
│
└── mukashimukashi/              # 物語コンテンツ
    └── titles/                  # タイトル読み上げ用音声
```

---

## 3. 各ファイルの役割詳細 (File Descriptions)

### コアシステム
| ファイル名 | 役割 |
| :--- | :--- |
| **keyboard_test_v2.py** | **[メイン]** システムの中核。`evdev` で入力を監視し、メニュー操作、音声再生、録音、ブログ投稿フローを統括します。 |
| `keyboard_test_v2_with_blog.py` | メインスクリプトの派生版。ブログ投稿機能のテスト実装などが含まれます（通常はv2を使用）。 |

### モジュール・ライブラリ
| ファイル名 | 役割 |
| :--- | :--- |
| `blog_poster.py` | ブログ投稿ロジックを担当。`alexa-blog-poster.onrender.com` に対してPOSTリクエストを送信します。 |
| `fan_messages.py` | ファンメッセージのデータソース（GAS）へのアクセスと、ローカルキャッシュの管理を行います。 |
| `voice_to_text.py` | `OpenAI` クライアントを使用し、ローカルの `.wav` ファイルをテキストに変換します。 |
| `podcast_player.py` | ポッドキャスト再生モジュール。RSSフィードからエピソードを取得し ffplay で再生します。 |

### ユーティリティ・バッチ
| ファイル名 | 役割 |
| :--- | :--- |
| `generate_ui_audio.py` | AWS Pollyを使ってUI音声（メニュー、効果音、ブログ関連、通知、方角）を一括生成します。 |
| `generate_titles.py` | GitHub上の物語ファイルリストを取得し、AWS Pollyを使ってタイトル読み上げ音声を一括生成します。 |
| `generate_fan_message_audio.py` | 新着ファンメッセージを定期チェックし、音声ファイル化して保存します（通常cronで実行）。 |
| `prepare_bird_audio.py` | 鳥の鳴き声MP3をダウンロードしてWAVに変換し、鳥名読み上げ音声も生成します。 |
| `audio_test.py` | オーディオ再生の総合診断ツール。デバイス/PulseAudio/ALSA/pygameを順にテストします。 |

---

## 4. サービスと依存関係 (Service & Dependencies)

### 外部サービス依存
本システムは正常動作のために以下のAPIキー・設定が必要です（`.env` に記述）。

- **OpenAI API:** Whisperモデルによる音声認識 (`OPENAI_API_KEY`)
- **AWS Polly:** "Takumi" 音声による読み上げ (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- **Google Apps Script (GAS):** ファンメッセージデータソース (`GAS_URL`)
- **Render (Custom API):** ブログ投稿用ブリッジAPI (Endpoint URL)

### 自動起動設定 (Systemd)
本環境では以下のサービスとして登録・稼働しています。

- **サービス名:** `mukashimukashi.service`
- **定義ファイル:** `/etc/systemd/system/mukashimukashi.service`
- **実行コマンド:** `/usr/bin/python3 /home/yasutoshi/projects/06.mini_keyboard/keyboard_test_v2.py`

管理コマンド例：
```bash
# ステータス確認（Tailscale MagicDNS ホスト名を使用）
ssh yasutoshi@raspberrypi-1 "systemctl status mukashimukashi.service"

# ログ確認
ssh yasutoshi@raspberrypi-1 "journalctl -u mukashimukashi.service -f"

# 再起動
ssh yasutoshi@raspberrypi-1 "sudo systemctl restart mukashimukashi.service"
```

---

## 7. 操作方法 (Hardware Operation)

ミニキーボードのキー割り当ては以下の通りです。

| ボタン | キーコード | 機能 |
| :--- | :--- | :--- |
| **つまみ回転** | `VOLUP/DOWN` | メニューの選択・移動 |
| **つまみ押し** | `MUTE` | **[決定]** 選択した項目の実行 |
| **ボタン 1** | `UP` | **[戻る]** 一つ前の画面に戻る / 再生停止 |
| **ボタン 2** | `LEFT` | **音量 DOWN** (押しっぱなしで連続調整) |
| **ボタン 3** | `DOWN` | **音量 UP** (押しっぱなし) / **再起動** (5秒長押し) |
| **ボタン 4** | `RIGHT` | (故障中につき無効化) |

> [!IMPORTANT]
> **ボタン4の物理的な故障に伴う変更 (2026/01/17):**
> 元々ボタン4に割り当てられていた「音量UP」機能を、ボタン3へ移行しました。ボタン3は「音量UP」と「5秒長押しによる再起動」の両方の機能を受け持ちます。

## 5. オーディオ自動検出とセットアップ (Audio Auto-Detection & Setup)

### 5.1 自動検出の仕組み

起動時に `detect_audio_devices()` が `aplay -l` / `arecord -l` を解析し、USBオーディオデバイスを自動検出する。

```
起動時
  │
  ├─ .env の SPEAKER_CARD / MIC_CARD を確認
  │     ├─ 数値指定 → そのカード番号を使用
  │     └─ "auto"  → 自動検出へ
  │
  ├─ aplay -l / arecord -l を実行
  │     └─ 出力をパースしてカード番号を抽出
  │
  ├─ 内蔵オーディオを除外（bcm2835, vc4, hdmi）
  │     └─ 残ったUSBデバイスを選択
  │
  └─ 検出結果を表示
        🔊 スピーカー: hw:2,0 (自動検出)
        🎤 マイク: hw:3,0 (自動検出)
```

`.env` での設定：

```bash
# USBデバイスを自動検出（推奨）
SPEAKER_CARD=auto
MIC_CARD=auto

# 手動で指定する場合（aplay -l でカード番号を確認）
SPEAKER_CARD=2
MIC_CARD=3
```

USBスピーカーを差し替えても `auto` であれば再起動時に新しいデバイスを自動検出する。

### 5.2 オーディオドライバーの優先順位

pygame 初期化時に以下の順で試行する：

1. **PulseAudio**（`SDL_AUDIODRIVER=pulseaudio`）← 推奨
2. **ALSA フォールバック**（`SDL_AUDIODRIVER=alsa`）
   - `plug:dmixed` → `plughw:{card},0` → `hw:{card},0` → `default`

systemd サービスから PulseAudio に接続するため、サービスファイルに以下の環境変数が必要：

```ini
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=PULSE_RUNTIME_PATH=/run/user/1000/pulse
```

### 5.3 再生方式

| 種別 | 方式 | 用途 |
|------|------|------|
| WAV ファイル | pygame.mixer.Sound | メニュー音声、効果音、ファンメッセージ |
| ストリーミング | ffplay (subprocess) | むかしむかし、ポッドキャスト |
| 録音 | arecord (subprocess) | ブログ投稿の音声入力 |

すべての音声再生は `SequentialAudioManager` のキューを通じて管理される：
- キューの最大待ち数: 2
- `urgent=True` で現在の再生を中断して割り込み再生
- 再生完了時のコールバック対応
- pygame チャンネル数: 16（同時再生用）

### 5.4 音声ファイルの準備

音声ファイルは `audio/` ディレクトリに配置する。

**既存環境からコピーする場合（Tailscale経由）：**

```bash
# -z は使わない（WAVは非圧縮なのでCPU負荷が増えるだけで逆効果）
# jikka-pi3 = 旧ラズパイ（Tailscale MagicDNS）
rsync -av yasutoshi@jikka-pi3:~/mini_keyboard/audio/ ~/mini_keyboard/audio/
rsync -av yasutoshi@jikka-pi3:~/mini_keyboard/cache/ ~/mini_keyboard/cache/
```

> **Note:** `-z`（圧縮）を付けるとラズパイのCPUがボトルネックになり大幅に遅くなる。
> Tailscale MagicDNS でホスト名 `jikka-pi3` から直接アクセス可能。

**ゼロから生成する場合（AWS Pollyが必要）：**

```bash
python3 generate_ui_audio.py    # UI音声（メニュー、効果音、ブログ関連等）
python3 prepare_bird_audio.py   # 鳥の鳴き声データ
```

### 5.5 新しいUSBスピーカーを接続した場合

```bash
# 1. デバイス認識を確認
aplay -l

# 2. PulseAudio/PipeWire のシンク確認
pactl list sinks short

# 3. デフォルトシンクを設定（sink名は Step 2 の出力から）
pactl set-default-sink <sink名>

# 4. ミュート解除と音量設定
pactl set-sink-mute @DEFAULT_SINK@ 0
pactl set-sink-volume @DEFAULT_SINK@ 50%

# 5. テストトーン
speaker-test -t sine -l 1 -p 2

# 6. WAV ファイルで確認
aplay ~/projects/06.mini_keyboard/audio/beep.wav

# 7. 総合テスト（ALSA / pygame 両方をチェック）
python3 audio_test.py
```

### 5.6 音量設定

| 変数 | デフォルト | 説明 |
|------|----------|------|
| `MIN_VOLUME` | `15` | 音量下限（%）。これ以下には下がらない |
| `DIRECTION_VOLUME` | `100` | 方角通知時の割り込み音量（%） |
| `DIRECTION_BOOST` | `4.0` | 方角音声のソフトウェアブースト倍率 |

音量制御は `amixer -c {SPEAKER_CARD} sset PCM {volume}%` で行う。ボタン長押しで5%刻みで調整。

### 5.7 トラブルシューティング

| 症状 | 確認ポイント |
|------|------------|
| 音が出ない | `pactl list sinks short` でシンクが表示されるか確認 |
| 音が出ない | `pactl get-sink-mute @DEFAULT_SINK@` でミュート状態を確認 |
| 音が出ない | `pactl get-sink-volume @DEFAULT_SINK@` で音量を確認 |
| デバイスが見つからない | USBケーブルを挿し直して `aplay -l` で再確認 |
| pygame初期化エラー | `XDG_RUNTIME_DIR` が設定されているか確認（systemd時に必要） |
| systemdで音が出ない | サービスファイルの `Environment=XDG_RUNTIME_DIR` を確認 |
| monoデバイス | `pactl list sinks short` で stereo/mono を確認。mono-fallback の場合はデバイス相性の問題 |

### 5.8 audio_test.py 診断ツール

`python3 audio_test.py` で以下を自動チェック：

1. オーディオデバイス一覧（`aplay -l`）
2. PulseAudio 動作状態
3. ALSA ミキサー音量
4. 音声ファイルの存在確認
5. ALSA 直接再生テスト（`speaker-test`）
6. `aplay` による WAV 再生テスト
7. pygame.mixer 初期化 & 再生テスト
8. keyboard_test プロセスの重複確認

---

## 6. 必要なライブラリ (Required Libraries)

以下のPythonパッケージが必要です。

**Input / UI:**
- `evdev`: キーボード・ロータリーエンコーダ入力の取得
- `pygame`: SE再生、オーディオミキサー制御

**Network / API:**
- `requests`: HTTP通信
- `python-dotenv`: 環境変数管理
- `boto3`: AWS Polly操作
- `openai`: Whisper API操作
- `beautifulsoup4`: HTML解析（`blog_poster.py`で使用）

**System Tools:**
- `ffmpeg` / `ffplay`: 音声変換・ストリーミング再生
- `alsa-utils`: 音量制御 (`amixer`コマンド)

---

## 8. 方角通知 API (Direction Notification API)

Flask サーバー（ポート5000）が HTTP API を提供する。
外部デバイスから方角を POST すると、現在の再生を一時停止して方角を読み上げる。

```bash
curl -X POST http://localhost:5000/direction \
  -H "Content-Type: application/json" \
  -d '{"dir": "north"}'
```

対応方角: `north`, `east`, `south`, `west`

通知時の動作：
1. 再生中の全チャンネルを一時停止
2. 音量を `DIRECTION_VOLUME` に引き上げ
3. 方角音声を再生（`DIRECTION_BOOST` 倍でソフトウェアブースト済み）
4. 再生完了後、音量を元に戻し、一時停止していたチャンネルを再開

---

## 9. 運用ルール (Maintenance Rules)

プロジェクトの継続的な改善と追跡可能性を維持するため、以下のルールを適用します。

### AI エージェント用開発ルール (AI Agent Rules)
本プロジェクトに携わる AI エージェントは、作業を開始する前に以下の手順を厳守してください。

1. **「実行」前の説明と合意**:
   - 修正、機能追加、または Git へのプッシュを行う際は、必ず事前に **「現在の状況・原因の分析」** と **「具体的な修正案」** をユーザーに提示してください。
   - ユーザーから **明確な承認（「OK」「やってよし」等）を得るまで** は、ファイルの書き換えやコマンドの実行を行わないでください。
2. **履歴の継承**:
   - `README.md` の運用ルールと `CHANGELOG.md` を読み、これまでの開発の文脈と、履歴管理のルール（ハッシュの記載等）を正しく把握してください。
3. **デグレードの防止**:
   - 既存の機能（特に音声再生の排他制御やモード遷移）を損なわないよう、変更範囲のコードを慎重に確認し、不明点がある場合は必ず質問してください。

### 変更管理 (Change Management)
- **CHANGELOG.md の更新**: 機能追加、改善、バグ修正を行った際は、セッションの最後に必ず [CHANGELOG.md](CHANGELOG.md) を更新します。
- **Git との紐付け**: 各変更点には、対応する Git の短縮コミットハッシュ（例: `9fbe415`）を併記し、コードの変更履歴とドキュメントを一致させます。
- **ユーザー目線の記述**: 変更内容は、技術的な詳細だけでなく「ユーザーにとって何が変わったか」を明快に記述します。

### 開発フロー
1.  新しい機能や修正の実装。
2.  検証（実機またはシミュレーション）。
3.  Git へのコミット & プッシュ。
4.  コミットハッシュを確認し、`CHANGELOG.md` へ追記。
5.  完了報告。
