# 杵築市 池水面面積モニタリングシステム

Google Earth Engine（GEE）のSentinel-1 SARデータを用いて、大分県杵築市内30か所の池の水面面積を自動算出し、水位変動を時系列で監視するシステムです。

https://sha91093.github.io/kitsuki-ike/

## デモ

GitHub Pages でホスティング：`docs/` フォルダを GitHub Pages のソースに設定してください。

- **地図画面** (`index.html`) — Leaflet.js による杵築市地図。池マーカーをクリックすると地域・面積情報を表示
- **グラフ画面** (`pond.html?id=N`) — 撮影日ごとの水面面積を年別折れ線グラフで比較

## 仕組み

```
Sentinel-1 SAR（降交軌道）
        ↓ Google Earth Engine
  水面ピクセル検出（VV < -16 dB）
        ↓
  池ポリゴンごとに面積集計（10m×10m）
        ↓
  data/water_area/YYYY/MM/YYYYMMDD.csv
        ↓ aggregate_data.py
  docs/data.json
        ↓ GitHub Pages
  ブラウザ（地図 + グラフ）
```

GitHub Actions が毎週月・木曜日に自動実行し、最新データを取得してリポジトリに反映します。

## ディレクトリ構成

```
kitsuki-ike/
├── 杵築池リスト名前入り.csv          # 池マスタ（simple_id, name, tiiki, ooaza, area_ha, latitude, longitude）
├── data/
│   └── water_area/
│       └── YYYY/MM/YYYYMMDD.csv      # 撮影日ごとの水面面積データ
├── docs/
│   ├── index.html                    # 地図インターフェース
│   ├── pond.html                     # 年別比較グラフページ
│   ├── data.json                     # フロントエンド用集計データ
│   └── assets/
│       ├── app.js                    # 地図ロジック
│       ├── chart.js                  # グラフロジック
│       └── style.css                 # スタイル
├── scripts/
│   ├── fetch_sentinel1.py            # GEEからデータ取得・水面面積算出
│   ├── mosaic_and_analyze.py         # モザイク処理・SAR閾値分析
│   ├── aggregate_data.py             # CSV集計・data.json生成
│   └── utils.py                      # 共通ユーティリティ
├── requirements.txt
└── .github/
    └── workflows/
        └── update_water_area.yml     # GitHub Actions定義
```

## セットアップ

### 1. GEEサービスアカウントの準備

1. [Google Cloud Console](https://console.cloud.google.com/) でサービスアカウントを作成
2. Earth Engine API を有効化
3. GEEプロジェクト `仮名` にサービスアカウントを登録
4. JSON キーファイルをダウンロード

### 2. GitHub Secrets の設定

| Secret名 | 内容 |
|---|---|
| `GEE_SERVICE_ACCOUNT_KEY` | サービスアカウントJSONキーの内容（全文） |

Settings → Secrets and variables → Actions から登録してください。

### 3. GitHub Pages の有効化

Settings → Pages → Source を **Deploy from a branch** に設定し、ブランチと `/docs` フォルダを指定してください。

### 4. 池リストCSVの配置

リポジトリルートに `杵築池リスト名前入り.csv` を配置してください。

必須カラム：

| カラム名 | 説明 |
|---|---|
| `simple_id` | GEEアセット `kitsuki_ike2026` の `simple_id` フィールドと一致する整数ID |
| `name` | 池名 |
| `tiiki` | 地域名 |
| `ooaza` | 大字 |
| `area_ha` | 登録面積（ha） |
| `latitude` | 緯度 |
| `longitude` | 経度 |

## データ取得の実行

### 通常更新（直近14日分）

GitHub Actions の **Run workflow** から手動実行、または月・木の自動実行を待ちます。

### 初回・過去データの一括取得

1. GitHub Actions → 「水面面積データ更新」→ **Run workflow**
2. `days_back` に遡りたい日数を指定して実行

| 取得したい期間 | days_back の目安 |
|---|---|
| 過去2年（2024年1月〜） | `800` |
| 過去1年 | `400` |
| 直近3か月 | `90` |

既に取得済みの日付はスキップされるため、重複実行しても問題ありません。

### ローカル実行

```bash
pip install -r requirements.txt
earthengine authenticate

# 特定日付を指定
python scripts/fetch_sentinel1.py --date 2025-06-01

# 直近N日分を取得
python scripts/fetch_sentinel1.py --days-back 30

# data.json を再生成
python scripts/aggregate_data.py
```

## CSVデータ形式

`data/water_area/YYYY/MM/YYYYMMDD.csv`

```csv
date,pond_id,pond_name,tiiki,ooaza,area_ha,water_area_m2,satellite,orbit
2025-06-01,3,床並溜池,山香,下,1.65,14823.0,Sentinel-1,DESCENDING
```

## 技術スタック

| 用途 | 技術 |
|---|---|
| 衛星データ取得・解析 | Google Earth Engine Python API |
| 水面検出 | Sentinel-1 VVバンド SAR後方散乱（閾値: -16 dB） |
| データ管理 | pandas, CSV |
| 地図表示 | Leaflet.js |
| グラフ表示 | Plotly.js |
| 自動化 | GitHub Actions |
| ホスティング | GitHub Pages |

## 注意事項

- Sentinel-1 降交軌道のみ使用（過去データとの一貫性のため）
- SAR閾値（-16 dB）は現地実測データと照合して調整が必要な場合があります
- GEEアセット: `projects/kitsuki-kato/assets/kitsuki_ike2026`
- GEE無料枠の処理量制限に注意してください（大量の過去データ取得は時間がかかります）
