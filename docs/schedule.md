# スケジュール（締切 2026-11-02 10:00）

## 進捗（10/28 時点）
- [x] 環境構築（Ignition Gazebo + CRANE+ V2、関節名・座標系・IK を実測）
- [x] 自然言語 → LLM計画 → 実行 → 判定 の通し動作（「赤いブロックを青いトレイに置いて」成功）
- [x] 曖昧指示（「青いブロックを同じ色のトレイに置いて」成功）
- [x] 妨害からの復帰（把持後にブロックを移動 → monitor が検知 → 再計画 → 緑のトレイへ載置成功）
- [ ] 動画撮影（修了ライン確保）
- [ ] レポートPDF
- [ ] GitHub public へ push、個人情報チェック

## 残り日程
- 10/29: 複数物体の指示（「色ごとに仕分けて」）の確認、Gazebo画面の見栄え調整、録画手順の確立、基本デモ1本を録画
- 10/30: 曖昧指示・妨害復帰の録画、レポート執筆開始
- 10/31-11/1: 動画編集（1〜3分）、レポート仕上げ、README整理、GitHub push
- 11/2 朝: 提出（omnicampus: PDF + GitHub URL / YouTube 限定公開以上）

## 録画メモ
- noVNC(http://localhost:6080) の Gazebo ウィンドウを手動で最大化してから、母機で画面録画（Win+G など）
- カメラ追従: `ign service -s /gui/follow --reqtype ignition.msgs.StringMsg --reptype ignition.msgs.Boolean --timeout 2000 --req 'data: "crane_plus"'`
- 妨害は Gazebo GUI の移動ツールでブロックをドラッグするか、`ign service -s /world/default/set_pose ...` で実施
