#!/bin/bash
# podcast.xmlをGitHubに直接プッシュ

REPO_URL="git@github.com:HisakoJP/mukashimukashi.git"
BRANCH="main"
FILE="podcast.xml"

# 一時ディレクトリ作成
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# リポジトリをクローン（shallow clone）
git clone --depth=1 --single-branch --branch="$BRANCH" "$REPO_URL" .

# podcast.xmlをコピー
cp ~/projects/07.podcast/podcast.xml .

# コミット＆プッシュ
git add podcast.xml
git commit -m "🎙️ ポッドキャスト更新 $(date '+%Y-%m-%d %H:%M')"
git push origin "$BRANCH"

# 後片付け
cd ~
rm -rf "$TEMP_DIR"

echo "✅ podcast.xml をプッシュしました"
