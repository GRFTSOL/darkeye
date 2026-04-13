# DarkEye - 暗黑界で、一つの目を開く

[![README · 简体中文](https://img.shields.io/badge/README%20%C2%B7%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge)](README.md)
[![README · 繁體中文](https://img.shields.io/badge/README%20%C2%B7%20%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87%EF%BC%88%E8%87%BA%E7%81%A3%EF%BC%89-555555?style=for-the-badge)](README.zh-TW.md)
[![README · 日本語](https://img.shields.io/badge/README%20%C2%B7%20%E6%97%A5%E6%9C%AC%E8%AA%9E-2ea44f?style=for-the-badge)](README.ja.md)

> 完全ローカル・プライバシー重視の成人向け動画コレクション／管理ツール。ブラウザ拡張機能による没入型の取得と、実物風 DVD ディスプレイに対応。PySide6 / Qt Quick 3D、SQLite、ローカル FastAPI とブラウザ拡張の連携、および C++ によるフォースレイアウト・グラフの高速化を備え、取得・整理・分析・可視化をひとつにまとめたソフトウェアです。

- **データと通信**：既定では実行ファイル近くの `data/` に保存（DB・設定・カバー画像など。設定で変更可）。コレクションを勝手にクラウドへ送ることはありません。通信は主にクローラーと画像等の取得、任意の更新確認（GitHub Releases）、翻訳（Google／設定した LLM API）などで発生します。

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Framework](https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/github/license/de4321/darkeye)
![GitHub last commit](https://img.shields.io/github/last-commit/de4321/darkeye)
![GitHub release](https://img.shields.io/github/v/release/de4321/darkeye)
![GitHub Repo stars](https://img.shields.io/github/stars/de4321/darkeye?style=social)
![GitHub all releases](https://img.shields.io/github/downloads/de4321/darkeye/total)

[📖 オンラインドキュメント](https://de4321.github.io/darkeye/)
[🎥 動画紹介](https://youtu.be/VCsw1D0ccgY?si=e9typx4kPnzaVFZq)
[🌐 公式サイト](https://de4321.github.io/darkeye-webpage/)
[💬 Discord](https://discord.gg/3thnEguWUk)

# 💡 クイックスタート
## ダウンロード
[![Windows 版](https://img.shields.io/badge/%20DL-Windows%20-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.2.3/DarkEye-v1.2.3.zip)
ZIP を展開し、`exe` を実行すれば利用できます。拡張機能はアプリの `extensions` フォルダに同梱されています。下記の拡張は必須ではありません。

[![Chrome/Edge 拡張](https://img.shields.io/badge/DL-Chrome%2FEdge%20ext-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.3/chrome_capture.zip) 下記の手順でインストールしてください。未インストールの場合、クローラー取得機能は使えません。お使いのブラウザ用を 1 つだけダウンロードしてください。

[![Firefox 拡張](https://img.shields.io/badge/DL-Firefox%20ext-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.3/firefox_capture.zip) 下記の手順でインストールしてください。未インストールの場合、クローラー取得機能は使えません。お使いのブラウザ用を 1 つだけダウンロードしてください。

## 拡張機能のインストール
👉 https://de4321.github.io/darkeye/usage/#_2

## 使い方
👉 https://de4321.github.io/darkeye/usage/#_3

## バージョン移行
👉 https://de4321.github.io/darkeye/faq/

通常は設定から自動更新で本体を更新できますが、ブラウザ拡張は手動でダウンロード・更新が必要です。ストアに公開できないため、より良い更新手段は現状ありません。

移行時はブラウザ拡張の更新を忘れずに。クローラーは性質上すぐ失効することがあり、フィードバックいただければ手作業で修正します。

## Jvedio からのデータ移行
👉 https://de4321.github.io/darkeye/usage/#jvedio

# コミュニティ

問題やアイデアがありますか？Discord コミュニティへどうぞ：https://discord.gg/3thnEguWUk

- 初心者向けのサポート
ドキュメントを読んで分からない点があればお気軽にどうぞ。オンラインドキュメントは引き続き整備中です。

- 進展を先に知る
「新機能・開発の進み方・プレリリースはまず Discord で話します。」

- 方向性に参加する
「ロードマップに影響したい方は議論に参加してください。」

# 参考プロジェクト

- [mdcz](https://github.com/ShotHeadman/mdcz) ローカル動画ファイル名から品番を抽出するコードの参考、および NFO 互換の試み
- [Jvedio](https://github.com/hitchao/Jvedio) データベース連携・データのエクスポート
- [JavSP](https://github.com/Yuukiy/JavSP) 一部サイトのクローラー実装の参考
- [JAV-JHS](https://sleazyfork.org/zh-CN/scripts/558525-jav-jhs) javdb・FC2 などの情報取得の参考


# 🚀 開発の方向
- 1.0 基本ツールの完成（フォースレイアウト・グラフで作品関係の探索、コレクション体験の強化）
- 2.0 UGC、分散同期
- 3.0 機械学習によるレコメンド

## 機能
- [x] 作品・女優・男優・タグの手動追加と CRUD、一部クローラー
- [x] 自慰・性交・朝立ち記録の手動追加と CRUD
- [x] 分析チャート・データ表示（一部未完了）
- [x] 実物風 DVD ビュー
- [x] 作品の絞り込み画面
- [x] Chrome / Edge / Firefox 用拡張、没入型の情報取得、javtxt・javlib・javdb など対話的取得
- [x] 複数ソースのクローラー（javlib, avdanyuwiki, javtxt, javdb, minnano-av など）。一般作品の取得に有効で、ボット対策の突破もしやすい
- [x] フォースレイアウト・グラフで関連を表示、約1 万ノードで 60fps 目安
- [x] ローカル動画の検索とクローラー一覧への追加
- [x] バックアップ、プライベートライブラリからお気に入り品番を再構築
- [x] JSON 設定駆動の外部リンクジャンプ（カスタム可）
- [x] テーマ切替（3D シーンはライト／ダーク未対応）
- [x] 一部スクリーンショット、女優画面で C キー
- [x] NFO インポート（試験中）
- [x] Jvedio から NFO エクスポート（試験中）
- [ ] NFO エクスポート（仕様の合意後）
- [x] 更新の自動検知とダウンロード
- [x] LLM 翻訳・ワンクリックで上書き翻訳



実物風 DVD
![コレクション](docs/assets/dvd.jpg)
![展開](docs/assets/dvd2.jpg)
![女優](docs/assets/actress.jpg)

グラフで関係を発見
![フォースレイアウト・グラフ](docs/assets/directforceview.jpg)
データの分析
![チャート](docs/assets/chart.jpg)
![複数作品](docs/assets/mutiwork.jpg)
![編集画面](docs/assets/edit.jpg)

javtxt を例にした拡張の動作です。拡張を有効にするとローカルアプリと連携し、「追加」をクリックするとクローラーが起動してローカルに取り込みます。javlib・javdb にも対応。画面中央の「コレクション」「収録」はサイト単体には出ず、拡張とローカルアプリを開いたときだけ表示されます。
![javtxt の例](docs/assets/capture.JPG)

## クローラー
作品については、公開日、監督、中日タイトルとあらすじ、女優・男優（いれば）、タグ、カバー、再生時間、メーカー、レーベル、シリーズ、スチルなどを取得します。

女優については、アイコン、生年月日、デビュー日、スリーサイズ、身長・カップ、旧名など。旧名の更新ルートはまだありません。最初から旧名で登録していると不整合が出ることがあります。

初回の取得では javlib のボット対策が必ず発動します。およそ 100 回に 1 回程度 javdb のクリック確認が出ることもあり、手で通せば続行できます。

ソフト側ではプロキシ問題を解決しません。対象サイトがブラウザで開ければクローラーで取得できます。


# 🚀 開発
👉 詳細は次をご覧ください：https://de4321.github.io/darkeye/development/


# 📚 ドキュメント
👉 完全なドキュメントは次をご覧ください：https://de4321.github.io/darkeye/



