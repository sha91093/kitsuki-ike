# 杵築市 池水面面積モニタリングシステム

Google Earth Engine（GEE）のSentinel-1 SARデータを用いて、大分県杵築市内30か所の池の水面面積を自動算出し、水位変動を時系列で監視するシステムです。

https://sha91093.github.io/kitsuki-ike/

## デモ

GitHub Pages でホスティング：`docs/` フォルダを GitHub Pages のソースに設定してください。

- **地図画面** (`index.html`) — Leaflet.js による杵築市地図。池マーカーをクリックすると地域・面積情報を表示
- **グラフ画面** (`pond.html?id=N`) — 撮影日ごとの水面面積を年別折れ線グラフで比較。降交／昇交軌道をタブで切り替え

## 仕組み

```
Sentinel-1 SAR（降交軌道 + 昇交軌道）
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

降交軌道（DESCENDING）と昇交軌道（ASCENDING）の両方を取得し、CSVの `orbit` 列で書き分けます。
両軌道は入射角・観測方向が異なり後方散乱特性も変わるため、グラフでは1本にまとめず軌道別のタブで表示します。

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

# 特定日付を指定（既定は降交・昇交の両軌道）
python scripts/fetch_sentinel1.py --date 2025-06-01

# 直近N日分を取得
python scripts/fetch_sentinel1.py --days-back 30

# 軌道を限定して取得
python scripts/fetch_sentinel1.py --days-back 30 --orbits descending

# 試験導入：特定の池だけ昇交軌道を取得
python scripts/fetch_sentinel1.py --days-back 30 --orbits ascending --pond-ids 3,12

# data.json を再生成
python scripts/aggregate_data.py
```

## CSVデータ形式

`data/water_area/YYYY/MM/YYYYMMDD.csv`

```csv
date,pond_id,pond_name,tiiki,ooaza,area_ha,water_area_m2,satellite,orbit
2025-06-01,3,床並溜池,山香,下,1.65,14823.0,Sentinel-1,DESCENDING
2025-06-01,3,床並溜池,山香,下,1.65,15104.2,Sentinel-1,ASCENDING
```

1つの撮影日に両軌道の観測がある場合、同じCSVに `orbit` 列で書き分けて保存します。
再取得時は `(pond_id, orbit)` をキーにマージするため、後から昇交軌道だけを追加しても
既存の降交軌道のデータは失われません。

### docs/data.json

池ごとに、従来の `timeseries`（降交軌道の全観測）に加えて、軌道別・年別の `orbit_data` を持ちます。

```json
{
  "id": "3",
  "name": "床並溜池",
  "timeseries": [ { "date": "2025-06-01", "water_area_m2": 14823.0 } ],
  "orbit_data": {
    "descending": { "2025": [ { "date": "2025-06-01", "area_m2": 14823.0 } ] },
    "ascending":  { "2025": [ { "date": "2025-06-01", "area_m2": 15104.2 } ] }
  }
}
```

観測データが1件も無い軌道は `orbit_data` からキーごと省略され、グラフ画面では該当タブが
「データなし」として無効化されます。

## 技術スタック

| 用途 | 技術 |
|---|---|
| 衛星データ取得・解析 | Google Earth Engine Python API |
| 水面検出 | Sentinel-1 VVバンド SAR後方散乱（閾値: -16 dB、両軌道共通） |
| データ管理 | pandas, CSV |
| 地図表示 | Leaflet.js |
| グラフ表示 | Plotly.js |
| 自動化 | GitHub Actions |
| ホスティング | GitHub Pages |

## 注意事項

- 降交軌道は2023年12月から、昇交軌道は導入以降のデータのみが蓄積されます（過去データの期間が軌道ごとに異なります）
- 降交・昇交では入射角と観測方向が異なるため、同じ池・同じ水位でも観測値に差が出ることがあります。軌道をまたいだ比較は行わず、タブを分けて確認してください
- SAR閾値（-16 dB）は当面は両軌道共通です。現地実測データと照合して軌道別に調整が必要な場合があります
- GEEアセット: `projects/kitsuki-kato/assets/kitsuki_ike2026`
- GEE無料枠の処理量制限に注意してください（大量の過去データ取得は時間がかかります）
