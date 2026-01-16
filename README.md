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
/home/yasutoshi/projects/06.mini_keyboard/
├── audio/                      # UI操作音（.wav）
├── cache/                      # キャッシュディレクトリ（ファンメッセージ音声等）
├── logs/                       # ログ出力先
├── mukashimukashi/             # 物語コンテンツ用ディレクトリ
│   └── titles/                 # タイトル読み上げ用音声ファイル
├── .env                        # [必須] 環境変数設定ファイル（APIキー等）
├── .env.example                # 環境変数テンプレート
├── README.md                   # 本ドキュメント
│
├── [Main System]
├── keyboard_test_v2.py         # ★メインスクリプト（本番稼働用）
├── keyboard_test_v2_with_blog.py # 開発中/テスト用バリエーション
│
├── [Modules]
├── blog_poster.py              # ブログ投稿モジュール（Render API連携）
├── fan_messages.py             # ファンメッセージ取得モジュール（GAS連携）
├── voice_to_text.py            # 音声認識モジュール（OpenAI Whisper API Wrapper）
│
└── [Utilities & Tools]
    ├── generate_titles.py      # 物語タイトル音声生成（AWS Polly使用）
    ├── generate_fan_message_audio.py # メッセージ音声生成バッチ（cron定期実行用）
    ├── test_knob.py            # 入力デバイス動作テスト
    ├── test_polly_pi4.py       # 音声合成動作テスト
    └── play_audio.py           # 音声再生ユーティリティ
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

### ユーティリティ・バッチ
| ファイル名 | 役割 |
| :--- | :--- |
| `generate_titles.py` | GitHub上の物語ファイルリストを取得し、AWS Pollyを使ってタイトル読み上げ音声を一括生成します。 |
| `generate_fan_message_audio.py` | 新着ファンメッセージを定期チェックし、音声ファイル化して保存します（通常cronで実行）。 |

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
# ステータス確認
ssh yasutoshi@192.168.4.118 "systemctl status mukashimukashi.service"

# ログ確認
ssh yasutoshi@192.168.4.118 "journalctl -u mukashimukashi.service -f"

# 再起動
ssh yasutoshi@192.168.4.118 "sudo systemctl restart mukashimukashi.service"
```

---

## 6. 操作方法 (Hardware Operation)

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

## 5. 必要なライブラリ (Required Libraries)
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
