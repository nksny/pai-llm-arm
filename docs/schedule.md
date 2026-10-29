# スケジュール（締切 2026-11-02 10:00）

## 進捗（10/29 時点）
- [x] 環境構築（Ignition Gazebo + CRANE+ V2、関節名・座標系・IK を実測）
- [x] 自然言語 → LLM計画 → 実行 → 判定 の通し動作（「赤いブロックを青いトレイに置いて」成功）
- [x] 曖昧指示（「青いブロックを同じ色のトレイに置いて」成功）
- [x] 妨害からの復帰（把持後にブロックを移動 → monitor が検知 → 再計画 → 緑のトレイへ載置成功）
- [x] 複数物体の指示（「色ごとに仕分けて」: 赤→赤トレイ, 青→青トレイ, 黄は対応トレイ無しと判断）
- [x] 動画素材の録画（基本・曖昧・妨害復帰・仕分けの4本, `videos/`）
- [ ] 動画編集（1〜3分に）
- [ ] レポートPDF
- [x] GitHub public へ push（https://github.com/nksny/pai-llm-arm）、個人情報チェック済み

## 残り日程
- 10/29: 済（仕分け確認、GUI設定・録画スクリプト整備、4本録画）
- 10/30: 動画編集、レポート執筆開始
- 10/31-11/1: 動画編集（1〜3分）、レポート仕上げ、README整理、GitHub push
- 11/2 朝: 提出（omnicampus: PDF + GitHub URL / YouTube 限定公開以上）

## 録画メモ
- `ros2 launch pai_llm_arm demo_gazebo.launch.py` で 1280x720・固定カメラの Gazebo を起動し、`scripts/run_demo.sh <name> "<指示>" [妨害秒]` で録画込みで1本実行
- 録画中は noVNC のブラウザでマウスを動かさない（カーソルが映り込む）
- カメラ追従: `ign service -s /gui/follow --reqtype ignition.msgs.StringMsg --reptype ignition.msgs.Boolean --timeout 2000 --req 'data: "crane_plus"'`
- 妨害は Gazebo GUI の移動ツールでブロックをドラッグするか、`ign service -s /world/default/set_pose ...` で実施
