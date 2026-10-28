# CLAUDE.md — PAI最終課題（Physical AI応用1講座）

このファイルは、claude.aiでの設計議論の結論をClaude Codeに引き継ぐためのもの。作業前に必ず読むこと。

## 課題と締切
- 課題名: AI×ロボティクスによる創造的タスクの実現（東大松尾・岩澤研 Physical AI応用1講座）
- 締切: **2026-11-02（月）10:00**。結果発表は11月下旬以降
- 合格ライン: ロボットがタスクを実行する動画＋コード＋簡単なレポートの提出。優秀賞より**確実な修了を優先**
- 加点軸: 創造性 / 技術力 / 実用性 / 表現力
- 提出物
  - omnicampus: レポートPDF（`説明資料_PAI最終課題_<omnicampusアカウント名>.pdf`）＋ GitHub public リポジトリURL
  - YouTube: 1〜3分（2倍速可、倍速は明記）、タイトル `PAI最終課題_<omnicampusアカウント名>`、限定公開以上、子ども向け・年齢制限は「いいえ」
  - **氏名・所属・メールアドレスを成果物（PDF/コード/動画）に一切含めない**。APIキーも絶対にコミットしない

## 決定済みの方針
- **本線**: 講義Dockerイメージ（`airobotbook/ros2-desktop-ai-robot-book-humble`, ROS2 Humble）上の Gazebo + CRANE+ V2（卓上アーム）で、自然言語指示によるピック&プレース
- **AI層の構成**（LLMは制御ループの外、イベント駆動で呼ぶ）
  - `planner`: 自然言語＋物体座標 → サブゴールJSON（Claude API）。action語彙は `move_to / grasp / release / home` に固定し、到達範囲チェックで不正な計画を弾く
  - `controller`: サブゴールを順に実行。簡易IKで `JointTrajectory` を送る
  - `monitor`: 完了後に物体位置を再観測、目標未達なら `/monitor/replan` で再計画要求（閉ループ）
  - `perception`: まずGazebo真値から物体座標。余力があればVLM（カメラ画像）に置換
- **見送り（レポートの「今後の発展」に書く）**: 世界モデル＋MPCによるController置換、toio（押し運び・Push-T相当）への移植、VLM知覚
- 自然言語指示のレベル設計: ①座標直指定（配管確認）②物体名指定（動画の主役）③曖昧・条件付き（「色ごとに仕分けて」等、LLM推論の見せ場）④妨害→再計画（Monitorの見せ場）
- 動画構成（2〜3分）: 構成説明 → 基本ピック&プレース → 曖昧指示 → 妨害からの回復 → 工夫点と今後

## 環境
- Windows 11 + WSL2。コンテナは `docker/run.sh` で起動し、`pai2026/` を `~/pai_work` にマウント。GUIは http://localhost:6080（noVNC）
- APIキーは環境変数 `ANTHROPIC_API_KEY` のみ。`.env` は `.gitignore` 済み
- toio.py を WSL2 で usbipd 経由BLEで動かした経験あり（今回は使わない）

## 環境の実測結果（10/28 コンテナ内で確認済み。推測ではない）
- Gazebo は **Ignition Fortress (`ign gazebo`, Gazebo Sim 6.16)**。Gazebo Classic の `/model_states` は無い
  - 物体真値は `ign topic -e -t /world/default/pose/info -n 1` の名前付きテキストを perception がパースして取得（約0.2秒）
  - `ros_gz_bridge` の Pose_V→TFMessage 変換は名前が落ちるので使わない
- 起動: `ros2 launch crane_plus_gazebo no_moveit_crane_plus_with_table.launch.py`（MoveItは不要なので軽い方）
  - `docker exec -u ubuntu -e DISPLAY=:0 pai ...` で Claude Code からも起動可能。noVNC の :0 に GUI が出る
- コントローラ: `/crane_plus_arm_controller/joint_trajectory`, `/crane_plus_gripper_controller/joint_trajectory`（JointTrajectoryController, 確認済み）
- 関節名: `crane_plus_joint1..4`, `crane_plus_joint_hand`
- 座標系: ロボット base_link は世界座標 (0, 0, 1.015)。テーブル面 = 世界 z 1.015 = ロボット基準 z 0。4cmブロックの中心はロボット基準 z=0.02
- リンク寸法(URDF): 肩高さ 0.0714, 上腕 0.083, 前腕 0.0935, joint4→指先 約0.12（把持点 0.11）
- 関節の向き(実測): joint2 正=前傾, joint3・joint4 正=後ろ向き。鉛直からの前傾角は θ2=q2, θ3=q2-q3, θ4=q2-q3-q4
- `anthropic` SDK はイメージに無いので `pip3 install -U anthropic brotli`（コンテナ再作成時に再実行）。イメージ同梱の Brotli 1.0.9 のままだと SDK が `Connection error` になる
- デモ物体は `scripts/setup_world.sh` で spawn（red/blue/yellow_block, blue/green_tray）
- APIキーは `pai-final-task/.env` に書き、`docker/run.sh` が読む

## 作業ルール
- 提出対象は `ros2_ws/src/pai_llm_arm/` のみ。講義イメージやCRANE+パッケージはリポジトリに含めない
- 環境依存の名前（関節名・コントローラトピック・Gazeboモデル名）はコンテナ内で `ros2 topic list` 等で確認してから直す。推測で固定しない
- 優先順位: 動画が撮れる状態を最優先 → 曖昧指示 → 妨害復帰 → レポート。新機能より完成を優先する
- コミットメッセージ・コード・ログに個人情報を書かない

## スケジュール
- 10/28-29: テレオペ再現 → planner+controller で「自然言語→アームが動く」
- 10/30: perception＋ピック&プレース1本を動画化（修了ライン確保）
- 10/31-11/1: 曖昧指示・妨害復帰、動画編集、レポート、GitHub整理
- 11/2 朝: 提出
